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
import { ref } from 'vue'
import { createLogger } from '@/utils/logger'
import { apiFetch } from '@/services/apiService'
import { useWorkspaceStore } from '@/stores/workspaceStore'

const log = createLogger('store:artifacts-explorer')

// ── ArtifactRecord interfaces (mirrors backend/app/models/artifact.py) ────────

export interface ArtifactIdentity {
  name: string
  description: string
  icon: string | null
  author: string
}

export interface ArtifactRuntime {
  entry_point: string | null
  strategy: 'frontend_injection' | 'docker_orchestration' | 'python_subprocess'
  required_artifacts: string[]
  env_vars: string[]
}

export interface ArtifactExecutionModel {
  orchestrator: 'frontend' | 'launcher'
  heartbeat_channel: string | null
  health_check: string | null
}

export interface ArtifactMetadata {
  tags: string[]
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
      // [DEBUG-2887] Log the full URL being called and current token state
      const wsStore = useWorkspaceStore()
      const hasToken = !!wsStore.sessionToken
      log.info('[DEBUG-2887][ArtifactsExplorerStore] loadArtifacts called', {
        filterMode,
        url: `/api/artifacts-map${params}`,
        hasToken,
      })
      const response = await apiFetch(`/api/artifacts-map${params}`, { method: 'GET' })
      // [DEBUG-2887] Log response status
      log.info('[DEBUG-2887][ArtifactsExplorerStore] Response received', {
        status: response.status,
        ok: response.ok,
        url: response.url,
      })
      const data = await response.json()
      // [DEBUG-2887] Log raw response structure
      const isArray = Array.isArray(data)
      const count = isArray ? data.length : -1
      const firstItem = isArray && data.length > 0 ? {
        artifact_id: data[0]?.artifact_id,
        artifact_type: data[0]?.artifact_type,
        stage: data[0]?.stage,
        identity_type: typeof data[0]?.identity,
        has_execution_model: !!data[0]?.execution_model,
      } : null
      log.info('[DEBUG-2887][ArtifactsExplorerStore] Raw data', {
        isArray,
        count,
        firstItem,
      })
      availableArtifacts.value = isArray ? data : []
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

  // ── Return ───────────────────────────────────────────────────────────────────
  return {
    availableArtifacts,
    isLoading,
    error,
    selectedArtifact,
    loadArtifacts,
    selectArtifact,
    clearSelection,
  }
})
