/**
 * @file usePartyCalls.ts — FACADE + REACTIVE SHELL
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
 *
 * ⚠️ MODULARIZED (issue party-calls-modularization): this file is now the
 * public FACADE + reactive shell (~400 lines).  The domain logic lives in the
 * sibling ``party-calls/`` modules (state, http, sfuSignaling, subscription,
 * discovery, remoteMedia, localMedia) — see ``party-calls/README.md``.  The
 * public contract (``usePartyCalls`` + ``type AvailableRoom`` and friends) is
 * unchanged, so no caller needed edits (verbatim code movement).
 */

import { ref, computed, onUnmounted, watch } from 'vue'
import { usePartyStore, type Participant, type TrackType } from '#artifacts/shared/stores/partyStore'
import { useDistributedState } from '#artifacts/shared/composables/useDistributedState'
import { apiFetch } from '#artifacts/shared/services/apiService'

import { log, state } from './party-calls/state'
import {
  _subscribedSessions,
  _subscribedTrackNames,
  _remoteTrackTypes,
  _remoteMidToTrackName,
  _transceiverMeta,
  _pendingSubscribeMids,
  _remoteStreamAddedAt,
  _localTrackNamesByDisplay,
} from './party-calls/state'
import { _apiFetchJson, _pollProvisionTask, _executePartyAction } from './party-calls/http'
import { _createAndSetOffer } from './party-calls/sfuSignaling'
import { _refreshDiscovery, _registerAndDiscoverSessions, _startHeartbeat, _stopHeartbeat } from './party-calls/discovery'
import { _handleRemoteTrack } from './party-calls/remoteMedia'
import { createLocalMediaActions, _stopStream, type LocalMediaContext } from './party-calls/localMedia'
import type { ConnectionPhase, AvailableRoom, UsePartyCallsReturn } from './party-calls/types'

export type { ConnectionPhase, AvailableRoom, UsePartyCallsReturn } from './party-calls/types'

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
      if (!_currentRoomRef.value || !state._pc) return
      if (_discoveryDebounce !== null) return
      _discoveryDebounce = window.setTimeout(() => {
        _discoveryDebounce = null
        const roomId = _currentRoomRef.value
        if (roomId && state._pc) void _refreshDiscovery(roomId, remoteStreams, participants.value, 'watcher')
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

    pc.ontrack = (event) => _handleRemoteTrack(event, remoteStreams)

    return pc
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

    if (state._pc) {
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
      //    state._localStream stays null and the self-view placeholder shows instead.

      // 2. Create pc + recvonly transceivers BEFORE building the offer.
      //    createOffer() only emits m= sections for transceivers that already
      //    exist (Cloudflare rejects media-less offers with 400 → backend 502).
      //    The recvonly transceivers keep the m= audio/video sections present
      //    WITHOUT capturing any media; _enableLocalTrack later switches the
      //    matching one to sendrecv via replaceTrack + renegotiation.
      const pc = _createPeerConnection()
      state._pc = pc
      state._localAudioTx = pc.addTransceiver('audio', { direction: 'recvonly' })
      state._localVideoTx = pc.addTransceiver('video', { direction: 'recvonly' })

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
      state._currentSessionId = mySessionId

      // DIAG: local tracks were attached BEFORE the offer was built
      log.warn('[DIAG][usePartyCalls] STEP6 addTrack: transceivers=%d',
        pc.getTransceivers().length)

      // 6. Room presence via computed contextId (auto WS reconnect)
      _currentRoomRef.value = roomId
      store.currentRoom = roomId

      // Caso B: no published tracks at join — the set stays empty and grows
      // only when _enableLocalTrack/shareStream add a track.
      state._publishedTracks = []
      state._publishedTrackNames = []
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
        state._pc ? 'created' : 'null',
        state._pc ? state._pc.getTransceivers().length : -1,
        _currentRoomRef.value,
      )
      hangUp()
    }
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
    const sessionId = state._currentSessionId

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
    if (state._pc) for (const tx of state._pc.getTransceivers()) _transceiverMeta.delete(tx)
    _localTrackNamesByDisplay.clear()
    state._screenTrackId = null
    state._orphanScreenTx = null
    state._localAudioTx = null
    state._localVideoTx = null
    // Cancel a pending Caso D discovery so it cannot fire after the hang-up.
    if (_discoveryDebounce !== null) {
      window.clearTimeout(_discoveryDebounce)
      _discoveryDebounce = null
    }

    // Close peer connection
    if (state._pc) {
      state._pc.close()
      state._pc = null
    }
    state._currentSessionId = null

    // Stop local media (mic/camera + shared screen — leak fix: the screen
    // stream was never stopped before, so the tab kept capturing after hangUp)
    _stopStream(state._localStream)
    state._localStream = null
    _stopStream(state._screenStream)
    state._screenStream = null
    state._publishedTracks = []
    state._publishedTrackNames = []

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

  // ── Local-media / screen-share actions (from party-calls/localMedia) ──────
  // The factory receives the reactive shell refs the actions close over — the
  // exact same refs the old monolithic shell closures captured.
  const mediaCtx: LocalMediaContext = {
    localStream,
    selfViewStream,
    cameraEnabled,
    micEnabled,
    isSharingScreen,
    remoteStreams,
    connectionError,
    participants,
    getRoomId: () => _currentRoomRef.value,
  }
  const { shareStream, muteAudio, toggleCamera, toggleScreenShare, stopSharing } = createLocalMediaActions(mediaCtx)

  // ── Cleanup on component unmount ─────────────────────────────────────────

  onUnmounted(() => {
    if (_discoveryDebounce !== null) {
      window.clearTimeout(_discoveryDebounce)
      _discoveryDebounce = null
    }
    if (state._pc || state._localStream) {
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
