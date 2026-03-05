/**
 * Vue Composable for Cell Transmutation Integration
 * 
 * Provides reactive interface for the Recursive Transmutation Engine:
 * - Subscribe to cell/transmuted events from WASM Orchestrator
 * - Handle transmutation state transitions
 * - Manage Book navigation and display
 * - Integrate with existing cell management
 * 
 * ⚠️ INTENTIONAL SINGLETON PATTERN (Issue #1400)
 * 
 * This composable intentionally uses module-level state for global transmutation tracking.
 * It maintains a single Chrome extension event listener and tracks Book data across ALL cells.
 * 
 * Pattern: Global event listener + Map<cellId, bookData> for per-cell tracking
 * 
 * DO NOT migrate to Factory-per-ID pattern - this is architectural by design.
 * 
 * @module composables/useTransmutation
 * @version 1.0.0
 */

import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useCellsStore } from '../stores/cells.js'
import { createLogger } from '../utils/logger.js'

const log = createLogger('composable:useTransmutation')

/**
 * Transmutation states
 */
export const TransmutationState = {
  IDLE: 'idle',
  PLANNING: 'planning',
  TRANSMUTING: 'transmuting',
  COMPLETED: 'completed',
  ERROR: 'error'
}

/**
 * Event topic constants (must match WASM Orchestrator)
 */
const EventTopics = {
  CELL_TRANSMUTE_PLAN: 'cell/transmute/plan',
  CELL_TRANSMUTED: 'cell/transmuted'
}

/**
 * Transmutation composable for managing cell → book transformations
 * @returns {Object} Transmutation interface
 */
