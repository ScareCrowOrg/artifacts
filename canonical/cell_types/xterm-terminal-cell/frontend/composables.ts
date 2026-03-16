/**
 * @file frontend/composables.ts
 * @description Vue composables for xterm-terminal-cell.
 *
 * usePTYConnection  – Manages the WebSocket connection to the Node-PTY service.
 * useTerminalResize – Observes container size and syncs PTY terminal dimensions.
 */

import { ref, onMounted, onUnmounted, type Ref } from 'vue'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface PTYInitMessage {
  type: 'init'
  session_id: string
  cwd: string
  shell: string
}

export interface PTYOutputMessage {
  type: 'output'
  data: string
}

export interface PTYErrorMessage {
  type: 'error'
  message: string
}

export interface PTYClosedMessage {
  type: 'closed'
  reason: string
}

export type PTYServerMessage =
  | PTYInitMessage
  | PTYOutputMessage
  | PTYErrorMessage
  | PTYClosedMessage

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

// ─── usePTYConnection ─────────────────────────────────────────────────────────

export interface PTYConnectionOptions {
  /** WebSocket URL (ws:// or wss://) */
  wsUrl: string
  /** Called with raw terminal output from the PTY */
  onOutput: (data: string) => void
  /** Called when the session is initialised */
  onInit?: (msg: PTYInitMessage) => void
  /** Called when the connection closes */
  onClosed?: (reason: string) => void
  /** Called on error */
  onError?: (message: string) => void
}

export interface PTYConnection {
  /** Connection status reactive ref */
  status: Ref<ConnectionStatus>
  /** Session ID assigned by the server */
  sessionId: Ref<string | null>
  /** Current working directory reported by the server */
  cwd: Ref<string | null>
  /** Connect to the WebSocket */
  connect: () => void
  /** Disconnect from the WebSocket */
  disconnect: () => void
  /** Send raw input to the PTY */
  sendInput: (data: string) => void
  /** Send a resize event to the PTY */
  sendResize: (cols: number, rows: number) => void
}

/**
 * Composable that manages a WebSocket connection to the Node-PTY service.
 *
 * @example
 * ```typescript
 * const { status, sendInput, sendResize, connect, disconnect } = usePTYConnection({
 *   wsUrl: 'ws://node-pty-service:8000/ws',
 *   onOutput: (data) => terminal.write(data),
 * })
 * onMounted(() => connect())
 * onUnmounted(() => disconnect())
 * ```
 */
export function usePTYConnection(opts: PTYConnectionOptions): PTYConnection {
  const status = ref<ConnectionStatus>('disconnected')
  const sessionId = ref<string | null>(null)
  const cwd = ref<string | null>(null)

  let ws: WebSocket | null = null

  function connect() {
    if (ws && ws.readyState === WebSocket.OPEN) return
    status.value = 'connecting'

    ws = new WebSocket(opts.wsUrl)

    ws.onopen = () => {
      status.value = 'connected'
    }

    ws.onmessage = (event: MessageEvent) => {
      let msg: PTYServerMessage
      try {
        msg = JSON.parse(event.data as string) as PTYServerMessage
      } catch {
        return
      }

      switch (msg.type) {
        case 'init':
          sessionId.value = msg.session_id
          cwd.value = msg.cwd
          opts.onInit?.(msg)
          break
        case 'output':
          opts.onOutput(msg.data)
          break
        case 'error':
          status.value = 'error'
          opts.onError?.(msg.message)
          break
        case 'closed':
          status.value = 'disconnected'
          sessionId.value = null
          opts.onClosed?.(msg.reason)
          break
      }
    }

    ws.onerror = () => {
      status.value = 'error'
      opts.onError?.('WebSocket connection error')
    }

    ws.onclose = () => {
      if (status.value !== 'error') {
        status.value = 'disconnected'
      }
    }
  }

  function disconnect() {
    if (ws) {
      try {
        ws.send(JSON.stringify({ type: 'close' }))
      } catch {
        // Connection may already be closing
      }
      ws.close()
      ws = null
    }
    status.value = 'disconnected'
    sessionId.value = null
  }

  function sendInput(data: string) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'input', data }))
    }
  }

  function sendResize(cols: number, rows: number) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'resize', cols, rows }))
    }
  }

  onUnmounted(() => {
    disconnect()
  })

  return { status, sessionId, cwd, connect, disconnect, sendInput, sendResize }
}

// ─── useTerminalResize ────────────────────────────────────────────────────────

export interface TerminalResizeOptions {
  /** The container element ref to observe */
  containerRef: Ref<HTMLElement | null>
  /** Font size in pixels (used to calculate cols/rows) */
  fontSize: Ref<number>
  /** Called when dimensions change */
  onResize: (cols: number, rows: number) => void
}

/**
 * Composable that observes a container element and emits terminal dimensions
 * whenever the container resizes.
 *
 * @example
 * ```typescript
 * const containerRef = ref<HTMLElement | null>(null)
 * useTerminalResize({
 *   containerRef,
 *   fontSize: ref(14),
 *   onResize: (cols, rows) => sendResize(cols, rows),
 * })
 * ```
 */
export function useTerminalResize(opts: TerminalResizeOptions) {
  let observer: ResizeObserver | null = null

  const CHAR_WIDTH_RATIO = 0.6   // approximate monospace char width = fontSize * 0.6
  const CHAR_HEIGHT_RATIO = 1.2  // approximate line height = fontSize * 1.2

  function calculateDimensions(width: number, height: number): { cols: number; rows: number } {
    const charW = opts.fontSize.value * CHAR_WIDTH_RATIO
    const charH = opts.fontSize.value * CHAR_HEIGHT_RATIO
    const cols = Math.max(10, Math.floor(width / charW))
    const rows = Math.max(5, Math.floor(height / charH))
    return { cols, rows }
  }

  onMounted(() => {
    if (!opts.containerRef.value) return

    observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect
        const { cols, rows } = calculateDimensions(width, height)
        opts.onResize(cols, rows)
      }
    })

    observer.observe(opts.containerRef.value)
  })

  onUnmounted(() => {
    observer?.disconnect()
    observer = null
  })
}
