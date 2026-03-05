/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-23",
 *   "console_calls_found": 17,
 *   "console_calls_migrated": 17,
 *   "migration_rate": 100,
 *   "logger_namespace": "layout:dynamic",
 *   "validation_status": "excellent"
 * }
 */
/**
 * @file useDynamicLayout.js
 * @description Composable for managing dynamic grid layout functionality
 * 
 * This composable provides the interface for interacting with the dynamic
 * grid layout system, including cell management, drag-drop, and persistence.
 * 
 * Part of Phase 1: Foundation & Infrastructure (Issue #1034)
 * Updated in Phase 6: Layout Persistence & Restore
 */

import { computed, ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { storeToRefs } from 'pinia'
import { createLogger } from '@/utils/logger'
import { useLayoutStore } from '@/stores/layout'
import { useAuthStore } from '@/stores/auth'

const log = createLogger('layout:dynamic')

/**
 * Composable for dynamic layout management
 * @param {Object} options - Configuration options
 * @param {boolean} [options.autoSave=true] - Enable auto-save on changes
 * @param {number} [options.autoSaveDelay=2000] - Debounce delay for auto-save (ms)
 * @returns {Object} Layout management interface
 */
export function useDynamicLayout(options = {}) {
  const { autoSave = true, autoSaveDelay = 2000 } = options
  
  const layoutStore = useLayoutStore()
  const authStore = useAuthStore()
  
  // Use storeToRefs to get reactive references without readonly computed wrappers
  // This allows vue3-grid-layout to mutate the layout array directly
  const { gridLayout, gridConfig } = storeToRefs(layoutStore)

  // Reactive references
  const isDragging = ref(false)
  const isResizing = ref(false)
  const draggedItemId = ref(null)
  const resizedItemId = ref(null)
  const autoSaveTimer = ref(null)
  const maxCellHeight = ref(30)  // ITERATION #5: Maximum cell height in grid units

  // Computed properties
  // Note: gridLayout and gridConfig are now direct refs from storeToRefs above
  const openCells = computed(() => layoutStore.getAllCells)
  const activeCellId = computed(() => layoutStore.activeCellId)
  const cellCount = computed(() => layoutStore.cellCount)
  const hasUnsavedChanges = computed(() => layoutStore.hasUnsavedChanges)
  const isMaxCellsReached = computed(() => layoutStore.isMaxCellsReached)
  const footerVisible = computed(() => layoutStore.footerVisible)
  const statusMessages = computed(() => layoutStore.getStatusMessages)

  /**
   * Add a new cell to the layout
   * @param {Object} params
   * @param {string} params.cellId - Cell ID from backend
   * @param {string} params.type - Cell type
   * @param {string} params.title - Cell title
   * @param {Object} [params.position] - Initial position
   * @param {Object} [params.state] - Initial state
   * @returns {boolean} Success
   */
  const addCell = (params) => {
    return layoutStore.addCell(params)
  }

  /**
   * Remove a cell from the layout
   * @param {string} cellId - Cell ID to remove
   * @param {boolean} [force=false] - Force close without confirmation
   * @returns {boolean} Success
   */
  const removeCell = (cellId, force = false) => {
    return layoutStore.removeCell(cellId, force)
  }

  /**
   * Close all cells (clear layout)
   * @param {boolean} [force=false] - Force close all without confirmation
   */
  const closeAllCells = (force = false) => {
    if (!force && hasUnsavedChanges.value) {
      // In production, this would show a confirmation dialog
      layoutStore.addStatusMessage({
        text: 'Some cells have unsaved changes',
        type: 'warning'
      })
      return false
    }

    layoutStore.clearLayout()
    return true
  }

  /**
   * Set the active cell
   * @param {string|null} cellId - Cell ID to activate
   */
  const setActiveCell = (cellId) => {
    layoutStore.setActiveCellId(cellId)
  }

  /**
   * Toggle footer visibility
   */
  const toggleFooter = () => {
    layoutStore.toggleFooter()
  }

  /**
   * Mark a cell as having unsaved changes
   * @param {string} cellId - Cell ID
   * @param {boolean} hasChanges - Whether cell has changes
   */
  const setCellUnsavedChanges = (cellId, hasChanges) => {
    layoutStore.setCellUnsavedChanges(cellId, hasChanges)
  }

  /**
   * Update cell state
   * @param {string} cellId - Cell ID
   * @param {Object} state - New state
   */
  const updateCellState = (cellId, state) => {
    layoutStore.updateCellState(cellId, state)
  }

  /**
   * Toggle minimize state for a cell
   * @param {string} cellId - Cell ID
   * @returns {boolean} Success
   */
  const toggleCellMinimize = (cellId) => {
    return layoutStore.toggleCellMinimize(cellId)
  }

  /**
   * Toggle maximize state for a cell
   * @param {string} cellId - Cell ID
   * @returns {boolean} Success
   */
  const toggleCellMaximize = (cellId) => {
    return layoutStore.toggleCellMaximize(cellId)
  }

  /**
   * Get cell by ID
   * @param {string} cellId - Cell ID
   * @returns {Object|undefined} Cell metadata
   */
  const getCellById = (cellId) => {
    return layoutStore.getCellById(cellId)
  }

  /**
   * Get layout item by cell ID
   * @param {string} cellId - Cell ID
   * @returns {Object|undefined} Layout item
   */
  const getLayoutItemByCellId = (cellId) => {
    return layoutStore.getLayoutItemByCellId(cellId)
  }

  /**
   * Handle layout update from vue3-grid-layout
   * @param {Array} newLayout - Updated layout from grid component
   */
  const handleLayoutUpdate = (newLayout) => {
    // Update each cell's position
    newLayout.forEach(item => {
      const cellId = item.cellId
      if (cellId) {
        layoutStore.updateCellPosition(cellId, {
          x: item.x,
          y: item.y,
          w: item.w,
          h: item.h
        })
      }
    })
  }

  /**
   * Handle drag start event
   * @param {string} itemId - Grid item ID
   */
  const handleDragStart = (itemId) => {
    isDragging.value = true
    draggedItemId.value = itemId
  }

  /**
   * Handle drag end event
   */
  const handleDragEnd = () => {
    isDragging.value = false
    draggedItemId.value = null
  }

  /**
   * Handle resize start event
   * @param {string} itemId - Grid item ID
   */
  const handleResizeStart = (itemId) => {
    isResizing.value = true
    resizedItemId.value = itemId
  }

  /**
   * Handle resize end event
   */
  const handleResizeEnd = () => {
    isResizing.value = false
    resizedItemId.value = null
  }

  /**
   * Handle item click (set as active)
   * @param {string} cellId - Cell ID
   */
  const handleItemClick = (cellId) => {
    setActiveCell(cellId)
  }

  /**
   * Add status message
   * @param {Object} params
   * @param {string} params.text - Message text
   * @param {string} [params.type='info'] - Message type
   * @param {number} [params.duration=5000] - Duration in ms
   */
  const addStatusMessage = (params) => {
    layoutStore.addStatusMessage(params)
  }

  /**
   * Remove status message
   * @param {string} messageId - Message ID
   */
  const removeStatusMessage = (messageId) => {
    layoutStore.removeStatusMessage(messageId)
  }

  /**
   * Clear all status messages
   */
  const clearStatusMessages = () => {
    layoutStore.clearStatusMessages()
  }

  /**
   * Save current layout
   */
  const saveLayout = async () => {
    const userId = authStore.user?.id
    await layoutStore.persistLayout(userId)
    addStatusMessage({
      text: 'Layout saved',
      type: 'success'
    })
  }

  /**
   * Load saved layout
   * @returns {boolean} Success
   */
  const loadLayout = async () => {
    const userId = authStore.user?.id
    const success = await layoutStore.loadLayout(userId)
    if (success) {
      addStatusMessage({
        text: 'Layout loaded',
        type: 'success'
      })
    }
    return success
  }

  /**
   * Auto-save layout with debouncing
   * @private
   */
  const scheduleAutoSave = () => {
    if (!autoSave) return

    // Clear existing timer
    if (autoSaveTimer.value) {
      clearTimeout(autoSaveTimer.value)
    }

    // Schedule new save
    autoSaveTimer.value = setTimeout(async () => {
      const userId = authStore.user?.id
      await layoutStore.persistLayout(userId)
      autoSaveTimer.value = null
    }, autoSaveDelay)
  }

  /**
   * Validate layout constraints
   * Ensures cells respect minimum/maximum sizes and don't overlap
   * @param {Array} layout - Layout to validate
   * @returns {Object} Validation result
   */
  const validateLayout = (layout) => {
    const errors = []
    const warnings = []

    layout.forEach(item => {
      // Check minimum size
      if (item.minW && item.w < item.minW) {
        errors.push(`Cell ${item.cellId} width below minimum (${item.w} < ${item.minW})`)
      }
      if (item.minH && item.h < item.minH) {
        errors.push(`Cell ${item.cellId} height below minimum (${item.h} < ${item.minH})`)
      }

      // Check maximum size
      if (item.maxW && item.w > item.maxW) {
        warnings.push(`Cell ${item.cellId} width above maximum (${item.w} > ${item.maxW})`)
      }
      if (item.maxH && item.h > item.maxH) {
        warnings.push(`Cell ${item.cellId} height above maximum (${item.h} > ${item.maxH})`)
      }

      // Check grid bounds
      if (item.x + item.w > layoutStore.gridConfig.cols) {
        errors.push(`Cell ${item.cellId} exceeds grid width`)
      }
    })

    return {
      isValid: errors.length === 0,
      errors,
      warnings
    }
  }

  /**
   * Calculate optimal cell size based on content type
   * @param {string} cellType - Type of cell
   * @returns {Object} Recommended size {w, h}
   */
  const getOptimalCellSize = (cellType) => {
    // Constants for better maintainability (Issue #1108 code review)
    const MIN_CELL_HEIGHT = 6
    const STANDARD_CELL_HEIGHT = 8
    const LARGE_CELL_HEIGHT = 10
    const XL_CELL_HEIGHT = 12
    
    const NARROW_CELL_WIDTH = 3
    const SMALL_CELL_WIDTH = 4
    const MEDIUM_CELL_WIDTH = 6
    const LARGE_CELL_WIDTH = 8
    
    // Default sizes for different cell types
    // Updated heights to provide better initial UX (Issue #1108)
    const sizePresets = {
      'file-editor': { w: MEDIUM_CELL_WIDTH, h: LARGE_CELL_HEIGHT },
      'markdown-editor': { w: MEDIUM_CELL_WIDTH, h: LARGE_CELL_HEIGHT },
      'code-fragment': { w: SMALL_CELL_WIDTH, h: STANDARD_CELL_HEIGHT },
      'chat-ia': { w: SMALL_CELL_WIDTH, h: STANDARD_CELL_HEIGHT },
      'notebook': { w: LARGE_CELL_WIDTH, h: XL_CELL_HEIGHT },
      'file-browser': { w: NARROW_CELL_WIDTH, h: LARGE_CELL_HEIGHT },
      'terminal': { w: LARGE_CELL_WIDTH, h: STANDARD_CELL_HEIGHT },
      'fragments-manager': { w: MEDIUM_CELL_WIDTH, h: LARGE_CELL_HEIGHT },
      'default': { w: SMALL_CELL_WIDTH, h: MIN_CELL_HEIGHT }
    }

    return sizePresets[cellType] || sizePresets.default
  }

  /**
   * Auto-organize cells in an optimal grid layout
   * Arranges cells in a compact, organized manner from top-left
   * @returns {boolean} Success
   */
  const autoOrganizeCells = () => {
    if (gridLayout.value.length === 0) {
      addStatusMessage({
        text: 'No cells to organize',
        type: 'info'
      })
      return false
    }

    console.log('[useDynamicLayout] 🎯 Auto-organizing cells', {
      totalCells: gridLayout.value.length
    })

    // Sort cells by current position (top to bottom, left to right)
    const sortedCells = [...gridLayout.value].sort((a, b) => {
      if (a.y !== b.y) return a.y - b.y
      return a.x - b.x
    })

    // Grid configuration
    const cols = layoutStore.gridConfig.cols
    let currentX = 0
    let currentY = 0
    let maxHeightInRow = 0

    // Reorganize each cell
    sortedCells.forEach((cell, index) => {
      // If cell would overflow, move to next row
      if (currentX + cell.w > cols) {
        currentX = 0
        currentY += maxHeightInRow
        maxHeightInRow = 0
      }

      // Update cell position
      layoutStore.updateCellPosition(cell.cellId, {
        x: currentX,
        y: currentY,
        w: cell.w,
        h: cell.h
      })

      // Track max height in current row
      maxHeightInRow = Math.max(maxHeightInRow, cell.h)

      // Move to next position
      currentX += cell.w
    })

    addStatusMessage({
      text: 'Cells auto-organized successfully',
      type: 'success',
      duration: 3000
    })

    log.info('Auto-organize complete')
    return true
  }

  /**
   * Calculate maximum cell height based on available viewport height
   * Part of dynamic height adjustment (Issue #1469 Iterations 5-6)
   * ITERATION #6: Apply 70% viewport constraint for one-time auto-resize
   * @returns {number} Maximum height in grid units
   */
  const calculateMaxCellHeight = () => {
    // Get workspace container element
    const workspaceElement = document.querySelector('.workspace-content')
    
    if (!workspaceElement) {
      log.warn('Workspace element not found for maxH calculation')
      return 30  // Fallback: reasonable default
    }
    
    // Get visible viewport height (clientHeight excludes scrollbars)
    const workspaceHeight = workspaceElement.clientHeight
    const rowHeight = gridConfig.value?.rowHeight || 30
    
    // ITERATION #6: Apply 70% constraint as requested by user
    // "penso que se vcs colocarem o tamanho maximo de 70% da viewport default"
    const constraint_percentage = 0.7
    const maxHeight_70percent = Math.floor(workspaceHeight * constraint_percentage)
    
    // Convert to grid units
    const maxH_calculated = Math.floor(maxHeight_70percent / rowHeight)
    
    // Ensure maxH is at least minH (4 units)
    const minH_constraint = 4
    let maxH_final = Math.min(Math.max(maxH_calculated, minH_constraint), 20);
    
    log.debug('Calculating maxH (70% constraint)', {
      workspaceHeight,
      constraint_percentage,
      maxHeight_70percent,
      rowHeight,
      maxH_calculated,
      minH_constraint,
      maxH_final,
      timestamp: new Date().toISOString()
    })
    
    return maxH_final
  }

  /**
   * Update maximum cell height
   * Part of dynamic height adjustment (Issue #1469 Iteration 5)
   * @returns {number} Updated maxH value
   */
  const updateMaxCellHeight = () => {
    const newMaxH = calculateMaxCellHeight()
    
    if (newMaxH !== maxCellHeight.value) {
      const oldMaxH = maxCellHeight.value
      maxCellHeight.value = newMaxH
      
      log.debug('maxH updated', {
        oldMaxH,
        newMaxH,
        change: newMaxH - oldMaxH
      })
    }
    
    return maxCellHeight.value
  }

  /**
   * Adjust cell height to fit content
   * Part of dynamic height adjustment (Issue #1469 Iterations 2, 4, 5)
   * @param {string} cellId - Cell ID
   * @param {number} contentHeight - Content height in pixels
   * @returns {boolean} Success
   */
  const adjustCellHeightToContent = (cellId, contentHeight) => {
    const rowHeight = gridConfig.value.rowHeight
    
    if (!rowHeight || rowHeight <= 0) {
      log.error('Invalid rowHeight', rowHeight)
      return false
    }
    
    // Find current cell
    const currentItem = getLayoutItemByCellId(cellId)
    
    if (!currentItem) {
      log.error('Layout item not found', cellId)
      return false
    }
    
    // Calculate required height
    const requiredUnits_calculated = Math.ceil(contentHeight / rowHeight)
    const currentHeight_units = currentItem.h
    
    // ITERATION #5: Get current maxH and apply constraint
    const maxH_units = maxCellHeight.value
    const finalHeight_units = Math.min(requiredUnits_calculated, maxH_units)
    
    // Check if limited by maxH
    const wasLimitedByMaxH = requiredUnits_calculated > maxH_units
    const willHaveScroll = finalHeight_units === maxH_units && contentHeight > (maxH_units * rowHeight)
    const heightChange = finalHeight_units - currentHeight_units
    
    log.debug('Adjusting cell height (ONE-TIME, 70% constraint)', {
      cellId,
      targetHeight_px: contentHeight,
      requiredUnits_calculated,
      currentHeight_units,
      maxH_units,
      finalHeight_units,
      wasLimitedByMaxH,
      willHaveScroll,
      heightChange
    })
    
    // Only update if height changed significantly (avoid micro-adjustments)
    if (Math.abs(heightChange) >= 1) {
      console.group('[useDynamicLayout] 🎯 Adjusting cell height to content')
      log.debug('Cell ID', cellId)
      log.debug('Content Height (px)', contentHeight)
      log.debug('Required h (units)', requiredUnits_calculated)
      log.debug('MaxH (units)', maxH_units)
      log.debug('Final h (units)', finalHeight_units)
      log.debug('Limited by maxH', wasLimitedByMaxH)
      console.groupEnd()
      
      return layoutStore.updateCellHeight(cellId, finalHeight_units, maxH_units)
    }
    
    return false
  }

  /**
   * Export layout configuration
   * @returns {Object} Exportable layout data
   */
  const exportLayout = () => {
    return {
      version: '1.0',
      gridConfig: layoutStore.gridConfig,
      layout: gridLayout.value,
      cells: openCells.value.map(cell => ({
        id: cell.id,
        type: cell.type,
        title: cell.title
      })),
      timestamp: Date.now()
    }
  }

  /**
   * Import layout configuration
   * @param {Object} layoutData - Layout data to import
   * @returns {boolean} Success
   */
  const importLayout = (layoutData) => {
    try {
      // Validate layout data
      if (!layoutData || !layoutData.version) {
        throw new Error('Invalid layout data')
      }

      // Clear current layout
      layoutStore.clearLayout()

      // Import layout
      // Note: In production, this would also restore cell data via API
      layoutData.layout.forEach(item => {
        const cellData = layoutData.cells.find(c => c.id === item.cellId)
        if (cellData) {
          addCell({
            cellId: cellData.id,
            type: cellData.type,
            title: cellData.title,
            position: {
              x: item.x,
              y: item.y,
              w: item.w,
              h: item.h
            }
          })
        }
      })

      addStatusMessage({
        text: 'Layout imported successfully',
        type: 'success'
      })

      return true
    } catch (error) {
      addStatusMessage({
        text: `Failed to import layout: ${error.message}`,
        type: 'error'
      })
      return false
    }
  }

  // Lifecycle hooks
  onMounted(() => {
    // Load saved layout on mount
    loadLayout()

    // ITERATION #6: Calculate initial maxH once (70% constraint)
    // No need to recalculate on viewport resize per user feedback
    nextTick(() => {
      const initialMaxH = calculateMaxCellHeight()
      maxCellHeight.value = initialMaxH
      
      log.info('Initial maxH set (70% constraint, ONE-TIME)', {
        maxH: initialMaxH,
        will_recalculate_on_resize: false,
        iteration: 6
      })
    })

    // ITERATION #6: Removed viewport resize listener per user feedback
    // User wants one-time 70% maxH, not dynamic recalculation
    // "apenas uma vez apos o render é suficiente"

    // Setup auto-save watchers if enabled
    if (autoSave) {
      // ITERATION #4: Watch for layout changes with guard to prevent save during load
      watch(
        () => layoutStore.gridLayout,
        () => {
          // Guard: Don't trigger autosave during layout loading
          if (layoutStore._isLoadingLayout) {
            log.debug('Skipping autosave - layout is loading (gridLayout changed)')
            return
          }
          scheduleAutoSave()
        },
        { deep: true }
      )

      watch(
        () => layoutStore.openCells,
        () => {
          // Guard: Don't trigger autosave during layout loading
          if (layoutStore._isLoadingLayout) {
            log.debug('Skipping autosave - layout is loading (openCells changed)')
            return
          }
          scheduleAutoSave()
        },
        { deep: true }
      )
    }

    // Setup keyboard shortcuts
    const handleKeydown = (event) => {
      // Ctrl/Cmd + S: Save layout
      if ((event.ctrlKey || event.metaKey) && event.key === 's') {
        event.preventDefault()
        saveLayout()
      }

      // Ctrl/Cmd + W: Close active cell
      if ((event.ctrlKey || event.metaKey) && event.key === 'w') {
        event.preventDefault()
        if (activeCellId.value) {
          removeCell(activeCellId.value)
        }
      }

      // Escape: Toggle footer
      if (event.key === 'Escape') {
        toggleFooter()
      }
    }

    window.addEventListener('keydown', handleKeydown)

    // Cleanup
    onUnmounted(() => {
      // Clear any pending auto-save
      if (autoSaveTimer.value) {
        clearTimeout(autoSaveTimer.value)
      }
      
      window.removeEventListener('keydown', handleKeydown)
      // ITERATION #6: Resize listener removed (one-time maxH calculation only)
    })
  })

  return {
    // State
    gridLayout,
    gridConfig,
    openCells,
    activeCellId,
    cellCount,
    hasUnsavedChanges,
    isMaxCellsReached,
    footerVisible,
    statusMessages,
    isDragging,
    isResizing,
    draggedItemId,
    resizedItemId,
    maxCellHeight,  // ITERATION #5: Maximum cell height constraint

    // Cell management
    addCell,
    removeCell,
    closeAllCells,
    setActiveCell,
    getCellById,
    getLayoutItemByCellId,
    setCellUnsavedChanges,
    updateCellState,
    toggleCellMinimize,
    toggleCellMaximize,

    // Layout management
    handleLayoutUpdate,
    handleDragStart,
    handleDragEnd,
    handleResizeStart,
    handleResizeEnd,
    handleItemClick,
    validateLayout,
    getOptimalCellSize,
    autoOrganizeCells,
    adjustCellHeightToContent,
    updateMaxCellHeight,  // ITERATION #5: Update maxH function

    // UI management
    toggleFooter,
    addStatusMessage,
    removeStatusMessage,
    clearStatusMessages,

    // Persistence
    saveLayout,
    loadLayout,
    exportLayout,
    importLayout
  }
}
