/**
 * ArtifactsExplorerCell — BaseCell Implementation
 *
 * Pure cell logic with NO Vue/UI dependencies.
 * Orchestrates the unified artifact catalog for the explorer UI.
 * View.vue is the presentation layer; it uses useArtifactsExplorerStore for state.
 */

import { BaseCell } from '@/types/BaseCell'
import type {
  CellResult,
  CellMetadata,
  ValidationError,
  ShowConfig,
} from '@/types/BaseCell'
import { createLogger } from '@/utils/logger'
import { apiFetch } from '@/services/apiService'

const log = createLogger('cell:artifacts-explorer')

/** Valid filter modes for the execute() input. */
type FilterMode = 'all' | 'cells_only'

export class ArtifactsExplorerCell extends BaseCell {
  /**
   * Execute: returns all artifacts from the unified Artifact Runtime Map API.
   * Accepts an optional `filter_mode` input:
   *   - 'cells_only' → passes ?artifact_type=cell-type query param
   *   - 'all' (default) → returns all artifact types
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()

    try {
      const filterMode: FilterMode =
        input.filter_mode === 'cells_only' ? 'cells_only' : 'all'
      const params = filterMode === 'cells_only' ? '?artifact_type=cell-type' : ''
      const response = await apiFetch(`/api/v1/artifacts-map${params}`, { method: 'GET' })
      const data = await response.json()
      const artifacts: any[] = Array.isArray(data) ? data : []

      log.info('[ArtifactsExplorerCell] execute: loaded artifacts', {
        count: artifacts.length,
        filterMode,
      })

      return {
        success: true,
        output: { artifacts },
        execution_time: performance.now() - startTime,
      }
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Unknown error'
      log.error('[ArtifactsExplorerCell] execute failed', { error: msg })
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: msg,
      }
    }
  }

  /**
   * Describe cell capabilities (CellMetadata).
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'artifacts-explorer-cell',
      name: 'Artifacts Explorer',
      version: '2.0.0',
      description:
        'Universal artifact discovery cell. Displays Cells, Services and Workers from the unified Artifact Runtime Map. Supports category filters and stage badges.',
      inputs: {
        filter_mode: {
          type: 'string',
          description: "'all' shows all artifact types with category tabs; 'cells_only' shows only cell-type artifacts without tabs",
          required: false,
          default: 'all',
        },
      },
      outputs: {
        artifacts: {
          type: 'array',
          description: 'List of ArtifactRecord entries from the Artifact Runtime Map',
        },
      },
      tags: ['workspace', 'explorer', 'picker', 'utility', 'artifacts'],
    }
  }

  /**
   * Validate input before execution.
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    if (input.filter_mode && !['all', 'cells_only'].includes(input.filter_mode)) {
      errors.push({
        field: 'filter_mode',
        message: "filter_mode must be 'all' or 'cells_only'",
      })
    }
    return errors
  }

  /**
   * Show: returns componentPath so resolveViewSpec loads View.vue.
   * Overrides default BaseCell.show() to avoid backend discovery overhead.
   */
  async show(_data: Record<string, any>, _options: ShowConfig): Promise<any> {
    log.debug('[ArtifactsExplorerCell] show() called, returning View.vue')
    return {
      componentPath: 'frontend/View.vue',
    }
  }
}

export default ArtifactsExplorerCell
