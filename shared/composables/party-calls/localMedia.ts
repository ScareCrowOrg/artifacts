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

import { _apiFetchJson, _executePartyAction } from './http'
import { _createAndSetOffer, _registerLocalTracksOnSfu, _removeTrackFromSfu } from './sfuSignaling'
import { _updateRegistryTracks } from './discovery'
import {
  log,
  state,
  _localTrackNamesByDisplay,
} from './state'
import type { TrackType, Participant } from '#artifacts/shared/stores/partyStore'
import type { Ref } from 'vue'
import type { SfuTrackResult } from './types'

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

    // Close the renegotiation (3 branches, mirror of shareStream).
    const respSd = regResult?.sessionDescription
    const respSdp = respSd?.sdp ? String(respSd.sdp) : ''
    if (regResult?.requiresImmediateRenegotiation && respSd?.type === 'offer' && respSdp.length > 0) {
      // SFU generated a fresh offer for the new track — answer it back.
      await state._pc.setRemoteDescription(new RTCSessionDescription(respSd))
      const localAnswer = await state._pc.createAnswer()
      await state._pc.setLocalDescription(localAnswer)
      await _apiFetchJson(
        `/calls/sessions/${state._currentSessionId}/renegotiate`,
        {
          method: 'PUT',
          body: JSON.stringify({
            sessionDescription: { type: localAnswer.type, sdp: localAnswer.sdp },
          }),
        },
      )
    } else if (respSd?.type === 'answer' && respSdp.length > 0) {
      await state._pc.setRemoteDescription(new RTCSessionDescription(respSd))
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
      // Only reflect the "sharing" state if the share actually started
      // (shareStream bails on a stream without a video track).  A cancelled
      // getDisplayMedia throws before this point → state unchanged.
      if (state._screenStream) {
        state._screenTrackId = stream.getVideoTracks()[0]?.id ?? null
        ctx.isSharingScreen.value = true
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
    if (!state._screenStream) return
    _stopStream(state._screenStream)
    state._screenStream = null
    if (state._pc) {
      let removedSender = false
      for (const sender of state._pc.getSenders()) {
        if (sender.track?.id === state._screenTrackId) {
          // Keep the sendonly transceiver for the next shareStream — removeTrack
          // only nulls sender.track; the transceiver/m-section survives.  A1:
          // reuse it via replaceTrack instead of stacking a new transceiver per
          // share/stop cycle (avoids the SFU's 413 accumulation error).
          const orphanTx = state._pc.getTransceivers().find((t) => t.sender === sender)
          if (orphanTx) state._orphanScreenTx = orphanTx
          // DIAG (F2): the screen transceiver's mid survives removeTrack — this
          // is the value the tracks/close contract needs (CloseTrackObject.mid).
          // F7 compares it to the target sent by _removeTrackFromSfu (both should
          // equal the same mid after the F3 fix).
          log.warn(
            '[stopSharing] DIAG detached sender screen_track=%s orphan_mid=%s orphan_direction=%s',
            sender.track?.id, orphanTx?.mid ?? 'none', orphanTx?.direction ?? 'n/a',
          )
          state._pc.removeTrack(sender)
          removedSender = true
        }
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
      // S1 (F3): expose the shared screen as the self-view source so the
      // publisher's own grid tile shows what is being shared (local preview).
      ctx.selfViewStream.value = stream
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
      // DIAG (B7): publisher identity — participantId ("typically the user's
      // id") lets F3 correlate WHO shared with the discovery enumeration to
      // label host (1st to join) vs guest (2nd) in the test.  No role check
      // exists in code — this is purely a runtime correlation marker.
      const _publisherUserId = ctx.participants.value
        .find((p) => p.sessionId === state._currentSessionId)?.participantId ?? '(unknown)'
      log.warn(
        '[DIAG][shareStream] addTransceiver sendonly session=%s userId=%s track=%s transceivers_before=%d',
        state._currentSessionId, _publisherUserId, videoTrack.id, state._pc.getTransceivers().length,
      )
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
        // DIAG (CICLO 2 L3): tracks/new now carries the publisher's offer.
        log.warn(
          '[DIAG][shareStream] tracks/new with offer session=%s track_objs=%d sdp_type=%s sdp_len=%d',
          state._currentSessionId, screenTrackObjs.length, offer.type, (offer.sdp || '').length,
        )
        regResult = await _registerLocalTracksOnSfu(
          state._pc,
          state._currentSessionId,
          screenTrackObjs,
          { type: offer.type, sdp: offer.sdp || '' },
        )
        // DIAG (CICLO 2 L4): what the SFU answered to tracks/new+offer — a
        // direct answer SDP, a renegotiation offer (requiresImmediateRenegotiation),
        // or nothing (per-track errorCode).
        log.warn(
          '[DIAG][shareStream] tracks/new response session=%s answer_type=%s answer_sdp_len=%d requires_renog=%s answer_tracks=%s',
          state._currentSessionId,
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
        await state._pc.setRemoteDescription(new RTCSessionDescription(respSd))
        const localAnswer = await state._pc.createAnswer()
        await state._pc.setLocalDescription(localAnswer)
        await _apiFetchJson(
          `/calls/sessions/${state._currentSessionId}/renegotiate`,
          {
            method: 'PUT',
            body: JSON.stringify({
              sessionDescription: { type: localAnswer.type, sdp: localAnswer.sdp },
            }),
          },
        )
      } else if (respSd?.type === 'answer' && respSdp.length > 0) {
        // Direct answer — apply as-is.
        await state._pc.setRemoteDescription(new RTCSessionDescription(respSd))
      } else if (regResult) {
        // The SFU answered without an offer/answer SDP (e.g. a per-track
        // errorCode on the new track).  Surface it for the F7 to observe —
        // do NOT apply an empty SDP.
        const trackErrors = (Array.isArray(regResult?.tracks) ? regResult.tracks : [])
          .filter((t: SfuTrackResult) => t && typeof t === 'object' && (t.errorCode || t.errorDescription))
        log.warn(
          '[DIAG][shareStream] tracks/new no offer/answer from SFU session=%s track_errors=%j',
          state._currentSessionId, trackErrors,
        )
      }

      // GAP 2: extend the room registry (upsert) so discovery returns the
      // screen in trackNames and subscribers learn about the new track.
      const roomId = ctx.getRoomId()
      const tracksDisplay: TrackType[] = [...state._publishedTracks, 'screen']
      const trackNames: string[] = [...state._publishedTrackNames, videoTrack.id]

      // Index the screen's native track so _updatePublishedTracks keeps it in
      // the published set while sharing (F2).
      const screenNames = _localTrackNamesByDisplay.get('screen') ?? []
      if (!screenNames.includes(videoTrack.id)) screenNames.push(videoTrack.id)
      _localTrackNamesByDisplay.set('screen', screenNames)

      if (roomId) {
        await _updateRegistryTracks(roomId, tracksDisplay, trackNames, ctx.remoteStreams, ctx.participants.value)
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
          roomId, state._currentSessionId, tracksDisplay, trackNames,
        )
        // REV-2 (F4 gate): send sessionId so the backend targets THIS session's
        // presence entry (REV-1 multi-session presence).
        await _executePartyAction({
          action: 'tracks_update',
          roomId,
          tracks: tracksDisplay,
          trackNames,
          sessionId: state._currentSessionId,
        })
      }

      // Persist the extended publish set for any future share/update.
      state._publishedTracks = tracksDisplay
      state._publishedTrackNames = trackNames

      log.info('[shareStream] Stream shared successfully tracks=%j trackNames=%j',
        tracksDisplay, trackNames)
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
