/**
 * useViewerHandshake.ts
 *
 * Cockpit-side composable that manages the postMessage handshake with the
 * Runner iframe hosting DynamicWorkspace v2.
 *
 * Responsibilities:
 * 1. Send INIT_WORKSPACE to the iframe after it loads.
 * 2. Listen for RUNNER_READY / RUNNER_ERROR responses.
 * 3. Validate runnerOrigin in the response (security check).
 * 4. Expose reactive state: status, error, workspaceId.
 */

import { ref, onMounted, onUnmounted } from 'vue'
import { createLogger } from '@/utils/logger'

const log = createLogger('viewer:handshake')

// ── Constants ───────────────────────────────────────────────────────────────

const HANDSHAKE_TIMEOUT_MS = 5_000
const RUNNER_ORIGIN =
  (import.meta as any).env?.VITE_RUNNER_URL || 'http://localhost:5052'

// ── Message types ────────────────────────────────────────────────────────────

export interface InitWorkspaceMessage {
  type: 'INIT_WORKSPACE'
  payload: {
    workspaceId: string
    sessionToken: string
    cockpitOrigin: string
    userId: string
  }
  timestamp: number
}

export interface WorkspaceReadyMessage {
  type: 'RUNNER_READY'
  payload: {
    workspaceId: string
    runnerOrigin: string
    version: string
    capabilities: string[]
    status: 'ready'
  }
  timestamp: number
}

export interface WorkspaceErrorMessage {
  type: 'RUNNER_ERROR'
  payload: {
    workspaceId: string
    errorCode: string
    message: string
  }
  timestamp: number
}

// ── Types ────────────────────────────────────────────────────────────────────

export type HandshakeStatus = 'idle' | 'pending' | 'ready' | 'error' | 'timeout'

// ── Composable ───────────────────────────────────────────────────────────────

export function useViewerHandshake(options: {
  iframeRef: { value: HTMLIFrameElement | null }
  workspaceId: string
  sessionToken: string
  userId: string
  expectedRunnerOrigin?: string
}) {
  const { iframeRef, expectedRunnerOrigin = RUNNER_ORIGIN } = options

  const status = ref<HandshakeStatus>('idle')
  const errorMessage = ref<string>('')
  const runnerVersion = ref<string>('')
  let timeoutHandle: ReturnType<typeof setTimeout> | null = null

  // ── Helpers ────────────────────────────────────────────────────────────────

  function clearHandshakeTimeout() {
    if (timeoutHandle !== null) {
      clearTimeout(timeoutHandle)
      timeoutHandle = null
    }
  }

  /**
   * Send INIT_WORKSPACE message to the runner iframe.
   * Reads workspaceId, sessionToken, userId from options at call time so that
   * values set in onMounted (e.g. workspaceId from crypto.randomUUID()) are
   * correctly included.
   */
  function sendInit() {
    const iframe = iframeRef.value
    if (!iframe?.contentWindow) {
      log.warn('[useViewerHandshake] iframe not available yet')
      return
    }

    // Read from options at call time (not at composable creation time)
    const currentWorkspaceId = options.workspaceId
    const currentSessionToken = options.sessionToken
    const currentUserId = options.userId

    const message: InitWorkspaceMessage = {
      type: 'INIT_WORKSPACE',
      payload: {
        workspaceId: currentWorkspaceId,
        sessionToken: currentSessionToken,
        cockpitOrigin: window.location.origin,
        userId: currentUserId,
      },
      timestamp: Date.now(),
    }

    log.info('[useViewerHandshake] Sending INIT_WORKSPACE', { workspaceId: currentWorkspaceId })
    iframe.contentWindow.postMessage(message, expectedRunnerOrigin)
    status.value = 'pending'

    // Start timeout guard
    timeoutHandle = setTimeout(() => {
      if (status.value === 'pending') {
        status.value = 'timeout'
        errorMessage.value = 'Handshake timeout: no RUNNER_READY received within 5 s'
        log.error('[useViewerHandshake] Handshake timed out', { workspaceId: currentWorkspaceId })
      }
    }, HANDSHAKE_TIMEOUT_MS)
  }

  // ── Message listener ────────────────────────────────────────────────────────

  function handleMessage(event: MessageEvent) {
    const data = event.data as Partial<WorkspaceReadyMessage & WorkspaceErrorMessage>

    if (data?.type === 'RUNNER_READY') {
      const payload = data.payload as WorkspaceReadyMessage['payload']

      // Security: validate runner origin
      if (payload?.runnerOrigin !== expectedRunnerOrigin) {
        const msg = `Origin mismatch: expected ${expectedRunnerOrigin}, got ${payload?.runnerOrigin}`
        log.error('[useViewerHandshake] RUNNER_READY origin mismatch', { msg })
        status.value = 'error'
        errorMessage.value = msg
        clearHandshakeTimeout()
        return
      }

      clearHandshakeTimeout()
      status.value = 'ready'
      runnerVersion.value = payload?.version ?? ''
      log.info('[useViewerHandshake] RUNNER_READY received', {
        workspaceId: payload?.workspaceId,
        version: payload?.version,
        capabilities: payload?.capabilities,
      })
      return
    }

    if (data?.type === 'RUNNER_ERROR') {
      const payload = data.payload as WorkspaceErrorMessage['payload']
      clearHandshakeTimeout()
      status.value = 'error'
      errorMessage.value = payload?.message ?? 'Unknown runner error'
      log.error('[useViewerHandshake] RUNNER_ERROR received', {
        errorCode: payload?.errorCode,
        message: payload?.message,
      })
    }
  }

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  onMounted(() => {
    window.addEventListener('message', handleMessage)
  })

  onUnmounted(() => {
    window.removeEventListener('message', handleMessage)
    clearHandshakeTimeout()
  })

  return {
    status,
    errorMessage,
    runnerVersion,
    sendInit,
  }
}
