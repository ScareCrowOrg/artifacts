/**
 * @file party-calls/types.ts
 * @description Public contracts for the usePartyCalls composable (Cloudflare
 * Calls / WebRTC).  Extracted VERBATIM from the former monolithic
 * ``usePartyCalls.ts`` (section "Types").  ``RemoteSession`` and
 * ``SfuTrackResult`` now carry ``export`` because they are shared across the
 * ``party-calls/`` modules (internals only — no caller impact).
 *
 * Dependency graph: leaf module (no imports from other ``party-calls/``
 * modules).  See ``party-calls/README.md``.
 */

import type { Ref } from 'vue'
import type { Participant, TrackType } from '#artifacts/shared/stores/partyStore'

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
export interface RemoteSession {
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
export interface SfuTrackResult {
  trackName?: string
  mid?: string
  errorCode?: string
  errorDescription?: string
}
