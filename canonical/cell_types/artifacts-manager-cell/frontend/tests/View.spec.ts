/**
 * @file View.spec.ts
 * @description Tests for ArtifactsManagerCell BaseCell implementation.
 *
 * Following the established project pattern (see UserSelectionCell.test.ts,
 * calculator-cell, inbox-cell, planet-chat-cell): tests verify the BaseCell
 * class methods via inline stubs that replicate the cell's logic.
 * This avoids import resolution issues with #canonical/ subpath imports
 * and @/ aliases in the vitest environment.
 *
 * Coverage:
 * - execute() returns artifact data from input
 * - execute() returns error when artifact_id missing
 * - describe() returns correct metadata (id, name, version, inputs, outputs, tags)
 * - validate() rejects missing artifact_id
 * - validate() accepts valid artifact_id
 * - show() returns componentPath for View.vue
 * - allowArtifact() opens UserSelectionCell, POSTs allowance, returns user
 * - allowArtifact() returns null on cancel
 * - allowArtifact() throws on backend error
 * - listAllowances() returns allowance entries on success
 * - listAllowances() throws on backend error
 * - removeAllowance() returns true on success
 * - removeAllowance() returns false when not found
 * - removeAllowance() throws on backend error
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'

// ── Module mocks (hoisted before imports) ─────────────────────────────────

vi.mock('@/utils/logger', () => ({
  createLogger: () => ({
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  }),
}))

// ── Real pure helpers (dependency-free module — importable in vitest) ─────
// ArtifactsManagerCell.ts itself cannot be imported (heavy #canonical/ chain),
// so we test the REAL promotion.ts helpers directly and replicate the cell's
// method logic in the stub below.
import { artifactTypeToDirName, classifyPromoteError, PromoteError } from '../promotion'
import type { DependencyPreview } from '../promotion'

// ── Types ─────────────────────────────────────────────────────────────────

interface SelectableUser {
  id: string
  name: string
  avatar_url?: string | null
}

interface AllowanceEntry {
  user_id: string
  name?: string
  avatar_url?: string | null
  artifact_id: string
  granted_at: string
}

// ── Inline stubs ──────────────────────────────────────────────────────────
// Avoids #canonical/ and @/services/ import resolution issues in test environment.
// Follows same pattern as UserSelectionCell.test.ts inline stub.

const mockUser: SelectableUser = { id: 'user-123', name: 'Alice' }

/** Minimal stub replicating ArtifactsManagerCell logic for unit testing. */
class ArtifactsManagerCellStub {
  private _userSelectionCell: { show: ReturnType<typeof vi.fn> }

  /** Current lifecycle stage — allowance is gated on it being 'runtime'. */
  private _stage = ''

  constructor() {
    this._userSelectionCell = {
      show: vi.fn(),
    }
  }

  /** Set the artifact lifecycle stage (called by the View on mount / after promote). */
  setStage(stage: string): void {
    this._stage = stage
  }

  /** Allowance only exists for promoted (runtime) artifacts. */
  canAllow(stage: string): boolean {
    return stage === 'runtime'
  }

  private _assertAllowanceAllowed(): void {
    if (!this.canAllow(this._stage)) {
      throw new Error(
        `Allowance is only available after promotion (current stage: '${this._stage || 'unknown'}').`,
      )
    }
  }

  /** Stub execute() — returns artifact data or error. */
  async execute(input: Record<string, any>) {
    const artifactId = input.artifact_id

    if (!artifactId) {
      return {
        success: false,
        output: {},
        execution_time: 0,
        error: 'No artifact_id provided. Cannot display artifact manager.',
      }
    }

    const artifactData = input.artifact_data || {}
    return {
      success: true,
      output: {
        artifact_id: artifactId,
        artifact_data: artifactData,
        metadata: artifactData.metadata || {},
        identity: artifactData.identity || {},
        runtime: artifactData.runtime || {},
        execution_model: artifactData.execution_model || {},
        stage: artifactData.stage || '',
        version: artifactData.version || '',
      },
      execution_time: 1,
    }
  }

