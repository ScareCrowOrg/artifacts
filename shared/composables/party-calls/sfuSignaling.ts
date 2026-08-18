/**
 * @file party-calls/sfuSignaling.ts
 * @description WebRTC/SFU primitives for the usePartyCalls composable
 * (Cloudflare Calls / WebRTC).  Extracted VERBATIM from the former monolithic
 * ``usePartyCalls.ts`` (sections "Multi-user SFU helpers" + the shell helper
 * ``_createAndSetOffer``).
 *
 * Dependency graph: imports ``_apiFetchJson`` from ``./http`` + state from
 * ``./state``.  No reverse imports.  See ``party-calls/README.md``.
 */

import { _apiFetchJson } from './http'
import {
  log,
  state,
  _pendingSubscribeMids,
  _remoteMidToTrackName,
  _transceiverMeta,
} from './state'
import type { SfuTrackResult } from './types'

// ─────────────────────────────────────────────────────────────────────────────
// SFU / Cloudflare Calls primitives
// ─────────────────────────────────────────────────────────────────────────────

/** Resolve true once the peer connection reaches 'connected'/'completed'. */
export function _waitForIceConnected(
  pc: RTCPeerConnection,
  timeoutMs: number,
): Promise<boolean> {
  return new Promise((resolve) => {
    const done = (ok: boolean) => {
      pc.removeEventListener('iceconnectionstatechange', onChange)
      window.clearTimeout(timer)
      resolve(ok)
    }
    const onChange = () => {
      const s = pc.iceConnectionState
      if (s === 'connected' || s === 'completed') done(true)
      else if (s === 'failed' || s === 'disconnected' || s === 'closed') done(false)
    }
    const timer = window.setTimeout(
      () => done(pc.iceConnectionState === 'connected' || pc.iceConnectionState === 'completed'),
      timeoutMs,
    )
    pc.addEventListener('iceconnectionstatechange', onChange)
    onChange() // reflect the current state immediately
  })
}

/**
 * Register the caller's OWN local tracks on the Cloudflare SFU via
 * ``/tracks/new`` with ``location:'local'`` AFTER the peer connection connects.
 *
 * ROOT CAUSE FIX (F3 ciclo 4): the SFU IGNORES the ``tracks`` array sent to
 * ``/sessions/new`` — the Cloudflare OpenAPI ``NewSessionRequest`` has no
 * ``tracks`` field — so a publisher session created that way has zero tracks
 * on the SFU (verified live: ``GET /sessions/{sid}`` → ``tracks: []`` even
 * while connected).  Tracks are only registered via ``/tracks/new`` with
 * ``location:'local'``, and that call is rejected with HTTP 425
 * ("Session is not ready yet. Please ensure the PeerConnection is connected")
 * until ICE/DTLS is established.  Without this step every remote subscription
 * returns ``not_found_track_error`` (F7 ciclo 2/3 — friendly AND native IDs).
 */
