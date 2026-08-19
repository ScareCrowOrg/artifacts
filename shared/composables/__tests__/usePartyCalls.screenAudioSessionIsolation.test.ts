/**
 * @vitest-environment jsdom
 *
 * Unit tests for issue `party-calls-screen-audio-session-isolation`:
 *
 *   Ajuste 1 — the shared screen carries its DISPLAY AUDIO (when the sharer left
 *   "share tab audio" checked) as a DEDICATED sendonly track registered in the
 *   same tracks/new; the subscriber receives it merged into the {sid}/screen
 *   tile; stopSharing removes BOTH video + audio from the SFU (symmetric);
 *   sharing WITHOUT display audio stays video-only (no regression).
 *
 *   Ajuste 2 — F13: the screen-share state is PER-INSTANCE (ctx.screenState), so
 *   a party-cell + glb-content-viewer on the same page (same room, shared
 *   PC/session) no longer clobber each other: a stop on one instance never stops
 *   the other's stream, and the 2nd share reuses the SAME PC (1 participant = 1
 *   connection within the room).
 *
 * The shared WebRTC mocks + mount harness live in `usePartyCalls.testBed.ts`.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref } from 'vue'
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
  _remoteTrackTypes,
  _remoteMidToTrackName,
  _subscribedTrackNames,
  _subscribedSessions,
} from '../party-calls/state'
import { _handleRemoteTrack } from '../party-calls/remoteMedia'
import {
  MockMediaStreamTrack,
  MockMediaStream,
  MockTransceiver,
  jsonResp,
  mountComposable,
  setupTestBed,
} from './usePartyCalls.testBed'

let wrapper: VueWrapper
let wrapperB: VueWrapper

/** Build the answer SDP from the current transceivers so the mock's
 *  setRemoteDescription finds every mid (no spurious ontrack). */
function answerSdp(): string {
  const mids = (state._pc as any).getTransceivers().map((t: { mid: string | null }) => t.mid).filter(Boolean)
  return `v=0\r\n${mids.map((m: string) => `a=mid:${m}`).join('\r\n')}`
}

/** Base mock fetch: single room 'room', no remote sessions, one participant
 *  ('me').  Counts local publish calls + the tracks each publish carried, and
 *  collects the mids removed via DELETE tracks/{mid}. */
function baseFetch() {
  const counters = {
    publishCalls: 0,
    publishedTrackNames: [] as string[][],
    removedMids: [] as string[],
    heartbeatCalls: 0,
  }
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
      const tracks = body.tracks ?? []
      const isLocal = tracks.length > 0 && tracks.every((t: { location: string }) => t.location === 'local')
      if (isLocal) {
        counters.publishCalls += 1
        counters.publishedTrackNames.push(tracks.map((t: { trackName: string }) => t.trackName))
        return jsonResp({
          sessionDescription: { type: 'answer', sdp: answerSdp() },
        })
      }
      // Remote subscription — no remote sessions in this suite, return no-op.
      return jsonResp({ ok: true })
    }
    const delMatch = path.match(/^\/calls\/sessions\/me\/tracks\/(.+)$/)
    if (delMatch && method === 'DELETE') {
      counters.removedMids.push(decodeURIComponent(delMatch[1]))
      return jsonResp({ ok: true })
    }
    if (path === '/calls/sessions/me/renegotiate' && method === 'PUT') return jsonResp({ ok: true })
    if (path.includes('/heartbeat') && method === 'PUT') {
      counters.heartbeatCalls += 1
      return jsonResp({ ok: true })
    }
    if (path === '/api/cells/execute-ephemeral' && method === 'POST') return jsonResp({ ok: true })
    if (path.includes('/sessions/me') && method === 'DELETE') return jsonResp({ ok: true })
    throw new Error(`Unhandled mock fetch: ${method} ${path}`)
  })
  return counters
}

