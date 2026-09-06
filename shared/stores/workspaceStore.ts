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
import { computed, ref } from 'vue'

export type HandshakeStatus = 'pending' | 'ready' | 'error'
export type ThemeMode = 'light' | 'dark' | 'auto'

export const useWorkspaceStore = defineStore('workspace-v2', () => {
  // ── State ──────────────────────────────────────────────────────────────────
  const workspaceId = ref<string>('')
  const sessionToken = ref<string>('')
  const userId = ref<string>('')
  const planetOwnerId = ref<string>('')
  const status = ref<HandshakeStatus>('pending')
  const errorCode = ref<string>('')
  const errorMessage = ref<string>('')

  // ── Theme & Locale State (synchronized with host shell) ──────────────────
  const theme = ref<ThemeMode>('auto')
  const locale = ref<string>('en')

  // ── Computed ─────────────────────────────────────────────────────────────────
  /** True when the current session user is the planet owner (used for owner-only gates). */
  const isOwner = computed<boolean>(
    () => !!userId.value && !!planetOwnerId.value && userId.value === planetOwnerId.value,
  )

  // ── Actions ────────────────────────────────────────────────────────────────

  /**
   * Store handshake data received from Cockpit INIT_WORKSPACE message.
   *
   * `planetOwnerId` is sourced from the body of POST /api/v1/auth/session-bind
   * (auth_session_router.py:408-415) and forwarded by the cockpit in the
   * handshake payload. It is the namespace of promoted artifacts.
   */
  function initWorkspace(payload: {
    workspaceId: string
    sessionToken: string
    userId: string
    planetOwnerId?: string
  }) {
    workspaceId.value = payload.workspaceId
    sessionToken.value = payload.sessionToken
    userId.value = payload.userId
    planetOwnerId.value = payload.planetOwnerId ?? ''
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

  /**
   * Update theme preference (synchronized from host shell).
   */
  function setTheme(newTheme: ThemeMode) {
    theme.value = newTheme
  }

  /**
   * Update locale preference (synchronized from host shell).
   */
  function setLocale(newLocale: string) {
    locale.value = newLocale
  }

  return {
    workspaceId,
    sessionToken,
    userId,
    planetOwnerId,
    isOwner,
    status,
    errorCode,
    errorMessage,
    theme,
    locale,
    initWorkspace,
    setReady,
    setError,
    setTheme,
    setLocale,
  }
})
