/**
 * useWorkspaceHandshake.ts
 *
 * Composable for the Runner-side of the Cockpit ↔ Runner handshake.
 *
 * Responsibilities:
 * 1. Listen for INIT_WORKSPACE postMessage from Cockpit.
 * 2. Validate event.origin against EXPECTED_COCKPIT_ORIGINS before processing.
 * 3. Validate the session token with the CentralHub backend.
 * 4. Reply with RUNNER_READY (success) or RUNNER_ERROR (failure).
 * 5. Persist workspace state via workspaceStore.
 *
 * Phase 1 – Hello World + Handshake only.
 */

import { onMounted, onUnmounted } from 'vue'
import { useWorkspaceStore } from '../stores/workspaceStore'
import { createLogger } from '@/utils/logger'

const log = createLogger('workspace:handshake')

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
  'http://localhost:5051'

/**
 * Allowed Cockpit origins. Messages from other origins are silently dropped.
 * Override via VITE_COCKPIT_ORIGINS env var (comma-separated list).
 */
const EXPECTED_COCKPIT_ORIGINS: string[] =
  (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_COCKPIT_ORIGINS)
    ?.split(',').map((o: string) => o.trim()).filter(Boolean) ||
  ['http://localhost:5173', 'http://localhost:8000', 'http://127.0.0.1:5173']

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
   * Uses cockpitOrigin to restrict the message to the legitimate parent only.
   */
  function sendReady(workspaceId: string, cockpitOrigin: string, source: MessageEventSource | null) {
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
    log.info('[WORKSPACE] Sending RUNNER_READY', message)
    if (source) {
      ;(source as Window).postMessage(message, cockpitOrigin)
    } else {
      window.parent.postMessage(message, cockpitOrigin)
    }
  }

  /**
   * Send RUNNER_ERROR back to Cockpit via the parent frame.
   * Uses cockpitOrigin to restrict the message to the legitimate parent only.
   */
  function sendError(
    workspaceId: string,
    errorCode: string,
    message: string,
    cockpitOrigin: string,
    source: MessageEventSource | null,
  ) {
    const msg: WorkspaceErrorMessage = {
      type: 'RUNNER_ERROR',
      payload: { workspaceId, errorCode, message },
      timestamp: Date.now(),
    }
    log.error('[WORKSPACE] Sending RUNNER_ERROR', msg)
    if (source) {
      ;(source as Window).postMessage(msg, cockpitOrigin)
    } else {
      window.parent.postMessage(msg, cockpitOrigin)
    }
  }

  // ── Message handler ────────────────────────────────────────────────────────

  async function handleMessage(event: MessageEvent) {
    // Security: validate origin FIRST before processing any message content
    if (!EXPECTED_COCKPIT_ORIGINS.includes(event.origin)) {
      log.warn('[WORKSPACE] Rejected message from unexpected origin', { origin: event.origin })
      return
    }

    const data = event.data as Partial<InitWorkspaceMessage>

    if (!data || data.type !== 'INIT_WORKSPACE') {
      return
    }

    log.info('[WORKSPACE] INIT_WORKSPACE received', data)

    const { workspaceId, sessionToken, userId, cockpitOrigin } = data.payload ?? {}

    if (!workspaceId || !sessionToken || !cockpitOrigin) {
      const code = 'INVALID_PAYLOAD'
      const msg = 'Missing required fields in INIT_WORKSPACE payload'
      store.setError(code, msg)
      // Use event.origin as fallback if cockpitOrigin is missing in the payload
      sendError(workspaceId ?? '', code, msg, event.origin, event.source)
      return
    }

    store.initWorkspace({ workspaceId, sessionToken, userId: userId ?? '' })

    try {
      await validateSessionWithBackend(workspaceId, sessionToken)
      store.setReady()
      log.info('[WORKSPACE] RUNNER_READY – session validated', { workspaceId })
      sendReady(workspaceId, cockpitOrigin, event.source)
    } catch (err) {
      const code = 'VALIDATION_FAILED'
      const message =
        err instanceof Error ? err.message : 'Failed to validate session: Backend unreachable'
      store.setError(code, message)
      log.error('[WORKSPACE] RUNNER_ERROR', { code, message })
      sendError(workspaceId, code, message, cockpitOrigin, event.source)
    }
  }

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  onMounted(() => {
    window.addEventListener('message', handleMessage)
    log.info('[WORKSPACE] useWorkspaceHandshake mounted – listening for INIT_WORKSPACE')
  })

  onUnmounted(() => {
    window.removeEventListener('message', handleMessage)
  })

  return { store }
}