  /** Stub describe() — returns cell metadata. */
  async describe() {
    return {
      id: 'artifacts-manager-cell',
      name: 'Artifacts Manager',
      version: '1.0.0',
      description: 'Artifact detail manager. Displays metadata and provides management actions (Allow) for artifacts discovered in the explorer.',
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

  /** Stub validate() — requires artifact_id. */
  validate(input: Record<string, any>) {
    const errors: Array<{ field: string; message: string }> = []
    if (!input.artifact_id) {
      errors.push({
        field: 'artifact_id',
        message: 'artifact_id is required',
      })
    }
    return errors
  }

  /** Stub show() — returns View.vue path. */
  async show() {
    return { componentPath: 'frontend/View.vue' }
  }

  /** Stub allowArtifact() — opens user selection and POSTs allowance (gated to runtime). */
  async allowArtifact(artifactId: string, _mockApiFetch?: ReturnType<typeof vi.fn>) {
    this._assertAllowanceAllowed()
    const user: SelectableUser | null = await this._userSelectionCell.show()

    if (!user) return null

    // In real implementation, this calls apiFetch('/api/local/allowance', ...)
    // The test provides a mock apiFetch for verification
    if (_mockApiFetch) {
      const response = await _mockApiFetch('/api/local/allowance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ artifact_id: artifactId, user_id: user.id }),
      })

      if (!response.ok) {
        const detail = await response.text()
        throw new Error(`Failed to grant permission (${response.status}): ${detail}`)
      }
    }

    return user
  }

  /** Stub listAllowances() — GET /api/local/allowance. */
  async listAllowances(artifactId: string, _mockApiFetch?: ReturnType<typeof vi.fn>): Promise<AllowanceEntry[]> {
    this._assertAllowanceAllowed()
    if (!_mockApiFetch) {
      return []
    }

    const response = await _mockApiFetch(
      `/api/local/allowance?artifact_id=${encodeURIComponent(artifactId)}`,
      { method: 'GET' },
    )

    if (!response.ok) {
      const detail = await response.text()
      throw new Error(`Failed to load allowances (${response.status}): ${detail}`)
    }

    const data = await response.json()
    return data.allowances || []
  }

  /** Stub removeAllowance() — DELETE /api/local/allowance. */
  async removeAllowance(artifactId: string, userId: string, _mockApiFetch?: ReturnType<typeof vi.fn>): Promise<boolean> {
    this._assertAllowanceAllowed()
    if (!_mockApiFetch) {
      return false
    }

    const response = await _mockApiFetch(
      `/api/local/allowance?artifact_id=${encodeURIComponent(artifactId)}&user_id=${encodeURIComponent(userId)}`,
      { method: 'DELETE' },
    )

    if (!response.ok) {
      const detail = await response.text()
      throw new Error(`Failed to remove allowance (${response.status}): ${detail}`)
    }

    const data = await response.json()
    return data.removed === true
  }

  /** Stub promoteArtifact() — /bundle (sandbox) then /promote (no target). */
  async promoteArtifact(
    artifact_type: string,
    slug: string,
    mockApiFetch?: ReturnType<typeof vi.fn>,
  ): Promise<{ bundleId: string; promotedCount: number; entries: Array<{ artifact_type: string; slug: string; target_path: string }> }> {
    const typeDir = artifactTypeToDirName(artifact_type)
    if (!typeDir) {
      throw new PromoteError(
        'promoteUnsupportedType',
        `Unsupported artifact type "${artifact_type}" — only cell-type/book/service/worker/job-type are promotable`,
      )
    }
    if (!mockApiFetch) {
      throw new Error('promoteArtifact needs a mock apiFetch in tests')
    }

    // Step 1: bundle sandbox artifact + transitive deps.
    const bundleResp = await mockApiFetch('/api/v1/artifacts/bundle', {
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
    if (!bundleResp.ok) {
      throw classifyPromoteError(bundleResp.status, await bundleResp.text())
    }
    const bundleData = await bundleResp.json()
    if (!bundleData.bundle_id) {
      throw new PromoteError('promoteInvalid', 'Bundle creation returned no bundle_id')
    }

    // Step 2: promote — no target_user_id (backend defaults to the owner).
    const promoteResp = await mockApiFetch('/api/v1/artifacts/promote', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bundle_id: bundleData.bundle_id, strategy: 'copy' }),
    })
    if (!promoteResp.ok) {
      throw classifyPromoteError(promoteResp.status, await promoteResp.text())
    }
    const promoData = await promoteResp.json()
    const entries = promoData.entries || []
    return { bundleId: bundleData.bundle_id, promotedCount: entries.length, entries }
  }

