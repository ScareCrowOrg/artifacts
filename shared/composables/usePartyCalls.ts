/**
 * @file usePartyCalls.ts
 * @description Vue 3 composable for Cloudflare Calls (WebRTC) — voice, video,
 * and screen-sharing in a room.  Multi-user: sessions are registered in a room
 * registry (Redis), remote sessions discovered, and their tracks subscribed via
 * the Cloudflare tracks/new proxy.
 *
 * Presence is **server-authoritative**: the party-cell backend script publishes
 * snapshot envelopes to ``calls:room:{roomId}``; ``useDistributedState``
 * replaces the ``participants`` branch with the authoritative list.
 *
 * A heartbeat every 20 s renews the 60 s registry TTL; a closed tab without
 * ``hangUp`` expires the registration (ghost cleanup).
 */

import { ref, computed, onUnmounted, type Ref } from 'vue'
import { usePartyStore, type Participant, type TrackType } from '#artifacts/shared/stores/partyStore'
import { useDistributedState } from '#artifacts/shared/composables/useDistributedState'
import { apiFetch } from '#artifacts/shared/services/apiService'
import { createLogger } from '@/utils/logger'

const log = createLogger('composable:usePartyCalls')

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Lifecycle phase of a party call, driving the connecting UX (F1).  The UI
 * shows a spinner + phase message while ``isConnecting`` is true and only
 * flips the "live" indicator when the phase reaches ``'connected'``.
 */
export type ConnectionPhase =
  | 'idle'
  | 'provisioning'
  | 'requesting-media'
  | 'signaling'
  | 'registering'
  | 'connected'
  | 'error'

/** A room discovered via ``listAvailableRooms`` (F4 — GET /calls/rooms). */
export interface AvailableRoom {
  roomId: string
  sessionCount: number
  sessions: RemoteSession[]
}

export interface UsePartyCallsReturn {
  isConnected: Ref<boolean>
  isProvisioning: Ref<boolean>
  /** Phase of the current (or last attempted) call — see ConnectionPhase. */
  connectionPhase: Ref<ConnectionPhase>
  /** True while the call is being set up (spinner + phase message). */
  isConnecting: Ref<boolean>
  /** Whether the local camera video is enabled (F2). */
  cameraEnabled: Ref<boolean>
  /** Whether the caller is currently sharing their screen (F2). */
  isSharingScreen: Ref<boolean>
  localStream: Ref<MediaStream | null>
  /** The publisher's own media for the self-view tile (S1): the camera stream
   *  during a call, swapped to the shared screen while sharing.  Local only —
   *  never sent via SFU (the screen transceiver is sendonly). */
  selfViewStream: Ref<MediaStream | null>
  /** Remote streams keyed by remote sessionId */
  remoteStreams: Ref<Map<string, MediaStream>>
  participants: Ref<Participant[]>
  connectionError: Ref<string | null>
  startCall: (roomId: string) => Promise<void>
  shareStream: (stream: MediaStream) => Promise<void>
  muteAudio: () => void
  /** Toggle the local camera on/off independently of mic/screen (F2). */
  toggleCamera: () => void
  /** Start (or stop, when already sharing) screen sharing (F2). */
  toggleScreenShare: () => Promise<void>
  /** Stop an active screen share (F2).  Async since S2 fix renegotiates with
   *  the SFU after removeTrack. */
  stopSharing: () => Promise<void>
  /** Refresh presence + remote discovery on demand (F5). */
  refreshRoom: () => Promise<void>
  /** List rooms with ≥1 active session (F4). */
  listAvailableRooms: () => Promise<AvailableRoom[]>
  /** Join an existing room by id (F4). */
  joinRoom: (roomId: string) => Promise<void>
  hangUp: () => void
  requestSnapshot: () => Promise<void>
}

/** A session discovered in the room registry. */
interface RemoteSession {
  sessionId: string
  userId?: string
  displayName?: string
  /** Display-friendly TrackType labels ('mic'/'camera') — for the UI grid. */
  tracks?: TrackType[]
  /** The publisher's NATIVE MediaStreamTrack ids (sender.track.id) as
   *  registered on the Cloudflare SFU.  When present, subscriptions MUST
   *  reference these exact names — the SFU resolves native track ids, not the
   *  display labels ('mic'/'camera' → not_found_track_error, H1 F7 ciclo 2). */
  trackNames?: string[]
}

/** Per-track result echoed by the Cloudflare tracks/new proxy.  A track that
 *  failed to resolve on the SFU carries ``errorCode``/``errorDescription``
 *  (e.g. ``not_found_track_error``, ``empty_track_error``). */
interface SfuTrackResult {
  trackName?: string
  mid?: string
  errorCode?: string
  errorDescription?: string
}

// ─────────────────────────────────────────────────────────────────────────────
// Module-level state (shared across composable instances)
// ─────────────────────────────────────────────────────────────────────────────

let _pc: RTCPeerConnection | null = null
let _localStream: MediaStream | null = null
let _currentSessionId: string | null = null
let _heartbeatTimer: number | null = null
const _subscribedSessions = new Set<string>()
/** The display stream being shared (screen/3D canvas) — stopped on hangUp. */
let _screenStream: MediaStream | null = null
/** Display-friendly TrackTypes this caller has published to the room (startCall
 *  base + 'screen' after shareStream) — kept so registry/presence updates carry
 *  the REAL track set (GAP 2). */
let _publishedTracks: TrackType[] = []
/** NATIVE track names (sender.track.id) this caller has published. */
let _publishedTrackNames: string[] = []
/** Native trackNames already subscribed per remote sessionId (GAP 3 — the
 *  heartbeat re-subscribes only the delta when a session adds a new track). */
const _subscribedTrackNames = new Map<string, string[]>()
/** sessionId → { nativeTrackId → 'mic'|'camera'|'screen' } — lets
 *  _handleRemoteTrack tell a screen track apart from the camera (GAP 4). */
const _remoteTrackTypes = new Map<string, Map<string, string>>()
/** mid (receiving transceiver) → {sessionId, trackName} for remote tracks,
 *  populated from the tracks/new remote response.  The mid is the ONLY reliable
 *  bridge to the publisher's native trackName — Cloudflare delivers the received
 *  track.id OPAQUE (no {sessionId}/{trackName} slash format), so the ontrack can
 *  classify via event.transceiver.mid against this map (F3 CICLO 4). */
const _remoteMidToTrackName = new Map<string, { sessionId: string; trackName: string }>()
/** The native MediaStreamTrack id of the currently shared screen (if any) —
 *  used by stopSharing to detach the correct sender from the peer connection. */
let _screenTrackId: string | null = null
/** The sendonly screen transceiver orphaned by the last stopSharing
 *  (``sender.track`` nulled by ``removeTrack`` but the transceiver kept) —
 *  reused by the next shareStream via ``replaceTrack`` so each share/stop cycle
 *  does NOT stack a new transceiver (A1; avoids the SFU's 413 accumulation
 *  error).  Captured explicitly because the old direction-only orphan search
 *  missed the transceiver once the last offer had re-negotiated its direction. */
let _orphanScreenTx: RTCRtpTransceiver | null = null
/** Display-friendly TrackType → the publisher's NATIVE track names currently
 *  known for the local streams.  Populated by startCall (mic/camera) and
 *  shareStream (screen); consumed by ``_updatePublishedTracks`` so the room
 *  registry + presence carry the REAL active track set when the camera is
 *  toggled off/on or the screen is stopped (F2). */
const _localTrackNamesByDisplay = new Map<TrackType, string[]>()

const HEARTBEAT_INTERVAL_MS = 20_000 // must be < the 60 s registry TTL

