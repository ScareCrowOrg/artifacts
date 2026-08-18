/**
 * @file party-calls/subscription.ts
 * @description Remote subscription helpers for the usePartyCalls composable
 * (Cloudflare Calls / WebRTC).  Extracted VERBATIM from the former monolithic
 * ``usePartyCalls.ts`` (section "Multi-user SFU helpers").
 *
 * Dependency graph: imports ``_apiFetchJson`` from ``./http`` + state from
 * ``./state``.  ⚠️ ANTI-CYCLE RULE: this module NEVER imports
 * ``./discovery`` — if it needs to signal a re-discovery it returns the signal
 * to the caller instead.  See ``party-calls/README.md``.
 */

import { _apiFetchJson } from './http'
import {
  log,
  state,
  _subscribedTrackNames,
  _remoteMidToTrackName,
  _transceiverMeta,
  _subscribedSessions,
  _markMidsPending,
  _unmarkMidPending,
  _anchorTransceiverMetaFromMidMap,
} from './state'
import type { RemoteSession, SfuTrackResult } from './types'
import type { Ref } from 'vue'

// ─────────────────────────────────────────────────────────────────────────────
// Remote subscription
// ─────────────────────────────────────────────────────────────────────────────

/** One-shot stats dump (F2 ITER_1 H2): ~5s after the first successful remote
 *  subscribe, read the inbound-rtp stats of the audio and video receivers.  A
 *  VIDEO receiver with bytesReceived==0 means the SFU accepted the subscription
 *  but is NOT delivering video RTP to this subscriber — discriminating H2 from
 *  H1 (the video track dropped client-side at the ontrack !stream guard) and
 *  from H3 (the video merged onto an opaque stream.id tile). */
async function _logSfuStatsDump(): Promise<void> {
  if (!state._pc) return
  try {
    const report = await state._pc.getStats()
    const inbound: Record<string, { kind: string; bytesReceived: number; packetsReceived: number }> = {}
    report.forEach((raw) => {
      const s = raw as unknown as {
        type: string
        kind?: string
        bytesReceived?: number
        packetsReceived?: number
      }
      if (s.type !== 'inbound-rtp') return
      const kind = s.kind || 'unknown'
      if (!inbound[kind]) inbound[kind] = { kind, bytesReceived: 0, packetsReceived: 0 }
      inbound[kind].bytesReceived += s.bytesReceived || 0
      inbound[kind].packetsReceived += s.packetsReceived || 0
    })
    // H2 telemetry: has_video + bytesReceived discriminates "SFU accepted the
    // subscribe but is NOT forwarding video RTP" from a client-side drop.
    const hasVideo = Object.prototype.hasOwnProperty.call(inbound, 'video')
    log.warn(
      '[stats] inbound_rtp=%j has_video=%s video_bytes=%d audio_bytes=%d',
      inbound, hasVideo, inbound.video?.bytesReceived ?? 0, inbound.audio?.bytesReceived ?? 0,
    )
  } catch (err) {
    log.warn('[stats] getStats failed: %s', err instanceof Error ? err.message : String(err))
  }
}

/**
 * Subscribe to a remote session's media tracks via Cloudflare tracks/new.
 *
 * Contract (realtime-api-2024-05-21.yaml, `remote_tracks` example): a remote
 * subscription is a TRACKS-ONLY request — each TrackObject carries
 * ``location:'remote'`` + ``sessionId`` (the track owner) + ``trackName`` (the
 * exact name the publisher registered).  The client does NOT build its own
 * offer: the SFU generates it and responds with ``requiresImmediateRenegotiation``
 * + an offer that we answer and send back via ``PUT /renegotiate``
 * (react-native-webrtc pattern).  This avoids re-offering ``state._pc``'s already
 * negotiated m= sections (406) and client-side transceiver accumulation (413).
 */
