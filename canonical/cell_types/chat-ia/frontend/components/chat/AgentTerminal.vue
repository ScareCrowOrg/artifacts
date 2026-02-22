/**
 * @metadata {
 *   "theme_validated": true,
 *   "i18n_validated": false,
 *   "component": "AgentTerminal",
 *   "purpose": "Real-time Agent Mode log terminal with xterm.js",
 *   "mvp": "MVP 4 - Agent Mode Live-Wire",
 *   "theme_validated_date": "2026-01-22",
 *   "theme_compliance": 98,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full"
 * }
 */
<template>
  <div
    v-if="isVisible"
    class="agent-terminal-container border rounded-lg overflow-hidden"
    :class="{ expanded: isExpanded }"
    style="
      background: var(--color-surface);
      border-color: var(--color-border);
    "
    data-testid="agent-terminal"
  >
    <!-- Terminal Header -->
    <div
      class="terminal-header flex justify-between items-center px-4 py-2 border-b"
      style="
        background: var(--color-surface-elevated);
        border-color: var(--color-border);
      "
    >
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold" style="color: var(--color-text-primary);">
          ⚡ {{ t('agentTerminal.title') }}
        </span>
        <span
          v-if="isConnected"
          class="px-2 py-0.5 text-xs rounded-full"
          style="
            background: rgba(34, 197, 94, 0.1);
            color: rgb(34, 197, 94);
          "
        >
          ● {{ t('agentTerminal.connected') }}
        </span>
        <span
          v-else
          class="px-2 py-0.5 text-xs rounded-full"
          style="
            background: rgba(239, 68, 68, 0.1);
            color: rgb(239, 68, 68);
          "
        >
          ○ {{ t('agentTerminal.disconnected') }}
        </span>
      </div>

      <div class="flex gap-1">
        <button
          class="terminal-btn p-1.5 rounded hover:bg-opacity-10"
          :title="t('agentTerminal.clear')"
          @click="clearTerminal"
        >
          🗑️
        </button>
        <button
          class="terminal-btn p-1.5 rounded hover:bg-opacity-10"
          :title="t('agentTerminal.copy')"
          @click="copyLogs"
        >
          📋
        </button>
        <button
          class="terminal-btn p-1.5 rounded hover:bg-opacity-10"
          :title="isExpanded ? t('agentTerminal.collapse') : t('agentTerminal.expand')"
          @click="toggleExpand"
        >
          {{ isExpanded ? '🗗' : '🗖' }}
        </button>
        <button
          class="terminal-btn p-1.5 rounded hover:bg-opacity-10"
          :title="t('agentTerminal.close')"
          @click="closeTerminal"
        >
          ✕
        </button>
      </div>
    </div>

    <!-- Terminal Body (xterm.js container) -->
    <div
      ref="terminalElement"
      class="terminal-body"
      :class="{ 'h-64': !isExpanded, 'h-96': isExpanded }"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import '@xterm/xterm/css/xterm.css'
import { createLogger } from '@/utils/logger'
import { useChatStore } from '../../stores/chat'
import authService from '@/services/authService'

const log = createLogger('component:AgentTerminal')
const { t } = useI18n()

interface Props {
  /** Conversation/session ID for WebSocket connection */
  conversationId?: string | null
  /** Whether terminal is visible */
  visible?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  conversationId: null,
  visible: false,
})

const emit = defineEmits<{
  close: []
}>()

// Store
const chatStore = useChatStore()

// Refs
const terminalElement = ref<HTMLDivElement>()
const terminal = ref<Terminal | null>(null)
const fitAddon = ref<FitAddon | null>(null)
const websocket = ref<WebSocket | null>(null)

// State
const isVisible = ref(props.visible)
const isExpanded = ref(false)
const isConnected = ref(false)

/**
 * Initialize xterm.js terminal
 */
