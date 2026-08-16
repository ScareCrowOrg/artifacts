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

import { ref, computed, onUnmounted, watch, type Ref } from 'vue'
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
  /** Whether the local mic is published (Caso B — opt-in; muted ≠ absent). */
  micEnabled: Ref<boolean>
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
  /** Mute/unmute the mic, or ENABLE it on the first click when no track is
   *  captured yet (Caso B — media opt-in). */
  muteAudio: () => Promise<void>
  /** Toggle the local camera on/off, or ENABLE it on the first click when no
   *  track is captured yet (Caso B — media opt-in).  Independent of mic/screen (F2). */
  toggleCamera: () => Promise<void>
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
/** F3 FIX (ITER_1 H3): transceiver-scoped copy of the same classification —
 *  ``RTCRtpTransceiver`` → {sessionId, trackName}.  The ontrack fires from a
 *  STABLE RTCRtpTransceiver, but ``_remoteMidToTrackName`` is a mid-keyed GLOBAL
 *  Map that concurrent operations (prune removeOwnerMappings /
 *  removeScreenMapping, _teardownRemoteMedia, interleaved _refreshDiscovery
 *  across heartbeats) mutate BETWEEN the population and the ontrack firing.  In
 *  F7 ciclo 2 the video ontrack read the global Map with mid "1" already gone
 *  (despite a 2-entry mid_map populated) and fell back to the opaque stream.id —
 *  a separate generic tile instead of the publisher's tile.  Storing the
 *  classification ON the transceiver (WeakMap — no strong refs, GC-safe) makes
 *  the ontrack read the mapping that belongs to ITS transceiver, immune to the
 *  race. */
const _transceiverMeta = new WeakMap<RTCRtpTransceiver, { sessionId: string; trackName: string }>()
/**
 * F3 FIX (ITER_1 guest-screenshare CICLO 2): mids whose remote subscription is
 * IN FLIGHT — the SFU tracks/new resolved the mid and ``_subscribeToRemoteTracks``
 * populated ``_remoteMidToTrackName`` / ``_transceiverMeta``, but the ontrack has
 * NOT fired yet.  Concurrent ``_refreshDiscovery`` prunes (removeOwnerMappings /
 * removeScreenMapping) must NOT drop those mids between the population and the
 * ontrack.  F7 ciclo 1 proved exactly this drop (race H3): the screen arrived on
 * the EXISTING video transceiver (mid 1), the first pass anchored its WeakMap
 * (transceiver_meta_sets=1), yet a concurrent prune dropped BOTH the WeakMap and
 * the global map before the ontrack, so the screen fell back to the opaque
 * stream.id and was pruned.  A mid leaves the set when its ontrack classifies,
 * or after ``_PENDING_SUBSCRIBE_TIMEOUT_MS`` (guard for a subscription whose
 * ontrack never fires — the timeout must never leak protected mids). */
const _pendingSubscribeMids = new Set<string>()
const _PENDING_SUBSCRIBE_TIMEOUT_MS = 5000

/**
 * F3 FIX (ITER_1 guest-screenshare CICLO 3): wall-clock time each remote-stream
 * tile key was last ADDED to `remoteStreams`.  Used as a GRACE-PERIOD guard in
 * `_cleanupEndedRemoteTrack`: a SPURIOUS end-of-track event (mute/ended fired by
 * Chrome on a STALE track riding a REUSED transceiver mid — confirmed in F7: the
 * screen tile entered _handleRemoteTrack and was removed in the SAME dispatch)
 * arrives within milliseconds of the ontrack.  A REAL end (publisher stops → SFU
 * reaper signals event=ended) arrives much later, so a ~400ms grace only blocks
 * the spurious same-dispatch removal and never defers a genuine teardown
 * meaningfully.  Entries are deleted when the tile is legitimately removed and
 * cleared on hangUp.
 */
const _remoteStreamAddedAt = new Map<string, number>()
const _REMOTE_STREAM_GRACE_MS = 400

/** Drop the transceiver-scoped meta for a mid, keeping the WeakMap in lockstep
 *  with ``_remoteMidToTrackName`` deletions (prune / teardown).  Safe to call
 *  for a mid whose transceiver is gone or whose meta was never set.  F3 FIX
 *  (CICLO 2): never drops a mid whose subscription is still in flight (pending)
 *  — the prune is a transient signal that can race the incoming screen. */
