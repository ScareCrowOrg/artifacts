/**
 * @file store.ts
 * @description Pinia store for artifacts-explorer-cell.
 *
 * Manages the list of available artifacts and the currently selected artifact.
 * App.vue watches `selectedArtifact` to instantiate cell-type artifacts.
 *
 * Store ID: 'artifactsExplorer'
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { createLogger } from '@/utils/logger'
import { apiFetch } from '@/services/apiService'

const log = createLogger('store:artifacts-explorer')

// ── ArtifactRecord interfaces (mirrors backend/app/models/artifact.py) ────────

export interface ArtifactIdentity {
  name: string
  description: string
  icon: string | null
  author: string
}

export interface ArtifactDependencyGraph {
  services: string[]
  cell_types: string[]
  book_types: string[]
  workers: string[]
  shared_utils: string[]
  viewers: string[]
}

export interface ArtifactRuntime {
  entry_point: string | null
  strategy: 'frontend_injection' | 'docker_orchestration' | 'python_subprocess'
  dependencies: ArtifactDependencyGraph
  env_vars: string[]
}

export interface ArtifactExecutionModel {
  orchestrator: 'frontend' | 'launcher'
  heartbeat_channel: string | null
  health_check: string | null
}

export interface ArtifactMetadata {
  tags: string[]
  /** File refs from type.json (e.g. basecell, view). Populated for cell-type artifacts. */
  default_refs?: Record<string, string[]>
}

export interface ExplorerArtifact {
  artifact_id: string
  version: string
  artifact_type: 'cell-type' | 'service' | 'worker' | 'book' | 'job-type'
  stage: 'canonical' | 'sandbox' | 'runtime'
  identity: ArtifactIdentity
  runtime: ArtifactRuntime
  execution_model: ArtifactExecutionModel
  metadata: ArtifactMetadata
}

export type FilterMode = 'all' | 'cells_only'

export const useArtifactsExplorerStore = defineStore('artifactsExplorer', () => {
  // ── State ────────────────────────────────────────────────────────────────────
  const availableArtifacts = ref<ExplorerArtifact[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const selectedArtifact = ref<ExplorerArtifact | null>(null)
  const manageArtifactTarget = ref<ExplorerArtifact | null>(null)

  // ── Actions ──────────────────────────────────────────────────────────────────

  /**
   * Load artifacts from the unified Artifact Runtime Map API.
   * When filterMode is 'cells_only', passes ?artifact_type=cell-type to the backend
   * so only cell-type artifacts are fetched (server-side filter, no extra payload).
   */
  async function loadArtifacts(filterMode: FilterMode = 'all'): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      const params =
        filterMode === 'cells_only' ? '?artifact_type=cell-type' : ''
      const response = await apiFetch(`/api/artifacts-map${params}`, { method: 'GET' })
      if (!response.ok) {
        log.warn('[DIAG] [ArtifactsExplorerStore] API returned non-OK status', {
          status: response.status,
          statusText: response.statusText,
          filterMode,
        })
      }
      const data = await response.json()
      availableArtifacts.value = Array.isArray(data) ? data : []
      log.info('[ArtifactsExplorerStore] Artifacts loaded', {
        count: availableArtifacts.value.length,
        filterMode,
      })
    } catch (err: any) {
      error.value = err?.message || 'Failed to load artifacts'
      log.error('[ArtifactsExplorerStore] Failed to load artifacts', { error: error.value })
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Select an artifact. For orchestrator === 'frontend' artifacts, triggers the
   * App.vue watcher to instantiate the cell type in the grid.
   */
  function selectArtifact(artifact: ExplorerArtifact): void {
    log.info('[ArtifactsExplorerStore] Artifact selected', {
      name: artifact.identity.name,
      orchestrator: artifact.execution_model.orchestrator,
    })
    selectedArtifact.value = artifact
  }

  /**
   * Clear the selection after App.vue has processed the selected artifact.
   */
  function clearSelection(): void {
    log.debug('[ArtifactsExplorerStore] Selection cleared')
    selectedArtifact.value = null
  }

  /**
   * Trigger the manage flow for an artifact.
   * Sets manageArtifactTarget which App.vue watches to open the artifacts-manager-cell.
   */
  function triggerManageArtifact(artifact: ExplorerArtifact): void {
    log.info('[ArtifactsExplorerStore] Manage triggered', {
      name: artifact.identity.name,
      artifactId: artifact.artifact_id,
    })
    manageArtifactTarget.value = artifact
  }

  /**
   * Clear the manage target after App.vue has processed it.
   */
  function clearManageArtifactTarget(): void {
    log.debug('[ArtifactsExplorerStore] Manage target cleared')
    manageArtifactTarget.value = null
  }

  // ── Computed (derived from availableArtifacts) ────────────────────────────────

  /**
   * Cell-type definitions derived from availableArtifacts.
   * Used by App.vue's findCellTypeByName() and handleLoadLayout() for cell lookup.
   * Filters artifacts where artifact_type === 'cell-type' and maps to CellTypeDefinition shape.
   */
  const availableCellTypes = computed(() => {
    const result = availableArtifacts.value
      .filter(a => a.artifact_type === 'cell-type')
      .map(a => {
        return {
          name: a.artifact_id,
          id: a.artifact_id,
          description: a.identity.description,
          version: a.version,
          icon: a.identity.icon ?? undefined,
          can_render_dynamically: true,
          stage: a.stage,
          default_refs: a.metadata.default_refs as Record<string, string[]> | undefined,
        }
      })
    return result
  })

  /**
   * Load cell types by fetching cell-type artifacts only.
   * Wraps loadArtifacts('cells_only') and resets the selection.
   */
  async function loadCellTypes(): Promise<void> {
    await loadArtifacts('cells_only')
    clearSelection()
  }

  // ── Return ───────────────────────────────────────────────────────────────────
  return {
    availableArtifacts,
    isLoading,
    error,
    selectedArtifact,
    manageArtifactTarget,
    availableCellTypes,
    loadArtifacts,
    loadCellTypes,
    selectArtifact,
    clearSelection,
    triggerManageArtifact,
    clearManageArtifactTarget,
  }
})
