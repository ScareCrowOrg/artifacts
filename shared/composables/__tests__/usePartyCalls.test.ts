/**
 * @vitest-environment jsdom
 *
 * F3 FIX (ITER_1 guest-screenshare) — unit test for the asymmetric screen-share
 * bug:
 *
 *   When a REMOTE session publishes a NEW track mid-call (the shared screen),
 *   the transceiver that carries it is created ONLY when the SFU's offer is
 *   applied at setRemoteDescription.  The first `_transceiverMeta` population
 *   pass in `_subscribeToRemoteTracks` runs BEFORE setRemoteDescription, so it
 *   finds no transceiver for the screen mid and leaves the WeakMap EMPTY — the
 *   screen's ontrack then depends 100% on the prunable global
 *   `_remoteMidToTrackName` map (race H3 → opaque tile → never renders).
 *
 * This test drives the real `usePartyCalls` subscribe flow with a mocked
 * RTCPeerConnection and asserts:
 *   1. the NEW screen transceiver is created by setRemoteDescription (mock),
 *   2. the post-setRemoteDescription re-anchor (`_anchorTransceiverMetaFromMidMap`)
 *      populates `_transceiverMeta` for it — observable via the
 *      `[DIAG][subscribe] transceiver_meta anchored post-setRemoteDescription`
 *      log,
 *   3. the screen's ontrack resolves to the `{guest}/screen` tile (so it is NOT
 *      an opaque orphan that the prune would remove).
 *
 * NOTE on timing: the mock fires the screen ontrack SYNCHRONOUSLY inside
 * setRemoteDescription — the edge-case ordering that the fix's on-the-spot
 * re-anchor in `_handleRemoteTrack` also covers.  Real browsers dispatch ontrack
 * as a task AFTER setRemoteDescription resolves, so the post-offer re-anchor
 * runs first and the WeakMap is already populated when the ontrack reads it.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'
import { createPinia, setActivePinia, type Pinia } from 'pinia'

// ── Logger mock (hoisted) ──────────────────────────────────────────────────
// Capture every warn(...) call so the test can assert the DIAG that proves the
// fix anchored the WeakMap for the NEW screen transceiver.
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

// ── apiService mock (hoisted router installed in beforeEach) ───────────────
vi.mock('#artifacts/shared/services/apiService', () => ({
  apiFetch: vi.fn(async (path: string, options: RequestInit = {}) =>
    (globalThis as any).__mockApiFetch(path, options),
  ),
}))

// useDistributedState uses WebSocket + JSON Patch — not needed for this test.
vi.mock('#artifacts/shared/composables/useDistributedState', () => ({
  useDistributedState: vi.fn(() => ({})),
}))

// ── WebRTC mocks (jsdom does not implement RTCPeerConnection/MediaStream) ──

class MockMediaStreamTrack {
  kind: string
  id: string
  enabled = true
  readyState: string = 'live'
  muted = false
  onended: (() => void) | null = null
  onmute: (() => void) | null = null
  onunmute: (() => void) | null = null
  constructor(kind: string, id: string) {
    this.kind = kind
    this.id = id
  }
  stop(): void {}
}

class MockMediaStream {
  tracks: MockMediaStreamTrack[] = []
  id: string
  onremovetrack: ((ev: unknown) => void) | null = null
  constructor() {
    this.id = `stream-${(MockMediaStream as any).__counter++}`
  }
  addTrack(t: MockMediaStreamTrack): void { this.tracks.push(t) }
  getTracks(): MockMediaStreamTrack[] { return this.tracks }
  getVideoTracks(): MockMediaStreamTrack[] { return this.tracks.filter((t) => t.kind === 'video') }
  getAudioTracks(): MockMediaStreamTrack[] { return this.tracks.filter((t) => t.kind === 'audio') }
  removeTrack(t: MockMediaStreamTrack): void {
    this.tracks = this.tracks.filter((x) => x !== t)
  }
  stop(): void {}
}
;(MockMediaStream as any).__counter = 0

class MockTransceiver {
  mid: string | null
  direction: string
  sender: { track: MockMediaStreamTrack | null; replaceTrack: ReturnType<typeof vi.fn> }
  receiver: { track: { readyState: string; muted: boolean } }
  constructor(mid: string | null, direction: string) {
    this.mid = mid
    this.direction = direction
    this.sender = { track: null, replaceTrack: vi.fn(async () => {}) }
    this.receiver = { track: { readyState: 'live', muted: false } }
  }
}

class MockRTCPeerConnection {
  transceivers: MockTransceiver[] = []
  localDescription: unknown = null
  remoteDescription: unknown = null
  oniceconnectionstatechange: (() => void) | null = null
  ontrack: ((ev: unknown) => void) | null = null
  iceConnectionState = 'connected'

  addTransceiver(trackOrKind: string | MockMediaStreamTrack, init?: { direction?: string }): MockTransceiver {
    const kind = typeof trackOrKind === 'string' ? trackOrKind : trackOrKind.kind
    const tx = new MockTransceiver(null, init?.direction ?? 'sendrecv')
    if (typeof trackOrKind !== 'string') tx.sender.track = trackOrKind
    this.transceivers.push(tx)
    return tx
  }
  getTransceivers(): MockTransceiver[] { return this.transceivers }

  async createOffer(): Promise<{ type: string; sdp: string }> {
    // Assign a mid to every transceiver that does not have one yet (the local
    // audio/video recvonly transceivers created at join → mids '0'/'1').
    this.transceivers.forEach((tx, i) => { if (tx.mid === null) tx.mid = String(i) })
    return { type: 'offer', sdp: this._buildSdp() }
  }
  async setLocalDescription(desc: unknown): Promise<void> { this.localDescription = desc }

  async setRemoteDescription(desc: { type?: string; sdp?: string }): Promise<void> {
    this.remoteDescription = desc
    // Simulate the SFU offer creating NEW receive transceivers for m-lines whose
    // mids do not exist yet — the shared screen (mid '2') is exactly this case.
    const mids = [...(desc.sdp || '').matchAll(/a=mid:(\S+)/g)].map((m) => m[1])
    const created: MockTransceiver[] = []
    for (const mid of mids) {
      let tx = this.transceivers.find((t) => t.mid === mid)
      if (!tx) {
        tx = new MockTransceiver(mid, 'recvonly')
        this.transceivers.push(tx)
        created.push(tx)
      }
    }
    // Fire the screen ontrack SYNCHRONOUSLY — the edge-case ordering that makes
    // the on-the-spot re-anchor in _handleRemoteTrack necessary.  (Real browsers
    // dispatch it as a task after setRemoteDescription, so the post-offer
    // re-anchor runs first.)
    for (const tx of created) {
      if (tx.mid === '2') {
        this.ontrack?.({
          track: new MockMediaStreamTrack('video', 'screen-track'),
          receiver: { track: { readyState: 'live', muted: false } },
          transceiver: tx,
          streams: [],
        })
      }
    }
  }

  async createAnswer(): Promise<{ type: string; sdp: string }> {
    return { type: 'answer', sdp: this._buildSdp() }
  }
  async getStats(): Promise<Map<string, unknown>> { return new Map<string, unknown>() }
  close(): void { this.transceivers = [] }
  removeEventListener(): void {}
  addEventListener(): void {}
  private _buildSdp(): string {
    return this.transceivers.map((t) => `a=mid:${t.mid}`).join('\r\n')
  }
}

// ── Composable import (AFTER mocks — vitest hoists vi.mock) ────────────────
import { usePartyCalls } from '../usePartyCalls'

// ── Test wrapper ────────────────────────────────────────────────────────────
let pinia: Pinia
let wrapper: VueWrapper

function mountComposable(): VueWrapper {
  const TestComp = defineComponent({
    setup() {
      return usePartyCalls()
    },
    template: '<div></div>',
  })
  const w = mount(TestComp, { global: { plugins: [pinia] } })
  return w
}

function jsonResp(body: unknown) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(''),
  }
}

describe('usePartyCalls — guest screen-share transceiver meta anchoring', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    warnCalls.length = 0
    ;(globalThis as any).RTCPeerConnection = MockRTCPeerConnection
    ;(globalThis as any).RTCSessionDescription = class {
      type: string
      sdp: string
      constructor(init: { type?: string; sdp?: string }) {
        this.type = init.type || ''
        this.sdp = init.sdp || ''
      }
    }
    ;(globalThis as any).MediaStream = MockMediaStream
    ;(globalThis as any).MediaStreamTrack = MockMediaStreamTrack

    let discoveryCount = 0
    const guestSession = {
      sessionId: 'guest',
      tracks: ['camera', 'screen'],
      trackNames: ['cam-native', 'screen-native'],
    }
    ;(globalThis as any).__mockApiFetch = vi.fn(async (path: string, options: RequestInit = {}) => {
      const method = (options.method || 'GET').toUpperCase()
      if (path === '/calls/provision' && method === 'POST') return jsonResp({ status: 'already_exists' })
      if (path === '/calls/session' && method === 'POST') {
        return jsonResp({
          sessionId: 'me',
          sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' },
        })
      }
      if (path === '/calls/rooms/room/sessions' && method === 'POST') return jsonResp({ ok: true })
      if (path === '/calls/rooms/room/sessions' && method === 'GET') {
        // First discovery pass (during register) sees no remotes; the second
        // (refreshRoom) sees the guest that shares its screen.
        discoveryCount += 1
        return jsonResp({ sessions: discoveryCount >= 2 ? [guestSession] : [] })
      }
      if (path === '/calls/sessions/me/tracks/new' && method === 'POST') {
        return jsonResp({
          requiresImmediateRenegotiation: true,
          sessionDescription: { type: 'offer', sdp: 'v=0\r\na=mid:1\r\na=mid:2\r\n' },
          tracks: [
            { trackName: 'cam-native', mid: '1' },
            { trackName: 'screen-native', mid: '2' },
          ],
        })
      }
      if (path === '/calls/sessions/me/renegotiate' && method === 'PUT') return jsonResp({ ok: true })
      if (path.includes('/heartbeat') && method === 'PUT') return jsonResp({ ok: true })
      if (path === '/api/cells/execute-ephemeral' && method === 'POST') return jsonResp({ ok: true })
      if (path.includes('/sessions/me') && method === 'DELETE') return jsonResp({ ok: true })
      throw new Error(`Unhandled mock fetch: ${method} ${path}`)
    })
  })

  afterEach(() => {
    if (wrapper) {
      try { (wrapper.vm as any).hangUp?.() } catch { /* teardown best-effort */ }
      wrapper.unmount()
      wrapper = undefined as unknown as VueWrapper
    }
  })

  it('anchors _transceiverMeta for a NEW screen transceiver after setRemoteDescription and resolves the screen to {guest}/screen', async () => {
    wrapper = mountComposable()
    const api = wrapper.vm as any

    await api.startCall('room')
    expect(api.isConnected).toBe(true)

    // Second discovery sees the guest with a screen track → subscribe creates a
    // NEW transceiver for the screen mid during setRemoteDescription → the fix
    // re-anchors _transceiverMeta post-offer.
    await api.refreshRoom()

    // 1. The screen ontrack classified to the dedicated {guest}/screen tile
    //    (NOT an opaque orphan that the prune would remove).
    expect(api.remoteStreams.has('guest/screen')).toBe(true)

    // 2. The fix's second pass anchored the WeakMap for the NEW screen
    //    transceiver — proven by the post-setRemoteDescription DIAG.  The
    //    logger uses printf-style formatting, so the template and the
    //    interpolated args are separate array items:
    //      [ '[DIAG][subscribe] %s: transceiver_meta anchored ... =%d anchored_mids=%j',
    //        remoteSessionId, anchoredCount, anchoredMids ]
    const anchoredLog = warnCalls.find((args) =>
      args.some((a) => typeof a === 'string' && a.includes('transceiver_meta anchored post-setRemoteDescription')))
    expect(anchoredLog).toBeDefined()
    expect(anchoredLog![1]).toBe('guest')      // remote session
    expect(anchoredLog![2]).toBe(1)            // exactly ONE new anchor (the screen)
    expect(JSON.stringify(anchoredLog![3])).toContain('"2"') // the screen mid is anchored
  })

  it('protects a pending screen subscription (screen on the EXISTING video transceiver) from a concurrent prune — ontrack still resolves {guest}/screen', async () => {
    // F7 ciclo 1 proved the REAL mechanism: the screen arrives on the EXISTING
    // video transceiver (mid 1), the first pass anchors its WeakMap
    // (transceiver_meta_sets=1), but a concurrent discovery/prune drops the mid
    // between the population and the ontrack (race H3) → the map/WeakMap are
    // gone at the ontrack → opaque stream.id → the screen never renders.  This
    // test drives that exact ordering: the subscription populates mid 1 and
    // marks it PENDING, the ontrack is DEFERRED, a concurrent STALE discovery
    // runs a prune that would drop the mid — and asserts the pending protection
    // blocks the drop so the deferred ontrack classifies to {guest}/screen.
    class DeferredOntrackPC extends MockRTCPeerConnection {
      async setRemoteDescription(desc: { type?: string; sdp?: string }): Promise<void> {
        this.remoteDescription = desc
        const mids = [...(desc.sdp || '').matchAll(/a=mid:(\S+)/g)].map((m) => m[1])
        for (const mid of mids) {
          let tx = this.transceivers.find((t) => t.mid === mid)
          if (!tx) {
            tx = new MockTransceiver(mid, 'recvonly')
            this.transceivers.push(tx)
          }
        }
        // Only the SFU subscription offer (it carries a NEW m-section mid '2',
        // which the base/local negotiation does not) schedules the screen
        // ontrack.  The screen fires on the EXISTING video transceiver (mid '1')
        // — deferred to a macrotask so a concurrent discovery prune can run in
        // between the population and the ontrack.
        if (mids.includes('2')) {
          const screenTx = this.transceivers.find((t) => t.mid === '1')
          if (screenTx) {
            window.setTimeout(() => {
              this.ontrack?.({
                track: new MockMediaStreamTrack('video', 'screen-track'),
                receiver: { track: { readyState: 'live', muted: false } },
                transceiver: screenTx,
                streams: [],
              })
            }, 0)
          }
        }
      }
    }
    ;(globalThis as any).RTCPeerConnection = DeferredOntrackPC

    let discoveryCount = 0
    const guestSession = {
      sessionId: 'guest',
      tracks: ['screen'],
      trackNames: ['screen-native'],
    }
    ;(globalThis as any).__mockApiFetch = vi.fn(async (path: string, options: RequestInit = {}) => {
      const method = (options.method || 'GET').toUpperCase()
      if (path === '/calls/provision' && method === 'POST') return jsonResp({ status: 'already_exists' })
      if (path === '/calls/session' && method === 'POST') {
        return jsonResp({ sessionId: 'me', sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' } })
      }
      if (path === '/calls/rooms/room/sessions' && method === 'POST') return jsonResp({ ok: true })
      if (path === '/calls/rooms/room/sessions' && method === 'GET') {
        discoveryCount += 1
        // #1 (register): no remotes.  #2 (refreshRoom): the guest shares its
        // screen.  #3 (concurrent refresh): STALE — the guest is ABSENT, so its
        // prune tries to ghost-drop the in-flight screen subscription.
        return jsonResp({ sessions: discoveryCount === 2 ? [guestSession] : [] })
      }
      if (path === '/calls/sessions/me/tracks/new' && method === 'POST') {
        return jsonResp({
          requiresImmediateRenegotiation: true,
          sessionDescription: { type: 'offer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\na=mid:2\r\n' },
          tracks: [{ trackName: 'screen-native', mid: '1' }],
        })
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
    await api.refreshRoom() // discovery #2 — subscribe to the guest's screen (mid 1); ontrack DEFERRED

    // The subscription populated mid 1 and marked it pending (proof the fix's
    // protection is armed for the F7-proven mid-on-existing-transceiver case).
    const markedLog = warnCalls.find((args) =>
      args.some((a) => typeof a === 'string' && a.includes('[DIAG][pending] marked')))
    expect(markedLog).toBeDefined()
    expect(JSON.stringify(markedLog![1])).toContain('"1"') // mid 1 marked pending
    expect(markedLog![2]).toBe('guest')

    // Discovery #3 is a STALE snapshot (guest absent) → its prune targets the
    // in-flight subscription.  The pending protection must block the drop.
    await api.refreshRoom()
    const protectLog = warnCalls.find((args) =>
      args.some((a) => typeof a === 'string' && a.includes('[DIAG][pending] protect')))
    expect(protectLog).toBeDefined()
    expect(protectLog![0]).toContain('prune=owner') // the owner prune was deferred

    // Now the deferred ontrack fires → mid 1 is STILL mapped (protection held)
    // → classifies to the dedicated {guest}/screen tile (NOT an opaque orphan).
    await new Promise((resolve) => setTimeout(resolve, 0))
    const clearedLog = warnCalls.find((args) =>
      args.some((a) => typeof a === 'string' && a.includes('[DIAG][pending] cleared on ontrack')))
    expect(clearedLog).toBeDefined()
    expect(clearedLog![1]).toBe('1')           // mid 1 released
    expect(api.remoteStreams.has('guest/screen')).toBe(true)
  })

  // ── Shared mock fetch for the CICLO 3 tests ──────────────────────────────
  // Guest shares its screen; the SFU's tracks/new offer maps the screen to the
  // EXISTING video transceiver mid '1' (the F7-proven reused-transceiver case).
  // Discovery #1 (register) sees no remotes; #2 (refreshRoom) sees the guest.
  function mockGuestShareOnExistingMidFetch(): void {
    let discoveryCount = 0
    const guestSession = {
      sessionId: 'guest',
      tracks: ['screen'],
      trackNames: ['screen-native'],
    }
    ;(globalThis as any).__mockApiFetch = vi.fn(async (path: string, options: RequestInit = {}) => {
      const method = (options.method || 'GET').toUpperCase()
      if (path === '/calls/provision' && method === 'POST') return jsonResp({ status: 'already_exists' })
      if (path === '/calls/session' && method === 'POST') {
        return jsonResp({ sessionId: 'me', sessionDescription: { type: 'answer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\n' } })
      }
      if (path === '/calls/rooms/room/sessions' && method === 'POST') return jsonResp({ ok: true })
      if (path === '/calls/rooms/room/sessions' && method === 'GET') {
        discoveryCount += 1
        return jsonResp({ sessions: discoveryCount >= 2 ? [guestSession] : [] })
      }
      if (path === '/calls/sessions/me/tracks/new' && method === 'POST') {
        return jsonResp({
          requiresImmediateRenegotiation: true,
          sessionDescription: { type: 'offer', sdp: 'v=0\r\na=mid:0\r\na=mid:1\r\na=mid:2\r\n' },
          tracks: [{ trackName: 'screen-native', mid: '1' }],
        })
      }
      if (path === '/calls/sessions/me/renegotiate' && method === 'PUT') return jsonResp({ ok: true })
      if (path.includes('/heartbeat') && method === 'PUT') return jsonResp({ ok: true })
      if (path === '/api/cells/execute-ephemeral' && method === 'POST') return jsonResp({ ok: true })
      if (path.includes('/sessions/me') && method === 'DELETE') return jsonResp({ ok: true })
      throw new Error(`Unhandled mock fetch: ${method} ${path}`)
    })
  }

  it('keeps {guest}/screen when the reused-transceiver track arrives ended/muted — stale end-handler bind is skipped so spurious mute/ended do NOT remove the tile', async () => {
    // F7 confirmed the mechanism: the SFU reuses the EXISTING video transceiver
    // (mid 1) to deliver the screen, and the ontrack carries the STALE track —
    // receiver_readyState=ended receiver_muted=true (echo of the pruned camera).
    // Before the fix, _bindTrackEndHandlers bound onmute/onended to that stale
    // track, Chrome fired them right after the ontrack, and the tile was removed
    // in the SAME dispatch.  The fix (candidate 1) skips binding end handlers for
    // an already-ended track → the tile survives.
    let staleTrackRef: MockMediaStreamTrack | null = null
    class StaleOntrackPC extends MockRTCPeerConnection {
      async setRemoteDescription(desc: { type?: string; sdp?: string }): Promise<void> {
        this.remoteDescription = desc
        const mids = [...(desc.sdp || '').matchAll(/a=mid:(\S+)/g)].map((m) => m[1])
        for (const mid of mids) {
          let tx = this.transceivers.find((t) => t.mid === mid)
          if (!tx) {
            tx = new MockTransceiver(mid, 'recvonly')
            this.transceivers.push(tx)
          }
        }
        if (mids.includes('2')) {
          const screenTx = this.transceivers.find((t) => t.mid === '1')
          if (screenTx) {
            const staleTrack = new MockMediaStreamTrack('video', 'stale-cam-echo')
            staleTrack.readyState = 'ended'
            staleTrack.muted = true
            staleTrackRef = staleTrack
            const staleStream = new MockMediaStream()
            staleStream.addTrack(staleTrack)
            this.ontrack?.({
              track: staleTrack,
              receiver: { track: { readyState: 'ended', muted: true } },
              transceiver: screenTx,
              streams: [staleStream],
            })
          }
        }
      }
    }
    ;(globalThis as any).RTCPeerConnection = StaleOntrackPC
    mockGuestShareOnExistingMidFetch()

    wrapper = mountComposable()
    const api = wrapper.vm as any

    await api.startCall('room')
    await api.refreshRoom() // discovery #2 — subscribe to the guest's screen (stale track on mid 1)

    // The screen tile ENTERED the Map (the merge executed).
    expect(api.remoteStreams.has('guest/screen')).toBe(true)

    // The fix skipped the stale end-handler bind (candidate 1).
    const bindSkipLog = warnCalls.find((args) =>
      args.some((a) => typeof a === 'string' && a.includes('[DIAG][bind-skip]')))
    expect(bindSkipLog).toBeDefined()

    // Simulate Chrome firing mute/ended on the stale track after the ontrack —
    // the spurious events that previously removed the tile in the SAME dispatch.
    // The cleanup handlers are NOT bound → the tile survives.
    // TS cannot trace the assignment inside the mock's async method, so it
    // narrows `staleTrackRef` to `null`/`never` — cast the initializer back to
    // the union so the `if (staleTrack)` guard narrows to the mock type.
    const staleTrack = staleTrackRef as MockMediaStreamTrack | null
    if (staleTrack) {
      staleTrack.onended?.()
      staleTrack.onmute?.()
    }
    expect(api.remoteStreams.has('guest/screen')).toBe(true)

    // No spurious removal of the screen tile occurred.
    const cleanupRemovedLog = warnCalls.find((args) =>
      args.some((a) => typeof a === 'string' && a.includes('[DIAG][cleanup] removed key=guest/screen')))
    expect(cleanupRemovedLog).toBeUndefined()
  })

  it('grace guard blocks a same-dispatch mute on a live-but-muted screen track, but a real end after the grace period still cleans up', async () => {
    // Edge case the confirmed ended-track fix does NOT cover: a screen track that
    // arrives LIVE but MUTED (not skipped by candidate 1) — Chrome can still fire
    // mute right after the ontrack.  The grace guard (candidate 2) blocks the
    // same-dispatch removal, while a REAL end (mute persists past the grace
    // window, i.e. the publisher actually stopped) still tears down normally.
    let mutedTrackRef: MockMediaStreamTrack | null = null
    class MutedOntrackPC extends MockRTCPeerConnection {
      async setRemoteDescription(desc: { type?: string; sdp?: string }): Promise<void> {
        this.remoteDescription = desc
        const mids = [...(desc.sdp || '').matchAll(/a=mid:(\S+)/g)].map((m) => m[1])
        for (const mid of mids) {
          let tx = this.transceivers.find((t) => t.mid === mid)
          if (!tx) {
            tx = new MockTransceiver(mid, 'recvonly')
            this.transceivers.push(tx)
          }
        }
        if (mids.includes('2')) {
          const screenTx = this.transceivers.find((t) => t.mid === '1')
          if (screenTx) {
            const mutedTrack = new MockMediaStreamTrack('video', 'muted-screen-track')
            mutedTrack.readyState = 'live'
            mutedTrack.muted = true
            mutedTrackRef = mutedTrack
            const mStream = new MockMediaStream()
            mStream.addTrack(mutedTrack)
            this.ontrack?.({
              track: mutedTrack,
              receiver: { track: { readyState: 'live', muted: true } },
              transceiver: screenTx,
              streams: [mStream],
            })
          }
        }
      }
    }
    ;(globalThis as any).RTCPeerConnection = MutedOntrackPC
    mockGuestShareOnExistingMidFetch()

    wrapper = mountComposable()
    const api = wrapper.vm as any

    await api.startCall('room')
    await api.refreshRoom()
    expect(api.remoteStreams.has('guest/screen')).toBe(true)

    // The track is LIVE but MUTED → candidate 1 does NOT skip → onmute IS bound
    // (gate=screen).  Firing it in the same dispatch is the spurious case → the
    // grace guard blocks the removal and the tile survives.
    const mutedTrack = mutedTrackRef!
    mutedTrack.onmute?.()
    expect(api.remoteStreams.has('guest/screen')).toBe(true)
    const blockedLog = warnCalls.find((args) =>
      args.some((a) => typeof a === 'string' && a.includes('[DIAG][cleanup] blocked')))
    expect(blockedLog).toBeDefined()

    // After the grace window, a REAL end (mute persists — publisher actually
    // stopped) cleans up normally: the tile is removed.
    await new Promise((resolve) => setTimeout(resolve, 550))
    mutedTrack.onmute?.()
    expect(api.remoteStreams.has('guest/screen')).toBe(false)
  })
})