function _dropTransceiverMeta(mid: string | null | undefined): void {
  if (!mid || !_pc) return
  if (_pendingSubscribeMids.has(mid)) return
  const tx = _pc.getTransceivers().find((t) => t.mid === mid)
  if (tx) _transceiverMeta.delete(tx)
}

/** F3 FIX (CICLO 2): protect the given mids (populated by a remote subscription)
 *  from concurrent prunes until their ontrack classifies or the timeout fires.
 *  One bounded 5s timer per mid, cleared by the ontrack — a timer firing for an
 *  already-cleared mid is a harmless no-op delete. */
function _markMidsPending(mids: string[], sessionId: string): void {
  const added: string[] = []
  for (const mid of mids) {
    if (!mid || _pendingSubscribeMids.has(mid)) continue
    _pendingSubscribeMids.add(mid)
    added.push(mid)
    window.setTimeout(() => {
      _pendingSubscribeMids.delete(mid)
    }, _PENDING_SUBSCRIBE_TIMEOUT_MS)
  }
  if (added.length > 0) {
    log.warn('[DIAG][pending] marked mids=%j session=%s', added, sessionId)
  }
}

/** F3 FIX (CICLO 2): the ontrack for a pending mid fired and classified — the
 *  subscription has landed on a tile, so the pending protection is released. */
function _unmarkMidPending(mid: string | null | undefined, sessionKey: string): void {
  if (mid && _pendingSubscribeMids.delete(mid)) {
    log.warn('[DIAG][pending] cleared on ontrack mid=%s sessionKey=%s', mid, sessionKey)
  }
}

/** F3 FIX (CICLO 2): does the owner have any subscription still in flight?  A
 *  ``removeOwnerMappings`` for such an owner is a stale concurrent snapshot (the
 *  tracks/new resolved, so the session IS active) — pruning would drop the
 *  just-populated map/WeakMap/_remoteTrackTypes of the incoming track. */
function _ownerHasPendingMids(ownerId: string): boolean {
  for (const mid of _pendingSubscribeMids) {
    const info = _remoteMidToTrackName.get(mid)
    if (info?.sessionId === ownerId) return true
  }
  return false
}
/**
 * F3 FIX (ITER_1 guest-screenshare): re-anchor ``_transceiverMeta`` for a remote
 * session's mids AFTER the SFU offer has been applied at setRemoteDescription.
 *
 * The FIRST population pass (in _subscribeToRemoteTracks, before
 * setRemoteDescription) anchors only transceivers that already exist at that
 * instant — the recvonly audio/video transceivers created at join.  A track
 * added mid-call (the shared screen) gets its transceiver created ONLY when the
 * SFU's offer is applied at setRemoteDescription, so the first pass found
 * nothing and the WeakMap stayed EMPTY for the screen.  The screen's ontrack
 * then depends 100% on the global ``_remoteMidToTrackName`` — if a concurrent
 * discovery/prune drops that entry between the population and the ontrack
 * (race H3), the ontrack falls back to the opaque stream.id → generic tile →
 * pruned → the screen never renders (the guest→host asymmetry).
 *
 * ontrack handlers are dispatched as tasks AFTER setRemoteDescription resolves,
 * so this second pass (running in the ``await`` continuation) anchors the NEW
 * transceiver before the screen's ontrack fires.  Idempotent and race-safe:
 * skips transceivers already anchored and never overwrites an existing entry.
 * Returns how many anchors it added (DIAG only — no behavior change).
 */
function _anchorTransceiverMetaFromMidMap(sessionId: string): number {
  if (!_pc) return 0
  let anchored = 0
  for (const [mid, meta] of _remoteMidToTrackName) {
    if (meta.sessionId !== sessionId) continue
    const tx = _pc.getTransceivers().find((t) => t.mid === mid)
    if (tx && !_transceiverMeta.has(tx)) {
      _transceiverMeta.set(tx, meta)
      anchored += 1
    }
  }
  return anchored
}
/** One-shot guard for the F2 (ITER_1) stats dump — H2: a video inbound-rtp with
 *  bytesReceived==0 ~5s after subscribe means the SFU resolved the subscription
 *  (mid 1, no errorCode) but is NOT forwarding video RTP to this subscriber
 *  (vs H1: the track is dropped client-side at the ontrack !stream guard). */
