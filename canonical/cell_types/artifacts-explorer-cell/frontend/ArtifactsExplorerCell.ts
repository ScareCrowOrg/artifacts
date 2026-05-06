/**
 * ArtifactsExplorerCell — BaseCell Implementation
 *
 * Pure cell logic with NO Vue/UI dependencies.
 * Orchestrates the list of available cell types for the picker UI.
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

export class ArtifactsExplorerCell extends BaseCell {
  /**
   * Execute: returns the list of renderable cell types from the backend API.
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()

    try {
      const response = await apiFetch('/api/cells/types/list', { method: 'GET' })
      const data = await response.json()
      const types: any[] = Array.isArray(data) ? data : (data.types ?? [])
      const renderable = types.filter((t) => t.can_render_dynamically !== false)

      log.info('[ArtifactsExplorerCell] execute: loaded cell types', { count: renderable.length })

      return {
        success: true,
        output: { cellTypes: renderable },
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
      version: '1.0.0',
      description:
        'Workspace utility cell. In picker mode, shows a searchable grid of available cell types so the user can add them to the dynamic workspace.',
      inputs: {
        mode: {
          type: 'string',
          description: "Display mode: 'picker' (browse/select) or 'view' (reserved for Phase 2)",
          required: false,
          default: 'picker',
        },
      },
      outputs: {
        cellTypes: {
          type: 'array',
          description: 'List of renderable cell type definitions',
        },
      },
      tags: ['workspace', 'explorer', 'picker', 'utility'],
    }
  }

  /**
   * Validate input before execution.
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    if (input.mode && !['picker', 'view'].includes(input.mode)) {
      errors.push({
        field: 'mode',
        message: "mode must be 'picker' or 'view'",
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
