/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-03-16",
 *   "theme_compliance": 100,
 *   "dark_mode_support": "full",
 *   "i18n_validated": false
 * }
 */
<template>
  <div
    ref="containerRef"
    class="xterm-terminal-cell flex flex-col bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg overflow-hidden shadow-sm h-full"
  >
    <!-- Header bar -->
    <div
      class="cell-header flex items-center justify-between px-3 py-2 bg-surface-elevated dark:bg-surface-elevated-dark border-b border-border dark:border-border-dark shrink-0"
    >
      <div class="flex items-center gap-2">
        <!-- Status dot -->
        <span
          :class="[
            'inline-block w-2 h-2 rounded-full',
            status === 'connected'
              ? 'bg-green-500'
              : status === 'connecting'
              ? 'bg-yellow-400 animate-pulse'
              : status === 'error'
              ? 'bg-red-500'
              : 'bg-neutral-400',
          ]"
        />
        <span class="text-sm font-medium text-text-primary dark:text-text-primary-dark">
          Terminal
        </span>
        <span
          v-if="cwd"
          class="text-xs text-text-secondary dark:text-text-secondary-dark font-mono truncate max-w-[200px]"
          :title="cwd"
        >
          {{ cwd }}
        </span>
      </div>

      <div class="flex items-center gap-1">
        <!-- Reconnect button (shown when disconnected or errored) -->
        <button
          v-if="status === 'disconnected' || status === 'error'"
          class="px-2 py-1 text-xs rounded bg-primary dark:bg-primary-hover text-white hover:bg-primary-hover dark:hover:bg-primary-light transition"
          @click="handleConnect"
        >
          Connect
        </button>
        <!-- Disconnect button -->
        <button
          v-if="status === 'connected'"
          class="px-2 py-1 text-xs rounded bg-neutral-600 dark:bg-neutral-700 text-white hover:bg-neutral-700 dark:hover:bg-neutral-600 transition"
          @click="handleDisconnect"
        >
          Disconnect
        </button>
      </div>
    </div>

    <!-- Error banner -->
    <div
      v-if="errorMessage"
      class="px-3 py-1 text-xs text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-950 border-b border-red-200 dark:border-red-800 shrink-0"
    >
      {{ errorMessage }}
    </div>

    <!-- Terminal viewport -->
    <div
      ref="terminalRef"
      class="terminal-viewport flex-1 min-h-0 overflow-hidden"
      :style="{ fontSize: `${fontSize}px` }"
    />

    <!-- Footer: session info -->
    <div
      v-if="sessionId"
      class="cell-footer px-3 py-1 text-xs text-text-secondary dark:text-text-secondary-dark bg-surface-elevated dark:bg-surface-elevated-dark border-t border-border dark:border-border-dark shrink-0 font-mono truncate"
    >
      session: {{ sessionId }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import { usePTYConnection, useTerminalResize } from './composables'

// ─── Props ────────────────────────────────────────────────────────────────────

const props = defineProps<{
  cell: {
    id: string
    notebook_item_type_id: string
    initial_data?: {
      ws_url?: string
      cols?: number
      rows?: number
      font_size?: number
      theme?: 'dark' | 'light'
    }
  }
}>()

const emit = defineEmits<{
  (e: 'update:cell', cell: typeof props.cell): void
}>()

// ─── Derived config ───────────────────────────────────────────────────────────

const wsUrl = computed(() => props.cell.initial_data?.ws_url ?? 'ws://node-pty-service:8000/ws')
const fontSize = computed(() => props.cell.initial_data?.font_size ?? 14)

// ─── Template refs ────────────────────────────────────────────────────────────

const containerRef = ref<HTMLElement | null>(null)
const terminalRef = ref<HTMLElement | null>(null)

// ─── Terminal instance ────────────────────────────────────────────────────────

// xterm.js is loaded lazily to avoid SSR issues and keep bundle size lean.
let terminal: any = null
let fitAddon: any = null

async function initTerminal() {
  if (!terminalRef.value) return

  try {
    const { Terminal } = await import('@xterm/xterm')
    const { FitAddon } = await import('@xterm/addon-fit')

  const isDark = props.cell.initial_data?.theme === 'dark' || props.cell.initial_data?.theme === undefined

  terminal = new Terminal({
    fontSize: fontSize.value,
    fontFamily: '"Cascadia Code", "Fira Code", Menlo, Monaco, "Courier New", monospace',
    cursorBlink: true,
    allowTransparency: false,
    theme: isDark
      ? {
          background: '#1a1a2e',
          foreground: '#e2e8f0',
          cursor: '#e2e8f0',
          selectionBackground: '#3b5998',
        }
      : {
          background: '#ffffff',
          foreground: '#1a1a2e',
          cursor: '#1a1a2e',
          selectionBackground: '#cce5ff',
        },
  })

  fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  terminal.open(terminalRef.value)
  fitAddon.fit()

  // Forward user keystrokes to the PTY
  terminal.onData((data: string) => {
    sendInput(data)
  })
  } catch (err) {
    console.error('[XtermTerminalCell] Failed to initialize terminal:', err)
  }
}

// ─── PTY connection ───────────────────────────────────────────────────────────

const errorMessage = ref<string | null>(null)
const cwd = ref<string | null>(null)
const sessionId = ref<string | null>(null)

const { status, connect, disconnect, sendInput, sendResize } = usePTYConnection({
  wsUrl: wsUrl.value,
  onOutput: (data: string) => {
    terminal?.write(data)
  },
  onInit: (msg) => {
    sessionId.value = msg.session_id
    cwd.value = msg.cwd
    errorMessage.value = null
    // Sync terminal size after init
    if (fitAddon) {
      fitAddon.fit()
      const dims = fitAddon.proposeDimensions()
      if (dims) sendResize(dims.cols, dims.rows)
    }
  },
  onError: (message: string) => {
    errorMessage.value = message
  },
  onClosed: (reason: string) => {
    terminal?.writeln(`\r\n\x1b[33m[Terminal closed: ${reason}]\x1b[0m`)
  },
})

// ─── Terminal resize (container → PTY) ───────────────────────────────────────

useTerminalResize({
  containerRef: terminalRef,
  fontSize,
  onResize: (cols: number, rows: number) => {
    fitAddon?.fit()
    sendResize(cols, rows)
  },
})

// ─── Lifecycle ────────────────────────────────────────────────────────────────

onMounted(() => {
  // Connect WebSocket immediately, then initialize terminal UI in parallel
  connect()
  initTerminal()
})

onUnmounted(() => {
  disconnect()
  terminal?.dispose()
  terminal = null
})

// ─── Handlers ─────────────────────────────────────────────────────────────────

function handleConnect() {
  errorMessage.value = null
  connect()
}

function handleDisconnect() {
  disconnect()
}

// Watch font size changes
watch(fontSize, (size) => {
  if (terminal) {
    terminal.options.fontSize = size
    fitAddon?.fit()
  }
})
</script>

<style scoped>
.xterm-terminal-cell {
  min-height: 200px;
}

.terminal-viewport :deep(.xterm) {
  height: 100%;
  padding: 4px;
}

.terminal-viewport :deep(.xterm-viewport) {
  overflow-y: auto;
}
</style>