let _statsDumpScheduled = false
/** Monotonic seq for _refreshDiscovery entry/exit DIAGs (B4) — lets F3 prove
 *  concurrent interleavings (race H3) by correlating [start] seq=N with
 *  [end] seq=N on the SAME discovery pass. */
let _discoverySeq = 0
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

/** The recvonly transceivers created at join (audio/video) — kept so
 *  _enableLocalTrack can attach a local track and switch the matching one to
 *  'sendrecv' on the first opt-in click (Caso B: media opt-in, no capture on
 *  join).  Reset on hangUp. */
let _localAudioTx: RTCRtpTransceiver | null = null
let _localVideoTx: RTCRtpTransceiver | null = null

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

/** One-shot stats dump (F2 ITER_1 H2): ~5s after the first successful remote
 *  subscribe, read the inbound-rtp stats of the audio and video receivers.  A
 *  VIDEO receiver with bytesReceived==0 means the SFU accepted the subscription
 *  but is NOT delivering video RTP to this subscriber — discriminating H2 from
 *  H1 (the video track dropped client-side at the ontrack !stream guard) and
 *  from H3 (the video merged onto an opaque stream.id tile). */
async function _logSfuStatsDump(): Promise<void> {
  if (!_pc) return
  try {
    const report = await _pc.getStats()
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
    // DIAG (B5/F3-H2): summary line with has_video so a single grep proves
    // whether the HOST receiver got ANY video RTP from the GUEST's shared
    // screen — bytesReceived stays 0 when the SFU resolved the subscribe (mid,
    // no errorCode) but is NOT forwarding the screen's video.
    const hasVideo = Object.prototype.hasOwnProperty.call(inbound, 'video')
    log.warn(
      '[DIAG][stats] inbound_rtp=%j has_video=%s video_bytes=%d audio_bytes=%d',
      inbound, hasVideo, inbound.video?.bytesReceived ?? 0, inbound.audio?.bytesReceived ?? 0,
    )
  } catch (err) {
    log.warn('[DIAG][stats] getStats failed: %s', err instanceof Error ? err.message : String(err))
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
        const tx = _pc.getTransceivers().find((t) => t.mid === entry.mid)
        if (tx) {
          _transceiverMeta.set(tx, { sessionId: remote.sessionId, trackName: entry.trackName })
          transceiverMetaSets += 1
        }
      }
    }
    if (midEntries.length > 0) {
      // DIAG (F2 ITER_1 H3): also log the FULL raw tracks[] response, not just
      // the resolved map entries.  Confirms whether BOTH audio (mid 0) and video
      // (mid 1) entered _remoteMidToTrackName and surfaces any errorCode on
      // tracks that were filtered out — a video track whose trackName is NOT
      // echoed by the SFU never enters the map, so its ontrack falls back to the
      // opaque stream.id (separate generic tile) instead of the owner tile.
      log.warn(
        '[DIAG][subscribe] mid_map populated session=%s entries=%j raw_tracks=%j transceiver_meta_sets=%d',
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
      await _pc.setRemoteDescription(new RTCSessionDescription(respSd))

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
          '[DIAG][subscribe] %s: transceiver_meta anchored post-setRemoteDescription=%d anchored_mids=%j',
          remote.sessionId, _anchoredPostOffer,
          _pc.getTransceivers().filter((t) => t.mid && _transceiverMeta.has(t)).map((t) => t.mid),
        )
      }

      // DIAG (F1 P2): the SFU offer's m-sections / mids — confirms the media
      // lines are bounded (recvonly only; no growth across retries).
      log.warn(
        '[DIAG][subscribe] %s: offer type=%s sdp_len=%d m_sections=%d mids=%j',
        remote.sessionId, respSd.type, respSdp.length,
        (respSdp.match(/^m=\w+/gm) || []).length,
        _pc.getTransceivers().map((t) => t.mid),
      )
      // DIAG (F2 ITER_1 H1/H3): SDP preview + a=msid lines.  A video m-line
      // WITHOUT a=msid (or an msid with no stream label) makes the video ontrack
      // arrive with an EMPTY event.streams → dropped at the !stream guard, which
      // would explain "audio flows, video never reaches the tile".
      log.warn(
        '[DIAG][subscribe] %s: offer sdp_preview="%s" a_msid_lines=%j',
        remote.sessionId, respSdp.slice(0, 200),
        respSdp.match(/^a=msid:[^\r\n]*$/gm) || [],
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
      if (!_statsDumpScheduled) {
        _statsDumpScheduled = true
        window.setTimeout(() => { void _logSfuStatsDump() }, 5000)
      }
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
  knownParticipants?: ReadonlyArray<{ sessionId?: string }>,
  callerLabel = 'unknown',
): Promise<void> {
  if (!_currentSessionId) return
  const _dseq = ++_discoverySeq
  // DIAG (B4): entry marker for EVERY discovery pass — proves the race H3
  // concurrency (R1/R3) by letting F3 correlate interleaved [start]/[end]
  // pairs.  mid_map_size at entry is the state a concurrent prune can drop
  // before the screen ontrack fires.
  log.warn(
    '[DIAG][discovery][start] seq=%d caller=%s room=%s session=%s mid_map_size=%d',
    _dseq, callerLabel, roomId, _currentSessionId, _remoteMidToTrackName.size,
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
    const _currentUserId = sessions.find((x) => x.sessionId === _currentSessionId)?.userId
    for (const s of sessions) {
      const isOwn = s.sessionId === _currentSessionId
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
      _dseq, callerLabel, _currentSessionId, _remoteMidToTrackName.size,
      ownersToPrune.size, _screenRemovedCount, _subscribedSessions.size,
    )
  } catch (err) {
    log.warn('[discovery] refresh failed: %s',
      err instanceof Error ? err.message : String(err))
    // DIAG (B4): error path still emits the end marker so a failing pass can't
    // be mistaken for a pass that never ran.
    log.warn(
      '[DIAG][discovery][end][error] seq=%d caller=%s session=%s mid_map_size=%d',
      _dseq, callerLabel, _currentSessionId, _remoteMidToTrackName.size,
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
async function _registerAndDiscoverSessions(
  roomId: string,
  remoteStreams: Ref<Map<string, MediaStream>>,
  tracks: TrackType[],
  trackNames: string[],
  knownParticipants?: ReadonlyArray<{ sessionId?: string }>,
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
  await _refreshDiscovery(roomId, remoteStreams, knownParticipants, 'register')
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
  knownParticipants?: ReadonlyArray<{ sessionId?: string }>,
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
  await _refreshDiscovery(roomId, remoteStreams, knownParticipants, 'registry')
}

/** Start the periodic heartbeat + discovery refresh. */
function _startHeartbeat(
  roomId: string,
  sessionId: string,
  remoteStreams: Ref<Map<string, MediaStream>>,
  knownParticipants?: ReadonlyArray<{ sessionId?: string }>,
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
      await _refreshDiscovery(roomId, remoteStreams, knownParticipants, 'heartbeat')
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
function _teardownRemoteMedia(mids: string[], callerLabel = 'unknown'): void {
  if (!_pc || !mids.length) return
  // DIAG (F2 CICLO 3, B5): prove WHICH path stopped the receiver transceivers
  // ('cleanup' = _cleanupEndedRemoteTrack / end-of-track handler, 'prune' =
  // discovery B2 removeScreenMapping).  A 'cleanup' teardown of mid=1 logged
  // right after [DIAG][merge] screen added confirms the spurious end-of-track
  // handler is the one stopping the just-received screen — NOT the prune (which
  // would also bump owners_to_prune/screen_removed in [DIAG][discovery][end]).
  log.warn('[DIAG][teardown] caller=%s mids=%s', callerLabel, JSON.stringify(mids))
  for (const mid of mids) {
    // F3 FIX (ITER_1 guest-screenshare CICLO 2): never tear down a subscription
    // still in flight — a concurrent prune can race the incoming screen
    // (tx.stop() would kill the transceiver the ontrack is about to fire on, and
    // the map/WeakMap deletion is the race H3 drop).  The pending protection
    // releases on the ontrack or after the 5s timeout.
    if (_pendingSubscribeMids.has(mid)) {
      log.warn('[DIAG][pending] protect mid=%s prune=teardown', mid)
      continue
    }
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
    // F3 FIX (ITER_1 H3): drop the transceiver-scoped meta for the same mid.
    // Uses the in-scope `tx` because removeTransceiver (above) already removed
    // it from _pc.getTransceivers() — a fresh _dropTransceiverMeta lookup would
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
  /** Whether the local mic is published (Caso B — opt-in).  True once the mic
   *  is acquired via _enableLocalTrack; a muted mic stays published (mute is a
   *  separate presence signal), so this only flips on acquire and hangUp. */
  const micEnabled = ref(false)
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

  // ── Caso D (party-cell-usability-ux): event-driven media convergence ──────
  // Presence is ALREADY broadcast via useDistributedState (WS snapshot →
  // store.participants).  This watcher closes the media-discovery gap: when a
  // participant's track set changes (e.g. A shares a screen or joins), B
  // re-runs _refreshDiscovery immediately instead of waiting for the 20s
  // heartbeat or the manual refresh button.  Debounced (600ms) so a burst of
  // snapshots collapses into ONE discovery; _refreshDiscovery is idempotent
  // (delta via _subscribedTrackNames), so redundant calls are no-ops.
  //
  // REVIEW #3069: the source is a STRING SIGNATURE of (sessionId + display
  // tracks), NOT the whole participants array — the heartbeat PUT renews
  // `lastHeartbeat`/`isMuted` on every participant every 20s, which mutates the
  // array and would reset the debounce perpetually (delaying discovery).  The
  // signature changes only on join/leave or a track add/remove, so the watcher
  // fires only when media discovery is actually needed.
  let _discoveryDebounce: number | null = null
  watch(
    () => participants.value
      .map((p) => `${p.sessionId ?? ''}:${(p.tracks ?? []).join(',')}`)
      .sort()
      .join('|'),
    () => {
      if (!_currentRoomRef.value || !_pc) return
      if (_discoveryDebounce !== null) return
      _discoveryDebounce = window.setTimeout(() => {
        _discoveryDebounce = null
        const roomId = _currentRoomRef.value
        if (roomId && _pc) void _refreshDiscovery(roomId, remoteStreams, participants.value, 'watcher')
      }, 600)
    },
  )

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
    // DIAG (F2 CICLO 3, B1): WHICH end-of-track handler fired — the origin lets
    // F7 discriminate a spurious cleanup (onmute/onended on a stale ended/muted
    // track riding the reused mid-1 transceiver) from a legitimate one.  The
    // three call sites in _handleRemoteTrack pass their fixed literal.
    origin: 'onmute' | 'onended' | 'onremovetrack' | 'unknown' = 'unknown',
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
  function _handleRemoteTrack(event: RTCTrackEvent): void {
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
      event.track.kind, _currentSessionId, event.track.id, /\//.test(event.track.id || ''),
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
        _cleanupEndedRemoteTrack(sessionKey, _txMid, _trackNameAtReceive, 'onended')
      }
      trk.onmute = () => {
        if (_displayAtReceive === 'screen') {
          // DIAG (F2 CICLO 3, B2): the mute handler fired on a SCREEN track — the
          // only mute path that calls cleanup.  If the bound track is the stale
          // ended/muted one, this is the spurious removal trigger.
          log.warn('[DIAG][track-event] onmute fired key=%s gate=screen', sessionKey)
          _cleanupEndedRemoteTrack(sessionKey, _txMid, _trackNameAtReceive, 'onmute')
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
      _cleanupEndedRemoteTrack(sessionKey, _txMid, _trackNameAtReceive, 'onremovetrack')
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

  /**
   * Enable a local track (mic/camera) on demand — the media opt-in for Caso B.
   *
   * Called by the toggles on their FIRST click (when no track is captured yet).
   * The permission prompt appears only HERE, never on join.  The flow mirrors
   * the proven shareStream mid-call pattern:
   *   getUserMedia(kind) → merge into _localStream → replaceTrack on the
   *   matching recvonly transceiver + direction='sendrecv' → renegotiate
   *   (offer → tracks/new location:'local' with sessionDescription → answer)
   *   → index the native track name → republish registry + presence with the
   *   REAL track set.
   *
   * On permission denied the state is UNCHANGED — only a log + early return,
   * so the toggle never flips to "on" (edge case of the ISSUE).
   */
  async function _enableLocalTrack(kind: 'mic' | 'camera'): Promise<void> {
    if (!_pc || !_currentSessionId) return

    const mediaKind = kind === 'mic' ? 'audio' : 'video'
    const tx = kind === 'mic' ? _localAudioTx : _localVideoTx
    // Already publishing this kind → the toggle flips track.enabled instead.
    const alreadySending = _localStream?.getTracks().some((t) => t.kind === mediaKind)
    if (alreadySending || !tx?.sender) return

    const roomId = _currentRoomRef.value
    // One media at a time: audio-only or video-only acquisition, so a failure
    // on one device does not block the other (edge case of the ISSUE).
    const constraints: MediaStreamConstraints = kind === 'mic'
      ? { audio: true, video: false }
      : { audio: false, video: true }

    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia(constraints)
    } catch (err) {
      log.error(
        '[enableLocalTrack] %s permission denied — state unchanged: %s',
        kind, err instanceof Error ? err.message : String(err),
      )
      return
    }

    // Merge the acquired track into _localStream (create it lazily).
    if (!_localStream) {
      _localStream = new MediaStream()
      localStream.value = _localStream
    }
    for (const track of stream.getTracks()) {
      _localStream.addTrack(track)
    }
    if (kind === 'camera') {
      cameraEnabled.value = true
      // S1: the self-view shows the camera ONLY when not sharing the screen —
      // while sharing it must keep showing the shared screen (a later camera
      // opt-in must not replace the screen preview).
      if (!isSharingScreen.value) {
        selfViewStream.value = _localStream
      }
    } else {
      micEnabled.value = true
    }

    // Switch the recvonly transceiver to sendrecv and attach the track.
    const track = stream.getTracks()[0]
    await tx.sender.replaceTrack(track)
    tx.direction = 'sendrecv'

    // Renegotiate + register the track on the SFU (mirror of shareStream GAP 1:
    // the publisher's offer is sent ALONG with the registration so the SFU can
    // answer/renegotiate and resolve the new track for subscribers).
    const offer = await _createAndSetOffer(_pc)
    const trackObjs = [{
      location: 'local' as const,
      mid: tx.mid as string,
      trackName: track.id,
    }]
    let regResult: any = null
    if (trackObjs.length) {
      regResult = await _registerLocalTracksOnSfu(
        _pc,
        _currentSessionId,
        trackObjs,
        { type: offer.type, sdp: offer.sdp || '' },
      )
    }

    // Close the renegotiation (3 branches, mirror of shareStream).
    const respSd = regResult?.sessionDescription
    const respSdp = respSd?.sdp ? String(respSd.sdp) : ''
    if (regResult?.requiresImmediateRenegotiation && respSd?.type === 'offer' && respSdp.length > 0) {
      // SFU generated a fresh offer for the new track — answer it back.
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
      await _pc.setRemoteDescription(new RTCSessionDescription(respSd))
    }

    // Index the native track name for _updatePublishedTracks (registry/presence
    // honest: ['mic'] after enabling only the mic).
    const names = _localTrackNamesByDisplay.get(kind) ?? []
    if (!names.includes(track.id)) names.push(track.id)
    _localTrackNamesByDisplay.set(kind, names)

    // Republish registry + presence with the REAL track set.
    if (roomId) {
      await _updatePublishedTracks(roomId)
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
   * 1. Caso B: does NOT capture media on join (opt-in — no permission prompt).
   * 2. Creates the RTCPeerConnection and adds recvonly audio/video transceivers
   *    BEFORE createOffer so the offer carries m= audio/video sections without
   *    capturing any media (the SFU rejects media-less offers with 400 → 502).
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

      // 1. Caso B (party-cell-usability-ux): NO media is captured on join —
      //    getUserMedia is deferred until the user explicitly enables mic or
      //    camera via a toggle (opt-in; no permission prompt on entry).
      //    _localStream stays null and the self-view placeholder shows instead.

      // 2. Create pc + recvonly transceivers BEFORE building the offer.
      //    createOffer() only emits m= sections for transceivers that already
      //    exist (Cloudflare rejects media-less offers with 400 → backend 502).
      //    The recvonly transceivers keep the m= audio/video sections present
      //    WITHOUT capturing any media; _enableLocalTrack later switches the
      //    matching one to sendrecv via replaceTrack + renegotiation.
      const pc = _createPeerConnection()
      _pc = pc
      _localAudioTx = pc.addTransceiver('audio', { direction: 'recvonly' })
      _localVideoTx = pc.addTransceiver('video', { direction: 'recvonly' })

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

      // 4. Send offer to signaling proxy.  Caso B: there are NO local tracks at
      //    join — localTracks/trackNames stay empty (the offer carries only the
      //    recvonly m-sections) and grow only after _enableLocalTrack publishes
      //    a track (indexed via _localTrackNamesByDisplay → _updatePublishedTracks).
      //    NOTE (F3 ciclo 4): the tracks array sent here in /sessions/new is
      //    IGNORED by the SFU anyway (NewSessionRequest has no tracks field);
      //    local tracks are registered later via /tracks/new location:'local'.
      const localTracks: TrackType[] = []
      const localTrackNames: string[] = []
      const localTrackObjs: Array<{ location: 'local'; mid: string; trackName: string }> = []
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

      // Caso B: no published tracks at join — the set stays empty and grows
      // only when _enableLocalTrack/shareStream add a track.
      _publishedTracks = []
      _publishedTrackNames = []
      _localTrackNamesByDisplay.clear()

      // 7. Register session in the room + discover & subscribe to others
      connectionPhase.value = 'registering'
      await _registerAndDiscoverSessions(roomId, remoteStreams, localTracks, localTrackNames, participants.value)

      // 7b. Caso B: SKIP _registerLocalTracksOnSfu on join — there are no local
      // tracks to publish (localTrackObjs is empty).  Tracks are registered on
      // the SFU later, inside _enableLocalTrack, on the first opt-in click
      // (same location:'local' + sessionDescription flow as shareStream).

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
      _startHeartbeat(roomId, mySessionId, remoteStreams, participants.value)

      // Only NOW is the call fully established (registry + presence + heartbeat
      // all in place; local SFU tracks are added on opt-in) — flip the "live"
      // indicator and the connecting phase (F1 — no more premature isConnected
      // → no screen blink).
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
      // DIAG (B7): publisher identity — participantId ("typically the user's
      // id") lets F3 correlate WHO shared with the discovery enumeration to
      // label host (1st to join) vs guest (2nd) in the test.  No role check
      // exists in code — this is purely a runtime correlation marker.
      const _publisherUserId = participants.value
        .find((p) => p.sessionId === _currentSessionId)?.participantId ?? '(unknown)'
      log.warn(
        '[DIAG][shareStream] addTransceiver sendonly session=%s userId=%s track=%s transceivers_before=%d',
        _currentSessionId, _publisherUserId, videoTrack.id, _pc.getTransceivers().length,
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
      // PERMANENTE (B2/F4): a share that reaches this point with EMPTY
      // screenTrackObjs means the sendonly transceiver never got its mid —
      // the screen is NOT registered on the SFU, yet registry + presence still
      // update below.  Silent inconsistency: the publisher sees the self-view,
      // subscribers get not_found_track_error forever.  Always visible.
      if (!screenTrackObjs.length) {
        log.warn(
          '[PERM][shareStream] screenTrackObjs EMPTY session=%s — screen track NOT registered on SFU (no mid); subscribers will not resolve it',
          _currentSessionId,
        )
      }
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
        await _updateRegistryTracks(roomId, tracksDisplay, trackNames, remoteStreams, participants.value)
      }

      // Notify room presence with the REAL tracks/trackNames (not hardcoded) so
      // the snapshot reflects the shared screen.
      if (roomId) {
        // DIAG (B6): presence tracks_update payload — lets F3 compare it against
        // the [DIAG][registry] re-register log to catch presence/registry
        // divergence (e.g. presence carrying 'screen' while the registry dropped
        // it, or a tracks↔trackNames positional misalignment — F7).
        log.warn(
          '[DIAG][shareStream] presence tracks_update room=%s session=%s tracks=%j trackNames=%j',
          roomId, _currentSessionId, tracksDisplay, trackNames,
        )
        // REV-2 (F4 gate): send sessionId so the backend targets THIS session's
        // presence entry (REV-1 multi-session presence).
        await _executePartyAction({
          action: 'tracks_update',
          roomId,
          tracks: tracksDisplay,
          trackNames,
          sessionId: _currentSessionId,
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

  /** Mute/unmute the mic, or ENABLE it on the first click (Caso B opt-in —
   *  no mic track captured yet → acquire + publish). */
  async function muteAudio(): Promise<void> {
    const hasAudio = (_localStream?.getAudioTracks().length ?? 0) > 0
    if (!hasAudio) {
      await _enableLocalTrack('mic')
      return
    }
    const audioTracks = _localStream!.getAudioTracks()
    for (const track of audioTracks) {
      track.enabled = !track.enabled
    }
    const muted = !audioTracks.some((t) => t.enabled)

    const roomId = _currentRoomRef.value
    if (roomId) {
      // REV-2 (F4 gate): send sessionId so the backend targets THIS session's
      // presence entry — with multi-session presence a participantId-only
      // toggle would flip the WRONG session of the same user (REV-1).
      await _executePartyAction({
        action: 'mute_toggle',
        roomId,
        isMuted: muted,
        sessionId: _currentSessionId,
      })
    }
  }

  /**
   * Recompute the caller's REAL published track set from the current local
   * media state and publish it to the room registry + presence (tracks_update).
   *
   * Toggles are INDEPENDENT decisions (F2): the camera is dropped from the
   * published set when disabled, re-added when enabled; the screen is dropped
   * when sharing stops.  Caso B (party-cell-usability-ux): the mic is NO
   * LONGER assumed to always be present — it only appears in
   * _localTrackNamesByDisplay after the user opts in via _enableLocalTrack
   * (muting stays a separate presence signal).  This keeps the registry/presence
   * honest so subscribers only see the tracks that are actually active.
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
      await _updateRegistryTracks(roomId, tracks, trackNames, remoteStreams, participants.value)
      // REV-2 (F4 gate): send sessionId so the backend targets THIS session's
      // presence entry (REV-1 multi-session presence).
      await _executePartyAction({
        action: 'tracks_update',
        roomId,
        tracks,
        trackNames,
        sessionId: _currentSessionId,
      })
    } catch (err) {
      log.warn(
        '[updatePublishedTracks] republish failed room=%s tracks=%j — heartbeat will reconcile: %s',
        roomId, tracks,
        err instanceof Error ? err.message : String(err),
      )
    }
  }

  /** Toggle the local camera on/off, or ENABLE it on the first click (Caso B
   *  opt-in — no camera track captured yet → acquire + publish).  Independent
   *  of mic/screen (F2). */
  async function toggleCamera(): Promise<void> {
    const hasVideo = (_localStream?.getVideoTracks().length ?? 0) > 0
    if (!hasVideo) {
      await _enableLocalTrack('camera')
      return
    }
    const videoTracks = _localStream!.getVideoTracks()
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
    if (roomId) await _refreshDiscovery(roomId, remoteStreams, participants.value, 'refreshRoom')
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

    // Broadcast leave so other clients drop us from presence (best-effort).
    // REV-2 (F4 gate): include sessionId so the backend (REV-1) removes ONLY
    // THIS session's presence entry — a parallel tab of the same user must
    // survive this leave instead of all of the user's sessions being dropped.
    if (roomId) {
      void _executePartyAction({ action: 'leave_room', roomId, sessionId })
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
    // F3 FIX (ITER_1 guest-screenshare CICLO 2): drop any pending-subscription
    // protection — a stale pending mid must never survive into the next call on
    // this recycled module-level state.
    _pendingSubscribeMids.clear()
    // F3 FIX (ITER_1 guest-screenshare CICLO 3): drop the per-tile add-time
    // grace map — a stale entry must never survive into the next call.
    _remoteStreamAddedAt.clear()
    // F3 FIX (ITER_1 H3): drop every transceiver-scoped meta before the pc is
    // closed (the WeakMap would GC them anyway, but clear explicitly so a
    // recycled module-level WeakMap can never tag a future session's mid).
    if (_pc) for (const tx of _pc.getTransceivers()) _transceiverMeta.delete(tx)
    _localTrackNamesByDisplay.clear()
    _screenTrackId = null
    _orphanScreenTx = null
    _localAudioTx = null
    _localVideoTx = null
    // Cancel a pending Caso D discovery so it cannot fire after the hang-up.
    if (_discoveryDebounce !== null) {
      window.clearTimeout(_discoveryDebounce)
      _discoveryDebounce = null
    }

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
    micEnabled.value = false
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
    if (_discoveryDebounce !== null) {
      window.clearTimeout(_discoveryDebounce)
      _discoveryDebounce = null
    }
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
    micEnabled,
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