export async function _registerLocalTracksOnSfu(
  pc: RTCPeerConnection,
  sessionId: string,
  trackObjs: Array<{ location: 'local'; mid: string; trackName: string }>,
  sessionDescription?: { type: string; sdp: string },
): Promise<any> {
  if (!state._currentSessionId || !trackObjs.length) return null

  const connected = await _waitForIceConnected(pc, 10_000)
  if (!connected) {
    log.warn('[publish] ICE not connected within timeout — local tracks NOT registered on SFU')
    return null
  }

  try {
    // CICLO 2: the publisher's renegotiation offer (with the new m= video for
    // the screen) is sent ALONG with the track registration.  The Cloudflare
    // tracks/new lifecycle accepts ``{tracks, sessionDescription}`` — the
    // offering side sends its offer here and receives the SFU's answer/offer
    // back (``sessionDescription`` + ``requiresImmediateRenegotiation``) to
    // close the renegotiation.  Only include the offer when it carries a
    // non-empty SDP — never send an empty/absent SDP (the SFU would reject it
    // and the caller cannot answer).  When omitted the body stays exactly
    // ``{ tracks }`` — startCall keeps the legacy behavior (its tracks were
    // already negotiated via /calls/session).
    const body: Record<string, unknown> = { tracks: trackObjs }
    if (sessionDescription && sessionDescription.sdp) {
      body.sessionDescription = sessionDescription
    }
    const result = await _apiFetchJson(
      `/calls/sessions/${sessionId}/tracks/new`,
      { method: 'POST', body: JSON.stringify(body) },
    )
    // PERMANENTE: the per-track resolution of the registration — a track with an
    // errorCode was NOT resolved on the SFU and must never be advertised.
    const perTrack = (Array.isArray(result?.tracks) ? result.tracks : [])
      .map((t: SfuTrackResult) => (t && typeof t === 'object'
        ? { trackName: t.trackName, mid: t.mid, errorCode: t.errorCode, errorDescription: t.errorDescription }
        : t))
    log.warn(
      '[publish] local tracks registered on SFU session=%s answer_type=%s answer_sdp_len=%d requires_renog=%s per_track=%j',
      sessionId,
      result?.sessionDescription?.type,
      String(result?.sessionDescription?.sdp || '').length,
      String(result?.requiresImmediateRenegotiation),
      perTrack,
    )
    // Return the parsed response so the caller (shareStream) can inspect the
    // SFU's sessionDescription (a direct answer OR a renegotiation offer) and
    // close the publisher renegotiation.  Null on any failure path above.
    return result
  } catch (err) {
    log.warn(
      '[publish] local track registration failed session=%s: %s',
      sessionId, err instanceof Error ? err.message : String(err),
    )
    return null
  }
}

/**
 * Stop the local receiver transceivers for the given mids and drop their
 * mid → trackName mappings (S2 subscriber side).
 *
 * The Cloudflare SFU is a black box and the backend has no tracks/remove
 * endpoint, so the subscriber cannot un-subscribe via signaling.  Locally,
 * ``transceiver.stop()`` + ``removeTransceiver()`` stop the receiver
 * immediately: RTP from the SFU may still arrive on the wire but is no longer
 * decoded or surfaced — closing the S2 leak where a peer that already
 * subscribed keeps receiving the shared screen after the publisher stops.
 */
export function _teardownRemoteMedia(mids: string[], callerLabel = 'unknown'): void {
  if (!state._pc || !mids.length) return
  // Prove WHICH path stopped the receiver transceivers ('cleanup' =
  // _cleanupEndedRemoteTrack / end-of-track handler, 'prune' = discovery B2
  // removeScreenMapping).  A 'cleanup' teardown of mid=1 logged right after the
  // merge confirms the spurious end-of-track handler is the one stopping the
  // just-received screen — NOT the prune (which would also bump
  // owners_to_prune/screen_removed in the discovery end prune).
  log.warn('[teardown] caller=%s mids=%s', callerLabel, JSON.stringify(mids))
  for (const mid of mids) {
    // F3 FIX (ITER_1 guest-screenshare CICLO 2): never tear down a subscription
    // still in flight — a concurrent prune can race the incoming screen
    // (tx.stop() would kill the transceiver the ontrack is about to fire on, and
    // the map/WeakMap deletion is the race H3 drop).  The pending protection
    // releases on the ontrack or after the 5s timeout.
    if (_pendingSubscribeMids.has(mid)) {
      log.warn('[pending] protect mid=%s prune=teardown', mid)
      continue
    }
    const tx = state._pc.getTransceivers().find((t) => t.mid === mid)
    if (tx && tx.receiver) {
      try {
        tx.stop()
        // F12 FIX (bug-hardening): removeTransceiver is not exposed on the
        // installed lib.dom RTCPeerConnection type (TS2339) — safe-cast so
        // `tsc --noEmit` is clean while keeping the real browser API call
        // (removeTransceiver stops + removes the transceiver; transceiver.stop()
        // above is the fallback when the method is absent).
        ;(state._pc as RTCPeerConnection & { removeTransceiver?: (t: RTCRtpTransceiver) => void }).removeTransceiver?.(tx)
      } catch {
        try { tx.direction = 'inactive' } catch { /* ignore */ }
      }
    }
    _remoteMidToTrackName.delete(mid)
    // F3 FIX (ITER_1 H3): drop the transceiver-scoped meta for the same mid.
    // Uses the in-scope `tx` because removeTransceiver (above) already removed
    // it from state._pc.getTransceivers() — a fresh _dropTransceiverMeta lookup would
    // miss it and leak the entry until GC.
    if (tx) _transceiverMeta.delete(tx)
  }
}