/** A fake display stream with only a VIDEO track (user unchecked "share audio"). */
function fakeVideoOnlyStream(id = 'my-screen-id'): MockMediaStream {
  const stream = new MockMediaStream()
  stream.addTrack(new MockMediaStreamTrack('video', id))
  return stream
}

/** A fake display stream with VIDEO + DISPLAY-AUDIO tracks (tab audio on). */
function fakeScreenWithAudio(videoId = 'my-screen-id', audioId = 'my-audio-id'): MockMediaStream {
  const stream = new MockMediaStream()
  stream.addTrack(new MockMediaStreamTrack('video', videoId))
  stream.addTrack(new MockMediaStreamTrack('audio', audioId))
  return stream
}

describe('usePartyCalls — Ajuste 1: screen display-audio', () => {
  beforeEach(() => {
    setupTestBed()
    warnCalls.length = 0
    // Clean the module-level remote maps so a direct _handleRemoteTrack test
    // cannot leak classification into the next test.
    _remoteTrackTypes.clear()
    _remoteMidToTrackName.clear()
    _subscribedTrackNames.clear()
    _subscribedSessions.clear()
  })

  afterEach(() => {
    if (wrapperB) {
      try { (wrapperB.vm as any).hangUp?.() } catch { /* teardown best-effort */ }
      wrapperB.unmount()
      wrapperB = undefined as unknown as VueWrapper
    }
    if (wrapper) {
      try { (wrapper.vm as any).hangUp?.() } catch { /* teardown best-effort */ }
      wrapper.unmount()
      wrapper = undefined as unknown as VueWrapper
    }
  })

  it('E1: a share WITH display audio registers BOTH tracks (video + audio) in ONE tracks/new, publishes [screen, screenAudio] to the registry, and tracks the audio id', async () => {
    const counters = baseFetch()
    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')

    await api.shareStream(fakeScreenWithAudio())

    // ONE tracks/new call carrying BOTH the video and the audio native ids.
    expect(counters.publishCalls).toBe(1)
    expect(counters.publishedTrackNames).toHaveLength(1)
    const names = counters.publishedTrackNames[0]
    expect(names).toContain('my-screen-id')
    expect(names).toContain('my-audio-id')
    expect(names).toHaveLength(2)

    // Registry/presence honest: ['screen', 'screenAudio'] with both native ids.
    expect(state._publishedTracks).toEqual(['screen', 'screenAudio'])
    expect(state._publishedTrackNames).toEqual(['my-screen-id', 'my-audio-id'])
    // The audio native id is tracked for the symmetric stopSharing cleanup.
    expect(state._screenAudioTrackId).toBe('my-audio-id')
    expect(api.isSharingScreen).toBe(true)
    // Two dedicated sendonly transceivers — video AND audio.
    const sendonly = (state._pc as any).getTransceivers().filter((t: any) => t.direction === 'sendonly')
    expect(sendonly).toHaveLength(2)
  })

  it('E2: the subscriber classifies a screen DISPLAY-AUDIO track into the {owner}/screen tile — merged with the screen video, separate from the mic stream', () => {
    // Publisher 'publisher' published tracks ['screen','screenAudio'] →
    // _remoteTrackTypes maps the audio native id to 'screenAudio'.
    _remoteTrackTypes.set('publisher', new Map([
      ['pub-video-id', 'screen'],
      ['pub-audio-id', 'screenAudio'],
    ]))
    // The subscribe resolved mid '9' → the publisher's audio track.
    const audioTx = new MockTransceiver('9', 'recvonly')
    _remoteMidToTrackName.set('9', { sessionId: 'publisher', trackName: 'pub-audio-id' })

    const remoteStreams = ref(new Map<string, MediaStream>())
    _handleRemoteTrack({
      track: new MockMediaStreamTrack('audio', 'opaque-audio-id'),
      receiver: { track: { readyState: 'live', muted: false } },
      transceiver: audioTx,
      streams: [],
    } as any, remoteStreams)

    // The audio merges into the SCREEN tile ({owner}/screen), not the mic tile
    // ({owner}) — so the receiver can mute only the screen sound.
    const screenTile = remoteStreams.value.get('publisher/screen')
    expect(screenTile).toBeDefined()
    expect(screenTile!.getTracks().some((t) => t.kind === 'audio')).toBe(true)
    expect(remoteStreams.value.has('publisher')).toBe(false) // mic NOT touched
  })

  it('E3: stopSharing does a SYMMETRIC cleanup — removes BOTH SFU tracks (video + audio mids), stops the stream, clears both ids, and drops screen/screenAudio from the registry', async () => {
    const counters = baseFetch()
    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')
    const stream = fakeScreenWithAudio()
    await api.shareStream(stream)

    await api.stopSharing()

    // Both the video AND the audio sendonly transceivers were removed from the
    // SFU via tracks/close (2 mids).
    expect(counters.removedMids).toHaveLength(2)
    expect(state._screenTrackId).toBeNull()
    expect(state._screenAudioTrackId).toBeNull()
    expect(state._screenStream).toBeNull()
    expect(api.isSharingScreen).toBe(false)
    // The display stream was stopped (leak fix).
    expect(stream.getTracks()[0].readyState).toBe('ended')
    // Registry/presence honest after the stop.
    expect(state._publishedTracks).not.toContain('screen')
    expect(state._publishedTracks).not.toContain('screenAudio')
    // The orphans were captured for transceiver reuse (A1) — video AND audio.
    expect(state._orphanScreenTx?.sender.track).toBeNull()
    expect(state._orphanScreenAudioTx?.sender.track).toBeNull()
  })

  it('E4: a share WITHOUT display audio (getAudioTracks() empty) stays video-only — no regression', async () => {
    const counters = baseFetch()
    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')

    await api.shareStream(fakeVideoOnlyStream())

    // ONE track registered — the video only.
    expect(counters.publishCalls).toBe(1)
    expect(counters.publishedTrackNames[0]).toEqual(['my-screen-id'])
    // Registry/presence honest: ['screen'], no 'screenAudio'.
    expect(state._publishedTracks).toEqual(['screen'])
    expect(state._publishedTrackNames).toEqual(['my-screen-id'])
    expect(state._screenAudioTrackId).toBeNull()
    expect(api.isSharingScreen).toBe(true)
    // Only ONE sendonly transceiver (video).
    const sendonly = (state._pc as any).getTransceivers().filter((t: any) => t.direction === 'sendonly')
    expect(sendonly).toHaveLength(1)
  })

  it('E5: a share with audio reuses the audio ORPHAN from the previous stop — no audio transceiver stacking per share/stop cycle (A1 symmetric)', async () => {
    const counters = baseFetch()
    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')

    const stream1 = fakeScreenWithAudio('screen-1', 'audio-1')
    const stream2 = fakeScreenWithAudio('screen-2', 'audio-2')
    await api.shareStream(stream1)
    const sendonlyAfterFirst = (state._pc as any).getTransceivers().filter((t: any) => t.direction === 'sendonly')
    expect(sendonlyAfterFirst).toHaveLength(2)
    await api.stopSharing()

    await api.shareStream(stream2)
    // The second share REUSED the 2 orphaned transceivers (video + audio) — no
    // new sendonly transceiver was added.
    const sendonlyAfterSecond = (state._pc as any).getTransceivers().filter((t: any) => t.direction === 'sendonly')
    expect(sendonlyAfterSecond).toHaveLength(2)
    expect(counters.publishCalls).toBe(2)
  })
})