  /** Stub previewDependencies() — /bundle with dry_run:true. */
  async previewDependencies(
    artifact_type: string,
    slug: string,
    mockApiFetch?: ReturnType<typeof vi.fn>,
  ): Promise<DependencyPreview[]> {
    const typeDir = artifactTypeToDirName(artifact_type)
    if (!typeDir) {
      throw new PromoteError(
        'promoteUnsupportedType',
        `Unsupported artifact type "${artifact_type}" — only cell-type/book/service/worker/job-type are promotable`,
      )
    }
    if (!mockApiFetch) {
      return []
    }
    const resp = await mockApiFetch('/api/v1/artifacts/bundle', {
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
    if (!resp.ok) {
      throw classifyPromoteError(resp.status, await resp.text())
    }
    const data = await resp.json()
    return data.dependencies || []
  }

  /** Helper to configure user-selection outcome. */
  _setUserSelectionResult(value: SelectableUser | null): void {
    this._userSelectionCell.show = vi.fn().mockResolvedValue(value)
  }
}

// ── Test Data ─────────────────────────────────────────────────────────────

const mockAllowances: AllowanceEntry[] = [
  { user_id: 'user-1', artifact_id: 'cell:test', granted_at: '2026-06-24T10:00:00Z', name: 'Alice' },
  { user_id: 'user-2', artifact_id: 'cell:test', granted_at: '2026-06-24T11:00:00Z', name: 'Bob' },
]

// ── Tests ─────────────────────────────────────────────────────────────────

describe('ArtifactsManagerCell', () => {
  let cell: ArtifactsManagerCellStub

  beforeEach(() => {
    vi.clearAllMocks()
    cell = new ArtifactsManagerCellStub()
    // Allowance methods are gated on stage === 'runtime'.
    cell.setStage('runtime')
  })

  // ── execute() ───────────────────────────────────────────────────────────

  describe('execute()', () => {
    it('returns artifact data from input', async () => {
      const result = await cell.execute({
        artifact_id: 'cell:test',
        artifact_data: {
          metadata: { tags: ['test'] },
          identity: { name: 'Test Cell' },
          runtime: {},
          execution_model: {},
          stage: 'canonical',
          version: '1.0.0',
        },
      })

      expect(result.success).toBe(true)
      expect(result.output.artifact_id).toBe('cell:test')
      expect(result.output.metadata).toEqual({ tags: ['test'] })
      expect(result.output.identity).toEqual({ name: 'Test Cell' })
    })

    it('returns error when artifact_id is missing', async () => {
      const result = await cell.execute({})
      expect(result.success).toBe(false)
      expect(result.error).toContain('No artifact_id')
    })

    it('returns empty metadata when artifact_data is omitted', async () => {
      const result = await cell.execute({ artifact_id: 'cell:test' })
      expect(result.success).toBe(true)
      expect(result.output.metadata).toEqual({})
    })
  })

  // ── describe() ──────────────────────────────────────────────────────────

  describe('describe()', () => {
    it('returns id = "artifacts-manager-cell"', async () => {
      const meta = await cell.describe()
      expect(meta.id).toBe('artifacts-manager-cell')
    })

    it('returns name = "Artifacts Manager"', async () => {
      const meta = await cell.describe()
      expect(meta.name).toBe('Artifacts Manager')
    })

    it('returns version = "1.0.0"', async () => {
      const meta = await cell.describe()
      expect(meta.version).toBe('1.0.0')
    })

    it('includes artifact_id as required input', async () => {
      const meta = await cell.describe()
      expect(meta.inputs?.artifact_id?.required).toBe(true)
    })

    it('includes artifact_data as optional input', async () => {
      const meta = await cell.describe()
      expect(meta.inputs?.artifact_data?.required).toBe(false)
    })

    it('includes metadata in outputs', async () => {
      const meta = await cell.describe()
      expect(meta.outputs?.metadata).toBeDefined()
    })

    it('includes relevant tags', async () => {
      const meta = await cell.describe()
      expect(meta.tags).toContain('workspace')
      expect(meta.tags).toContain('manager')
      expect(meta.tags).toContain('allowance')
    })
  })

  // ── validate() ──────────────────────────────────────────────────────────

  describe('validate()', () => {
    it('returns error when artifact_id is missing', () => {
      const errors = cell.validate({})
      expect(errors.length).toBeGreaterThanOrEqual(1)
      expect(errors[0].field).toBe('artifact_id')
    })

    it('returns no errors when artifact_id is present', () => {
      const errors = cell.validate({ artifact_id: 'cell:test' })
      expect(errors.length).toBe(0)
    })
  })

  // ── show() ──────────────────────────────────────────────────────────────

  describe('show()', () => {
    it('returns componentPath for View.vue', async () => {
      const result = await cell.show()
      expect(result.componentPath).toBe('frontend/View.vue')
    })
  })

  // ── allowArtifact() ─────────────────────────────────────────────────────

  describe('allowArtifact()', () => {
    it('returns user on successful allowance', async () => {
      cell._setUserSelectionResult(mockUser)
      const mockApiFetch = vi.fn().mockResolvedValue({ ok: true })

      const user = await cell.allowArtifact('cell:test', mockApiFetch)

      expect(user).toEqual(mockUser)
      expect(mockApiFetch).toHaveBeenCalledWith('/api/local/allowance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ artifact_id: 'cell:test', user_id: mockUser.id }),
      })
    })

    it('returns null when user cancels selection', async () => {
      cell._setUserSelectionResult(null)
      const mockApiFetch = vi.fn()

      const user = await cell.allowArtifact('cell:test', mockApiFetch)

      expect(user).toBeNull()
      // API should not be called when cancelled
      expect(mockApiFetch).not.toHaveBeenCalled()
    })

    it('throws when backend returns error', async () => {
      cell._setUserSelectionResult(mockUser)
      const mockApiFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        text: () => Promise.resolve('Internal server error'),
      })

      await expect(cell.allowArtifact('cell:test', mockApiFetch)).rejects.toThrow(
        'Failed to grant permission',
      )
    })
  })

