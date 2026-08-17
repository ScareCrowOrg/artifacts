/**
 * @file party-calls/remoteMedia.ts
 * @description Incoming remote-track classification + tile merge + end-of-track
 * cleanup for the usePartyCalls composable (Cloudflare Calls / WebRTC).
 * Extracted VERBATIM from the former monolithic ``usePartyCalls.ts`` (shell
 * section), with ONE extraction adjustment: the functions now receive the
 * reactive ``remoteStreams: Ref<Map<string, MediaStream>>`` as an explicit
 * parameter instead of closing over the shell's ref.
 *
 * Dependency graph: imports ``_teardownRemoteMedia`` from ``./sfuSignaling`` +
 * state from ``./state``.  No reverse imports.  See ``party-calls/README.md``.
 */

import { _teardownRemoteMedia } from './sfuSignaling'
import {
  log,
  state,
  _remoteTrackTypes,
  _remoteMidToTrackName,
  _transceiverMeta,
  _unmarkMidPending,
  _subscribedSessions,
  _remoteStreamAddedAt,
  _REMOTE_STREAM_GRACE_MS,
  _subscribedTrackNames,
} from './state'
import type { Ref } from 'vue'

// ─────────────────────────────────────────────────────────────────────────────
// Remote media handling
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Tear down the local state for a remote track that ended/was removed (S2
 * subscriber side).  Removes the grid tile, stops the recvonly receiver
 * transceiver (local-only — the backend has no tracks/remove endpoint to
 * un-subscribe via signaling), and drops the mid/trackName mappings so a
 * later re-subscription can't misclassify.  Called by the track.onended /
 * stream.onremovetrack handlers in _handleRemoteTrack, and (transceiver-only)
 * by the B2 prune via _teardownRemoteMedia.
 */
function _cleanupEndedRemoteTrack(
  key: string,
  mid: string | null,
  trackName: string | null,
  // DIAG (F2 CICLO 3, B1): WHICH end-of-track handler fired — the origin lets
  // F7 discriminate a spurious cleanup (onmute/onended on a stale ended/muted
  // track riding the reused mid-1 transceiver) from a legitimate one.  The
  // three call sites in _handleRemoteTrack pass their fixed literal.
  origin: 'onmute' | 'onended' | 'onremovetrack' | 'unknown' = 'unknown',
  remoteStreams: Ref<Map<string, MediaStream>>,
): void {
  // DIAG (F2 CICLO 3, B1): prove the cleanup fired and against which tile.
  // F7 cross-references [DIAG][merge] "screen added key={sid}/screen" →
  // [DIAG][cleanup] origin=... key={sid}/screen → [DIAG][cleanup] removed — the
  // spurious-removal sequence in the SAME dispatch as the ontrack.
  log.warn(
    '[DIAG][cleanup] origin=%s key=%s mid=%s trackName=%s',
    origin, key, mid ?? 'none', trackName ?? 'none',
  )
  // F3 FIX (ITER_1 guest-screenshare CICLO 3): grace-period guard against the
  // SPURIOUS end-of-track removal.  If this tile key was added to remoteStreams
  // within the last _REMOTE_STREAM_GRACE_MS, this cleanup is the spurious event
  // fired by a STALE track (readyState=ended / muted) riding a REUSED
  // transceiver mid — the confirmed mechanism: the screen tile entered in
  // _handleRemoteTrack and was removed in the SAME dispatch by onmute/onended.
  // Skip the removal + teardown so the just-received tile survives; a REAL end
  // of this subscription is handled by the B2 registry prune and by any
  // post-grace end-of-track event (both arrive well after the grace window).
  const _addedAt = _remoteStreamAddedAt.get(key)
  if (_addedAt !== undefined && Date.now() - _addedAt < _REMOTE_STREAM_GRACE_MS) {
    log.warn(
      '[DIAG][cleanup] blocked key=%s origin=%s age_ms=%d (tile just added — spurious end-track guard)',
      key, origin, Date.now() - _addedAt,
    )
    return
  }
  const next = new Map(remoteStreams.value)
  if (next.has(key)) {
    next.delete(key)
    remoteStreams.value = next
    _remoteStreamAddedAt.delete(key)
    // PERMANENTE: a screen tile disappearing from the reactive Map was the
    // silent blind spot of this bug class (took 3+ iterations to find).  Keep
    // the removal visible permanently so any future silent tile loss is caught
    // on the first run instead of after N E2E passes.
    log.warn('[DIAG][cleanup] removed key=%s size=%d', key, remoteStreams.value.size)
  }
  if (mid) _teardownRemoteMedia([mid], 'cleanup')
  const ownerId = key.endsWith('/screen') ? key.slice(0, -'/screen'.length) : key
  if (trackName) {
    const already = _subscribedTrackNames.get(ownerId)
    if (already) {
      _subscribedTrackNames.set(ownerId, already.filter((n) => n !== trackName))
    }
    const typeMap = _remoteTrackTypes.get(ownerId)
    if (typeMap) typeMap.delete(trackName)
  }
  if (!_subscribedTrackNames.get(ownerId)?.length) _subscribedTrackNames.delete(ownerId)
  if (!_remoteTrackTypes.get(ownerId)?.size) _remoteTrackTypes.delete(ownerId)
}

