/**
 * ArtifactsManagerCell — BaseCell Implementation
 *
 * Pure cell logic with NO Vue/UI dependencies.
 * Displays artifact metadata and provides management actions (Allow).
 * The allowArtifact() method is migrated from ArtifactsExplorerCell.
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
import { UserSelectionCell } from '#canonical/cell_types/user-selection-cell/frontend/UserSelectionCell'
import type { SelectableUser } from '#canonical/cell_types/user-selection-cell/frontend/store'

const log = createLogger('cell:artifacts-manager')

export class ArtifactsManagerCell extends BaseCell {
  /** UserSelectionCell instance — created once and reused for all allowArtifact() calls. */
  private readonly _userSelectionCell = new UserSelectionCell()

  /**
   * Execute: returns the artifact metadata stored in initial_data.
   * Returns an error if no artifact data is available.
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()

    try {
      const artifactId = input.artifact_id || this._initialData?.artifact_id
      const artifactData = input.artifact_data || this._initialData?.artifact_data

      if (!artifactId) {
        return {
          success: false,
          output: {},
          execution_time: performance.now() - startTime,
          error: 'No artifact_id provided. Cannot display artifact manager.',
        }
      }

      log.info('[ArtifactsManagerCell] execute: returning artifact metadata', {
        artifactId,
        hasData: !!artifactData,
      })

      return {
        success: true,
        output: {
          artifact_id: artifactId,
          artifact_data: artifactData,
          metadata: artifactData?.metadata || {},
          identity: artifactData?.identity || {},
          runtime: artifactData?.runtime || {},
          execution_model: artifactData?.execution_model || {},
          stage: artifactData?.stage || '',
          version: artifactData?.version || '',
        },
        execution_time: performance.now() - startTime,
      }
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Unknown error'
      log.error('[ArtifactsManagerCell] execute failed', { error: msg })
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
      id: 'artifacts-manager-cell',
      name: 'Artifacts Manager',
      version: '1.0.0',
      description:
        'Artifact detail manager. Displays metadata and provides management actions (Allow) for artifacts discovered in the explorer.',
      inputs: {
        artifact_id: {
          type: 'string',
          description: 'The artifact ID from the Artifact Runtime Map',
          required: true,
        },
        artifact_data: {
          type: 'object',
          description: 'Full artifact record data (identity, runtime, execution_model, metadata, stage, version)',
          required: false,
        },
      },
      outputs: {
        metadata: {
          type: 'object',
          description: 'The artifact metadata in readable JSON format',
        },
      },
      tags: ['workspace', 'manager', 'artifacts', 'allowance'],
    }
  }

  /**
   * Validate input before execution.
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    const artifactId = input.artifact_id || this._initialData?.artifact_id
    if (!artifactId) {
      errors.push({
        field: 'artifact_id',
        message: 'artifact_id is required',
      })
    }
    return errors
  }

  /**
   * Show: returns componentPath so resolveViewSpec loads View.vue.
   */
  async show(_data: Record<string, any>, _options: ShowConfig): Promise<any> {
    log.debug('[ArtifactsManagerCell] show() called, returning View.vue')
    return {
      componentPath: 'frontend/View.vue',
    }
  }

  /**
   * Allow an artifact: opens the user-selection overlay, and if the user
   * confirms, persists the allowance via POST /api/local/allowance.
   *
   * - If the user cancels (null): returns null without calling the backend.
   * - If the backend call fails: throws an Error so the View can handle it.
   *
   * @param artifactId - The ID of the artifact to grant allowance for
   * @returns The selected user, or null on cancel
   */
  async allowArtifact(artifactId: string): Promise<SelectableUser | null> {
    log.info('[ArtifactsManagerCell] allowArtifact() called', { artifactId })
    const user = await this._userSelectionCell.show({}, {
      mode: 'pick-one',
      title: 'Select user for allowance',
    })

    if (!user) {
      log.debug('[ArtifactsManagerCell] allowArtifact() cancelled', { artifactId })
      return null
    }

    log.info('[ArtifactsManagerCell] allowArtifact() user selected, persisting', {
      artifactId,
      selected: user.name,
    })

    const response = await apiFetch('/api/local/allowance', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ artifact_id: artifactId, user_id: user.id }),
    })

    if (!response.ok) {
      const detail = await response.text()
      log.error('[ArtifactsManagerCell] allowArtifact() backend error', {
        status: response.status,
        detail,
      })
      throw new Error(`Failed to grant permission (${response.status}): ${detail}`)
    }

    log.info('[ArtifactsManagerCell] allowArtifact() persisted successfully', {
      artifactId,
      userId: user.id,
    })
    return user
  }
}

export default ArtifactsManagerCell
