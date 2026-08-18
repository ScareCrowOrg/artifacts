/**
 * @vitest-environment jsdom
 *
 * F3 FIX (ITER_1 guest-screenshare) — unit tests for the asymmetric screen-share
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
 * The shared WebRTC mocks + mount harness live in `usePartyCalls.testBed.ts`
 * (extracted so no test file exceeds RULESET 1.1's >1000-line blocker).  The
 * bug-hardening tests (G1/F1-F11) live in `usePartyCalls.bugHardening.test.ts`.
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
  MockMediaStreamTrack,
  MockMediaStream,
  MockTransceiver,
  MockRTCPeerConnection,
  jsonResp,
  mountComposable,
  setupTestBed,
} from './usePartyCalls.testBed'

// ── Test wrapper ────────────────────────────────────────────────────────────
let wrapper: VueWrapper

describe('usePartyCalls — guest screen-share transceiver meta anchoring', () => {
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

  it('anchors _transceiverMeta for a NEW screen transceiver after setRemoteDescription and resolves the screen to {guest}/screen', async () => {
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
    //    interpolated args are separate array items.
    const anchoredLog = warnCalls.find((args) =>
      args.some((a) => typeof a === 'string' && a.includes('transceiver_meta anchored post-setRemoteDescription')))
    expect(anchoredLog).toBeDefined()
    expect(anchoredLog![1]).toBe('guest')      // remote session
    expect(anchoredLog![2]).toBe(1)            // exactly ONE new anchor (the screen)
    expect(JSON.stringify(anchoredLog![3])).toContain('"2"') // the screen mid is anchored
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
      args.some((a) => typeof a === 'string' && a.includes('[bind-skip]')))
    expect(bindSkipLog).toBeDefined()

    // Simulate Chrome firing mute/ended on the stale track after the ontrack —
    // the spurious events that previously removed the tile in the SAME dispatch.
    // The cleanup handlers are NOT bound → the tile survives.
    const staleTrack = staleTrackRef as MockMediaStreamTrack | null
    if (staleTrack) {
      staleTrack.onended?.()
      staleTrack.onmute?.()
    }
    expect(api.remoteStreams.has('guest/screen')).toBe(true)

    // No spurious removal of the screen tile occurred.
    const cleanupRemovedLog = warnCalls.find((args) =>
      args.some((a) => typeof a === 'string' && a.includes('[cleanup] removed key=guest/screen')))
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
      args.some((a) => typeof a === 'string' && a.includes('[cleanup] blocked')))
    expect(blockedLog).toBeDefined()

    // After the grace window, a REAL end (mute persists — publisher actually
    // stopped) cleans up normally: the tile is removed.
    await new Promise((resolve) => setTimeout(resolve, 550))
    mutedTrack.onmute?.()
    expect(api.remoteStreams.has('guest/screen')).toBe(false)
  })
})
