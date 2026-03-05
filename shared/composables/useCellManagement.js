/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-22",
 *   "console_calls_found": 26,
 *   "console_calls_migrated": 26,
 *   "migration_rate": 100,
 *   "logger_namespace": "cells:management",
 *   "validation_status": "excellent"
 * }
 */
import { ref } from 'vue'
import apiService from '../services/apiService.js'
import { ENDPOINTS } from '../config/endpoints.js'
import {
  getNotebookItemTypeId,
  CellStatus,
  DEFAULT_CELL_VERSION,
} from '../types/notebook.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:management')

/**
 * Composable for managing cell operations and state.
 * Adapted to work with NotebookItem architecture.
 *
 * @returns {Object} An object containing:
 *   @property {Ref<ICelula|null>} activeCell - The currently active cell (NotebookItem/Celula).
 *   @property {Ref<Object|null>} activeCellViewComponent - The current view component for the active cell.
 *   @property {Ref<string|null>} activeCellTypeId - The type ID of the active cell.
 *   @property {Ref<Object|null>} activeCellType - The type object of the active cell.
 *   @property {Ref<string|null>} cellViewError - Error state for the cell view.
 *   @property {Ref<string|null>} expectedComponentName - The expected component name for the cell type.
 *   @property {Ref<Array>} ephemeralCells - List of ephemeral cells (temporary cells).
 *   @property {Ref<boolean>} isSavingCell - Boolean indicating if a cell is being saved.
 *   @property {Ref<Object|null>} cellDataBuffer - Buffer for cell data.
 *   @property {Function} setActiveCell - Sets the active cell.
 *   @property {Function} clearActiveCell - Clears the active cell state.
 *   @property {Function} updateCellViewState - Updates cell view loading state.
 *   @property {Function} onCellSaved - Handles cell saved event.
 *   @property {Function} onCellDeleted - Handles cell deleted event.
 *   @property {Function} createNewCell - Creates a new unclassified cell.
 *   @property {Function} createFileEditorCell - Creates an ephemeral file editor cell.
 *   @property {Function} closeEphemeralCell - Closes an ephemeral cell.
 *   @property {Function} updateCellDataBuffer - Updates cell data buffer.
 *   @property {Function} saveCell - Saves a cell (create or update).
 *   @property {Function} deleteCell - Deletes a cell.
 *   @property {Function} canSaveCell - Checks if a cell can be saved.
 */