function initializeTerminal(): void {
  if (!terminalElement.value || terminal.value) return

  try {
    // Create terminal instance
    terminal.value = new Terminal({
      cursorBlink: false,
      fontSize: 13,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: 'var(--color-surface-dark, #1e1e1e)',
        foreground: 'var(--color-text-primary, #d4d4d4)',
        cursor: 'var(--color-text-primary, #d4d4d4)',
        black: '#000000',
        red: 'var(--color-error, #cd3131)',
        green: 'var(--color-success, #0dbc79)',
        yellow: 'var(--color-warning, #e5e510)',
        blue: 'var(--color-info, #2472c8)',
        magenta: 'var(--color-accent, #bc3fbc)',
        cyan: '#11a8cd',
        white: '#e5e5e5',
        brightBlack: '#666666',
        brightRed: 'var(--color-error-light, #f14c4c)',
        brightGreen: 'var(--color-success-light, #23d18b)',
        brightYellow: 'var(--color-warning-light, #f5f543)',
        brightBlue: 'var(--color-info-light, #3b8eea)',
        brightMagenta: 'var(--color-accent-light, #d670d6)',
        brightCyan: '#29b8db',
        brightWhite: '#ffffff',
      },
      scrollback: 10000,
      convertEol: true,
    })

    // Add fit addon for automatic resizing
    fitAddon.value = new FitAddon()
    terminal.value.loadAddon(fitAddon.value)

    // Add web links addon
    const webLinksAddon = new WebLinksAddon()
    terminal.value.loadAddon(webLinksAddon)

    // Open terminal
    terminal.value.open(terminalElement.value)
    fitAddon.value.fit()

    // Welcome message
    terminal.value.writeln('\x1b[1;36m╔═══════════════════════════════════════════════════════════╗\x1b[0m')
    terminal.value.writeln('\x1b[1;36m║       Agent Mode Terminal - Real-time Log Stream         ║\x1b[0m')
    terminal.value.writeln('\x1b[1;36m╚═══════════════════════════════════════════════════════════╝\x1b[0m')
    terminal.value.writeln('')

    log.info('Terminal initialized successfully')
  } catch (error) {
    log.error('Failed to initialize terminal', error)
  }
}

/**
 * Connect to WebSocket for real-time log streaming
 */
function connectWebSocket(): void {
  if (!props.conversationId || websocket.value) return

  try {
    // Get auth token from authService (centralized token management)
    const token = authService.getToken()
    if (!token) {
      terminal.value?.writeln('\x1b[1;31m[ERROR] No authentication token found\x1b[0m')
      log.error('No auth token for WebSocket')
      return
    }

    // Build WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws/agent/${props.conversationId}?token=${token}`

    terminal.value?.writeln(`\x1b[33m[INFO] Connecting to: ${props.conversationId}\x1b[0m`)
    log.info('Connecting to WebSocket', { conversationId: props.conversationId })

    websocket.value = new WebSocket(wsUrl)

    websocket.value.onopen = () => {
      isConnected.value = true
      terminal.value?.writeln('\x1b[1;32m[CONNECTED] WebSocket connection established\x1b[0m')
      terminal.value?.writeln('')
      log.info('WebSocket connected')
    }

    websocket.value.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        
        // Handle different message types
        if (message.type === 'log' && message.content) {
          // Write log line (preserving ANSI codes)
          terminal.value?.writeln(message.content)
        } else if (message.type === 'status') {
          terminal.value?.writeln(`\x1b[36m[STATUS] ${message.status}\x1b[0m`)
        } else if (message.type === 'error') {
          terminal.value?.writeln(`\x1b[1;31m[ERROR] ${message.message}\x1b[0m`)
        }
        
        // Auto-scroll to bottom
        terminal.value?.scrollToBottom()
      } catch (error) {
        log.error('Failed to parse WebSocket message', error)
      }
    }

    websocket.value.onerror = (error) => {
      isConnected.value = false
      terminal.value?.writeln('\x1b[1;31m[ERROR] WebSocket error occurred\x1b[0m')
      log.error('WebSocket error', error)
    }

    websocket.value.onclose = () => {
      isConnected.value = false
      terminal.value?.writeln('\x1b[33m[DISCONNECTED] WebSocket connection closed\x1b[0m')
      log.info('WebSocket disconnected')
      websocket.value = null
    }
  } catch (error) {
    log.error('Failed to connect WebSocket', error)
    terminal.value?.writeln(`\x1b[1;31m[ERROR] Connection failed: ${error}\x1b[0m`)
  }
}

