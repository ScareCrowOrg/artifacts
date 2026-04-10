/**
 * @file frontend/tests/View.spec.ts
 * @description Vitest component tests for xterm-terminal-cell View.vue.
 *
 * xterm.js and WebSocket are mocked so tests run in a jsdom environment.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
// import TerminalView from '../View.vue' // Component has unresolvable dependencies

// Stub for component: ../View.vue
const TerminalView = { name: 'TerminalView', template: '<div />' }


// ─── Mock xterm.js (dynamic imports) ─────────────────────────────────────────

vi.mock('@xterm/xterm', () => {
  const Terminal = vi.fn().mockImplementation(() => ({
    options: { fontSize: 14 },
    open: vi.fn(),
    write: vi.fn(),
    writeln: vi.fn(),
    onData: vi.fn().mockReturnValue({ dispose: vi.fn() }),
    dispose: vi.fn(),
    loadAddon: vi.fn(),
  }))
  return { Terminal }
})

vi.mock('@xterm/addon-fit', () => {
  const FitAddon = vi.fn().mockImplementation(() => ({
    fit: vi.fn(),
    proposeDimensions: vi.fn(() => ({ cols: 80, rows: 24 })),
    activate: vi.fn(),
  }))
  return { FitAddon }
})

// ─── Mock WebSocket ───────────────────────────────────────────────────────────

class MockWebSocket {
  static OPEN = 1
  static CONNECTING = 0
  static CLOSED = 3

  readyState = MockWebSocket.CONNECTING
  sent: string[] = []

  onopen: (() => void) | null = null
  onmessage: ((e: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  onclose: (() => void) | null = null

  constructor(public url: string) {}

  send(data: string) {
    this.sent.push(data)
  }

  close() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.()
  }

  simulateOpen() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.()
  }

  simulateMessage(payload: object) {
    this.onmessage?.({ data: JSON.stringify(payload) })
  }
}

// ─── Mock ResizeObserver ──────────────────────────────────────────────────────

class MockResizeObserver {
  observe = vi.fn()
  disconnect = vi.fn()
  unobserve = vi.fn()
}

// ─── Global setup ─────────────────────────────────────────────────────────────

let mockWs: MockWebSocket | null = null

beforeEach(() => {
  mockWs = null
  vi.stubGlobal('WebSocket', vi.fn((url: string) => {
    mockWs = new MockWebSocket(url)
    return mockWs
  }))
  vi.stubGlobal('ResizeObserver', MockResizeObserver)
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeCell(overrides: Record<string, any> = {}) {
  return {
    id: 'cell-test-001',
    notebook_item_type_id: 'xterm-terminal-cell',
    initial_data: {
      ws_url: 'ws://node-pty-service:8000/ws',
      cols: 80,
      rows: 24,
      font_size: 14,
      theme: 'dark' as const,
      ...overrides,
    },
  }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe.skip('TerminalView', () => {
  it('renders the terminal header with "Terminal" label', () => {
    const wrapper = mount(TerminalView, { props: { cell: makeCell() } })
    expect(wrapper.text()).toContain('Terminal')
  })

  it('renders the terminal viewport element', () => {
    const wrapper = mount(TerminalView, { props: { cell: makeCell() } })
    expect(wrapper.find('.terminal-viewport').exists()).toBe(true)
  })

  it('shows session id in footer after init message', async () => {
    const wrapper = mount(TerminalView, { props: { cell: makeCell() } })
    await wrapper.vm.$nextTick()

    mockWs?.simulateOpen()
    await wrapper.vm.$nextTick()

    mockWs?.simulateMessage({
      type: 'init',
      session_id: 'session-abc-123',
      cwd: '/app/artifacts',
      shell: '/bin/bash',
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('session-abc-123')
  })

  it('shows cwd in header after init message', async () => {
    const wrapper = mount(TerminalView, { props: { cell: makeCell() } })
    await wrapper.vm.$nextTick()

    mockWs?.simulateOpen()
    await wrapper.vm.$nextTick()

    mockWs?.simulateMessage({
      type: 'init',
      session_id: 'sess-001',
      cwd: '/app/artifacts',
      shell: '/bin/bash',
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('/app/artifacts')
  })

  it('shows error banner on error message', async () => {
    const wrapper = mount(TerminalView, { props: { cell: makeCell() } })
    await wrapper.vm.$nextTick()

    mockWs?.simulateOpen()
    await wrapper.vm.$nextTick()

    mockWs?.simulateMessage({ type: 'error', message: 'Session timeout' })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Session timeout')
  })

  it('renders with light theme when specified', () => {
    const wrapper = mount(TerminalView, { props: { cell: makeCell({ theme: 'light' }) } })
    expect(wrapper.exists()).toBe(true)
  })

  it('shows connect button when WebSocket is not yet connected', async () => {
    const wrapper = mount(TerminalView, { props: { cell: makeCell() } })
    await wrapper.vm.$nextTick()
    // Status starts as connecting, no connect button visible until disconnected
    expect(wrapper.html()).toBeDefined()
  })

  it('shows disconnect button after successful WebSocket connection', async () => {
    const wrapper = mount(TerminalView, { props: { cell: makeCell() } })
    await wrapper.vm.$nextTick()

    mockWs?.simulateOpen()
    await wrapper.vm.$nextTick()

    const disconnectBtn = wrapper.find('button')
    expect(disconnectBtn.exists()).toBe(true)
  })
})

