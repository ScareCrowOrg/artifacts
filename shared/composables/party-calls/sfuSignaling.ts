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
  _withNegotiationLock,
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
      if (s === 'connected' || s === 'completed') {
        // F4 (review #3078): record that THIS PC's ICE has reached a usable
        // state — the 2D/b gate uses it to tell a mid-call restart (short grace)
        // from the initial connection (full wait).
        state._iceWasEverConnected = true
        done(true)
      } else if (s === 'failed' || s === 'disconnected' || s === 'closed') done(false)
    }
    const timer = window.setTimeout(
      () => {
        const connected = pc.iceConnectionState === 'connected' || pc.iceConnectionState === 'completed'
        if (connected) state._iceWasEverConnected = true
        done(connected)
      },
      timeoutMs,
    )
    pc.addEventListener('iceconnectionstatechange', onChange)
    onChange() // reflect the current state immediately
  })
}

/**
 * FIX (party-cell-screen-share-sfu-register-fail, CHANGE_PLAN 2D/a): verify the
 * peer connection is in a HEALTHY, STABLE state before a local renegotiation
 * (the `shareStream` publish) builds its offer.
 *
 * Guard 1 — ``signalingState === 'stable'``: a renegotiation still in flight
 * (e.g. a remote subscribe that just landed on this PC) must settle first;
 * creating an offer mid-renegotiation throws ``InvalidStateError`` and wedges
 * the PC.
 *
 * Guard 2 — terminal ICE fails fast: 'failed'/'disconnected'/'closed' means
 * there is nothing to negotiate with.  NON-terminal ICE ('new'/'connecting') is
 * ALLOWED to proceed — the register gate in ``_registerLocalTracksOnSfu`` gives
 * a short grace and then sends the offer, which is what completes a restart
 * (waiting for ICE here would deadlock against the answer only the POST brings
 * back — the diagnosed "publish never sent").
 *
 * F3 (review #3078): callers MUST run this OUTSIDE ``_withNegotiationLock`` (the
 * lock already guarantees no concurrent renegotiation is in flight, so a PC
 * stuck non-stable is a pre-existing wedge — a bounded 3s wait detects it, then
 * fails fast instead of holding the global lock for the full poll).  Default
 * timeout shortened to 3s for that reason.
 *
 * Returns true when the PC is ready to renegotiate, false otherwise.
 */
