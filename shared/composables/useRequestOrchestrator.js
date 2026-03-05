/**
 * Vue Composable for Request Orchestrator
 * Routes external API requests through backend proxy
 * 
 * ⚠️ FACTORY-PER-ID PATTERN:
 * This composable uses the Factory-per-ID pattern to ensure isolated request tracking
 * per cell UUID. Each cell gets its own independent request orchestrator.
 * 
 * ⚠️ BREAKING CHANGE (2026-02-08):
 * Browser extension integration has been removed. All requests now route through
 * backend proxy. This provides:
 * - Centralized credential management
 * - Better security (credentials never leave backend)
 * - Simplified architecture
 * 
 * Usage:
 * ```js
 * import { useRequestOrchestrator } from '@/composables/useRequestOrchestrator'
 * 
 * const props = defineProps({ cellId: String })
 * const { executeRequest } = useRequestOrchestrator(props.cellId)
 * 
 * const response = await executeRequest({
 *   vaultRef: 'my-openai-key',
 *   targetUrl: 'https://api.openai.com/v1/chat/completions',
 *   method: 'POST',
 *   body: { model: 'gpt-4', messages: [...] }
 * })
 * ```
 * 
 * @module composables/useRequestOrchestrator
 * @version 3.0.0 - Extension removed, backend proxy only (2026-02-08)
 */

import { ref, computed, onUnmounted } from 'vue'
import { createLogger } from '@/utils/logger'
import { getCellInstance, cleanupCellInstance } from '@/utils/CellRegistry'
import apiService from '@/services/apiService'

/**
 * Routing strategies for external API requests
 */
export const RoutingStrategy = {
  BACKEND_PROXY: 'backend_proxy',
  DIRECT: 'direct',
  FAILED: 'failed'
}

/**
 * Internal factory function to create isolated request orchestrator instance
 * 
 * @private
 * @param {string} cellUuid - Unique cell identifier
 * @returns {Object} Isolated request orchestrator instance
 */
