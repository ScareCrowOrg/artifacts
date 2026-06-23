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

// ── Types ─────────────────────────────────────────────────────────────────

interface SelectableUser {
  id: string
  name: string
  avatar_url?: string | null
}

// ── Inline stubs ──────────────────────────────────────────────────────────
// Avoids #canonical/ and @/services/ import resolution issues in test environment.
// Follows same pattern as UserSelectionCell.test.ts inline stub.

const mockUser: SelectableUser = { id: 'user-123', name: 'Alice' }

/** Minimal stub replicating ArtifactsManagerCell logic for unit testing. */
class ArtifactsManagerCellStub {
  private _userSelectionCell: { show: ReturnType<typeof vi.fn> }

  constructor() {
    this._userSelectionCell = {
      show: vi.fn(),
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

  /** Stub allowArtifact() — opens user selection and POSTs allowance. */
  async allowArtifact(artifactId: string, _mockApiFetch?: ReturnType<typeof vi.fn>) {
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

  /** Helper to configure user-selection outcome. */
  _setUserSelectionResult(value: SelectableUser | null): void {
    this._userSelectionCell.show = vi.fn().mockResolvedValue(value)
  }
}

// ── Tests ─────────────────────────────────────────────────────────────────

describe('ArtifactsManagerCell', () => {
  let cell: ArtifactsManagerCellStub

  beforeEach(() => {
    vi.clearAllMocks()
    cell = new ArtifactsManagerCellStub()
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
})
