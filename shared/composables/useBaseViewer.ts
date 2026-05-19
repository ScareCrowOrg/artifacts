/**
 * useBaseViewer.ts
 *
 * Base composable for standalone viewers. Provides HTTP client (delegating to
 * apiService.ts), auth detection, loading state management, and utilities.
 *
 * The apiFetch exposed here is a convenience wrapper around apiService.apiFetch:
 * - If workspaceStore (Pinia) is available → Bearer token auth
 * - If not (standalone viewer) → cookie-based auth (credentials: 'include')
 * This ensures a SINGLE fetch pattern across the entire codebase.
 *
 * Dependencies:
 * - vue (ref)
 * - @/services/apiService (getApiBaseUrl, normalizePath, apiFetch)
 * - No Pinia, workspaceStore, or Cockpit dependency
 */

import { ref, type Ref } from 'vue'
import { getApiBaseUrl, normalizePath, apiFetch as apiServiceFetch } from '@/services/apiService'

// ── Auth Constants (internal) ────────────────────────────────────────────

const TOKEN_KEY = 'scareverse_token'

// ── Composable ────────────────────────────────────────────────────────────

export function useBaseViewer() {
  // ── URL Resolution ────────────────────────────────────────────────────
  const API_BASE = getApiBaseUrl()

  // ── Reactive State ────────────────────────────────────────────────────
  const loadingState: Ref<boolean> = ref(true)
  const errorMessage: Ref<string> = ref('')
  const isAuthenticated: Ref<boolean> = ref(false)
  const sessionToken: Ref<string> = ref('')

  // ── HTTP Client ───────────────────────────────────────────────────────
  // Convenience wrapper around apiService.apiFetch. Adds JSON parsing and
  // reactive error state. The auth strategy is handled transparently:
  //   - With Pinia/token → Bearer header (cells, dynamic-workspace)
  //   - Without Pinia/token → cookie-based (standalone viewers)

  async function apiFetch(path: string, options: RequestInit = {}) {
    try {
      const response = await apiServiceFetch(path, options)

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
      }

      return response.json()
    } catch (err) {
      errorMessage.value = (err as Error).message
      throw err
    }
  }

  // ── Auth ──────────────────────────────────────────────────────────────

  /**
   * Exchange a JWT (from localStorage) for an httpOnly session cookie.
   * Matches ViewerShell's bootstrapSession() pattern.
   */
  async function bindSession(token: string): Promise<boolean> {
    try {
      const url = normalizePath('/api/v1/auth/session-bind')
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        credentials: 'include',
      })
      return response.ok
    } catch {
      return false
    }
  }

  /**
   * Detect authentication status:
   * 1. Try JWT from localStorage → session-bind → httpOnly cookie
   * 2. Fallback: probe with existing sessionId cookie
   */
  async function checkAuth() {
    const token = localStorage.getItem(TOKEN_KEY)
    if (token) {
      sessionToken.value = token
      const bound = await bindSession(token)
      if (bound) {
        isAuthenticated.value = true
        return
      }
    }

    // Fallback: probe with existing sessionId cookie
    try {
      const url = normalizePath('/api/inbox/requests?status=pending')
      const response = await fetch(url, {
        method: 'GET',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      })
      isAuthenticated.value = response.ok
    } catch {
      isAuthenticated.value = false
    }
  }

  // ── Lifecycle Helper ──────────────────────────────────────────────────

  /**
   * Wraps a data-loading function with loading/error state management.
   * Usage:
   *   await loadData(async () => {
   *     const data = await apiFetch('/api/endpoint')
   *     items.value = data
   *   })
   */
  async function loadData(loader: () => Promise<void>) {
    loadingState.value = true
    errorMessage.value = ''
    try {
      await loader()
    } catch (err) {
      errorMessage.value = (err as Error).message
    } finally {
      loadingState.value = false
    }
  }

  // ── Utilities ─────────────────────────────────────────────────────────

  function formatDate(isoStr?: string): string {
    if (!isoStr) return ''
    const d = new Date(isoStr)
    if (isNaN(d.getTime())) return isoStr
    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
  }

  // ── Return ────────────────────────────────────────────────────────────

  return {
    // URL resolution
    API_BASE,
    normalizePath,

    // Reactive state
    loadingState,
    errorMessage,
    isAuthenticated,
    sessionToken,

    // HTTP client (delega para apiService.ts — ver doc acima)
    apiFetch,

    // Auth
    bindSession,
    checkAuth,

    // Lifecycle
    loadData,

    // Utilities
    formatDate,
  }
}
