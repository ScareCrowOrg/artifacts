/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-02",
 *   "console_calls_found": 10,
 *   "console_calls_migrated": 10,
 *   "migration_rate": 100,
 *   "logger_namespace": "store:cells",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Cells Store
 *
 * Manages cells-related state and actions.
 * Replaces global events and emits from cell components:
 * - refresh-cells-list, celula-criada, delete-cell
 * - copy-content, selection-changed, add-fragment, toggle-fragments, save, delete
 * - cell-closed, close-cell-view, update:cell-data, file-saved
 * - cell-saved, cell-deleted, update:filename, update:folder, send-to-chat
 *
 * @module stores/cells
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createLogger } from '@/utils/logger'

// Create logger for this store
const log = createLogger('store:cells')

export const useCellsStore = defineStore('cells', () => {
  // State
  const cellsSidebarRef = ref(null)
  const lastCreatedCell = ref(null)
  const deleteCellTrigger = ref(0)
  const selectedCells = ref([])
  const fragmentsVisible = ref(false)
  const saveCellTrigger = ref(0)
  const copiedContent = ref(null)

  // Cell View state - replaces emits from cell views
  const cellViewCloseTrigger = ref(0) // Replaces 'cell-closed', 'close-cell-view' emits
  const cellDataUpdates = ref({}) // Replaces 'update:cell-data' emit
  const fileSavedTrigger = ref(0) // Replaces 'file-saved' emit
  const cellSavedData = ref(null) // Replaces 'cell-saved' emit
  const cellDeletedId = ref(null) // Replaces 'cell-deleted' emit

  // Filename/folder state - replaces v-model emits from CellFileControls
  const cellFilename = ref('')
  const cellFolder = ref('')

  // Fragment management - replaces 'add-fragment' emit
  const addFragmentTrigger = ref(0) // Replaces 'add-fragment' emit

  // Cell data buffer for persistence
  const cellDataBuffer = ref(null)

  /**
   * Register the CellsSidebar component instance
   *
   * @param {Object} componentInstance - Vue component instance
   */
  function registerCellsSidebar(componentInstance) {
    cellsSidebarRef.value = componentInstance
  }

  /**
   * Refresh the cells list
   * Replaces: refresh-cells-list event
   */
  function refreshCellsList() {
    const cellsSidebar = cellsSidebarRef.value
    if (cellsSidebar && typeof cellsSidebar.refreshCells === 'function') {
      cellsSidebar.refreshCells()
      log.debug('Cells list refresh triggered')
    } else {
      log.warn('CellsSidebar or refreshCells method not available')
    }
  }

  /**
   * Notify that a cell was created
   * Replaces: celula-criada event
   *
   * @param {Object} cell - Created cell data
   */
  function notifyCellCreated(cell) {
    lastCreatedCell.value = cell
    refreshCellsList()
    log.info('Cell created', cell)
  }

  /**
   * Trigger cell deletion
   * Replaces: delete-cell event
   */
  function triggerDeleteCell() {
    deleteCellTrigger.value = Date.now()
    log.debug('Delete cell triggered')
  }

  /**
   * Copy content for cell creation
   * Replaces: copy-content event
   *
   * @param {string} content - Content to copy
   */
  function copyContentForCell(content) {
    copiedContent.value = content
    log.debug('Content copied for cell creation')
  }

  /**
   * Update cell selection state
   * Replaces: selection-changed event
   *
   * @param {string} cellId - Cell ID
   * @param {boolean} isSelected - Selection state
   */
  function updateCellSelection(cellId, isSelected) {
    if (isSelected) {
      if (!selectedCells.value.includes(cellId)) {
        selectedCells.value.push(cellId)
      }
    } else {
      const index = selectedCells.value.indexOf(cellId)
      if (index > -1) {
        selectedCells.value.splice(index, 1)
      }
    }
    log.debug('Cell selection updated', { cellId, isSelected })
  }

  /**
   * Toggle fragments panel visibility
   * Replaces: toggle-fragments event
   */
  function toggleFragments() {
    fragmentsVisible.value = !fragmentsVisible.value
    log.debug('Fragments visibility toggled', { fragmentsVisible: fragmentsVisible.value })
  }

  /**
   * Trigger cell save
   * Replaces: save event
   */
  function triggerSaveCell() {
    saveCellTrigger.value = Date.now()
    log.debug('Save cell triggered')
  }

  /**
   * Clear copied content
   */
  function clearCopiedContent() {
    copiedContent.value = null
  }

  /**
   * Unregister the CellsSidebar component instance
   */
  function unregisterCellsSidebar() {
    cellsSidebarRef.value = null
  }

  /**
   * Close cell view
   * Replaces: 'cell-closed', 'close-cell-view' emits
   *
   * @param {string|number} cellId - Optional cell ID for context
   */
  function closeCellView(cellId = null) {
    cellViewCloseTrigger.value = Date.now()
    log.debug('Cell view close triggered', { cellId })
  }

  /**
   * Update cell data
   * Replaces: 'update:cell-data' emit
   *
   * @param {string|number} cellId - Cell ID
   * @param {Object} data - Updated cell data
   */
  function updateCellData(cellId, data) {
    cellDataUpdates.value = {
      ...cellDataUpdates.value,
      [cellId]: {
        data,
        timestamp: Date.now(),
      },
    }
    log.debug('Cell data updated', { cellId, data })
  }

  /**
   * Notify that a file was saved
   * Replaces: 'file-saved' emit
   */
  function notifyFileSaved() {
    fileSavedTrigger.value = Date.now()
    log.debug('File saved notification')
  }

  /**
   * Notify that a cell was saved
   * Replaces: 'cell-saved' emit
   *
   * @param {Object} cell - Saved cell data
   */
  function notifyCellSaved(cell) {
    cellSavedData.value = cell
    log.debug('Cell saved', { cell })
  }

  /**
   * Notify that a cell was deleted
   * Replaces: 'cell-deleted' emit
   *
   * @param {string|number} cellId - Deleted cell ID
   */
  function notifyCellDeleted(cellId) {
    cellDeletedId.value = cellId
    log.debug('Cell deleted', { cellId })
  }

  /**
   * Update cell filename
   * Replaces: 'update:filename' emit
   *
   * @param {string} filename - New filename
   */
  function updateCellFilename(filename) {
    cellFilename.value = filename
  }

  /**
   * Update cell folder
   * Replaces: 'update:folder' emit
   *
   * @param {string} folder - New folder path
   */
  function updateCellFolder(folder) {
    cellFolder.value = folder
  }

  /**
   * Trigger add fragment modal
   * Replaces: 'add-fragment' emit
   */
  function triggerAddFragment() {
    addFragmentTrigger.value = Date.now()
    log.debug('Add fragment triggered')
  }

  /**
   * Update cell data buffer for pending save
   * This is critical for persistence flow
   *
   * @param {Object} data - Cell data to buffer
   */
  function updateCellDataBuffer(data) {
    cellDataBuffer.value = data
    log.debug('Cell data buffer updated', { data })
  }

  return {
    // State
    cellsSidebarRef,
    lastCreatedCell,
    deleteCellTrigger,
    selectedCells,
    fragmentsVisible,
    saveCellTrigger,
    copiedContent,
    cellViewCloseTrigger,
    cellDataUpdates,
    fileSavedTrigger,
    cellSavedData,
    cellDeletedId,
    cellFilename,
    cellFolder,
    addFragmentTrigger,
    cellDataBuffer,

    // Actions
    registerCellsSidebar,
    unregisterCellsSidebar,
    refreshCellsList,
    notifyCellCreated,
    triggerDeleteCell,
    copyContentForCell,
    updateCellSelection,
    toggleFragments,
    triggerSaveCell,
    clearCopiedContent,
    closeCellView,
    updateCellData,
    notifyFileSaved,
    notifyCellSaved,
    notifyCellDeleted,
    updateCellFilename,
    updateCellFolder,
    triggerAddFragment,
    updateCellDataBuffer,
  }
})
