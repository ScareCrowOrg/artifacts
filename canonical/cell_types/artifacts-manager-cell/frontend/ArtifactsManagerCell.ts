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
// Pure promotion helpers — dependency-free module isolated for unit testing.
import { artifactTypeToDirName, classifyPromoteError, PromoteError } from './promotion'
import type { DependencyPreview, PromoteErrorCode, PromotionSummary } from './promotion'
// Re-exported so the View / tests can import from this module.
export { artifactTypeToDirName, classifyPromoteError, PromoteError } from './promotion'
export type { PromoteErrorCode, DependencyPreview, PromotionSummary } from './promotion'

const log = createLogger('cell:artifacts-manager')

/** A single allowance entry returned by the list endpoint. */
export interface AllowanceEntry {
  user_id: string
  name?: string
  avatar_url?: string | null
  artifact_id: string
  granted_at: string
}

export class ArtifactsManagerCell extends BaseCell {
  /** UserSelectionCell instance — created once and reused for all allowArtifact() calls. */
  private readonly _userSelectionCell = new UserSelectionCell()

  /** Current artifact lifecycle stage (sandbox | runtime | canonical). Set via setStage(). */
  private _stage = ''

  /**
   * Set the artifact lifecycle stage. Called by the View on mount and after a
   * successful promotion, so allowance methods can be gated defensively
   * (allowance only exists for promoted, stage='runtime', artifacts).
   */
  setStage(stage: string): void {
    this._stage = stage
  }

  /**
   * Allowance is only available after the artifact is promoted to runtime.
   * Pure predicate — used by the View and by the allowance methods below.
   */
  canAllow(stage: string): boolean {
    return stage === 'runtime'
  }

