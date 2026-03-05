/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-22",
 *   "console_calls_found": 117,
 *   "console_calls_migrated": 117,
 *   "migration_rate": 100,
 *   "logger_namespace": "store:layout",
 *   "validation_status": "excellent"
 * }
 */
/**
 * @file layout.js
 * @description Pinia store for managing dynamic layout state
 * 
 * This store manages the state of the dynamic grid layout system,
 * including open cells, grid positions, and persistence.
 * 
 * Part of Phase 1: Foundation & Infrastructure (Issue #1034)
 * Updated in Phase 6: Layout Persistence & Restore
 */

import { defineStore } from 'pinia'
import * as layoutPersistence from '@/services/layoutPersistence.js'
import * as layoutBooksService from '@/services/layoutBooksService.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('store:layout')

/**
 * @typedef {Object} GridLayoutItem
 * @property {string} id - Unique identifier for the grid item
 * @property {string} cellId - Cell ID from backend
 * @property {string} type - Cell type (e.g., 'file-editor', 'chat-ia')
 * @property {number} x - X position in grid (column)
 * @property {number} y - Y position in grid (row)
 * @property {number} w - Width in grid units
 * @property {number} h - Height in grid units
 * @property {number} [minW] - Minimum width
 * @property {number} [minH] - Minimum height
 * @property {number} [maxW] - Maximum width
 * @property {number} [maxH] - Maximum height
 * @property {boolean} [isDraggable] - Whether item can be dragged
 * @property {boolean} [isResizable] - Whether item can be resized
 * @property {boolean} [static] - Whether item is static (not movable)
 */

/**
 * @typedef {Object} CellMetadata
 * @property {string} id - Cell ID
 * @property {string} type - Cell type
 * @property {string} title - Cell title/name
 * @property {Object} [state] - Cell-specific state
 * @property {boolean} hasUnsavedChanges - Whether cell has unsaved changes
 */

/**
 * @typedef {Object} StatusMessage
 * @property {string} id - Message ID
 * @property {string} text - Message text
 * @property {('info'|'success'|'warning'|'error')} type - Message type
 * @property {number} timestamp - Message timestamp
 */

