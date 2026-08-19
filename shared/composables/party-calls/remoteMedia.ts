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
  // F1 FIX (bug-hardening): bypass the grace-period guard.  Used ONLY for a
  // non-screen (mic/camera) track that ARRIVED already ended — a genuinely dead
  // track (the publisher stopped it) has no reason to keep a black tile, so the
  // 400ms grace guard (which exists to protect NEW tiles from spurious
  // same-dispatch mute/ended events) must not defer its removal.
  bypassGrace = false,
): void {
  // Prove the cleanup fired and against which tile: F7 cross-references the
  // merge "screen added key={sid}/screen" → [cleanup] origin=... key={sid}/screen
  // → [cleanup] removed — the spurious-removal sequence in the SAME dispatch as
  // the ontrack.
  log.warn(
    '[cleanup] origin=%s key=%s mid=%s trackName=%s',
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
  if (!bypassGrace && _addedAt !== undefined && Date.now() - _addedAt < _REMOTE_STREAM_GRACE_MS) {
    log.warn(
      '[cleanup] blocked key=%s origin=%s age_ms=%d (tile just added — spurious end-track guard)',
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
    log.warn('[cleanup] removed key=%s size=%d', key, remoteStreams.value.size)
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

/** R#1/R#4 FIX (review #3077): drop a single trackName from the per-owner
 *  subscription maps WITHOUT touching the participant tile.  Used by the
 *  keep-tile cleanup paths — a dead non-screen track arriving while the owner
 *  has a LIVE tile (F1 regression), and an onremovetrack that leaves surviving
 *  tracks on the merged stream (F2) — which tear down only the removed track's
 *  transceiver + mapping, never the whole tile. */
function _dropTrackNameMapping(sessionKey: string, trackName: string | null): void {
  if (!trackName) return
  const ownerId = sessionKey.endsWith('/screen') ? sessionKey.slice(0, -'/screen'.length) : sessionKey
  const already = _subscribedTrackNames.get(ownerId)
  if (already) _subscribedTrackNames.set(ownerId, already.filter((n) => n !== trackName))
  const typeMap = _remoteTrackTypes.get(ownerId)
  if (typeMap) typeMap.delete(trackName)
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
  const trackIdMatch = /^([^/]+)\/(.+)$/.exec(event.track.id || '')
  let sessionKey: string
  if (trackIdMatch) {
    // Backward compat: track.id in the historical {sessionId}/{trackName}
    // slash format.  Cloudflare does NOT deliver this on the receiving side
    // (the id is opaque), but keep the branch for any SFU that does.
    const ownerId = trackIdMatch[1]
    const trackName = trackIdMatch[2]
    const display = _remoteTrackTypes.get(ownerId)?.get(trackName)
    // Ajuste 1: the screen's DISPLAY-AUDIO track ('screenAudio') merges into the
    // SAME {ownerId}/screen tile as the screen video — the <video> plays both, and
    // the receiver can mute only that tile's sound without touching the mic.
    sessionKey = (display === 'screen' || display === 'screenAudio') ? `${ownerId}/screen` : ownerId
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
    if (!info && event.transceiver) {
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
    }
    if (info) {
      const ownerId = info.sessionId
      const display = _remoteTrackTypes.get(ownerId)?.get(info.trackName)
      // Ajuste 1: 'screenAudio' merges into the screen tile (see the comment on
      // the slash-format branch above).
      sessionKey = (display === 'screen' || display === 'screenAudio') ? `${ownerId}/screen` : ownerId
    } else {
      // Last resort: mid absent (very old browser without transceiver) or the
      // track was never mapped — keep the historical stream.id behavior; when
      // event.streams was EMPTY there is no stream.id, so key by the opaque
      // track id (defensive — mid-map should have resolved a real track).
      sessionKey = stream ? stream.id : (event.track.id || 'remote')
    }
  }

  // G1 FIX (bug-hardening): the pending protection is NO LONGER released here —
  // the ontrack fires BEFORE the subscription is confirmed on the SFU
  // (_subscribedSessions.add runs after the PUT /renegotiate round-trip), so
  // releasing at the ontrack re-opened the race: a concurrent stale prune in
  // the ontrack→confirm gap dropped the just-arrived tile.  The release now
  // happens in _subscribeToRemoteTracks after the subscription confirms.


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
  // F1 FIX (bug-hardening): when a NON-screen incoming stream arrives with ALL
  // its tracks already ended, the subscription is genuinely dead (the publisher
  // stopped the mic/camera) — the tile must NOT be added (a black camera tile
  // that lingers until the session leaves).  Set by the bind loop below; the
  // merge step checks it before creating/merging the tile.
  let _deadNonScreenStream = false
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
        '[bind-skip] key=%s track_id=%s kind=%s readyState=ended — stale track on reused transceiver, end handlers NOT bound',
        sessionKey, trk.id, trk.kind,
      )
      // F1 FIX (bug-hardening): a NON-SCREEN (mic/camera) track that arrives
      // ALREADY ended is genuinely dead — the publisher stopped it and no
      // newer track is coming on this transceiver (unlike a SCREEN arriving as
      // the stale echo of a pruned camera, which the grace guard protects).  If
      // the whole incoming stream is dead, do not add the tile at all and clean
      // up the mapping + transceiver (bypassing the grace guard — a dead tile
      // has no reason to render black until the session leaves).
      if (!sessionKey.endsWith('/screen') && effectiveStream.getTracks().every((t: MediaStreamTrack) => t.readyState === 'ended')) {
        _deadNonScreenStream = true
        // This mid's ontrack HAS fired (with a genuinely dead track) — release
        // the pending protection so _teardownRemoteMedia (inside the cleanup)
        // is not deferred by it: there is nothing left to protect, and the dead
        // track + its mapping must not leak until the session leaves.
        _unmarkMidPending(_txMid, sessionKey)
        // R#1 (review #3077): a dead non-screen track must NEVER delete a LIVE
        // participant tile.  If the owner already has a tile with a live track
        // (e.g. the mic from a prior audio ontrack), tear down ONLY the dead
        // track's transceiver + mapping and keep the tile — the full-tile
        // cleanup below runs only when the participant has no live tile.
        const _existing = remoteStreams.value.get(sessionKey)
        const _existingHasLive = _existing
          ? _existing.getTracks().some((t: MediaStreamTrack) => t.readyState !== 'ended')
          : false
        if (_existingHasLive) {
          log.warn(
            '[cleanup] dead non-screen track skipped — owner tile has live tracks key=%s trackName=%s',
            sessionKey, _trackNameAtReceive ?? 'none',
          )
          if (_txMid) _teardownRemoteMedia([_txMid], 'cleanup')
          _dropTrackNameMapping(sessionKey, _trackNameAtReceive)
        } else {
          _cleanupEndedRemoteTrack(sessionKey, _txMid, _trackNameAtReceive, 'onended', remoteStreams, true)
        }
      }
      return
    }
    trk.onended = () => {
      // review #1 (party-calls-screen-audio-session-isolation): a DISPLAY-AUDIO
      // track ending is NOT "share over" — the screen VIDEO may still be flowing.
      // Drop only the audio track's mapping + receiver transceiver and KEEP the
      // {sid}/screen tile (a silent screen is still the screen); the video
      // track's own end/mute is what signals a real stop.
      if (_displayAtReceive === 'screenAudio') {
        if (_txMid) _teardownRemoteMedia([_txMid], 'cleanup')
        _dropTrackNameMapping(sessionKey, _trackNameAtReceive)
        return
      }
      _cleanupEndedRemoteTrack(sessionKey, _txMid, _trackNameAtReceive, 'onended', remoteStreams)
    }
    trk.onmute = () => {
      // Screen VIDEO has no mute button — a mute means the publisher stopped or
      // the SFU dropped it → cleanup.  DISPLAY-AUDIO mute is reversible (the
      // video keeps flowing) → no cleanup.  Camera/mic mute stays reversible.
      if (_displayAtReceive === 'screen') {
        _cleanupEndedRemoteTrack(sessionKey, _txMid, _trackNameAtReceive, 'onmute', remoteStreams)
      }
    }
    trk.onunmute = () => { /* camera/mic/screenAudio mute stays reversible — no cleanup */ }
  }
  for (const trk of effectiveStream.getTracks()) _bindTrackEndHandlers(trk)
  // F2 FIX (bug-hardening): event-driven onremovetrack — resolve the removed
  // track's OWN transceiver/mid/trackName at event time instead of closing over
  // the FIRST track's values.  The old closure made a merged stream's
  // onremovetrack clean up the wrong transceiver (the first track's mid) when a
  // DIFFERENT track was removed — killing a live mic while re-subscribing with
  // a duplicate mid.  The handler is re-bound to the surviving stream on the
  // merge path below so it always targets the removed track's transceiver.
  const _bindOnRemoveTrack = (stream: MediaStream) => {
    stream.onremovetrack = (ev: Event) => {
      const removedTrack = (ev as MediaStreamTrackEvent).track
      const removedTx = state._pc
        ? state._pc.getTransceivers().find((t) => t.receiver?.track === removedTrack)
        : undefined
      const removedMid = removedTx?.mid ?? null
      const removedInfo = (removedMid ? _remoteMidToTrackName.get(removedMid) : undefined)
        ?? (removedTx ? _transceiverMeta.get(removedTx) : undefined)
      const removedTrackName = removedInfo?.trackName ?? null
      // R#4 (review #3077): a single-track removal from a MERGED participant
      // stream must not delete the whole tile — the browser already removed the
      // track from `stream`; if OTHER tracks remain (e.g. the mic while only the
      // camera was stopped), keep the tile alive and tear down ONLY the removed
      // track's transceiver + mapping.  Full tile teardown runs only when
      // nothing remains.
      const remaining = stream.getTracks().filter((t: MediaStreamTrack) => t !== removedTrack)
      if (remaining.length > 0) {
        log.warn(
          '[cleanup] onremovetrack key=%s — tile kept (remaining=%d) mid=%s trackName=%s',
          sessionKey, remaining.length, removedMid ?? 'none', removedTrackName ?? 'none',
        )
        if (removedMid) _teardownRemoteMedia([removedMid], 'cleanup')
        _dropTrackNameMapping(sessionKey, removedTrackName)
      } else {
        _cleanupEndedRemoteTrack(sessionKey, removedMid, removedTrackName, 'onremovetrack', remoteStreams)
      }
    }
  }
  _bindOnRemoveTrack(effectiveStream)

  // F1 FIX (bug-hardening): a non-screen incoming stream that arrived with all
  // tracks ended was already cleaned up in the bind loop — do NOT add its tile.
  if (_deadNonScreenStream) {
    log.warn('[cleanup] dead non-screen stream key=%s — tile not added', sessionKey)
    return
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
    // F2 FIX (bug-hardening): re-bind onremovetrack on the SURVIVING stream so
    // a later removal cleans up the removed track's own transceiver (the old
    // code kept the abandoned stream's first-track closure).
    _bindOnRemoveTrack(existing)
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
  log.debug('[PC] remote track received, key=%s', sessionKey)
}