describe('usePartyCalls — Ajuste 2 (F13): per-instance screen state', () => {
  beforeEach(() => {
    setupTestBed()
    warnCalls.length = 0
  })

  afterEach(() => {
    if (wrapperB) {
      try { (wrapperB.vm as any).hangUp?.() } catch { /* teardown best-effort */ }
      wrapperB.unmount()
      wrapperB = undefined as unknown as VueWrapper
    }
    if (wrapper) {
      try { (wrapper.vm as any).hangUp?.() } catch { /* teardown best-effort */ }
      wrapper.unmount()
      wrapper = undefined as unknown as VueWrapper
    }
  })

  it('F1: 2 instances on the same page/room SHARE the PC/session — the 2nd shareStream (no startCall) piggybacks on the 1st and does NOT disrupt its connection', async () => {
    const counters = baseFetch()
    wrapper = mountComposable()      // instance A — the party-cell
    wrapperB = mountComposable()     // instance B — the glb-content-viewer
    const apiA = wrapper.vm as any
    const apiB = wrapperB.vm as any

    await apiA.startCall('room')
    const pcAfterStart = state._pc
    expect(apiA.isConnected).toBe(true)

    // B shares WITHOUT calling startCall — it must reuse A's PC/session
    // (1 participant = 1 connection within the room).
    await apiB.shareStream(fakeVideoOnlyStream('stream-B-video'))
    expect(state._pc).toBe(pcAfterStart) // same PC — no second connection
    expect(apiA.isConnected).toBe(true) // A's call survived B's share

    // A's connection was not disrupted by B's piggyback share.
    expect((state._pc as any).signalingState).toBe('stable')
  })

  it('F2: a stop on instance A never stops instance B\'s share (F13 — per-instance screen state)', async () => {
    const counters = baseFetch()
    wrapper = mountComposable()      // instance A — the party-cell
    wrapperB = mountComposable()     // instance B — the glb-content-viewer
    const apiA = wrapper.vm as any
    const apiB = wrapperB.vm as any

    await apiA.startCall('room')
    const streamA = fakeVideoOnlyStream('stream-A-video')
    const streamB = fakeVideoOnlyStream('stream-B-video')
    await apiA.shareStream(streamA)
    await apiB.shareStream(streamB)

    // Both instances share independently (the pre-fix singleton would have had
    // B's share clobber A's state).
    expect(apiA.isSharingScreen).toBe(true)
    expect(apiB.isSharingScreen).toBe(true)

    // A stops ITS share — only A's stream is stopped; B's stream stays live.
    await apiA.stopSharing()
    expect(streamA.getTracks()[0].readyState).toBe('ended')   // A's video stopped
    expect(streamB.getTracks()[0].readyState).toBe('live')    // B's video untouched
    expect(apiA.isSharingScreen).toBe(false)
    expect(apiB.isSharingScreen).toBe(true)                   // B still sharing

    // B stops its own share cleanly too.
    await apiB.stopSharing()
    expect(streamB.getTracks()[0].readyState).toBe('ended')
    expect(apiB.isSharingScreen).toBe(false)
  })
})

