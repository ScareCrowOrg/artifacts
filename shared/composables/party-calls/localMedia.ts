/**
 * @file party-calls/localMedia.ts
 * @description Local media actions for the usePartyCalls composable (Cloudflare
 * Calls / WebRTC): opt-in mic/camera capture (Caso B), screen sharing / publish
 * and stop, and the published-track-set recompute.  Extracted VERBATIM from the
 * former monolithic ``usePartyCalls.ts`` (shell section) — the CHANGE_PLAN
 * accepted merging the planned ``localMedia.ts`` + ``publish.ts`` into ONE
 * module (~500 lines, still < 650) because ``_updatePublishedTracks`` is shared
 * by both and a split would create an import cycle.
 *
 * Extraction adjustment: the functions closed over the shell's reactive refs, so
 * they are wrapped in a factory ``createLocalMediaActions(ctx)`` that receives a
 * typed ``LocalMediaContext`` (the refs the old closure captured).  Module-level
 * state (``state._pc``, ``state._localStream``, ``_localTrackNamesByDisplay``, …) still
 * comes from ``./state``.
 *
 * Dependency graph: imports ``_apiFetchJson``/``_executePartyAction`` from
 * ``./http``, ``_createAndSetOffer``/``_registerLocalTracksOnSfu``/
 * ``_removeTrackFromSfu`` from ``./sfuSignaling``, ``_updateRegistryTracks``
 * from ``./discovery`` + state from ``./state``.  No reverse imports.
 * See ``party-calls/README.md``.
 */

import { _executePartyAction } from './http'
import {
  _createAndSetOffer,
  _registerLocalTracksOnSfu,
  _removeTrackFromSfu,
  _closeLocalRenegotiation,
} from './sfuSignaling'
import { _updateRegistryTracks } from './discovery'
import {
  log,
  state,
  _localTrackNamesByDisplay,
} from './state'
import type { TrackType, Participant } from '#artifacts/shared/stores/partyStore'
import type { Ref } from 'vue'

// ─────────────────────────────────────────────────────────────────────────────
// Local media / publish context
// ─────────────────────────────────────────────────────────────────────────────

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
 * Each returned action closes over ``ctx`` (the reactive refs) and the
 * module-level state in ``./state`` — behaviour identical to the original
 * monolithic shell closures.
 */