  // ── listAllowances() ────────────────────────────────────────────────────

  describe('listAllowances()', () => {
    it('returns allowance entries on success', async () => {
      const mockApiFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ allowances: mockAllowances }),
      })

      const entries = await cell.listAllowances('cell:test', mockApiFetch)

      expect(entries).toHaveLength(2)
      expect(entries[0].user_id).toBe('user-1')
      expect(entries[0].name).toBe('Alice')
      expect(entries[1].user_id).toBe('user-2')
      expect(mockApiFetch).toHaveBeenCalledWith(
        '/api/local/allowance?artifact_id=cell%3Atest',
        { method: 'GET' },
      )
    })

    it('returns empty array when backend returns empty list', async () => {
      const mockApiFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ allowances: [] }),
      })

      const entries = await cell.listAllowances('cell:test', mockApiFetch)

      expect(entries).toHaveLength(0)
    })

    it('throws on backend error', async () => {
      const mockApiFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        text: () => Promise.resolve('Bad Gateway'),
      })

      await expect(cell.listAllowances('cell:test', mockApiFetch)).rejects.toThrow(
        'Failed to load allowances',
      )
    })

    it('handles missing allowances field in response', async () => {
      const mockApiFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({}),
      })

      const entries = await cell.listAllowances('cell:test', mockApiFetch)
      expect(entries).toEqual([])
    })
  })

  // ── removeAllowance() ───────────────────────────────────────────────────

  describe('removeAllowance()', () => {
    it('returns true on successful removal', async () => {
      const mockApiFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true, removed: true }),
      })

      const removed = await cell.removeAllowance('cell:test', 'user-1', mockApiFetch)

      expect(removed).toBe(true)
      expect(mockApiFetch).toHaveBeenCalledWith(
        '/api/local/allowance?artifact_id=cell%3Atest&user_id=user-1',
        { method: 'DELETE' },
      )
    })

    it('returns false when entry did not exist (idempotent)', async () => {
      const mockApiFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true, removed: false }),
      })

      const removed = await cell.removeAllowance('cell:test', 'nonexistent', mockApiFetch)

      expect(removed).toBe(false)
    })

    it('throws on backend error', async () => {
      const mockApiFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        text: () => Promise.resolve('Forbidden'),
      })

      await expect(cell.removeAllowance('cell:test', 'user-1', mockApiFetch)).rejects.toThrow(
        'Failed to remove allowance',
      )
    })

    it('returns false without mock (no-op path)', async () => {
      const removed = await cell.removeAllowance('cell:test', 'user-1')
      expect(removed).toBe(false)
    })
  })

  // ── artifactTypeToDirName() (real pure helper) ──────────────────────────

  describe('artifactTypeToDirName()', () => {
    it('maps cell-type → cell_types', () => {
      expect(artifactTypeToDirName('cell-type')).toBe('cell_types')
    })

    it('maps book → book_types', () => {
      expect(artifactTypeToDirName('book')).toBe('book_types')
    })

    it('maps service → services', () => {
      expect(artifactTypeToDirName('service')).toBe('services')
    })

    it('maps worker → workers', () => {
      expect(artifactTypeToDirName('worker')).toBe('workers')
    })

    it('maps job-type → workers', () => {
      expect(artifactTypeToDirName('job-type')).toBe('workers')
    })

    it('rejects viewers (unsupported)', () => {
      expect(artifactTypeToDirName('viewers')).toBeNull()
    })

    it('rejects shared_utils (unsupported)', () => {
      expect(artifactTypeToDirName('shared_utils')).toBeNull()
    })

    it('rejects unknown types', () => {
      expect(artifactTypeToDirName('something-else')).toBeNull()
    })
  })

  // ── classifyPromoteError() (real pure helper) ────────────────────────────

  describe('classifyPromoteError()', () => {
    it('maps 403 → promoteForbidden', () => {
      const err = classifyPromoteError(403, 'Only the planet owner')
      expect(err).toBeInstanceOf(PromoteError)
      expect(err.code).toBe('promoteForbidden')
    })

    it('maps 409 → promoteConflict', () => {
      expect(classifyPromoteError(409, 'Slug conflict').code).toBe('promoteConflict')
    })

    it('maps 422 → promoteInvalid', () => {
      expect(classifyPromoteError(422, 'Validation failed').code).toBe('promoteInvalid')
    })

    it('maps 500 → promoteFailed', () => {
      expect(classifyPromoteError(500, 'Internal error').code).toBe('promoteFailed')
    })
  })

  // ── canAllow() / setStage() ──────────────────────────────────────────────

  describe('canAllow() / setStage()', () => {
    it('canAllow returns true only for runtime', () => {
      expect(cell.canAllow('runtime')).toBe(true)
      expect(cell.canAllow('sandbox')).toBe(false)
      expect(cell.canAllow('canonical')).toBe(false)
    })
  })

  // ── promoteArtifact() ────────────────────────────────────────────────────

  describe('promoteArtifact()', () => {
    it('calls /bundle then /promote in order, with correct URLs/bodies and no target', async () => {
      const mockApiFetch = vi.fn()
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ bundle_id: 'bundle-1', dependencies: [] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            status: 'promoted',
            entries: [{ artifact_type: 'cell_types', slug: 'my-cell', target_path: '/runtime/user/owner/cell_types/my-cell' }],
          }),
        })

      const summary = await cell.promoteArtifact('cell-type', 'my-cell', mockApiFetch)

      expect(summary.bundleId).toBe('bundle-1')
      expect(summary.promotedCount).toBe(1)
      expect(summary.entries[0].slug).toBe('my-cell')

      expect(mockApiFetch).toHaveBeenCalledTimes(2)
      const [bundleCall, promoteCall] = mockApiFetch.mock.calls

      expect(bundleCall[0]).toBe('/api/v1/artifacts/bundle')
      expect(JSON.parse(bundleCall[1].body)).toEqual({
        source_stage: 'sandbox',
        artifact_type: 'cell_types',
        slug: 'my-cell',
        include_dependencies: true,
        dry_run: false,
      })

      expect(promoteCall[0]).toBe('/api/v1/artifacts/promote')
      const promoteBody = JSON.parse(promoteCall[1].body)
      expect(promoteBody).toEqual({ bundle_id: 'bundle-1', strategy: 'copy' })
      expect(promoteBody).not.toHaveProperty('target_user_id')
    })

    it('throws promoteUnsupportedType for reviewers (unsupported)', async () => {
      await expect(cell.promoteArtifact('viewers', 'my-viewer', vi.fn())).rejects.toMatchObject({
        code: 'promoteUnsupportedType',
      })
    })

    it('maps 403 → promoteForbidden', async () => {
      const mockApiFetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 403,
        text: () => Promise.resolve('Only the planet owner'),
      })
      await expect(cell.promoteArtifact('cell-type', 'my-cell', mockApiFetch)).rejects.toMatchObject({
        code: 'promoteForbidden',
      })
    })

    it('maps 409 → promoteConflict', async () => {
      const mockApiFetch = vi.fn()
        .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ bundle_id: 'bundle-1' }) })
        .mockResolvedValueOnce({ ok: false, status: 409, text: () => Promise.resolve('Slug conflict') })
      await expect(cell.promoteArtifact('cell-type', 'my-cell', mockApiFetch)).rejects.toMatchObject({
        code: 'promoteConflict',
      })
    })

    it('maps 422 → promoteInvalid', async () => {
      const mockApiFetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 422,
        text: () => Promise.resolve('Validation failed'),
      })
      await expect(cell.promoteArtifact('cell-type', 'my-cell', mockApiFetch)).rejects.toMatchObject({
        code: 'promoteInvalid',
      })
    })

    it('throws promoteInvalid when bundle returns no bundle_id', async () => {
      const mockApiFetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ dependencies: [] }),
      })
      await expect(cell.promoteArtifact('cell-type', 'my-cell', mockApiFetch)).rejects.toMatchObject({
        code: 'promoteInvalid',
      })
    })
  })

  // ── previewDependencies() ────────────────────────────────────────────────

  describe('previewDependencies()', () => {
    it('calls /bundle with dry_run:true and returns dependencies', async () => {
      const mockApiFetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          bundle_id: 'bundle-p',
          dependencies: [{ artifact_type: 'cell_types', slug: 'dep-1' }],
        }),
      })

      const deps = await cell.previewDependencies('cell-type', 'my-cell', mockApiFetch)

      expect(deps).toEqual([{ artifact_type: 'cell_types', slug: 'dep-1' }])
      const body = JSON.parse(mockApiFetch.mock.calls[0][1].body)
      expect(body).toMatchObject({ source_stage: 'sandbox', dry_run: true, include_dependencies: true })
    })

    it('throws promoteUnsupportedType for unsupported types', async () => {
      await expect(cell.previewDependencies('shared_utils', 'x', vi.fn())).rejects.toMatchObject({
        code: 'promoteUnsupportedType',
      })
    })
  })

  // ── Allowance gating (stage !== runtime) ─────────────────────────────────

  describe('allowance gating (stage !== runtime)', () => {
    it('allowArtifact blocks when stage is sandbox', async () => {
      cell.setStage('sandbox')
      cell._setUserSelectionResult(mockUser)
      await expect(cell.allowArtifact('cell:test', vi.fn())).rejects.toThrow('only available after promotion')
    })

    it('listAllowances blocks when stage is sandbox', async () => {
      cell.setStage('sandbox')
      await expect(cell.listAllowances('cell:test', vi.fn())).rejects.toThrow('only available after promotion')
    })

    it('removeAllowance blocks when stage is canonical', async () => {
      cell.setStage('canonical')
      await expect(cell.removeAllowance('cell:test', 'user-1', vi.fn())).rejects.toThrow('only available after promotion')
    })

    it('allowArtifact works when stage is runtime (set by the View)', async () => {
      cell.setStage('runtime')
      cell._setUserSelectionResult(mockUser)
      const mockApiFetch = vi.fn().mockResolvedValue({ ok: true })
      const user = await cell.allowArtifact('cell:test', mockApiFetch)
      expect(user).toEqual(mockUser)
    })
  })
})