export async function _subscribeToRemoteTracks(
  remote: RemoteSession,
  remoteStreams: Ref<Map<string, MediaStream>>,
): Promise<void> {
  if (!state._pc || !state._currentSessionId) return

  // The remote session's NATIVE trackNames come from the room registry
  // metadata (GET /calls/rooms/{room}/sessions → metadata.trackNames).  The
  // publisher registers each track on the SFU under sender.track.id — the
  // display labels ('mic'/'camera') resolve to not_found_track_error (H1
  // proven in F7 ciclo 2).  Fall back to the display labels only for sessions
  // registered before trackNames existed (backward compatibility).
  const allTrackNames: string[] = (remote.trackNames && remote.trackNames.length)
    ? [...remote.trackNames]
    : (remote.tracks && remote.tracks.length)
      ? [...remote.tracks]
      : ['mic', 'camera']

  // GAP 3: subscribe only to tracks NOT yet subscribed.  When a session adds a
  // new track (e.g. the shared screen) its trackNames grow and the next
  // heartbeat subscribes just the delta — no page reload needed.
  const already = _subscribedTrackNames.get(remote.sessionId) ?? []
  const trackNames = allTrackNames.filter((n) => !already.includes(n))
  if (trackNames.length === 0) return

  const tracksToSend = trackNames.map((trackName) => ({
    location: 'remote' as const,
    sessionId: remote.sessionId,
    trackName,
  }))

  try {
    const result = await _apiFetchJson(
      `/calls/sessions/${state._currentSessionId}/tracks/new`,
      {
        method: 'POST',
        body: JSON.stringify({ tracks: tracksToSend }),
      },
    )

    const respSd = result?.sessionDescription
    const respSdp = respSd?.sdp ? String(respSd.sdp) : ''
    let subscribed = false

    // F3 FIX (CICLO 5): populate _remoteMidToTrackName IMMEDIATELY after the
    // tracks/new (remote) fetch, BEFORE any setRemoteDescription.  In the
    // requiresImmediateRenegotiation branch the ontrack fires AS SOON AS THE
    // SFU's offer is applied at setRemoteDescription (below) — populating the
    // map later (inside `if (subscribed)`, after createAnswer +
    // setLocalDescription + the PUT /renegotiate round-trip) was a RACE:
    // _handleRemoteTrack consumed the map while it was still empty and fell
    // back to stream.id → generic tile, no '/screen', mic+camera split into 2
    // tiles (TEST_RESULTS_4).  Only resolved tracks (no errorCode) are mapped —
    // errored tracks never fire ontrack, so no stale mapping.  mid →
    // {sessionId, trackName} is the ONLY bridge between the OPAQUE track.id (no
    // {sessionId}/{trackName} slash) on the ontrack and the publisher's native
    // trackName (which then resolves to 'screen' via _remoteTrackTypes).
    const midEntries = (Array.isArray(result?.tracks) ? result.tracks : [])
      .filter((t: SfuTrackResult) => t && typeof t === 'object' && t.mid && t.trackName && !t.errorCode)
      .map((t: SfuTrackResult) => ({ mid: t.mid, trackName: t.trackName }))
    let transceiverMetaSets = 0
    for (const entry of midEntries) {
      if (entry.mid && entry.trackName) {
        _remoteMidToTrackName.set(entry.mid, { sessionId: remote.sessionId, trackName: entry.trackName })
        // F3 FIX (ITER_1 H3): ALSO anchor the classification on the transceiver
        // that will carry this mid — the ontrack reads _transceiverMeta as a
        // race-immune fallback when the global mid Map was pruned/overwritten
        // between this population and the ontrack firing (video mid "1" fell
        // back to the opaque stream.id in F7 ciclo 2 despite a 2-entry map).
        // The recvonly transceivers created at join already carry their mids
        // (DIAG transceivers_before_offer=2 recvonly_mids=[0, 1] on this flow),
        // so the lookup matches; a miss is non-fatal (global Map stays primary).
        const tx = state._pc.getTransceivers().find((t) => t.mid === entry.mid)
        if (tx) {
          _transceiverMeta.set(tx, { sessionId: remote.sessionId, trackName: entry.trackName })
          transceiverMetaSets += 1
        }
      }
    }
    if (midEntries.length > 0) {
      // PERMANENTE: which mids resolved to which publisher trackNames (the
      // bridge the ontrack uses to classify an opaque track.id).  Surfaces any
      // errorCode on tracks filtered out — a track whose name the SFU never
      // echoes never enters the map and falls back to the opaque stream.id.
      log.warn(
        '[subscribe] mid_map populated session=%s entries=%j raw_tracks=%j transceiver_meta_sets=%d',
        remote.sessionId, midEntries,
        Array.isArray(result?.tracks) ? result.tracks : [],
        transceiverMetaSets,
      )
      // F3 FIX (ITER_1 guest-screenshare CICLO 2): mark these mids as pending —
      // concurrent _refreshDiscovery prunes (removeOwnerMappings /
      // removeScreenMapping / _dropTransceiverMeta / _teardownRemoteMedia) must
      // NOT drop the just-populated map/WeakMap between here and the ontrack
      // (race H3).  Released on the ontrack classification or after 5s.
      _markMidsPending(midEntries.map((e: { mid: string; trackName: string }) => e.mid), remote.sessionId)
    }

    if (result?.requiresImmediateRenegotiation && respSd?.type === 'offer' && respSdp.length > 0) {
      // SFU generated the offer — apply it, answer, and send the answer back
      // via the renegotiate proxy so the SFU completes the m-line setup.
      await state._pc.setRemoteDescription(new RTCSessionDescription(respSd))

      // F3 FIX (ITER_1 guest-screenshare): the SFU offer just created the
      // transceiver for the NEW screen track (it did not exist during the first
      // _transceiverMeta population above).  Re-anchor the WeakMap NOW — the
      // screen's ontrack is dispatched as a task AFTER setRemoteDescription
      // resolves, so it will read the populated fallback instead of depending on
      // the prunable global map.  Idempotent; no-op for the already-anchored
      // audio/video transceivers.
      const _anchoredPostOffer = _anchorTransceiverMetaFromMidMap(remote.sessionId)
      if (_anchoredPostOffer > 0) {
        log.warn(
          '[subscribe] %s: transceiver_meta anchored post-setRemoteDescription=%d anchored_mids=%j',
          remote.sessionId, _anchoredPostOffer,
          state._pc.getTransceivers().filter((t) => t.mid && _transceiverMeta.has(t)).map((t) => t.mid),
        )
      }

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
      subscribed = true
    } else if (respSd?.type === 'answer' && respSdp.length > 0) {
      // Direct answer (no SFU offer) — apply as-is.  Only applied when the SDP
      // is non-empty: applying an empty SDP crashes setRemoteDescription with
      // "Failed to parse SessionDescription. Expect line: v=".
      await state._pc.setRemoteDescription(new RTCSessionDescription(respSd))
      // F3 FIX (ITER_1 guest-screenshare): direct-answer branch — transceivers
      // already exist here (no new m-line created), but run the same idempotent
      // re-anchor for uniformity/defense (no-op when already anchored).
      _anchorTransceiverMetaFromMidMap(remote.sessionId)
      subscribed = true
    } else {
      // Canonical no-op (react-native-webrtc #1536 / realtime-examples echo):
      // when requiresImmediateRenegotiation is false there is nothing to
      // negotiate — never apply an absent/empty SDP.  If the backend propagated
      // per-track errors (e.g. errorCode='empty_track_error'), the tracks did
      // NOT resolve on the SFU: surface them and leave the session unsubscribed
      // so the heartbeat retries once the publisher's trackNames resolve.
      const trackErrors = (Array.isArray(result?.tracks) ? result.tracks : [])
        .filter((t: SfuTrackResult) => t && typeof t === 'object' && (t.errorCode || t.errorDescription))
      if (trackErrors.length === 0) {
        subscribed = true // resolved without needing a renegotiation
      } else {
        log.warn(
          '[subscribe] %s: no-op — remote tracks not resolved on SFU (will retry) errors=%j',
          remote.sessionId, trackErrors,
        )
      }
    }

    if (subscribed) {
      _subscribedSessions.add(remote.sessionId)
      _subscribedTrackNames.set(remote.sessionId, [...already, ...trackNames])
      // G1 FIX (bug-hardening): the subscription is now CONFIRMED on the SFU
      // (_subscribedSessions.add after the PUT /renegotiate round-trip) — this
      // is the ONLY release point for the pending protection.  Releasing at the
      // ontrack (which fires BEFORE the round-trip) re-opened the race: a
      // concurrent stale prune in the ontrack→confirm gap dropped the
      // just-arrived tile (race H3).  A pending mid whose ontrack never fired
      // is still released here on confirm; the 5s timeout guards a subscription
      // that never confirms.
      for (const entry of midEntries) {
        if (entry.mid) _unmarkMidPending(entry.mid, remote.sessionId)
      }
      // F3 FIX (CICLO 5): the _remoteMidToTrackName population was MOVED up to
      // right after the tracks/new (remote) fetch, BEFORE the branch below — so
      // the map is populated before setRemoteDescription fires the ontrack.  L7
      // (mid_map populated) is emitted at that earlier point; nothing left here.
      log.info(
        '[subscribe] subscribed to remote session=%s answer_type=%s trackNames=%j',
        remote.sessionId, respSd?.type, trackNames,
      )
      // DIAG (F2 ITER_1 H2): one-shot stats dump ~5s after the FIRST successful
      // remote subscribe.  If the VIDEO receiver's inbound-rtp bytesReceived is
      // still 0 at that point, the SFU resolved the subscription (mid 1, no
      // errorCode) but is NOT forwarding video RTP — distinguishing H2 from H1
      // (the track never reached the tile) and H3 (it reached an opaque tile).
      if (!state._statsDumpScheduled) {
        state._statsDumpScheduled = true
        window.setTimeout(() => { void _logSfuStatsDump() }, 5000)
      }
    }
  } catch (err) {
    log.warn('[subscribe] failed for remote session=%s current_session=%s: %s',
      remote.sessionId, state._currentSessionId,
      err instanceof Error ? err.message : String(err))
  }
}
