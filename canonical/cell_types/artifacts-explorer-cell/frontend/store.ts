/**
 * @file store.ts
 * @description Pinia store for artifacts-explorer-cell.
 *
 * Manages the list of available cell types and the currently selected cell type.
 * App.vue watches `selectedCellType` to instantiate the selected cell type.
 *
 * Store ID: 'artifactsExplorer'
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createLogger } from '@/utils/logger'
import { apiFetch } from '@/services/apiService'

const log = createLogger('store:artifacts-explorer')

/**
 * Minimal cell type info shape returned by the backend API.
 * Structurally compatible with CellTypeDefinition from the viewer types.
 */
export interface ExplorerCellType {
  name: string
  id: string
  description?: string
  version?: string
  category?: string
  icon?: string
  can_render_dynamically?: boolean
  default_refs?: Record<string, string[]>
  [key: string]: any
}

export const useArtifactsExplorerStore = defineStore('artifactsExplorer', () => {
  // ── State ────────────────────────────────────────────────────────────────────
  const availableCellTypes = ref<ExplorerCellType[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const selectedCellType = ref<ExplorerCellType | null>(null)

  // ── Actions ──────────────────────────────────────────────────────────────────

  /**
   * Load renderable cell types from the backend API.
   * Filters out types with can_render_dynamically === false.
   */
  async function loadCellTypes(): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      const response = await apiFetch('/api/cells/types/list', { method: 'GET' })
      const data = await response.json()
      let types: ExplorerCellType[]
      if (Array.isArray(data)) {
        types = data
      } else if (data && Array.isArray(data.types)) {
        types = data.types
      } else {
        log.warn('[ArtifactsExplorerStore] Unexpected API response format', {
          keys: Object.keys(data || {}),
        })
        types = []
      }
      availableCellTypes.value = types.filter((t) => t.can_render_dynamically !== false)
      log.info('[ArtifactsExplorerStore] Cell types loaded', {
        count: availableCellTypes.value.length,
      })
    } catch (err: any) {
      error.value = err?.message || 'Failed to load cell types'
      log.error('[ArtifactsExplorerStore] Failed to load cell types', { error: error.value })
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Select a cell type. Triggers the App.vue watcher to instantiate it.
   */
  function selectCellType(cellType: ExplorerCellType): void {
    log.info('[ArtifactsExplorerStore] Cell type selected', { name: cellType.name })
    selectedCellType.value = cellType
  }

  /**
   * Clear the selection after App.vue has processed the selected cell type.
   */
  function clearSelection(): void {
    log.debug('[ArtifactsExplorerStore] Selection cleared')
    selectedCellType.value = null
  }

  // ── Return ───────────────────────────────────────────────────────────────────
  return {
    availableCellTypes,
    isLoading,
    error,
    selectedCellType,
    loadCellTypes,
    selectCellType,
    clearSelection,
  }
})