export function useTransmutation() {
  const cellsStore = useCellsStore()

  // State
  const transmutationState = ref(TransmutationState.IDLE)
  const currentCellId = ref(null)
  const transmutationProgress = ref(0)
  const errorMessage = ref(null)
  const activeBooks = ref(new Map()) // cellId -> Book data
  
  // Animation state
  const isAnimating = ref(false)
  const animatingCellId = ref(null)

  // Message listener reference
  let messageListener = null

  /**
   * Subscribe to transmutation events from chrome runtime
   * Handles both direct messages and Event Bus wrapped messages
   * @private
   */
  function setupEventListeners() {
    messageListener = (message, sender, sendResponse) => {
      try {
        // Handle Event Bus wrapped messages (from WASM Orchestrator)
        if (message.type === 'EVENT_BUS_MESSAGE') {
          const event = message.message
          
          if (event.topic === EventTopics.CELL_TRANSMUTE_PLAN) {
            handleTransmutePlan(event.payload)
            sendResponse({ success: true })
            return true
          }
          
          if (event.topic === EventTopics.CELL_TRANSMUTED) {
            handleTransmuted(event.payload)
            sendResponse({ success: true })
            return true
          }
        }
        
        // Handle direct topic messages (backward compatibility)
        if (message.topic === EventTopics.CELL_TRANSMUTE_PLAN) {
          handleTransmutePlan(message.payload)
          sendResponse({ success: true })
          return true
        }
        
        if (message.topic === EventTopics.CELL_TRANSMUTED) {
          handleTransmuted(message.payload)
          sendResponse({ success: true })
          return true
        }
      } catch (error) {
        log.error('Error handling transmutation event:', error)
        sendResponse({ success: false, error: error.message })
      }
      
      return false
    }

    if (typeof chrome !== 'undefined' && chrome.runtime?.onMessage) {
      chrome.runtime.onMessage.addListener(messageListener)
      log.info('Subscribed to transmutation events')
    } else {
      log.warn('Chrome runtime not available, transmutation events disabled')
    }
  }

  /**
   * Handle transmutation plan event (Phase 1: Planning)
   * @param {Object} payload - Plan payload
   * @param {string} payload.cell_id - Cell being planned for transmutation
   * @param {Object} payload.action_plan - ActionPlan with complexity evaluation
   * @param {string} payload.reasoning - Why this cell needs transmutation
   * @private
   */
  function handleTransmutePlan(payload) {
    const { cell_id, action_plan, reasoning } = payload
    
    log.info('Transmutation plan received:', {
      cell_id,
      complexity: action_plan?.complexity,
      reasoning
    })

    transmutationState.value = TransmutationState.PLANNING
    currentCellId.value = cell_id
    transmutationProgress.value = 10 // 10% for planning complete
    errorMessage.value = null

    // Update cell state in store to show planning status
    cellsStore.updateCellMetadata(cell_id, {
      transmuting: true,
      transmutationState: 'planning',
      actionPlan: action_plan
    })
  }

  /**
   * Handle transmutation complete event (Phase 2: Transmuted)
   * @param {Object} payload - Transmutation result
   * @param {string} payload.cell_id - Original cell ID
   * @param {string} payload.book_id - New Book ID
   * @param {Array<string>} payload.new_cell_ids - Sub-cell IDs within the Book
   * @param {string} payload.reasoning - Transmutation reasoning
   * @param {string} payload.timestamp - Completion timestamp
   * @private
   */
  function handleTransmuted(payload) {
    const { cell_id, book_id, new_cell_ids, reasoning, timestamp } = payload
    
    log.info('Cell transmuted successfully:', {
      cell_id,
      book_id,
      sub_cells: new_cell_ids?.length || 0,
      reasoning
    })

    // Start animation
    isAnimating.value = true
    animatingCellId.value = cell_id
    transmutationState.value = TransmutationState.TRANSMUTING
    transmutationProgress.value = 50

    // Store Book data
    const bookData = {
      id: book_id,
      originalCellId: cell_id,
      subCellIds: new_cell_ids || [],
      reasoning,
      timestamp,
      expanded: false // Initially collapsed
    }
    
    activeBooks.value.set(cell_id, bookData)

    // Simulate smooth animation progression
    setTimeout(() => {
      transmutationProgress.value = 75
    }, 300)

    setTimeout(() => {
      transmutationProgress.value = 100
      transmutationState.value = TransmutationState.COMPLETED
      
      // Update cell to show it's now a Book
      cellsStore.updateCellMetadata(cell_id, {
        transmuted: true,
        bookId: book_id,
        subCellIds: new_cell_ids,
        transmutationState: 'completed'
      })
      
      // End animation after transition completes
      setTimeout(() => {
        isAnimating.value = false
        animatingCellId.value = null
      }, 500)
    }, 600)
  }

  /**
   * Get Book data for a transmuted cell
   * @param {string} cellId - Original cell ID
   * @returns {Object|null} Book data or null if not transmuted
   */
  function getBook(cellId) {
    return activeBooks.value.get(cellId) || null
  }

  /**
   * Check if a cell has been transmuted to a Book
   * @param {string} cellId - Cell ID to check
   * @returns {boolean} True if cell is now a Book
   */
  function isTransmuted(cellId) {
    return activeBooks.value.has(cellId)
  }

  /**
   * Toggle Book expansion state
   * @param {string} cellId - Original cell ID
   */
  function toggleBookExpansion(cellId) {
    const book = activeBooks.value.get(cellId)
    if (book) {
      book.expanded = !book.expanded
      log.debug(`Book ${book.id} ${book.expanded ? 'expanded' : 'collapsed'}`)
    }
  }

  /**
   * Navigate to a sub-cell within a Book
   * @param {string} bookId - Book ID
   * @param {string} subCellId - Sub-cell ID to navigate to
   */
  function navigateToSubCell(bookId, subCellId) {
    log.info('Navigating to sub-cell:', { bookId, subCellId })
    
    // Trigger cell view for the sub-cell
    cellsStore.setActiveCell(subCellId)
  }

  /**
   * Clear transmutation error
   */
  function clearError() {
    errorMessage.value = null
  }

  /**
   * Reset transmutation state
   */
  function reset() {
    transmutationState.value = TransmutationState.IDLE
    currentCellId.value = null
    transmutationProgress.value = 0
    errorMessage.value = null
    isAnimating.value = false
    animatingCellId.value = null
  }

  // Computed properties
  const isTransmuting = computed(() => 
    transmutationState.value === TransmutationState.TRANSMUTING ||
    transmutationState.value === TransmutationState.PLANNING
  )

  const hasError = computed(() => 
    transmutationState.value === TransmutationState.ERROR
  )

  const isCompleted = computed(() => 
    transmutationState.value === TransmutationState.COMPLETED
  )

  // Lifecycle hooks
  onMounted(() => {
    setupEventListeners()
  })

  onUnmounted(() => {
    if (messageListener && typeof chrome !== 'undefined' && chrome.runtime?.onMessage) {
      chrome.runtime.onMessage.removeListener(messageListener)
      log.info('Unsubscribed from transmutation events')
    }
  })

  return {
    // State
    transmutationState,
    currentCellId,
    transmutationProgress,
    errorMessage,
    activeBooks: computed(() => Array.from(activeBooks.value.values())),
    
    // Animation state
    isAnimating,
    animatingCellId,
    
    // Computed
    isTransmuting,
    hasError,
    isCompleted,
    
    // Methods
    getBook,
    isTransmuted,
    toggleBookExpansion,
    navigateToSubCell,
    clearError,
    reset
  }
}
