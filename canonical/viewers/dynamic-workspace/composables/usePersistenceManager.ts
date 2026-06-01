/**
 * composables/usePersistenceManager.ts
 *
 * Layout persistence for DynamicWorkspace v2 — Phase 3.
 * Calls the /api/layout-books backend endpoints via the shared apiFetch utility,
 * which uses VITE_API_BASE_URL from environment and injects
 * the session token from workspaceStore automatically.
 */

import { useGridLayout } from './useGridLayout'
import { apiFetch } from '@/services/apiService'
import { createLogger } from '@/utils/logger'
import type {
  Book,
  CellReference,
  GridConfig,
  GridCell,
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
   * Extract the current state from a cell instance for persistence.
   * Inspects the cellInstance for observable state fields (status, jobId,
   * content_id, error, progress, etc.) and returns them as a plain object.
   *
   * Falls back to an empty object if the instance is null or has no state.
   */
  function extractCellState(cellInstance: any): Record<string, any> {
    if (!cellInstance) return {}

    const state: Record<string, any> = {}

    // Common state fields found across cell types
    const stateFields = [
      'status',
      'jobId',
      'content_id',
      'input_content_id',
      'error',
      'progress',
      'isGenerating',
      'generatedMesh',
      'inputImage',
      'outputData',
    ]

    for (const field of stateFields) {
      if (field in cellInstance) {
        // Skip binary/base64 data (stored separately, not in MongoDB)
        if (typeof cellInstance[field] === 'string') {
          const val = cellInstance[field] as string
          if (val.startsWith('data:') || val.startsWith('blob:')) {
            continue
          }
        }
        state[field] = cellInstance[field]
      }
    }

    return state
  }

  /**
   * Serialize current grid cells into the CellReference format required by
   * the layout books API.
   *
   * For persisted cells (isPersisted === true):
   * - category = "persistent"
   * - cellId = runtimeId (MongoDB _id)
   * - initialization_data = current cell state (for full restore on reload)
   *
   * For ephemeral cells:
   * - category = "ephemeral" (unchanged)
   * - No initialization_data (state is not saved)
   */
  function serializeCells(): CellReference[] {
    return cells.value.map((cell: GridCell): CellReference => {
      const isPersisted = cell.isPersisted === true

      const ref: CellReference = {
        category: isPersisted ? 'persistent' : 'ephemeral',
        type: cell.cellTypeName,
        title: cell.cellType?.name ?? cell.cellTypeName,
        position: cell.position,
        state: {
          isMinimized: cell.isMinimized ?? false,
          isMaximized: cell.isMaximized ?? false,
        },
      }

      if (isPersisted) {
        ref.cellId = cell.runtimeId
        ref.initialization_data = extractCellState(cell.cellInstance)
      }

      return ref
    })
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
   * Find an existing auto-save layout book by name.
   * Returns the book id, or null if none exists.
   */
  async function findAutoSaveBook(): Promise<string | null> {
    try {
      const layouts = await listLayouts(0, 100)
      const existing = layouts.find(b => b.name === '__auto-save__')
      return existing?.id ?? null
    } catch {
      return null
    }
  }

  /**
   * Save the current grid state to an existing auto-save layout book (update),
   * or create a new one if no auto-save book exists yet.
   *
   * Strategy (idempotent):
   * 1. If autoSaveBookId is known, try to update it directly.
   * 2. If update fails or no ID known, search for existing __auto-save__ book by name.
   * 3. If found, update that book and return its ID.
   * 4. If nothing found, create a new __auto-save__ book.
   *
   * This ensures the auto-save always targets the SAME book across page reloads,
   * and recovers gracefully if the book was deleted externally.
   *
   * @param autoSaveBookId  Hint: previously known auto-save book ID (may be stale).
   * @returns               The id of the auto-save book (for subsequent saves).
   */
  async function autoSaveWorkspaceState(autoSaveBookId: string | null): Promise<string> {
    const serializedCells = serializeCells()

    // ── Case 1: Known book ID → try direct update ──────────────────────────
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
        log.warn('[PersistenceManager] Auto-save update failed, will look for existing book', {
          autoSaveBookId,
          error: err.message,
        })
      }
    }

    // ── Case 2: Look for an existing __auto-save__ book by name ────────────
    try {
      const existingId = await findAutoSaveBook()
      if (existingId) {
        await updateLayout(existingId, {
          cells: serializedCells,
          grid_config: DEFAULT_GRID_CONFIG,
        })
        log.info('[PersistenceManager] Auto-save updated (via name lookup)', {
          autoSaveBookId: existingId,
          cellCount: serializedCells.length,
        })
        return existingId
      }
    } catch (err: any) {
      log.warn('[PersistenceManager] Auto-save name lookup/update failed', {
        error: err.message,
      })
    }

    // ── Case 3: No existing auto-save book → create one ────────────────────
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
