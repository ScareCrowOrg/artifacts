/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-02",
 *   "console_calls_found": 31,
 *   "console_calls_migrated": 31,
 *   "migration_rate": 100,
 *   "logger_namespace": "factory:cell",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Vue Composable for Cell Factory Integration
 * 
 * Provides reactive interface for AI-driven cell code generation:
 * - Generation request triggering
 * - Streaming progress monitoring
 * - Completion and error handling
 * - markdown-it integration for rendering
 * 
 * ⚠️ FACTORY-PER-ID PATTERN:
 * This composable uses the Factory-per-ID pattern to ensure isolated state
 * per cell UUID. Each cell gets its own independent factory instance.
 * 
 * @module composables/useCellFactory
 * @version 2.0.0 - Migrated to Factory-per-ID pattern (2025-12-28)
 */

import { ref, computed, onUnmounted } from 'vue'
import MarkdownIt from 'markdown-it'
import { getCellInstance, cleanupCellInstance } from '@/utils/CellRegistry'
import { createLogger } from '@/utils/logger'
import authService from '@/services/authService'

/**
 * Cell Factory states
 */
export const GenerationState = {
  IDLE: 'idle',
  GENERATING: 'generating',
  VALIDATING: 'validating',
  COMPLETED: 'completed',
  ERROR: 'error'
}

/**
 * Internal factory function to create isolated cell factory instance
 * 
 * This function creates a completely isolated state instance for a specific cell UUID.
 * It's called by getCellInstance() from CellRegistry to ensure per-UUID isolation.
 * 
 * @private
 * @param {string} cellUuid - Unique cell identifier
 * @returns {Object} Isolated cell factory instance
 */
