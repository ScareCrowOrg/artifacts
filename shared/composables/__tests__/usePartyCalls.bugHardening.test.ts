/**
 * @vitest-environment jsdom
 *
 * Bug-hardening tests for usePartyCalls (issue `party-calls-bug-hardening`) —
 * G1/F1–F11.  Each fix is exercised against the REAL composable with the shared
 * WebRTC mocks + mount harness from `usePartyCalls.testBed.ts` (extracted so no
 * test file exceeds RULESET 1.1's >1000-line blocker).
 *
 * The G1/G4/F1/F2/F7 tests drive the raw subscribe/discovery modules directly
 * for DETERMINISTIC race control (an in-flight subscribe needs a delayed
 * renegotiate PUT that the facade cannot orchestrate via sequential awaits).
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
  _pendingSubscribeMids,
  _pendingSubscribeTimers,
  _subscribedSessions,
  _remoteMidToTrackName,
  _remoteTrackTypes,
  _localTrackNamesByDisplay,
} from '../party-calls/state'
import { _subscribeToRemoteTracks } from '../party-calls/subscription'
import { _refreshDiscovery } from '../party-calls/discovery'
import { _pollProvisionTask } from '../party-calls/http'
import { _closeLocalRenegotiation } from '../party-calls/sfuSignaling'
import type { RemoteSession } from '../party-calls/types'
import {
  MockMediaStreamTrack,
  MockMediaStream,
  MockTransceiver,
  MockRTCPeerConnection,
  jsonResp,
  errResp,
  mountComposable,
  setupTestBed,
} from './usePartyCalls.testBed'

let wrapper: VueWrapper

describe('usePartyCalls — bug hardening (G1, G2, F1-F11)', () => {
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

  it('G1: keeps the pending protection armed until the subscribe confirms — a stale prune in the ontrack→confirm gap cannot drop the just-subscribed session or its tile', async () => {
    // G1 moved the pending release from the ontrack to AFTER _subscribedSessions.add
    // (the ontrack fires BEFORE the PUT /renegotiate round-trip, so releasing it
    // there re-opened the race).  This test drives the real subscribe with a
    // DELAYED renegotiate PUT — the subscription stays IN FLIGHT (mid pending)
    // after the screen ontrack has fired — and proves a concurrent STALE
    // discovery prune is blocked (owner mappings AND the just-arrived tile
    // survive), then the pending is released once the subscribe confirms.
    let gateScreenRenegotiate = false
    let resolveScreenRenegotiate: () => void = () => {}
    const screenRenegotiateGate = new Promise<void>((resolve) => { resolveScreenRenegotiate = resolve })

    const camSession: RemoteSession = { sessionId: 'guest', tracks: ['camera'], trackNames: ['cam-native'] }
    const guestWithScreen: RemoteSession = {
      sessionId: 'guest',
      tracks: ['camera', 'screen'],
      trackNames: ['cam-native', 'screen-native'],
    }
    ;(globalThis as any).__mockApiFetch = vi.fn(async (path: string, options: RequestInit = {}) => {
      const method = (options.method || 'GET').toUpperCase()
      if (path === '/calls/provision' && method === 'POST') return jsonResp({ status: 'already_exists' })
      if (path === '/calls/session' && method === 'POST') {
        return jsonResp({ sessionId: 'me', sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' } })
      }
      if (path === '/calls/rooms/room/sessions' && method === 'POST') return jsonResp({ ok: true })
      if (path === '/calls/rooms/room/sessions' && method === 'GET') {
        // startCall's register-discovery sees no remotes; the stale prune below
        // is driven EXPLICITLY with an empty snapshot (guest absent).
        return jsonResp({ sessions: [] })
      }
      if (path === '/calls/sessions/me/tracks/new' && method === 'POST') {
        const body = JSON.parse(options.body as string)
        const trackName = body.tracks?.[0]?.trackName
        if (trackName === 'screen-native') {
          gateScreenRenegotiate = true
          return jsonResp({
            requiresImmediateRenegotiation: true,
            sessionDescription: { type: 'offer', sdp: 'v=0\r\na=mid:1\r\na=mid:2\r\n' },
            tracks: [{ trackName: 'screen-native', mid: '2' }],
          })
        }
        return jsonResp({
          requiresImmediateRenegotiation: true,
          sessionDescription: { type: 'offer', sdp: 'v=0\r\na=mid:1\r\n' },
          tracks: [{ trackName: 'cam-native', mid: '1' }],
        })
      }
      if (path === '/calls/sessions/me/renegotiate' && method === 'PUT') {
        // Gate ONLY the screen subscribe's renegotiate round-trip.
        if (gateScreenRenegotiate) return screenRenegotiateGate.then(() => jsonResp({ ok: true }))
        return jsonResp({ ok: true })
      }
      if (path.includes('/heartbeat') && method === 'PUT') return jsonResp({ ok: true })
      if (path === '/api/cells/execute-ephemeral' && method === 'POST') return jsonResp({ ok: true })
      if (path.includes('/sessions/me') && method === 'DELETE') return jsonResp({ ok: true })
      throw new Error(`Unhandled mock fetch: ${method} ${path}`)
    })

    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')

    // Pre-populate what a discovery pass would have learned: the guest's native
    // track names map to their display types (lets the screen ontrack resolve to
    // the dedicated {guest}/screen tile).
    _remoteTrackTypes.set('guest', new Map([
      ['cam-native', 'camera'],
      ['screen-native', 'screen'],
    ]))

    // 1. Pre-subscribe the guest's camera so 'guest' is in _subscribedSessions —
    //    a stale prune only targets sessions already in _subscribedSessions.
    await _subscribeToRemoteTracks(camSession, api.remoteStreams)
    expect(_subscribedSessions.has('guest')).toBe(true)
    expect(_pendingSubscribeMids.size).toBe(0)

    // 2. The guest adds its screen — subscribe the DELTA (['screen-native']).
    //    The base mock fires the screen ontrack SYNCHRONOUSLY inside
    //    setRemoteDescription (new mid '2' transceiver), but the renegotiate PUT
    //    stays IN FLIGHT (gate held) → the subscribe has NOT confirmed yet →
    //    mid '2' stays PENDING.  The tile has already landed (ontrack fired).
    const screenSubscribe = _subscribeToRemoteTracks(guestWithScreen, api.remoteStreams)
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(_pendingSubscribeMids.has('2')).toBe(true)           // protection armed
    expect(api.remoteStreams.has('guest/screen')).toBe(true)    // tile landed

    // 3. A concurrent STALE discovery (guest absent) prunes while the subscribe
    //    is still in flight — G1 must block the owner prune AND keep the tile.
    await _refreshDiscovery('room', api.remoteStreams, [], 'stale')
    const protectLog = warnCalls.find((args) =>
      args.some((a) => typeof a === 'string' && a.includes('[pending] protect')))
    expect(protectLog).toBeDefined()
    expect(protectLog![0]).toContain('prune=owner') // the owner prune was deferred
    expect(_subscribedSessions.has('guest')).toBe(true)      // session not dropped
    expect(_remoteMidToTrackName.has('2')).toBe(true)        // screen mapping survived
    expect(api.remoteStreams.has('guest/screen')).toBe(true) // tile NOT dropped (G1)

    // 4. The renegotiate resolves → subscribe confirms → pending released.
    resolveScreenRenegotiate()
    await screenSubscribe
    expect(_pendingSubscribeMids.size).toBe(0)
    const clearedLog = warnCalls.find((args) =>
      args[1] === '2' && args.some((a) => typeof a === 'string'
        && a.includes('[pending] cleared after subscribe confirmed')))
    expect(clearedLog).toBeDefined()
    expect(clearedLog![1]).toBe('2') // mid 2 released
    expect(_subscribedSessions.has('guest')).toBe(true)
  })

  it('G2: when the SFU registration fails (regResult null), the local offer is rolled back and the track is NOT published to registry/presence', async () => {
    let registryPostCount = 0
    let tracksUpdateCount = 0
    ;(globalThis as any).__mockApiFetch = vi.fn(async (path: string, options: RequestInit = {}) => {
      const method = (options.method || 'GET').toUpperCase()
      if (path === '/calls/provision' && method === 'POST') return jsonResp({ status: 'already_exists' })
      if (path === '/calls/session' && method === 'POST') {
        return jsonResp({ sessionId: 'me', sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' } })
      }
      if (path === '/calls/rooms/room/sessions' && method === 'POST') { registryPostCount += 1; return jsonResp({ ok: true }) }
      if (path === '/calls/rooms/room/sessions' && method === 'GET') return jsonResp({ sessions: [] })
      if (path === '/calls/sessions/me/tracks/new' && method === 'POST') {
        // Simulate the SFU tracks/new failing (ICE blip) → _registerLocalTracksOnSfu
        // catches and returns null.
        throw new Error('simulated SFU tracks/new failure')
      }
      if (path === '/calls/sessions/me/renegotiate' && method === 'PUT') return jsonResp({ ok: true })
      if (path.includes('/heartbeat') && method === 'PUT') return jsonResp({ ok: true })
      if (path === '/api/cells/execute-ephemeral' && method === 'POST') {
        const body = JSON.parse(options.body as string)
        if (body.input_data?.action === 'tracks_update') tracksUpdateCount += 1
        return jsonResp({ ok: true })
      }
      if (path.includes('/sessions/me') && method === 'DELETE') return jsonResp({ ok: true })
      throw new Error(`Unhandled mock fetch: ${method} ${path}`)
    })
    // Fake camera stream for the Caso B media opt-in.
    const fakeCam = new MockMediaStream()
    fakeCam.addTrack(new MockMediaStreamTrack('video', 'cam-native-id'))
    Object.defineProperty(navigator, 'mediaDevices', {
      value: { getUserMedia: vi.fn(async () => fakeCam) },
      configurable: true,
    })

    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')
    expect(registryPostCount).toBe(1) // only startCall's register

    await api.toggleCamera() // Caso B opt-in → _enableLocalTrack('camera') → SFU register FAILS

    // 1. PC is NOT wedged: the local offer was rolled back to 'stable'.
    expect((state._pc as any).localDescription.type).toBe('rollback')
    // 2. Descriptive connectionError surfaced.
    expect(api.connectionError).toContain('Could not enable camera')
    // 3. Enable state reverted → the toggle shows off, no local media leaked.
    expect(api.cameraEnabled).toBe(false)
    expect(api.localStream).toBeNull()
    // 4. Registry/presence did NOT announce the unregistered track.
    expect(registryPostCount).toBe(1)
    expect(tracksUpdateCount).toBe(0)
  })

  it('F1: a non-screen (camera) track that arrives ALREADY ended is genuinely dead — the tile is NOT added and the mapping/transceiver are cleaned up', async () => {
    class EndedCameraPC extends MockRTCPeerConnection {
      async setRemoteDescription(desc: { type?: string; sdp?: string }): Promise<void> {
        this.remoteDescription = desc
        const mids = [...(desc.sdp || '').matchAll(/a=mid:(\S+)/g)].map((m) => m[1])
        for (const mid of mids) {
          let tx = this.transceivers.find((t) => t.mid === mid)
          if (!tx) { tx = new MockTransceiver(mid, 'recvonly'); this.transceivers.push(tx) }
        }
        // The subscription offer fires the CAMERA ontrack (mid '1') with an
        // ALREADY-ended track — the F1 dead non-screen case.
        if (desc.type === 'offer' && mids.includes('1')) {
          const camTx = this.transceivers.find((t) => t.mid === '1')
          if (camTx) {
            const deadTrack = new MockMediaStreamTrack('video', 'dead-cam')
            deadTrack.readyState = 'ended'
            const deadStream = new MockMediaStream()
            deadStream.addTrack(deadTrack)
            this.ontrack?.({
              track: deadTrack,
              receiver: { track: { readyState: 'ended', muted: false } },
              transceiver: camTx,
              streams: [deadStream],
            })
          }
        }
      }
    }
    ;(globalThis as any).RTCPeerConnection = EndedCameraPC

    const camSession: RemoteSession = { sessionId: 'guest', tracks: ['camera'], trackNames: ['cam-native'] }
    ;(globalThis as any).__mockApiFetch = vi.fn(async (path: string, options: RequestInit = {}) => {
      const method = (options.method || 'GET').toUpperCase()
      if (path === '/calls/provision' && method === 'POST') return jsonResp({ status: 'already_exists' })
      if (path === '/calls/session' && method === 'POST') {
        return jsonResp({ sessionId: 'me', sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' } })
      }
      if (path === '/calls/rooms/room/sessions' && method === 'POST') return jsonResp({ ok: true })
      if (path === '/calls/rooms/room/sessions' && method === 'GET') return jsonResp({ sessions: [] })
      if (path === '/calls/sessions/me/tracks/new' && method === 'POST') {
        return jsonResp({
          requiresImmediateRenegotiation: true,
          sessionDescription: { type: 'offer', sdp: 'v=0\r\na=mid:1\r\n' },
          tracks: [{ trackName: 'cam-native', mid: '1' }],
        })
      }
      if (path === '/calls/sessions/me/renegotiate' && method === 'PUT') return jsonResp({ ok: true })
      if (path.includes('/heartbeat') && method === 'PUT') return jsonResp({ ok: true })
      if (path === '/api/cells/execute-ephemeral' && method === 'POST') return jsonResp({ ok: true })
      if (path.includes('/sessions/me') && method === 'DELETE') return jsonResp({ ok: true })
      throw new Error(`Unhandled mock fetch: ${method} ${path}`)
    })
    _remoteTrackTypes.set('guest', new Map([['cam-native', 'camera']]))

    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')
    await _subscribeToRemoteTracks(camSession, api.remoteStreams)

    // The dead camera stream was NOT added as a black tile.
    expect(api.remoteStreams.has('guest')).toBe(false)
    // The mapping was cleaned up (no mid leak) + the receiver transceiver stopped.
    expect(_remoteMidToTrackName.has('1')).toBe(false)
    expect((state._pc as any).getTransceivers().find((t: any) => t.mid === '1').stopped).toBe(true)
  })

  it('F2: the merged stream re-binds onremovetrack with an event-driven handler — removing a track tears down ITS OWN transceiver, not the first track\'s', async () => {
    let videoTrackRef: MockMediaStreamTrack | null = null
    class AudioVideoPC extends MockRTCPeerConnection {
      async setRemoteDescription(desc: { type?: string; sdp?: string }): Promise<void> {
        this.remoteDescription = desc
        const mids = [...(desc.sdp || '').matchAll(/a=mid:(\S+)/g)].map((m) => m[1])
        for (const mid of mids) {
          let tx = this.transceivers.find((t) => t.mid === mid)
          if (!tx) { tx = new MockTransceiver(mid, 'recvonly'); this.transceivers.push(tx) }
        }
        if (desc.type === 'offer') {
          // Fire audio (mid 0) then video (mid 1) — the merge path (both onto
          // the same {guest} tile).  Mirror the real browser invariant: the
          // transceiver's receiver.track IS the ontrack's track object (the
          // F2 event-driven onremovetrack resolves the mid via that lookup).
          const audioTx = this.transceivers.find((t) => t.mid === '0')
          if (audioTx) {
            const audioTrack = new MockMediaStreamTrack('audio', 'audio-native')
            audioTx.receiver.track = audioTrack
            const audioStream = new MockMediaStream(); audioStream.addTrack(audioTrack)
            this.ontrack?.({
              track: audioTrack,
              receiver: { track: audioTrack },
              transceiver: audioTx,
              streams: [audioStream],
            })
          }
          const videoTx = this.transceivers.find((t) => t.mid === '1')
          if (videoTx) {
            const videoTrack = new MockMediaStreamTrack('video', 'video-native')
            videoTx.receiver.track = videoTrack
            videoTrackRef = videoTrack
            const videoStream = new MockMediaStream(); videoStream.addTrack(videoTrack)
            this.ontrack?.({
              track: videoTrack,
              receiver: { track: videoTrack },
              transceiver: videoTx,
              streams: [videoStream],
            })
          }
        }
      }
    }
    ;(globalThis as any).RTCPeerConnection = AudioVideoPC

    const guestSession: RemoteSession = { sessionId: 'guest', tracks: ['mic', 'camera'], trackNames: ['audio-native', 'video-native'] }
    ;(globalThis as any).__mockApiFetch = vi.fn(async (path: string, options: RequestInit = {}) => {
      const method = (options.method || 'GET').toUpperCase()
      if (path === '/calls/provision' && method === 'POST') return jsonResp({ status: 'already_exists' })
      if (path === '/calls/session' && method === 'POST') {
        return jsonResp({ sessionId: 'me', sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' } })
      }
      if (path === '/calls/rooms/room/sessions' && method === 'POST') return jsonResp({ ok: true })
      if (path === '/calls/rooms/room/sessions' && method === 'GET') return jsonResp({ sessions: [] })
      if (path === '/calls/sessions/me/tracks/new' && method === 'POST') {
        return jsonResp({
          requiresImmediateRenegotiation: true,
          sessionDescription: { type: 'offer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' },
          tracks: [
            { trackName: 'audio-native', mid: '0' },
            { trackName: 'video-native', mid: '1' },
          ],
        })
      }
      if (path === '/calls/sessions/me/renegotiate' && method === 'PUT') return jsonResp({ ok: true })
      if (path.includes('/heartbeat') && method === 'PUT') return jsonResp({ ok: true })
      if (path === '/api/cells/execute-ephemeral' && method === 'POST') return jsonResp({ ok: true })
      if (path.includes('/sessions/me') && method === 'DELETE') return jsonResp({ ok: true })
      throw new Error(`Unhandled mock fetch: ${method} ${path}`)
    })
    _remoteTrackTypes.set('guest', new Map([
      ['audio-native', 'mic'],
      ['video-native', 'camera'],
    ]))

    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')
    await _subscribeToRemoteTracks(guestSession, api.remoteStreams)

    // Both audio + video merged into ONE {guest} tile.
    expect(api.remoteStreams.has('guest')).toBe(true)
    const tileStream = api.remoteStreams.get('guest')
    expect(tileStream.getTracks().length).toBe(2)

    // Past the grace window, the publisher removes the VIDEO track — the
    // event-driven onremovetrack handler (F2) must tear down the VIDEO
    // transceiver (mid '1'), NOT the audio one (mid '0').
    await new Promise((resolve) => setTimeout(resolve, 550))
    // Real browser: removeTrack fires onremovetrack AFTER the removal.
    tileStream.removeTrack(videoTrackRef!)
    tileStream.onremovetrack?.({ track: videoTrackRef })
    const txs = (state._pc as any).getTransceivers()
    expect(txs.find((t: any) => t.mid === '1').stopped).toBe(true)  // video torn down
    expect(txs.find((t: any) => t.mid === '0').stopped).toBe(false) // audio survives
    // R#4 (review #3077 finding 4): stopping only the camera must NOT delete the
    // whole participant tile — the {guest} tile survives with the audio.
    expect(api.remoteStreams.has('guest')).toBe(true)
    const surviving = api.remoteStreams.get('guest')
    expect(surviving.getTracks().some((t: any) => t.id === 'audio-native')).toBe(true)
    expect(_remoteMidToTrackName.has('1')).toBe(false) // video mapping cleaned
  })

  it('F3+F6: a DIRECT shareStream populates _screenTrackId + isSharingScreen, and the browser native "Stop sharing" (ended) runs the full stopSharing cleanup (state, registry/presence, SFU)', async () => {
    let tracksCloseCount = 0
    ;(globalThis as any).__mockApiFetch = vi.fn(async (path: string, options: RequestInit = {}) => {
      const method = (options.method || 'GET').toUpperCase()
      if (path === '/calls/provision' && method === 'POST') return jsonResp({ status: 'already_exists' })
      if (path === '/calls/session' && method === 'POST') {
        return jsonResp({ sessionId: 'me', sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' } })
      }
      if (path === '/calls/rooms/room/sessions' && method === 'POST') return jsonResp({ ok: true })
      if (path === '/calls/rooms/room/sessions' && method === 'GET') return jsonResp({ sessions: [] })
      if (path === '/calls/sessions/me/tracks/new' && method === 'POST') {
        // Direct answer — the screen track is registered.
        return jsonResp({ sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:2\r\n' } })
      }
      if (path === '/calls/sessions/me/renegotiate' && method === 'PUT') return jsonResp({ ok: true })
      if (path.includes('/heartbeat') && method === 'PUT') return jsonResp({ ok: true })
      if (path.includes('/tracks/') && method === 'DELETE') { tracksCloseCount += 1; return jsonResp({ ok: true }) }
      if (path === '/api/cells/execute-ephemeral' && method === 'POST') return jsonResp({ ok: true })
      if (path.includes('/sessions/me') && method === 'DELETE') return jsonResp({ ok: true })
      throw new Error(`Unhandled mock fetch: ${method} ${path}`)
    })

    const fakeScreen = new MockMediaStream()
    const screenTrack = new MockMediaStreamTrack('video', 'screen-native-id')
    fakeScreen.addTrack(screenTrack)

    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')

    // Direct shareStream (glb-content-viewer style — no toggleScreenShare).
    await api.shareStream(fakeScreen)
    // F6: _screenTrackId + isSharingScreen populated for a DIRECT caller.
    expect(state._screenTrackId).toBe('screen-native-id')
    expect(api.isSharingScreen).toBe(true)
    expect(api.selfViewStream?.getVideoTracks()?.[0]?.id).toBe('screen-native-id')
    // F10: the canonical _updatePublishedTracks published the REAL set.
    expect(state._publishedTracks).toContain('screen')

    // F3: the browser native "Stop sharing" ends the display track → full
    // cleanup (same as stopSharing).  stopSharing is async (awaits the SFU
    // tracks/close), so flush the microtask queue before asserting.
    screenTrack.onended?.()
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(api.isSharingScreen).toBe(false)
    expect(state._screenStream).toBeNull()
    expect(state._screenTrackId).toBeNull()
    expect(_localTrackNamesByDisplay.has('screen')).toBe(false)
    expect(tracksCloseCount).toBe(1) // _removeTrackFromSfu ran
    expect(state._publishedTracks).not.toContain('screen')
  })

  it('F4: pending-subscribe timers are tracked and cancelled on hangUp — a stale timer cannot fire into the next call', async () => {
    let gateRenegotiate = false
    let resolveRenegotiate: () => void = () => {}
    const gate = new Promise<void>((resolve) => { resolveRenegotiate = resolve })
    ;(globalThis as any).__mockApiFetch = vi.fn(async (path: string, options: RequestInit = {}) => {
      const method = (options.method || 'GET').toUpperCase()
      if (path === '/calls/provision' && method === 'POST') return jsonResp({ status: 'already_exists' })
      if (path === '/calls/session' && method === 'POST') {
        return jsonResp({ sessionId: 'me', sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' } })
      }
      if (path === '/calls/rooms/room/sessions' && method === 'POST') return jsonResp({ ok: true })
      if (path === '/calls/rooms/room/sessions' && method === 'GET') return jsonResp({ sessions: [] })
      if (path === '/calls/sessions/me/tracks/new' && method === 'POST') {
        gateRenegotiate = true
        return jsonResp({
          requiresImmediateRenegotiation: true,
          sessionDescription: { type: 'offer', sdp: 'v=0\r\na=mid:2\r\n' },
          tracks: [{ trackName: 'screen-native', mid: '2' }],
        })
      }
      if (path === '/calls/sessions/me/renegotiate' && method === 'PUT') {
        if (gateRenegotiate) return gate.then(() => jsonResp({ ok: true }))
        return jsonResp({ ok: true })
      }
      if (path.includes('/heartbeat') && method === 'PUT') return jsonResp({ ok: true })
      if (path === '/api/cells/execute-ephemeral' && method === 'POST') return jsonResp({ ok: true })
      if (path.includes('/sessions/me') && method === 'DELETE') return jsonResp({ ok: true })
      throw new Error(`Unhandled mock fetch: ${method} ${path}`)
    })
    _remoteTrackTypes.set('guest', new Map([['screen-native', 'screen']]))

    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')

    const screenSession: RemoteSession = { sessionId: 'guest', tracks: ['screen'], trackNames: ['screen-native'] }
    const pendingSubscribe = _subscribeToRemoteTracks(screenSession, api.remoteStreams)
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(_pendingSubscribeMids.has('2')).toBe(true)
    expect(_pendingSubscribeTimers.has('2')).toBe(true)

    // hangUp while the subscribe is STILL in flight → timers cancelled.
    api.hangUp()
    expect(_pendingSubscribeTimers.size).toBe(0)
    expect(_pendingSubscribeMids.size).toBe(0)

    // Release the gate so the in-flight subscribe settles (harmless — state is
    // already cleared), keeping the promise settled for the teardown.
    resolveRenegotiate()
    await pendingSubscribe
  })

  it('F5: startCall has a reentrancy guard — overlapping invocations create only ONE peer connection', async () => {
    let pcCount = 0
    class CountingPC extends MockRTCPeerConnection {
      constructor() { super(); pcCount += 1 }
    }
    ;(globalThis as any).RTCPeerConnection = CountingPC
    ;(globalThis as any).__mockApiFetch = vi.fn(async (path: string, options: RequestInit = {}) => {
      const method = (options.method || 'GET').toUpperCase()
      if (path === '/calls/provision' && method === 'POST') return jsonResp({ status: 'already_exists' })
      if (path === '/calls/session' && method === 'POST') {
        return jsonResp({ sessionId: 'me', sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' } })
      }
      if (path === '/calls/rooms/room/sessions' && method === 'POST') return jsonResp({ ok: true })
      if (path === '/calls/rooms/room/sessions' && method === 'GET') return jsonResp({ sessions: [] })
      if (path === '/calls/sessions/me/tracks/new' && method === 'POST') return jsonResp({ ok: true })
      if (path === '/calls/sessions/me/renegotiate' && method === 'PUT') return jsonResp({ ok: true })
      if (path.includes('/heartbeat') && method === 'PUT') return jsonResp({ ok: true })
      if (path === '/api/cells/execute-ephemeral' && method === 'POST') return jsonResp({ ok: true })
      if (path.includes('/sessions/me') && method === 'DELETE') return jsonResp({ ok: true })
      throw new Error(`Unhandled mock fetch: ${method} ${path}`)
    })

    wrapper = mountComposable()
    const api = wrapper.vm as any
    const p1 = api.startCall('room')
    const p2 = api.startCall('room') // overlapping — must early-return
    await Promise.all([p1, p2])
    expect(pcCount).toBe(1) // exactly ONE RTCPeerConnection created
  })

  it('F7: removeOwnerMappings tears down the ghosted owner\'s recvonly transceivers (no local RTP leak)', async () => {
    ;(globalThis as any).__mockApiFetch = vi.fn(async (path: string, options: RequestInit = {}) => {
      const method = (options.method || 'GET').toUpperCase()
      if (path === '/calls/provision' && method === 'POST') return jsonResp({ status: 'already_exists' })
      if (path === '/calls/session' && method === 'POST') {
        return jsonResp({ sessionId: 'me', sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' } })
      }
      if (path === '/calls/rooms/room/sessions' && method === 'POST') return jsonResp({ ok: true })
      if (path === '/calls/rooms/room/sessions' && method === 'GET') return jsonResp({ sessions: [] })
      if (path === '/calls/sessions/me/tracks/new' && method === 'POST') {
        return jsonResp({
          requiresImmediateRenegotiation: true,
          sessionDescription: { type: 'offer', sdp: 'v=0\r\na=mid:2\r\n' },
          tracks: [{ trackName: 'screen-native', mid: '2' }],
        })
      }
      if (path === '/calls/sessions/me/renegotiate' && method === 'PUT') return jsonResp({ ok: true })
      if (path.includes('/heartbeat') && method === 'PUT') return jsonResp({ ok: true })
      if (path === '/api/cells/execute-ephemeral' && method === 'POST') return jsonResp({ ok: true })
      if (path.includes('/sessions/me') && method === 'DELETE') return jsonResp({ ok: true })
      throw new Error(`Unhandled mock fetch: ${method} ${path}`)
    })
    _remoteTrackTypes.set('guest', new Map([['screen-native', 'screen']]))

    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')

    const screenSession: RemoteSession = { sessionId: 'guest', tracks: ['screen'], trackNames: ['screen-native'] }
    await _subscribeToRemoteTracks(screenSession, api.remoteStreams)
    expect(_subscribedSessions.has('guest')).toBe(true)
    const txBefore = (state._pc as any).getTransceivers().find((t: any) => t.mid === '2')
    expect(txBefore.stopped).toBe(false)

    // A discovery pass where the guest is ABSENT → ghost prune → F7 tears down
    // the guest's recvonly receiver transceiver.
    await _refreshDiscovery('room', api.remoteStreams, [], 'stale')
    expect(txBefore.stopped).toBe(true)
    expect(_subscribedSessions.has('guest')).toBe(false)
    expect(_remoteMidToTrackName.has('2')).toBe(false)
  })

  it('F8: _pollProvisionTask treats a transient 502 mid-poll as RETRY (backoff) instead of aborting the call, and completes on the next poll', async () => {
    let pollCalls = 0
    ;(globalThis as any).__mockApiFetch = vi.fn(async (path: string) => {
      pollCalls += 1
      if (pollCalls === 1) return errResp(502, 'Bad Gateway') // transient gateway blip
      return jsonResp({ status: 'completed', app_id: 'app-1' })
    })

    const result = await _pollProvisionTask('task-1', 5, 10)
    expect(result.app_id).toBe('app-1')
    expect(pollCalls).toBe(2) // 1 transient failure + 1 success (no abort)
    // The transient error was surfaced as a retry, not an abort.
    const transientLog = warnCalls.find((args) =>
      args.some((a) => typeof a === 'string' && a.includes('[pollProvision] transient error mid-poll')))
    expect(transientLog).toBeDefined()
  })

  it('F11: hangUp resets _statsDumpScheduled so the one-shot stats dump re-arms on the NEXT call', async () => {
    ;(globalThis as any).__mockApiFetch = vi.fn(async (path: string, options: RequestInit = {}) => {
      const method = (options.method || 'GET').toUpperCase()
      if (path === '/calls/provision' && method === 'POST') return jsonResp({ status: 'already_exists' })
      if (path === '/calls/session' && method === 'POST') {
        return jsonResp({ sessionId: 'me', sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' } })
      }
      if (path === '/calls/rooms/room/sessions' && method === 'POST') return jsonResp({ ok: true })
      if (path === '/calls/rooms/room/sessions' && method === 'GET') return jsonResp({ sessions: [] })
      if (path === '/calls/sessions/me/tracks/new' && method === 'POST') {
        return jsonResp({
          requiresImmediateRenegotiation: true,
          sessionDescription: { type: 'offer', sdp: 'v=0\r\na=mid:1\r\n' },
          tracks: [{ trackName: 'cam-native', mid: '1' }],
        })
      }
      if (path === '/calls/sessions/me/renegotiate' && method === 'PUT') return jsonResp({ ok: true })
      if (path.includes('/heartbeat') && method === 'PUT') return jsonResp({ ok: true })
      if (path === '/api/cells/execute-ephemeral' && method === 'POST') return jsonResp({ ok: true })
      if (path.includes('/sessions/me') && method === 'DELETE') return jsonResp({ ok: true })
      throw new Error(`Unhandled mock fetch: ${method} ${path}`)
    })
    _remoteTrackTypes.set('guest', new Map([['cam-native', 'camera']]))
    const camSession: RemoteSession = { sessionId: 'guest', tracks: ['camera'], trackNames: ['cam-native'] }

    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')
    await _subscribeToRemoteTracks(camSession, api.remoteStreams)
    expect(state._statsDumpScheduled).toBe(true) // armed on the first subscribe

    api.hangUp()
    expect(state._statsDumpScheduled).toBe(false) // reset → re-arms on the next call
  })

  it('R1: a dead non-screen track arriving while the owner has a LIVE tile tears down only its transceiver+mapping — the live mic tile survives', async () => {
    // R#1 (review #3077 finding 1): the F1 dead-camera cleanup previously
    // deleted the WHOLE {owner} tile (bypassGrace), killing the participant's
    // live mic.  It now preserves a live tile and cleans up only the dead
    // track's transceiver + mapping.
    class LiveAudioDeadCamPC extends MockRTCPeerConnection {
      async setRemoteDescription(desc: { type?: string; sdp?: string }): Promise<void> {
        this.remoteDescription = desc
        const mids = [...(desc.sdp || '').matchAll(/a=mid:(\S+)/g)].map((m) => m[1])
        for (const mid of mids) {
          let tx = this.transceivers.find((t) => t.mid === mid)
          if (!tx) { tx = new MockTransceiver(mid, 'recvonly'); this.transceivers.push(tx) }
        }
        if (desc.type === 'offer') {
          const audioTx = this.transceivers.find((t) => t.mid === '0')
          if (audioTx && mids.includes('0')) {
            const audioTrack = new MockMediaStreamTrack('audio', 'audio-native')
            audioTx.receiver.track = audioTrack
            const audioStream = new MockMediaStream(); audioStream.addTrack(audioTrack)
            this.ontrack?.({
              track: audioTrack,
              receiver: { track: audioTrack },
              transceiver: audioTx,
              streams: [audioStream],
            })
          }
          const camTx = this.transceivers.find((t) => t.mid === '1')
          if (camTx && mids.includes('1')) {
            const deadTrack = new MockMediaStreamTrack('video', 'dead-cam')
            deadTrack.readyState = 'ended'
            camTx.receiver.track = deadTrack
            const deadStream = new MockMediaStream(); deadStream.addTrack(deadTrack)
            this.ontrack?.({
              track: deadTrack,
              receiver: { track: deadTrack },
              transceiver: camTx,
              streams: [deadStream],
            })
          }
        }
      }
    }
    ;(globalThis as any).RTCPeerConnection = LiveAudioDeadCamPC

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
        const trackName = body.tracks?.[0]?.trackName
        return trackName === 'video-native'
          ? jsonResp({ requiresImmediateRenegotiation: true, sessionDescription: { type: 'offer', sdp: 'v=0\r\na=mid:1\r\n' }, tracks: [{ trackName: 'video-native', mid: '1' }] })
          : jsonResp({ requiresImmediateRenegotiation: true, sessionDescription: { type: 'offer', sdp: 'v=0\r\na=mid:0\r\n' }, tracks: [{ trackName: 'audio-native', mid: '0' }] })
      }
      if (path === '/calls/sessions/me/renegotiate' && method === 'PUT') return jsonResp({ ok: true })
      if (path.includes('/heartbeat') && method === 'PUT') return jsonResp({ ok: true })
      if (path === '/api/cells/execute-ephemeral' && method === 'POST') return jsonResp({ ok: true })
      if (path.includes('/sessions/me') && method === 'DELETE') return jsonResp({ ok: true })
      throw new Error(`Unhandled mock fetch: ${method} ${path}`)
    })
    _remoteTrackTypes.set('guest', new Map([
      ['audio-native', 'mic'],
      ['video-native', 'camera'],
    ]))

    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')

    // 1. Subscribe the mic → LIVE audio tile {guest}.
    await _subscribeToRemoteTracks({ sessionId: 'guest', tracks: ['mic'], trackNames: ['audio-native'] }, api.remoteStreams)
    expect(api.remoteStreams.has('guest')).toBe(true)
    expect(api.remoteStreams.get('guest').getTracks()[0].readyState).toBe('live')

    // 2. Subscribe the camera DELTA → dead camera ontrack fires while the mic
    //    tile is alive.  R#1: the tile survives, the dead track is torn down.
    await _subscribeToRemoteTracks(
      { sessionId: 'guest', tracks: ['mic', 'camera'], trackNames: ['audio-native', 'video-native'] },
      api.remoteStreams,
    )
    expect(api.remoteStreams.has('guest')).toBe(true)   // mic tile SURVIVES
    const tile = api.remoteStreams.get('guest')
    expect(tile.getTracks().some((t: any) => t.id === 'audio-native')).toBe(true)
    expect(_remoteMidToTrackName.has('1')).toBe(false)  // dead cam mapping cleaned
    expect((state._pc as any).getTransceivers().find((t: any) => t.mid === '1').stopped).toBe(true)
  })

  it('R2: _closeLocalRenegotiation rolls back (returns false) when a DIRECT ANSWER SDP carries a per-track errorCode — the errored track is never applied', async () => {
    // R#2 (review #3077 finding 2): the answer branch previously applied the
    // SDP and returned true without inspecting per-track errorCode → the caller
    // published a track the SFU rejected (not_found_track_error forever).  The
    // errorCode must be checked BEFORE any setRemoteDescription (a rollback only
    // works from have-local-offer — after an answer the PC is stable).
    ;(globalThis as any).__mockApiFetch = vi.fn(async (path: string, options: RequestInit = {}) => {
      const method = (options.method || 'GET').toUpperCase()
      if (path === '/calls/provision' && method === 'POST') return jsonResp({ status: 'already_exists' })
      if (path === '/calls/session' && method === 'POST') {
        return jsonResp({ sessionId: 'me', sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' } })
      }
      if (path === '/calls/rooms/room/sessions' && method === 'POST') return jsonResp({ ok: true })
      if (path === '/calls/rooms/room/sessions' && method === 'GET') return jsonResp({ sessions: [] })
      if (path.includes('/heartbeat') && method === 'PUT') return jsonResp({ ok: true })
      if (path === '/api/cells/execute-ephemeral' && method === 'POST') return jsonResp({ ok: true })
      if (path.includes('/sessions/me') && method === 'DELETE') return jsonResp({ ok: true })
      throw new Error(`Unhandled mock fetch: ${method} ${path}`)
    })

    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')

    // Put the PC in 'have-local-offer' (as _enableLocalTrack/shareStream do).
    await (state._pc as any).createOffer()
    await (state._pc as any).setLocalDescription({ type: 'offer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' })
    const remoteDescBefore = (state._pc as any).remoteDescription

    const closed = await _closeLocalRenegotiation({
      sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' },
      tracks: [{ trackName: 'cam-native', mid: '1', errorCode: 'not_found_track_error' }],
    })

    expect(closed).toBe(false)
    expect((state._pc as any).localDescription.type).toBe('rollback')
    // The crafted answer was NOT applied — remoteDescription is unchanged
    // (startCall already applied its own answer; the errorCode check runs before
    // any setRemoteDescription).
    expect((state._pc as any).remoteDescription).toBe(remoteDescBefore)
  })

  it('R3: a FAILED shareStream detaches the sendonly transceiver (sender.track null) and restores it as the orphan — the next share REUSES it instead of stacking a new transceiver', async () => {
    // R#3 (review #3077 finding 3): the shareStream G2 branch previously
    // stopped the stream but left the sendonly transceiver attached to the
    // stopped track — the next share stacked a NEW transceiver (A1/413
    // accumulation).  It now detaches + restores the orphan (mirror of
    // _enableLocalTrack).
    let screenRegCalls = 0
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
        const trackName = body.tracks?.[0]?.trackName
        if (trackName === 'screen-native-id') {
          screenRegCalls += 1
          if (screenRegCalls === 1) {
            // First share → the SFU rejects the screen (per-track errorCode).
            return jsonResp({
              sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:2\r\n' },
              tracks: [{ trackName: 'screen-native-id', mid: '2', errorCode: 'empty_track_error' }],
            })
          }
          return jsonResp({ sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:2\r\n' } })
        }
        return jsonResp({ requiresImmediateRenegotiation: true, sessionDescription: { type: 'offer', sdp: 'v=0\r\na=mid:1\r\n' }, tracks: [{ trackName: 'cam-native', mid: '1' }] })
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

    const fakeScreen = new MockMediaStream()
    const screenTrack = new MockMediaStreamTrack('video', 'screen-native-id')
    fakeScreen.addTrack(screenTrack)
    const txCountBefore = (state._pc as any).getTransceivers().length

    // 1. First share FAILS (SFU errorCode) → the G2 branch.
    await api.shareStream(fakeScreen)
    expect(api.isSharingScreen).toBe(false)
    expect(state._screenStream).toBeNull()
    // R#3: the sendonly transceiver was detached + restored as the orphan.
    expect(state._orphanScreenTx).not.toBeNull()
    expect(state._orphanScreenTx!.sender.track).toBeNull()
    expect(state._orphanScreenTx!.sender.replaceTrack).toHaveBeenCalledWith(null)
    const txCountAfterFail = (state._pc as any).getTransceivers().length

    // 2. Second share SUCCEEDS → reuses the orphan (NO new transceiver stacked).
    const fakeScreen2 = new MockMediaStream()
    const screenTrack2 = new MockMediaStreamTrack('video', 'screen-native-id-2')
    fakeScreen2.addTrack(screenTrack2)
    await api.shareStream(fakeScreen2)
    expect(api.isSharingScreen).toBe(true)
    expect(state._orphanScreenTx).toBeNull() // consumed by the reuse
    expect((state._pc as any).getTransceivers().length).toBe(txCountAfterFail)
    expect((state._pc as any).getTransceivers().length).toBeGreaterThanOrEqual(txCountBefore)
  })

  it('R5: a FAILED camera registration while screen sharing preserves the screen self-view (does not blank it with the null local stream)', async () => {
    // R#5 (review #3077 finding 5): the _enableLocalTrack G2 branch set
    // selfViewStream = localStream.value (= null) on camera failure — wiping the
    // active screen-share preview.  Now preserved while isSharingScreen is true.
    let camRegFails = false
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
        const trackName = body.tracks?.[0]?.trackName
        if (trackName === 'screen-native-id') {
          return jsonResp({ sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:2\r\n' } })
        }
        if (trackName === 'cam-native-id' && camRegFails) {
          throw new Error('simulated camera registration failure')
        }
        return jsonResp({ requiresImmediateRenegotiation: true, sessionDescription: { type: 'offer', sdp: 'v=0\r\na=mid:1\r\n' }, tracks: [{ trackName: 'cam-native-id', mid: '1' }] })
      }
      if (path === '/calls/sessions/me/renegotiate' && method === 'PUT') return jsonResp({ ok: true })
      if (path.includes('/heartbeat') && method === 'PUT') return jsonResp({ ok: true })
      if (path === '/api/cells/execute-ephemeral' && method === 'POST') return jsonResp({ ok: true })
      if (path.includes('/sessions/me') && method === 'DELETE') return jsonResp({ ok: true })
      throw new Error(`Unhandled mock fetch: ${method} ${path}`)
    })

    const fakeCam = new MockMediaStream()
    fakeCam.addTrack(new MockMediaStreamTrack('video', 'cam-native-id'))
    Object.defineProperty(navigator, 'mediaDevices', {
      value: { getUserMedia: vi.fn(async () => fakeCam) },
      configurable: true,
    })

    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')

    // 1. Share the screen successfully → selfViewStream = the screen.
    const fakeScreen = new MockMediaStream()
    const screenTrack = new MockMediaStreamTrack('video', 'screen-native-id')
    fakeScreen.addTrack(screenTrack)
    await api.shareStream(fakeScreen)
    expect(api.isSharingScreen).toBe(true)
    expect(api.selfViewStream?.getVideoTracks()?.[0]?.id).toBe('screen-native-id')

    // 2. The camera registration fails while sharing.
    camRegFails = true
    await api.toggleCamera()
    expect(api.cameraEnabled).toBe(false)
    // R#5: the screen self-view is PRESERVED (not blanked with the null local
    // stream).
    expect(api.selfViewStream?.getVideoTracks()?.[0]?.id).toBe('screen-native-id')
  })
})
