/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-22",
 *   "console_calls_found": 26,
 *   "console_calls_migrated": 26,
 *   "migration_rate": 100,
 *   "logger_namespace": "service:layout-books",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Layout Books Service
 * 
 * API service for managing layout books - saved workspace configurations.
 * Communicates with backend /api/layout-books endpoints.
 * 
 * Part of Layout Books implementation (Issue #1539, Phase 2)
 */

import { apiFetch } from '@/services/apiService.js'
import { createLogger } from '@/utils/logger'
import { API_BASE_URL } from '@/config/endpoints.js'

const log = createLogger('service:layout-books')

const API_BASE = `${API_BASE_URL}/api/layout-books`

/**
 * @typedef {Object} CellPosition
 * @property {number} x - X coordinate on grid
 * @property {number} y - Y coordinate on grid
 * @property {number} w - Width in grid columns
 * @property {number} h - Height in grid rows
 */

/**
 * @typedef {Object} CellState
 * @property {boolean} isMinimized - Whether cell is minimized
 * @property {boolean} isMaximized - Whether cell is maximized
 */

/**
 * @typedef {Object} CellReference
 * @property {string} [cellId] - UUID of persistent cell (omit for ephemeral)
 * @property {string} category - 'persistent' or 'ephemeral'
 * @property {string} type - Cell type identifier
 * @property {string} title - Cell display title
 * @property {CellPosition} position - Grid position
 * @property {CellState} state - Cell display state
 * @property {Object} [initialization_data] - Init data for ephemeral cells
 */

/**
 * @typedef {Object} GridConfig
 * @property {number} cols - Number of columns
 * @property {number} rowHeight - Height of each row in pixels
 * @property {number[]} margin - Margin [horizontal, vertical]
 */

/**
 * @typedef {Object} LayoutBook
 * @property {string} id - Layout book UUID
 * @property {string} assignee_id - Owner user UUID (snake_case from API)
 * @property {string} name - Layout book name
 * @property {string} description - Layout book description
 * @property {Object} initial_data - Layout data structure (snake_case from API)
 * @property {Object} initial_data.grid_config - Grid configuration
 * @property {Array} initial_data.cells - Cell definitions  
 * @property {string} created_at - ISO timestamp (snake_case from API)
 * @property {string} updated_at - ISO timestamp (snake_case from API)
 * 
 * Note: API returns snake_case field names (initial_data, assignee_id, created_at, updated_at)
 * because response_model_by_alias=False is set in the backend router.
 */

/**
 * Fetch all layout books for current user
 * 
 * @param {Object} options - Query options
 * @param {number} [options.skip=0] - Number of items to skip
 * @param {number} [options.limit=20] - Max items to return
 * @param {string} [options.name] - Filter by name (partial match)
 * @returns {Promise<{items: Array, total: number, skip: number, limit: number}>}
 */
export async function fetchLayoutBooks({ skip = 0, limit = 20, name = null } = {}) {
  try {
    const params = new URLSearchParams({
      skip: skip.toString(),
      limit: limit.toString()
    })
    
    if (name) {
      params.append('name', name)
    }

    const url = `${API_BASE}?${params.toString()}`
    log.debug('Fetching layout books', { skip, limit, name })
    log.debug('API_BASE', API_BASE)
    log.debug('Full URL', url)
    
    const response = await apiFetch(url, {
      method: 'GET'
    })

    if (!response.ok) {
      log.error('Response not OK', {
        status: response.status,
        statusText: response.statusText,
        url: url
      })
      throw new Error(`Failed to fetch layout books: ${response.statusText}`)
    }

    const data = await response.json()
    log.info('Fetched layout books', { 
      count: data.items.length, 
      total: data.total 
    })
    
    return data
  } catch (error) {
    log.error('Error fetching layout books', error)
    log.error('Error stack', error.stack)
    throw error
  }
}

/**
 * Get a specific layout book by ID
 * 
 * @param {string} id - Layout book UUID
 * @returns {Promise<LayoutBook>}
 */
export async function getLayoutBook(id) {
  try {
    log.debug('Fetching layout book', { id })
    
    const response = await apiFetch(`${API_BASE}/${id}`, {
      method: 'GET'
    })

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Layout book not found')
      }
      throw new Error(`Failed to fetch layout book: ${response.statusText}`)
    }

    const data = await response.json()
    log.info('Fetched layout book', { id, name: data.name })
    
    return data
  } catch (error) {
    log.error('Error fetching layout book', error)
    throw error
  }
}

