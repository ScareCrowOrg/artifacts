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

export interface UsePartyCallsReturn {
  isConnected: Ref<boolean>
  isProvisioning: Ref<boolean>
  localStream: Ref<MediaStream | null>
  /** Remote streams keyed by remote sessionId */
  remoteStreams: Ref<Map<string, MediaStream>>
  participants: Ref<Participant[]>
  connectionError: Ref<string | null>
  startCall: (roomId: string) => Promise<void>
  shareStream: (stream: MediaStream) => Promise<void>
  muteAudio: () => void
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

    // Prune streams whose session is no longer active (ghost participants).
    // Screen tiles are keyed ``{sessionId}/screen`` — map them back to the
    // owning session so they are pruned with it.
    const next = new Map(remoteStreams.value)
    let changed = false
    for (const key of next.keys()) {
      const ownerId = key.endsWith('/screen') ? key.slice(0, -'/screen'.length) : key
      if (!activeIds.has(ownerId) && _subscribedSessions.has(ownerId)) {
        next.delete(key)
        _subscribedSessions.delete(ownerId)
        _subscribedTrackNames.delete(ownerId)
        _remoteTrackTypes.delete(ownerId)
        changed = true
      }
    }
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
): Promise<void> {
  if (!_currentSessionId || !trackObjs.length) return

  const connected = await _waitForIceConnected(pc, 10_000)
  if (!connected) {
    log.warn(
      '[DIAG][publish] ICE not connected within timeout — local tracks NOT registered on SFU',
    )
    return
  }

  try {
    const result = await _apiFetchJson(
      `/calls/sessions/${sessionId}/tracks/new`,
      { method: 'POST', body: JSON.stringify({ tracks: trackObjs }) },
    )
    const perTrack = (Array.isArray(result?.tracks) ? result.tracks : [])
      .map((t: SfuTrackResult) => (t && typeof t === 'object'
        ? { trackName: t.trackName, mid: t.mid, errorCode: t.errorCode, errorDescription: t.errorDescription }
        : t))
    log.warn(
      '[DIAG][publish] local tracks registered on SFU session=%s per_track=%j',
      sessionId, perTrack,
    )
  } catch (err) {
    log.warn(
      '[DIAG][publish] local track registration failed session=%s: %s',
      sessionId, err instanceof Error ? err.message : String(err),
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
  const localStream = ref<MediaStream | null>(null)
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
        connectionError.value = `Connection lost: ${pc.iceConnectionState}`
      }
    }

    pc.ontrack = _handleRemoteTrack

    return pc
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

    const trackIdMatch = /^([^/]+)\/(.+)$/.exec(event.track.id || '')
    let sessionKey: string
    if (trackIdMatch) {
      const ownerId = trackIdMatch[1]
      const trackName = trackIdMatch[2]
      const display = _remoteTrackTypes.get(ownerId)?.get(trackName)
      sessionKey = display === 'screen' ? `${ownerId}/screen` : ownerId
    } else {
      sessionKey = stream.id
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
      log.info('[startCall] Requesting mic/camera...')
      const stream = await _requestUserMedia()
      _localStream = stream
      localStream.value = stream
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

      // 5. Apply Cloudflare SDP answer
      const answer = new RTCSessionDescription(sessionData.sessionDescription)
      await pc.setRemoteDescription(answer)
      isConnected.value = true
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

      // 7. Register session in the room + discover & subscribe to others
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

      log.info('[startCall] Call established for room:', roomId)
    } catch (err: unknown) {
      isProvisioning.value = false
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
   * (GAP 1 — without it the SFU never learns the track and no subscriber
   * resolves it), extend the room registry trackNames so discovery returns it
   * (GAP 2), renegotiate via tracks/update, and publish presence with the REAL
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
      _pc.addTrack(videoTrack, stream)

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
      // from startCall — _waitForIceConnected resolves immediately).
      const screenTrackObjs = _pc.getTransceivers()
        .filter((t) => t.sender && t.sender.track === videoTrack && t.mid)
        .map((t) => ({
          location: 'local' as const,
          mid: t.mid as string,
          trackName: t.sender!.track!.id,
        }))
      if (screenTrackObjs.length) {
        await _registerLocalTracksOnSfu(_pc, _currentSessionId, screenTrackObjs)
      }

      // GAP 2: extend the room registry (upsert) so discovery returns the
      // screen in trackNames and subscribers learn about the new track.
      const roomId = _currentRoomRef.value
      const tracksDisplay: TrackType[] = [..._publishedTracks, 'screen']
      const trackNames: string[] = [..._publishedTrackNames, videoTrack.id]
      if (roomId) {
        await _updateRegistryTracks(roomId, tracksDisplay, trackNames, remoteStreams)
      }

      // Renegotiate so the SFU learns about the new track
      const answer = await _apiFetchJson(
        `/calls/sessions/${_currentSessionId}/tracks/update`,
        {
          method: 'PUT',
          body: JSON.stringify({
            sessionDescription: { type: offer.type, sdp: offer.sdp },
          }),
        },
      )
      // Apply the returned SDP only when usable — the backend now omits
      // sessionDescription when the SFU returns none (never apply empty SDP).
      if (answer?.sessionDescription?.sdp) {
        await _pc.setRemoteDescription(new RTCSessionDescription(answer.sessionDescription))
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
    localStream.value = null
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
    localStream,
    remoteStreams,
    participants,
    connectionError,
    startCall,
    shareStream,
    muteAudio,
    hangUp,
    requestSnapshot,
  }
}