function createCellFactoryInstance(cellUuid) {
  const log = createLogger(`factory:${cellUuid}`)
  
  log.debug('Creating cell factory instance', { cellUuid })

  // ✅ FACTORY-PER-ID: State is created PER INSTANCE (per UUID)
  // Each cell UUID gets its own isolated reactive state
  const generationState = ref(GenerationState.IDLE)
  const currentCellId = ref(cellUuid) // Initialize with the UUID
  const currentRequestId = ref(null)
  const streamingContent = ref('')
  const generatedRefs = ref([])
  const progressPercentage = ref(0)
  const errorMessage = ref(null)
  const isProcessing = ref(false)

  log.debug('Initial state created', {
    cellUuid,
    generationState: generationState.value,
    isIdle: generationState.value === GenerationState.IDLE
  })

  // Markdown renderer (created per instance)
  const md = new MarkdownIt({
    html: false,
    linkify: true,
    typographer: true,
    breaks: true
  })

  // Message listener
  let messageListener = null

  /**
   * Render markdown content to HTML
   * @param {string} content - Markdown content
   * @returns {string} Rendered HTML
   */
  const renderMarkdown = (content) => {
    try {
      return md.render(content || '')
    } catch (error) {
      log.error('Markdown rendering error', { error: error.message })
      return content || ''
    }
  }

  /**
   * Request cell code generation
   * @param {string} cellId - Cell ID
   * @param {string} content - User prompt/content
   * @param {string} format - Desired output format (svg, vue, js, python, auto)
   * @param {Object} options - Additional options
   * @returns {Promise<Object>} Generation request result
   */
  const generateCellCode = async (cellId, content, format = 'auto', options = {}) => {
    log.debug('generateCellCode called', {
      cellIdParam: cellId,
      cellUuidInstance: cellUuid,
      contentLength: content?.length,
      format,
      options,
      stateBefore: generationState.value
    })
    
    log.info('Requesting code generation', {
      cellId,
      cellUuid,
      format,
      contentLength: content?.length
    })

    // Verify cellId matches our UUID (defensive check)
    if (cellId !== cellUuid) {
      log.warn('CellId mismatch - using instance UUID', {
        providedCellId: cellId,
        instanceCellUuid: cellUuid,
        willUse: cellUuid
      })
    }

    // Reset state for new generation
    log.debug('Setting state to GENERATING')
    generationState.value = GenerationState.GENERATING
    streamingContent.value = ''
    generatedRefs.value = []
    progressPercentage.value = 0
    errorMessage.value = null
    isProcessing.value = true
    
    log.debug('State after reset', {
      generationState: generationState.value,
      isProcessing: isProcessing.value,
      isGenerating: generationState.value === GenerationState.GENERATING
    })

    try {
      // Generate unique request ID
      currentRequestId.value = `req-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`
      log.debug('Generated request ID', { requestId: currentRequestId.value })

      // Build payload
      const payload = {
        cell_id: cellUuid, // Use instance UUID instead of parameter
        content,
        format,
        model: options.model || 'mistral',
        conversation_id: options.conversationId,
        use_rag: options.useRag || false
      }
      
      log.debug('Calling sendToBackend with payload', {
        ...payload,
        content: payload.content ? `<${payload.content.length} chars>` : null
      })

      // Send generation request to backend via extension
      const response = await sendToBackend('generate_cell_code', payload)

      log.debug('sendToBackend resolved successfully')
      log.info('Generation request sent', { response, requestId: currentRequestId.value })

      return {
        success: true,
        requestId: currentRequestId.value,
        cellId: cellUuid
      }
    } catch (error) {
      log.error('generateCellCode failed', {
        error: error.message,
        errorStack: error.stack,
        settingStateToError: true
      })
      
      generationState.value = GenerationState.ERROR
      errorMessage.value = error.message || 'Failed to start generation'
      isProcessing.value = false

      return {
        success: false,
        error: error.message
      }
    }
  }

  /**
   * Handle streaming progress events
   * @param {Object} payload - Progress event payload
   */
  const handleProgressEvent = (payload) => {
    const { request_id, chunk, type, progress } = payload

    // ✅ FACTORY-PER-ID: Only process events for THIS instance's request
    if (request_id !== currentRequestId.value) {
      log.debug('Progress event for different request, ignoring', {
        receivedRequestId: request_id,
        expectedRequestId: currentRequestId.value
      })
      return
    }

    log.debug('Progress event received', {
      type,
      chunkLength: chunk?.content?.length,
      progress
    })

    // Update state
    generationState.value = GenerationState.GENERATING
    
    // Update progress percentage
    if (progress !== undefined) {
      progressPercentage.value = Math.min(100, Math.max(0, progress))
    }

    // Append chunk to streaming content
    if (chunk) {
      if (chunk.type === 'narrative') {
        // Narrative chunk - add to streaming content
        streamingContent.value += chunk.content || ''
      } else if (chunk.type === 'code') {
        // Code chunk - will be extracted to OPFS by orchestrator
        // Just show indication in narrative
        const codeIndicator = `\n\`\`\`${chunk.fence || ''}\n${chunk.content || ''}\n\`\`\`\n`
        streamingContent.value += codeIndicator
      }
    }
  }

  /**
   * Handle generation completion events
   * @param {Object} payload - Completion event payload
   */
  const handleCompletionEvent = (payload) => {
    const { request_id, cell_id, refs, metadata } = payload

    // ✅ FACTORY-PER-ID: Only process events for THIS instance's request
    if (request_id !== currentRequestId.value) {
      log.debug('Completion event for different request, ignoring', {
        receivedRequestId: request_id,
        expectedRequestId: currentRequestId.value
      })
      return
    }

    log.info('Completion event received', {
      cellId: cell_id,
      cellUuid,
      refsCount: refs?.length
    })

    // Update state
    generationState.value = GenerationState.COMPLETED
    generatedRefs.value = refs || []
    progressPercentage.value = 100
    isProcessing.value = false

    log.info('Generation completed successfully', { cellUuid })
  }

  /**
   * Handle generation error events
   * @param {Object} payload - Error event payload
   */
  const handleErrorEvent = (payload) => {
    const { request_id, error, message } = payload

    // ✅ FACTORY-PER-ID: Only process events for THIS instance's request
    if (request_id !== currentRequestId.value) {
      log.debug('Error event for different request, ignoring', {
        receivedRequestId: request_id,
        expectedRequestId: currentRequestId.value
      })
      return
    }

    log.error('Error event received', {
      error,
      message,
      cellUuid
    })

    // Update state
    generationState.value = GenerationState.ERROR
    errorMessage.value = message || error || 'Generation failed'
    isProcessing.value = false
  }

  /**
   * Handle messages from extension/offscreen
   * @param {MessageEvent} event - Message event
   */
  const handleMessage = (event) => {
    // Validate origin
    if (event.origin !== window.location.origin) {
      return
    }

    const message = event.data

    // Validate message structure
    if (!message || message.source !== 'scareverse-extension') {
      return
    }

    log.debug('Message received', { topic: message.topic, cellUuid })

    // Route to appropriate handler
    switch (message.topic) {
      case 'cell/generate/progress':
        handleProgressEvent(message.payload)
        break

      case 'cell/generate/complete':
        handleCompletionEvent(message.payload)
        break

      case 'cell/generate/error':
        handleErrorEvent(message.payload)
        break

      default:
        // Ignore other topics
        break
    }
  }

  /**
   * Send message to backend via extension
   * @param {string} endpoint - API endpoint
   * @param {Object} payload - Request payload
   * @returns {Promise<Object>} Response
   */
  const sendToBackend = async (endpoint, payload) => {
    return new Promise((resolve, reject) => {
      const requestId = `backend-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`
      
      // Get JWT token from authService for authentication
      // This uses the proper abstraction with expiry validation
      const token = authService.getToken()
      
      log.debug('sendToBackend initiating', {
        requestId,
        endpoint,
        payload,
        hasToken: !!token,
        origin: window.location.origin,
        timestamp: new Date().toISOString()
      })
      
      if (!token) {
        log.warn('No authentication token available from authService', { requestId })
        // Don't reject - let the backend handle the authentication error
      }
      
      const timeout = setTimeout(() => {
        log.error('Backend request timeout', { requestId, timeoutMs: 30000 })
        reject(new Error('Backend request timeout'))
      }, 30000)

      // Listen for response
      const responseHandler = (event) => {
        if (event.data?.requestId === requestId) {
          log.debug('Response received', {
            requestId,
            success: event.data.success,
            eventData: event.data,
            timestamp: new Date().toISOString()
          })
          
          clearTimeout(timeout)
          window.removeEventListener('message', responseHandler)

          if (event.data.success) {
            log.debug('Request succeeded, resolving promise', { requestId })
            resolve(event.data.data)
          } else {
            const errorMsg = event.data.error || 'Backend request failed'
            log.error('Request failed', {
              requestId,
              error: event.data.error,
              data: event.data.data,
              statusCode: event.data.statusCode,
              fullResponse: event.data
            })
            reject(new Error(errorMsg))
          }
        }
      }

      window.addEventListener('message', responseHandler)

      const messagePayload = {
        source: 'scareverse-cockpit',
        type: 'backend_request',
        requestId,
        endpoint,
        payload,
        token // Include JWT token for authentication
      }
      log.debug('Sending postMessage', {
        messagePayload: {
          ...messagePayload,
          token: token ? '***' : null // Hide token in logs
        },
        origin: window.location.origin
      })
      
      // Send request
      window.postMessage(messagePayload, window.location.origin)
      
      log.debug('postMessage sent, awaiting response', { requestId })
    })
  }

  /**
   * Reset generation state
   */
  const resetGeneration = () => {
    log.debug('Resetting generation state', { cellUuid })

    generationState.value = GenerationState.IDLE
    currentRequestId.value = null
    streamingContent.value = ''
    generatedRefs.value = []
    progressPercentage.value = 0
    errorMessage.value = null
    isProcessing.value = false

    log.debug('Reset complete', { cellUuid })
  }

  /**
   * Cancel current generation
   */
  const cancelGeneration = async () => {
    if (!currentRequestId.value) {
      log.debug('No active generation to cancel', { cellUuid })
      return
    }

    log.info('Canceling generation', {
      requestId: currentRequestId.value,
      cellUuid
    })

    try {
      await sendToBackend('cancel_generation', {
        request_id: currentRequestId.value
      })

      resetGeneration()
    } catch (error) {
      log.error('Failed to cancel generation', { error: error.message, cellUuid })
    }
  }

  /**
   * Setup message listener (per instance)
   */
  const setupMessageListener = () => {
    if (!messageListener) {
      messageListener = handleMessage
      window.addEventListener('message', messageListener)
      log.debug('Message listener registered', { cellUuid })
    }
  }

  /**
   * Cleanup message listener
   */
  const cleanupMessageListener = () => {
    if (messageListener) {
      window.removeEventListener('message', messageListener)
      messageListener = null
      log.debug('Message listener cleaned up', { cellUuid })
    }
  }

  /**
   * Cleanup function for registry
   * Called automatically when instance is removed from registry
   */
  const cleanup = () => {
    log.info('Cleaning up cell factory instance', { cellUuid })
    
    cleanupMessageListener()
    resetGeneration()
    
    log.debug('Cleanup complete', { cellUuid })
  }

  // Setup message listener immediately
  setupMessageListener()

  // Computed properties
  const renderedContent = computed(() => {
    return renderMarkdown(streamingContent.value)
  })

  const isGenerating = computed(() => {
    const result = generationState.value === GenerationState.GENERATING
    if (import.meta.env.DEV) {
      log.debug('isGenerating computed evaluation', {
        generationState: generationState.value,
        isGenerating: result
      })
    }
    return result
  })

  const isCompleted = computed(() => {
    return generationState.value === GenerationState.COMPLETED
  })

  const hasError = computed(() => {
    return generationState.value === GenerationState.ERROR
  })

  const hasGeneratedCode = computed(() => {
    return generatedRefs.value.length > 0
  })

  // Return isolated instance interface
  return {
    // Metadata
    cellUuid,
    
    // State
    generationState,
    currentCellId,
    currentRequestId,
    streamingContent,
    generatedRefs,
    progressPercentage,
    errorMessage,
    isProcessing,

    // Computed
    renderedContent,
    isGenerating,
    isCompleted,
    hasError,
    hasGeneratedCode,

    // Methods
    generateCellCode,
    resetGeneration,
    cancelGeneration,
    renderMarkdown,
    
    // Lifecycle
    cleanup
  }
}

