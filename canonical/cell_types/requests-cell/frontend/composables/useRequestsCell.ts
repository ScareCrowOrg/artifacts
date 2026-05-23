/**
 * @file useRequestsCell.ts
 * @description Composable that encapsulates RequestsCell.execute() calls with
 * reactive state for loading, error, and requests.
 *
 * This composable is also imported by planet-hall/App.vue to sync the requests
 * state for allowanceStatus detection (anti-spam behavior from PR #2947).
 */

import { ref, readonly } from 'vue'
import { RequestsCell } from '../RequestsCell'

export function useRequestsCell() {
  const cell = new RequestsCell()
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const requests = ref<any[]>([])

  async function loadRequests() {
    isLoading.value = true
    error.value = null
    try {
      const result = await cell.execute({ action: 'list_requests' })
      if (result.success) {
        requests.value = Array.isArray(result.output) ? result.output : []
      } else {
        error.value = result.error || 'Failed to load requests'
      }
    } catch (e: any) {
      error.value = e.message || 'Failed to load requests'
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Inject a pending request directly into the reactive buffer so the UI
   * updates instantly (no server round-trip). Used by planet-hall for the
   * anti-spam allowanceStatus indicator.
   */
  function injectLocalRequest(newItem: any) {
    requests.value = [...requests.value, newItem]
  }

  return {
    isLoading: readonly(isLoading),
    error: readonly(error),
    requests: readonly(requests),
    loadRequests,
    injectLocalRequest,
  }
}