function createRequestOrchestratorInstance(cellUuid) {
  const log = createLogger(`orchestrator:${cellUuid}`)
  
  log.debug('Creating request orchestrator instance', { cellUuid })

  // ✅ FACTORY-PER-ID: State is created PER INSTANCE (per UUID)
  // Each cell UUID gets its own isolated request tracking
  const activeRequests = ref(new Map())
  const requestHistory = ref([])
  const circuitBreakerOpen = ref(false)
  const circuitBreakerCooldownEndsAt = ref(null)

  // Extension is no longer available
  const isExtensionInstalled = ref(false)
  const extensionVersion = ref(null)

  /**
   * Determines the routing strategy for a given request
   * @param {Object} config - Request configuration
   * @returns {string} Routing strategy
   */
  const getRoutingStrategy = (config) => {
    // 1. If no credentials needed, direct backend call
    if (!config.vaultRef) {
      log.debug('Routing strategy: DIRECT (no credentials)', {
        requestId: config.requestId,
        cellUuid
      })
      return RoutingStrategy.DIRECT
    }

    // 2. All credential-based requests go through backend proxy
    log.debug('Routing strategy: BACKEND_PROXY', {
      requestId: config.requestId,
      cellUuid
    })
    return RoutingStrategy.BACKEND_PROXY
  }

  /**
   * Executes an external API request with intelligent routing
   * @param {Object} config - Request configuration
   * @param {string} config.vaultRef - Vault reference for credential (optional)
   * @param {string} config.masterPassword - Master password for decryption (optional)
   * @param {string} config.targetUrl - Target API URL
   * @param {string} config.method - HTTP method (GET, POST, etc.)
   * @param {Object} config.headers - Request headers (optional)
   * @param {Object} config.body - Request body (optional)
   * @param {number} config.timeout - Request timeout in ms (default: 30000)
   * @param {boolean} config.forceBackendRoute - Force backend proxy route (optional)
   * @returns {Promise<Object>} Orchestrated response
   */
  const executeRequest = async (config) => {
    const requestId = config.requestId || generateRequestId()
    const startTime = Date.now()

    log.info('Executing orchestrated request', {
      requestId,
      cellUuid,
      targetUrl: config.targetUrl,
      method: config.method,
      hasCredentials: !!config.vaultRef
    })

    // Determine routing strategy
    const strategy = getRoutingStrategy(config)

    // Create abort controller for cancellation
    const abortController = new AbortController()
    
    // ✅ FACTORY-PER-ID: Track request in THIS instance's Map only
    activeRequests.value.set(requestId, {
      requestId,
      cellUuid,
      strategy,
      targetUrl: config.targetUrl,
      startTime,
      abortController
    })

    try {
      let response

      // Route based on strategy
      switch (strategy) {
        case RoutingStrategy.BACKEND_PROXY:
          response = await executeViaBackendProxy({
            ...config,
            requestId,
            signal: abortController.signal
          })
          break

        case RoutingStrategy.DIRECT:
          response = await executeDirectBackend({
            ...config,
            requestId,
            signal: abortController.signal
          })
          break

        default:
          throw new Error(`Unsupported routing strategy: ${strategy}`)
      }

      // Add metadata to response
      const enhancedResponse = {
        ...response,
        requestId,
        cellUuid,
        routedVia: strategy,
        executionTimeMs: Date.now() - startTime
      }

      // Add to history
      addToHistory(enhancedResponse)

      log.info('Request completed successfully', {
        requestId,
        cellUuid,
        strategy,
        statusCode: response.statusCode,
        executionTimeMs: enhancedResponse.executionTimeMs
      })

      return enhancedResponse
    } catch (error) {
      log.error('Request failed', {
        requestId,
        cellUuid,
        strategy,
        error: error.message
      })

      // Add failed request to history
      const errorResponse = {
        requestId,
        cellUuid,
        success: false,
        error: error.message,
        routedVia: strategy,
        executionTimeMs: Date.now() - startTime
      }
      addToHistory(errorResponse)

      throw error
    } finally {
      // ✅ FACTORY-PER-ID: Remove from THIS instance's Map only
      activeRequests.value.delete(requestId)
    }
  }

  /**
   * Executes request via backend HTTP proxy
   * @private
   */
  const executeViaBackendProxy = async (config) => {
    log.debug('Executing via backend proxy', {
      requestId: config.requestId,
      cellUuid
    })

    // Check circuit breaker
    if (circuitBreakerOpen.value) {
      const cooldownRemaining = circuitBreakerCooldownEndsAt.value - Date.now()
      throw new Error(
        `Circuit breaker is open. Retry in ${Math.ceil(cooldownRemaining / 1000)}s`
      )
    }

    try {
      // Call backend proxy endpoint
      const response = await apiService.fetch('/api/proxy/external', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          vaultRef: config.vaultRef,
          masterPassword: config.masterPassword,
          targetUrl: config.targetUrl,
          method: config.method,
          headers: config.headers,
          body: config.body
        }),
        signal: config.signal
      })

      const data = await response.json()

      if (!response.ok) {
        // Record failure for circuit breaker
        recordCircuitBreakerFailure()
        
        throw new Error(data.error || `Backend proxy failed with status ${response.status}`)
      }

      // Record success for circuit breaker
      recordCircuitBreakerSuccess()

      return {
        success: true,
        statusCode: data.statusCode || response.status,
        statusText: data.statusText || response.statusText,
        headers: data.headers || {},
        body: data.body
      }
    } catch (error) {
      recordCircuitBreakerFailure()
      throw error
    }
  }

  /**
   * Executes direct backend request (no credentials)
   * @private
   */
  const executeDirectBackend = async (config) => {
    log.debug('Executing direct backend request', {
      requestId: config.requestId,
      cellUuid
    })

    const response = await apiService.fetch(config.targetUrl, {
      method: config.method,
      headers: {
        'Content-Type': 'application/json',
        ...config.headers
      },
      body: config.body ? JSON.stringify(config.body) : undefined,
      signal: config.signal
    })

    const body = await response.json()

    return {
      success: response.ok,
      statusCode: response.status,
      statusText: response.statusText,
      headers: Object.fromEntries(response.headers.entries()),
      body
    }
  }

  /**
   * Cancels an active request
   * @param {string} requestId - Request ID to cancel
   * @returns {boolean} True if cancelled
   */
  const cancelRequest = (requestId) => {
    const request = activeRequests.value.get(requestId)
    
    if (request) {
      request.abortController.abort()
      activeRequests.value.delete(requestId)
      
      log.info('Request cancelled', { requestId, cellUuid })
      return true
    }

    log.warn('Request not found for cancellation', { requestId, cellUuid })
    return false
  }

  /**
   * Circuit breaker management
   * @private
   */
  let circuitBreakerFailureCount = 0
  const CIRCUIT_BREAKER_THRESHOLD = 5
  const CIRCUIT_BREAKER_COOLDOWN_MS = 60000 // 60 seconds

  const recordCircuitBreakerSuccess = () => {
    circuitBreakerFailureCount = 0
    circuitBreakerOpen.value = false
    circuitBreakerCooldownEndsAt.value = null
    
    log.debug('Circuit breaker: success recorded, circuit closed', { cellUuid })
  }

  const recordCircuitBreakerFailure = () => {
    circuitBreakerFailureCount++
    
    if (circuitBreakerFailureCount >= CIRCUIT_BREAKER_THRESHOLD) {
      circuitBreakerOpen.value = true
      circuitBreakerCooldownEndsAt.value = Date.now() + CIRCUIT_BREAKER_COOLDOWN_MS
      
      log.warn('Circuit breaker opened', {
        cellUuid,
        failureCount: circuitBreakerFailureCount,
        cooldownEndsAt: new Date(circuitBreakerCooldownEndsAt.value).toISOString()
      })

      // Auto-reset after cooldown
      setTimeout(() => {
        circuitBreakerOpen.value = false
        circuitBreakerFailureCount = 0
        circuitBreakerCooldownEndsAt.value = null
        
        log.info('Circuit breaker automatically closed after cooldown', { cellUuid })
      }, CIRCUIT_BREAKER_COOLDOWN_MS)
    } else {
      log.debug('Circuit breaker: failure recorded', {
        cellUuid,
        count: `${circuitBreakerFailureCount}/${CIRCUIT_BREAKER_THRESHOLD}`
      })
    }
  }

  /**
   * Adds request to history (keeps last 100)
   * @private
   */
  const addToHistory = (response) => {
    requestHistory.value.unshift(response)
    
    // Keep only last 100 requests per instance
    if (requestHistory.value.length > 100) {
      requestHistory.value = requestHistory.value.slice(0, 100)
    }
  }

  /**
   * Generates a unique request ID
   * @private
   */
  const generateRequestId = () => {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }

  /**
   * Gets active requests as array
   */
  const activeRequestsList = computed(() => {
    return Array.from(activeRequests.value.values())
  })

  /**
   * Gets request history filtered by status
   */
  const getRequestHistory = (filter = 'all') => {
    if (filter === 'all') {
      return requestHistory.value
    }
    
    return requestHistory.value.filter(req => {
      if (filter === 'success') return req.success
      if (filter === 'failed') return !req.success
      return true
    })
  }

  /**
   * Cleanup function for registry
   */
  const cleanup = () => {
    log.info('Cleaning up request orchestrator instance', { cellUuid })
    
    // Cancel all active requests
    for (const [requestId, request] of activeRequests.value.entries()) {
      try {
        request.abortController.abort()
        log.debug('Aborted active request on cleanup', { requestId, cellUuid })
      } catch (error) {
        log.error('Error aborting request on cleanup', {
          requestId,
          cellUuid,
          error: error.message
        })
      }
    }
    
    // Clear state
    activeRequests.value.clear()
    requestHistory.value = []
    circuitBreakerOpen.value = false
    circuitBreakerCooldownEndsAt.value = null
    circuitBreakerFailureCount = 0
    
    log.debug('Cleanup complete', { cellUuid })
  }

  // Initialize extension check immediately
  checkExtension().then(() => {
    log.debug('Request orchestrator initialized', {
      cellUuid,
      extensionInstalled: isExtensionInstalled.value,
      extensionVersion: extensionVersion.value
    })
  })

  return {
    // Metadata
    cellUuid,
    
    // Methods
    executeRequest,
    cancelRequest,
    getRoutingStrategy,
    getRequestHistory,

    // State
    isExtensionInstalled,
    extensionVersion,
    activeRequests: activeRequestsList,
    requestHistory: computed(() => requestHistory.value),
    circuitBreakerOpen,
    circuitBreakerCooldownEndsAt,

    // Constants
    RoutingStrategy,
    
    // Lifecycle
    cleanup
  }
}

