/**
 * @file party-calls/localMedia.ts
 * @description Local media actions for the usePartyCalls composable (Cloudflare
 * Calls / WebRTC): opt-in mic/camera capture (Caso B), screen sharing / publish
 * and stop, and the published-track-set recompute.  Extracted VERBATIM from the
 * former monolithic ``usePartyCalls.ts`` (shell section), wrapped in a factory
 * ``createLocalMediaActions(ctx)`` that receives the shell's reactive refs.
 * Screen-share transceiver helpers live in ``./sfuSignaling`` (Ajuste 1 + F13 —
 * keeps this module under RULESET 1.1's 650-line limit).  No reverse imports.
 */

import { _executePartyAction } from './http'
import {
  _createAndSetOffer,
  _ensurePcReadyForNegotiation,
  _registerLocalTracksOnSfu,
  _removeTrackFromSfu,
  _closeLocalRenegotiation,
  _allocateSendonlyTransceiver,
  _applyVideoCodecFilter,
  _buildLocalTrackObjs,
  _detachSendonlyTransceivers,
  _publishLocalTracks,
} from './sfuSignaling'
import { _updateRegistryTracks } from './discovery'
import {
  log,
  state,
  _withNegotiationLock,
  _localTrackNamesByDisplay,
  _activeScreenIdsByInstance,
} from './state'
import type { TrackType, Participant } from '#artifacts/shared/stores/partyStore'
import type { Ref } from 'vue'

// ─────────────────────────────────────────────────────────────────────────────
// Local media / publish context
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Per-instance screen-share state (F13 — party-calls-screen-audio-session-isolation).
 * Each composable instance owns its OWN screen share tracking, so a party-cell +
 * glb-content-viewer on the same page no longer clobber each other's share on the
 * shared PC/session (the 2nd shareStream previously overwrote the 1st's
 * ``_screenStream``/``_screenTrackId``/``_orphanScreenTx``).  The module-level
 * ``state._screenStream``/``_screenTrackId``/``_orphanScreenTx`` remain as
 * DIAGNOSTIC mirrors of the most recent activity (test backward-compat + debug).
 */
export interface ScreenShareState {
  /** The display stream being shared (screen/3D canvas) by THIS instance. */
  stream: MediaStream | null
  /** Native id of the shared VIDEO track. */
  trackId: string | null
  /** Native id of the shared DISPLAY-AUDIO track (optional — null when the
   *  sharer unchecked "share tab audio" in the native picker). */
  audioTrackId: string | null
  /** The sendonly VIDEO transceiver orphaned by THIS instance's last
   *  stopSharing (reused via replaceTrack so share/stop cycles don't stack). */
  orphanVideoTx: RTCRtpTransceiver | null
  /** The sendonly AUDIO transceiver orphaned by THIS instance's last
   *  stopSharing (Ajuste 1 — display-audio track). */
  orphanAudioTx: RTCRtpTransceiver | null
}

/** Reactive shell refs the local-media actions close over — the extraction
 *  param that replaces the old shell closure.  Assembled by the facade
 *  ``usePartyCalls.ts`` and passed to ``createLocalMediaActions``. */
export interface LocalMediaContext {
  localStream: Ref<MediaStream | null>
  selfViewStream: Ref<MediaStream | null>
  cameraEnabled: Ref<boolean>
  micEnabled: Ref<boolean>
  isSharingScreen: Ref<boolean>
  remoteStreams: Ref<Map<string, MediaStream>>
  connectionError: Ref<string | null>
  participants: Readonly<Ref<Participant[]>>
  /** Per-instance screen-share state (F13 isolation) — the facade creates one
   *  fresh object per ``usePartyCalls()`` instance. */
  screenState: ScreenShareState
  getRoomId: () => string | null
}

/** Stop all tracks in a stream and clean up. */
export function _stopStream(stream: MediaStream | null): void {
  if (!stream) return
  for (const track of stream.getTracks()) {
    track.stop()
  }
}

