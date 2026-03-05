/**
 * composables/usePersistenceManager.ts
 *
 * Layout persistence for DynamicWorkspace v2 — Phase 3.
 * Calls the /api/layout-books backend endpoints via the shared apiFetch utility,
 * which routes requests through the Nginx proxy (VITE_BACKEND_URL) and injects
 * the session token from workspaceStore automatically.
 */

import { useGridLayout } from './useGridLayout'
import { apiFetch } from '@/services/apiService'
import { createLogger } from '@/utils/logger'
import type {
  Book,
  CellReference,
  GridConfig,
  LayoutBook,
  LayoutBookListItem,
  LayoutBookListResponse,
} from '../types'

const log = createLogger('persistence:layout-books')

// ── Constants ─────────────────────────────────────────────────────────────────

const DEFAULT_GRID_CONFIG: GridConfig = {
  cols: 12,
  rowHeight: 50,
  margin: [8, 8],
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Parse a JSON response, throwing a descriptive error on non-2xx status.
 * Returns `undefined` for 204 No Content responses.
 */
async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = 'Unknown error'
    try {
      const body = await response.json()
      detail = body?.detail ?? JSON.stringify(body)
    } catch {
      detail = await response.text().catch(() => 'Unknown error')
    }
    throw new Error(`HTTP ${response.status}: ${detail}`)
  }
  if (response.status === 204) {
    return undefined as unknown as T
  }
  return response.json()
}

/**
 * Convert a Book's CellReference array to a LayoutBook-compatible cells list
 * for the LayoutBookSelector component.
 */
function bookToLayoutBook(book: Book): LayoutBook {
  return {
    id: book.id,
    name: book.name,
    description: book.description || undefined,
    cells: (book.initial_data?.cells ?? []).map(ref => ({
      cellTypeName: ref.type,
      position: ref.position,
    })),
    createdAt: book.created_at,
    updatedAt: book.updated_at,
  }
}

// ── Composable ────────────────────────────────────────────────────────────────

export function usePersistenceManager() {
  const { cells } = useGridLayout()

  /**
   * Serialize current grid cells into the CellReference format required by
   * the layout books API.
   */
  function serializeCells(): CellReference[] {
    return cells.value.map(cell => ({
      category: 'ephemeral' as const,
      type: cell.cellTypeName,
      title: cell.cellType?.name ?? cell.cellTypeName,
      position: cell.position,
      state: {
        isMinimized: cell.isMinimized ?? false,
        isMaximized: cell.isMaximized ?? false,
      },
    }))
  }

  // ── CRUD ──────────────────────────────────────────────────────────────────

  /**
   * Save the current grid state as a named layout book.
   * POST /api/layout-books
   */
  async function saveLayout(name: string, description = ''): Promise<Book> {
    log.info('[PersistenceManager] Saving layout', { name, cellCount: cells.value.length })

    const response = await apiFetch('/layout-books', {
      method: 'POST',
      body: JSON.stringify({
        name,
        description,
        cells: serializeCells(),
        grid_config: DEFAULT_GRID_CONFIG,
      }),
    })
    const book = await parseJsonResponse<Book>(response)

    log.info('[PersistenceManager] Layout saved', { layoutId: book.id, name })
    return book
  }

  /**
   * Load a specific saved layout by ID.
   * GET /api/layout-books/{layoutId}
   * Returns the raw Book object; the caller is responsible for hydrating the grid.
   */
  async function fetchLayout(layoutId: string): Promise<Book> {
    log.debug('[PersistenceManager] Fetching layout', { layoutId })

    const response = await apiFetch(`/layout-books/${layoutId}`)
    const book = await parseJsonResponse<Book>(response)

    log.info('[PersistenceManager] Layout fetched', {
      layoutId,
      cellCount: book.initial_data?.cells?.length ?? 0,
    })
    return book
  }

  /**
   * List all saved layouts for the current user.
   * GET /api/layout-books?skip=0&limit=20
   */
  async function listLayouts(skip = 0, limit = 20): Promise<LayoutBook[]> {
    log.debug('[PersistenceManager] Listing layouts', { skip, limit })

    const response = await apiFetch(`/layout-books?skip=${skip}&limit=${limit}`)
    const data = await parseJsonResponse<LayoutBookListResponse>(response)

    // The list endpoint returns LayoutBookListItem[] (fewer fields than a full Book).
    // We convert them into LayoutBook for the LayoutBookSelector component.
    const items: LayoutBook[] = (data.items ?? []).map((item: LayoutBookListItem) => ({
      id: item.id,
      name: item.name,
      description: item.description || undefined,
      cells: [],
      createdAt: item.created_at,
      updatedAt: item.updated_at,
    }))

    log.info('[PersistenceManager] Layouts listed', { count: items.length })
    return items
  }

  /**
   * Update an existing layout (name, description, or cells).
   * PUT /api/layout-books/{layoutId}
   */
  async function updateLayout(
    layoutId: string,
    updates: { name?: string; description?: string; cells?: CellReference[]; grid_config?: GridConfig },
  ): Promise<Book> {
    log.info('[PersistenceManager] Updating layout', { layoutId, updateKeys: Object.keys(updates) })

    const response = await apiFetch(`/layout-books/${layoutId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    })
    const book = await parseJsonResponse<Book>(response)

    log.info('[PersistenceManager] Layout updated', { layoutId })
    return book
  }

  /**
   * Delete a saved layout.
   * DELETE /api/layout-books/{layoutId}
   */
  async function deleteLayout(layoutId: string): Promise<void> {
    log.info('[PersistenceManager] Deleting layout', { layoutId })

    const response = await apiFetch(`/layout-books/${layoutId}`, { method: 'DELETE' })
    await parseJsonResponse<void>(response)
    log.info('[PersistenceManager] Layout deleted', { layoutId })
  }

  /**
   * Save the current grid state to an existing auto-save layout book (update),
   * or create a new one if no auto-save book exists yet.
   *
   * @param autoSaveBookId  If provided, PUT to update; otherwise POST to create.
   * @returns               The id of the auto-save book (for subsequent saves).
   */
  async function autoSaveWorkspaceState(autoSaveBookId: string | null): Promise<string> {
    const serializedCells = serializeCells()

    if (autoSaveBookId) {
      try {
        await updateLayout(autoSaveBookId, {
          cells: serializedCells,
          grid_config: DEFAULT_GRID_CONFIG,
        })
        log.info('[PersistenceManager] Auto-save updated', {
          autoSaveBookId,
          cellCount: serializedCells.length,
        })
        return autoSaveBookId
      } catch (err: any) {
        // If the update fails (e.g. book was deleted), fall through to create a new one
        log.warn('[PersistenceManager] Auto-save update failed, creating new', {
          autoSaveBookId,
          error: err.message,
        })
      }
    }

    const book = await saveLayout('__auto-save__', 'Automatic workspace state backup')
    log.info('[PersistenceManager] Auto-save created', {
      layoutId: book.id,
      cellCount: serializedCells.length,
    })
    return book.id
  }

  return {
    saveLayout,
    fetchLayout,
    listLayouts,
    updateLayout,
    deleteLayout,
    autoSaveWorkspaceState,
    serializeCells,
    bookToLayoutBook,
  }
}