/**
 * Public API: Get or create request orchestrator instance for a specific cell UUID
 * 
 * ✅ FACTORY-PER-ID PATTERN:
 * Each cell UUID gets its own isolated request orchestrator with independent tracking.
 * This eliminates request/response cross-contamination between multiple cells.
 * 
 * @param {string} cellUuid - Unique cell identifier (required)
 * @returns {Object} Request orchestrator composable instance
 * 
 * @example
 * // In component
 * const props = defineProps({ cellId: String })
 * const orchestrator = useRequestOrchestrator(props.cellId)
 * 
 * const response = await orchestrator.executeRequest({
 *   targetUrl: 'https://api.example.com/v1/chat',
 *   method: 'POST',
 *   body: { message: 'Hello' }
 * })
 */
export function useRequestOrchestrator(cellUuid) {
  const log = createLogger('composable:useRequestOrchestrator')
  
  // Validate UUID parameter
  if (!cellUuid) {
    log.error('useRequestOrchestrator called without cellUuid', {
      stack: new Error().stack
    })
    throw new Error('cellUuid is required for useRequestOrchestrator. Pass the cell UUID as parameter.')
  }

  if (typeof cellUuid !== 'string') {
    log.error('useRequestOrchestrator called with invalid cellUuid type', {
      cellUuid,
      type: typeof cellUuid
    })
    throw new TypeError('cellUuid must be a string')
  }

  log.debug('Getting request orchestrator instance', { cellUuid })

  // Get or create isolated instance from registry
  const instance = getCellInstance(cellUuid, createRequestOrchestratorInstance)

  // Cleanup on component unmount
  onUnmounted(() => {
    log.debug('Component unmounting, scheduling cleanup', { cellUuid })
    cleanupCellInstance(cellUuid)
  })

  return instance
}
