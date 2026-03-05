/**
 * Notebook Cells Admin Service
 *
 * Provides API methods for administrative notebook cell management:
 * - Fetching cells with filtering and pagination
 * - Viewing detailed cell information
 * - Updating cell content
 *
 * @module services/notebookCellsService
 */

import { API_BASE_URL } from '../config/endpoints.js'
import apiService from './apiService.js'

/**
 * Fetch paginated notebook cells with optional filtering.
 *
 * @param {Object} options - Query options
 * @param {number} [options.page=1] - Page number (starts at 1)
 * @param {number} [options.limit=20] - Items per page
 * @param {string} [options.status] - Filter by cell status (pendente, executando, finalizado, erro)
 * @param {string} [options.notebookItemTypeId] - Filter by notebook_item_type_id
 * @returns {Promise<Object>} Paginated response with cells and metadata
 */
export async function fetchNotebookCells({
  page = 1,
  limit = 20,
  status = null,
  notebookItemTypeId = null,
} = {}) {
  let url = `${API_BASE_URL}/api/issues-dashboard/cells?page=${page}&limit=${limit}`

  if (status && status !== 'all') {
    url += `&status=${encodeURIComponent(status)}`
  }

  // Add server-side filtering by notebook_item_type_id
  if (notebookItemTypeId && notebookItemTypeId !== 'all') {
    url += `&item_type=${encodeURIComponent(notebookItemTypeId)}`
  }

  const response = await apiService.fetch(url)

  if (!response.ok) {
    throw new Error(`Failed to fetch notebook cells: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Fetch details of a specific notebook cell.
 *
 * @param {string} cellId - UUID of the cell
 * @returns {Promise<Object>} Cell object with full details
 */
export async function fetchCellDetails(cellId) {
  const response = await apiService.fetch(
    `${API_BASE_URL}/api/issues-dashboard/cells/${cellId}`,
  )

  if (!response.ok) {
    throw new Error(
      `Failed to fetch cell details: ${response.statusText}`,
    )
  }

  return response.json()
}

/**
 * Update a notebook cell.
 *
 * @param {string} cellId - UUID of the cell to update
 * @param {Object} updates - Fields to update
 * @param {Object} [updates.initial_data] - Updated initial data
 * @param {string} [updates.status] - Updated status
 * @param {Array} [updates.fragments] - Updated fragments
 * @param {string} [updates.title] - Updated title
 * @param {string} [updates.content] - Updated content
 * @returns {Promise<Object>} Updated cell object
 */
export async function updateNotebookCell(cellId, updates) {
  const response = await apiService.fetch(
    `${API_BASE_URL}/api/cells/${cellId}/update`,
    {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updates),
    },
  )

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(
      `Failed to update cell: ${response.statusText} - ${errorText}`,
    )
  }

  return response.json()
}

/**
 * Fetch available notebook item types for filtering.
 *
 * @returns {Promise<Array>} List of notebook item types
 */
export async function fetchNotebookItemTypes() {
  const response = await apiService.fetch(
    `${API_BASE_URL}/api/notebook-item-types/listar`,
  )

  if (!response.ok) {
    throw new Error(
      `Failed to fetch notebook item types: ${response.statusText}`,
    )
  }

  return response.json()
}

/**
 * Trigger discovery of cell types from the filesystem registry.
 * 
 * This automatically refreshes the cell type registry without requiring
 * manual intervention or server restart.
 *
 * @returns {Promise<Object>} Discovery results with count and type IDs
 * @throws {Error} If discovery fails
 */
export async function discoverCellTypes() {
  const response = await apiService.fetch(
    `${API_BASE_URL}/api/notebook-item-types/registry/discover`,
    {
      method: 'POST',
    }
  )

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(
      errorData.detail || `Failed to discover cell types: ${response.statusText}`
    )
  }

  return response.json()
}

export default {
  fetchNotebookCells,
  fetchCellDetails,
  updateNotebookCell,
  fetchNotebookItemTypes,
  discoverCellTypes,
}