export function useCellManagement() {
  const activeCell = ref(null)
  const activeCellViewComponent = ref(null)
  const activeCellTypeId = ref(null)
  const activeCellType = ref(null)
  const cellViewError = ref(null)
  const expectedComponentName = ref(null)
  const ephemeralCells = ref([])
  const isSavingCell = ref(false)
  const cellDataBuffer = ref(null)

  /**
   * Set active cell (now accepts NotebookItem/Celula)
   */
  function setActiveCell(cell) {
    // Clear previous cell view state when switching to a new cell
    if (activeCell.value && activeCell.value.id !== cell?.id) {
      activeCellViewComponent.value = null
      cellViewError.value = null
      activeCellType.value = null
      expectedComponentName.value = null
    }
    
    activeCell.value = cell
    activeCellTypeId.value = getNotebookItemTypeId(cell)
  }

  /**
   * Clear active cell
   */
  function clearActiveCell() {
    activeCell.value = null
    activeCellViewComponent.value = null
    activeCellTypeId.value = null
    activeCellType.value = null
    cellViewError.value = null
    expectedComponentName.value = null
  }

  /**
   * Update cell view loading state
   */
  function updateCellViewState({ viewComponent, error, cellType }) {
    if (error) {
      cellViewError.value = error
      activeCellType.value = cellType
      expectedComponentName.value = cellType?.views_components?.[0]
    } else if (viewComponent) {
      activeCellViewComponent.value = viewComponent
      cellViewError.value = null
    }
  }

  /**
   * Handle cell saved event
   */
  function onCellSaved(savedCell, cellsSidebarRef) {
    log.info('Cell saved', savedCell)
    activeCell.value = savedCell

    if (cellsSidebarRef?.refreshCells) {
      cellsSidebarRef.refreshCells()
    }
  }

  /**
   * Handle cell deleted event
   */
  function onCellDeleted(cellId, cellsSidebarRef) {
    log.info('Cell deleted', cellId)
    clearActiveCell()

    if (cellsSidebarRef?.refreshCells) {
      cellsSidebarRef.refreshCells()
    }
  }

  /**
   * Create new unclassified cell (NotebookItem structure)
   */
  function createNewCell() {
    const unclassifiedTypeId = 'unclassified'

    const newCell = {
      id: null,
      notebook_item_type_id: unclassifiedTypeId,
      assignee_id: null, // Will be set on save
      fragments: [],
      refs: {},
      initial_data: {
        title: '',
        content: '',
      },
      status: CellStatus.PENDING,
      version: DEFAULT_CELL_VERSION,
    }

    setActiveCell(newCell)
  }

  /**
   * Create ephemeral file editor cell (NotebookItem structure)
   */
  function createFileEditorCell(fileInfo) {
    const fileEditorTypeId = 'file_editor'
    const ephemeralId = `ephemeral-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

    const ephemeralCell = {
      id: ephemeralId,
      notebook_item_type_id: fileEditorTypeId,
      assignee_id: null,
      fragments: [],
      refs: {},
      initial_data: {
        fileName: fileInfo.fileName,
        filePath: fileInfo.filePath,
      },
      status: CellStatus.PENDING,
      version: DEFAULT_CELL_VERSION,
    }

    ephemeralCells.value.push(ephemeralCell)
    setActiveCell(ephemeralCell)
  }

  /**
   * Close ephemeral cell
   */
  function closeEphemeralCell(cellId) {
    log.info('Ephemeral cell closed', cellId)
    ephemeralCells.value = ephemeralCells.value.filter((c) => c.id !== cellId)

    if (activeCell.value && activeCell.value.id === cellId) {
      clearActiveCell()
    }
  }

  /**
   * Update cell data buffer
   */
  function updateCellDataBuffer(cellData) {
    cellDataBuffer.value = cellData
  }

  /**
   * Save cell (create or update) - uses NotebookItem structure
   */
  async function saveCell(userId, activeCellComponentRef) {
    if (!activeCell.value) {
      log.warn('saveCell: No active cell to save')
      return
    }

    log.debug('Starting save for cell', {
      cellId: activeCell.value.id,
      cellType: activeCellTypeId.value,
      hasBuffer: !!cellDataBuffer.value,
      bufferData: cellDataBuffer.value
    })

    isSavingCell.value = true

    try {
      // Special handling for file_editor cells (ephemeral)
      if (activeCellTypeId.value === 'file_editor') {
        log.debug('Handling file_editor cell save')
        if (activeCellComponentRef?.onSave) {
          await activeCellComponentRef.onSave()
        }
        isSavingCell.value = false
        return
      }

      const dataToSave = cellDataBuffer.value || activeCell.value.initial_data || activeCell.value.data || {}

      // Validate and log dataToSave
      if (!dataToSave || typeof dataToSave !== 'object' || Array.isArray(dataToSave)) {
        log.error('Invalid cell data', {
          cellDataBuffer: cellDataBuffer.value,
          initial_data: activeCell.value?.initial_data,
          data: activeCell.value?.data,
          dataToSave: dataToSave
        })
        throw new Error('Invalid cell data: dataToSave is not an object')
      }
      log.debug('Cell data to save', JSON.stringify(dataToSave, null, 2))

      if (!activeCell.value.id) {
        // Create new cell - send full NotebookItem structure
        log.debug('Creating new cell with type', activeCellTypeId.value)
        const endpoint = `${ENDPOINTS.cells}/create`
        log.debug('API endpoint', endpoint)
        
        // Include fragments from the active cell (always include, even if empty)
        const cellFragments = activeCell.value.fragments || []
        log.debug('Including fragments in CREATE', cellFragments.length)
        
        const response = await apiService.fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            notebook_item_type_id: activeCellTypeId.value,
            assignee_id: userId,
            fragments: cellFragments,
            refs: activeCell.value.refs || {},
            initial_data: dataToSave,
            source_book_id: activeCell.value.source_book_id || null,
            status: activeCell.value.status || CellStatus.PENDING,
            version: activeCell.value.version || DEFAULT_CELL_VERSION,
          }),
        })

        log.debug('Create response status', response.status)

        if (!response.ok) {
          const errorText = await response.text()
          log.error('Create cell failed', {
            status: response.status,
            statusText: response.statusText,
            error: errorText,
          })
          throw new Error('Failed to create cell')
        }

        const createdCell = await response.json()
        log.info('Cell created successfully', createdCell.id)
        log.debug('Created cell data', {
          id: createdCell.id,
          fragmentsCount: createdCell.fragments?.length || 0,
          hasInitialData: !!createdCell.initial_data
        })
        return createdCell
      } else {
        // Update existing cell - send complete updated data
        log.debug('Updating existing cell', activeCell.value.id)
        const endpoint = ENDPOINTS.updateCell(activeCell.value.id)
        log.debug('API endpoint', endpoint)
        
        // Include fragments from the active cell (always include for consistency with CREATE)
        const cellFragments = activeCell.value.fragments || []
        log.debug('Including fragments in UPDATE', cellFragments.length)
        
        // Prepare the update payload with all relevant fields
        const updatePayload = {
          initial_data: dataToSave,
          fragments: cellFragments, // Always include for consistency
        }
        
        // Include status if it's been modified
        if (activeCell.value.status) {
          updatePayload.status = activeCell.value.status
        }
        
        log.debug('Update payload', {
          hasInitialData: !!updatePayload.initial_data,
          fragmentsCount: updatePayload.fragments?.length || 0,
          hasStatus: !!updatePayload.status
        })
        
        const response = await apiService.fetch(
          endpoint,
          {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(updatePayload),
          },
        )

        log.debug('Update response status', response.status)

        if (!response.ok) {
          const errorText = await response.text()
          log.error('Update cell failed', {
            status: response.status,
            statusText: response.statusText,
            error: errorText,
          })
          throw new Error('Failed to update cell')
        }

        const updatedCell = await response.json()
        log.info('Cell updated successfully', updatedCell.id)
        log.debug('Updated cell data', {
          id: updatedCell.id,
          fragmentsCount: updatedCell.fragments?.length || 0,
          hasInitialData: !!updatedCell.initial_data
        })
        return updatedCell
      }
    } catch (error) {
      log.error('Error saving cell', error)
      throw error
    } finally {
      isSavingCell.value = false
      cellDataBuffer.value = null
      log.debug('Save operation completed, buffer cleared')
    }
  }

  /**
   * Delete cell
   */
  async function deleteCell() {
    if (!activeCell.value || !activeCell.value.id) return

    // Try to get display name from initial_data or name
    const cellTitle =
      activeCell.value.initial_data?.title ||
      activeCell.value.initial_data?.fileName ||
      activeCell.value.name ||
      'this cell'

    if (!confirm(`Are you sure you want to delete "${cellTitle}"?`)) {
      return
    }

    isSavingCell.value = true

    try {
      const response = await apiService.fetch(
        `${ENDPOINTS.cells}/${activeCell.value.id}`,
        {
          method: 'DELETE',
        },
      )

      if (!response.ok) {
        throw new Error('Failed to delete cell')
      }

      return activeCell.value.id
    } catch (error) {
      log.error('Error deleting cell', error)
      throw error
    } finally {
      isSavingCell.value = false
    }
  }

  /**
   * Check if cell can be saved
   */
  function canSaveCell() {
    if (!activeCell.value) return false
    if (!activeCell.value.id) return true
    return true
  }

  return {
    // State
    activeCell,
    activeCellViewComponent,
    activeCellTypeId,
    activeCellType,
    cellViewError,
    expectedComponentName,
    ephemeralCells,
    isSavingCell,
    cellDataBuffer,

    // Methods
    setActiveCell,
    clearActiveCell,
    updateCellViewState,
    onCellSaved,
    onCellDeleted,
    createNewCell,
    createFileEditorCell,
    closeEphemeralCell,
    updateCellDataBuffer,
    saveCell,
    deleteCell,
    canSaveCell,
  }
}
