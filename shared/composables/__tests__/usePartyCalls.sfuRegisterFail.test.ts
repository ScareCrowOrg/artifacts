/**
 * @vitest-environment jsdom
 *
 * Unit tests for the 2nd screen-share SFU-register fix
 * (issue `party-cell-screen-share-sfu-register-fail`).
 *
 * The diagnosis (`docs/issues/party-cell-screen-share-sfu-register-fail/diagnosis/FINDINGS.md`):
 * when the 2nd participant publishes their screen while already receiving another
 * participant's screen (the SFU REUSED the base transceivers for the delivery),
 * the publish renegotiation on the SAME PC corrupts the state — ICE stuck in 'new'
 * (publish never sent → G2) or, in other environments, an SFU answer the browser
 * rejected at `setRemoteDescription` (mid='2').  The fix (CHANGE_PLAN Fase 2):
 * - 2D/a publish only on a stable/healthy PC (stable-signaling wait + terminal-ICE
 *   fail-fast);
 * - 2D/b do NOT deadlock the ICE gate on a mid-call restart (non-terminal ICE
 *   proceeds — the offer completes the restart);
 * - 2D    roll back + friendly G2 error when the browser rejects the SFU answer
 *   (no raw `mid='2'` error, PC stays recoverable);
 * - 2C    serialize renegotiations (`_withNegotiationLock`) — publish and
 *   subscribe never overlap on the shared PC;
 * - 2B    defensive codec filter VP8/H264 on the screen transceiver.
 *
 * The shared WebRTC mocks + mount harness live in `usePartyCalls.testBed.ts`.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { VueWrapper } from '@vue/test-utils'

// ── Logger mock (hoisted) — capture every warn(...) call for assertions.
const { warnCalls } = vi.hoisted(() => ({ warnCalls: [] as unknown[][] }))

vi.mock('@/utils/logger', () => ({
  createLogger: vi.fn(() => ({
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn((...args: unknown[]) => { warnCalls.push(args) }),
    error: vi.fn(),
    success: vi.fn(),
    isEnabled: vi.fn(() => false),
    getNamespace: vi.fn(() => 'test'),
  })),
}))

vi.mock('#artifacts/shared/services/apiService', () => ({
  apiFetch: vi.fn(async (path: string, options: RequestInit = {}) =>
    (globalThis as any).__mockApiFetch(path, options),
  ),
}))

vi.mock('#artifacts/shared/composables/useDistributedState', () => ({
  useDistributedState: vi.fn(() => ({})),
}))

import {
  state,
  _subscribedSessions,
  _remoteTrackTypes,
} from '../party-calls/state'
import { _subscribeToRemoteTracks } from '../party-calls/subscription'
import {
  MockMediaStreamTrack,
  MockMediaStream,
  MockRTCPeerConnection,
  jsonResp,
  mountComposable,
  setupTestBed,
} from './usePartyCalls.testBed'

let wrapper: VueWrapper

/** Base mock fetch for a room where the participant can subscribe and publish
 *  a screen successfully (the publish gets a direct answer).  Callers override
 *  the per-test branches via the returned object's counters. */
