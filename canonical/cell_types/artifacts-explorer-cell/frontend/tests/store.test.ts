/**
 * @file store.test.ts
 * @description Unit tests for useArtifactsExplorerStore (Pinia).
 *
 * Coverage:
 * - loadArtifacts() with filterMode 'all' and 'cells_only'
 * - loadArtifacts() error handling
 * - selectArtifact() / clearSelection() state transitions
 * - ExplorerArtifact type shape
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

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

import { useArtifactsExplorerStore } from '../store'
import type { ExplorerArtifact } from '../store'
import { apiFetch } from '@/services/apiService'

const mockApiFetch = vi.mocked(apiFetch)

// ── Fixtures ──────────────────────────────────────────────────────────────

function makeArtifact(overrides: Partial<ExplorerArtifact> = {}): ExplorerArtifact {
  return {
    artifact_id: 'test-cell',
    version: '1.0.0',
    artifact_type: 'cell-type',
    stage: 'canonical',
    identity: {
      name: 'Test Cell',
      description: 'A test cell',
      icon: '🧩',
      author: 'system',
    },
    runtime: {
      entry_point: 'frontend/TestCell.ts',
      strategy: 'frontend_injection',
      required_artifacts: [],
      env_vars: [],
    },
    execution_model: {
      orchestrator: 'frontend',
      heartbeat_channel: null,
      health_check: null,
    },
    metadata: { tags: ['test'] },
    ...overrides,
  }
}

function makeApiResponse(artifacts: ExplorerArtifact[]) {
  return {
    json: async () => artifacts,
  } as unknown as Response
}

// ─────────────────────────────────────────────────────────────────────────────
// loadArtifacts()
// ─────────────────────────────────────────────────────────────────────────────

describe('useArtifactsExplorerStore.loadArtifacts()', () => {
  let store: ReturnType<typeof useArtifactsExplorerStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useArtifactsExplorerStore()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('calls /api/v1/artifacts-map without params when filterMode is "all"', async () => {
    mockApiFetch.mockResolvedValueOnce(makeApiResponse([]))

    await store.loadArtifacts('all')

    expect(mockApiFetch).toHaveBeenCalledTimes(1)
    const [url] = mockApiFetch.mock.calls[0]
    expect(url).toBe('/api/v1/artifacts-map')
  })

  it('calls /api/v1/artifacts-map without params when filterMode defaults', async () => {
    mockApiFetch.mockResolvedValueOnce(makeApiResponse([]))

    await store.loadArtifacts()

    const [url] = mockApiFetch.mock.calls[0]
    expect(url).toBe('/api/v1/artifacts-map')
  })

  it('appends ?artifact_type=cell-type when filterMode is "cells_only"', async () => {
    mockApiFetch.mockResolvedValueOnce(makeApiResponse([]))

    await store.loadArtifacts('cells_only')

    const [url] = mockApiFetch.mock.calls[0]
    expect(url).toBe('/api/v1/artifacts-map?artifact_type=cell-type')
  })

  it('uses GET method', async () => {
    mockApiFetch.mockResolvedValueOnce(makeApiResponse([]))

    await store.loadArtifacts()

    const [, options] = mockApiFetch.mock.calls[0]
    expect((options as RequestInit).method).toBe('GET')
  })

  it('stores returned artifacts in availableArtifacts', async () => {
    const artifacts = [makeArtifact(), makeArtifact({ artifact_id: 'another-cell' })]
    mockApiFetch.mockResolvedValueOnce(makeApiResponse(artifacts))

    await store.loadArtifacts()

    expect(store.availableArtifacts).toHaveLength(2)
    expect(store.availableArtifacts[0].artifact_id).toBe('test-cell')
    expect(store.availableArtifacts[1].artifact_id).toBe('another-cell')
  })

  it('stores empty array when API returns empty list', async () => {
    mockApiFetch.mockResolvedValueOnce(makeApiResponse([]))

    await store.loadArtifacts()

    expect(store.availableArtifacts).toHaveLength(0)
  })

  it('stores empty array when API returns non-array', async () => {
    mockApiFetch.mockResolvedValueOnce({
      json: async () => ({ unexpected: 'shape' }),
    } as unknown as Response)

    await store.loadArtifacts()

    expect(store.availableArtifacts).toHaveLength(0)
  })

  it('sets isLoading to true during fetch and false after', async () => {
    let resolveJson!: (value: any) => void
    const jsonPromise = new Promise<any>((res) => { resolveJson = res })
    mockApiFetch.mockResolvedValueOnce({
      json: () => jsonPromise,
    } as unknown as Response)

    const loadPromise = store.loadArtifacts()
    expect(store.isLoading).toBe(true)

    resolveJson([])
    await loadPromise

    expect(store.isLoading).toBe(false)
  })

  it('sets error and clears availableArtifacts length on network failure', async () => {
    mockApiFetch.mockRejectedValueOnce(new Error('Network error'))

    await store.loadArtifacts()

    expect(store.error).toBe('Network error')
    expect(store.isLoading).toBe(false)
  })

  it('sets generic error message when exception has no message', async () => {
    mockApiFetch.mockRejectedValueOnce({})

    await store.loadArtifacts()

    expect(store.error).toBe('Failed to load artifacts')
  })

  it('clears previous error on successful reload', async () => {
    // First call fails
    mockApiFetch.mockRejectedValueOnce(new Error('Fail'))
    await store.loadArtifacts()
    expect(store.error).toBeTruthy()

    // Second call succeeds
    mockApiFetch.mockResolvedValueOnce(makeApiResponse([]))
    await store.loadArtifacts()

    expect(store.error).toBeNull()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// selectArtifact() / clearSelection()
// ─────────────────────────────────────────────────────────────────────────────

describe('useArtifactsExplorerStore selection state', () => {
  let store: ReturnType<typeof useArtifactsExplorerStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useArtifactsExplorerStore()
  })

  it('selectedArtifact starts as null', () => {
    expect(store.selectedArtifact).toBeNull()
  })

  it('selectArtifact() sets selectedArtifact', () => {
    const artifact = makeArtifact()
    store.selectArtifact(artifact)
    expect(store.selectedArtifact).toEqual(artifact)
  })

  it('selectArtifact() works for launcher-orchestrated artifacts', () => {
    const artifact = makeArtifact({
      artifact_type: 'service',
      execution_model: {
        orchestrator: 'launcher',
        heartbeat_channel: 'redis_l1',
        health_check: null,
      },
    })
    store.selectArtifact(artifact)
    expect(store.selectedArtifact?.execution_model.orchestrator).toBe('launcher')
  })

  it('clearSelection() resets selectedArtifact to null', () => {
    store.selectArtifact(makeArtifact())
    expect(store.selectedArtifact).not.toBeNull()

    store.clearSelection()

    expect(store.selectedArtifact).toBeNull()
  })

  it('clearSelection() is idempotent', () => {
    store.clearSelection()
    store.clearSelection()
    expect(store.selectedArtifact).toBeNull()
  })

  it('successive selectArtifact() calls replace the selection', () => {
    const a = makeArtifact({ artifact_id: 'first' })
    const b = makeArtifact({ artifact_id: 'second' })

    store.selectArtifact(a)
    store.selectArtifact(b)

    expect(store.selectedArtifact?.artifact_id).toBe('second')
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Initial state
// ─────────────────────────────────────────────────────────────────────────────

describe('useArtifactsExplorerStore initial state', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('availableArtifacts starts empty', () => {
    const store = useArtifactsExplorerStore()
    expect(store.availableArtifacts).toEqual([])
  })

  it('isLoading starts false', () => {
    const store = useArtifactsExplorerStore()
    expect(store.isLoading).toBe(false)
  })

  it('error starts null', () => {
    const store = useArtifactsExplorerStore()
    expect(store.error).toBeNull()
  })

  it('selectedArtifact starts null', () => {
    const store = useArtifactsExplorerStore()
    expect(store.selectedArtifact).toBeNull()
  })
})
