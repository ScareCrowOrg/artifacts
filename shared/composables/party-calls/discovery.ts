/**
 * @file party-calls/discovery.ts
 * @description Room discovery / registry / heartbeat helpers for the
 * usePartyCalls composable (Cloudflare Calls / WebRTC).  Extracted VERBATIM
 * from the former monolithic ``usePartyCalls.ts`` (section "Multi-user SFU
 * helpers").
 *
 * Dependency graph: imports ``_apiFetchJson`` from ``./http``,
 * ``_subscribeToRemoteTracks`` from ``./subscription`` and
 * ``_teardownRemoteMedia`` from ``./sfuSignaling`` + state from ``./state``.
 * No reverse imports — ``./subscription`` NEVER imports this module
 * (anti-cycle rule).  See ``party-calls/README.md``.
 */

import { _apiFetchJson } from './http'
import { _subscribeToRemoteTracks } from './subscription'
import { _teardownRemoteMedia } from './sfuSignaling'
import {
  log,
  state,
  _remoteMidToTrackName,
  _remoteTrackTypes,
  _subscribedSessions,
  _subscribedTrackNames,
  _ownerHasPendingMids,
  _dropTransceiverMeta,
  _pendingSubscribeMids,
  HEARTBEAT_INTERVAL_MS,
} from './state'
import type { RemoteSession } from './types'
import type { TrackType } from '#artifacts/shared/stores/partyStore'
import type { Ref } from 'vue'

// ─────────────────────────────────────────────────────────────────────────────
// Discovery / registry / heartbeat
// ─────────────────────────────────────────────────────────────────────────────

