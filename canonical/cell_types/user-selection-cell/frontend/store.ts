/**
 * @file store.ts
 * @description Pinia store for user-selection-cell.
 *
 * Acts as the Promise ↔ View communication channel:
 * - UserSelectionCell.show() calls open(title, resolve) to register the Promise callback
 * - View.vue reads isOpen / users and calls selectUser(user) or cancel()
 * - selectUser / cancel resolve the Promise and close the overlay
 *
 * Store ID: 'userSelection'
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createLogger } from '@/utils/logger'
import { apiFetch } from '@/services/apiService'

const log = createLogger('store:user-selection')

// ── User interface (mirrors backend User model fields used here) ──────────

export interface SelectableUser {
  id: string
  username: string
  avatar_url?: string | null
}

export const useUserSelectionStore = defineStore('userSelection', () => {
  // ── State ────────────────────────────────────────────────────────────────────
  const isOpen = ref(false)
  const title = ref('Select a User')
  const users = ref<SelectableUser[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const searchQuery = ref('')

  /** Internal Promise resolver — set by open(), consumed by selectUser/cancel */
  let _resolve: ((user: SelectableUser | null) => void) | null = null

  // ── Actions ──────────────────────────────────────────────────────────────────

  /**
   * Load users from GET /api/users/ (backend proxy to CentralHub).
   * Accessible to any authenticated user — no 403 for non-admins.
   *
   * @param query - Optional username search filter (passed as `?q=`)
   */
  async function loadUsers(query?: string): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      const params = new URLSearchParams()
      if (query) params.set('q', query)
      params.set('limit', '50')
      const url = `/api/users/?${params.toString()}`
      const response = await apiFetch(url, { method: 'GET' })
      if (!response.ok) {
        error.value = `Failed to load users (HTTP ${response.status})`
        log.error('[UserSelectionStore] Non-ok response', { status: response.status })
        return
      }
      const data = await response.json()
      users.value = Array.isArray(data) ? data : []
      log.info('[UserSelectionStore] Users loaded', { count: users.value.length })
    } catch (err: any) {
      error.value = err?.message || 'Failed to load users'
      log.error('[UserSelectionStore] loadUsers error', { error: error.value })
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Open the user selection overlay.
   * Called by UserSelectionCell.show() — registers the Promise resolver.
   * If a previous selection is still pending, it is auto-cancelled first.
   *
   * @param overlayTitle - Title shown in the overlay header
   * @param resolve - Promise resolver to call with the selected user or null
   * @param query - Optional initial search query
   */
  async function open(
    overlayTitle: string,
    resolve: (user: SelectableUser | null) => void,
    query?: string,
  ): Promise<void> {
    // Auto-cancel any orphaned pending selection before opening a new one
    if (_resolve) {
      log.warn('[UserSelectionStore] Auto-cancelling orphaned pending selection')
      const orphanedResolve = _resolve
      _resolve = null
      orphanedResolve(null)
    }
    title.value = overlayTitle
    searchQuery.value = query ?? ''
    _resolve = resolve
    isOpen.value = true
    log.debug('[UserSelectionStore] Overlay opened', { title: overlayTitle })
    await loadUsers(searchQuery.value || undefined)
  }

  /**
   * Confirm selection of a user.
   * Resolves the Promise with the selected user and closes the overlay.
   *
   * @param user - The user that was selected
   */
  function selectUser(user: SelectableUser): void {
    log.info('[UserSelectionStore] User selected', { username: user.username })
    if (_resolve) {
      _resolve(user)
      _resolve = null
    }
    isOpen.value = false
  }

  /**
   * Cancel the selection.
   * Resolves the Promise with null and closes the overlay.
   */
  function cancel(): void {
    log.debug('[UserSelectionStore] Selection cancelled')
    if (_resolve) {
      _resolve(null)
      _resolve = null
    }
    isOpen.value = false
  }

  // ── Return ───────────────────────────────────────────────────────────────────
  return {
    isOpen,
    title,
    users,
    isLoading,
    error,
    searchQuery,
    loadUsers,
    open,
    selectUser,
    cancel,
  }
})
