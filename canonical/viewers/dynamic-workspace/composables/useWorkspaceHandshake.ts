/**
 * useWorkspaceHandshake.ts
 *
 * Composable for the Runner-side of the Cockpit ↔ Runner handshake.
 *
 * Responsibilities:
 * 1. Listen for INIT_WORKSPACE postMessage from Cockpit.
 * 2. Validate the session token with the CentralHub backend.
 * 3. Reply with RUNNER_READY (success) or RUNNER_ERROR (failure).
 * 4. Persist workspace state via workspaceStore.
 *
 * Phase 1 – Hello World + Handshake only.
 */

import { onMounted, onUnmounted } from 'vue'
import { useWorkspaceStore } from '../stores/workspaceStore'

// ── Message interfaces ──────────────────────────────────────────────────────

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

// ── Constants ───────────────────────────────────────────────────────────────

const RUNNER_VERSION = 'v2.0.0-phase1'
const VALIDATE_SESSION_URL =
  (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_CENTRALHUB_URL) ||
  'http://localhost:5050'

// ── Composable ──────────────────────────────────────────────────────────────

export function useWorkspaceHandshake() {
  const store = useWorkspaceStore()

  // ── Private helpers ────────────────────────────────────────────────────────

  /**
   * Call CentralHub to validate the JWT and workspace ID.
   */
  async function validateSessionWithBackend(
    workspaceId: string,
    sessionToken: string,
  ): Promise<{ userId: string }> {
    const response = await fetch(`${VALIDATE_SESSION_URL}/api/workspace/validate-session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspaceId, sessionToken }),
    })

    if (!response.ok) {
      const detail = await response.text().catch(() => 'unknown error')
      throw new Error(`VALIDATION_FAILED: ${response.status} ${detail}`)
    }

    return response.json()
  }

  /**
   * Send RUNNER_READY back to Cockpit via the parent frame.
   */
  function sendReady(workspaceId: string, source: MessageEventSource | null) {
    const message: WorkspaceReadyMessage = {
      type: 'RUNNER_READY',
      payload: {
        workspaceId,
        runnerOrigin: window.location.origin,
        version: RUNNER_VERSION,
        capabilities: ['hello-world'],
        status: 'ready',
      },
      timestamp: Date.now(),
    }
    console.info('[WORKSPACE] Sending RUNNER_READY', message)
    if (source) {
      ;(source as Window).postMessage(message, '*')
    } else {
      window.parent.postMessage(message, '*')
    }
  }

  /**
   * Send RUNNER_ERROR back to Cockpit via the parent frame.
   */
  function sendError(
    workspaceId: string,
    errorCode: string,
    message: string,
    source: MessageEventSource | null,
  ) {
    const msg: WorkspaceErrorMessage = {
      type: 'RUNNER_ERROR',
      payload: { workspaceId, errorCode, message },
      timestamp: Date.now(),
    }
    console.error('[WORKSPACE] Sending RUNNER_ERROR', msg)
    if (source) {
      ;(source as Window).postMessage(msg, '*')
    } else {
      window.parent.postMessage(msg, '*')
    }
  }

  // ── Message handler ────────────────────────────────────────────────────────

  async function handleMessage(event: MessageEvent) {
    const data = event.data as Partial<InitWorkspaceMessage>

    if (!data || data.type !== 'INIT_WORKSPACE') {
      return
    }

    console.info('[WORKSPACE] INIT_WORKSPACE received', data)

    const { workspaceId, sessionToken, userId, cockpitOrigin } = data.payload ?? {}

    if (!workspaceId || !sessionToken || !cockpitOrigin) {
      const code = 'INVALID_PAYLOAD'
      const msg = 'Missing required fields in INIT_WORKSPACE payload'
      store.setError(code, msg)
      sendError(workspaceId ?? '', code, msg, event.source)
      return
    }

    store.initWorkspace({ workspaceId, sessionToken, userId: userId ?? '' })

    try {
      await validateSessionWithBackend(workspaceId, sessionToken)
      store.setReady()
      console.info('[WORKSPACE] RUNNER_READY – session validated for workspaceId=%s', workspaceId)
      sendReady(workspaceId, event.source)
    } catch (err) {
      const code = 'VALIDATION_FAILED'
      const message =
        err instanceof Error ? err.message : 'Failed to validate session: Backend unreachable'
      store.setError(code, message)
      console.error('[WORKSPACE] RUNNER_ERROR: %s – %s', code, message)
      sendError(workspaceId, code, message, event.source)
    }
  }

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  onMounted(() => {
    window.addEventListener('message', handleMessage)
    console.info('[WORKSPACE] useWorkspaceHandshake mounted – listening for INIT_WORKSPACE')
  })

  onUnmounted(() => {
    window.removeEventListener('message', handleMessage)
  })

  return { store }
}