  /**
   * Promote an artifact (plus its transitive dependencies) from sandbox to the
   * planet owner's runtime namespace (`runtime/user/{owner}/`).
   *
   * Steps:
   * 1. Map the artifact record type to the /bundle directory name (pure fn).
   * 2. POST /api/v1/artifacts/bundle with `source_stage:'sandbox'` +
   *    `include_dependencies:true` → `bundle_id` + resolved dependencies.
   * 3. POST /api/v1/artifacts/promote with `{ bundle_id, strategy:'copy' }`
   *    (NO target_user_id — the backend defaults to the planet owner).
   *
   * Errors are mapped to {@link PromoteError} with a specific code so the View
   * can surface a friendly i18n message (403 non-owner / 409 conflict /
   * 422 validation / unsupported type).
   *
   * @param artifact_type - Artifact record type, e.g. 'cell-type'.
   * @param slug - Artifact slug/id (the artifact_id from the runtime map).
   */
  async promoteArtifact(artifact_type: string, slug: string): Promise<PromotionSummary> {
    const typeDir = artifactTypeToDirName(artifact_type)
    if (!typeDir) {
      throw new PromoteError(
        'promoteUnsupportedType',
        `Unsupported artifact type "${artifact_type}" — only cell-type/book/service/worker/job-type are promotable`,
      )
    }
    log.info('[ArtifactsManagerCell] promoteArtifact() start', { artifactType: artifact_type, typeDir, slug })

    // Step 1: bundle the artifact + transitive deps from sandbox.
    const bundleResp = await apiFetch('/api/v1/artifacts/bundle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_stage: 'sandbox',
        artifact_type: typeDir,
        slug,
        include_dependencies: true,
        dry_run: false,
      }),
    })
    const bundleData = await this._parseArtifactsResponse<{ bundle_id?: string; dependencies?: DependencyPreview[] }>(
      bundleResp,
      'bundle',
    )
    const bundleId = bundleData.bundle_id
    if (!bundleId) {
      throw new PromoteError('promoteInvalid', 'Bundle creation returned no bundle_id')
    }

    // Step 2: promote — no target_user_id (backend defaults to the planet owner).
    const promoteResp = await apiFetch('/api/v1/artifacts/promote', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bundle_id: bundleId, strategy: 'copy' }),
    })
    const promoteData = await this._parseArtifactsResponse<{
      status?: string
      entries?: Array<{ artifact_type: string; slug: string; target_path: string }>
    }>(promoteResp, 'promote')
    const entries = promoteData.entries || []
    const promotedCount = entries.length

    log.info('[ArtifactsManagerCell] promoteArtifact() done', { bundleId, promotedCount })
    return { bundleId, promotedCount, entries }
  }

  /**
   * Preview the transitive dependencies that WOULD be bundled for promotion,
   * without creating a bundle. Calls /bundle with `dry_run: true`.
   *
   * @param artifact_type - Artifact record type, e.g. 'cell-type'.
   * @param slug - Artifact slug/id.
   */
  async previewDependencies(artifact_type: string, slug: string): Promise<DependencyPreview[]> {
    const typeDir = artifactTypeToDirName(artifact_type)
    if (!typeDir) {
      throw new PromoteError(
        'promoteUnsupportedType',
        `Unsupported artifact type "${artifact_type}" — only cell-type/book/service/worker/job-type are promotable`,
      )
    }
    log.info('[ArtifactsManagerCell] previewDependencies() start', { artifactType: artifact_type, typeDir, slug })

    const bundleResp = await apiFetch('/api/v1/artifacts/bundle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_stage: 'sandbox',
        artifact_type: typeDir,
        slug,
        include_dependencies: true,
        dry_run: true,
      }),
    })
    const data = await this._parseArtifactsResponse<{ dependencies?: DependencyPreview[] }>(bundleResp, 'bundle')
    return data.dependencies || []
  }

  /**
   * Defensive allowance gate: allowance only exists after promotion.
   * Throws when the current stage !== 'runtime' (matches canAllow()).
   */
  private _assertAllowanceAllowed(): void {
    if (!this.canAllow(this._stage)) {
      throw new Error(
        `Allowance is only available after promotion (current stage: '${this._stage || 'unknown'}').`,
      )
    }
  }

  /**
   * Parse an artifacts API response, mapping non-OK statuses to a structured
   * {@link PromoteError} (403 → forbidden, 409 → conflict, 422 → invalid).
   */
  private async _parseArtifactsResponse<T>(response: Response, context: string): Promise<T> {
    if (response.ok) {
      return await response.json()
    }
    throw await this._mapArtifactsError(response, context)
  }

  private async _mapArtifactsError(response: Response, _context: string): Promise<PromoteError> {
    let detail = ''
    try {
      detail = await response.text()
    } catch {
      detail = ''
    }
    return classifyPromoteError(response.status, detail)
  }

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
    this._assertAllowanceAllowed()
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

    // DIAG: log the raw backend response (status + body) for the allowance POST.
    // The backend may return HTTP 200 with an error body ({"detail":"Planet not
    // found"}) which response.ok treats as success — F7 must observe this
    // false-success in the runtime logs.
    const rawText = await response.text()
    log.info('[ArtifactsManagerCell][DIAG] allowArtifact() raw backend response', {
      artifactId,
      userId: user.id,
      status: response.status,
      ok: response.ok,
      body: rawText.slice(0, 500),
    })

    // F3: the backend proxy may return HTTP 200 with an error body
    // ({"detail":"Planet not found"}) when it fails to resolve the planet.
    // response.ok alone would treat that as success — never do that.
    let backendDetail: string | null = null
    if (rawText && rawText.trim().startsWith('{')) {
      try {
        const parsedBody = JSON.parse(rawText)
        if (parsedBody && typeof parsedBody.detail === 'string' && parsedBody.detail) {
          backendDetail = parsedBody.detail
        }
      } catch {
        // not JSON — leave backendDetail as null
      }
    }

    if (!response.ok || backendDetail) {
      const detail = backendDetail || rawText
      log.error('[ArtifactsManagerCell] allowArtifact() backend error', {
        status: response.status,
        ok: response.ok,
        detail,
      })
      throw new Error(`Failed to grant permission (${response.status}): ${detail}`)
    }

    log.info('[ArtifactsManagerCell] allowArtifact() persisted successfully', {
      artifactId,
      userId: user.id,
      status: response.status,
      body: rawText.slice(0, 500),
    })
    return user
  }

  /**
   * List all users with allowance for a specific artifact.
   *
   * Calls GET /api/local/allowance?artifact_id=xxx through the backend proxy.
   *
   * @param artifactId - The ID of the artifact to list allowances for
   * @returns Array of AllowanceEntry objects
   */
  async listAllowances(artifactId: string): Promise<AllowanceEntry[]> {
    this._assertAllowanceAllowed()
    log.info('[ArtifactsManagerCell] listAllowances() called', { artifactId })

    const response = await apiFetch(
      `/api/local/allowance?artifact_id=${encodeURIComponent(artifactId)}`,
      { method: 'GET' },
    )

    if (!response.ok) {
      const detail = await response.text()
      log.error('[ArtifactsManagerCell] listAllowances() backend error', {
        status: response.status,
        detail,
      })
      throw new Error(`Failed to load allowances (${response.status}): ${detail}`)
    }

    const data = await response.json()
    const entries: AllowanceEntry[] = data.allowances || []
    log.info('[ArtifactsManagerCell] listAllowances() loaded', {
      artifactId,
      count: entries.length,
    })
    return entries
  }

  /**
   * Remove an artifact allowance for a specific user.
   *
   * Calls DELETE /api/local/allowance?artifact_id=xxx&user_id=xxx through the
   * backend proxy.
   *
   * @param artifactId - The ID of the artifact to revoke
   * @param userId - The ID of the user whose allowance to revoke
   * @returns true if the allowance was removed, false if it didn't exist
   */
  async removeAllowance(artifactId: string, userId: string): Promise<boolean> {
    this._assertAllowanceAllowed()
    log.info('[ArtifactsManagerCell] removeAllowance() called', {
      artifactId,
      userId,
    })

    const response = await apiFetch(
      `/api/local/allowance?artifact_id=${encodeURIComponent(artifactId)}&user_id=${encodeURIComponent(userId)}`,
      { method: 'DELETE' },
    )

    if (!response.ok) {
      const detail = await response.text()
      log.error('[ArtifactsManagerCell] removeAllowance() backend error', {
        status: response.status,
        detail,
      })
      throw new Error(`Failed to remove allowance (${response.status}): ${detail}`)
    }

    const data = await response.json()
    const removed = data.removed === true
    log.info('[ArtifactsManagerCell] removeAllowance() result', {
      artifactId,
      userId,
      removed,
    })
    return removed
  }
}

export default ArtifactsManagerCell