/**
 * Disconnect WebSocket
 */
function disconnectWebSocket(): void {
  if (websocket.value) {
    websocket.value.close()
    websocket.value = null
    isConnected.value = false
    log.info('WebSocket disconnected manually')
  }
}

/**
 * Clear terminal content
 */
function clearTerminal(): void {
  terminal.value?.clear()
  terminal.value?.writeln('\x1b[2J\x1b[H')
  terminal.value?.writeln('\x1b[33m[INFO] Terminal cleared\x1b[0m')
  terminal.value?.writeln('')
  log.debug('Terminal cleared')
}

/**
 * Copy terminal logs to clipboard
 */
async function copyLogs(): Promise<void> {
  try {
    if (!terminal.value?.buffer) return

    // Extract text from terminal buffer
    const buffer = terminal.value.buffer.active
    let text = ''
    for (let i = 0; i < buffer.length; i++) {
      const line = buffer.getLine(i)
      if (line) {
        text += line.translateToString(true) + '\n'
      }
    }

    await navigator.clipboard.writeText(text)
    terminal.value?.writeln('\x1b[32m[SUCCESS] Logs copied to clipboard\x1b[0m')
    log.info('Logs copied to clipboard')
  } catch (error) {
    log.error('Failed to copy logs', error)
    terminal.value?.writeln('\x1b[31m[ERROR] Failed to copy logs\x1b[0m')
  }
}

/**
 * Toggle terminal expanded/collapsed
 */
function toggleExpand(): void {
  isExpanded.value = !isExpanded.value
  
  // Refit terminal after animation
  setTimeout(() => {
    fitAddon.value?.fit()
  }, 300)
  
  log.debug('Terminal expand toggled', { expanded: isExpanded.value })
}

/**
 * Close terminal
 */
function closeTerminal(): void {
  isVisible.value = false
  chatStore.toggleAgentTerminal()
  emit('close')
  log.info('Terminal closed')
}

/**
 * Handle window resize
 */
function handleResize(): void {
  fitAddon.value?.fit()
}

// Watch for visibility changes
watch(() => props.visible, (newValue) => {
  isVisible.value = newValue
  if (newValue && !terminal.value) {
    setTimeout(initializeTerminal, 100)
  }
})

// Watch for conversation ID changes
watch(() => props.conversationId, (newValue, oldValue) => {
  if (newValue && newValue !== oldValue) {
    disconnectWebSocket()
    setTimeout(connectWebSocket, 100)
  }
})

// Lifecycle
onMounted(() => {
  if (props.visible) {
    initializeTerminal()
  }
  
  if (props.conversationId) {
    connectWebSocket()
  }

  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  disconnectWebSocket()
  terminal.value?.dispose()
  window.removeEventListener('resize', handleResize)
  log.info('Terminal unmounted and cleaned up')
})
</script>

<style scoped>
.agent-terminal-container {
  transition: all 0.3s ease;
}

.agent-terminal-container.expanded {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.terminal-header {
  user-select: none;
}

.terminal-btn {
  transition: background-color 0.2s ease;
  color: var(--color-text-secondary);
}

.terminal-btn:hover {
  background-color: var(--color-surface-hover);
  color: var(--color-text-primary);
}

.terminal-body {
  transition: height 0.3s ease;
  overflow: hidden;
}

/* xterm.js overrides for theming */
.terminal-body :deep(.xterm) {
  padding: 8px;
  height: 100%;
}

.terminal-body :deep(.xterm-viewport) {
  background-color: var(--color-surface-dark, #1e1e1e) !important;
}

.terminal-body :deep(.xterm-screen) {
  background-color: var(--color-surface-dark, #1e1e1e) !important;
}
</style>