// ─────────────────────────────────────────────────────────────────────────────
// HTTP helpers
// ─────────────────────────────────────────────────────────────────────────────

/** Thin wrapper around apiFetch that throws with the server's error detail. */
async function _apiFetchJson(path: string, options: RequestInit = {}): Promise<any> {
  const resp = await apiFetch(path, options)
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`
    try {
      const body = await resp.json()
      if (body.detail) detail = body.detail
    } catch { /* ignore parse errors */ }
    throw new Error(detail)
  }
  return resp.json()
}

/** Poll the async provision task until it completes or fails. */
async function _pollProvisionTask(
  taskId: string,
  maxRetries = 100,
  intervalMs = 2000,
): Promise<{ app_id: string }> {
  for (let i = 0; i < maxRetries; i++) {
    const resp = await _apiFetchJson(`/calls/provision/${taskId}`)
    if (resp.status === 'completed') {
      log.debug('[pollProvision] task completed, app_id=%s', resp.app_id)
      return { app_id: resp.app_id }
    }
    if (resp.status === 'failed') {
      throw new Error(`Provision failed: ${resp.error || 'Unknown provision error'}`)
    }
    await new Promise(resolve => setTimeout(resolve, intervalMs))
  }
  throw new Error('Provision timeout — task did not complete within the retry limit')
}

/** Execute a party-cell backend action via execute-ephemeral (best-effort). */
async function _executePartyAction(input: Record<string, unknown>): Promise<void> {
  try {
    const resp = await apiFetch('/api/cells/execute-ephemeral', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cell_type: 'party-cell', input_data: input }),
    })
    if (!resp.ok) {
      const text = await resp.text().catch(() => '')
      log.warn('[partyAction] action=%s failed (%s): %s', input.action, resp.status, text)
    }
  } catch (err) {
    log.warn('[partyAction] action=%s error: %s', input.action,
      err instanceof Error ? err.message : String(err))
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Multi-user SFU helpers (subscribe / discover / heartbeat)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Subscribe to a remote session's media tracks via Cloudflare tracks/new.
 *
 * Contract (realtime-api-2024-05-21.yaml, `remote_tracks` example): a remote
 * subscription is a TRACKS-ONLY request — each TrackObject carries
 * ``location:'remote'`` + ``sessionId`` (the track owner) + ``trackName`` (the
 * exact name the publisher registered).  The client does NOT build its own
 * offer: the SFU generates it and responds with ``requiresImmediateRenegotiation``
 * + an offer that we answer and send back via ``PUT /renegotiate``
 * (react-native-webrtc pattern).  This avoids re-offering ``_pc``'s already
 * negotiated m= sections (406) and client-side transceiver accumulation (413).
 */
async function _subscribeToRemoteTracks(
  remote: RemoteSession,
  remoteStreams: Ref<Map<string, MediaStream>>,
): Promise<void> {
  if (!_pc || !_currentSessionId) return

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

  // DIAG (F1 P2): transceiver count BEFORE the request — in the tracks-only
  // flow no recvonly transceivers are added client-side, so this stays flat
  // across heartbeat retries (no accumulation → no 413).
  const txsBeforeOffer = _pc.getTransceivers()
  log.warn(
    '[DIAG][subscribe] %s: transceivers_before_offer=%d recvonly_mids=%j new_trackNames=%j',
    remote.sessionId, txsBeforeOffer.length,
    txsBeforeOffer.filter((t) => t.direction === 'recvonly').map((t) => t.mid),
    trackNames,
  )

  const tracksToSend = trackNames.map((trackName) => ({
    location: 'remote' as const,
    sessionId: remote.sessionId,
    trackName,
  }))
  log.warn('[DIAG][subscribe] %s: tracks_payload=%j', remote.sessionId, tracksToSend)

  try {
    const result = await _apiFetchJson(
      `/calls/sessions/${_currentSessionId}/tracks/new`,
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
    // requiresImmediateRenegotiation branch the ontrack fires AS SOON AS the
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
    for (const entry of midEntries) {
      if (entry.mid && entry.trackName) {
        _remoteMidToTrackName.set(entry.mid, { sessionId: remote.sessionId, trackName: entry.trackName })
      }
    }
    if (midEntries.length > 0) {
      log.warn(
        '[DIAG][subscribe] mid_map populated session=%s entries=%j',
        remote.sessionId, midEntries,
      )
    }

    if (result?.requiresImmediateRenegotiation && respSd?.type === 'offer' && respSdp.length > 0) {
      // SFU generated the offer — apply it, answer, and send the answer back
      // via the renegotiate proxy so the SFU completes the m-line setup.
      await _pc.setRemoteDescription(new RTCSessionDescription(respSd))

      // DIAG (F1 P2): the SFU offer's m-sections / mids — confirms the media
      // lines are bounded (recvonly only; no growth across retries).
      log.warn(
        '[DIAG][subscribe] %s: offer type=%s sdp_len=%d m_sections=%d mids=%j',
        remote.sessionId, respSd.type, respSdp.length,
        (respSdp.match(/^m=\w+/gm) || []).length,
        _pc.getTransceivers().map((t) => t.mid),
      )

      const localAnswer = await _pc.createAnswer()
      await _pc.setLocalDescription(localAnswer)
      await _apiFetchJson(
        `/calls/sessions/${_currentSessionId}/renegotiate`,
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
      await _pc.setRemoteDescription(new RTCSessionDescription(respSd))
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
      // F3 FIX (CICLO 5): the _remoteMidToTrackName population was MOVED up to
      // right after the tracks/new (remote) fetch, BEFORE the branch below — so
      // the map is populated before setRemoteDescription fires the ontrack.  L7
      // (mid_map populated) is emitted at that earlier point; nothing left here.
      log.info(
        '[subscribe] subscribed to remote session=%s answer_type=%s trackNames=%j',
        remote.sessionId, respSd?.type, trackNames,
      )
    }
  } catch (err) {
    log.warn('[subscribe] failed for remote session=%s current_session=%s: %s',
      remote.sessionId, _currentSessionId,
      err instanceof Error ? err.message : String(err))
  }
}

/** Re-discover active room sessions: subscribe to new ones, prune expired. */
async function _refreshDiscovery(
  roomId: string,
  remoteStreams: Ref<Map<string, MediaStream>>,
): Promise<void> {
  if (!_currentSessionId) return
  try {
    const resp = await _apiFetchJson(`/calls/rooms/${roomId}/sessions`)
    const sessions = (resp.sessions || []) as RemoteSession[]
    const activeIds = new Set(sessions.map((s) => s.sessionId))

    for (const s of sessions) {
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
      if (s.sessionId !== _currentSessionId) {
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
      _subscribedSessions.delete(ownerId)
      _subscribedTrackNames.delete(ownerId)
      _remoteTrackTypes.delete(ownerId)
      // F3 FIX (CICLO 4): drop the pruned session's mid → trackName mappings so
      // a dead session's mids can't misclassify a re-subscribed track later.
      for (const [mid, info] of _remoteMidToTrackName) {
        if (info.sessionId === ownerId) _remoteMidToTrackName.delete(mid)
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
      for (const nativeId of screenNativeIds) typeMap.delete(nativeId)
      const already = _subscribedTrackNames.get(ownerId)
      if (already) {
        _subscribedTrackNames.set(ownerId, already.filter((n) => !screenNativeIds.includes(n)))
      }
      for (const [mid, info] of _remoteMidToTrackName) {
        if (info.sessionId === ownerId && screenNativeIds.includes(info.trackName)) {
          _remoteMidToTrackName.delete(mid)
        }
      }
    }

    let changed = false
    // B3 pass 2: decide per key using the pre-computed owner set (never mutated
    // during the iteration) plus the B2 screen-removed condition.
    for (const key of next.keys()) {
      const ownerId = key.endsWith('/screen') ? key.slice(0, -'/screen'.length) : key
      const sessionLeft = ownersToPrune.has(ownerId)
      const screenRemoved = key.endsWith('/screen') && activeIds.has(ownerId)
        && !(activeTracksByOwner.get(ownerId) ?? []).includes('screen')
      if (sessionLeft || screenRemoved) {
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
          // S2 (F3): stop the receiver transceivers for the removed screen
          // track locally (no tracks/remove endpoint to un-subscribe via SFU).
          _teardownRemoteMedia(screenMids)
        }
        changed = true
      }
    }

    // B3: clean up owner-level maps for pruned sessions, outside the key loop.
    for (const ownerId of ownersToPrune) removeOwnerMappings(ownerId)

    if (changed) remoteStreams.value = next
  } catch (err) {
    log.warn('[discovery] refresh failed: %s',
      err instanceof Error ? err.message : String(err))
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
async function _registerAndDiscoverSessions(
  roomId: string,
  remoteStreams: Ref<Map<string, MediaStream>>,
  tracks: TrackType[],
  trackNames: string[],
): Promise<void> {
  if (!_currentSessionId) return
  const body: Record<string, unknown> = {
    sessionId: _currentSessionId,
    tracks,
  }
  if (trackNames.length) body.trackNames = trackNames
  log.warn(
    '[DIAG][register] room=%s session=%s tracks=%j trackNames=%j',
    roomId, _currentSessionId, tracks, trackNames,
  )
  await _apiFetchJson(`/calls/rooms/${roomId}/sessions`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
  await _refreshDiscovery(roomId, remoteStreams)
}

/**
 * Re-register the caller's session in the room registry with EXTENDED
 * tracks/trackNames (upsert — calls_rooms.register_session writes via hset) and
 * refresh discovery so subscribers learn about newly added tracks.  GAP 2: the
 * shared screen must appear in GET /rooms/{room}/sessions before anyone can
 * subscribe to it.  Caller: shareStream (when a screen track is added).
 */
async function _updateRegistryTracks(
  roomId: string,
  tracks: TrackType[],
  trackNames: string[],
  remoteStreams: Ref<Map<string, MediaStream>>,
): Promise<void> {
  if (!_currentSessionId) return
  const body: Record<string, unknown> = {
    sessionId: _currentSessionId,
    tracks,
  }
  if (trackNames.length) body.trackNames = trackNames
  log.warn(
    '[DIAG][registry] re-register room=%s session=%s tracks=%j trackNames=%j',
    roomId, _currentSessionId, tracks, trackNames,
  )
  await _apiFetchJson(`/calls/rooms/${roomId}/sessions`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
  await _refreshDiscovery(roomId, remoteStreams)
}

/** Start the periodic heartbeat + discovery refresh. */
function _startHeartbeat(
  roomId: string,
  sessionId: string,
  remoteStreams: Ref<Map<string, MediaStream>>,
): void {
  _stopHeartbeat()
  _heartbeatTimer = window.setInterval(() => {
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
      await _refreshDiscovery(roomId, remoteStreams)
    })()
  }, HEARTBEAT_INTERVAL_MS)
}

function _stopHeartbeat(): void {
  if (_heartbeatTimer !== null) {
    window.clearInterval(_heartbeatTimer)
    _heartbeatTimer = null
  }
}

/** Resolve true once the peer connection reaches 'connected'/'completed'. */
function _waitForIceConnected(
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
      log.warn(
        '[DIAG][PC] iceConnectionState=%s connectionState=%s',
        s, pc.connectionState,
      )
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
async function _registerLocalTracksOnSfu(
  pc: RTCPeerConnection,
  sessionId: string,
  trackObjs: Array<{ location: 'local'; mid: string; trackName: string }>,
  sessionDescription?: { type: string; sdp: string },
): Promise<any> {
  if (!_currentSessionId || !trackObjs.length) return null

  const connected = await _waitForIceConnected(pc, 10_000)
  if (!connected) {
    log.warn(
      '[DIAG][publish] ICE not connected within timeout — local tracks NOT registered on SFU',
    )
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
    log.warn(
      '[DIAG][publish] tracks/new session=%s has_sdp=%s sdp_type=%s sdp_len=%d',
      sessionId,
      Object.prototype.hasOwnProperty.call(body, 'sessionDescription') ? 'yes' : 'no',
      sessionDescription?.type,
      String(sessionDescription?.sdp || '').length,
    )
    const result = await _apiFetchJson(
      `/calls/sessions/${sessionId}/tracks/new`,
      { method: 'POST', body: JSON.stringify(body) },
    )
    const perTrack = (Array.isArray(result?.tracks) ? result.tracks : [])
      .map((t: SfuTrackResult) => (t && typeof t === 'object'
        ? { trackName: t.trackName, mid: t.mid, errorCode: t.errorCode, errorDescription: t.errorDescription }
        : t))
    log.warn(
      '[DIAG][publish] local tracks registered on SFU session=%s answer_type=%s answer_sdp_len=%d requires_renog=%s per_track=%j',
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
      '[DIAG][publish] local track registration failed session=%s: %s',
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
function _teardownRemoteMedia(mids: string[]): void {
  if (!_pc || !mids.length) return
  for (const mid of mids) {
    const tx = _pc.getTransceivers().find((t) => t.mid === mid)
    if (tx && tx.receiver) {
      try {
        tx.stop()
        _pc.removeTransceiver(tx)
      } catch {
        try { tx.direction = 'inactive' } catch { /* ignore */ }
      }
    }
    _remoteMidToTrackName.delete(mid)
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
async function _answerSfuRenegotiationOffer(respSd: RTCSessionDescriptionInit): Promise<void> {
  if (!_pc || !_currentSessionId) return
  await _pc.setRemoteDescription(new RTCSessionDescription(respSd))
  const localAnswer = await _pc.createAnswer()
  await _pc.setLocalDescription(localAnswer)
  await _apiFetchJson(
    `/calls/sessions/${_currentSessionId}/renegotiate`,
    {
      method: 'PUT',
      body: JSON.stringify({
        sessionDescription: { type: localAnswer.type, sdp: localAnswer.sdp },
      }),
    },
  )
  log.warn(
    '[stopSharing] tracks/close renegotiation answered session=%s answer_type=%s',
    _currentSessionId, localAnswer.type,
  )
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
 * (``_orphanScreenTx.mid``), which survives ``removeTrack`` — NOT the native
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
async function _removeTrackFromSfu(mid: string): Promise<void> {
  if (!_currentSessionId) return
  // DIAG (F2, P3): expose the value actually placed in the URL + the mid
  // available on the orphaned sendonly screen transceiver (_orphanScreenTx set
  // by stopSharing).  The tracks/close contract requires the transceiver MID
  // (CloseTrackObject.mid), NOT the native MediaStreamTrack id (_screenTrackId)
  // — F7 greps this line to confirm target === orphan_mid (both the same mid)
  // after the F3 fix.
  log.warn(
    '[stopSharing] _removeTrackFromSfu DIAG target=%s session=%s orphan_mid=%s url=%s',
    mid, _currentSessionId, _orphanScreenTx?.mid ?? 'none',
    `/calls/sessions/${_currentSessionId}/tracks/${encodeURIComponent(mid)}`,
  )
  try {
    const result = await _apiFetchJson(
      `/calls/sessions/${_currentSessionId}/tracks/${encodeURIComponent(mid)}`,
      { method: 'DELETE' },
    )
    log.info(
      '[stopSharing] track removed from SFU session=%s track=%s',
      _currentSessionId, mid,
    )
    // DIAG (F2, P6): the tracks/close RESPONSE — lets F7 validate the `force`
    // blind spot (whether the SFU asks for a renegotiation answer).  Requires
    // the F3 backend change to propagate requiresImmediateRenegotiation/
    // sessionDescription.
    const respSd = result?.sessionDescription
    const respSdp = respSd?.sdp ? String(respSd.sdp) : ''
    log.warn(
      '[stopSharing] _removeTrackFromSfu DIAG response session=%s target=%s requires_renog=%s resp_sd_type=%s resp_sdp_chars=%d',
      _currentSessionId, mid,
      String(result?.requiresImmediateRenegotiation),
      respSd?.type,
      respSdp.length,
    )
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
      _currentSessionId, mid,
      err instanceof Error ? err.message : String(err),
    )
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Composable
// ─────────────────────────────────────────────────────────────────────────────

export function usePartyCalls(): UsePartyCallsReturn {
  const store = usePartyStore()

  // ── Reactive state ───────────────────────────────────────────────────────
  const isConnected = ref(false)
  const isProvisioning = ref(false)
  /** Call lifecycle phase — drives the connecting spinner/status (F1). */
  const connectionPhase = ref<ConnectionPhase>('idle')
  /** True while the call is being set up (provisioning → registering). */
  const isConnecting = computed(() =>
    ['provisioning', 'requesting-media', 'signaling', 'registering'].includes(connectionPhase.value),
  )
  /** Whether the local camera video is enabled (F2). */
  const cameraEnabled = ref(false)
  /** Whether the caller is currently sharing their screen (F2). */
  const isSharingScreen = ref(false)
  const localStream = ref<MediaStream | null>(null)
  /** Self-view stream (S1): the publisher's own camera, swapped to the shared
   *  screen while sharing.  Local-only preview — never sent via SFU.  Flat ref
   *  (Buffer Local Pattern — REACTIVITY_ISOLATION.md), updated directly by
   *  startCall/shareStream/stopSharing/hangUp. */
  const selfViewStream = ref<MediaStream | null>(null)
  const remoteStreams = ref<Map<string, MediaStream>>(new Map())
  const connectionError = ref<string | null>(null)
  const _currentRoomRef = ref<string | null>(null)

  /** Expose participants from the store as a convenience ref. */
  const participants = computed<Participant[]>(() => store.participants)

  // ── Distributed state (room presence) ──────────────────────────────────
  // useDistributedState is called ONCE at composable level.  A computed
  // contextId reactively switches between the active room and an empty channel
  // when idle; the composable auto-reconnects whenever the contextId changes.
  //
  // conflictStrategy 'append': presence is server-authoritative (the script
  // publishes snapshot envelopes).  The client never emits replace patches, so
  // one participant's local reset can't wipe another's participant list.
  const _roomCtx = computed(() => {
    const roomId = _currentRoomRef.value
    return roomId ? `calls:room:${roomId}` : ''
  })

  useDistributedState({
    contextId: _roomCtx,
    store: store as any,
    branch: 'participants',
    conflictStrategy: 'append',
  })

  // ── Internal helpers ─────────────────────────────────────────────────────

  /** Create an RTCPeerConnection configured with the given ICE servers. */
  function _createPeerConnection(iceServers: RTCIceServer[] = []): RTCPeerConnection {
    const pc = new RTCPeerConnection({ iceServers })

    pc.oniceconnectionstatechange = () => {
      log.debug('[PC] iceConnectionState:', pc.iceConnectionState)
      if (
        pc.iceConnectionState === 'disconnected' ||
        pc.iceConnectionState === 'failed' ||
        pc.iceConnectionState === 'closed'
      ) {
        isConnected.value = false
        connectionPhase.value = 'error'
        connectionError.value = `Connection lost: ${pc.iceConnectionState}`
      }
    }

    pc.ontrack = _handleRemoteTrack

    return pc
  }

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
  ): void {
    const next = new Map(remoteStreams.value)
    if (next.has(key)) {
      next.delete(key)
      remoteStreams.value = next
    }
    if (mid) _teardownRemoteMedia([mid])
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
  function _handleRemoteTrack(event: RTCTrackEvent): void {
    const [stream] = event.streams
    if (!stream) return

    // DIAG (F2 CICLO 4): capture the raw ontrack fields BEFORE classification.
    // Cloudflare delivers an OPAQUE track.id (no '/'), so the regex branch below
    // never matches and classification must resolve the owner via
    // event.transceiver.mid → _remoteMidToTrackName (F3). This log lets F7
    // confirm the mid present on the ontrack (e.g. '4' for the screen) matches
    // the mid echoed in the tracks/new response (see the [DIAG][subscribe]
    // mid_map log) — the bridge that makes an opaque track.id classifiable.
    log.warn(
      '[DIAG][remote-track] ontrack session=%s track_id=%s track_id_has_slash=%s transceiver_mid=%s stream_id=%s',
      _currentSessionId, event.track.id, /\//.test(event.track.id || ''),
      event.transceiver?.mid ?? 'none', stream.id,
    )

    const trackIdMatch = /^([^/]+)\/(.+)$/.exec(event.track.id || '')
    let sessionKey: string
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
          ownerId, trackName, sessionKey, stream.id,
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
      const info = transceiverMid ? _remoteMidToTrackName.get(transceiverMid) : undefined
      if (info) {
        const ownerId = info.sessionId
        const display = _remoteTrackTypes.get(ownerId)?.get(info.trackName)
        sessionKey = display === 'screen' ? `${ownerId}/screen` : ownerId
        if (display === 'screen') {
          log.warn(
            '[DIAG][remote-track] screen track received sessionId=%s trackName=%s sessionKey=%s stream_id=%s',
            ownerId, info.trackName, sessionKey, stream.id,
          )
        }
      } else {
        // Last resort: mid absent (very old browser without transceiver) or the
        // track was never mapped — keep the historical stream.id behavior.
        sessionKey = stream.id
      }
    }

    // S2 subscriber side: bind end/change-of-track handlers that tear down the
    // local media path when the publisher stops the share.  A real end is:
    // track ended, stream.onremovetrack, or a SCREEN track going mute (screen
    // shares have no mute button — mute on the screen track means the publisher
    // stopped or the SFU dropped it).  Camera/mic mute stays reversible
    // (onmute/onunmute no-op, no cleanup).
    const _txMid = event.transceiver?.mid ?? null
    const _infoAtReceive = _txMid ? _remoteMidToTrackName.get(_txMid) : undefined
    const _trackNameAtReceive = _infoAtReceive?.trackName ?? null
    const _displayAtReceive = _infoAtReceive
      ? _remoteTrackTypes.get(_infoAtReceive.sessionId)?.get(_infoAtReceive.trackName)
      : undefined
    const _bindTrackEndHandlers = (trk: MediaStreamTrack) => {
      trk.onended = () => {
        _cleanupEndedRemoteTrack(sessionKey, _txMid, _trackNameAtReceive)
      }
      trk.onmute = () => {
        if (_displayAtReceive === 'screen') {
          _cleanupEndedRemoteTrack(sessionKey, _txMid, _trackNameAtReceive)
        }
      }
      trk.onunmute = () => { /* camera/mic mute stays reversible — no cleanup */ }
    }
    for (const trk of stream.getTracks()) _bindTrackEndHandlers(trk)
    stream.onremovetrack = () => {
      _cleanupEndedRemoteTrack(sessionKey, _txMid, _trackNameAtReceive)
    }

    const next = new Map(remoteStreams.value)
    const existing = next.get(sessionKey)
    if (existing && existing !== stream) {
      // Merge additional tracks (e.g. audio + video) into one per participant
      for (const track of stream.getTracks()) {
        if (!existing.getTracks().includes(track)) {
          existing.addTrack(track)
        }
      }
      next.set(sessionKey, existing)
    } else {
      next.set(sessionKey, stream)
    }
    remoteStreams.value = next
    log.debug('[PC] remote track received, key=%s', sessionKey)
  }

  /** Request mic/camera permission and return the local stream. */
  async function _requestUserMedia(): Promise<MediaStream> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: true,
      })
      log.debug('_requestUserMedia success tracks=%d', stream.getTracks().length)
      return stream
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      log.error('_requestUserMedia blocked error="%s"', msg)
      throw err
    }
  }

  /**
   * Attach local tracks to the peer connection so they are sent to the SFU.
   *
   * Must run BEFORE createOffer() — createOffer() only emits m= sections for
   * existing transceivers, so tracks added after would be missing from the SDP
   * (Cloudflare rejects media-less offers with 400 → backend 502).  Non-throwing.
   */
  function _attachLocalTracks(pc: RTCPeerConnection, stream: MediaStream): void {
    try {
      for (const track of stream.getTracks()) {
        pc.addTrack(track, stream)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      log.warn('[startCall] _attachLocalTracks failed — continuing without media: %s', msg)
    }
  }

  /** Stop all tracks in a stream and clean up. */
  function _stopStream(stream: MediaStream | null): void {
    if (!stream) return
    for (const track of stream.getTracks()) {
      track.stop()
    }
  }

  /** Build the SDP offer and set it as the local description. */
  async function _createAndSetOffer(pc: RTCPeerConnection): Promise<RTCSessionDescriptionInit> {
    const offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    return offer
  }

  // ── Public actions ───────────────────────────────────────────────────────

  /**
   * Create or join a room call.
   *
   * 0. Provisions the Cloudflare Calls App (POST /api/calls/provision, async)
   * 1. Requests mic/camera permission
   * 2. Creates the RTCPeerConnection and attaches local tracks (addTrack
   *    BEFORE createOffer so the offer carries m= audio/video sections)
   * 3. Creates an SDP offer
   * 4. Sends it to the signaling proxy (POST /api/calls/session)
   * 5. Applies the Cloudflare SDP answer
   * 6. Registers the session in the room + discovers & subscribes to others
   * 7. Broadcasts join_room presence via the party-cell backend script
   * 8. Starts the periodic heartbeat + discovery refresh (ghost cleanup)
   */
  async function startCall(roomId: string): Promise<void> {
    connectionError.value = null
    isProvisioning.value = false
    connectionPhase.value = 'provisioning'

    if (_pc) {
      log.warn('[startCall] Already in a call — hanging up first')
      hangUp()
    }

    try {
      // Step 0: Provision Cloudflare Calls App (idempotent, async)
      log.info('[startCall] Provisioning Cloudflare Calls...')
      isProvisioning.value = true
      const provisionResult = await _apiFetchJson('/calls/provision', { method: 'POST' })
      log.info('[startCall] Provision response: status=%s', provisionResult.status)
      if (provisionResult.status === 'provisioning') {
        log.info('[startCall] Provision dispatched as task=%s — polling...', provisionResult.task_id)
        await _pollProvisionTask(provisionResult.task_id, 100, 2000)
        log.info('[startCall] Provision completed via polling')
      } else if (provisionResult.status === 'already_exists') {
        log.info('[startCall] Provision already exists (fast path)')
      }
      isProvisioning.value = false

      // 1. Request local media
      connectionPhase.value = 'requesting-media'
      log.info('[startCall] Requesting mic/camera...')
      const stream = await _requestUserMedia()
      _localStream = stream
      localStream.value = stream
      // S1 (F3): the self-view starts as the local camera — the publisher's own
      // tile shows the camera until a screen share swaps it (shareStream).
      selfViewStream.value = stream
      cameraEnabled.value = stream.getVideoTracks().some((t) => t.enabled)
      log.warn(
        '[DIAG][usePartyCalls] STEP1 getUserMedia: streamId=%s tracks=%d (0 = sem mídia)',
        stream.id, stream.getTracks().length,
      )

      // 2. Create pc, then attach local tracks BEFORE building the offer —
      //    createOffer() only emits m= sections for transceivers that already
      //    exist (Cloudflare rejects media-less offers with 400 → backend 502).
      const pc = _createPeerConnection()
      _pc = pc
      _attachLocalTracks(pc, stream)

      // 3. Create SDP offer
      connectionPhase.value = 'signaling'
      const offer = await _createAndSetOffer(pc)

      // DIAG: inspect the offer before it leaves the browser
      const offerSdp = offer.sdp || ''
      const firstM = offerSdp.match(/^m=\w+/gm)
      log.warn(
        '[DIAG][usePartyCalls] STEP3 createOffer: hasAudio=%s hasVideo=%s firstM=%s',
        /^m=audio/m.test(offerSdp), /^m=video/m.test(offerSdp),
        firstM ? firstM[0] : '(sem mídia)',
      )
      log.warn(
        '[DIAG][usePartyCalls] STEP4 POST /calls/session: type=%s hasMedia=%s sdpLen=%d',
        offer.type, /^m=/m.test(offerSdp), offerSdp.length,
      )

      // 4. Send offer to signaling proxy.  Each local track is named by its
      //    NATIVE MediaStreamTrack id (sender.track.id) — the name the Cloudflare
      //    SFU actually records (display labels 'mic'/'camera' resolve to
      //    not_found_track_error — H1 proven in F7 ciclo 2).  NOTE (F3 ciclo 4):
      //    the tracks array sent here in /sessions/new is IGNORED by the SFU
      //    (NewSessionRequest has no tracks field) — the tracks are actually
      //    registered in step 7b via /tracks/new with location:'local' after ICE
      //    connects.  The array is kept for the room registry (trackNames) and
      //    diagnostics; the display-friendly TrackType labels are derived and
      //    kept separately (tracks) for the UI grid.
      const trackPairs = pc.getTransceivers()
        .filter((t) => t.sender && t.sender.track && t.mid)
        .map((t) => ({
          mid: t.mid as string,
          nativeId: t.sender!.track!.id,
          display: (t.sender!.track!.kind === 'audio' ? 'mic' : 'camera') as TrackType,
        }))
      const localTrackObjs = trackPairs.map((p) => ({
        location: 'local' as const,
        mid: p.mid,
        trackName: p.nativeId,
      }))
      const localTracks: TrackType[] = trackPairs.map((p) => p.display)
      const localTrackNames: string[] = trackPairs.map((p) => p.nativeId)
      log.warn(
        '[DIAG][startCall] publishing to Cloudflare native trackNames=%j (display tracks=%j)',
        localTrackNames, localTracks,
      )

      const sessionData = await _apiFetchJson('/calls/session', {
        method: 'POST',
        body: JSON.stringify({
          roomId,
          sessionDescription: { type: offer.type, sdp: offer.sdp },
          tracks: localTrackObjs,
        }),
      })

      // 5. Apply Cloudflare SDP answer.  isConnected stays FALSE here — it only
      //    flips at the very END of startCall (after register + SFU tracks +
      //    presence), so the "live" indicator never lights up before the call is
      //    actually ready (F1 — fixes the screen "blink").
      const answer = new RTCSessionDescription(sessionData.sessionDescription)
      await pc.setRemoteDescription(answer)
      const mySessionId: string = sessionData.sessionId
      _currentSessionId = mySessionId

      // DIAG: local tracks were attached BEFORE the offer was built
      log.warn('[DIAG][usePartyCalls] STEP6 addTrack: transceivers=%d',
        pc.getTransceivers().length)

      // 6. Room presence via computed contextId (auto WS reconnect)
      _currentRoomRef.value = roomId
      store.currentRoom = roomId

      // Track the published local track metadata so shareStream can extend it
      // with the screen track (registry + presence carry the REAL track set).
      _publishedTracks = [...localTracks]
      _publishedTrackNames = [...localTrackNames]

      // Index the NATIVE track names by display type (mic/camera) — the source
      // of truth for _updatePublishedTracks when the camera is toggled (F2).
      _localTrackNamesByDisplay.clear()
      localTracks.forEach((display, i) => {
        const names = _localTrackNamesByDisplay.get(display) ?? []
        if (localTrackNames[i]) names.push(localTrackNames[i])
        _localTrackNamesByDisplay.set(display, names)
      })

      // 7. Register session in the room + discover & subscribe to others
      connectionPhase.value = 'registering'
      await _registerAndDiscoverSessions(roomId, remoteStreams, localTracks, localTrackNames)

      // 7b. ROOT CAUSE FIX (F3 ciclo 4): register the publisher's OWN local
      // tracks on the SFU via /tracks/new with location:'local', AFTER ICE
      // connects.  The SFU IGNORES the tracks array in /sessions/new
      // (NewSessionRequest has no tracks field) and rejects /tracks/new with
      // 425 until the PC is connected — without this step the publisher
      // session has zero tracks on the SFU and every remote subscription fails
      // with not_found_track_error (friendly AND native IDs, F7 ciclo 2/3).
      await _registerLocalTracksOnSfu(pc, mySessionId, localTrackObjs)

      // 8. Broadcast join_room presence (script publishes authoritative snapshot)
      await _executePartyAction({
        action: 'join_room',
        roomId,
        sessionId: mySessionId,
        tracks: localTracks,
        trackNames: localTrackNames,
      })

      // 9. Force a presence snapshot so all clients converge immediately
      await _executePartyAction({ action: 'snapshot_request', roomId })

      // 10. Periodic heartbeat + discovery refresh (ghost cleanup)
      _startHeartbeat(roomId, mySessionId, remoteStreams)

      // Only NOW is the call fully established (registry + SFU tracks +
      // presence + heartbeat all in place) — flip the "live" indicator and the
      // connecting phase (F1 — no more premature isConnected → no screen blink).
      isConnected.value = true
      connectionPhase.value = 'connected'
      log.info('[startCall] Call established for room:', roomId)
    } catch (err: unknown) {
      isProvisioning.value = false
      connectionPhase.value = 'error'
      const msg = err instanceof Error ? err.message : 'Failed to start call'
      connectionError.value = msg
      log.error('[startCall] Error:', msg)
      log.warn(
        '[DIAG][usePartyCalls] catch: pc=%s transceivers=%d room=%s',
        _pc ? 'created' : 'null',
        _pc ? _pc.getTransceivers().length : -1,
        _currentRoomRef.value,
      )
      hangUp()
    }
  }

  /**
   * Share an additional media stream (screen/3D canvas) with the room.
   *
   * A screen track is added MID-CALL, so unlike startCall the flow must
   * explicitly register the track on the SFU via tracks/new location:'local'
   * sending the publisher's renegotiation offer ALONG with the registration
   * (GAP 1 — the Cloudflare tracks/new lifecycle accepts ``{tracks,
   * sessionDescription}`` and returns the SFU's answer/offer to close the
   * renegotiation; without it the SFU never learns the track and no subscriber
   * resolves it), apply the SFU's answer/offer (direct answer, or answer a
   * fresh SFU offer via PUT /renegotiate), extend the room registry trackNames
   * so discovery returns it (GAP 2), and publish presence with the REAL
   * tracks/trackNames so subscribers can re-subscribe (GAP 3) and render a
   * dedicated screen tile (GAP 4).
   */
  async function shareStream(stream: MediaStream): Promise<void> {
    if (!_pc) {
      connectionError.value = 'Not connected — start a call first'
      log.warn('[shareStream] No peer connection')
      return
    }

    try {
      // Share only the VIDEO track of the screen.  getDisplayMedia({audio:true})
      // may also carry an audio track that, delivered without registration,
      // becomes a black tile (audio in <video> = black) and double-audio with
      // the mic already active since startCall.
      const videoTrack = stream.getVideoTracks()[0]
      if (!videoTrack) {
        log.warn('[shareStream] No video track in display stream — nothing to share')
        return
      }
      _screenStream = stream
      // S1 (F3): expose the shared screen as the self-view source so the
      // publisher's own grid tile shows what is being shared (local preview).
      selfViewStream.value = stream
      // CICLO 3: use a DEDICATED sendonly transceiver for the screen track.
      // addTrack would REUSE an existing recvonly video transceiver (e.g. the one
      // subscribed to B's camera) making it sendrecv on the same m-section — the
      // SFU accepts that offer but never resolves the track for subscribers
      // (not_found_track_error). A fresh transceiver gets its own mid (no
      // collision with receive mids).
      //
      // A1 (F8): reuse the screen transceiver from the previous stop instead of
      // stacking a new one per share/stop cycle (avoids m-section growth and the
      // SFU's 413 accumulation error).  Two candidates in order:
      //   1. _orphanScreenTx — explicitly captured by stopSharing (sender.track
      //      nulled by removeTrack but the transceiver kept).
      //   2. any sendonly transceiver with sender.track === null (pre-issue
      //      fallback for peers that stopped sharing before this fix).
      // Force direction back to 'sendonly' before replaceTrack — the direction
      // was re-negotiated away from 'sendonly' by the previous offer, so the old
      // direction-only search silently missed and stacked a new transceiver
      // (transceivers 5→6 in F7 → 413 risk).
      log.warn(
        '[DIAG][shareStream] addTransceiver sendonly session=%s track=%s transceivers_before=%d',
        _currentSessionId, videoTrack.id, _pc.getTransceivers().length,
      )
      let screenTx: RTCRtpTransceiver | null = null
      if (_orphanScreenTx?.sender) {
        screenTx = _orphanScreenTx
        _orphanScreenTx = null
      } else {
        screenTx = _pc.getTransceivers().find(
          (t) => t.direction === 'sendonly' && t.sender && t.sender.track === null,
        ) ?? null
      }
      if (screenTx?.sender) {
        try {
          screenTx.direction = 'sendonly'
        } catch { /* ignore — non-mutating on some browsers */ }
        await screenTx.sender.replaceTrack(videoTrack)
      } else {
        _pc.addTransceiver(videoTrack, { direction: 'sendonly' })
      }

      if (!_currentSessionId) {
        log.warn('[shareStream] No current session — cannot negotiate')
        return
      }

      // Build the offer so the new transceiver gets its mid and the renegotiation
      // SDP carries the new m= video section.
      const offer = await _pc.createOffer()
      await _pc.setLocalDescription(offer)

      // GAP 1: register the screen track on the SFU via tracks/new with
      // location:'local' + mid + NATIVE track id, after ICE (already connected
      // from startCall — _waitForIceConnected resolves immediately).  The
      // publisher's offer (with the new m= video for the screen) is sent ALONG
      // with the registration: the Cloudflare tracks/new lifecycle accepts
      // ``{tracks, sessionDescription}`` — the offering side sends its offer
      // here and receives the SFU's answer/offer back to close the
      // renegotiation.  (CICLO 2: the previous PUT /tracks/update only
      // reconfigures EXISTING simulcast tracks — the SFU rejected the new
      // track with update_track_error, leaving subscribers stuck on
      // not_found_track_error.)
      const screenTrackObjs = _pc.getTransceivers()
        .filter((t) => t.sender && t.sender.track === videoTrack && t.mid)
        .map((t) => ({
          location: 'local' as const,
          mid: t.mid as string,
          trackName: t.sender!.track!.id,
        }))
      let regResult: any = null
      if (screenTrackObjs.length) {
        // DIAG (CICLO 2 L3): tracks/new now carries the publisher's offer.
        log.warn(
          '[DIAG][shareStream] tracks/new with offer session=%s track_objs=%d sdp_type=%s sdp_len=%d',
          _currentSessionId, screenTrackObjs.length, offer.type, (offer.sdp || '').length,
        )
        regResult = await _registerLocalTracksOnSfu(
          _pc,
          _currentSessionId,
          screenTrackObjs,
          { type: offer.type, sdp: offer.sdp || '' },
        )
        // DIAG (CICLO 2 L4): what the SFU answered to tracks/new+offer — a
        // direct answer SDP, a renegotiation offer (requiresImmediateRenegotiation),
        // or nothing (per-track errorCode).
        log.warn(
          '[DIAG][shareStream] tracks/new response session=%s answer_type=%s answer_sdp_len=%d requires_renog=%s answer_tracks=%s',
          _currentSessionId,
          regResult?.sessionDescription?.type,
          String(regResult?.sessionDescription?.sdp || '').length,
          String(regResult?.requiresImmediateRenegotiation),
          Array.isArray(regResult?.tracks) ? `present(${regResult.tracks.length})` : 'absent',
        )
      }

      // Close the publisher renegotiation with the SFU's response (CICLO 2).
      // tracks/new+offer returns either a DIRECT answer (apply as-is) or, when
      // requiresImmediateRenegotiation, a fresh SFU offer that we answer and
      // send back via PUT /renegotiate (mirroring the subscriber flow in
      // _subscribeToRemoteTracks).  Never apply an empty/absent SDP — it
      // crashes setRemoteDescription with "Expect line: v=".
      const respSd = regResult?.sessionDescription
      const respSdp = respSd?.sdp ? String(respSd.sdp) : ''
      if (regResult?.requiresImmediateRenegotiation && respSd?.type === 'offer' && respSdp.length > 0) {
        // SFU generated a fresh offer for the new track — answer it and send
        // the answer back so the SFU completes the m-line setup.
        await _pc.setRemoteDescription(new RTCSessionDescription(respSd))
        const localAnswer = await _pc.createAnswer()
        await _pc.setLocalDescription(localAnswer)
        await _apiFetchJson(
          `/calls/sessions/${_currentSessionId}/renegotiate`,
          {
            method: 'PUT',
            body: JSON.stringify({
              sessionDescription: { type: localAnswer.type, sdp: localAnswer.sdp },
            }),
          },
        )
      } else if (respSd?.type === 'answer' && respSdp.length > 0) {
        // Direct answer — apply as-is.
        await _pc.setRemoteDescription(new RTCSessionDescription(respSd))
      } else if (regResult) {
        // The SFU answered without an offer/answer SDP (e.g. a per-track
        // errorCode on the new track).  Surface it for the F7 to observe —
        // do NOT apply an empty SDP.
        const trackErrors = (Array.isArray(regResult?.tracks) ? regResult.tracks : [])
          .filter((t: SfuTrackResult) => t && typeof t === 'object' && (t.errorCode || t.errorDescription))
        log.warn(
          '[DIAG][shareStream] tracks/new no offer/answer from SFU session=%s track_errors=%j',
          _currentSessionId, trackErrors,
        )
      }

      // GAP 2: extend the room registry (upsert) so discovery returns the
      // screen in trackNames and subscribers learn about the new track.
      const roomId = _currentRoomRef.value
      const tracksDisplay: TrackType[] = [..._publishedTracks, 'screen']
      const trackNames: string[] = [..._publishedTrackNames, videoTrack.id]

      // Index the screen's native track so _updatePublishedTracks keeps it in
      // the published set while sharing (F2).
      const screenNames = _localTrackNamesByDisplay.get('screen') ?? []
      if (!screenNames.includes(videoTrack.id)) screenNames.push(videoTrack.id)
      _localTrackNamesByDisplay.set('screen', screenNames)

      if (roomId) {
        await _updateRegistryTracks(roomId, tracksDisplay, trackNames, remoteStreams)
      }

      // Notify room presence with the REAL tracks/trackNames (not hardcoded) so
      // the snapshot reflects the shared screen.
      if (roomId) {
        await _executePartyAction({
          action: 'tracks_update',
          roomId,
          tracks: tracksDisplay,
          trackNames,
        })
      }

      // Persist the extended publish set for any future share/update.
      _publishedTracks = tracksDisplay
      _publishedTrackNames = trackNames

      log.info('[shareStream] Stream shared successfully tracks=%j trackNames=%j',
        tracksDisplay, trackNames)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to share stream'
      connectionError.value = msg
      log.error('[shareStream] Error:', msg)
    }
  }

  /** Mute or unmute the local microphone and reflect the state to the room. */
  function muteAudio(): void {
    if (!_localStream) return
    const audioTracks = _localStream.getAudioTracks()
    for (const track of audioTracks) {
      track.enabled = !track.enabled
    }
    const muted = !audioTracks.some((t) => t.enabled)

    const roomId = _currentRoomRef.value
    if (roomId) {
      void _executePartyAction({ action: 'mute_toggle', roomId, isMuted: muted })
    }
  }

  /**
   * Recompute the caller's REAL published track set from the current local
   * media state and publish it to the room registry + presence (tracks_update).
   *
   * Toggles are INDEPENDENT decisions (F2): the camera is dropped from the
   * published set when disabled, re-added when enabled; the screen is dropped
   * when sharing stops.  The mic always stays (muting is a separate presence
   * signal).  This keeps the registry/presence honest so subscribers only see
   * the tracks that are actually active.
   *
   * Failures here are non-fatal: the registry upsert / presence publish are
   * best-effort (a network blip would otherwise surface as an UNHANDLED promise
   * rejection from ``void _updatePublishedTracks`` in toggleCamera/stopSharing).
   * The 20s heartbeat re-reconciles registry + presence within a TTL.
   */
  async function _updatePublishedTracks(roomId: string): Promise<void> {
    const tracks: TrackType[] = []
    const trackNames: string[] = []
    for (const [display, names] of _localTrackNamesByDisplay) {
      if (!names.length) continue
      if (display === 'camera' && !cameraEnabled.value) continue
      if (display === 'screen' && !isSharingScreen.value) continue
      tracks.push(display)
      trackNames.push(...names)
    }
    _publishedTracks = [...tracks]
    _publishedTrackNames = [...trackNames]
    // PERMANENTE: the real published track set — the registry source state subscribers
    // reconcile against. Confirms B2's origin: after stopSharing, `tracks` is ['mic'] and
    // the screen nativeId is gone from trackNames BEFORE _refreshDiscovery runs on peers.
    log.info(
      '[party-cell][tracks] room=%s published tracks=%j trackNames=%j',
      roomId, _publishedTracks, _publishedTrackNames,
    )
    try {
      await _updateRegistryTracks(roomId, tracks, trackNames, remoteStreams)
      await _executePartyAction({ action: 'tracks_update', roomId, tracks, trackNames })
    } catch (err) {
      log.warn(
        '[updatePublishedTracks] republish failed room=%s tracks=%j — heartbeat will reconcile: %s',
        roomId, tracks,
        err instanceof Error ? err.message : String(err),
      )
    }
  }

  /** Toggle the local camera on/off independently of mic/screen (F2). */
  function toggleCamera(): void {
    if (!_localStream) return
    const videoTracks = _localStream.getVideoTracks()
    const nowEnabled = !videoTracks.some((t) => t.enabled)
    for (const track of videoTracks) track.enabled = nowEnabled
    cameraEnabled.value = nowEnabled
    const roomId = _currentRoomRef.value
    if (roomId) void _updatePublishedTracks(roomId)
  }

  /** Start screen sharing, or stop it when already sharing (F2). */
  async function toggleScreenShare(): Promise<void> {
    if (isSharingScreen.value) {
      await stopSharing()
      return
    }
    if (!_pc) {
      connectionError.value = 'Not connected — start a call first'
      log.warn('[toggleScreenShare] No peer connection')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: false,
      })
      await shareStream(stream)
      // Only reflect the "sharing" state if the share actually started
      // (shareStream bails on a stream without a video track).  A cancelled
      // getDisplayMedia throws before this point → state unchanged.
      if (_screenStream) {
        _screenTrackId = stream.getVideoTracks()[0]?.id ?? null
        isSharingScreen.value = true
      }
    } catch (err) {
      log.warn(
        '[toggleScreenShare] cancelled or failed: %s',
        err instanceof Error ? err.message : String(err),
      )
    }
  }

  /** Stop an active screen share: detach the sender, remove the track from the
   *  SFU session (tracks/close), republish the published set, and keep the
   *  sendonly transceiver orphaned for reuse on the next share (A1 — no
   *  transceiver accumulation). */
  async function stopSharing(): Promise<void> {
    if (!_screenStream) return
    _stopStream(_screenStream)
    _screenStream = null
    if (_pc) {
      let removedSender = false
      for (const sender of _pc.getSenders()) {
        if (sender.track?.id === _screenTrackId) {
          // Keep the sendonly transceiver for the next shareStream — removeTrack
          // only nulls sender.track; the transceiver/m-section survives.  A1:
          // reuse it via replaceTrack instead of stacking a new transceiver per
          // share/stop cycle (avoids the SFU's 413 accumulation error).
          const orphanTx = _pc.getTransceivers().find((t) => t.sender === sender)
          if (orphanTx) _orphanScreenTx = orphanTx
          // DIAG (F2): the screen transceiver's mid survives removeTrack — this
          // is the value the tracks/close contract needs (CloseTrackObject.mid).
          // F7 compares it to the target sent by _removeTrackFromSfu (both should
          // equal the same mid after the F3 fix).
          log.warn(
            '[stopSharing] DIAG detached sender screen_track=%s orphan_mid=%s orphan_direction=%s',
            sender.track?.id, orphanTx?.mid ?? 'none', orphanTx?.direction ?? 'n/a',
          )
          _pc.removeTrack(sender)
          removedSender = true
        }
      }
      // Tell the SFU the track is gone — replaces the renegotiate-with-offer
      // path, which the Cloudflare contract rejects (406 "answer is expected" →
      // 502 on every stop).  Non-fatal: on failure the SFU reaper still signals
      // event=ended to already-subscribed peers.  The tracks/close contract
      // identifies the track by the transceiver mid (which survives removeTrack)
      // — NOT the native _screenTrackId (which only locates the local sender
      // above; the mid is the value the Cloudflare CloseTrackObject requires).
      if (removedSender && _orphanScreenTx?.mid) {
        await _removeTrackFromSfu(_orphanScreenTx.mid)
      } else if (removedSender) {
        log.warn(
          '[stopSharing] cannot remove screen track from SFU — no orphan transceiver mid available',
        )
      }
    }
    _screenTrackId = null
    isSharingScreen.value = false
    // S1 (F3): swap the self-view back to the camera when sharing stops.
    selfViewStream.value = localStream.value
    _localTrackNamesByDisplay.delete('screen')
    const roomId = _currentRoomRef.value
    if (roomId) void _updatePublishedTracks(roomId)
    log.info('[stopSharing] Screen share stopped')
  }

  /** Force-refresh presence + remote discovery on demand (F5). */
  async function refreshRoom(): Promise<void> {
    await requestSnapshot()
    const roomId = _currentRoomRef.value
    if (roomId) await _refreshDiscovery(roomId, remoteStreams)
  }

  /** List rooms that currently have ≥1 active session (F4). */
  async function listAvailableRooms(): Promise<AvailableRoom[]> {
    const data = await _apiFetchJson('/calls/rooms')
    return (data.rooms || []) as AvailableRoom[]
  }

  /** Join an existing room by id (F4) — reuses the full startCall flow. */
  async function joinRoom(roomId: string): Promise<void> {
    await startCall(roomId)
  }

  /**
   * Leave the call — broadcast leave_room, stop the heartbeat, close the peer
   * connection, stop local tracks, disconnect room presence, and reset state.
   */
  function hangUp(): void {
    const roomId = _currentRoomRef.value
    const sessionId = _currentSessionId

    _stopHeartbeat()

    // Broadcast leave so other clients drop us from presence (best-effort)
    if (roomId) {
      void _executePartyAction({ action: 'leave_room', roomId })
    }

    // Remove the room registry entry (best-effort — TTL is the safety net)
    if (roomId && sessionId) {
      void apiFetch(`/calls/rooms/${roomId}/sessions/${sessionId}`, { method: 'DELETE' })
        .catch(() => {})
    }

    _subscribedSessions.clear()
    _subscribedTrackNames.clear()
    _remoteTrackTypes.clear()
    _remoteMidToTrackName.clear()
    _localTrackNamesByDisplay.clear()
    _screenTrackId = null
    _orphanScreenTx = null

    // Close peer connection
    if (_pc) {
      _pc.close()
      _pc = null
    }
    _currentSessionId = null

    // Stop local media (mic/camera + shared screen — leak fix: the screen
    // stream was never stopped before, so the tab kept capturing after hangUp)
    _stopStream(_localStream)
    _localStream = null
    _stopStream(_screenStream)
    _screenStream = null
    _publishedTracks = []
    _publishedTrackNames = []

    // Disconnect room presence: nulling _currentRoomRef makes the computed
    // resolve to '' (idle channel), closing the WebSocket via the watcher.
    _currentRoomRef.value = null
    store.currentRoom = null

    // Reset state
    isConnected.value = false
    connectionPhase.value = 'idle'
    cameraEnabled.value = false
    isSharingScreen.value = false
    localStream.value = null
    selfViewStream.value = null
    remoteStreams.value = new Map()
    store.reset()

    log.info('[hangUp] Call ended')
  }

  /** Request a snapshot of the current room participants. */
  async function requestSnapshot(): Promise<void> {
    const roomId = _currentRoomRef.value
    if (!roomId) return
    await _executePartyAction({ action: 'snapshot_request', roomId })
  }

  // ── Cleanup on component unmount ─────────────────────────────────────────

  onUnmounted(() => {
    if (_pc || _localStream) {
      log.info('[cleanup] Component unmounted — hanging up')
      hangUp()
    }
  })

  return {
    isConnected,
    isProvisioning,
    connectionPhase,
    isConnecting,
    cameraEnabled,
    isSharingScreen,
    localStream,
    selfViewStream,
    remoteStreams,
    participants,
    connectionError,
    startCall,
    shareStream,
    muteAudio,
    toggleCamera,
    toggleScreenShare,
    stopSharing,
    refreshRoom,
    listAvailableRooms,
    joinRoom,
    hangUp,
    requestSnapshot,
  }
}