describe('usePartyCalls — review fixes (R1-R6, REVIEW_REPORT.md)', () => {
  beforeEach(() => {
    setupTestBed()
    warnCalls.length = 0
    _remoteTrackTypes.clear()
    _remoteMidToTrackName.clear()
    _subscribedTrackNames.clear()
    _subscribedSessions.clear()
  })

  afterEach(() => {
    if (wrapperB) {
      try { (wrapperB.vm as any).hangUp?.() } catch { /* teardown best-effort */ }
      wrapperB.unmount()
      wrapperB = undefined as unknown as VueWrapper
    }
    if (wrapper) {
      try { (wrapper.vm as any).hangUp?.() } catch { /* teardown best-effort */ }
      wrapper.unmount()
      wrapper = undefined as unknown as VueWrapper
    }
  })

  it('R1: a DISPLAY-AUDIO track that mutes or ends does NOT remove the {owner}/screen tile — only the VIDEO\'s mute/end signals a stop (regression fix)', () => {
    // Publisher 'publisher' shared BOTH screen video + display-audio.
    _remoteTrackTypes.set('publisher', new Map([
      ['pub-video-id', 'screen'],
      ['pub-audio-id', 'screenAudio'],
    ]))
    // Video arrives first → creates the tile.
    const videoTx = new MockTransceiver('9', 'recvonly')
    _remoteMidToTrackName.set('9', { sessionId: 'publisher', trackName: 'pub-video-id' })
    const remoteStreams = ref(new Map<string, MediaStream>())
    const videoTrack = new MockMediaStreamTrack('video', 'opaque-video-id')
    _handleRemoteTrack({
      track: videoTrack,
      receiver: { track: { readyState: 'live', muted: false } },
      transceiver: videoTx,
      streams: [],
    } as any, remoteStreams)
    expect(remoteStreams.value.has('publisher/screen')).toBe(true)

    // The display-audio track merges into the SAME tile.
    const audioTx = new MockTransceiver('10', 'recvonly')
    _remoteMidToTrackName.set('10', { sessionId: 'publisher', trackName: 'pub-audio-id' })
    const audioTrack = new MockMediaStreamTrack('audio', 'opaque-audio-id')
    _handleRemoteTrack({
      track: audioTrack,
      receiver: { track: { readyState: 'live', muted: false } },
      transceiver: audioTx,
      streams: [],
    } as any, remoteStreams)
    const tile = remoteStreams.value.get('publisher/screen')
    expect(tile!.getTracks().length).toBe(2) // video + audio merged

    // Audio mute is reversible — the tile stays.
    audioTrack.onmute?.()
    expect(remoteStreams.value.has('publisher/screen')).toBe(true)

    // Audio end drops ONLY the audio mapping — the screen tile (video) stays.
    audioTrack.onended?.()
    expect(remoteStreams.value.has('publisher/screen')).toBe(true)
    expect(_remoteTrackTypes.get('publisher')?.has('pub-audio-id')).toBe(false)
    expect(_remoteTrackTypes.get('publisher')?.has('pub-video-id')).toBe(true)
  })

  it('R2: a share on instance B does NOT steal instance A\'s orphan — B creates a fresh transceiver and A\'s re-share reuses A\'s own, never clobbering B (F13 fallback fix)', async () => {
    baseFetch()
    wrapper = mountComposable()      // A — party-cell
    wrapperB = mountComposable()     // B — glb-content-viewer
    const apiA = wrapper.vm as any
    const apiB = wrapperB.vm as any

    await apiA.startCall('room')
    // A shares and stops → A's video transceiver becomes A's orphan (VA).
    await apiA.shareStream(fakeVideoOnlyStream('stream-A-1'))
    await apiA.stopSharing()
    const va = state._orphanScreenTx
    expect(va).not.toBeNull()

    // B shares → must NOT reuse A's orphan (fresh transceiver VB with B's video).
    await apiB.shareStream(fakeVideoOnlyStream('stream-B-video'))
    const vb = (state._pc as any).getTransceivers()
      .find((t: any) => t.sender?.track?.id === 'stream-B-video')
    expect(vb).toBeDefined()
    expect(vb).not.toBe(va) // fresh transceiver — the fix

    // A re-shares → reuses A's OWN orphan VA, and B's transceiver is untouched.
    await apiA.shareStream(fakeVideoOnlyStream('stream-A-2'))
    const va2 = (state._pc as any).getTransceivers()
      .find((t: any) => t.sender?.track?.id === 'stream-A-2')
    expect(va2).toBe(va) // reused A's own orphan
    // B's share is still intact (the pre-fix fallback would have clobbered it).
    expect((state._pc as any).getTransceivers()
      .some((t: any) => t.sender?.track?.id === 'stream-B-video')).toBe(true)
    expect(apiB.isSharingScreen).toBe(true)
  })

  it('R3: shareStream on an unhealthy PC fails fast with a friendly error and leaves NO half-set share state', async () => {
    baseFetch()
    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')

    // A PC in a terminal ICE state (or mid-renegotiation) must abort BEFORE any
    // transceiver allocation / state is set (the old code allocated first and
    // left self-view stuck on the screen on InvalidStateError).
    ;(state._pc as any).iceConnectionState = 'failed'

    await api.shareStream(fakeVideoOnlyStream('my-screen-id'))

    expect(api.connectionError).toContain('not ready')
    expect(api.isSharingScreen).toBe(false)
    expect(state._screenStream).toBeNull()
    expect(state._screenTrackId).toBeNull()
    // No transceiver was allocated for a share that never started.
    const sendonly = (state._pc as any).getTransceivers()
      .filter((t: any) => t.direction === 'sendonly')
    expect(sendonly).toHaveLength(0)
  })

  it('R4: a republish from instance A keeps instance B\'s screen in the registry (merge of all active instances)', async () => {
    baseFetch()
    wrapper = mountComposable()      // A
    wrapperB = mountComposable()     // B
    const apiA = wrapper.vm as any
    const apiB = wrapperB.vm as any

    await apiA.startCall('room')
    await apiA.shareStream(fakeVideoOnlyStream('stream-A-video'))
    // B shares via piggyback (no startCall → no roomId of its own, so B cannot
    // itself republish) — but B's screen contribution is registered in the
    // shared-session registry (`_activeScreenIdsByInstance`).
    await apiB.shareStream(fakeVideoOnlyStream('stream-B-video'))

    // A stops its OWN share → the republish must MERGE B's screen ids into the
    // registry (a per-instance-only republish would drop them → subscribers
    // prune B's live screen tile).
    await apiA.stopSharing()
    expect(state._publishedTrackNames).toContain('stream-B-video')
    expect(state._publishedTrackNames).not.toContain('stream-A-video')
    expect(state._publishedTracks).toContain('screen') // B's screen still advertised
  })

  it('R5: hangUp on instance A while B is sharing is a SOFT hang-up — the shared PC/session survives and B\'s share keeps flowing', async () => {
    baseFetch()
    wrapper = mountComposable()      // A — party-cell (owns the call)
    wrapperB = mountComposable()     // B — glb-content-viewer (piggyback)
    const apiA = wrapper.vm as any
    const apiB = wrapperB.vm as any

    await apiA.startCall('room')
    const streamA = fakeVideoOnlyStream('stream-A-video')
    const streamB = fakeVideoOnlyStream('stream-B-video')
    await apiA.shareStream(streamA)
    await apiB.shareStream(streamB)

    // A unmounts → hangUp.  B is still sharing the shared session, so A's
    // hangUp must NOT close the PC (the pre-fix hard teardown killed B's share).
    apiA.hangUp()
    expect(state._pc).not.toBeNull()              // shared PC kept
    expect(state._currentSessionId).not.toBeNull() // session kept
    expect(apiB.isSharingScreen).toBe(true)       // B still sharing
    expect(streamB.getTracks()[0].readyState).toBe('live')
    expect(streamA.getTracks()[0].readyState).toBe('ended') // A's own capture stopped

    // When B also hangs up (the last instance), the FULL teardown runs.
    apiB.hangUp()
    expect(state._pc).toBeNull()
  })

  it('R6: stopSharing logs a warning when the display-AUDIO transceiver has no mid (symmetric to the video path)', async () => {
    baseFetch()
    wrapper = mountComposable()
    const api = wrapper.vm as any
    await api.startCall('room')

    const stream = fakeScreenWithAudio('screen-id', 'audio-id')
    await api.shareStream(stream)
    // Null the audio transceiver's mid so the tracks/close cannot target it.
    const audioTx = (state._pc as any).getTransceivers()
      .find((t: any) => t.sender?.track?.id === 'audio-id')
    expect(audioTx).toBeDefined()
    audioTx.mid = null

    await api.stopSharing()

    const warned = warnCalls.some((args) =>
      args.some((a) => typeof a === 'string' && a.includes('cannot remove screen AUDIO track from SFU')))
    expect(warned).toBe(true)
    // The video track still cleaned up normally.
    expect(stream.getTracks()[0].readyState).toBe('ended')
  })
})
