/**
 * @file View.spec.ts
 * @description Unit tests for artifacts-explorer-cell View.vue component.
 *
 * Coverage:
 * - Category filter tabs visibility (all vs cells_only mode)
 * - Tab switching changes activeCategory filter
 * - Search functionality
 * - Icon fallback priority (identity.icon → type fallback → 📦)
 * - Sandbox stage badge rendering
 * - Strategy Interface (frontend vs launcher rendering)
 * - loadArtifacts() called on mount when store is empty
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia, defineStore } from 'pinia'
import { ref } from 'vue'

// ── Module mocks ──────────────────────────────────────────────────────────

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

import View from '../View.vue'
import { useArtifactsExplorerStore } from '../store'
import type { ExplorerArtifact } from '../store'

// ── Fixtures ──────────────────────────────────────────────────────────────

function makeArtifact(overrides: Partial<ExplorerArtifact> = {}): ExplorerArtifact {
  return {
    artifact_id: 'test-cell',
    version: '1.0.0',
    artifact_type: 'cell-type',
    stage: 'canonical',
    identity: {
      name: 'Test Cell',
      description: 'A test cell description',
      icon: '🧩',
      author: 'system',
    },
    runtime: {
      entry_point: 'frontend/TestCell.ts',
      strategy: 'frontend_injection',
      dependencies: { services: [], cell_types: [], book_types: [], workers: [], shared_utils: [], viewers: [] },
      env_vars: [],
    },
    execution_model: {
      orchestrator: 'frontend',
      heartbeat_channel: null,
      health_check: null,
    },
    metadata: { tags: [] },
    ...overrides,
  }
}

function makeServiceArtifact(overrides: Partial<ExplorerArtifact> = {}): ExplorerArtifact {
  return makeArtifact({
    artifact_id: 'ollama-service',
    artifact_type: 'service',
    identity: {
      name: 'Ollama Service',
      description: 'LLM inference service',
      icon: '🤖',
      author: 'system',
    },
    execution_model: {
      orchestrator: 'launcher',
      heartbeat_channel: 'redis_l1',
      health_check: null,
    },
    ...overrides,
  })
}

// ── Helpers ───────────────────────────────────────────────────────────────

function mountView(options: {
  artifacts?: ExplorerArtifact[]
  isLoading?: boolean
  error?: string | null
  filterMode?: 'all' | 'cells_only'
} = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)

  const store = useArtifactsExplorerStore()
  store.availableArtifacts = options.artifacts ?? []
  store.isLoading = options.isLoading ?? false
  store.error = options.error ?? null

  const cellType = {
    default_initial_data: { filter_mode: options.filterMode ?? 'all' },
  }

  return mount(View, {
    global: { plugins: [pinia] },
    props: { cell: { cellType } },
  })
}

// ─────────────────────────────────────────────────────────────────────────────
// Category Filter Tabs
// ─────────────────────────────────────────────────────────────────────────────

describe('View.vue — Category filter tabs', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders category tabs when filter_mode is "all"', () => {
    const wrapper = mountView({ filterMode: 'all' })
    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs.length).toBeGreaterThan(0)
  })

  it('hides category tabs when filter_mode is "cells_only"', () => {
    const wrapper = mountView({ filterMode: 'cells_only' })
    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs.length).toBe(0)
  })

  it('shows All, Cells, Infrastructure and Intelligence tabs', () => {
    const wrapper = mountView({ filterMode: 'all' })
    const text = wrapper.text()
    expect(text).toContain('All')
    expect(text).toContain('Cells')
    expect(text).toContain('Infrastructure')
    expect(text).toContain('Intelligence')
  })

  it('highlights the active tab (All by default)', () => {
    const wrapper = mountView({ filterMode: 'all' })
    const allTab = wrapper.findAll('[role="tab"]').find((t) => t.text().includes('All'))
    expect(allTab?.classes()).toContain('bg-blue-600')
  })

  it('changes active tab on click', async () => {
    const wrapper = mountView({
      filterMode: 'all',
      artifacts: [makeArtifact()],
    })
    const cellsTab = wrapper.findAll('[role="tab"]').find((t) => t.text().includes('Cells'))
    await cellsTab?.trigger('click')

    expect(cellsTab?.classes()).toContain('bg-blue-600')
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Artifact Cards & Search
// ─────────────────────────────────────────────────────────────────────────────

describe('View.vue — Artifact cards', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders artifact name from identity.name', () => {
    const artifact = makeArtifact({ identity: { name: 'My Unique Cell', description: '', icon: null, author: 'system' } })
    const wrapper = mountView({ artifacts: [artifact] })
    expect(wrapper.text()).toContain('My Unique Cell')
  })

  it('renders artifact description from identity.description', () => {
    const artifact = makeArtifact({ identity: { name: 'Cell', description: 'Unique description text', icon: null, author: 'system' } })
    const wrapper = mountView({ artifacts: [artifact] })
    expect(wrapper.text()).toContain('Unique description text')
  })

  it('renders artifact version', () => {
    const artifact = makeArtifact({ version: '3.7.2' })
    const wrapper = mountView({ artifacts: [artifact] })
    expect(wrapper.text()).toContain('3.7.2')
  })

  it('shows "no artifacts found" when list is empty', () => {
    const wrapper = mountView({ artifacts: [] })
    expect(wrapper.text()).toContain('No artifacts found')
  })

  it('filters by search query', async () => {
    const artifacts = [
      makeArtifact({ artifact_id: 'alpha', identity: { name: 'Alpha Cell', description: '', icon: null, author: 'system' } }),
      makeArtifact({ artifact_id: 'beta', identity: { name: 'Beta Cell', description: '', icon: null, author: 'system' } }),
    ]
    const wrapper = mountView({ artifacts })

    const input = wrapper.find('input[type="text"]')
    await input.setValue('Alpha')
    await flushPromises()

    expect(wrapper.text()).toContain('Alpha Cell')
    expect(wrapper.text()).not.toContain('Beta Cell')
  })

  it('shows empty state when search has no matches', async () => {
    const artifacts = [makeArtifact()]
    const wrapper = mountView({ artifacts })

    const input = wrapper.find('input[type="text"]')
    await input.setValue('xyzzy-no-match')

    expect(wrapper.text()).toContain('No artifacts found')
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Icon Fallback Priority
// ─────────────────────────────────────────────────────────────────────────────

describe('View.vue — Icon fallback', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('uses identity.icon when available', () => {
    const artifact = makeArtifact({ identity: { name: 'Cell', description: '', icon: '🎯', author: 'system' } })
    const wrapper = mountView({ artifacts: [artifact] })
    expect(wrapper.text()).toContain('🎯')
  })

  it('falls back to 🧩 for cell-type artifacts with no icon', () => {
    const artifact = makeArtifact({
      artifact_type: 'cell-type',
      identity: { name: 'Cell', description: '', icon: null, author: 'system' },
    })
    const wrapper = mountView({ artifacts: [artifact] })
    expect(wrapper.text()).toContain('🧩')
  })

  it('falls back to 🏗️ for service artifacts with no icon', () => {
    const artifact = makeServiceArtifact({
      identity: { name: 'Svc', description: '', icon: null, author: 'system' },
    })
    const wrapper = mountView({ artifacts: [artifact] })
    expect(wrapper.text()).toContain('🏗️')
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Sandbox Badge
// ─────────────────────────────────────────────────────────────────────────────

describe('View.vue — Sandbox badge', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows sandbox badge when stage is "sandbox"', () => {
    const artifact = makeArtifact({ stage: 'sandbox' })
    const wrapper = mountView({ artifacts: [artifact] })
    expect(wrapper.text()).toContain('sandbox')
  })

  it('does NOT show sandbox badge when stage is "canonical"', () => {
    const artifact = makeArtifact({ stage: 'canonical' })
    const wrapper = mountView({ artifacts: [artifact] })
    // Should not have 🧪 sandbox badge in the card area
    const badges = wrapper.findAll('.bg-yellow-100')
    expect(badges.length).toBe(0)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Strategy Interface
// ─────────────────────────────────────────────────────────────────────────────

describe('View.vue — Strategy Interface', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders "Add to Workspace" button for frontend-orchestrated artifacts', () => {
    const artifact = makeArtifact({ execution_model: { orchestrator: 'frontend', heartbeat_channel: null, health_check: null } })
    const wrapper = mountView({ artifacts: [artifact] })
    expect(wrapper.text()).toContain('Add to Workspace')
  })

  it('renders "Managed by Launcher" indicator for launcher-orchestrated artifacts', () => {
    const artifact = makeServiceArtifact()
    const wrapper = mountView({ artifacts: [artifact] })
    expect(wrapper.text()).toContain('Managed by Launcher')
  })

  it('does NOT render "Add to Workspace" for launcher-orchestrated artifacts', () => {
    const artifact = makeServiceArtifact()
    const wrapper = mountView({ artifacts: [artifact] })
    expect(wrapper.text()).not.toContain('Add to Workspace')
  })

  it('shows heartbeat_channel when launcher-orchestrated and channel is present', () => {
    const artifact = makeServiceArtifact({
      execution_model: { orchestrator: 'launcher', heartbeat_channel: 'redis_l1', health_check: null },
    })
    const wrapper = mountView({ artifacts: [artifact] })
    expect(wrapper.text()).toContain('redis_l1')
  })

  it('does not show heartbeat channel when null', () => {
    const artifact = makeServiceArtifact({
      execution_model: { orchestrator: 'launcher', heartbeat_channel: null, health_check: null },
    })
    const wrapper = mountView({ artifacts: [artifact] })
    // heartbeat_channel span should not be present
    const channelSpans = wrapper.findAll('.font-mono')
    expect(channelSpans.length).toBe(0)
  })

  it('calls selectArtifact when "Add to Workspace" is clicked', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useArtifactsExplorerStore()
    store.availableArtifacts = [makeArtifact()]
    const spy = vi.spyOn(store, 'selectArtifact')

    const wrapper = mount(View, {
      global: { plugins: [pinia] },
      props: { cell: { cellType: { default_initial_data: { filter_mode: 'all' } } } },
    })

    const addBtn = wrapper.find('button[aria-label^="Add"]')
    await addBtn.trigger('click')

    expect(spy).toHaveBeenCalledTimes(1)
    expect(spy.mock.calls[0][0].artifact_id).toBe('test-cell')
  })

  it('does NOT call selectArtifact when launcher artifact card is interacted with', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useArtifactsExplorerStore()
    store.availableArtifacts = [makeServiceArtifact()]
    const spy = vi.spyOn(store, 'selectArtifact')

    mount(View, {
      global: { plugins: [pinia] },
      props: { cell: { cellType: { default_initial_data: { filter_mode: 'all' } } } },
    })

    // selectArtifact is never called unless Add button is clicked (which doesn't exist for launcher)
    expect(spy).not.toHaveBeenCalled()
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Loading / Error States
// ─────────────────────────────────────────────────────────────────────────────

describe('View.vue — Loading and error states', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows loading spinner when isLoading is true', () => {
    const wrapper = mountView({ isLoading: true })
    expect(wrapper.find('.spinner').exists()).toBe(true)
  })

  it('shows error message when error is set', () => {
    const wrapper = mountView({ error: 'Test error message' })
    expect(wrapper.text()).toContain('Test error message')
  })

  it('shows retry button when error is set', () => {
    const wrapper = mountView({ error: 'Some error', filterMode: 'cells_only' })
    const retryBtn = wrapper.find('button')
    expect(retryBtn.text()).toContain('Retry')
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// Lifecycle: loadArtifacts on mount
// ─────────────────────────────────────────────────────────────────────────────

describe('View.vue — onMounted', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('calls loadArtifacts on mount when store is empty', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useArtifactsExplorerStore()
    const spy = vi.spyOn(store, 'loadArtifacts').mockResolvedValueOnce()

    mount(View, {
      global: { plugins: [pinia] },
      props: { cell: { cellType: { default_initial_data: { filter_mode: 'all' } } } },
    })

    await flushPromises()

    expect(spy).toHaveBeenCalledTimes(1)
    expect(spy.mock.calls[0][0]).toBe('all')
  })

  it('calls loadArtifacts with "cells_only" when filter_mode is cells_only', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useArtifactsExplorerStore()
    const spy = vi.spyOn(store, 'loadArtifacts').mockResolvedValueOnce()

    mount(View, {
      global: { plugins: [pinia] },
      props: { cell: { cellType: { default_initial_data: { filter_mode: 'cells_only' } } } },
    })

    await flushPromises()

    expect(spy).toHaveBeenCalledWith('cells_only')
  })

  it('does NOT call loadArtifacts when store already has artifacts', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useArtifactsExplorerStore()
    store.availableArtifacts = [makeArtifact()]
    const spy = vi.spyOn(store, 'loadArtifacts').mockResolvedValueOnce()

    mount(View, {
      global: { plugins: [pinia] },
      props: { cell: { cellType: { default_initial_data: { filter_mode: 'all' } } } },
    })

    await flushPromises()

    expect(spy).not.toHaveBeenCalled()
  })
})