/**
 * Answer an SFU-generated renegotiation offer via PUT /renegotiate.
 *
 * Used by the publisher after a ``tracks/close`` that returns
 * ``requiresImmediateRenegotiation`` + a ``sessionDescription`` (offer), and by
 * the subscriber after ``tracks/new`` (remote).  The Cloudflare ``renegotiate``
 * proxy is ANSWER-only (406 when sent an offer) — the SFU always generates the
 * offer and the client sends back an answer.
 */
export async function _answerSfuRenegotiationOffer(respSd: RTCSessionDescriptionInit): Promise<void> {
  if (!state._pc || !state._currentSessionId) return
  await state._pc.setRemoteDescription(new RTCSessionDescription(respSd))
  const localAnswer = await state._pc.createAnswer()
  await state._pc.setLocalDescription(localAnswer)
  await _apiFetchJson(
    `/calls/sessions/${state._currentSessionId}/renegotiate`,
    {
      method: 'PUT',
      body: JSON.stringify({
        sessionDescription: { type: localAnswer.type, sdp: localAnswer.sdp },
      }),
    },
  )
  log.warn(
    '[stopSharing] tracks/close renegotiation answered session=%s answer_type=%s',
    state._currentSessionId, localAnswer.type,
  )
}

/**
 * F9 FIX (bug-hardening): single implementation of the PUBLISHER renegotiation
 * close after a ``tracks/new`` (local) response — previously byte-identical in
 * ``_enableLocalTrack`` and ``shareStream`` (deduplicated).  Handles the three
 * response shapes:
 *
 *  1. ``requiresImmediateRenegotiation`` + SFU offer → answer via
 *     ``_answerSfuRenegotiationOffer`` (PUT /renegotiate);
 *  2. direct answer SDP → apply as-is via ``setRemoteDescription``;
 *  3. nothing usable (regResult null/absent or a per-track errorCode) → G2:
 *     ROLL BACK the local offer (``setLocalDescription({type:'rollback'})``) so
 *     the PC returns to 'stable' instead of wedging in 'have-local-offer' — a
 *     wedged PC makes every later ``createOffer`` throw ``InvalidStateError``
 *     and the call is unrecoverable until ``hangUp``.
 *
 * Returns ``true`` when an SDP was applied (renegotiation closed cleanly);
 * ``false`` when nothing was applied — the caller MUST NOT publish the track to
 * the registry/presence (the SFU never registered it).
 */
export async function _closeLocalRenegotiation(regResult: any): Promise<boolean> {
  if (!state._pc || !state._currentSessionId) return false
  const respSd = regResult?.sessionDescription
  const respSdp = respSd?.sdp ? String(respSd.sdp) : ''
  // R#2 (review #3077): a per-track errorCode means the SFU did NOT resolve the
  // track — the caller MUST NOT publish it, whatever SDP shape the response
  // carries.  Checked BEFORE any setRemoteDescription: a rollback only works
  // from 'have-local-offer' — after an answer is applied the PC is 'stable' and
  // cannot roll back.  This closes the hole where a direct-answer SDP carrying
  // per-track errors was applied and returned true → the track announced in
  // registry/presence → subscribers stuck on not_found_track_error forever.
  const trackErrors = (Array.isArray(regResult?.tracks) ? regResult.tracks : [])
    .filter((t: SfuTrackResult) => t && typeof t === 'object' && (t.errorCode || t.errorDescription))
  if (trackErrors.length > 0) {
    log.warn('[closeLocalRenegotiation] per-track errorCode — rolling back local offer track_errors=%j', trackErrors)
    try {
      await state._pc.setLocalDescription({ type: 'rollback' } as RTCSessionDescriptionInit)
    } catch (rollbackErr) {
      log.warn('[closeLocalRenegotiation] rollback failed: %s',
        rollbackErr instanceof Error ? rollbackErr.message : String(rollbackErr))
    }
    return false
  }
  if (regResult?.requiresImmediateRenegotiation && respSd?.type === 'offer' && respSdp.length > 0) {
    await _answerSfuRenegotiationOffer(respSd)
    return true
  }
  if (respSd?.type === 'answer' && respSdp.length > 0) {
    await state._pc.setRemoteDescription(new RTCSessionDescription(respSd))
    return true
  }
  if (!regResult) {
    log.warn('[closeLocalRenegotiation] no SFU response — rolling back local offer')
  } else {
    log.warn('[closeLocalRenegotiation] no offer/answer from SFU track_errors=%j', trackErrors)
  }
  try {
    await state._pc.setLocalDescription({ type: 'rollback' } as RTCSessionDescriptionInit)
  } catch (rollbackErr) {
    log.warn('[closeLocalRenegotiation] rollback failed: %s',
      rollbackErr instanceof Error ? rollbackErr.message : String(rollbackErr))
  }
  return false
}