/** Re-discover active room sessions: subscribe to new ones, prune expired. */
export async function _refreshDiscovery(
  roomId: string,
  remoteStreams: Ref<Map<string, MediaStream>>,
  knownParticipants?: ReadonlyArray<{ sessionId?: string }>,
  callerLabel = 'unknown',
): Promise<void> {
  if (!state._currentSessionId) return
  const _dseq = ++state._discoverySeq
  // DIAG (B4): entry marker for EVERY discovery pass — proves the race H3
  // concurrency (R1/R3) by letting F3 correlate interleaved [start]/[end]
  // pairs.  mid_map_size at entry is the state a concurrent prune can drop
  // before the screen ontrack fires.
  log.warn(
    '[DIAG][discovery][start] seq=%d caller=%s room=%s session=%s mid_map_size=%d',
    _dseq, callerLabel, roomId, state._currentSessionId, _remoteMidToTrackName.size,
  )
  try {
    const resp = await _apiFetchJson(`/calls/rooms/${roomId}/sessions`)
    const sessions = (resp.sessions || []) as RemoteSession[]
    const activeIds = new Set(sessions.map((s) => s.sessionId))

    // DIAG (ITER_1 party-cell-mock-remote-user): enumerate EVERY session the
    // registry returned, tagging own-vs-remote and the current user id (from the
    // caller's OWN registry entry).  Cross-reference with the View.vue
    // [DIAG][remoteLabel][LOOKUP-FAIL] log: an orphan tile whose ownerId IS in
    // this list ⇒ H1 (parallel/ghost session); NOT in this list ⇒ H2 (opaque
    // stream.id key that never matches any session).
    const _currentUserId = sessions.find((x) => x.sessionId === state._currentSessionId)?.userId
    for (const s of sessions) {
      const isOwn = s.sessionId === state._currentSessionId
      log.warn(
        '[DIAG][discovery] session=%s userId=%s displayName=%s own=%s tracks=%j trackNames=%j',
        s.sessionId, s.userId ?? '(none)', s.displayName ?? '(none)',
        isOwn ? 'yes' : 'no', s.tracks ?? [], s.trackNames ?? [],
      )
      // REV-2 (F4 gate, party-cell-mock-remote-user): a REMOTE session owned by
      // the SAME user (parallel tab / ghost ≤60s in the registry) IS subscribed
      // again.  With the backend presence now upserting by sessionId (REV-1,
      // main.py), each session has its OWN presence entry — so this same-user
      // tile resolves to its participant and renders with the CORRECT
      // displayName instead of "Usuário Remoto" (View.vue:482).  The original
      // F3 FIX (skip same-user) is REVERTED here per the F4 review; the H2
      // opaque-orphan prune (FIX-2) remains as the "never show orphans" guard.
      // Other users' sessions are still subscribed (multiuser flow intact).
      const isSameUser = !isOwn && !!s.userId && !!_currentUserId && s.userId === _currentUserId
      if (isSameUser) {
        log.warn(
          '[DIAG][discovery][H1-SAME-USER] remote session=%s userId=%s == current_user_id=%s — parallel tab / ghost session of the same user (SUBSCRIBED: REV-1 presence-by-sessionId makes its tile resolve to the correct displayName)',
          s.sessionId, s.userId, _currentUserId,
        )
      }
      if (!isOwn && knownParticipants && !knownParticipants.some((p) => p.sessionId === s.sessionId)) {
        // GHOST suspect: remote session NOT present in the presence list.  Its
        // tile (if media resolves) has no matching participant → "Usuário Remoto".
        // Either a registry ghost (≤60s TTL, calls_rooms.py:63) or a transient
        // presence race (snapshot not yet converged).
        log.warn(
          '[DIAG][discovery][GHOST-SUSPECT] remote session=%s userId=%s NOT in participants=%j — ghost/registry-stale session or presence race',
          s.sessionId, s.userId ?? '(none)',
          (knownParticipants || []).map((p) => p.sessionId),
        )
      }
      // GAP 4: keep the nativeId → display mapping (positional tracks↔trackNames)
      // so _handleRemoteTrack can tell a screen track from the camera.
      if (s.trackNames && s.trackNames.length) {
        const typeMap = _remoteTrackTypes.get(s.sessionId) ?? new Map<string, string>()
        if (s.tracks && s.tracks.length !== s.trackNames.length) {
          // Positional fragility guard: display labels ↔ native trackNames must
          // stay aligned for the 'screen' classification in _handleRemoteTrack.
          log.warn(
            '[DIAG][discovery] %s: tracks.length=%d != trackNames.length=%d — screen type may misclassify',
            s.sessionId, s.tracks.length, s.trackNames.length,
          )
        }
        s.trackNames.forEach((trackName, i) => {
          const display = s.tracks?.[i]
          if (display) typeMap.set(trackName, display)
        })
        _remoteTrackTypes.set(s.sessionId, typeMap)
      }
      // REV-2 (F4 gate): restore subscribing same-user sessions (isSameUser is
      // computed above only for the informative H1-SAME-USER log).  With the
      // backend presence upserting by sessionId (REV-1), a parallel session of
      // the SAME user resolves to its own participant entry → its tile renders
      // with the correct displayName instead of "Usuário Remoto".  Only the own
      // session is excluded via !isOwn (unchanged original guard).
      if (!isOwn) {
        await _subscribeToRemoteTracks(s, remoteStreams)
      }
    }

    // Prune streams whose session is no longer active (ghost participants) OR
    // whose screen track was removed while the session stayed active (B2).
    // Screen tiles are keyed ``{sessionId}/screen`` — map them back to the
    // owning session so they are pruned with it.
    //
    // B3 (two-pass): determine the owners to prune WITHOUT deleting
    // _subscribedSessions mid-iteration — the old code deleted inside the key
    // loop, so a 2nd key of the same owner ({sid}/screen) failed has() and its
    // tile leaked.
    const next = new Map(remoteStreams.value)
    // B2: display-friendly track set per ACTIVE owner from the discovery
    // response (s.tracks = ['mic'] | ['mic','screen']).  When a publisher stops
    // sharing, the registry drops 'screen' but the session stays active.
    const activeTracksByOwner = new Map<string, string[]>()
    for (const s of sessions) activeTracksByOwner.set(s.sessionId, s.tracks ?? [])

    // B3 pass 1: owners whose session left/ghosted (no mutation here).
    const ownersToPrune = new Set<string>()
    for (const ownerId of _subscribedSessions) {
      if (!activeIds.has(ownerId)) ownersToPrune.add(ownerId)
    }

    /** Drop all per-owner mappings for a session that left/ghosted. */
    const removeOwnerMappings = (ownerId: string): void => {
      // F3 FIX (ITER_1 guest-screenshare CICLO 2): a session with an in-flight
      // subscription is NOT genuinely ghosted — a stale concurrent snapshot
      // excluded it, but tracks/new just resolved for it.  Pruning here would
      // drop the just-populated map/WeakMap/_remoteTrackTypes of the incoming
      // screen (race H3).  Defer the owner prune until the pending clears (its
      // ontrack or the 5s timeout); the next discovery re-evaluates.
      if (_ownerHasPendingMids(ownerId)) {
        log.warn('[DIAG][pending] protect owner=%s prune=owner', ownerId)
        return
      }
      _subscribedSessions.delete(ownerId)
      _subscribedTrackNames.delete(ownerId)
      _remoteTrackTypes.delete(ownerId)
      // F3 FIX (CICLO 4): drop the pruned session's mid → trackName mappings so
      // a dead session's mids can't misclassify a re-subscribed track later.
      for (const [mid, info] of _remoteMidToTrackName) {
        if (info.sessionId === ownerId) {
          _remoteMidToTrackName.delete(mid)
          // F3 FIX (ITER_1 H3): keep the transceiver-scoped meta in lockstep so
          // a pruned mid can never misclassify a later re-subscribed track.
          _dropTransceiverMeta(mid)
        }
      }
    }

    /** B2: for an ACTIVE owner, drop only the stale screen track mapping. */
    const removeScreenMapping = (ownerId: string): void => {
      const typeMap = _remoteTrackTypes.get(ownerId)
      if (!typeMap) return
      const screenNativeIds = [...typeMap.entries()]
        .filter(([, display]) => display === 'screen')
        .map(([nativeId]) => nativeId)
      if (screenNativeIds.length === 0) return
      // F3 FIX (ITER_1 guest-screenshare CICLO 2): the screen nativeIds whose
      // subscription is STILL IN FLIGHT (race H3) must keep their typeMap entry,
      // _subscribedTrackNames entry and mid mapping — a concurrent stale
      // snapshot sees the owner without 'screen' (or the owner as ghosted) while
      // the new screen's tracks/new already resolved.  Dropping them here would
      // make the incoming ontrack fall back to the opaque stream.id.
      const protectedNativeIds = new Set<string>()
      for (const mid of _pendingSubscribeMids) {
        const info = _remoteMidToTrackName.get(mid)
        if (info?.sessionId === ownerId && screenNativeIds.includes(info.trackName)) {
          protectedNativeIds.add(info.trackName)
        }
      }
      for (const nativeId of screenNativeIds) {
        if (!protectedNativeIds.has(nativeId)) typeMap.delete(nativeId)
      }
      const already = _subscribedTrackNames.get(ownerId)
      if (already) {
        _subscribedTrackNames.set(ownerId, already.filter((n) =>
          !screenNativeIds.includes(n) || protectedNativeIds.has(n)))
      }
      for (const [mid, info] of _remoteMidToTrackName) {
        if (info.sessionId === ownerId && screenNativeIds.includes(info.trackName)) {
          if (protectedNativeIds.has(info.trackName)) {
            log.warn('[DIAG][pending] protect mid=%s session=%s prune=screen', mid, ownerId)
            continue
          }
          _remoteMidToTrackName.delete(mid)
          // F3 FIX (ITER_1 H3): keep the transceiver-scoped meta in lockstep.
          _dropTransceiverMeta(mid)
        }
      }
    }

    let changed = false
    let _screenRemovedCount = 0
    // B3 pass 2: decide per key using the pre-computed owner set (never mutated
    // during the iteration) plus the B2 screen-removed condition.
    for (const key of next.keys()) {
      const ownerId = key.endsWith('/screen') ? key.slice(0, -'/screen'.length) : key
      const sessionLeft = ownersToPrune.has(ownerId)
      const screenRemoved = key.endsWith('/screen') && activeIds.has(ownerId)
        && !(activeTracksByOwner.get(ownerId) ?? []).includes('screen')
      // F3 FIX (ITER_1 party-cell-mock-remote-user, H2): an OPAQUE-ORPHAN tile —
      // a non-screen key that is neither an active registry session NOR a
      // successfully-subscribed session.  These keys come from the
      // _handleRemoteTrack last-resort fallback `sessionKey = stream.id ||
      // track.id || 'remote'` (:1267): a received track whose mid resolved to
      // NO owner.  Such a key never matches a participant (permanent
      // "Usuário Remoto", View.vue:482) and the existing prune (ownersToPrune /
      // screenRemoved) never removes it, because it is absent from BOTH
      // _subscribedSessions AND activeIds.  Screen tiles (own or not) and real
      // owner tiles are left untouched — only truly-orphaned opaque keys are
      // cleaned.  This is the "never pruned" half of the ghost-tile symptom.
      const opaqueOrphan = !key.endsWith('/screen')
        && !activeIds.has(ownerId) && !_subscribedSessions.has(ownerId)
      if (sessionLeft || screenRemoved || opaqueOrphan) {
        // DIAG (ITER_1 party-cell-mock-remote-user, H2): the opaque-key tile is
        // being removed — surfaces the orphan so F7 can confirm the prune fired
        // for a tile that the discovery subscribe-guard never created (the
        // session this key belongs to is NOT in activeIds/subscribedSessions).
        if (opaqueOrphan) {
          log.warn(
            '[DIAG][discovery][H2-PRUNED-OPAQUE] key=%s ownerId=%s — tile with opaque/non-resolvable key removed (no participant, never pruned before)',
            key, ownerId,
          )
        }
        // S2 (F3): capture the receiver mids for the removed screen BEFORE the
        // mappings are dropped (removeScreenMapping deletes them), so the
        // recvonly transceivers can be stopped locally — the prune removes the
        // TILE but not the media path (recvonly receiver + SFU subscription
        // survive) unless the receiver is torn down here.
        const screenMids: string[] = []
        if (screenRemoved) {
          for (const [mid, info] of _remoteMidToTrackName) {
            if (info.sessionId === ownerId
              && _remoteTrackTypes.get(ownerId)?.get(info.trackName) === 'screen') {
              screenMids.push(mid)
            }
          }
        }
        next.delete(key)
        if (sessionLeft) removeOwnerMappings(ownerId)
        else removeScreenMapping(ownerId)
        if (screenRemoved) {
          _screenRemovedCount += 1
          // S2 (F3): stop the receiver transceivers for the removed screen
          // track locally (no tracks/remove endpoint to un-subscribe via SFU).
          _teardownRemoteMedia(screenMids, 'prune')
        }
        changed = true
      }
    }

    // B3: clean up owner-level maps for pruned sessions, outside the key loop.
    for (const ownerId of ownersToPrune) removeOwnerMappings(ownerId)

    if (changed) remoteStreams.value = next
    // DIAG (B4): exit marker — how the mid map + subscribed set changed across
    // this pass.  owners_to_prune>0 / screen_removed>0 mean a prune deleted
    // mids; F3 correlates against [start] mid_map_size to prove whether a
    // CONCURRENT pass pruned the screen mid between population (:376) and the
    // screen ontrack (race H3).
    log.warn(
      '[DIAG][discovery][end] seq=%d caller=%s session=%s mid_map_size=%d owners_to_prune=%d screen_removed=%d subscribed_sessions=%d',
      _dseq, callerLabel, state._currentSessionId, _remoteMidToTrackName.size,
      ownersToPrune.size, _screenRemovedCount, _subscribedSessions.size,
    )
  } catch (err) {
    log.warn('[discovery] refresh failed: %s',
      err instanceof Error ? err.message : String(err))
    // DIAG (B4): error path still emits the end marker so a failing pass can't
    // be mistaken for a pass that never ran.
    log.warn(
      '[DIAG][discovery][end][error] seq=%d caller=%s session=%s mid_map_size=%d',
      _dseq, callerLabel, state._currentSessionId, _remoteMidToTrackName.size,
    )
  }
}