export async function _ensurePcReadyForNegotiation(
  pc: RTCPeerConnection,
  timeoutMs = 3_000,
): Promise<boolean> {
  const deadline = Date.now() + timeoutMs
  while (pc.signalingState !== 'stable') {
    if (Date.now() > deadline) {
      log.warn('[publish] PC not stable-signaling within %dms — aborting share renegotiation', timeoutMs)
      return false
    }
    await new Promise((resolve) => setTimeout(resolve, 50))
  }
  const ice = pc.iceConnectionState
  if (ice === 'failed' || ice === 'disconnected' || ice === 'closed') {
    log.warn('[publish] ICE in terminal state %s — cannot start screen share', ice)
    return false
  }
  return true
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

  // 2D/b (party-cell-screen-share-sfu-register-fail): the ICE gate must not
  // deadlock a MID-CALL renegotiation.  An established session whose ICE is
  // 'new'/'connecting' is mid-restart — the restart completes when the offer we
  // are about to send is ANSWERED by the SFU, so waiting the full 10s here only
  // guarantees failure (the diagnosed "ICE stuck in 'new', publish never sent").
  // TERMINAL ICE ('failed'/'disconnected'/'closed') hard-fails.
  //
  // F4 (review #3078): distinguish the RESTART from the INITIAL connection.
  // ``state._iceWasEverConnected`` is true once this PC's ICE reached
  // connected/completed — a 'new'/'connecting' state then IS a mid-call restart
  // → 3s grace then send the offer (the offer completes the restart).  When the
  // PC NEVER connected (e.g. a fast camera/mic opt-in while ICE is still
  // 'connecting'), send the offer only after the full wait — an early POST
  // would 425 ("Session is not ready yet") and fail the 1st opt-in on a slow
  // connection (a regression the old 10s wait did not have).
  const iceState = pc.iceConnectionState
  if (iceState === 'failed' || iceState === 'disconnected' || iceState === 'closed') {
    log.warn('[publish] ICE in terminal state %s — local tracks NOT registered on SFU', iceState)
    return null
  }
  if (iceState !== 'connected' && iceState !== 'completed') {
    const graceMs = state._iceWasEverConnected ? 3_000 : 10_000
    const connected = await _waitForIceConnected(pc, graceMs)
    if (!connected) {
      if (state._iceWasEverConnected) {
        log.warn(
          '[publish] ICE %s after grace — sending tracks/new anyway (the offer completes the restart)',
          pc.iceConnectionState,
        )
      } else {
        log.warn('[publish] ICE not connected within timeout — local tracks NOT registered on SFU')
        return null
      }
    }
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
    // F1 (review #3078): the SFU-offer branch must be as rollback-protected as
    // the answer branch below.  A browser REJECTING the SFU's offer at
    // setRemoteDescription (inside _answerSfuRenegotiationOffer) would otherwise
    // escape, wedge the PC in have-local-offer (no rollback), surface a raw
    // error via the caller's catch, skip the G2 cleanup — the same class as the
    // diagnosed mid='2' Surface B, just on the offer branch.
    try {
      await _answerSfuRenegotiationOffer(respSd)
    } catch (applyErr) {
      log.warn(
        '[closeLocalRenegotiation] SFU offer rejected by browser — rolling back local offer: %s',
        applyErr instanceof Error ? applyErr.message : String(applyErr),
      )
      try {
        await state._pc.setLocalDescription({ type: 'rollback' } as RTCSessionDescriptionInit)
      } catch (rollbackErr) {
        log.warn('[closeLocalRenegotiation] rollback failed: %s',
          rollbackErr instanceof Error ? rollbackErr.message : String(rollbackErr))
      }
      return false
    }
    return true
  }
  if (respSd?.type === 'answer' && respSdp.length > 0) {
    // 2D (party-cell-screen-share-sfu-register-fail): an SFU answer that the
    // browser REJECTS (the diagnosed `Failed to set remote video description
    // send parameters for m-section with mid='2'` on the 2nd screen share) must
    // NOT wedge the PC or surface as a raw error.  Roll back the local offer
    // (PC back to 'stable', recoverable) and return false → the caller shows the
    // friendly G2 message instead of the raw setRemoteDescription error.
    try {
      await state._pc.setRemoteDescription(new RTCSessionDescription(respSd))
    } catch (applyErr) {
      log.warn(
        '[closeLocalRenegotiation] SFU answer rejected by browser — rolling back local offer: %s',
        applyErr instanceof Error ? applyErr.message : String(applyErr),
      )
      try {
        await state._pc.setLocalDescription({ type: 'rollback' } as RTCSessionDescriptionInit)
      } catch (rollbackErr) {
        log.warn('[closeLocalRenegotiation] rollback failed: %s',
          rollbackErr instanceof Error ? rollbackErr.message : String(rollbackErr))
      }
      return false
    }
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
 * The ``mid`` argument is a publisher's sendonly screen-transceiver mid (the
 * per-instance ``ctx.screenState.orphanVideoTx.mid`` / ``orphanAudioTx.mid`` —
 * Ajuste 1 + F13), which survives ``removeTrack`` — NOT the native
 * MediaStreamTrack id.  The Cloudflare ``CloseTrackObject`` identifies tracks by
 * transceiver ``mid``.
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
    // F2 (review #3078): this renegotiation mutates the SAME peer connection the
    // publish/subscribe serialize — run it under the lock too so a stopShare
    // answer can never overlap a concurrent shareStream/subscribe.
    if (result?.requiresImmediateRenegotiation === true && respSd?.type === 'offer' && respSdp.length > 0) {
      await _withNegotiationLock(() => _answerSfuRenegotiationOffer(respSd))
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

// ─────────────────────────────────────────────────────────────────────────────
// Screen-share transceiver helpers (Ajuste 1 + F13 — issue
// party-calls-screen-audio-session-isolation).  Extracted from localMedia.ts so
// that module stays under RULESET 1.1's 650-line limit.
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Allocate a DEDICATED sendonly transceiver for a screen-share track (the
 * screen VIDEO or its DISPLAY-AUDIO).
 *
 * CICLO 3: never addTrack — addTrack would REUSE an existing recvonly
 * transceiver (e.g. the one subscribed to B's camera/mic) making it sendrecv on
 * the same m-section; the SFU accepts that offer but never resolves the track
 * for subscribers (not_found_track_error).  A fresh transceiver gets its own
 * mid (no collision with receive mids).
 *
 * A1 (F8): reuse the transceiver orphaned by the previous stopSharing instead
 * of stacking a new one per share/stop cycle (avoids m-section growth and the
 * SFU's 413 accumulation error).  The ONLY reuse candidate is ``orphan`` — the
 * transceiver explicitly captured by THIS instance's stopSharing (sender.track
 * nulled by removeTrack but the transceiver kept), per-instance since F13.
 * There is deliberately NO global `pc.getTransceivers()` fallback search: on a
 * SHARED PC (party-cell + glb-content-viewer on the same page) a global search
 * can steal ANOTHER instance's orphan and clobber its active share (review #2
 * of party-calls-screen-audio-session-isolation).  When no orphan is available
 * a fresh transceiver is allocated — an extra m-section is cheaper than
 * corrupting a live share.
 * Force direction back to 'sendonly' before replaceTrack — the direction was
 * re-negotiated away from 'sendonly' by the previous offer, so the old
 * direction-only search silently missed and stacked a new transceiver
 * (transceivers 5→6 in F7 → 413 risk).
 *
 * Returns the allocated transceiver + whether the ORPHAN was reused (the caller
 * clears its orphan handle + the diagnostic mirror when true).
 */
export async function _allocateSendonlyTransceiver(
  pc: RTCPeerConnection,
  track: MediaStreamTrack,
  orphan: RTCRtpTransceiver | null,
): Promise<{ tx: RTCRtpTransceiver; reusedOrphan: boolean }> {
  let tx: RTCRtpTransceiver | null = null
  let reusedOrphan = false
  if (orphan?.sender) {
    tx = orphan
    reusedOrphan = true
  }
  if (tx?.sender) {
    try {
      tx.direction = 'sendonly'
    } catch { /* ignore — non-mutating on some browsers */ }
    await tx.sender.replaceTrack(track)
  } else {
    // Capture the fresh transceiver so the codec filter (2B) can act on the
    // very transceiver created for this share.
    tx = pc.addTransceiver(track, { direction: 'sendonly' })
  }
  return { tx, reusedOrphan }
}

/**
 * 2B (defensive — party-cell-screen-share-sfu-register-fail): keep the quality
 * video codecs (VP8/VP9/AV1/H264) on the given transceiver and drop only the
 * families that surfaced the SFU codec artifact (H265/H266) plus the FEC/rtx
 * baggage.  F5 (review #3078): H2 was DISCARDED as the root cause, so the
 * filter is purely defensive and must NOT degrade the share's quality on Chrome
 * (which offers VP9/AV1 via getCapabilities).  Fallback: browsers without
 * setCodecPreferences / RTCRtpSender.getCapabilities keep the current behavior
 * (no filter).
 */
export function _applyVideoCodecFilter(tx: RTCRtpTransceiver | null): void {
  if (!tx?.setCodecPreferences) return
  const codecCaps = (typeof RTCRtpSender !== 'undefined' && RTCRtpSender.getCapabilities
    ? (RTCRtpSender.getCapabilities('video')?.codecs ?? [])
    : [])
    .filter((c) => /(^|\/)(vp8|vp9|av1|h264)$/i.test(c.mimeType))
  if (codecCaps.length > 0) {
    try {
      tx.setCodecPreferences(codecCaps)
    } catch { /* ignore — non-mutating on some browsers */ }
  }
}

/**
 * Build the ``tracks/new`` (location:'local') payload for the given sender-owned
 * screen tracks (the shared video + its optional display-audio).  GAP 1: the
 * publisher registers its OWN tracks via tracks/new AFTER the renegotiation
 * offer — the native track id (sender.track.id) is what remote subscribers must
 * reference to resolve the media.
 *
 * ⚠️ The ``t.sender.track`` truthiness guard is REQUIRED: when a track argument
 * is null (share without display audio), ``sender.track === audioTrack`` would
 * otherwise match the base recvonly transceivers whose sender.track is null
 * (null === null) — and ``track!.id`` on that null track crashes the share.
 */
export function _buildLocalTrackObjs(
  pc: RTCPeerConnection,
  tracks: Array<MediaStreamTrack | null>,
): Array<{ location: 'local'; mid: string; trackName: string }> {
  const trackSet = new Set(tracks.filter((t): t is MediaStreamTrack => !!t))
  return pc.getTransceivers()
    .filter((t) => t.sender && t.sender.track && trackSet.has(t.sender.track) && t.mid)
    .map((t) => ({
      location: 'local' as const,
      mid: t.mid as string,
      trackName: t.sender!.track!.id,
    }))
}

/**
 * G2/R#3 (review #3077) failure cleanup: detach the sendonly transceivers
 * owning the given tracks (``replaceTrack(null)``) and return them so the caller
 * can restore them as ORPHANS for the NEXT shareStream to reuse
 * (sender.track === null → replaceTrack) instead of stacking a new transceiver
 * per failed share.  Without this, repeated share-fail cycles accumulate
 * m-sections → the SFU's 413 error that the A1 orphan-reuse exists to prevent.
 */
export function _detachSendonlyTransceivers(
  pc: RTCPeerConnection,
  tracks: Array<MediaStreamTrack | null>,
): Array<RTCRtpTransceiver | null> {
  const trackSet = new Set(tracks.filter((t): t is MediaStreamTrack => !!t))
  const orphans: Array<RTCRtpTransceiver | null> = []
  for (const track of trackSet) {
    const tx = pc.getTransceivers().find((t) => t.sender?.track === track) ?? null
    if (tx?.sender) {
      try { void tx.sender.replaceTrack(null) } catch { /* ignore — PC rolled back to stable */ }
    }
    orphans.push(tx)
  }
  return orphans
}

/**
 * Register the given screen tracks on the SFU and close the publisher
 * renegotiation in one step — the ``_registerLocalTracksOnSfu`` +
 * ``_closeLocalRenegotiation`` composition used by shareStream.
 *
 * Returns true when an SDP was applied (the tracks were registered on the SFU);
 * false when nothing was applied (regResult null / per-track errorCode) — the
 * caller MUST NOT publish the tracks to the registry/presence.
 *
 * PERMANENTE (B2/F4): an EMPTY trackObjs reaching this point means the sendonly
 * transceiver never got its mid — the screen is NOT registered on the SFU, yet
 * registry + presence would still update below if the caller proceeded.  Silent
 * inconsistency: the publisher sees the self-view, subscribers get
 * not_found_track_error forever.  Always visible.
 */
export async function _publishLocalTracks(
  pc: RTCPeerConnection,
  sessionId: string,
  screenTrackObjs: Array<{ location: 'local'; mid: string; trackName: string }>,
  offer: RTCSessionDescriptionInit,
): Promise<boolean> {
  let regResult: any = null
  if (!screenTrackObjs.length) {
    log.warn(
      '[PERM][shareStream] screenTrackObjs EMPTY session=%s — screen track NOT registered on SFU (no mid); subscribers will not resolve it',
      sessionId,
    )
  }
  if (screenTrackObjs.length) {
    regResult = await _registerLocalTracksOnSfu(
      pc,
      sessionId,
      screenTrackObjs,
      { type: offer.type, sdp: offer.sdp || '' },
    )
  }
  // Close the publisher renegotiation (F9 single helper — offer → answer,
  // direct answer → apply, null → roll back so the PC is not wedged in
  // have-local-offer).
  return _closeLocalRenegotiation(regResult)
}
