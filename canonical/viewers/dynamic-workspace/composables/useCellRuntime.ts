/**
 * composables/useCellRuntime.ts
 *
 * Cell state persistence for DynamicWorkspace — persisted cell runtime.
 * Calls the existing /api/cells endpoints with scope=published to save,
 * update, list, and delete cell state in MongoDB via CentralHub.
 *
 * Design:
 * - Uses apiFetch (same as usePersistenceManager) for authenticated HTTP calls
 * - All endpoints use scope=published to route to CentralHub → MongoDB
 * - Errors are handled gracefully (warn log, no throw in loadPersistedCells)
 * - No direct grid mutations — returns data for the caller (App.vue) to hydrate
 *
 * @see cells_router.py — endpoints exist and are unchanged
 * @see collections.py — "cells" must be in RUNTIME_COLLECTIONS for routing
 */

import { useWorkspaceStore } from '@/stores/workspaceStore'
import { apiFetch } from '@/services/apiService'
import { createLogger } from '@/utils/logger'
import type { CellTypeDefinition } from '../types'

const log = createLogger('workspace:cell-runtime')

// ── Types ─────────────────────────────────────────────────────────────────────

/** Shape returned by GET /api/cells/list for a single persisted cell */
export interface PersistedCell {
  _id: string
  id?: string
  assignee_id: string
  notebook_item_type_id: string
  initial_data?: Record<string, any>
  fragments?: Array<Record<string, any>>
  status?: string
  category?: string
  title?: string
  created_at?: string
  updated_at?: string
}

/** Return shape from POST /api/cells/create */
export interface CreateCellResponse {
  _id: string
  id?: string
  _scope?: string
  _location?: string
  [key: string]: any
}

// ── Composable ────────────────────────────────────────────────────────────────

export function useCellRuntime() {
  const store = useWorkspaceStore()

  /**
   * Get the current user's ID from the workspace store.
   * Returns empty string if not yet available (handshake pending).
   */
  function getAssigneeId(): string {
    return store.userId || ''
  }

  /**
   * Save a new cell runtime snapshot in MongoDB via CentralHub.
   *
   * POST /api/cells/create?scope=published
   *
   * @param notebookItemTypeId  UUID of the NotebookItemType (cell type)
   * @param initialData         Current cell state to persist
   * @returns                   The created cell document with _id
   */
  async function saveCellRuntime(
    notebookItemTypeId: string,
    initialData: Record<string, any>,
    title?: string,
  ): Promise<CreateCellResponse | null> {
    const assigneeId = getAssigneeId()
    if (!assigneeId) {
      log.warn('[CellRuntime] Cannot save: assignee_id not available')
      return null
    }

    log.info('[CellRuntime] Saving cell runtime', { notebookItemTypeId })

    try {
      const response = await apiFetch('/cells/create?scope=published', {
        method: 'POST',
        body: JSON.stringify({
          notebook_item_type_id: notebookItemTypeId,
          assignee_id: assigneeId,
          initial_data: initialData,
          category: 'persistent',
          title: title || 'Persisted Cell',
        }),
      })

      if (!response.ok) {
        log.warn('[CellRuntime] Save request failed', { status: response.status })
        return null
      }

      const result = await response.json()
      log.info('[CellRuntime] Cell runtime saved', { _id: result._id || result.id })
      return result as CreateCellResponse
    } catch (err: any) {
      log.error('[CellRuntime] Failed to save cell runtime', { error: err?.message })
      return null
    }
  }

  /**
   * Update an existing cell runtime snapshot.
   *
   * PUT /api/cells/{cellId}/update?scope=published
   * PUT /api/cells/{cellId} (fallback)
   *
   * @param cellId      MongoDB _id of the persisted cell
   * @param initialData Updated cell state to persist
   */
  async function updateCellRuntime(
    cellId: string,
    initialData: Record<string, any>,
  ): Promise<boolean> {
    if (!cellId) {
      log.warn('[CellRuntime] Cannot update: no cellId provided')
      return false
    }

    log.info('[CellRuntime] Updating cell runtime', { cellId })

    try {
      const response = await apiFetch(`/cells/${cellId}/update?scope=published`, {
        method: 'PUT',
        body: JSON.stringify({ initial_data: initialData }),
      })

      if (!response.ok) {
        // Try PUT /cells/{cellId} fallback
        const fallbackResponse = await apiFetch(`/cells/${cellId}?scope=published`, {
          method: 'PUT',
          body: JSON.stringify({ initial_data: initialData }),
        })
        if (!fallbackResponse.ok) {
          throw new Error(`HTTP ${fallbackResponse.status}: ${fallbackResponse.statusText}`)
        }
      }

      log.info('[CellRuntime] Cell runtime updated', { cellId })
      return true
    } catch (err: any) {
      log.error('[CellRuntime] Failed to update cell runtime', { cellId, error: err?.message })
      return false
    }
  }

  /**
   * List all persisted cells for the current user.
   *
   * GET /api/cells/list?assignee_id=X
   * Filters results to category === "persistent" (in-memory).
   *
   * @returns Array of persisted cells for the current user
   */
  async function listCellRuntimes(): Promise<PersistedCell[]> {
    const assigneeId = getAssigneeId()
    if (!assigneeId) {
      log.warn('[CellRuntime] Cannot list: assignee_id not available')
      return []
    }

    log.info('[CellRuntime] Listing cell runtimes', { assigneeId })

    try {
      const response = await apiFetch(`/cells/list?scope=published&assignee_id=${encodeURIComponent(assigneeId)}`)

      if (!response.ok) {
        log.warn('[CellRuntime] List request failed', { status: response.status })
        return []
      }

      const cells = (await response.json()) as PersistedCell[]

      // Filter to only cells with category === "persistent" (saved cells)
      // The frontend sends category='persistent' at request root level,
      // and the backend stores it as-is via CreateCellRequest.category field.
      // Old records may have category inside initial_data as a secondary fallback.
      const persistedCells = cells.filter(
        c => c.category === 'persistent' || (c.initial_data && c.initial_data.category === 'persistent'),
      )

      log.info('[CellRuntime] Listed cell runtimes', {
        total: cells.length,
        persisted: persistedCells.length,
      })

      return persistedCells
    } catch (err: any) {
      log.warn('[CellRuntime] Failed to list cell runtimes', { error: err?.message })
      return []
    }
  }

  /**
   * Delete a persisted cell runtime.
   *
   * DELETE /api/cells/{cellId}?scope=published
   *
   * @param cellId MongoDB _id of the persisted cell to delete
   * @returns      True if deletion was successful
   */
  async function deleteCellRuntime(cellId: string): Promise<boolean> {
    if (!cellId) {
      log.warn('[CellRuntime] Cannot delete: no cellId provided')
      return false
    }

    log.info('[CellRuntime] Deleting cell runtime', { cellId })

    try {
      const response = await apiFetch(`/cells/${cellId}?scope=published`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        log.warn('[CellRuntime] Delete request failed', { cellId, status: response.status })
        return false
      }

      log.info('[CellRuntime] Cell runtime deleted', { cellId })
      return true
    } catch (err: any) {
      log.warn('[CellRuntime] Failed to delete cell runtime', { cellId, error: err?.message })
      return false
    }
  }

  return {
    saveCellRuntime,
    updateCellRuntime,
    listCellRuntimes,
    deleteCellRuntime,
    getAssigneeId,
  }
}