/**
 * Create a new layout book
 * 
 * @param {Object} layoutBookData - Layout book creation data
 * @param {string} layoutBookData.name - Layout book name (1-100 chars)
 * @param {string} [layoutBookData.description] - Description (max 500 chars)
 * @param {CellReference[]} layoutBookData.cells - Cell references
 * @param {GridConfig} layoutBookData.grid_config - Grid configuration
 * @returns {Promise<LayoutBook>}
 */
export async function createLayoutBook(layoutBookData) {
  try {
    log.info('Creating layout book', { 
      name: layoutBookData.name,
      cellCount: layoutBookData.cells.length
    })
    log.debug('API_BASE', API_BASE)
    log.debug('POST URL', API_BASE)
    
    const response = await apiFetch(API_BASE, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(layoutBookData)
    })

    if (!response.ok) {
      log.error('Response not OK', {
        status: response.status,
        statusText: response.statusText,
        url: API_BASE
      })
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `Failed to create layout book: ${response.statusText}`)
    }

    const data = await response.json()
    log.info('Created layout book', { id: data.id, name: data.name })
    
    return data
  } catch (error) {
    log.error('Error creating layout book', error)
    log.error('Error stack', error.stack)
    throw error
  }
}

/**
 * Update an existing layout book
 * 
 * @param {string} id - Layout book UUID
 * @param {Object} updates - Fields to update
 * @param {string} [updates.name] - New name (1-100 chars)
 * @param {string} [updates.description] - New description (max 500 chars)
 * @param {CellReference[]} [updates.cells] - Updated cell references
 * @param {GridConfig} [updates.grid_config] - Updated grid configuration
 * @returns {Promise<LayoutBook>}
 */
export async function updateLayoutBook(id, updates) {
  try {
    log.debug('Updating layout book', { id, updates })
    
    const response = await apiFetch(`${API_BASE}/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(updates)
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `Failed to update layout book: ${response.statusText}`)
    }

    const data = await response.json()
    log.info('Updated layout book', { id, name: data.name })
    
    return data
  } catch (error) {
    log.error('Error updating layout book', error)
    throw error
  }
}

/**
 * Delete a layout book
 * 
 * @param {string} id - Layout book UUID
 * @returns {Promise<void>}
 */
export async function deleteLayoutBook(id) {
  try {
    log.debug('Deleting layout book', { id })
    
    const response = await apiFetch(`${API_BASE}/${id}`, {
      method: 'DELETE'
    })

    if (!response.ok) {
      throw new Error(`Failed to delete layout book: ${response.statusText}`)
    }

    log.info('Deleted layout book', { id })
  } catch (error) {
    log.error('Error deleting layout book', error)
    throw error
  }
}

/**
 * Validate layout book before applying (checks if persistent cells exist)
 * 
 * @param {string} id - Layout book UUID
 * @returns {Promise<{success: boolean, cells_found: number, cells_missing: number, missing_cell_ids: string[]}>}
 */
export async function validateLayoutBook(id) {
  try {
    log.debug('Validating layout book', { id })
    
    const response = await apiFetch(`${API_BASE}/${id}/apply`, {
      method: 'PUT'
    })

    if (!response.ok) {
      throw new Error(`Failed to validate layout book: ${response.statusText}`)
    }

    const data = await response.json()
    log.info('Validated layout book', { 
      id, 
      cellsFound: data.cells_found,
      cellsMissing: data.cells_missing
    })
    
    return data
  } catch (error) {
    log.error('Error validating layout book', error)
    throw error
  }
}

export default {
  fetchLayoutBooks,
  getLayoutBook,
  createLayoutBook,
  updateLayoutBook,
  deleteLayoutBook,
  validateLayoutBook
}
