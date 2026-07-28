/**
 * @file usePartyCalls.ts
 * @description Vue 3 composable for Cloudflare Calls (WebRTC) — voice, video,
 * and screen-sharing in a room.
 *
 * ## Architecture
 * ```
 * usePartyCalls()
 *   ├── startCall(roomId)
 *   │   ├── apiFetch('POST /api/calls/session')   → signaling proxy
 *   │   ├── new RTCPeerConnection(iceServers)       → WebRTC peer
 *   │   ├── getUserMedia()                          → local mic/camera
 *   │   └── useDistributedState({contextId})        → room presence
 *   │
 *   ├── shareStream(mediaStream)
 *   │   ├── pc.addTrack()                           → add to peer
 *   │   └── updateParticipant()                     → notify room
 *   │
 *   ├── muteAudio()    → track.enabled = false
 *   ├── hangUp()       → close peer + stop tracks + leave room
 *   └── requestSnapshot() → force participant refresh
 * ```
 *
 * ## Usage
 * ```typescript
 * const { isConnected, startCall, hangUp, muteAudio } = usePartyCalls()
 * await startCall('planet-lobby')
 * ```
 *
 * Must be called inside a Vue component's `setup()` (or `<script setup>`).
 * Works with or without useBaseViewer — has no dependency on it.
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
  /** Whether the RTCPeerConnection is established */
  isConnected: Ref<boolean>

  /** Whether Cloudflare Calls App provisioning is in progress */
  isProvisioning: Ref<boolean>

  /** Local media stream (mic/camera) */
  localStream: Ref<MediaStream | null>

  /** Remote streams keyed by participantId */
  remoteStreams: Ref<Map<string, MediaStream>>

  /** Room participants from the distributed store */
  participants: Ref<Participant[]>

  /** Last connection or permission error, or null */
  connectionError: Ref<string | null>

  /** Create or join a room call */
  startCall: (roomId: string) => Promise<void>

  /** Share a media stream (screen, canvas) with the room */
  shareStream: (stream: MediaStream) => Promise<void>

  /** Toggle local microphone mute */
  muteAudio: () => void

  /** Leave the call and clean up all resources */
  hangUp: () => void

  /** Request a participant snapshot refresh */
  requestSnapshot: () => Promise<void>
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Thin wrapper around the shared apiFetch that throws on non-ok responses
 * with the server's error detail message.
 */
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

// ─────────────────────────────────────────────────────────────────────────────
// Composable
// ─────────────────────────────────────────────────────────────────────────────

let _pc: RTCPeerConnection | null = null
let _localStream: MediaStream | null = null

