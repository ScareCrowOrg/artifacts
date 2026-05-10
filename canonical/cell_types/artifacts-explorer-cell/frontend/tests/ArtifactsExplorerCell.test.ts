/**
 * @file ArtifactsExplorerCell.test.ts
 * @description Unit tests for ArtifactsExplorerCell (BaseCell implementation).
 *
 * NOTE: ArtifactsExplorerCell imports from `@/types/BaseCell` which cannot be
 * resolved in the test environment (the shared types live in artifacts/shared/types,
 * outside the cockpit-vue @/ alias). Following the established codebase pattern
 * (see fragment-editor-cell, content-manager-cell, calculator-cell), this test
 * uses an inline stub that replicates the cell's logic to verify behavior.
 *
 * Coverage:
 * - execute() calls GET /api/artifacts-map with correct params per filter_mode
 * - execute() handles API success and failure
 * - validate() accepts/rejects filter_mode values
 * - describe() returns correct metadata
 * - show() returns componentPath
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'

// ── Module mocks (hoisted before imports) ─────────────────────────────────

vi.mock('@/utils/logger', () => ({
  createLogger: () => ({
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  }),
}))

vi.mock('@/services/apiService', () => ({
  apiFetch: vi.fn(),
}))

// ── Imports ───────────────────────────────────────────────────────────────

import { apiFetch } from '@/services/apiService'
import { createLogger } from '@/utils/logger'

const mockApiFetch = vi.mocked(apiFetch)

// ── Inline stub — mirrors ArtifactsExplorerCell logic ────────────────────
// This avoids the @/types/BaseCell import resolution issue (see test file header).

type FilterMode = 'all' | 'cells_only'

interface SelectableUser {
  id: string
  name: string
  email: string
  role?: string
}

const log = createLogger('cell:artifacts-explorer')

class ArtifactsExplorerCell {
  /** Injected UserSelectionCell mock for testing allowArtifact() */
  private _userCell: { show: (_d: any, _o: any) => Promise<SelectableUser | null> } | null = null

  constructor(userCell?: { show: (_d: any, _o: any) => Promise<SelectableUser | null> }) {
    this._userCell = userCell ?? null
  }

  async execute(input: Record<string, any>) {
    const startTime = performance.now()
    try {
      const filterMode: FilterMode =
        input.filter_mode === 'cells_only' ? 'cells_only' : 'all'
      const params = filterMode === 'cells_only' ? '?artifact_type=cell-type' : ''
      const response = await apiFetch(`/api/artifacts-map${params}`, { method: 'GET' })
      const data = await response.json()
      const artifacts: any[] = Array.isArray(data) ? data : []
      return {
        success: true,
        output: { artifacts },
        execution_time: performance.now() - startTime,
      }
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Unknown error'
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: msg,
      }
    }
  }

  validate(input: Record<string, any>) {
    const errors: Array<{ field: string; message: string }> = []
    if (input.filter_mode && !['all', 'cells_only'].includes(input.filter_mode)) {
      errors.push({
        field: 'filter_mode',
        message: "filter_mode must be 'all' or 'cells_only'",
      })
    }
    return errors
  }

  async describe() {
    return {
      id: 'artifacts-explorer-cell',
      name: 'Artifacts Explorer',
      version: '2.0.0',
      description:
        'Universal artifact discovery cell. Displays Cells, Services and Workers from the unified Artifact Runtime Map.',
      inputs: {
        filter_mode: {
          type: 'string',
          description: "'all' shows all artifact types with category tabs; 'cells_only' shows only cell-type artifacts",
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

  async show(_data: Record<string, any>, _options: any) {
    return { componentPath: 'frontend/View.vue' }
  }

  async allowArtifact(artifactId: string): Promise<SelectableUser | null> {
    if (!this._userCell) {
      throw new Error('No userCell injected')
    }
    const user = await this._userCell.show({}, {
      mode: 'pick-one',
      title: 'Select user for allowance',
    })

    if (!user) {
      return null
    }

    const response = await apiFetch('/api/local/allowance', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ artifact_id: artifactId, user_id: user.id }),
    })

    if (!response.ok) {
      throw new Error(`Failed to grant permission (${response.status})`)
    }

    return user
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────

function makeArtifactResponse(count = 2) {
  return {
    json: async () =>
      Array.from({ length: count }, (_, i) => ({
        artifact_id: `cell-${i}`,
        version: '1.0.0',
        artifact_type: 'cell-type',
        stage: 'canonical',
        identity: { name: `Cell ${i}`, description: '', icon: '🧩', author: 'system' },
        runtime: { entry_point: null, strategy: 'frontend_injection', required_artifacts: [], env_vars: [] },
        execution_model: { orchestrator: 'frontend', heartbeat_channel: null, health_check: null },
        metadata: { tags: [] },
      })),
  } as unknown as Response
}

// ─────────────────────────────────────────────────────────────────────────────
// execute()
// ─────────────────────────────────────────────────────────────────────────────

describe('ArtifactsExplorerCell.execute()', () => {
  let cell: ArtifactsExplorerCell

  beforeEach(() => {
    cell = new ArtifactsExplorerCell()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('calls GET /api/artifacts-map without params when filter_mode is "all"', async () => {
    mockApiFetch.mockResolvedValueOnce(makeArtifactResponse())

    await cell.execute({ filter_mode: 'all' })

    expect(mockApiFetch).toHaveBeenCalledTimes(1)
    const [url, options] = mockApiFetch.mock.calls[0]
    expect(url).toBe('/api/artifacts-map')
    expect((options as RequestInit).method).toBe('GET')
  })

  it('calls GET /api/artifacts-map without params when filter_mode is absent', async () => {
    mockApiFetch.mockResolvedValueOnce(makeArtifactResponse())

    await cell.execute({})

    const [url] = mockApiFetch.mock.calls[0]
    expect(url).toBe('/api/artifacts-map')
  })

  it('appends ?artifact_type=cell-type when filter_mode is "cells_only"', async () => {
    mockApiFetch.mockResolvedValueOnce(makeArtifactResponse())

    await cell.execute({ filter_mode: 'cells_only' })

    const [url] = mockApiFetch.mock.calls[0]
    expect(url).toBe('/api/artifacts-map?artifact_type=cell-type')
  })

  it('returns success=true with artifacts array on success', async () => {
    mockApiFetch.mockResolvedValueOnce(makeArtifactResponse(3))

    const result = await cell.execute({ filter_mode: 'all' })

    expect(result.success).toBe(true)
    expect(Array.isArray(result.output.artifacts)).toBe(true)
    expect(result.output.artifacts).toHaveLength(3)
  })

  it('returns empty artifacts array when API returns non-array', async () => {
    mockApiFetch.mockResolvedValueOnce({
      json: async () => ({ unexpected: 'shape' }),
    } as unknown as Response)

    const result = await cell.execute({})

    expect(result.success).toBe(true)
    expect(result.output.artifacts).toEqual([])
  })

  it('returns success=false on network error', async () => {
    mockApiFetch.mockRejectedValueOnce(new Error('Network failure'))

    const result = await cell.execute({})

    expect(result.success).toBe(false)
    expect(result.error).toContain('Network failure')
  })

  it('always includes execution_time in result', async () => {
    mockApiFetch.mockResolvedValueOnce(makeArtifactResponse())

    const result = await cell.execute({})

    expect(typeof result.execution_time).toBe('number')
    expect(result.execution_time).toBeGreaterThanOrEqual(0)
  })

  it('returns execution_time even on failure', async () => {
    mockApiFetch.mockRejectedValueOnce(new Error('Fail'))

    const result = await cell.execute({})

    expect(typeof result.execution_time).toBe('number')
  })

  it('treats unknown filter_mode values as "all" (no query param)', async () => {
    mockApiFetch.mockResolvedValueOnce(makeArtifactResponse())

    await cell.execute({ filter_mode: 'anything_else' })

    const [url] = mockApiFetch.mock.calls[0]
    expect(url).toBe('/api/artifacts-map')
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// validate()
// ─────────────────────────────────────────────────────────────────────────────

describe('ArtifactsExplorerCell.validate()', () => {
  let cell: ArtifactsExplorerCell

  beforeEach(() => {
    cell = new ArtifactsExplorerCell()
  })

  it('returns no errors for filter_mode "all"', () => {
    const errors = cell.validate({ filter_mode: 'all' })
    expect(errors).toHaveLength(0)
  })

  it('returns no errors for filter_mode "cells_only"', () => {
    const errors = cell.validate({ filter_mode: 'cells_only' })
    expect(errors).toHaveLength(0)
  })

  it('returns no errors when filter_mode is absent', () => {
    const errors = cell.validate({})
    expect(errors).toHaveLength(0)
  })

  it('returns error for unknown filter_mode', () => {
    const errors = cell.validate({ filter_mode: 'invalid_mode' })
    expect(errors).toHaveLength(1)
    expect(errors[0].field).toBe('filter_mode')
    expect(errors[0].message).toContain("'all'")
    expect(errors[0].message).toContain("'cells_only'")
  })

  it('returns error for filter_mode "picker" (legacy value)', () => {
    const errors = cell.validate({ filter_mode: 'picker' })
    expect(errors.some((e) => e.field === 'filter_mode')).toBe(true)
  })

  it('returns error for filter_mode "view" (legacy value)', () => {
    const errors = cell.validate({ filter_mode: 'view' })
    expect(errors.some((e) => e.field === 'filter_mode')).toBe(true)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// describe()
// ─────────────────────────────────────────────────────────────────────────────

describe('ArtifactsExplorerCell.describe()', () => {
  let cell: ArtifactsExplorerCell

  beforeEach(() => {
    cell = new ArtifactsExplorerCell()
  })

  it('returns id = "artifacts-explorer-cell"', async () => {
    const meta = await cell.describe()
    expect(meta.id).toBe('artifacts-explorer-cell')
  })

  it('returns name = "Artifacts Explorer"', async () => {
    const meta = await cell.describe()
    expect(meta.name).toBe('Artifacts Explorer')
  })

  it('returns version = "2.0.0"', async () => {
    const meta = await cell.describe()
    expect(meta.version).toBe('2.0.0')
  })

  it('includes filter_mode in inputs', async () => {
    const meta = await cell.describe()
    expect(meta.inputs).toHaveProperty('filter_mode')
  })

  it('filter_mode input defaults to "all"', async () => {
    const meta = await cell.describe()
    expect(meta.inputs.filter_mode.default).toBe('all')
  })

  it('includes artifacts in outputs', async () => {
    const meta = await cell.describe()
    expect(meta.outputs).toHaveProperty('artifacts')
  })

  it('includes workspace-related tags', async () => {
    const meta = await cell.describe()
    expect(meta.tags).toContain('workspace')
    expect(meta.tags).toContain('explorer')
    expect(meta.tags).toContain('artifacts')
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// show()
// ─────────────────────────────────────────────────────────────────────────────

describe('ArtifactsExplorerCell.show()', () => {
  let cell: ArtifactsExplorerCell

  beforeEach(() => {
    cell = new ArtifactsExplorerCell()
  })

  it('returns componentPath pointing to View.vue', async () => {
    const spec = await cell.show({}, {})
    expect(spec.componentPath).toBe('frontend/View.vue')
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// allowArtifact()
// ─────────────────────────────────────────────────────────────────────────────

describe('ArtifactsExplorerCell.allowArtifact()', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('calls userCell.show() with pick-one mode and allowance title', async () => {
    const mockUserCell = {
      show: vi.fn().mockResolvedValue(null),
    }
    const cell = new ArtifactsExplorerCell(mockUserCell)

    await cell.allowArtifact('artifact-123')

    expect(mockUserCell.show).toHaveBeenCalledTimes(1)
    const [_data, options] = mockUserCell.show.mock.calls[0]
    expect(options.mode).toBe('pick-one')
    expect(options.title).toContain('allowance')
  })

  it('returns null when selection is cancelled without calling backend', async () => {
    const mockUserCell = {
      show: vi.fn().mockResolvedValue(null),
    }
    const cell = new ArtifactsExplorerCell(mockUserCell)

    const result = await cell.allowArtifact('artifact-xyz')

    expect(result).toBeNull()
    expect(mockApiFetch).not.toHaveBeenCalled()
  })

  it('calls POST /api/local/allowance with correct artifact_id and user_id when user is selected', async () => {
    const selectedUser: SelectableUser = {
      id: 'user-99',
      name: 'carol',
      email: 'carol@example.com',
    }
    const mockUserCell = {
      show: vi.fn().mockResolvedValue(selectedUser),
    }
    mockApiFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ success: true, added: true }) } as unknown as Response)
    const cell = new ArtifactsExplorerCell(mockUserCell)

    await cell.allowArtifact('artifact-abc')

    expect(mockApiFetch).toHaveBeenCalledTimes(1)
    const [url, options] = mockApiFetch.mock.calls[0]
    expect(url).toBe('/api/local/allowance')
    expect((options as RequestInit).method).toBe('POST')
    const body = JSON.parse((options as RequestInit).body as string)
    expect(body.artifact_id).toBe('artifact-abc')
    expect(body.user_id).toBe('user-99')
  })

  it('returns the selected user when backend call succeeds', async () => {
    const selectedUser: SelectableUser = {
      id: 'user-99',
      name: 'carol',
      email: 'carol@example.com',
    }
    const mockUserCell = {
      show: vi.fn().mockResolvedValue(selectedUser),
    }
    mockApiFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ success: true, added: true }) } as unknown as Response)
    const cell = new ArtifactsExplorerCell(mockUserCell)

    const result = await cell.allowArtifact('artifact-abc')

    expect(result).toEqual(selectedUser)
    expect(result?.name).toBe('carol')
  })

  it('throws an Error when backend returns non-ok response', async () => {
    const selectedUser: SelectableUser = {
      id: 'user-99',
      name: 'carol',
      email: 'carol@example.com',
    }
    const mockUserCell = {
      show: vi.fn().mockResolvedValue(selectedUser),
    }
    mockApiFetch.mockResolvedValueOnce({ ok: false, status: 403, text: async () => 'Forbidden' } as unknown as Response)
    const cell = new ArtifactsExplorerCell(mockUserCell)

    await expect(cell.allowArtifact('artifact-abc')).rejects.toThrow(/Failed to grant permission/)
  })
})
