/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-14",
 *   "console_calls_found": 11,
 *   "console_calls_migrated": 11,
 *   "migration_rate": 100,
 *   "logger_namespace": "store:notebook-cells",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Notebook Cells Admin Store
 *
 * Manages state for the administrative notebook cells viewer.
 * Handles cell listing, filtering, selection, and editing.
 *
 * @module stores/notebookCells
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import notebookCellsService from '../services/notebookCellsService.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('store:notebook-cells')

export const useNotebookCellsStore = defineStore('notebookCells', () => {
  // State
  const cells = ref([])
  const selectedCell = ref(null)
  const isLoading = ref(false)
  const error = ref(null)

  // Pagination state
  const currentPage = ref(1)
  const itemsPerPage = ref(20)
  const totalItems = ref(0)
  const totalPages = ref(0)

  // Filter state
  const filters = ref({
    status: 'all',
    notebookItemTypeId: 'all',
    searchText: '',
  })

  // Notebook item types for filtering
  const notebookItemTypes = ref([])
  const isLoadingTypes = ref(false)

  // Computed
  const filteredCells = computed(() => {
    let filtered = cells.value

    // Apply search text filter (client-side)
    if (filters.value.searchText) {
      const searchLower = filters.value.searchText.toLowerCase()
      filtered = filtered.filter(
        (cell) =>
          cell.title?.toLowerCase().includes(searchLower) ||
          cell.content?.toLowerCase().includes(searchLower) ||
          cell.id?.toLowerCase().includes(searchLower),
      )
    }

    return filtered
  })

  // Actions

  /**
   * Load notebook cells with current filters and pagination.
   */
  async function loadCells() {
    isLoading.value = true
    error.value = null

    try {
      const response = await notebookCellsService.fetchNotebookCells({
        page: currentPage.value,
        limit: itemsPerPage.value,
        status: filters.value.status,
        notebookItemTypeId: filters.value.notebookItemTypeId,
      })

      cells.value = response.items || []
      totalItems.value = response.total_items || 0
      totalPages.value = response.total_pages || 0
      currentPage.value = response.current_page || 1

      log.debug(`Loaded ${cells.value.length} cells`)
    } catch (err) {
      error.value = `Failed to load cells: ${err.message}`
      log.error('Error loading cells', err)
      cells.value = []
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Load notebook item types for filtering.
   * Also triggers automatic cell type discovery from registry.
   */
  async function loadNotebookItemTypes() {
    isLoadingTypes.value = true

    try {
      // First, trigger registry discovery to ensure we have latest types
      try {
        const discoveryResult = await notebookCellsService.discoverCellTypes()
        log.debug(`Auto-discovered ${discoveryResult.discovered_count} cell types`)
      } catch (discoveryErr) {
        // Log warning but don't fail - continue with existing types
        log.warn('Cell type discovery failed (non-critical)', discoveryErr)
      }

      // Fetch the notebook item types (including newly discovered ones)
      const types = await notebookCellsService.fetchNotebookItemTypes()
      notebookItemTypes.value = types || []

      log.debug(`Loaded ${notebookItemTypes.value.length} types`)
    } catch (err) {
      log.error('Error loading notebook item types', err)
      notebookItemTypes.value = []
    } finally {
      isLoadingTypes.value = false
    }
  }

  /**
   * Select a cell for detailed viewing.
   *
   * @param {Object} cell - Cell to select
   */
  async function selectCell(cell) {
    if (!cell || !cell.id) {
      selectedCell.value = null
      return
    }

    isLoading.value = true
    error.value = null

    try {
      // Fetch full cell details
      const cellDetails = await notebookCellsService.fetchCellDetails(cell.id)
      selectedCell.value = cellDetails

      log.debug('Cell selected', cell.id)
    } catch (err) {
      error.value = `Failed to load cell details: ${err.message}`
      log.error('Error loading cell details', err)
      selectedCell.value = null
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Clear cell selection.
   */
  function clearSelection() {
    selectedCell.value = null
  }

  /**
   * Update a notebook cell.
   *
   * @param {string} cellId - UUID of the cell
   * @param {Object} updates - Fields to update
   */
  async function updateCell(cellId, updates) {
    isLoading.value = true
    error.value = null

    try {
      const updatedCell = await notebookCellsService.updateNotebookCell(
        cellId,
        updates,
      )

      // Update in cells list
      const index = cells.value.findIndex((c) => c.id === cellId)
      if (index !== -1) {
        cells.value[index] = updatedCell
      }

      // Update selected cell if it's the one being updated
      if (selectedCell.value && selectedCell.value.id === cellId) {
        selectedCell.value = updatedCell
      }

      log.debug('Cell updated', cellId)

      return updatedCell
    } catch (err) {
      error.value = `Failed to update cell: ${err.message}`
      log.error('Error updating cell', err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Set filter and reload cells.
   *
   * @param {Object} newFilters - Filter values to update
   */
  function setFilters(newFilters) {
    filters.value = { ...filters.value, ...newFilters }
    currentPage.value = 1 // Reset to first page
    loadCells()
  }

  /**
   * Navigate to a specific page.
   *
   * @param {number} page - Page number
   */
  function goToPage(page) {
    if (page < 1 || page > totalPages.value) {
      log.warn('Invalid page number', page)
      return
    }

    currentPage.value = page
    loadCells()
  }

  /**
   * Reset all filters.
   */
  function resetFilters() {
    filters.value = {
      status: 'all',
      notebookItemTypeId: 'all',
      searchText: '',
    }
    currentPage.value = 1
    loadCells()
  }

  return {
    // State
    cells,
    selectedCell,
    isLoading,
    error,
    currentPage,
    itemsPerPage,
    totalItems,
    totalPages,
    filters,
    notebookItemTypes,
    isLoadingTypes,

    // Computed
    filteredCells,

    // Actions
    loadCells,
    loadNotebookItemTypes,
    selectCell,
    clearSelection,
    updateCell,
    setFilters,
    goToPage,
    resetFilters,
  }
})
