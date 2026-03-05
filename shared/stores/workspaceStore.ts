/**
 * workspaceStore.ts
 *
 * Pinia store for DynamicWorkspace v2 (Runner-side).
 * Holds handshake state received via postMessage from Cockpit.
 *
 * Moved to artifacts/shared/stores so any viewer or cell type can access
 * the session token without depending on dynamic-workspace internals.
 *
 * Phase 1: stores workspaceId, sessionToken, userId and handshake status.
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

export type HandshakeStatus = 'pending' | 'ready' | 'error'

export const useWorkspaceStore = defineStore('workspace-v2', () => {
  // ── State ──────────────────────────────────────────────────────────────────
  const workspaceId = ref<string>('')
  const sessionToken = ref<string>('')
  const userId = ref<string>('')
  const status = ref<HandshakeStatus>('pending')
  const errorCode = ref<string>('')
  const errorMessage = ref<string>('')

  // ── Actions ────────────────────────────────────────────────────────────────

  /**
   * Store handshake data received from Cockpit INIT_WORKSPACE message.
   */
  function initWorkspace(payload: {
    workspaceId: string
    sessionToken: string
    userId: string
  }) {
    workspaceId.value = payload.workspaceId
    sessionToken.value = payload.sessionToken
    userId.value = payload.userId
    status.value = 'pending'
    errorCode.value = ''
    errorMessage.value = ''
  }

  /**
   * Mark workspace as ready after successful backend validation.
   */
  function setReady() {
    status.value = 'ready'
  }

  /**
   * Mark workspace as errored.
   */
  function setError(code: string, message: string) {
    status.value = 'error'
    errorCode.value = code
    errorMessage.value = message
  }

  return {
    workspaceId,
    sessionToken,
    userId,
    status,
    errorCode,
    errorMessage,
    initWorkspace,
    setReady,
    setError,
  }
})