function baseFetch() {
  const counters = { publishRegCalls: 0 }
  ;(globalThis as any).__mockApiFetch = vi.fn(async (path: string, options: RequestInit = {}) => {
    const method = (options.method || 'GET').toUpperCase()
    if (path === '/calls/provision' && method === 'POST') return jsonResp({ status: 'already_exists' })
    if (path === '/calls/session' && method === 'POST') {
      return jsonResp({ sessionId: 'me', sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' } })
    }
    if (path === '/calls/rooms/room/sessions' && method === 'POST') return jsonResp({ ok: true })
    if (path === '/calls/rooms/room/sessions' && method === 'GET') return jsonResp({ sessions: [] })
    if (path === '/calls/sessions/me/tracks/new' && method === 'POST') {
      const body = JSON.parse(options.body as string)
      const track = body.tracks?.[0]
      if (track?.location === 'remote') {
        return jsonResp({
          requiresImmediateRenegotiation: true,
          sessionDescription: { type: 'offer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' },
          tracks: [{ trackName: track.trackName, mid: '1' }],
        })
      }
      if (track?.trackName === 'my-screen-id') {
        counters.publishRegCalls += 1
        return jsonResp({ sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\na=mid:2\r\n' } })
      }
      return jsonResp({ ok: true })
    }
    if (path === '/calls/sessions/me/renegotiate' && method === 'PUT') return jsonResp({ ok: true })
    if (path.includes('/heartbeat') && method === 'PUT') return jsonResp({ ok: true })
    if (path === '/api/cells/execute-ephemeral' && method === 'POST') return jsonResp({ ok: true })
    if (path.includes('/sessions/me') && method === 'DELETE') return jsonResp({ ok: true })
    throw new Error(`Unhandled mock fetch: ${method} ${path}`)
  })
  return counters
}

/** A fresh fake display stream whose video track is the native screen id. */
function fakeScreenStream(id = 'my-screen-id'): MockMediaStream {
  const stream = new MockMediaStream()
  stream.addTrack(new MockMediaStreamTrack('video', id))
  return stream
}

describe('usePartyCalls — 2nd screen share SFU-register fix (2D/2C/2B)', () => {
  beforeEach(() => {
    setupTestBed()
    warnCalls.length = 0
  })

  afterEach(() => {
    if (wrapper) {
      try { (wrapper.vm as any).hangUp?.() } catch { /* teardown best-effort */ }
      wrapper.unmount()
      wrapper = undefined as unknown as VueWrapper
    }
  })

  it('D1: a 2nd publisher that already receives another participant\'s screen (SFU reused the base mids) registers its OWN screen — no conflicting mid, no wedged PC', async () => {
    // The diagnosed state of the 2nd participant: the SFU delivered the 1st
    // participant's screen by REUSING the base transceivers (mids 0/1 — the
    // subscribe offer had only those two, both a=sendonly from the SFU).  When
    // this participant publishes its own screen, the NEW sendonly transceiver
    // must get its own mid and the registration must complete — before the fix
    // this was the exact state that corrupted ICE / made Chrome reject the
    // answer (`mid='2'`).
    const counters = baseFetch()
    _remoteTrackTypes.set('guest', new Map([['screen-native', 'screen']]))

    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')

    // 1. The 2nd participant receives the 1st's screen (subscribe renegotiation).
    await _subscribeToRemoteTracks(
      { sessionId: 'guest', tracks: ['screen'], trackNames: ['screen-native'] },
      api.remoteStreams,
    )
    expect(_subscribedSessions.has('guest')).toBe(true)
    // Only the base transceivers exist — the SFU reused them (H1), no new mid.
    expect((state._pc as any).getTransceivers().length).toBe(2)

    // 2. Publish the participant's OWN screen.
    await api.shareStream(fakeScreenStream())

    // 3. Registered on the SFU + published to registry/presence + PC healthy.
    expect(counters.publishRegCalls).toBe(1)
    expect(api.isSharingScreen).toBe(true)
    expect(state._publishedTracks).toContain('screen')
    expect((state._pc as any).signalingState).toBe('stable') // NOT wedged
    // The publish transceiver got its own mid — NOT the receive video mid '1'.
    const screenTx = (state._pc as any).getTransceivers().find((t: any) => t.sender?.track?.id === 'my-screen-id')
    expect(screenTx).toBeDefined()
    expect(screenTx.mid).not.toBe('1')
    // No rollback was applied (localDescription is the offer, not a rollback).
    expect((state._pc as any).localDescription.type).not.toBe('rollback')
  })

  it('D2: a publish that starts while a subscribe renegotiation is in flight WAITS for signalingState === \'stable\' before creating its offer', async () => {
    // 2D/a — serialize: the publish offer must never be built while a subscribe
    // renegotiation is mid-flight on the same PC (creating an offer then throws
    // InvalidStateError and wedges the PC).
    class GatedSignalingPC extends MockRTCPeerConnection {
      createOfferCalls = 0
      async createOffer(): Promise<{ type: string; sdp: string }> {
        this.createOfferCalls += 1
        return super.createOffer()
      }
    }
    ;(globalThis as any).RTCPeerConnection = GatedSignalingPC
    baseFetch()

    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')
    const offersAfterStart = (state._pc as any).createOfferCalls

    // Simulate a subscribe renegotiation that just applied the SFU's offer but
    // has not answered yet (the exact overlap the diagnosis identified).
    ;(state._pc as any).signalingState = 'have-remote-offer'

    const sharePromise = api.shareStream(fakeScreenStream())
    // Give shareStream a tick to reach the stable-signaling wait.
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect((state._pc as any).createOfferCalls).toBe(offersAfterStart) // NOT offered yet — waiting

    // The concurrent subscribe settles → signaling becomes stable → publish proceeds.
    ;(state._pc as any).signalingState = 'stable'
    await sharePromise

    expect((state._pc as any).createOfferCalls).toBe(offersAfterStart + 1) // exactly ONE publish offer
    expect(api.isSharingScreen).toBe(true)
  })

  it('D3: the screen transceiver offer drops only the codec-artifact families (H265 + rtx) — VP8/VP9/AV1/H264 quality codecs are preserved (F5 review #3078)', async () => {
    // Browser advertises a full codec set incl. the H265 family that surfaces
    // the malformed `rtx 50 (apt=49)` in the SFU answer.  F5 (review #3078):
    // H2 was DISCARDED as the root cause, so the 2B filter is purely defensive
    // and must PRESERVE VP9/AV1 (Chrome quality codecs) while dropping H265 and
    // the rtx/FEC baggage.
    ;(globalThis as any).RTCRtpSender = {
      getCapabilities: vi.fn((kind: string) => ({
        codecs: [
          { mimeType: 'video/VP8' },
          { mimeType: 'video/rtx' },
          { mimeType: 'video/VP9' },
          { mimeType: 'video/H264' },
          { mimeType: 'video/H265' },
          { mimeType: 'video/AV1' },
        ],
      })),
    }
    const counters = baseFetch()

    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')
    await api.shareStream(fakeScreenStream())

    const screenTx = (state._pc as any).getTransceivers().find((t: any) => t.sender?.track?.id === 'my-screen-id')
    expect(screenTx).toBeDefined()
    expect(screenTx.setCodecPreferences).toHaveBeenCalled()
    const offered = screenTx.codecPreferences.map((c: { mimeType: string }) => c.mimeType)
    expect(offered).toContain('video/VP8')
    expect(offered).toContain('video/VP9')
    expect(offered).toContain('video/AV1')
    expect(offered).toContain('video/H264')
    expect(offered).not.toContain('video/H265') // codec-artifact family dropped
    expect(offered).not.toContain('video/rtx')  // rtx dropped with its codec
    expect(counters.publishRegCalls).toBe(1) // the filtered offer still registered

    delete (globalThis as any).RTCRtpSender // don't leak the global into later tests
  })

  it('D4: an SFU answer the browser REJECTS (the diagnosed mid=\'2\' send-parameters error) rolls back and surfaces the friendly G2 error — the PC stays recoverable', async () => {
    // Surface B from the diagnosis: Chrome threw "Failed to set remote video
    // description send parameters for m-section with mid='2'" applying the SFU's
    // answer at setRemoteDescription.  Before the fix this propagated as a raw
    // error and left the PC in have-local-offer.  Now it rolls back (PC stable,
    // recoverable) and returns false → the friendly G2 message.
    class RejectingAnswerPC extends MockRTCPeerConnection {
      async setRemoteDescription(desc: { type?: string; sdp?: string }): Promise<void> {
        if (desc?.type === 'answer' && /a=mid:2/.test(desc.sdp || '')) {
          throw new Error("Failed to set remote video description send parameters for m-section with mid='2'")
        }
        return super.setRemoteDescription(desc)
      }
    }
    ;(globalThis as any).RTCPeerConnection = RejectingAnswerPC
    baseFetch()

    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')
    await api.shareStream(fakeScreenStream())

    // Friendly G2 error — NOT the raw setRemoteDescription message.
    expect(api.connectionError).toContain('Could not start screen share')
    expect(api.connectionError).not.toContain('send parameters')
    // PC rolled back to stable (not wedged in have-local-offer) → a retry works.
    expect((state._pc as any).signalingState).toBe('stable')
    expect((state._pc as any).localDescription.type).toBe('rollback')
    // Share state reverted so the user can retry cleanly.
    expect(api.isSharingScreen).toBe(false)
    expect(state._screenStream).toBeNull()
    // The sendonly transceiver was detached and restored as the orphan (R#3
    // reuse) — the next share does NOT stack a new transceiver.
    expect(state._orphanScreenTx?.sender.track).toBeNull()
  })

  it('D5: ICE stuck in \'new\' after a renegotiation no longer deadlocks the publish — a recovery within the grace is detected and the tracks/new POST is sent', async () => {
    // Surface A from the diagnosis: ICE reset to 'new' after the subscribe
    // renegotiation and never recovered, so _waitForIceConnected timed out (10s)
    // and the publish was NEVER sent.  The gate now fails fast on TERMINAL ICE
    // only; 'new'/'connecting' gets a short grace during which a recovery is
    // detected (the offer about to be sent is what completes the restart).
    let iceListener: (() => void) | null = null
    class IceRecoverPC extends MockRTCPeerConnection {
      addEventListener(type?: string, listener?: () => void): void {
        if (type === 'iceconnectionstatechange' && listener) iceListener = listener
      }
      removeEventListener(): void { iceListener = null }
    }
    ;(globalThis as any).RTCPeerConnection = IceRecoverPC
    const counters = baseFetch()

    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')

    // The diagnosed corrupted baseline: ICE was reset to 'new' and did not
    // reconnect.  Simulate it recovering shortly after the publish starts (the
    // ICE restart completing).
    // F4 (review #3078): this PC WAS connected before the restart — the 2D/b
    // gate treats 'new' as a mid-call restart (short grace then send) rather
    // than an initial connection.
    state._iceWasEverConnected = true
    ;(state._pc as any).iceConnectionState = 'new'
    setTimeout(() => {
      if (iceListener) {
        ;(state._pc as any).iceConnectionState = 'connected'
        iceListener()
      }
    }, 10)

    await api.shareStream(fakeScreenStream())
    expect(counters.publishRegCalls).toBe(1) // the POST was sent — no deadlock
    expect(api.isSharingScreen).toBe(true)
    // The gate did NOT hard-abort on the transient 'new' state (the recovery was
    // detected within the grace) — no terminal-ICE abort log.
    const abortLog = warnCalls.find((args) =>
      args.some((a) => typeof a === 'string' && a.includes('ICE in terminal state')))
    expect(abortLog).toBeUndefined()
  })

  it('D6: an SFU RENEGOTIATION OFFER the browser rejects rolls back and surfaces the friendly G2 error — the PC stays recoverable (F1 review #3078, Blocker)', async () => {
    // F1 (review #3078, Blocker): the _closeLocalRenegotiation branch `offer`
    // (requiresImmediateRenegotiation + SFU offer) was NOT rollback-protected —
    // a browser rejecting the SFU offer at setRemoteDescription escaped, wedged
    // the PC in have-local-offer and surfaced a raw error.  It now rolls back
    // (PC stable, recoverable) and returns false → the friendly G2 message,
    // exactly like the direct-answer branch.
    class RejectingOfferPC extends MockRTCPeerConnection {
      async setRemoteDescription(desc: { type?: string; sdp?: string }): Promise<void> {
        if (desc?.type === 'offer' && /a=mid:2/.test(desc.sdp || '')) {
          throw new Error("Failed to set remote video description send parameters for m-section with mid='2'")
        }
        return super.setRemoteDescription(desc)
      }
    }
    ;(globalThis as any).RTCPeerConnection = RejectingOfferPC
    // The SFU answers the publish tracks/new with a RENEGOTIATION OFFER (not a
    // direct answer) — the branch F1 protects.
    let tracksNewCount = 0
    ;(globalThis as any).__mockApiFetch = vi.fn(async (path: string, options: RequestInit = {}) => {
      const method = (options.method || 'GET').toUpperCase()
      if (path === '/calls/provision' && method === 'POST') return jsonResp({ status: 'already_exists' })
      if (path === '/calls/session' && method === 'POST') {
        return jsonResp({ sessionId: 'me', sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' } })
      }
      if (path === '/calls/rooms/room/sessions' && method === 'POST') return jsonResp({ ok: true })
      if (path === '/calls/rooms/room/sessions' && method === 'GET') return jsonResp({ sessions: [] })
      if (path === '/calls/sessions/me/tracks/new' && method === 'POST') {
        const body = JSON.parse(options.body as string)
        const track = body.tracks?.[0]
        if (track?.location === 'remote') {
          return jsonResp({
            requiresImmediateRenegotiation: true,
            sessionDescription: { type: 'offer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' },
            tracks: [{ trackName: track.trackName, mid: '1' }],
          })
        }
        if (track?.trackName === 'my-screen-id') {
          tracksNewCount += 1
          // requiresImmediateRenegotiation + an SFU OFFER — the F1 branch.
          return jsonResp({
            requiresImmediateRenegotiation: true,
            sessionDescription: { type: 'offer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\na=mid:2\r\n' },
            tracks: [{ trackName: 'my-screen-id', mid: '2' }],
          })
        }
        return jsonResp({ ok: true })
      }
      if (path === '/calls/sessions/me/renegotiate' && method === 'PUT') return jsonResp({ ok: true })
      if (path.includes('/heartbeat') && method === 'PUT') return jsonResp({ ok: true })
      if (path === '/api/cells/execute-ephemeral' && method === 'POST') return jsonResp({ ok: true })
      if (path.includes('/sessions/me') && method === 'DELETE') return jsonResp({ ok: true })
      throw new Error(`Unhandled mock fetch: ${method} ${path}`)
    })

    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')
    await api.shareStream(fakeScreenStream())

    // Friendly G2 error — NOT the raw setRemoteDescription message.
    expect(api.connectionError).toContain('Could not start screen share')
    expect(api.connectionError).not.toContain('send parameters')
    // PC rolled back to stable (not wedged in have-local-offer) → a retry works.
    expect((state._pc as any).signalingState).toBe('stable')
    expect((state._pc as any).localDescription.type).toBe('rollback')
    // Share state reverted + the sendonly transceiver detached (R#3 reuse).
    expect(api.isSharingScreen).toBe(false)
    expect(state._screenStream).toBeNull()
    expect(state._orphanScreenTx?.sender.track).toBeNull()
    expect(tracksNewCount).toBe(1) // the publish reached the SFU
  })
})