/**
 * Factory that assembles the local-media / screen-share actions for the shell.
 * Each returned action closes over ``ctx`` (the reactive refs) + the module-level
 * state in ``./state`` — identical behaviour to the original shell closures.
 */
export function createLocalMediaActions(ctx: LocalMediaContext) {
  /**
   * Enable a local track (mic/camera) on demand — the media opt-in for Caso B.
   * Called by the toggles on their FIRST click (no track captured yet); the
   * permission prompt appears only HERE.  Flow mirrors shareStream: getUserMedia
   * → merge into state._localStream → replaceTrack on the matching recvonly
   * transceiver + direction='sendrecv' → renegotiate (offer → tracks/new
   * location:'local' → answer) → index the native name → republish the REAL set.
   * On permission denied the state is UNCHANGED (only a log + early return), so
   * the toggle never flips to "on".
   */
  async function _enableLocalTrack(kind: 'mic' | 'camera'): Promise<void> {
    if (!state._pc || !state._currentSessionId) return

    const mediaKind = kind === 'mic' ? 'audio' : 'video'
    const tx = kind === 'mic' ? state._localAudioTx : state._localVideoTx
    // Already publishing this kind → the toggle flips track.enabled instead.
    const alreadySending = state._localStream?.getTracks().some((t) => t.kind === mediaKind)
    if (alreadySending || !tx?.sender) return

    const roomId = ctx.getRoomId()
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

    // Merge the acquired track into state._localStream (create it lazily).
    if (!state._localStream) {
      state._localStream = new MediaStream()
      ctx.localStream.value = state._localStream
    }
    for (const track of stream.getTracks()) {
      state._localStream.addTrack(track)
    }
    if (kind === 'camera') {
      ctx.cameraEnabled.value = true
      // S1: the self-view shows the camera ONLY when not sharing the screen —
      // while sharing it must keep showing the shared screen (a later camera
      // opt-in must not replace the screen preview).
      if (!ctx.isSharingScreen.value) {
        ctx.selfViewStream.value = state._localStream
      }
    } else {
      ctx.micEnabled.value = true
    }

    // Switch the recvonly transceiver to sendrecv and attach the track.
    const track = stream.getTracks()[0]
    await tx.sender.replaceTrack(track)
    tx.direction = 'sendrecv'

    // Renegotiate + register the track on the SFU (mirror of shareStream GAP 1:
    // the publisher's offer is sent ALONG with the registration so the SFU can
    // answer/renegotiate and resolve the new track for subscribers).
    // F2 (review #3078): the offer → tracks/new → close mutates the SAME peer
    // connection the shareStream publish and the subscribe renegotiate — run it
    // under the same _withNegotiationLock so a camera/mic opt-in can never
    // overlap a concurrent screen share or heartbeat subscribe.
    const closed = await _withNegotiationLock(async () => {
      const offer = await _createAndSetOffer(state._pc!)
      const trackObjs = [{
        location: 'local' as const,
        mid: tx.mid as string,
        trackName: track.id,
      }]
      let regResult: any = null
      if (trackObjs.length) {
        regResult = await _registerLocalTracksOnSfu(
          state._pc!,
          state._currentSessionId!,
          trackObjs,
          { type: offer.type, sdp: offer.sdp || '' },
        )
      }
      // Close the renegotiation (F9: single helper — offer → answer, direct
      // answer → apply, null → roll back so the PC is not wedged in
      // have-local-offer).
      return _closeLocalRenegotiation(regResult)
    })
    if (!closed) {
      // G2 FIX (bug-hardening): the SFU registration FAILED (regResult null or
      // a per-track error) — the track was never registered.  Do NOT index or
      // publish it (registry/presence must not announce tracks the SFU never
      // resolved → not_found_track_error for subscribers); revert the enable
      // state so the next toggle click can retry cleanly.  The local offer was
      // already rolled back by the helper, so the PC is back in 'stable' (no
      // InvalidStateError on a subsequent createOffer).
      log.warn('[enableLocalTrack] %s SFU registration failed — track NOT published to registry/presence', kind)
      ctx.connectionError.value = `Could not enable ${kind === 'mic' ? 'microphone' : 'camera'} — media registration with the SFU failed. Please try again.`
      for (const t of stream.getTracks()) {
        state._localStream?.removeTrack(t)
        t.stop()
      }
      if (state._localStream && state._localStream.getTracks().length === 0) {
        state._localStream = null
        ctx.localStream.value = null
      }
      try {
        await tx.sender.replaceTrack(null)
        tx.direction = 'recvonly'
      } catch { /* ignore — rollback already returned the PC to stable */ }
      if (kind === 'camera') {
        ctx.cameraEnabled.value = false
        // R#5 (review #3077): while a screen share is active the self-view
        // shows the SHARED SCREEN — a failed camera registration must not
        // blank it.  Only fall back to the (now-null) local stream when not
        // sharing.
        if (!ctx.isSharingScreen.value) {
          ctx.selfViewStream.value = ctx.localStream.value
        }
      } else {
        ctx.micEnabled.value = false
      }
      return
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

  /** Mute/unmute the mic, or ENABLE it on the first click (Caso B opt-in —
   *  no mic track captured yet → acquire + publish). */
  async function muteAudio(): Promise<void> {
    const hasAudio = (state._localStream?.getAudioTracks().length ?? 0) > 0
    if (!hasAudio) {
      await _enableLocalTrack('mic')
      return
    }
    const audioTracks = state._localStream!.getAudioTracks()
    for (const track of audioTracks) {
      track.enabled = !track.enabled
    }
    const muted = !audioTracks.some((t) => t.enabled)

    const roomId = ctx.getRoomId()
    if (roomId) {
      // REV-2 (F4 gate): send sessionId so the backend targets THIS session's
      // presence entry — with multi-session presence a participantId-only
      // toggle would flip the WRONG session of the same user (REV-1).
      await _executePartyAction({
        action: 'mute_toggle',
        roomId,
        isMuted: muted,
        sessionId: state._currentSessionId,
      })
    }
  }

  /**
   * Recompute the caller's REAL published track set from the current local
   * media state and publish it to the room registry + presence (tracks_update).
   * Toggles are INDEPENDENT (F2); the mic only appears after opt-in (Caso B).
   * Failures are non-fatal (best-effort); the 20s heartbeat re-reconciles.
   */
  async function _updatePublishedTracks(roomId: string): Promise<void> {
    const tracks: TrackType[] = []
    const trackNames: string[] = []
    // mic/camera come from the (session-level) _localTrackNamesByDisplay map.
    for (const [display, names] of _localTrackNamesByDisplay) {
      if (!names.length) continue
      if (display === 'camera' && !ctx.cameraEnabled.value) continue
      tracks.push(display)
      trackNames.push(...names)
    }
    // F13 (review #4): screen/screenAudio come from the MERGED set of ALL
    // instances sharing on the session — a republish from ONE instance must not
    // drop another instance's live screen ids (subscribers would prune its tile).
    for (const ids of _activeScreenIdsByInstance.values()) {
      if (ids.videoId) {
        tracks.push('screen')
        trackNames.push(ids.videoId)
      }
      if (ids.audioId) {
        tracks.push('screenAudio')
        trackNames.push(ids.audioId)
      }
    }
    state._publishedTracks = [...tracks]
    state._publishedTrackNames = [...trackNames]
    // PERMANENTE: the real published track set — the registry source state subscribers
    // reconcile against. Confirms B2's origin: after stopSharing, `tracks` is ['mic'] and
    // the screen nativeId is gone from trackNames BEFORE _refreshDiscovery runs on peers.
    log.info(
      '[party-cell][tracks] room=%s published tracks=%j trackNames=%j',
      roomId, state._publishedTracks, state._publishedTrackNames,
    )
    try {
      await _updateRegistryTracks(roomId, tracks, trackNames, ctx.remoteStreams, ctx.participants.value)
      // REV-2 (F4 gate): send sessionId so the backend targets THIS session's
      // presence entry (REV-1 multi-session presence).
      await _executePartyAction({
        action: 'tracks_update',
        roomId,
        tracks,
        trackNames,
        sessionId: state._currentSessionId,
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
   *  opt-in — no camera track captured yet → acquire + publish).  Independent (F2). */
  async function toggleCamera(): Promise<void> {
    const hasVideo = (state._localStream?.getVideoTracks().length ?? 0) > 0
    if (!hasVideo) {
      await _enableLocalTrack('camera')
      return
    }
    const videoTracks = state._localStream!.getVideoTracks()
    const nowEnabled = !videoTracks.some((t) => t.enabled)
    for (const track of videoTracks) track.enabled = nowEnabled
    ctx.cameraEnabled.value = nowEnabled
    const roomId = ctx.getRoomId()
    if (roomId) void _updatePublishedTracks(roomId)
  }

  /** Start screen sharing, or stop it when already sharing (F2). */
  async function toggleScreenShare(): Promise<void> {
    if (ctx.isSharingScreen.value) {
      await stopSharing()
      return
    }
    if (!state._pc) {
      ctx.connectionError.value = 'Not connected — start a call first'
      log.warn('[toggleScreenShare] No peer connection')
      return
    }
    try {
      // Ajuste 1 (party-calls-screen-audio-session-isolation): request the
      // DISPLAY AUDIO too — the sharer can share a tab/video/game WITH its sound.
      // The audio is OPTIONAL (the picker lets the user uncheck "share tab
      // audio") — shareStream continues video-only when absent.
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: true,
      })
      await shareStream(stream)
      // F6/F10: shareStream flips isSharingScreen + mirrors itself (success and
      // failure) — nothing to reflect here.  A cancelled getDisplayMedia throws
      // before this point → state unchanged.
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
    // F13: the screen state is PER-INSTANCE (ctx.screenState) — a stop on this
    // composable instance never touches another instance's share on the shared
    // PC/session (the old module-level _screenStream was clobbered by the 2nd
    // shareStream and stopped the WRONG stream on stop).
    const ss = ctx.screenState
    if (!ss.stream) return
    _stopStream(ss.stream)
    ss.stream = null
    state._screenStream = null // diagnostic mirror
    if (state._pc) {
      const pc = state._pc
      let removedSender = false
      // F6 FIX (bug-hardening): match the screen VIDEO sender by native id
      // (ss.trackId — populated by shareStream so a DIRECT caller like
      // glb-content-viewer is covered); fallback to the dedicated SENDONLY video
      // transceiver when the id is null (prevents stacking per share/stop).
      const matchedSender = pc.getSenders().find((s) => s.track?.id === ss.trackId)
        ?? (ss.trackId === null
          ? pc.getSenders().find((s) => s.track?.kind === 'video'
              && pc.getTransceivers().find((t) => t.sender === s)?.direction === 'sendonly')
          : undefined)
      if (matchedSender) {
        // Keep the sendonly transceiver for the next shareStream — removeTrack
        // only nulls sender.track; the transceiver/m-section survives.  A1:
        // reuse it via replaceTrack instead of stacking per share/stop (SFU 413).
        const orphanTx = pc.getTransceivers().find((t) => t.sender === matchedSender)
        if (orphanTx) {
          ss.orphanVideoTx = orphanTx
          state._orphanScreenTx = orphanTx // diagnostic mirror
        }
        pc.removeTrack(matchedSender)
        removedSender = true
      }
      // Tell the SFU the track is gone — tracks/close identifies by the
      // transceiver mid (survives removeTrack), NOT the native track id.  The
      // renegotiate-with-offer path is rejected (406 → 502); non-fatal (the SFU
      // reaper still signals event=ended to subscribed peers).
      if (removedSender && ss.orphanVideoTx?.mid) {
        await _removeTrackFromSfu(ss.orphanVideoTx.mid)
      } else if (removedSender) {
        log.warn(
          '[stopSharing] cannot remove screen track from SFU — no orphan transceiver mid available',
        )
      }
      // Ajuste 1: SYMMETRIC cleanup of the display-audio track (when present) —
      // detach its sendonly sender, keep the audio orphan for reuse, and remove
      // it from the SFU by its own mid (the same tracks/close contract).
      const audioSender = ss.audioTrackId
        ? pc.getSenders().find((s) => s.track?.id === ss.audioTrackId)
        : undefined
      if (audioSender) {
        const audioOrphanTx = pc.getTransceivers().find((t) => t.sender === audioSender)
        if (audioOrphanTx) {
          ss.orphanAudioTx = audioOrphanTx
          state._orphanScreenAudioTx = audioOrphanTx // diagnostic mirror
        }
        pc.removeTrack(audioSender)
        if (ss.orphanAudioTx?.mid) {
          await _removeTrackFromSfu(ss.orphanAudioTx.mid)
        } else {
          // review #6 (party-calls-screen-audio-session-isolation): symmetric
          // warning to the video path — an audio transceiver without a mid was
          // detached locally but NOT closed on the SFU (the audio track would
          // otherwise leak until the SFU reaper).
          log.warn(
            '[stopSharing] cannot remove screen AUDIO track from SFU — no orphan audio transceiver mid available',
          )
        }
      }
    }
    ss.trackId = null
    ss.audioTrackId = null
    state._screenTrackId = null // diagnostic mirror
    state._screenAudioTrackId = null // diagnostic mirror
    // F13 (review #4): this instance's screen contribution leaves the shared
    // session's registry — _updatePublishedTracks then republishes the MERGED
    // set of the remaining instances.
    _activeScreenIdsByInstance.delete(ss)
    ctx.isSharingScreen.value = false
    // S1 (F3): swap the self-view back to the camera when sharing stops.
    ctx.selfViewStream.value = ctx.localStream.value
    const roomId = ctx.getRoomId()
    if (roomId) void _updatePublishedTracks(roomId)
    log.info('[stopSharing] Screen share stopped')
  }

  /** review #3 (party-calls-screen-audio-session-isolation): reset the share
   *  state after a failure/exception — never leave the self-view stuck on the
   *  screen, the browser capturing, or a stale registry entry.  Shared by the
   *  G2 branch and the shareStream catch. */
  function _resetScreenShareState(stream: MediaStream | null): void {
    _stopStream(stream)
    const ss = ctx.screenState
    ss.stream = null
    ss.trackId = null
    ss.audioTrackId = null
    state._screenStream = null // mirror
    state._screenTrackId = null // mirror
    state._screenAudioTrackId = null // mirror
    ctx.selfViewStream.value = ctx.localStream.value
    ctx.isSharingScreen.value = false
    _activeScreenIdsByInstance.delete(ss)
  }

  /**
   * Share an additional media stream (screen/3D canvas) with the room — MID-CALL,
   * so unlike startCall it explicitly registers the track(s) on the SFU via
   * tracks/new location:'local' sending the publisher's offer ALONG with the
   * registration (GAP 1), applies the SFU's answer/offer, extends the room
   * registry trackNames (GAP 2), and publishes presence with the REAL set (GAP 3)
   * so subscribers render a dedicated screen tile (GAP 4).
   */
  async function shareStream(stream: MediaStream): Promise<void> {
    if (!state._pc) {
      ctx.connectionError.value = 'Not connected — start a call first'
      log.warn('[shareStream] No peer connection')
      return
    }
    if (!state._currentSessionId) {
      ctx.connectionError.value = 'Not connected — start a call first'
      log.warn('[shareStream] No current session — cannot negotiate')
      return
    }
    const ss = ctx.screenState

    // 2D + 2C (party-cell-screen-share-sfu-register-fail) + review #3
    // (party-calls-screen-audio-session-isolation): WAIT for a healthy, STABLE
    // PC BEFORE allocating the sendonly transceivers — ``addTransceiver`` throws
    // InvalidStateError while a renegotiation is in flight.  The stable-signaling
    // wait runs OUTSIDE the global lock (F3); the lock below then makes the
    // offer → tracks/new → close an atomic section.  Failing here leaves NO
    // share state set (clean retry).
    const ready = await _ensurePcReadyForNegotiation(state._pc!)
    if (!ready) {
      ctx.connectionError.value = 'Could not start screen share — the connection is not ready. Please try again.'
      log.warn('[shareStream] PC not ready for screen share renegotiation')
      return
    }

    try {
      // Ajuste 1 (party-calls-screen-audio-session-isolation): share the VIDEO
      // track AND — when the user left "share tab audio" checked — the DISPLAY
      // AUDIO track.  The audio is OPTIONAL (user can uncheck it → share stays
      // video-only) and is registered as its OWN dedicated sendonly track (CICLO
      // 3, never addTrack) so the receiver gets ``mic`` and ``screenAudio`` as
      // SEPARATE streams (echo control).
      const videoTrack = stream.getVideoTracks()[0]
      if (!videoTrack) {
        log.warn('[shareStream] No video track in display stream — nothing to share')
        return
      }
      const audioTrack = stream.getAudioTracks()[0] ?? null
      // F13: per-instance screen state (ctx.screenState, declared above).
      ss.stream = stream
      ss.trackId = videoTrack.id
      ss.audioTrackId = audioTrack?.id ?? null
      // Diagnostic mirrors (F13 — the ACTIVE state lives in ss).
      state._screenStream = stream
      state._screenTrackId = videoTrack.id
      state._screenAudioTrackId = audioTrack?.id ?? null
      // S1 (F3): the self-view shows the shared screen while sharing.
      ctx.selfViewStream.value = stream
      // F3 FIX (bug-hardening): the browser's NATIVE "Stop sharing" ends the
      // display track — run the same cleanup as stopSharing so isSharingScreen,
      // the registry/presence, the self-view and the SFU registration all stay
      // consistent (previously the share stayed stale: isSharingScreen true,
      // registry advertising a dead track, subscribers stuck on a black tile).
      videoTrack.addEventListener('ended', () => {
        if (ctx.screenState.stream) void stopSharing()
      })
      // CICLO 3 (dedicated sendonly, never addTrack) + A1 orphan reuse for the
      // screen VIDEO and (when present) its DISPLAY-AUDIO — implemented in
      // _allocateSendonlyTransceiver/_applyVideoCodecFilter (sfuSignaling.ts).
      const videoAlloc = await _allocateSendonlyTransceiver(state._pc, videoTrack, ss.orphanVideoTx)
      const screenTx = videoAlloc.tx
      if (videoAlloc.reusedOrphan) {
        ss.orphanVideoTx = null
        state._orphanScreenTx = null // mirror consumed
      }
      // 2B (defensive codec filter VP8/VP9/AV1/H264 — see _applyVideoCodecFilter).
      _applyVideoCodecFilter(screenTx)

      let screenAudioTx: RTCRtpTransceiver | null = null
      if (audioTrack) {
        const audioAlloc = await _allocateSendonlyTransceiver(state._pc, audioTrack, ss.orphanAudioTx)
        screenAudioTx = audioAlloc.tx
        if (audioAlloc.reusedOrphan) {
          ss.orphanAudioTx = null
          state._orphanScreenAudioTx = null // mirror consumed
        }
      }

      // 2C (party-cell-screen-share-sfu-register-fail): the offer → tracks/new
      // → close runs UNDER the serialization lock — the diagnosis proved an
      // overlapping renegotiation corrupts signaling/ICE on a PC that already
      // receives another participant's screen.  `closed` false → the G2 branch
      // below (friendly error, PC rolled back, no registry/presence announce).
      const closed = await _withNegotiationLock(async () => {
        // Build the offer so the new transceiver gets its mid and the
        // renegotiation SDP carries the new m= video section.
        const offer = await state._pc!.createOffer()
        await state._pc!.setLocalDescription(offer)

        // GAP 1 + Ajuste 1: build the tracks/new (location:'local') payload for
        // BOTH the video AND the display-audio (see _buildLocalTrackObjs) and
        // register + close the renegotiation in one step (_publishLocalTracks —
        // the offer is sent ALONG with the registration so the SFU resolves both
        // m-lines; subscribers reference the NATIVE track ids).
        const screenTrackObjs = _buildLocalTrackObjs(state._pc!, [videoTrack, audioTrack])
        return _publishLocalTracks(state._pc!, state._currentSessionId!, screenTrackObjs, offer)
      })
      if (!closed) {
        // G2 FIX (bug-hardening): the screen track was NOT registered on the
        // SFU (regResult null / per-track error — the offer was already rolled
        // back).  Do NOT publish 'screen' (subscribers would get
        // not_found_track_error forever).  R#3 (review #3077): detach the
        // sendonly transceivers (video + display-audio) and restore them as
        // ORPHANS so the next share reuses them (A1 / SFU 413).
        log.warn('[shareStream] SFU registration failed — screen track NOT shared')
        const [failedVideoTx, failedAudioTx] = _detachSendonlyTransceivers(state._pc, [videoTrack, audioTrack])
        if (failedVideoTx) {
          ss.orphanVideoTx = failedVideoTx
          state._orphanScreenTx = failedVideoTx // mirror
        }
        if (failedAudioTx) {
          ss.orphanAudioTx = failedAudioTx
          state._orphanScreenAudioTx = failedAudioTx // mirror
        }
        // F13 (review #4): no registry contribution from a failed share.
        _resetScreenShareState(stream)
        ctx.connectionError.value = 'Could not start screen share — media registration with the SFU failed. Please try again.'
        return
      }

      // F10 FIX (bug-hardening): single writer — the screen's native ids live in
      // ctx.screenState and _updatePublishedTracks computes the REAL published
      // set (per-instance, never pushed into the shared _localTrackNamesByDisplay).
      const roomId = ctx.getRoomId()
      // F13 (review #4): register THIS instance's screen contribution in the
      // shared-session registry BEFORE the republish — _updatePublishedTracks
      // merges ALL instances so a republish never drops a live screen.
      _activeScreenIdsByInstance.set(ss, { videoId: ss.trackId, audioId: ss.audioTrackId })
      // isSharingScreen gates the 'screen'/'screenAudio' publish — set it here
      // (also lets a DIRECT shareStream caller's stopSharing and the F3
      // ended-handler run the canonical cleanup).
      ctx.isSharingScreen.value = true
      if (roomId) {
        await _updatePublishedTracks(roomId)
      }

      const published = audioTrack
        ? [ss.trackId, ss.audioTrackId]
        : [ss.trackId]
      log.info('[shareStream] Stream shared successfully trackNames=%j', published)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to share stream'
      ctx.connectionError.value = msg
      log.error('[shareStream] Error:', msg)
      // review #3: an exception AFTER the transceiver allocation must not leave
      // the screen state half-set — _resetScreenShareState clears it all.
      if (ctx.isSharingScreen.value || ss.stream) {
        log.warn('[shareStream] clearing half-set share state after error: %s', msg)
        _resetScreenShareState(stream)
      }
    }
  }

  return {
    shareStream,
    muteAudio,
    toggleCamera,
    toggleScreenShare,
    stopSharing,
  }
}