export const useLayoutStore = defineStore('layout', {
  state: () => ({
    /**
     * @type {GridLayoutItem[]}
     * Grid layout configuration for all open cells
     */
    gridLayout: [],

    /**
     * @type {Map<string, CellMetadata>}
     * Metadata for each open cell (indexed by cell ID)
     */
    openCells: new Map(),

    /**
     * @type {string|null}
     * ID of the currently active/focused cell
     */
    activeCellId: null,

    /**
     * @type {boolean}
     * Whether the footer window manager is visible
     */
    footerVisible: true,

    /**
     * @type {StatusMessage[]}
     * Status bar messages
     */
    statusMessages: [],

    /**
     * @type {number}
     * Maximum number of cells that can be open simultaneously
     */
    maxOpenCells: 10,
    
    /**
     * @type {boolean}
     * Flag to prevent auto-save during load operations
     * @private
     */
    _isLoadingLayout: false,

    /**
     * @type {Object}
     * Grid configuration
     */
    gridConfig: {
      cols: 12, // Number of columns
      rowHeight: 30, // Height of each row in pixels
      margin: [10, 10], // Margin between grid items [x, y]
      containerPadding: [10, 10], // Padding around container [x, y]
      isDraggable: true,
      isResizable: true,
      isBounded: false,
      useCssTransforms: true,
      verticalCompact: true,
      preventCollision: false,
      responsive: true,
      breakpoints: {
        lg: 1200,
        md: 996,
        sm: 768,
        xs: 480,
        xxs: 0
      },
      colsPerBreakpoint: {
        lg: 12,
        md: 10,
        sm: 6,
        xs: 4,
        xxs: 2
      }
    },

    /**
     * Layout Books state (Phase 2: Layout Books)
     * @type {Array<Object>}
     */
    layoutBooks: [],

    /**
     * @type {string|null}
     * ID of the currently active layout book (if any)
     */
    activeLayoutBookId: null,

    /**
     * @type {boolean}
     * Loading state for layout books operations
     */
    layoutBooksLoading: false,

    /**
     * @type {string|null}
     * Error message for layout books operations
     */
    layoutBooksError: null
  }),

  getters: {
    /**
     * Get the currently active cell ID
     * @returns {string|null}
     */
    getActiveCellId: (state) => state.activeCellId,

    /**
     * Get count of open cells
     * @returns {number}
     */
    cellCount: (state) => state.openCells.size,

    /**
     * Check if there are any cells with unsaved changes
     * @returns {boolean}
     */
    hasUnsavedChanges: (state) => {
      for (const cell of state.openCells.values()) {
        if (cell.hasUnsavedChanges) {
          return true
        }
      }
      return false
    },

    /**
     * Get cell metadata by ID
     * @returns {function(string): CellMetadata|undefined}
     */
    getCellById: (state) => (cellId) => {
      return state.openCells.get(cellId)
    },

    /**
     * Get grid layout item by cell ID
     * @returns {function(string): GridLayoutItem|undefined}
     */
    getLayoutItemByCellId: (state) => (cellId) => {
      return state.gridLayout.find(item => item.cellId === cellId)
    },

    /**
     * Check if max cells limit has been reached
     * @returns {boolean}
     */
    isMaxCellsReached: (state) => {
      return state.openCells.size >= state.maxOpenCells
    },

    /**
     * Get all open cells as array
     * @returns {CellMetadata[]}
     */
    getAllCells: (state) => {
      return Array.from(state.openCells.values())
    },

    /**
     * Get status messages
     * @returns {StatusMessage[]}
     */
    getStatusMessages: (state) => state.statusMessages,

    /**
     * Layout Books getters (Phase 2)
     */

    /**
     * Get all layout books
     * @returns {Array}
     */
    getLayoutBooks: (state) => state.layoutBooks,

    /**
     * Get active layout book ID
     * @returns {string|null}
     */
    getActiveLayoutBookId: (state) => state.activeLayoutBookId,

    /**
     * Check if layout books are loading
     * @returns {boolean}
     */
    isLayoutBooksLoading: (state) => state.layoutBooksLoading,

    /**
     * Get layout books error message
     * @returns {string|null}
     */
    getLayoutBooksError: (state) => state.layoutBooksError,

    /**
     * Get layout book by ID
     * @param {string} id - Layout book ID
     * @returns {Object|undefined}
     */
    getLayoutBookById: (state) => (id) => {
      return state.layoutBooks.find(book => book.id === id)
    }
  },

  actions: {
    /**
     * Add a new cell to the layout
     * @param {Object} params
     * @param {string} params.cellId - Cell ID from backend (MUST BE IMMUTABLE)
     * @param {string} params.type - Cell type
     * @param {string} params.title - Cell title
     * @param {Object} [params.position] - Initial position {x, y, w, h}
     * @param {Object} [params.state] - Initial cell state
     */
    addCell({ cellId, type, title, position, state }) {
      log.debug('addCell called', {
        cellId,
        type,
        title,
        position,
        state,
        currentCellCount: this.openCells.size,
        maxCells: this.maxOpenCells,
        timestamp: new Date().toISOString()
      })
      
      // CRITICAL: Validate cellId immutability
      if (!cellId || typeof cellId !== 'string') {
        log.error('Invalid cellId provided', cellId)
        this.addStatusMessage({
          text: 'Failed to add cell: invalid cell ID',
          type: 'error'
        })
        return false
      }
      
      // Check max cells limit
      if (this.isMaxCellsReached) {
        log.warn('Max cells reached', {
          current: this.openCells.size,
          max: this.maxOpenCells
        })
        this.addStatusMessage({
          text: `Maximum number of cells (${this.maxOpenCells}) reached`,
          type: 'warning'
        })
        return false
      }

      // Check if cell already exists - IMMUTABILITY CHECK
      if (this.openCells.has(cellId)) {
        log.warn('Cell already exists - cellId must be unique and immutable', { 
          cellId,
          existingCell: this.openCells.get(cellId)
        })
        this.setActiveCellId(cellId)
        return false
      }

      // Add cell metadata with IMMUTABLE cellId
      const cellMetadata = Object.freeze({
        id: cellId, // IMMUTABLE
        type,
        title,
        state: state || {},
        hasUnsavedChanges: false,
        isMinimized: false,
        isMaximized: false
      })
      
      log.debug('Adding cell metadata with IMMUTABLE cellId', {
        cellId,
        metadata: cellMetadata
      })
      
      // DEBUG ITERATION 1: Log state object in detail
      log.debug('DEBUG ITERATION 1 - State Object Analysis', {
        stateReceived: state,
        initial_data: state?.initial_data,
        cellInstanceInitialData: state?.cellInstance?.initial_data,
        cellTypeDefaultInitialData: state?.cellType?.default_initial_data,
        contentField: state?.cellInstance?.initial_data?.content,
        languageField: state?.cellInstance?.initial_data?.language,
        fileNameField: state?.cellInstance?.initial_data?.fileName
      })
      
      this.openCells.set(cellId, cellMetadata)

      // Calculate default position if not provided
      const defaultPosition = this._calculateDefaultPosition()
      // Merge positions: default provides x/y, position can override any values
      const finalPosition = { ...defaultPosition, ...position }
      
      log.debug('Cell position', {
        provided: position,
        default: defaultPosition,
        final: finalPosition
      })

      // Add to grid layout
      // No maxH restriction - users can freely resize cells as needed
      
      const layoutItem = {
        i: `grid-item-${cellId}`, // 'i' is required by vue3-grid-layout
        cellId,
        type,
        x: finalPosition.x,
        y: finalPosition.y,
        w: finalPosition.w,
        h: finalPosition.h,
        minW: 2,
        minH: 4, // Increased from 2 to 4 to properly accommodate toolbar + content (Issue: cell layout UX)
        isDraggable: true,
        isResizable: true,
        static: false
      }
      
      log.debug('Adding layout item to grid', {
        layoutItem,
        gridLayoutBefore: this.gridLayout.length
      })

      this.gridLayout.push(layoutItem)
      
      log.debug('Cell added to grid', {
        cellId,
        gridLayoutAfter: this.gridLayout.length,
        layoutItem
      })

      // Set as active cell
      this.setActiveCellId(cellId)

      // Add status message
      this.addStatusMessage({
        text: `Cell "${title}" opened`,
        type: 'success'
      })

      // Persist layout
      this.persistLayout()
      
      log.debug('Cell add complete', {
        cellId,
        type,
        totalCells: this.openCells.size,
        gridItems: this.gridLayout.length
      })

      return true
    },

    /**
     * Remove a cell from the layout
     * @param {string} cellId - Cell ID to remove
     * @param {boolean} [force=false] - Force close even with unsaved changes
     */
    removeCell(cellId, force = false) {
      const cell = this.openCells.get(cellId)
      if (!cell) return false

      // Check for unsaved changes
      if (!force && cell.hasUnsavedChanges) {
        // In a real implementation, this would trigger a confirmation modal
        // For now, we'll just add a warning message
        this.addStatusMessage({
          text: `Cell "${cell.title}" has unsaved changes`,
          type: 'warning'
        })
        return false
      }

      // Remove from open cells
      this.openCells.delete(cellId)

      // Remove from grid layout
      this.gridLayout = this.gridLayout.filter(item => item.cellId !== cellId)

      // Update active cell if needed
      if (this.activeCellId === cellId) {
        const remainingCells = Array.from(this.openCells.keys())
        this.activeCellId = remainingCells.length > 0 ? remainingCells[0] : null
      }

      // Add status message
      this.addStatusMessage({
        text: `Cell "${cell.title}" closed`,
        type: 'info'
      })

      // Persist layout (but skip during layout loading to prevent empty state persistence)
      if (!this._isLoadingLayout) {
        this.persistLayout()
      }

      return true
    },

    /**
     * Update the position/size of a cell in the grid
     * @param {string} cellId - Cell ID
     * @param {Object} updates - Position/size updates {x, y, w, h}
     */
    updateCellPosition(cellId, updates) {
      const layoutItem = this.gridLayout.find(item => item.cellId === cellId)
      if (!layoutItem) return false

      // Update layout item
      Object.assign(layoutItem, updates)

      // Persist layout
      this.persistLayout()

      return true
    },

    /**
     * Set the active cell
     * @param {string|null} cellId - Cell ID to activate (or null to deactivate)
     */
    setActiveCellId(cellId) {
      if (cellId && !this.openCells.has(cellId)) return false
      this.activeCellId = cellId
      return true
    },

    /**
     * Toggle footer visibility
     */
    toggleFooter() {
      this.footerVisible = !this.footerVisible
      localStorage.setItem('scareverse_footer_visible', String(this.footerVisible))
    },

    /**
     * Mark a cell as having unsaved changes
     * @param {string} cellId - Cell ID
     * @param {boolean} hasChanges - Whether cell has unsaved changes
     */
    setCellUnsavedChanges(cellId, hasChanges) {
      const cell = this.openCells.get(cellId)
      if (cell) {
        cell.hasUnsavedChanges = hasChanges
      }
    },

    /**
     * Update cell state
     * @param {string} cellId - Cell ID
     * @param {Object} state - New state
     */
    updateCellState(cellId, state) {
      const cell = this.openCells.get(cellId)
      if (cell) {
        cell.state = { ...cell.state, ...state }
      }
    },

    /**
     * Toggle minimize state for a cell
     * Properly minimizes by reducing grid item height (Issue #1108)
     * @param {string} cellId - Cell ID
     */
    toggleCellMinimize(cellId) {
      const cell = this.openCells.get(cellId)
      if (!cell) return false

      const layoutItem = this.gridLayout.find(item => item.cellId === cellId)
      if (!layoutItem) return false

      // Constant for minimized height (Issue #1108 code review)
      const MINIMIZED_HEIGHT = 2 // Grid units (~60px, just showing toolbar)

      cell.isMinimized = !cell.isMinimized
      
      if (cell.isMinimized) {
        // If minimizing, ensure not maximized
        cell.isMaximized = false
        
        // Store current position and size before minimizing
        layoutItem.savedPosition = {
          x: layoutItem.x,
          y: layoutItem.y,
          w: layoutItem.w,
          h: layoutItem.h
        }
        
        // Minimize to compact height (just showing toolbar)
        // Keep width and x/y position, only reduce height
        layoutItem.h = MINIMIZED_HEIGHT
      } else {
        // Restore previous size
        if (layoutItem.savedPosition) {
          layoutItem.x = layoutItem.savedPosition.x
          layoutItem.y = layoutItem.savedPosition.y
          layoutItem.w = layoutItem.savedPosition.w
          layoutItem.h = layoutItem.savedPosition.h
          delete layoutItem.savedPosition
        }
      }

      this.persistLayout()
      return true
    },

    /**
     * Toggle maximize state for a cell
     * @param {string} cellId - Cell ID
     */
    toggleCellMaximize(cellId) {
      const cell = this.openCells.get(cellId)
      if (!cell) return false

      const layoutItem = this.gridLayout.find(item => item.cellId === cellId)
      if (!layoutItem) return false

      cell.isMaximized = !cell.isMaximized

      if (cell.isMaximized) {
        // If maximizing, ensure not minimized
        cell.isMinimized = false
        
        // Store current position before maximizing
        layoutItem.savedPosition = {
          x: layoutItem.x,
          y: layoutItem.y,
          w: layoutItem.w,
          h: layoutItem.h
        }
        
        // Maximize to full grid
        layoutItem.x = 0
        layoutItem.y = 0
        layoutItem.w = this.gridConfig.cols
        layoutItem.h = 12 // Reasonable full height
      } else {
        // Restore previous position
        if (layoutItem.savedPosition) {
          layoutItem.x = layoutItem.savedPosition.x
          layoutItem.y = layoutItem.savedPosition.y
          layoutItem.w = layoutItem.savedPosition.w
          layoutItem.h = layoutItem.savedPosition.h
          delete layoutItem.savedPosition
        }
      }

      this.persistLayout()
      return true
    },

    /**
     * Add a status message
     * @param {Object} params
     * @param {string} params.text - Message text
     * @param {('info'|'success'|'warning'|'error')} [params.type='info'] - Message type
     * @param {number} [params.duration=5000] - Duration in ms (0 for permanent)
     */
    addStatusMessage({ text, type = 'info', duration = 5000 }) {
      const message = {
        id: `status-${Date.now()}-${Math.random()}`,
        text,
        type,
        timestamp: Date.now()
      }

      this.statusMessages.push(message)

      // Auto-remove after duration
      if (duration > 0) {
        setTimeout(() => {
          this.removeStatusMessage(message.id)
        }, duration)
      }
    },

    /**
     * Remove a status message
     * @param {string} messageId - Message ID to remove
     */
    removeStatusMessage(messageId) {
      this.statusMessages = this.statusMessages.filter(msg => msg.id !== messageId)
    },

    /**
     * Clear all status messages
     */
    clearStatusMessages() {
      this.statusMessages = []
    },

    /**
     * Persist layout to localStorage
     * Also syncs to backend if user is authenticated
     * @param {string} [userId] - Optional user ID for backend sync
     */
    async persistLayout(userId = null) {
      const callTime = Date.now()
      const callStack = new Error().stack
      log.debug('💾 persistLayout called', {
        timestamp: new Date(callTime).toISOString(),
        userId,
        gridItemsCount: this.gridLayout.length,
        openCellsCount: this.openCells.size,
        isLoadingLayout: this._isLoadingLayout,
        callStack: callStack?.split('\n').slice(1, 4).join('\n') // Show caller
      })
      
      // GUARD: Don't persist during load to prevent infinite loop
      if (this._isLoadingLayout) {
        log.warn('persistLayout called during loadLayout - skipping to prevent loop')
        return false
      }
      
      try {
        const layoutData = {
          gridLayout: this.gridLayout,
          openCells: Array.from(this.openCells.entries()),
          activeCellId: this.activeCellId,
          footerVisible: this.footerVisible,
          timestamp: Date.now()
        }

        let localSuccess = false
        let backendSuccess = false

        // Save to localStorage (synchronous)
        const localResult = layoutPersistence.saveToLocalStorage(layoutData)
        
        if (!localResult.success) {
          log.error('Failed to save to localStorage:', localResult.error)
          // Don't return early - try backend save anyway
        } else {
          localSuccess = true
          log.debug('✅ Saved to localStorage')
        }

        // If user is authenticated, also save to backend (asynchronous)
        if (userId) {
          const backendResult = await layoutPersistence.saveToBackend(userId, layoutData)
          
          if (!backendResult.success) {
            log.warn('Failed to save to backend:', backendResult.error)
          } else {
            backendSuccess = true
            log.debug('✅ Saved to backend')
          }
        }

        // Show appropriate status message
        if (localSuccess || backendSuccess) {
          // At least one save succeeded
          if (!localSuccess) {
            this.addStatusMessage({
              text: 'Layout saved to server (local storage failed)',
              type: 'warning'
            })
          } else if (userId && !backendSuccess) {
            // Local saved but backend failed (less critical)
            // Don't show error - local save is enough for now
          }
          log.debug('✅ persistLayout completed successfully')
          return true
        } else {
          // Both failed
          this.addStatusMessage({
            text: 'Failed to save layout',
            type: 'error'
          })
          return false
        }
      } catch (error) {
        log.error('Failed to persist layout', error)
        this.addStatusMessage({
          text: 'Failed to save layout',
          type: 'error'
        })
        return false
      }
    },

    /**
     * Load layout from localStorage or backend
     * Prefers backend if user is authenticated (for cross-device sync)
     * @param {string} [userId] - Optional user ID for backend sync
     */
    async loadLayout(userId = null) {
      log.debug('loadLayout called')
      log.debug('userId:', userId)
      log.debug('Current state before load:', {
        cellCount: this.openCells.size,
        gridItems: this.gridLayout.length,
        activeCellId: this.activeCellId,
        isAlreadyLoading: this._isLoadingLayout
      })
      
      // GUARD: Prevent concurrent loadLayout calls
      if (this._isLoadingLayout) {
        log.warn('loadLayout already in progress - skipping to prevent loop')
        // Group end
        return false
      }
      
      // Set loading flag to prevent auto-save watchers from triggering during load
      this._isLoadingLayout = true
      log.debug('🔒 Loading flag set - auto-save watchers will be suppressed')
      
      try {
        let layoutData = null

        // If user is authenticated, try to sync with backend
        if (userId) {
          const syncResult = await layoutPersistence.syncLayout(userId)
          
          if (syncResult.success) {
            layoutData = syncResult.data
            log.debug('Layout loaded from ${syncResult.source}')
          } else {
            log.warn('Failed to sync layout:', syncResult.error)
            // Fall through to localStorage-only load
          }
        }

        // If not authenticated or sync failed, load from localStorage only
        if (!layoutData) {
          log.debug('📂 Loading from localStorage only')
          const localResult = layoutPersistence.loadFromLocalStorage()
          
          if (!localResult.success) {
            log.debug('ℹ️ No saved layout found, using default')
            // Group end
            return false
          }

          layoutData = localResult.data
        }

        log.debug('Layout data to restore:', {
          gridLayoutLength: layoutData.gridLayout?.length,
          openCellsLength: layoutData.openCells?.length,
          activeCellId: layoutData.activeCellId
        })

        // CRITICAL: Track cellIds before and after restore to detect mutations
        const cellIdsBefore = new Set(this.openCells.keys())
        log.debug('CellIds before restore:', Array.from(cellIdsBefore))

        // Restore grid layout - IMMUTABLE cellId check
        const restoredGridLayout = layoutData.gridLayout || []
        log.debug('🔍 Validating gridLayout cellIds for immutability')
        restoredGridLayout.forEach((item, index) => {
          if (!item.cellId || typeof item.cellId !== 'string') {
            log.error(`Invalid cellId at grid index ${index}:`, item)
            throw new Error(`Invalid cellId in gridLayout at index ${index}`)
          }
          log.debug(`  ✓ Grid item ${index}: cellId="${item.cellId}" (valid)`)
        })
        this.gridLayout = restoredGridLayout

        // Restore open cells (convert array back to Map) - IMMUTABLE cellId check
        const restoredCells = layoutData.openCells || []
        log.debug('🔍 Validating openCells cellIds for immutability')
        
        const newOpenCells = new Map()
        restoredCells.forEach(([cellId, metadata], index) => {
          if (!cellId || typeof cellId !== 'string') {
            log.error(`Invalid cellId at cell index ${index}:`, cellId)
            throw new Error(`Invalid cellId in openCells at index ${index}`)
          }
          
          // IMMUTABILITY GUARD: Freeze metadata to prevent modification
          const frozenMetadata = Object.freeze({
            ...metadata,
            id: cellId // Ensure id matches key
          })
          
          log.debug(`  ✓ Cell ${index}: cellId="${cellId}" (valid, frozen)`)
          newOpenCells.set(cellId, frozenMetadata)
        })
        
        this.openCells = newOpenCells

        // CRITICAL: Check for cellId mutations
        const cellIdsAfter = new Set(this.openCells.keys())
        log.debug('CellIds after restore:', Array.from(cellIdsAfter))
        
        // Detect if any cellIds changed (should never happen)
        const addedCells = Array.from(cellIdsAfter).filter(id => !cellIdsBefore.has(id))
        const removedCells = Array.from(cellIdsBefore).filter(id => !cellIdsAfter.has(id))
        
        if (addedCells.length > 0 || removedCells.length > 0) {
          log.warn('CellId changes detected during restore:', {
            added: addedCells,
            removed: removedCells
          })
        }

        // Restore active cell
        this.activeCellId = layoutData.activeCellId || null

        // Restore footer visibility
        this.footerVisible = layoutData.footerVisible !== undefined ? layoutData.footerVisible : true

        log.debug('Layout restore complete:', {
          cellCount: this.openCells.size,
          gridItems: this.gridLayout.length,
          activeCellId: this.activeCellId
        })
        
        // Clear loading flag AFTER all state changes to allow watchers to resume
        this._isLoadingLayout = false
        log.debug('🔓 Loading flag cleared - auto-save watchers resumed')
        // Group end
        return true
      } catch (error) {
        log.error('Failed to load layout:', error)
        // Clear loading flag on error too
        this._isLoadingLayout = false
        log.debug('🔓 Loading flag cleared (error case)')
        // Group end
        this.addStatusMessage({
          text: 'Failed to load saved layout',
          type: 'error'
        })
        return false
      }
    },

    /**
     * Clear layout (remove all cells)
     */
    clearLayout() {
      this.gridLayout = []
      this.openCells = new Map()
      this.activeCellId = null
      this.persistLayout()
    },

    /**
     * Calculate default position for a new cell
     * @private
     * @returns {Object} Position {x, y, w, h}
     */
    _calculateDefaultPosition() {
      // Find the next available position
      // This is a simple implementation - can be improved
      const existingPositions = this.gridLayout.map(item => ({
        x: item.x,
        y: item.y,
        w: item.w,
        h: item.h
      }))

      // Default dimensions for new cells
      const DEFAULT_CELL_WIDTH = 3  // 3 columns allows 4 cells per line: 12/3=4
      const DEFAULT_CELL_HEIGHT = 15 // Default 15 grid units (~450px with 30px rows, ~15vh) - user adjustable
      
      const defaultW = DEFAULT_CELL_WIDTH
      const defaultH = DEFAULT_CELL_HEIGHT

      // Start from top-left
      let x = 0
      let y = 0

      // Find first available position
      while (this._isPositionOccupied(x, y, defaultW, defaultH, existingPositions)) {
        x += defaultW
        if (x + defaultW > this.gridConfig.cols) {
          x = 0
          y += defaultH
        }
      }

      return { x, y, w: defaultW, h: defaultH }
    },
    
    /**
     * Calculate 70% of viewport height in grid units
     * @private
     * @returns {number} Height in grid units
     */
    _calculate70PercentHeight() {
      // Get workspace container element
      const workspaceElement = document.querySelector('.workspace-content')
      
      if (!workspaceElement) {
        log.warn('Workspace element not found, using fallback height')
        return 20 // Fallback: reasonable default (~600px with 30px rows)
      }
      
      // Get visible viewport height
      const workspaceHeight = workspaceElement.clientHeight
      const rowHeight = this.gridConfig.rowHeight || 30
      
      // Calculate 70% of viewport height
      const constraint_percentage = 0.7
      const maxHeight_70percent = Math.floor(workspaceHeight * constraint_percentage)
      
      // Convert to grid units
      const heightUnits = Math.floor(maxHeight_70percent / rowHeight)
      
      // Ensure height is at least minH (4 units) and reasonable
      const minH_constraint = 4
      const maxH_reasonable = 50 // Cap at reasonable maximum
      const finalHeight = Math.max(minH_constraint, Math.min(heightUnits, maxH_reasonable))
      
      log.debug('📏 Calculating default height (70% viewport)', {
        workspaceHeight,
        constraint_percentage,
        maxHeight_70percent,
        rowHeight,
        heightUnits,
        finalHeight,
        pixels: `${finalHeight * rowHeight}px`,
        timestamp: new Date().toISOString()
      })
      
      return finalHeight
    },

    /**
     * Check if a position is occupied
     * @private
     */
    _isPositionOccupied(x, y, w, h, positions) {
      return positions.some(pos => {
        return !(
          x + w <= pos.x ||
          x >= pos.x + pos.w ||
          y + h <= pos.y ||
          y >= pos.y + pos.h
        )
      })
    },

    /**
     * Update cell height in grid units
     * Part of dynamic height adjustment (Issue #1469 Iterations 2, 5)
     * @param {string} cellId - Cell ID
     * @param {number} newHeightUnits - New height in grid units
     * @param {number} maxH - Maximum allowed height in grid units (optional, for logging)
     * @returns {boolean} Success
     */
    updateCellHeight(cellId, newHeightUnits, maxH = null) {
      const layoutItem = this.gridLayout.find(item => item.cellId === cellId)
      
      if (!layoutItem) {
        log.error('❌ Cell not found for height update:', cellId)
        return false
      }
      
      // Respect minH
      const minH = layoutItem.minH || 4
      let finalHeight = Math.max(newHeightUnits, minH)
      
      // Respect maxH if defined
      if (layoutItem.maxH && finalHeight > layoutItem.maxH) {
        finalHeight = layoutItem.maxH
      }
      
      // ITERATION #5: Check if was clamped to maxH
      const wasClampedToMaxH = maxH !== null && newHeightUnits >= maxH
      
      log.debug('📊 Updating cell height', {
        cellId,
        oldHeight: layoutItem.h,
        newHeight: finalHeight,
        maxH: maxH || 'none',  // ITERATION #5
        wasClampedToMaxH,      // ITERATION #5
        gridUnit: `${finalHeight} units`,
        pixels: `${finalHeight * this.gridConfig.rowHeight}px`,
        timestamp: new Date().toISOString()
      })
      
      layoutItem.h = finalHeight
      
      // Trigger reactivity by creating new array reference
      this.gridLayout = [...this.gridLayout]
      
      // Persist updated layout
      this.persistLayout()
      
      return true
    },

    /**
     * ========================================
     * Layout Books Actions (Phase 2)
     * ========================================
     */

    /**
     * Fetch all layout books for current user
     * @param {Object} options - Query options
     * @param {number} [options.skip=0] - Skip items
     * @param {number} [options.limit=20] - Limit items
     * @param {string} [options.name] - Filter by name
     */
    async fetchLayoutBooks({ skip = 0, limit = 20, name = null } = {}) {
      this.layoutBooksLoading = true
      this.layoutBooksError = null
      
      try {
        log.debug('[LayoutStore] 📚 Fetching layout books')
        const response = await layoutBooksService.fetchLayoutBooks({ skip, limit, name })
        
        this.layoutBooks = response.items
        
        log.debug('✅ Layout books fetched', { count: response.items.length })
        
        return response
      } catch (error) {
        log.error('❌ Error fetching layout books:', error)
        this.layoutBooksError = error.message || 'Failed to fetch layout books'
        this.addStatusMessage({
          text: 'Failed to load layout books',
          type: 'error'
        })
        throw error
      } finally {
        this.layoutBooksLoading = false
      }
    },

    /**
     * Save current workspace layout as a new layout book
     * @param {string} name - Layout book name (1-100 chars)
     * @param {string} description - Layout book description (max 500 chars)
     * @returns {Promise<Object>} Created layout book
     */
    async saveLayoutAsBook(name, description = '') {
      this.layoutBooksLoading = true
      this.layoutBooksError = null
      
      try {
        log.debug('💾 Saving current layout as book', { name, cellCount: this.openCells.size })
        
        // Capture current workspace state
        const cells = []
        
        for (const layoutItem of this.gridLayout) {
          const cellMetadata = this.openCells.get(layoutItem.cellId)
          
          if (!cellMetadata) {
            log.warn('Cell metadata not found for', layoutItem.cellId)
            continue
          }
          
          // Determine cell category and collect data
          const cellRef = {
            category: cellMetadata.state?.cellInstance?.is_persistent ? 'persistent' : 'ephemeral',
            type: cellMetadata.type,
            title: cellMetadata.title,
            position: {
              x: layoutItem.x,
              y: layoutItem.y,
              w: layoutItem.w,
              h: layoutItem.h
            },
            state: {
              isMinimized: cellMetadata.isMinimized || false,
              isMaximized: cellMetadata.isMaximized || false
            }
          }
          
          // For persistent cells, store cell ID
          if (cellRef.category === 'persistent' && cellMetadata.state?.cellInstance?.id) {
            cellRef.cellId = cellMetadata.state.cellInstance.id
          }
          
          // For ephemeral cells, store initialization data
          if (cellRef.category === 'ephemeral' && cellMetadata.state?.cellInstance?.initial_data) {
            cellRef.initialization_data = cellMetadata.state.cellInstance.initial_data
          }
          
          cells.push(cellRef)
        }
        
        // Create layout book via API
        const layoutBookData = {
          name,
          description,
          cells,
          grid_config: {
            cols: this.gridConfig.cols,
            rowHeight: this.gridConfig.rowHeight,
            margin: this.gridConfig.margin
          }
        }
        
        const createdBook = await layoutBooksService.createLayoutBook(layoutBookData)
        
        // Add to local state
        this.layoutBooks.push({
          id: createdBook.id,
          name: createdBook.name,
          description: createdBook.description,
          cell_count: cells.length,
          persistent_count: cells.filter(c => c.category === 'persistent').length,
          ephemeral_count: cells.filter(c => c.category === 'ephemeral').length,
          created_at: createdBook.created_at,
          updated_at: createdBook.updated_at
        })
        
        // Set as active layout book
        this.activeLayoutBookId = createdBook.id
        
        this.addStatusMessage({
          text: `Layout book "${name}" saved successfully`,
          type: 'success'
        })
        
        log.debug('✅ Layout book saved', { id: createdBook.id, name })
        
        return createdBook
      } catch (error) {
        log.error('❌ Error saving layout book:', error)
        this.layoutBooksError = error.message || 'Failed to save layout book'
        this.addStatusMessage({
          text: 'Failed to save layout book',
          type: 'error'
        })
        throw error
      } finally {
        this.layoutBooksLoading = false
      }
    },

    /**
     * Load a layout book and restore workspace to saved state
     * @param {string} layoutBookId - Layout book UUID
     * @returns {Promise<Object>} Validation result
     */
    async loadLayoutBook(layoutBookId) {
      log.debug('loadLayoutBook called')
      log.debug('🎯 layoutBookId:', layoutBookId)
      log.debug('⏰ Timestamp:', new Date().toISOString())
      
      this.layoutBooksLoading = true
      this.layoutBooksError = null
      
      try {
        log.debug('📖 Loading layout book', { id: layoutBookId })
        
        // Check for unsaved changes
        if (this.hasUnsavedChanges) {
          const proceed = confirm('You have unsaved changes. Loading a layout book will close all cells. Continue?')
          if (!proceed) {
            log.debug('[LayoutStore] ℹ️ User cancelled layout book load')
            this.layoutBooksLoading = false
            // Group end
            return { cancelled: true }
          }
        }
        
        // Fetch layout book details
        log.debug('🔍 Fetching layout book from API...')
        const layoutBook = await layoutBooksService.getLayoutBook(layoutBookId)
        
        // Diagnostic logs to verify data structure
        log.debug('Data Structure Diagnosis')
        log.debug('Property Check:', {
          hasInitialData: !!layoutBook.initial_data,
          initialDataType: typeof layoutBook.initial_data
        })
        log.debug('📋 Available Keys:', {
          initialDataKeys: layoutBook.initial_data ? Object.keys(layoutBook.initial_data) : 'N/A'
        })
        log.debug('🔢 Cell Counts:', {
          cellsInInitialData: layoutBook.initial_data?.cells?.length || 0,
          initialDataCellsExists: !!layoutBook.initial_data?.cells
        })
        log.debug('⚙️ Grid Config Check:', {
          gridConfigInInitialData: !!layoutBook.initial_data?.grid_config
        })
        // Group end
        
        log.debug('📦 Layout Book Fetched:', {
          id: layoutBook.id,
          name: layoutBook.name,
          hasInitialData: !!layoutBook.initial_data,
          initialDataKeys: layoutBook.initial_data ? Object.keys(layoutBook.initial_data) : [],
          cellsCount: layoutBook.initial_data?.cells?.length || 0
        })
        log.debug('🔬 Complete Layout Book Structure:', JSON.stringify(layoutBook, null, 2))
        
        // Validate that persistent cells exist
        log.debug('🔍 Validating layout book...')
        const validation = await layoutBooksService.validateLayoutBook(layoutBookId)
        log.debug('Validation Complete:', validation)
        
        if (validation.cells_missing > 0) {
          log.warn('Some persistent cells are missing', {
            missing: validation.cells_missing,
            missingIds: validation.missing_cell_ids
          })
          
          const proceed = confirm(
            `${validation.cells_missing} persistent cell(s) no longer exist. Continue loading with available cells?`
          )
          
          if (!proceed) {
            this.layoutBooksLoading = false
            // Group end
            return { cancelled: true, validation }
          }
        }
        
        // CRITICAL FIX: Set loading flag BEFORE closing cells to prevent empty state persistence
        // This prevents removeCell() from calling persistLayout() and saving an empty workspace
        this._isLoadingLayout = true
        log.debug('[LayoutStore] 🔒 Loading flag set - preventing persistence during cell operations')
        
        // Close all current cells
        log.debug('[LayoutStore] 🧹 Closing all current cells')
        log.debug('Cells to close:', Array.from(this.openCells.keys()))
        const cellIds = Array.from(this.openCells.keys())
        for (const cellId of cellIds) {
          this.removeCell(cellId, true) // true = force removal (skip confirmation)
        }
        log.debug('All cells closed. Current cell count:', this.openCells.size)
        
        // Restore grid configuration
        // API returns data in `layoutBook.initial_data` (snake_case because response_model_by_alias=False)
        log.debug('🔧 Restoring grid configuration...')
        
        // Use correct field name: initial_data (snake_case from backend)
        const layoutData = layoutBook.initial_data
        
        if (!layoutData) {
          log.error('CRITICAL: Layout Book has no initial_data property')
          this.layoutBooksLoading = false
          this._isLoadingLayout = false
          throw new Error('Invalid Layout Book structure - no initial_data found')
        }
        
        log.debug('✅ Using layoutData from: layoutBook.initial_data')
        
        if (layoutData.grid_config) {
          log.debug('Grid config to restore:', layoutData.grid_config)
          Object.assign(this.gridConfig, layoutData.grid_config)
          log.debug('Grid config restored:', this.gridConfig)
        } else {
          log.warn('No grid_config found in layoutData')
        }
        
        // Restore cells
        const cells = layoutData.cells || []
        log.debug('Restoring Cells (FIXED PATH)')
        log.debug('Total cells to restore:', cells.length)
        log.debug('📦 Cells array:', JSON.stringify(cells, null, 2))
        const restoredCells = []
        const failedCells = []
        
        for (let i = 0; i < cells.length; i++) {
          const cellRef = cells[i]
          log.debug(`Restoring Cell ${i + 1}/${cells.length}`)
          log.debug('📦 cellRef:', JSON.stringify(cellRef, null, 2))
          log.debug('Cell details:', {
            category: cellRef.category,
            type: cellRef.type,
            title: cellRef.title,
            hasCellId: !!cellRef.cellId,
            hasInitializationData: !!cellRef.initialization_data,
            position: cellRef.position,
            state: cellRef.state
          })
          
          try {
            // For persistent cells, load from backend
            if (cellRef.category === 'persistent' && cellRef.cellId) {
              log.debug('PERSISTENT CELL - Using cellId:', cellRef.cellId)
              
              // Skip if cell is in missing list
              if (validation.missing_cell_ids?.includes(cellRef.cellId)) {
                log.warn('Skipping missing persistent cell', cellRef.cellId)
                failedCells.push(cellRef)
                // Group end
                continue
              }
              
              // Add cell with its saved position and state
              const cellParams = {
                cellId: cellRef.cellId,
                type: cellRef.type,
                title: cellRef.title,
                position: cellRef.position,
                state: {
                  ...cellRef.state,
                  cellInstance: {
                    id: cellRef.cellId,
                    is_persistent: true
                  }
                }
              }
              log.debug('🚀 Calling addCell with params:', JSON.stringify(cellParams, null, 2))
              const addResult = this.addCell(cellParams)
              log.debug('addCell result:', addResult)
              
              if (addResult) {
                restoredCells.push(cellRef)
                log.debug('✅ Cell restored successfully')
              } else {
                log.error('addCell returned false')
                failedCells.push(cellRef)
              }
              // Group end
            }
            // For ephemeral cells, recreate with initialization data
            else if (cellRef.category === 'ephemeral' && cellRef.initialization_data) {
              log.debug('🟢 EPHEMERAL CELL - Creating new ID')
              log.debug('📦 initialization_data:', JSON.stringify(cellRef.initialization_data, null, 2))
              
              // Generate a temporary ID for ephemeral cell
              const ephemeralId = `ephemeral-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`
              log.debug('🆔 Generated ephemeral ID:', ephemeralId)
              
              const cellParams = {
                cellId: ephemeralId,
                type: cellRef.type,
                title: cellRef.title,
                position: cellRef.position,
                state: {
                  ...cellRef.state,
                  cellInstance: {
                    id: ephemeralId,
                    is_persistent: false,
                    initial_data: cellRef.initialization_data  // ⚠️ CRITICAL
                  }
                }
              }
              log.debug('🚀 Calling addCell with params:', JSON.stringify(cellParams, null, 2))
              log.debug('State structure being passed:', {
                hasState: !!cellParams.state,
                hasCellInstance: !!cellParams.state.cellInstance,
                hasInitialData: !!cellParams.state.cellInstance.initial_data,
                initialDataKeys: cellParams.state.cellInstance.initial_data ? Object.keys(cellParams.state.cellInstance.initial_data) : []
              })
              
              const addResult = this.addCell(cellParams)
              log.debug('addCell result:', addResult)
              
              if (addResult) {
                restoredCells.push(cellRef)
                log.debug('✅ Cell restored successfully')
              } else {
                log.error('addCell returned false')
                failedCells.push(cellRef)
              }
              // Group end
            } else {
              log.warn('Cell skipped - neither persistent nor ephemeral with data:', {
                category: cellRef.category,
                hasCellId: !!cellRef.cellId,
                hasInitializationData: !!cellRef.initialization_data
              })
              failedCells.push(cellRef)
              // Group end
            }
          } catch (error) {
            log.error('❌ Error restoring cell:', error, cellRef)
            log.error('Error stack', error.stack)
            failedCells.push(cellRef)
            // Group end
          }
        }
        
        // Group end // End of "Restoring Cells" group
        
        // Reset loading flag
        this._isLoadingLayout = false
        log.debug('🔓 Loading flag cleared')
        
        // Set active layout book
        this.activeLayoutBookId = layoutBookId
        log.debug('Active layout book set:', layoutBookId)
        
        // Persist the restored layout to localStorage
        // Layout Books define the current layout state, localStorage is the snapshot
        log.debug('💾 Persisting Layout Book state to localStorage...')
        this.persistLayout()
        log.debug('✅ Layout Book state persisted to localStorage')
        
        log.debug('✅ Layout book loaded', {
          id: layoutBookId,
          restored: restoredCells.length,
          failed: failedCells.length,
          finalCellCount: this.openCells.size,
          finalGridItemsCount: this.gridLayout.length
        })
        
        log.debug('Final State Check:', {
          openCellsIds: Array.from(this.openCells.keys()),
          gridLayoutItems: this.gridLayout.map(item => ({
            cellId: item.cellId,
            type: item.type,
            position: { x: item.x, y: item.y, w: item.w, h: item.h }
          }))
        })
        
        this.addStatusMessage({
          text: `Layout book "${layoutBook.name}" loaded (${restoredCells.length} cells restored)`,
          type: 'success'
        })
        
        // Group end // End of main loadLayoutBook group
        
        return {
          success: true,
          restored: restoredCells.length,
          failed: failedCells.length,
          validation
        }
      } catch (error) {
        log.error('❌ Error loading layout book:', error)
        log.error('Error details', {
          message: error.message,
          stack: error.stack
        })
        // Group end
        this.layoutBooksError = error.message || 'Failed to load layout book'
        this.addStatusMessage({
          text: 'Failed to load layout book',
          type: 'error'
        })
        this._isLoadingLayout = false
        throw error
      } finally {
        this.layoutBooksLoading = false
      }
    },

    /**
     * Delete a layout book
     * @param {string} layoutBookId - Layout book UUID
     */
    async deleteLayoutBook(layoutBookId) {
      this.layoutBooksLoading = true
      this.layoutBooksError = null
      
      try {
        log.debug('🗑️ Deleting layout book', { id: layoutBookId })
        
        await layoutBooksService.deleteLayoutBook(layoutBookId)
        
        // Remove from local state
        this.layoutBooks = this.layoutBooks.filter(book => book.id !== layoutBookId)
        
        // Clear active if this was active
        if (this.activeLayoutBookId === layoutBookId) {
          this.activeLayoutBookId = null
        }
        
        this.addStatusMessage({
          text: 'Layout book deleted successfully',
          type: 'success'
        })
        
        log.debug('✅ Layout book deleted', { id: layoutBookId })
      } catch (error) {
        log.error('❌ Error deleting layout book:', error)
        this.layoutBooksError = error.message || 'Failed to delete layout book'
        this.addStatusMessage({
          text: 'Failed to delete layout book',
          type: 'error'
        })
        throw error
      } finally {
        this.layoutBooksLoading = false
      }
    },

    /**
     * Update a layout book
     * @param {string} layoutBookId - Layout book UUID
     * @param {Object} updates - Fields to update
     */
    async updateLayoutBook(layoutBookId, updates) {
      this.layoutBooksLoading = true
      this.layoutBooksError = null
      
      try {
        log.debug('✏️ Updating layout book', { id: layoutBookId, updates })
        
        const updatedBook = await layoutBooksService.updateLayoutBook(layoutBookId, updates)
        
        // Update in local state
        const index = this.layoutBooks.findIndex(book => book.id === layoutBookId)
        if (index !== -1) {
          this.layoutBooks[index] = {
            ...this.layoutBooks[index],
            name: updatedBook.name,
            description: updatedBook.description,
            updated_at: updatedBook.updated_at
          }
        }
        
        this.addStatusMessage({
          text: 'Layout book updated successfully',
          type: 'success'
        })
        
        log.debug('✅ Layout book updated', { id: layoutBookId })
        
        return updatedBook
      } catch (error) {
        log.error('❌ Error updating layout book:', error)
        this.layoutBooksError = error.message || 'Failed to update layout book'
        this.addStatusMessage({
          text: 'Failed to update layout book',
          type: 'error'
        })
        throw error
      } finally {
        this.layoutBooksLoading = false
      }
    }
  }
})