/**
 * Public API: Get or create cell factory instance for a specific cell UUID
 * 
 * ✅ FACTORY-PER-ID PATTERN:
 * Each cell UUID gets its own isolated factory instance with independent state.
 * This eliminates race conditions and state pollution between multiple cells.
 * 
 * @param {string} cellUuid - Unique cell identifier (required)
 * @returns {Object} Cell factory composable instance
 * 
 * @example
 * // In component
 * const props = defineProps({ cellId: String })
 * const factory = useCellFactory(props.cellId)
 * 
 * // Multiple cells = multiple isolated instances
 * const factory1 = useCellFactory('uuid-1') // Instance 1
 * const factory2 = useCellFactory('uuid-2') // Instance 2 (isolated)
 */
export function useCellFactory(cellUuid) {
  const log = createLogger('composable:useCellFactory')
  
  // Validate UUID parameter
  if (!cellUuid) {
    log.error('useCellFactory called without cellUuid', {
      stack: new Error().stack
    })
    throw new Error('cellUuid is required for useCellFactory. Pass the cell UUID as parameter.')
  }

  if (typeof cellUuid !== 'string') {
    log.error('useCellFactory called with invalid cellUuid type', {
      cellUuid,
      type: typeof cellUuid
    })
    throw new TypeError('cellUuid must be a string')
  }

  log.debug('Getting cell factory instance', { cellUuid })

  // Get or create isolated instance from registry
  const instance = getCellInstance(cellUuid, createCellFactoryInstance)

  // Cleanup on component unmount
  onUnmounted(() => {
    log.debug('Component unmounting, scheduling cleanup', { cellUuid })
    cleanupCellInstance(cellUuid)
  })

  return instance
}
