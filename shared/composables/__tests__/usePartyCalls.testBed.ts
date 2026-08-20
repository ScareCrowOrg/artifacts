/**
 * @file usePartyCalls.testBed.ts — SHARED test harness for the usePartyCalls
 * suites (usePartyCalls.test.ts + usePartyCalls.bugHardening.test.ts).
 *
 * Extracted from the former single usePartyCalls.test.ts so no test file
 * exceeds RULESET 1.1 (>1000 lines = absolute blocker).  The harness owns ONLY
 * the pure WebRTC mock classes + response helpers + the composable mount
 * harness.
 *
 * ⚠️ The `vi.mock` calls (logger / apiService / useDistributedState) are NOT
 * here — vitest's vi.mock must be registered in EACH TEST FILE (hoisted to its
 * top) so it applies to that file's module graph.  Each test file declares its
 * own hoisted `warnCalls` + the three vi.mock factories, then imports this
 * harness.
 */

import { vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { createPinia, setActivePinia, type Pinia } from 'pinia'

// ── WebRTC mocks (jsdom has no RTCPeerConnection/MediaStream) ───────────────

export class MockMediaStreamTrack {
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
  stop(): void { this.readyState = 'ended' }
  addEventListener(type: string, listener: (ev?: unknown) => void): void {
    // Minimal support for the F3 native "Stop sharing" ended handler.
    if (type === 'ended') this.onended = listener as () => void
  }
}

export class MockMediaStream {
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

export class MockTransceiver {
  mid: string | null
  direction: string
  stopped = false
  sender: { track: MockMediaStreamTrack | null; replaceTrack: ReturnType<typeof vi.fn> }
  receiver: { track: { readyState: string; muted: boolean } & Partial<MockMediaStreamTrack> }
  /** 2B (party-cell-screen-share-sfu-register-fail): the codec list passed to
   *  setCodecPreferences, if the screen share applied the VP8/H264 filter. */
  codecPreferences: Array<{ mimeType: string }> = []
  setCodecPreferences: ReturnType<typeof vi.fn>
  constructor(mid: string | null, direction: string) {
    this.mid = mid
    this.direction = direction
    this.sender = {
      track: null,
      // Faithful replaceTrack: mutates sender.track like the real browser
      // (null detaches, a track attaches) so the orphan-reuse + G2-detach flows
      // are testable.
      replaceTrack: vi.fn(async (track: MockMediaStreamTrack | null) => { this.sender.track = track }),
    }
    this.receiver = { track: { readyState: 'live', muted: false } }
    // Capture the filtered codecs so tests can assert the offer carries only
    // VP8/H264 (2B) — mirrors the real browser API.
    this.setCodecPreferences = vi.fn((codecs: Array<{ mimeType: string }>) => { this.codecPreferences = codecs })
  }
  stop(): void { this.stopped = true }
}

export class MockRTCPeerConnection {
  transceivers: MockTransceiver[] = []
  localDescription: unknown = null
  remoteDescription: unknown = null
  oniceconnectionstatechange: (() => void) | null = null
  ontrack: ((ev: unknown) => void) | null = null
  iceConnectionState = 'connected'
  /** Mirrors the real PC's JSEP state so the 2D stable-signaling guard
   *  (_ensurePcReadyForNegotiation) is testable: offer → have-local-offer /
   *  have-remote-offer, answer/rollback → stable. */
  signalingState: string = 'stable'

  addTransceiver(trackOrKind: string | MockMediaStreamTrack, init?: { direction?: string }): MockTransceiver {
    const kind = typeof trackOrKind === 'string' ? trackOrKind : trackOrKind.kind
    const tx = new MockTransceiver(null, init?.direction ?? 'sendrecv')
    if (typeof trackOrKind !== 'string') tx.sender.track = trackOrKind
    this.transceivers.push(tx)
    return tx
  }
  getTransceivers(): MockTransceiver[] { return this.transceivers }
  getSenders(): Array<MockTransceiver['sender']> {
    return this.transceivers.map((t) => t.sender)
  }
  removeTrack(sender: MockTransceiver['sender']): void {
    const tx = this.transceivers.find((t) => t.sender === sender)
    if (tx) tx.sender.track = null
  }

  async createOffer(): Promise<{ type: string; sdp: string }> {
    // Assign a mid to every transceiver that does not have one yet (the local
    // audio/video recvonly transceivers created at join → mids '0'/'1').
    this.transceivers.forEach((tx, i) => { if (tx.mid === null) tx.mid = String(i) })
    return { type: 'offer', sdp: this._buildSdp() }
  }
  async setLocalDescription(desc: unknown): Promise<void> {
    this.localDescription = desc
    const type = (desc as { type?: string } | null)?.type
    if (type === 'offer') this.signalingState = 'have-local-offer'
    else if (type === 'answer' || type === 'rollback') this.signalingState = 'stable'
  }

  async setRemoteDescription(desc: { type?: string; sdp?: string }): Promise<void> {
    this.remoteDescription = desc
    const type = desc?.type
    if (type === 'offer') this.signalingState = 'have-remote-offer'
    else if (type === 'answer') this.signalingState = 'stable'
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

// ── Response helpers ─────────────────────────────────────────────────────────

export function jsonResp(body: unknown) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(''),
  }
}

/** Non-OK response — drives _apiFetchJson's throw path (transient 502/404/5xx). */
export function errResp(status: number, detail: string) {
  return {
    ok: false,
    status,
    json: () => Promise.resolve({ detail }),
    text: () => Promise.resolve(detail),
  }
}

// ── Composable mount harness ────────────────────────────────────────────────
// The usePartyCalls import resolves against the mock apiService registered by
// the TEST FILE (vi.mock is hoisted to the top of each test file BEFORE this
// module is imported).

import { usePartyCalls } from '../usePartyCalls'

let pinia: Pinia

export function mountComposable(): VueWrapper {
  const TestComp = defineComponent({
    setup() {
      return usePartyCalls()
    },
    template: '<div></div>',
  })
  return mount(TestComp, { global: { plugins: [pinia] } })
}

/** Register the base WebRTC globals + fresh pinia.  Call from each test file's
 *  beforeEach (after clearing that file's own warnCalls). */
export function setupTestBed(): void {
  pinia = createPinia()
  setActivePinia(pinia)
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
}