export function usePartyCalls(): UsePartyCallsReturn {
  const store = usePartyStore()

  // ── Reactive state ───────────────────────────────────────────────────────
  const isConnected = ref(false)
  const isProvisioning = ref(false)
  const localStream = ref<MediaStream | null>(null)
  const remoteStreams = ref<Map<string, MediaStream>>(new Map())
  const connectionError = ref<string | null>(null)
  const _currentRoomRef = ref<string | null>(null)

  /**
   * Expose participants from the store as a convenience ref so consumers
   * don't need to know about the store internals.
   */
  const participants = computed<Participant[]>(() => store.participants)

  // ── Distributed state (room presence) ──────────────────────────────────
  // useDistributedState is called ONCE at composable level (not inside
  // startCall).  A computed contextId reactively switches between the active
  // room and an empty channel when idle.  useDistributedState auto-reconnects
  // whenever the contextId changes.
  const _roomCtx = computed(() => {
    const roomId = _currentRoomRef.value
    return roomId ? `calls:room:${roomId}` : ''
  })

  useDistributedState({
    contextId: _roomCtx,
    store: store as any,
    branch: 'participants',
    conflictStrategy: 'lww',
  })

  // ── Internal helpers ─────────────────────────────────────────────────────

  /**
   * Create an RTCPeerConnection configured with the given ICE servers.
   */
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

    pc.ontrack = (event: RTCTrackEvent) => {
      const [stream] = event.streams
      if (stream) {
        log.debug('[PC] remote track received, stream id:', stream.id)
        // Track remote streams by a synthetic id — in a full
        // SFU scenario Cloudflare would tag each track with the
        // sender's participantId.
        const trackKey = stream.id
        const next = new Map(remoteStreams.value)
        next.set(trackKey, stream)
        remoteStreams.value = next
      }
    }

    return pc
  }

  /**
   * Request mic/camera permission and return the local stream.
   * Throws if permission is denied.
   */
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
   * Attach local tracks to the peer connection so they are sent
   * to the SFU / remote peers.
   */
  function _attachLocalTracks(pc: RTCPeerConnection, stream: MediaStream): void {
    for (const track of stream.getTracks()) {
      pc.addTrack(track, stream)
    }
  }

  /**
   * Stop all tracks in a stream and clean up.
   */
  function _stopStream(stream: MediaStream | null): void {
    if (!stream) return
    for (const track of stream.getTracks()) {
      track.stop()
    }
  }

  /**
   * Build the SDP offer and return it.
   */
  async function _createAndSetOffer(pc: RTCPeerConnection): Promise<RTCSessionDescriptionInit> {
    const offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    return offer
  }

  // ── Public actions ───────────────────────────────────────────────────────

  /**
   * Create or join a room call.
   *
   * 0. Provisions the Cloudflare Calls App if needed (POST /api/calls/provision)
   * 1. Requests mic/camera permission
   * 2. Creates an SDP offer
   * 3. Sends it to the signaling proxy (POST /api/calls/session)
   * 4. Applies the Cloudflare SDP answer
   * 5. Connects room presence via useDistributedState
   *
   * @param roomId - Room identifier (e.g. 'planet-lobby')
   */
  async function startCall(roomId: string): Promise<void> {
    connectionError.value = null
    isProvisioning.value = false

    // Guard: avoid re-entering a call
    if (_pc) {
      log.warn('[startCall] Already in a call — hanging up first')
      hangUp()
    }

    try {
      // Step 0: Provision Cloudflare Calls App (idempotent)
      log.info('[startCall] Provisioning Cloudflare Calls...')
      isProvisioning.value = true
      const provisionResult = await _apiFetchJson('/calls/provision', {
        method: 'POST',
      })
      log.info('[startCall] Provision status:', provisionResult.status)
      isProvisioning.value = false

      // 1. Request local media
      log.info('[startCall] Requesting mic/camera...')
      const stream = await _requestUserMedia()
      _localStream = stream
      localStream.value = stream

      // 2. Create SDP offer
      const pc = _createPeerConnection()
      _pc = pc
      const offer = await _createAndSetOffer(pc)

      // 3. Send offer to signaling proxy
      log.info('[startCall] Sending session request...')
      const sessionData = await _apiFetchJson('/calls/session', {
        method: 'POST',
        body: JSON.stringify({
          roomId,
          sessionDescription: {
            type: offer.type,
            sdp: offer.sdp,
          },
        }),
      })

      // 4. Apply Cloudflare SDP answer
      const answer = new RTCSessionDescription(sessionData.sessionDescription)
      await pc.setRemoteDescription(answer)
      isConnected.value = true

      // 5. Attach local tracks to the peer
      _attachLocalTracks(pc, stream)

      // 6. Room presence via computed contextId (useDistributedState declared
      //    at composable level — the _currentRoomRef change triggers an
      //    automatic WebSocket reconnect).
      _currentRoomRef.value = roomId
      store.currentRoom = roomId
      store.addParticipant({
        participantId: 'self', // will be replaced with actual user id
        displayName: 'Me',
        tracks: ['mic', 'camera'],
        isMuted: false,
        joinedAt: Date.now(),
      })

      log.info('[startCall] Call established for room:', roomId)
    } catch (err: unknown) {
      isProvisioning.value = false
      const msg = err instanceof Error ? err.message : 'Failed to start call'
      connectionError.value = msg
      log.error('[startCall] Error:', msg)
      // Clean up partially-created state
      hangUp()
    }
  }

  /**
   * Share an additional media stream (e.g. screen share or 3D canvas)
   * with the current room.
   *
   * @param stream - The MediaStream to share (from getDisplayMedia or canvas.captureStream)
   */
  async function shareStream(stream: MediaStream): Promise<void> {
    if (!_pc) {
      connectionError.value = 'Not connected — start a call first'
      log.warn('[shareStream] No peer connection')
      return
    }

    try {
      for (const track of stream.getTracks()) {
        _pc.addTrack(track, stream)
      }

      // Keep a reference so the stream isn't garbage-collected
      // Update the room presence to reflect screen-sharing
      store.updateParticipant('self', {
        tracks: ['mic', 'camera', 'screen'],
      })

      log.info('[shareStream] Stream shared successfully')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to share stream'
      connectionError.value = msg
      log.error('[shareStream] Error:', msg)
    }
  }

  /**
   * Mute or unmute the local microphone.
   */
  function muteAudio(): void {
    if (!_localStream) return
    const audioTracks = _localStream.getAudioTracks()
    for (const track of audioTracks) {
      track.enabled = !track.enabled
    }
    store.updateParticipant('self', {
      isMuted: !audioTracks.some((t) => t.enabled),
    })
  }

  /**
   * Leave the call — close the peer connection, stop all local tracks,
   * disconnect room presence, and reset state.
   */
  function hangUp(): void {
    // Close peer connection
    if (_pc) {
      _pc.close()
      _pc = null
    }

    // Stop local media
    _stopStream(_localStream)
    _localStream = null

    // Disconnect room presence: setting _currentRoomRef to null makes the
    // useDistributedState computed resolve to '' (idle channel), which
    // automatically closes the WebSocket via the watcher.
    _currentRoomRef.value = null

    // Reset state
    isConnected.value = false
    localStream.value = null
    remoteStreams.value = new Map()
    store.reset()

    log.info('[hangUp] Call ended')
  }

  /**
   * Request a snapshot of the current room participants.
   * Useful after reconnect or to force-sync state.
   */
  async function requestSnapshot(): Promise<void> {
    log.debug('[requestSnapshot] Not implemented — useDistributedState handles snapshots')
    // In the current architecture, useDistributedState sends a snapshot_request
    // automatically on WebSocket connect.  This method is a placeholder for
    // future manual refresh if needed.
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