/**
 * Remove a published track from the Cloudflare SFU session (backend
 * ``DELETE /calls/sessions/{sid}/tracks/{mid}`` → Cloudflare
 * ``PUT /sessions/{sid}/tracks/close``).  Called by stopSharing after
 * ``RTCRtpSender.removeTrack()`` — this is what actually tells the SFU the
 * track is gone.  Replaces the previous ``PUT /renegotiate``-with-offer path,
 * which the Cloudflare contract rejects (``406 sessionDescription.type=answer
 * is expected`` → 502 on every stop).
 *
 * The ``mid`` argument is the publisher's sendonly screen-transceiver mid
 * (``state._orphanScreenTx.mid``), which survives ``removeTrack`` — NOT the native
 * MediaStreamTrack id (``_screenTrackId``).  The Cloudflare ``CloseTrackObject``
 * identifies tracks by transceiver ``mid``.
 *
 * The backend proxies this DELETE to Cloudflare ``PUT .../tracks/close`` and
 * sends ``force: true`` by default (the real API REQUIRES the field — a body
 * without it returns 400 ``decoding_error: Body JSON validation error: force``
 * → 502).  ``force:true`` stops just the data flow without WebRTC renegotiation
 * — simplest, keeps the m-section (compatible with the orphan transceiver
 * reuse of AC4).  This DELETE sends no body; the backend fills ``force=true``.
 *
 * When the SFU answers ``tracks/close`` with ``requiresImmediateRenegotiation``
 * + a ``sessionDescription`` (offer), the publisher answers it via ``PUT
 * /renegotiate`` so the m-section is really removed (mirror of the subscriber
 * flow in _subscribeToRemoteTracks).  Non-fatal: on failure the SFU reaper
 * still signals ``event=ended`` to already-subscribed peers (safety net) and
 * the registry/presence already drop the screen, so new subscribers stop
 * seeing it.
 */
export async function _removeTrackFromSfu(mid: string): Promise<void> {
  if (!state._currentSessionId) return
  try {
    const result = await _apiFetchJson(
      `/calls/sessions/${state._currentSessionId}/tracks/${encodeURIComponent(mid)}`,
      { method: 'DELETE' },
    )
    log.info(
      '[stopSharing] track removed from SFU session=%s track=%s',
      state._currentSessionId, mid,
    )
    // The tracks/close response — the `force` blind spot (whether the SFU asks
    // for a renegotiation answer).
    const respSd = result?.sessionDescription
    const respSdp = respSd?.sdp ? String(respSd.sdp) : ''
    // P6: if the SFU asks for a renegotiation after the close, answer the offer
    // so the m-section is really removed.  This is the publisher mirror of the
    // subscriber answer flow (_subscribeToRemoteTracks) — the SFU generates the
    // offer, the client sends back an ANSWER via PUT /renegotiate.
    if (result?.requiresImmediateRenegotiation === true && respSd?.type === 'offer' && respSdp.length > 0) {
      await _answerSfuRenegotiationOffer(respSd)
    }
  } catch (err) {
    log.warn(
      '[stopSharing] tracks/remove failed session=%s track=%s: %s',
      state._currentSessionId, mid,
      err instanceof Error ? err.message : String(err),
    )
  }
}

/** Build the SDP offer and set it as the local description. */
export async function _createAndSetOffer(pc: RTCPeerConnection): Promise<RTCSessionDescriptionInit> {
  const offer = await pc.createOffer()
  await pc.setLocalDescription(offer)
  return offer
}