/**
 * Register the caller's session in the room and subscribe to remote sessions.
 *
 * ``tracks`` are the display-friendly TrackType labels ('mic'/'camera') kept
 * for the UI; ``trackNames`` are the publisher's NATIVE MediaStreamTrack ids
 * (sender.track.id) that the Cloudflare SFU registered — the names remote
 * subscribers must reference to resolve the media tracks.
 */
export async function _registerAndDiscoverSessions(
  roomId: string,
  remoteStreams: Ref<Map<string, MediaStream>>,
  tracks: TrackType[],
  trackNames: string[],
  knownParticipants?: ReadonlyArray<{ sessionId?: string }>,
): Promise<void> {
  if (!state._currentSessionId) return
  const body: Record<string, unknown> = {
    sessionId: state._currentSessionId,
    tracks,
  }
  if (trackNames.length) body.trackNames = trackNames
  log.warn(
    '[DIAG][register] room=%s session=%s tracks=%j trackNames=%j',
    roomId, state._currentSessionId, tracks, trackNames,
  )
  await _apiFetchJson(`/calls/rooms/${roomId}/sessions`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
  await _refreshDiscovery(roomId, remoteStreams, knownParticipants, 'register')
}

/**
 * Re-register the caller's session in the room registry with EXTENDED
 * tracks/trackNames (upsert — calls_rooms.register_session writes via hset) and
 * refresh discovery so subscribers learn about newly added tracks.  GAP 2: the
 * shared screen must appear in GET /rooms/{room}/sessions before anyone can
 * subscribe to it.  Caller: shareStream (when a screen track is added).
 */
export async function _updateRegistryTracks(
  roomId: string,
  tracks: TrackType[],
  trackNames: string[],
  remoteStreams: Ref<Map<string, MediaStream>>,
  knownParticipants?: ReadonlyArray<{ sessionId?: string }>,
): Promise<void> {
  if (!state._currentSessionId) return
  const body: Record<string, unknown> = {
    sessionId: state._currentSessionId,
    tracks,
  }
  if (trackNames.length) body.trackNames = trackNames
  log.warn(
    '[DIAG][registry] re-register room=%s session=%s tracks=%j trackNames=%j',
    roomId, state._currentSessionId, tracks, trackNames,
  )
  await _apiFetchJson(`/calls/rooms/${roomId}/sessions`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
  await _refreshDiscovery(roomId, remoteStreams, knownParticipants, 'registry')
}

/** Start the periodic heartbeat + discovery refresh. */
export function _startHeartbeat(
  roomId: string,
  sessionId: string,
  remoteStreams: Ref<Map<string, MediaStream>>,
  knownParticipants?: ReadonlyArray<{ sessionId?: string }>,
): void {
  _stopHeartbeat()
  state._heartbeatTimer = window.setInterval(() => {
    void (async () => {
      try {
        await _apiFetchJson(
          `/calls/rooms/${roomId}/sessions/${sessionId}/heartbeat`,
          { method: 'PUT' },
        )
      } catch (err) {
        log.warn('[heartbeat] renewal failed: %s',
          err instanceof Error ? err.message : String(err))
      }
      await _refreshDiscovery(roomId, remoteStreams, knownParticipants, 'heartbeat')
    })()
  }, HEARTBEAT_INTERVAL_MS)
}

export function _stopHeartbeat(): void {
  if (state._heartbeatTimer !== null) {
    window.clearInterval(state._heartbeatTimer)
    state._heartbeatTimer = null
  }
}
