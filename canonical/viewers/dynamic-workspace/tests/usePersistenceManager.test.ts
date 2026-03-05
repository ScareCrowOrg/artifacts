/**
 * tests/usePersistenceManager.test.ts
 *
 * Unit tests for usePersistenceManager composable.
 * Uses vi.stubGlobal to mock fetch so no real network calls are made.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWorkspaceStore } from '@/stores/workspaceStore'

// ── Fetch mock helpers ────────────────────────────────────────────────────────

function mockFetchOk(body: any, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: true,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response)
}

function mockFetchError(status: number, detail = 'Error') {
  return vi.fn().mockResolvedValue({
    ok: false,
    status,
    json: () => Promise.resolve({ detail }),
    text: () => Promise.resolve(detail),
  } as unknown as Response)
}

function mockFetchNoContent() {
  return vi.fn().mockResolvedValue({
    ok: true,
    status: 204,
    json: () => Promise.resolve(null),
    text: () => Promise.resolve(''),
  } as unknown as Response)
}

// ── Sample data ───────────────────────────────────────────────────────────────

const sampleBook = {
  id: 'book-123',
  assignee_id: 'user-1',
  notebook_item_type_id: 'layout-book',
  name: 'Test Layout',
  description: 'A test layout',
  type: 'VOLATILE',
  initial_data: {
    layout_version: '1.0.0',
    cells: [
      {
        category: 'ephemeral',
        type: 'calculator-cell',
        title: 'Calculator',
        position: { x: 0, y: 0, w: 6, h: 8 },
        state: { isMinimized: false, isMaximized: false },
      },
    ],
    grid_config: { cols: 12, rowHeight: 50, margin: [8, 8] },
    metadata: { layout_version: '1.0.0' },
  },
  created_at: '2026-03-05T00:00:00Z',
  updated_at: '2026-03-05T00:00:00Z',
}

const sampleListResponse = {
  items: [
    {
      id: 'book-123',
      name: 'Test Layout',
      description: 'A test layout',
      cell_count: 1,
      created_at: '2026-03-05T00:00:00Z',
      updated_at: '2026-03-05T00:00:00Z',
    },
  ],
  total: 1,
  skip: 0,
  limit: 20,
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('usePersistenceManager', () => {
  let store: ReturnType<typeof useWorkspaceStore>
  let originalFetch: typeof global.fetch

  beforeEach(async () => {
    setActivePinia(createPinia())
    store = useWorkspaceStore()
    store.initWorkspace({ workspaceId: 'ws-1', sessionToken: 'jwt-token', userId: 'user-1' })
    store.setReady()
    originalFetch = global.fetch
  })

  afterEach(() => {
    global.fetch = originalFetch
    vi.restoreAllMocks()
  })

  describe('saveLayout', () => {
    it('should POST to /api/layout-books and return the created book', async () => {
      global.fetch = mockFetchOk(sampleBook)

      const { usePersistenceManager } = await import('../composables/usePersistenceManager')
      const { saveLayout } = usePersistenceManager()

      const result = await saveLayout('Test Layout', 'A test layout')

      expect(result.id).toBe('book-123')
      expect(result.name).toBe('Test Layout')

      const [url, options] = (global.fetch as any).mock.calls[0]
      expect(url).toContain('/api/layout-books')
      expect(options.method).toBe('POST')
      expect(options.headers?.Authorization).toBe('Bearer jwt-token')
    })

    it('should throw when session token is missing', async () => {
      store.initWorkspace({ workspaceId: 'ws-1', sessionToken: '', userId: 'user-1' })
      const { usePersistenceManager } = await import('../composables/usePersistenceManager')
      const { saveLayout } = usePersistenceManager()

      await expect(saveLayout('Test', '')).rejects.toThrow('No session token')
    })

    it('should throw a descriptive error on HTTP failure', async () => {
      global.fetch = mockFetchError(403, 'Forbidden')
      const { usePersistenceManager } = await import('../composables/usePersistenceManager')
      const { saveLayout } = usePersistenceManager()

      await expect(saveLayout('Test', '')).rejects.toThrow('HTTP 403')
    })
  })

  describe('fetchLayout', () => {
    it('should GET /api/layout-books/{id} and return the book', async () => {
      global.fetch = mockFetchOk(sampleBook)
      const { usePersistenceManager } = await import('../composables/usePersistenceManager')
      const { fetchLayout } = usePersistenceManager()

      const result = await fetchLayout('book-123')

      expect(result.id).toBe('book-123')
      const [url] = (global.fetch as any).mock.calls[0]
      expect(url).toContain('/api/layout-books/book-123')
    })

    it('should throw on 404', async () => {
      global.fetch = mockFetchError(404, 'Not found')
      const { usePersistenceManager } = await import('../composables/usePersistenceManager')
      const { fetchLayout } = usePersistenceManager()

      await expect(fetchLayout('missing')).rejects.toThrow('HTTP 404')
    })
  })

  describe('listLayouts', () => {
    it('should GET /api/layout-books and map items to LayoutBook[]', async () => {
      global.fetch = mockFetchOk(sampleListResponse)
      const { usePersistenceManager } = await import('../composables/usePersistenceManager')
      const { listLayouts } = usePersistenceManager()

      const result = await listLayouts()

      expect(result).toHaveLength(1)
      expect(result[0].id).toBe('book-123')
      expect(result[0].name).toBe('Test Layout')

      const [url] = (global.fetch as any).mock.calls[0]
      expect(url).toContain('/api/layout-books?skip=0&limit=20')
    })

    it('should pass custom skip/limit params', async () => {
      global.fetch = mockFetchOk({ items: [], total: 0, skip: 10, limit: 5 })
      const { usePersistenceManager } = await import('../composables/usePersistenceManager')
      const { listLayouts } = usePersistenceManager()

      await listLayouts(10, 5)

      const [url] = (global.fetch as any).mock.calls[0]
      expect(url).toContain('skip=10&limit=5')
    })
  })

  describe('updateLayout', () => {
    it('should PUT to /api/layout-books/{id}', async () => {
      global.fetch = mockFetchOk({ ...sampleBook, name: 'Updated' })
      const { usePersistenceManager } = await import('../composables/usePersistenceManager')
      const { updateLayout } = usePersistenceManager()

      const result = await updateLayout('book-123', { name: 'Updated' })

      expect(result.name).toBe('Updated')
      const [url, options] = (global.fetch as any).mock.calls[0]
      expect(url).toContain('/api/layout-books/book-123')
      expect(options.method).toBe('PUT')
    })
  })

  describe('deleteLayout', () => {
    it('should DELETE /api/layout-books/{id} without throwing', async () => {
      global.fetch = mockFetchNoContent()
      const { usePersistenceManager } = await import('../composables/usePersistenceManager')
      const { deleteLayout } = usePersistenceManager()

      await expect(deleteLayout('book-123')).resolves.not.toThrow()

      const [url, options] = (global.fetch as any).mock.calls[0]
      expect(url).toContain('/api/layout-books/book-123')
      expect(options.method).toBe('DELETE')
    })
  })

  describe('autoSaveWorkspaceState', () => {
    it('should create a new auto-save book when no existing ID is provided', async () => {
      global.fetch = mockFetchOk(sampleBook)
      const { usePersistenceManager } = await import('../composables/usePersistenceManager')
      const { autoSaveWorkspaceState } = usePersistenceManager()

      const id = await autoSaveWorkspaceState(null)

      expect(id).toBe('book-123')
      const [, options] = (global.fetch as any).mock.calls[0]
      expect(options.method).toBe('POST')
    })

    it('should update an existing auto-save book when ID is provided', async () => {
      global.fetch = mockFetchOk({ ...sampleBook, id: 'auto-save-id' })
      const { usePersistenceManager } = await import('../composables/usePersistenceManager')
      const { autoSaveWorkspaceState } = usePersistenceManager()

      const id = await autoSaveWorkspaceState('auto-save-id')

      expect(id).toBe('auto-save-id')
      const [url, options] = (global.fetch as any).mock.calls[0]
      expect(url).toContain('/api/layout-books/auto-save-id')
      expect(options.method).toBe('PUT')
    })

    it('should create a new book if the update of existing ID fails', async () => {
      let callCount = 0
      global.fetch = vi.fn().mockImplementation(() => {
        callCount++
        if (callCount === 1) {
          // First call (PUT): fail
          return Promise.resolve({
            ok: false,
            status: 404,
            json: () => Promise.resolve({ detail: 'Not found' }),
            text: () => Promise.resolve('Not found'),
          })
        }
        // Second call (POST): succeed
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ ...sampleBook, id: 'new-auto-save' }),
          text: () => Promise.resolve(''),
        })
      })

      const { usePersistenceManager } = await import('../composables/usePersistenceManager')
      const { autoSaveWorkspaceState } = usePersistenceManager()

      const id = await autoSaveWorkspaceState('stale-id')
      expect(id).toBe('new-auto-save')
    })
  })
})