export function createLocalMediaActions(ctx: LocalMediaContext) {
  /**
   * Enable a local track (mic/camera) on demand — the media opt-in for Caso B.
   *
   * Called by the toggles on their FIRST click (when no track is captured yet).
   * The permission prompt appears only HERE, never on join.  The flow mirrors
   * the proven shareStream mid-call pattern:
   *   getUserMedia(kind) → merge into state._localStream → replaceTrack on the
   *   matching recvonly transceiver + direction='sendrecv' → renegotiate
   *   (offer → tracks/new location:'local' with sessionDescription → answer)
   *   → index the native track name → republish registry + presence with the
   *   REAL track set.
   *
   * On permission denied the state is UNCHANGED — only a log + early return,
   * so the toggle never flips to "on" (edge case of the ISSUE).
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
    const offer = await _createAndSetOffer(state._pc)
    const trackObjs = [{
      location: 'local' as const,
      mid: tx.mid as string,
      trackName: track.id,
    }]
    let regResult: any = null
    if (trackObjs.length) {
      regResult = await _registerLocalTracksOnSfu(
        state._pc,
        state._currentSessionId,
        trackObjs,
        { type: offer.type, sdp: offer.sdp || '' },
      )
    }

    // Close the renegotiation (F9: single helper — offer → answer, direct
    // answer → apply, null → roll back so the PC is not wedged in
    // have-local-offer).
    const closed = await _closeLocalRenegotiation(regResult)
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
      if (display === 'camera' && !ctx.cameraEnabled.value) continue
      if (display === 'screen' && !ctx.isSharingScreen.value) continue
      tracks.push(display)
      trackNames.push(...names)
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
   *  opt-in — no camera track captured yet → acquire + publish).  Independent
   *  of mic/screen (F2). */
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
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: false,
      })
      await shareStream(stream)
      // F6/F10: shareStream now populates state._screenTrackId and flips
      // isSharingScreen itself on success, and reverts them on failure — nothing
      // to reflect here.  A cancelled getDisplayMedia throws before this point →
      // state unchanged.
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
    if (!state._screenStream) return
    _stopStream(state._screenStream)
    state._screenStream = null
    if (state._pc) {
      const pc = state._pc
      let removedSender = false
      // F6 FIX (bug-hardening): match the screen sender.  Primary: the native
      // track id (state._screenTrackId — now populated by shareStream so a
      // DIRECT caller like glb-content-viewer is covered).  Fallback when the id
      // is null: a dedicated SENDONLY video transceiver (the camera is sendrecv,
      // so a sendonly video sender is unambiguously the screen) — prevents the
      // share/stop cycle from stacking a transceiver when the id was never set.
      const matchedSender = pc.getSenders().find((s) => s.track?.id === state._screenTrackId)
        ?? (state._screenTrackId === null
          ? pc.getSenders().find((s) => s.track?.kind === 'video'
              && pc.getTransceivers().find((t) => t.sender === s)?.direction === 'sendonly')
          : undefined)
      if (matchedSender) {
        // Keep the sendonly transceiver for the next shareStream — removeTrack
        // only nulls sender.track; the transceiver/m-section survives.  A1:
        // reuse it via replaceTrack instead of stacking a new transceiver per
        // share/stop cycle (avoids the SFU's 413 accumulation error).
        const orphanTx = pc.getTransceivers().find((t) => t.sender === matchedSender)
        if (orphanTx) state._orphanScreenTx = orphanTx
        pc.removeTrack(matchedSender)
        removedSender = true
      }
      // Tell the SFU the track is gone — replaces the renegotiate-with-offer
      // path, which the Cloudflare contract rejects (406 "answer is expected" →
      // 502 on every stop).  Non-fatal: on failure the SFU reaper still signals
      // event=ended to already-subscribed peers.  The tracks/close contract
      // identifies the track by the transceiver mid (which survives removeTrack)
      // — NOT the native state._screenTrackId (which only locates the local sender
      // above; the mid is the value the Cloudflare CloseTrackObject requires).
      if (removedSender && state._orphanScreenTx?.mid) {
        await _removeTrackFromSfu(state._orphanScreenTx.mid)
      } else if (removedSender) {
        log.warn(
          '[stopSharing] cannot remove screen track from SFU — no orphan transceiver mid available',
        )
      }
    }
    state._screenTrackId = null
    ctx.isSharingScreen.value = false
    // S1 (F3): swap the self-view back to the camera when sharing stops.
    ctx.selfViewStream.value = ctx.localStream.value
    _localTrackNamesByDisplay.delete('screen')
    const roomId = ctx.getRoomId()
    if (roomId) void _updatePublishedTracks(roomId)
    log.info('[stopSharing] Screen share stopped')
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
    if (!state._pc) {
      ctx.connectionError.value = 'Not connected — start a call first'
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
      state._screenStream = stream
      // F6 FIX (bug-hardening): populate _screenTrackId HERE (it was only set in
      // toggleScreenShare) so a DIRECT shareStream caller (glb-content-viewer,
      // no toggleScreenShare) still lets stopSharing match the sender and run
      // _removeTrackFromSfu instead of stacking a transceiver per share.
      state._screenTrackId = videoTrack.id
      // S1 (F3): expose the shared screen as the self-view source so the
      // publisher's own grid tile shows what is being shared (local preview).
      ctx.selfViewStream.value = stream
      // F3 FIX (bug-hardening): the browser's NATIVE "Stop sharing" ends the
      // display track — run the same cleanup as stopSharing so isSharingScreen,
      // the registry/presence, the self-view and the SFU registration all stay
      // consistent (previously the share stayed stale: isSharingScreen true,
      // registry advertising a dead track, subscribers stuck on a black tile).
      videoTrack.addEventListener('ended', () => {
        if (state._screenStream) void stopSharing()
      })
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
      //   1. state._orphanScreenTx — explicitly captured by stopSharing (sender.track
      //      nulled by removeTrack but the transceiver kept).
      //   2. any sendonly transceiver with sender.track === null (pre-issue
      //      fallback for peers that stopped sharing before this fix).
      // Force direction back to 'sendonly' before replaceTrack — the direction
      // was re-negotiated away from 'sendonly' by the previous offer, so the old
      // direction-only search silently missed and stacked a new transceiver
      // (transceivers 5→6 in F7 → 413 risk).
      let screenTx: RTCRtpTransceiver | null = null
      if (state._orphanScreenTx?.sender) {
        screenTx = state._orphanScreenTx
        state._orphanScreenTx = null
      } else {
        screenTx = state._pc.getTransceivers().find(
          (t) => t.direction === 'sendonly' && t.sender && t.sender.track === null,
        ) ?? null
      }
      if (screenTx?.sender) {
        try {
          screenTx.direction = 'sendonly'
        } catch { /* ignore — non-mutating on some browsers */ }
        await screenTx.sender.replaceTrack(videoTrack)
      } else {
        state._pc.addTransceiver(videoTrack, { direction: 'sendonly' })
      }

      if (!state._currentSessionId) {
        log.warn('[shareStream] No current session — cannot negotiate')
        return
      }

      // Build the offer so the new transceiver gets its mid and the renegotiation
      // SDP carries the new m= video section.
      const offer = await state._pc.createOffer()
      await state._pc.setLocalDescription(offer)

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
      const screenTrackObjs = state._pc.getTransceivers()
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
          state._currentSessionId,
        )
      }
      if (screenTrackObjs.length) {
        regResult = await _registerLocalTracksOnSfu(
          state._pc,
          state._currentSessionId,
          screenTrackObjs,
          { type: offer.type, sdp: offer.sdp || '' },
        )
      }

      // Close the publisher renegotiation (F9 single helper — offer → answer,
      // direct answer → apply, null → roll back so the PC is not wedged in
      // have-local-offer).
      const closed = await _closeLocalRenegotiation(regResult)
      if (!closed) {
        // G2 FIX (bug-hardening): the screen track was NOT registered on the
        // SFU (regResult null / per-track error).  The local offer was already
        // rolled back by the helper; clean up the share state and do NOT
        // publish 'screen' to the registry/presence — subscribers would get
        // not_found_track_error forever while the self-view showed a share that
        // never reached anyone.
        log.warn('[shareStream] SFU registration failed — screen track NOT shared')
        // R#3 (review #3077): detach the sendonly transceiver from the stopped
        // track and restore it as the ORPHAN so the NEXT shareStream reuses it
        // (sender.track === null → replaceTrack) instead of stacking a new
        // transceiver per failed share — mirror of the _enableLocalTrack G2
        // branch.  Without this, repeated share-fail cycles accumulate
        // m-sections → the SFU's 413 error that the A1 orphan-reuse exists to
        // prevent.  Looked up by sender.track because `screenTx` above is null
        // when a NEW transceiver was created via addTransceiver.
        const _failedScreenTx = state._pc?.getTransceivers().find((t) => t.sender?.track === videoTrack) ?? null
        if (_failedScreenTx?.sender) {
          try { await _failedScreenTx.sender.replaceTrack(null) } catch { /* ignore — PC rolled back to stable */ }
          state._orphanScreenTx = _failedScreenTx
        }
        _stopStream(stream)
        state._screenStream = null
        state._screenTrackId = null
        ctx.selfViewStream.value = ctx.localStream.value
        ctx.isSharingScreen.value = false
        ctx.connectionError.value = 'Could not start screen share — media registration with the SFU failed. Please try again.'
        return
      }

      // F10 FIX (bug-hardening): single writer — index the screen's native track
      // and let _updatePublishedTracks compute the REAL published set + registry
      // + presence (this hand-rolled append was a SECOND writer of the
      // _publishedTracks set and could drift from the canonical function).
      const roomId = ctx.getRoomId()
      const screenNames = _localTrackNamesByDisplay.get('screen') ?? []
      if (!screenNames.includes(videoTrack.id)) screenNames.push(videoTrack.id)
      _localTrackNamesByDisplay.set('screen', screenNames)
      // _updatePublishedTracks publishes 'screen' only while isSharingScreen is
      // true — set it here (also lets a DIRECT shareStream caller's stopSharing
      // and the F3 ended-handler run the canonical cleanup).
      ctx.isSharingScreen.value = true
      if (roomId) {
        await _updatePublishedTracks(roomId)
      }

      log.info('[shareStream] Stream shared successfully trackNames=%j', screenNames)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to share stream'
      ctx.connectionError.value = msg
      log.error('[shareStream] Error:', msg)
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