/**
 * Incoming remote track.  Cloudflare tags the track id with the publisher's
 * session (``{sessionId}/{trackName}``); tracks merge per sessionId.  Screen
 * tracks (display type 'screen' resolved via _remoteTrackTypes) get their own
 * ``{sessionId}/screen`` key so the grid renders a dedicated highlighted tile
 * instead of letting the camera win or showing a black tile (GAP 4).
 */
export function _handleRemoteTrack(
  event: RTCTrackEvent,
  remoteStreams: Ref<Map<string, MediaStream>>,
): void {
  // F3 FIX (ITER_1 H1): keep the stream reference but ALLOW it to be empty.
  // Cloudflare can deliver a video ontrack with an EMPTY event.streams (the
  // video m-line in the SFU offer carries no a=msid).  The old `if (!stream)
  // return` guard discarded that track SILENTLY — the exact "audio flows, video
  // never reaches the tile" symptom.  stream === null now means "create a fresh
  // MediaStream and attach the track" (handled after classification).
  const stream = Array.isArray(event.streams) && event.streams.length > 0
    ? event.streams[0]
    : null
  // DIAG (F2 ITER_1 H1 — DECISIVE): emitted BEFORE stream-creation so the
  // evidence of the F3 fix is captured.  Records kind/streams_len/mid on EVERY
  // ontrack — including the previously-dropped empty-stream video case — so F7
  // can confirm kind=video streams_len=0 still classifies + merges (H1 fixed).
  // receiver_readyState/muted double as the lightweight H2 probe (no RTP →
  // readyState stays 0/muted); the [DIAG][stats] dump adds bytesReceived.
  log.warn(
    '[DIAG][ontrack-before-drop] kind=%s track_id=%s mid=%s streams_len=%d stream_present=%s stream_id=%s receiver_readyState=%s receiver_muted=%s',
    event.track.kind, event.track.id, event.transceiver?.mid ?? 'none',
    Array.isArray(event.streams) ? event.streams.length : -1,
    stream ? 'yes' : 'no', stream?.id ?? 'none',
    event.receiver?.track.readyState ?? 'n/a', event.receiver?.track.muted ?? 'n/a',
  )

  // DIAG (F2 CICLO 4): capture the raw ontrack fields BEFORE classification.
  // Cloudflare delivers an OPAQUE track.id (no '/'), so the regex branch below
  // never matches and classification must resolve the owner via
  // event.transceiver.mid → _remoteMidToTrackName (F3). This log lets F7
  // confirm the mid present on the ontrack (e.g. '4' for the screen) matches
  // the mid echoed in the tracks/new response (see the [DIAG][subscribe]
  // mid_map log) — the bridge that makes an opaque track.id classifiable.
  log.warn(
    '[DIAG][remote-track] ontrack kind=%s session=%s track_id=%s track_id_has_slash=%s transceiver_mid=%s stream_id=%s',
    event.track.kind, state._currentSessionId, event.track.id, /\//.test(event.track.id || ''),
    event.transceiver?.mid ?? 'none', stream ? stream.id : 'none',
  )

  const trackIdMatch = /^([^/]+)\/(.+)$/.exec(event.track.id || '')
  let sessionKey: string
  // F3 FIX (ITER_1 H3): where the owner/trackName classification came from —
  // reported on the classified DIAG so F7 can prove the WeakMap anchor
  // resolved the video (meta_source=transceiver) vs the global mid Map.
  let metaSource: 'map' | 'transceiver' | 'none' = 'none'
  if (trackIdMatch) {
    // Backward compat: track.id in the historical {sessionId}/{trackName}
    // slash format.  Cloudflare does NOT deliver this on the receiving side
    // (the id is opaque), but keep the branch for any SFU that does.
    const ownerId = trackIdMatch[1]
    const trackName = trackIdMatch[2]
    const display = _remoteTrackTypes.get(ownerId)?.get(trackName)
    sessionKey = display === 'screen' ? `${ownerId}/screen` : ownerId
    if (display === 'screen') {
      log.warn(
        '[DIAG][remote-track] screen track received sessionId=%s trackName=%s sessionKey=%s stream_id=%s',
        ownerId, trackName, sessionKey, stream ? stream.id : 'none',
      )
    }
  } else {
    // F3 FIX (CICLO 4): the real Cloudflare receiver delivers an OPAQUE
    // track.id (no '/'), so classify via event.transceiver.mid → the
    // mid → {sessionId, trackName} map built from the tracks/new (remote)
    // response in _subscribeToRemoteTracks.  Non-screen tracks key by the
    // OWNER sessionId so mic+camera merge into ONE tile per participant
    // (no more stream.id duplicates) and ghost pruning works on the key.
    const transceiverMid = event.transceiver?.mid ?? null
    // F3 FIX (ITER_1 H3): the global mid → {sessionId, trackName} Map is the
    // PRIMARY classification, but concurrent operations (prune
    // removeOwnerMappings / removeScreenMapping, _teardownRemoteMedia,
    // interleaved _refreshDiscovery across heartbeats) can mutate it BETWEEN
    // the population and this ontrack firing — in F7 ciclo 2 the video ontrack
    // read the map with mid "1" already gone (despite a 2-entry mid_map
    // populated) and fell back to the opaque stream.id (separate generic
    // tile).  When the global Map misses, fall back to the transceiver-scoped
    // meta: the ontrack's OWN RTCRtpTransceiver is stable, so its WeakMap
    // entry is race-immune.
    let info = transceiverMid ? _remoteMidToTrackName.get(transceiverMid) : undefined
    if (info) {
      metaSource = 'map'
    } else if (event.transceiver) {
      // F3 FIX (ITER_1 guest-screenshare): edge-case defense for the NEW
      // screen transceiver.  If the global mid map STILL carries this mid but
      // the WeakMap was never anchored for the transceiver — the transceiver is
      // created during setRemoteDescription, and in a synchronous-ontrack
      // browser it can fire before our post-setRemoteDescription re-anchor —
      // anchor it ON THE SPOT so the race-immune fallback resolves this
      // ontrack.  Idempotent (set() with the same meta) and only fires when
      // the global map is authoritative (never invents a mapping).
      if (transceiverMid && _remoteMidToTrackName.has(transceiverMid)) {
        _transceiverMeta.set(event.transceiver, _remoteMidToTrackName.get(transceiverMid)!)
      }
      info = _transceiverMeta.get(event.transceiver) ?? undefined
      if (info) metaSource = 'transceiver'
    }
    if (info) {
      const ownerId = info.sessionId
      const display = _remoteTrackTypes.get(ownerId)?.get(info.trackName)
      sessionKey = display === 'screen' ? `${ownerId}/screen` : ownerId
      if (display === 'screen') {
        log.warn(
          '[DIAG][remote-track] screen track received sessionId=%s trackName=%s sessionKey=%s stream_id=%s',
          ownerId, info.trackName, sessionKey, stream ? stream.id : 'none',
        )
      }
    } else {
      // Last resort: mid absent (very old browser without transceiver) or the
      // track was never mapped — keep the historical stream.id behavior; when
      // event.streams was EMPTY there is no stream.id, so key by the opaque
      // track id (defensive — mid-map should have resolved a real track).
      sessionKey = stream ? stream.id : (event.track.id || 'remote')
      // DIAG (ITER_1 party-cell-mock-remote-user, H2): this is the OPAQUE-key
      // fallback — a track that resolved to NO owner.  Surface WHY: mid present
      // but missing from the mid→{sessionId,trackName} map (pruned/never
      // populated) vs mid absent entirely.  A tile keyed by stream.id/track.id
      // never matches a participant (permanent "Usuário Remoto") and is never
      // pruned (prune only removes known owner keys).  Cross-reference the
      // sessionKey against the [DIAG][discovery] enumeration: it appears there
      // ⇒ H1, absent ⇒ H2 confirmed.
      log.warn(
        '[DIAG][remote-track][H2-OPAQUE-FALLBACK] kind=%s mid=%s mid_in_map=%s mid_in_txmeta=%s sessionKey=%s track_id=%s subscribed_sessions=%j',
        event.track.kind,
        event.transceiver?.mid ?? 'none',
        event.transceiver?.mid ? _remoteMidToTrackName.has(event.transceiver.mid) : false,
        event.transceiver ? _transceiverMeta.has(event.transceiver) : false,
        sessionKey,
        event.track.id,
        [..._subscribedSessions],
      )
    }
  }

  // F3 FIX (ITER_1 guest-screenshare CICLO 2): the ontrack for a pending mid
  // has fired and classified — the subscription has landed on a tile, so the
  // pending protection is released (a later legitimate prune of this mid may
  // proceed).  Runs AFTER the classification read the map/WeakMap.
  _unmarkMidPending(event.transceiver?.mid ?? null, sessionKey)

  // DIAG (F2 ITER_1 H3): after classification, before the tile merge — shows
  // whether this track (audio/video) was resolved via _remoteMidToTrackName to
  // the OWNER tile (sessionKey = ownerId) or fell back to the OPAQUE stream.id
  // (a separate, generic "remoteUser" tile).  kind=video + via_stream_id_fallback=yes
  // ⇒ the video never merged into the publisher's tile — consistent with H3.
  log.warn(
    '[DIAG][remote-track-classified] kind=%s sessionKey=%s mid=%s via_stream_id_fallback=%s meta_source=%s',
    event.track.kind, sessionKey, event.transceiver?.mid ?? 'none',
    (stream && sessionKey === stream.id) ? 'yes' : 'no',
    metaSource,
  )

  // DIAG (B1/B4 — CRITICAL F1+F2 proof): full dump when this ontrack is the
  // SCREEN (resolved to '{sid}/screen') OR fell to the opaque stream.id
  // fallback (metaSource 'none' — a screen whose mid was pruned/never mapped
  // is indistinguishable from a camera here; the dump proves the map state).
  //  • mid_map_entries — the GLOBAL map at ontrack time: if the screen mid is
  //    MISSING despite a populated map, a concurrent prune dropped it (race
  //    H3, F2).
  //  • tx_meta_present/tx_meta — the _transceiverMeta WeakMap entry for the
  //    ontrack's OWN transceiver: '(none)' for a NEW screen transceiver
  //    proves F1 (no race-immune fallback → classification depends 100% on
  //    the global map).
  //  • meta_source — which path classified this track: 'map' (:1280) /
  //    'transceiver' (:1284) / 'none' (opaque fallback :1302).
  if (event.track.kind === 'video' && (sessionKey.endsWith('/screen') || metaSource === 'none')) {
    const _txMetaVal = event.transceiver ? _transceiverMeta.get(event.transceiver) : undefined
    log.warn(
      '[DIAG][ontrack][screen] kind=%s sessionKey=%s mid=%s meta_source=%s track_id=%s stream_id=%s opaque=%s mid_map_entries=%s tx_meta_present=%s tx_meta=%s',
      event.track.kind, sessionKey, event.transceiver?.mid ?? 'none', metaSource,
      event.track.id, stream ? stream.id : 'none',
      (stream && sessionKey === stream.id) ? 'yes' : 'no',
      JSON.stringify([..._remoteMidToTrackName.entries()]),
      event.transceiver ? _transceiverMeta.has(event.transceiver) : false,
      _txMetaVal ? JSON.stringify(_txMetaVal) : '(none)',
    )
  }

  // F3 FIX (ITER_1 H1): NEVER drop a remote track that arrived with an EMPTY
  // event.streams.  Create a fresh MediaStream and attach the track so the merge
  // below can add it to the publisher's tile — this fixes the video track that
  // previously died at the `if (!stream) return` guard while its audio sibling
  // (stream-bearing) had already created the tile.  When the audio track came
  // first, `existing` holds that tile's stream and the video track is merged
  // into it via the existing.addTrack path (the already-attached <video> picks
  // the new track up automatically via MediaStreamTrack events).
  const effectiveStream = stream ?? new MediaStream()
  if (!stream) effectiveStream.addTrack(event.track)

  // S2 subscriber side: bind end/change-of-track handlers that tear down the
  // local media path when the publisher stops the share.  A real end is:
  // track ended, stream.onremovetrack, or a SCREEN track going mute (screen
  // shares have no mute button — mute on the screen track means the publisher
  // stopped or the SFU dropped it).  Camera/mic mute stays reversible
  // (onmute/onunmute no-op, no cleanup).
  const _txMid = event.transceiver?.mid ?? null
  // F3 FIX (ITER_1 H3): mirror the classification fallback — bind the end-of-
  // track handlers to the SAME owner/trackName the ontrack resolved (WeakMap
  // anchor when the global mid Map was already pruned before the handlers fire).
  const _infoAtReceive = (_txMid ? _remoteMidToTrackName.get(_txMid) : undefined)
    ?? (event.transceiver ? _transceiverMeta.get(event.transceiver) : undefined)
  const _trackNameAtReceive = _infoAtReceive?.trackName ?? null
  const _displayAtReceive = _infoAtReceive
    ? _remoteTrackTypes.get(_infoAtReceive.sessionId)?.get(_infoAtReceive.trackName)
    : undefined
  const _bindTrackEndHandlers = (trk: MediaStreamTrack) => {
    // DIAG (F2 CICLO 3, B2): record the track state at BIND time.  If the
    // screen track arrives ALREADY ended/muted (stale echo of the pruned host
    // camera on the reused mid-1 transceiver), Chrome fires mute/ended right
    // after the ontrack returns → spurious cleanup.  F7 reads this to confirm
    // the bound track is the stale one (cross-ref [DIAG][ontrack-before-drop]
    // receiver_readyState=ended receiver_muted=true).
    log.warn(
      '[DIAG][bind] key=%s track_id=%s kind=%s readyState=%s muted=%s',
      sessionKey, trk.id, trk.kind, trk.readyState, trk.muted,
    )
    // F3 FIX (ITER_1 guest-screenshare CICLO 3): if the track arrived ALREADY
    // ended (the stale echo of a pruned camera riding a REUSED transceiver mid —
    // confirmed in F7 by receiver_readyState=ended receiver_muted=true on the
    // screen ontrack), binding onmute/onended makes Chrome fire those events
    // right after the ontrack returns → spurious cleanup of the just-added
    // screen tile.  An already-ended track cannot fire a meaningful NEW end
    // later (the end already happened) — a real end of this subscription is
    // handled by the B2 registry prune and by the post-grace guard in
    // _cleanupEndedRemoteTrack.  Skip binding the cleanup handlers so the tile
    // persists (video validity is validated by F7).
    if (trk.readyState === 'ended') {
      log.warn(
        '[DIAG][bind-skip] key=%s track_id=%s kind=%s readyState=ended — stale track on reused transceiver, end handlers NOT bound',
        sessionKey, trk.id, trk.kind,
      )
      return
    }
    trk.onended = () => {
      // DIAG (F2 CICLO 3, B2): prove the end-of-track handler FIRED and against
      // which tile key (real end vs spurious stale-track event).
      log.warn('[DIAG][track-event] onended fired key=%s', sessionKey)
      _cleanupEndedRemoteTrack(sessionKey, _txMid, _trackNameAtReceive, 'onended', remoteStreams)
    }
    trk.onmute = () => {
      if (_displayAtReceive === 'screen') {
        // DIAG (F2 CICLO 3, B2): the mute handler fired on a SCREEN track — the
        // only mute path that calls cleanup.  If the bound track is the stale
        // ended/muted one, this is the spurious removal trigger.
        log.warn('[DIAG][track-event] onmute fired key=%s gate=screen', sessionKey)
        _cleanupEndedRemoteTrack(sessionKey, _txMid, _trackNameAtReceive, 'onmute', remoteStreams)
      } else {
        // DIAG (F2 CICLO 3): mute on a camera/mic track is reversible — no
        // cleanup.  Logging the gate=skip path keeps the trace complete so F7
        // can prove the gate decision (not a silent no-op).
        log.warn(
          '[DIAG][track-event] onmute fired key=%s gate=skip display=%s',
          sessionKey, _displayAtReceive ?? 'none',
        )
      }
    }
    trk.onunmute = () => { /* camera/mic mute stays reversible — no cleanup */ }
  }
  for (const trk of effectiveStream.getTracks()) _bindTrackEndHandlers(trk)
  effectiveStream.onremovetrack = () => {
    _cleanupEndedRemoteTrack(sessionKey, _txMid, _trackNameAtReceive, 'onremovetrack', remoteStreams)
  }

  const next = new Map(remoteStreams.value)
  const existing = next.get(sessionKey)
  if (existing && existing !== effectiveStream) {
    // Merge additional tracks (e.g. audio + video) into one per participant
    for (const track of effectiveStream.getTracks()) {
      if (!existing.getTracks().includes(track)) {
        existing.addTrack(track)
      }
    }
    next.set(sessionKey, existing)
  } else {
    next.set(sessionKey, effectiveStream)
  }
  remoteStreams.value = next
  // F3 FIX (ITER_1 guest-screenshare CICLO 3): record when this tile key entered
  // the Map — the grace guard in _cleanupEndedRemoteTrack uses it to block a
  // spurious SAME-DISPATCH end-of-track removal (mute/ended on a stale track
  // riding a reused transceiver mid).  Reset on every merge; a real end arrives
  // well past the grace window, so this never defers a genuine teardown.
  _remoteStreamAddedAt.set(sessionKey, Date.now())
  // DIAG (F2 CICLO 3, B1): proof the classified SCREEN tile ENTERED the reactive
  // Map.  F7 expects the spurious-removal sequence: [DIAG][merge] screen added
  // key={sid}/screen → [DIAG][cleanup] origin=onmute|onended key={sid}/screen →
  // [DIAG][cleanup] removed key={sid}/screen, all in the SAME dispatch as the
  // ontrack.  size = Map size after the set (a persistent tile stays ≥ its
  // pre-merge size; a spurious removal drops it back).
  if (sessionKey.endsWith('/screen')) {
    log.warn('[DIAG][merge] screen added key=%s size=%d', sessionKey, remoteStreams.value.size)
  }
  log.debug('[PC] remote track received, key=%s', sessionKey)
}
