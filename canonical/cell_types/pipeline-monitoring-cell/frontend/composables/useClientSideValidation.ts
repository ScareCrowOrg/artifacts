/**
 * useClientSideValidation Composable
 * 
 * Client-side validation for prerequisites that cannot be validated server-side.
 * Validates Frontend composables, Extension status, WASM components, and Browser APIs.
 * 
 * Sprint 4: Client-Side Validation Implementation
 * 
 * @module composables/useClientSideValidation
 */

import { ref, type Ref } from 'vue'
import { createLogger } from '@/utils/logger'

const log = createLogger('composable:useClientSideValidation')

/**
 * Validation result for a client-side prerequisite
 */
export interface ClientValidationResult {
  id: string
  name: string
  category: string
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
  criticality: 'critical' | 'high' | 'medium' | 'low'
  validation_method: string
  monitoring_available: boolean
  details: Record<string, any>
  timestamp: number
}

// Shared state
const validationResults: Ref<ClientValidationResult[]> = ref([])
const isValidating: Ref<boolean> = ref(false)
const lastError: Ref<string | null> = ref(null)

/**
 * useClientSideValidation Composable
 * 
 * Provides client-side validation for browser-specific prerequisites
 */
export function useClientSideValidation() {
  /**
   * Validate all client-side prerequisites
   */
  async function validateAll(): Promise<ClientValidationResult[]> {
    if (isValidating.value) {
      log.debug('Validation already in progress, returning cached results', {
        cachedCount: validationResults.value.length
      })
      return validationResults.value
    }
    
    isValidating.value = true
    lastError.value = null
    
    try {
      log.info('Starting client-side validation')
      
      const results: ClientValidationResult[] = []
      
      // Frontend Prerequisites
      results.push(await validateUseCellFactory())
      results.push(await validateUseExtension())
      results.push(await validateCellRegistry())
      
      // Browser API Prerequisites
      results.push(await validateBrowserAPIs())
      
      // Extension Prerequisites (if extension available)
      const extensionResults = await validateExtension()
      results.push(...extensionResults)
      
      validationResults.value = results
      log.info('Client-side validation complete', { count: results.length })
      
      return results
      
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      lastError.value = errorMessage
      log.error('Client-side validation failed', { error: errorMessage })
      return []
    } finally {
      isValidating.value = false
    }
  }
  
  /**
   * Validate useCellFactory composable
   */
  async function validateUseCellFactory(): Promise<ClientValidationResult> {
    try {
      // Try to import the composable
      const { useCellFactory } = await import('@/composables/useCellFactory.js')
      
      if (typeof useCellFactory === 'function') {
        return {
          id: 'frontend.use_cell_factory',
          name: 'useCellFactory Composable',
          category: 'frontend',
          status: 'healthy',
          criticality: 'critical',
          validation_method: 'import_and_type_check',
          monitoring_available: true,
          details: {
            available: true,
            type: 'function',
            location: '@/composables/useCellFactory.js'
          },
          timestamp: Date.now()
        }
      }
      
      return {
        id: 'frontend.use_cell_factory',
        name: 'useCellFactory Composable',
        category: 'frontend',
        status: 'unhealthy',
        criticality: 'critical',
        validation_method: 'import_and_type_check',
        monitoring_available: true,
        details: {
          available: false,
          issue: 'Imported but not a function'
        },
        timestamp: Date.now()
      }
      
    } catch (error) {
      return {
        id: 'frontend.use_cell_factory',
        name: 'useCellFactory Composable',
        category: 'frontend',
        status: 'unhealthy',
        criticality: 'critical',
        validation_method: 'import_check',
        monitoring_available: false,
        details: {
          available: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        },
        timestamp: Date.now()
      }
    }
  }
  
  /**
   * Validate useExtension composable
   * 
   * ⚠️ DEPRECATED: Extension infrastructure removed (2026-02-08)
   * This validation always returns unavailable status.
   */
  async function validateUseExtension(): Promise<ClientValidationResult> {
    // Extension has been removed - return unavailable status
    return {
      id: 'frontend.use_extension',
      name: 'useExtension Composable',
      category: 'frontend',
      status: 'unhealthy',
      criticality: 'low', // Reduced from critical since extension is no longer required
      validation_method: 'static_check',
      monitoring_available: false,
      details: {
        available: false,
        issue: 'Browser extension infrastructure removed from project (2026-02-08)',
        migration: 'Use backend APIs for credential management and external requests'
      },
      timestamp: Date.now()
    }
  }
  
  /**
   * Validate CellRegistry
   */
  async function validateCellRegistry(): Promise<ClientValidationResult> {
    try {
      // Try to import CellRegistry
      const CellRegistry = await import('@/utils/CellRegistry.js')
      
      if (CellRegistry && typeof CellRegistry.getCellInstance === 'function') {
        return {
          id: 'frontend.cell_registry',
          name: 'CellRegistry State',
          category: 'frontend',
          status: 'healthy',
          criticality: 'high',
          validation_method: 'import_and_method_check',
          monitoring_available: true,
          details: {
            available: true,
            methods: ['getCellInstance', 'cleanupCellInstance'],
            location: '@/utils/CellRegistry.js'
          },
          timestamp: Date.now()
        }
      }
      
      return {
        id: 'frontend.cell_registry',
        name: 'CellRegistry State',
        category: 'frontend',
        status: 'unhealthy',
        criticality: 'high',
        validation_method: 'import_and_method_check',
        monitoring_available: true,
        details: {
          available: false,
          issue: 'CellRegistry imported but methods missing'
        },
        timestamp: Date.now()
      }
      
    } catch (error) {
      return {
        id: 'frontend.cell_registry',
        name: 'CellRegistry State',
        category: 'frontend',
        status: 'unhealthy',
        criticality: 'high',
        validation_method: 'import_check',
        monitoring_available: false,
        details: {
          available: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        },
        timestamp: Date.now()
      }
    }
  }
  
  /**
   * Validate Browser API support
   */
  async function validateBrowserAPIs(): Promise<ClientValidationResult> {
    const apis = {
      opfs: 'getDirectory' in (navigator.storage || {}),
      webassembly: typeof WebAssembly !== 'undefined',
      indexeddb: 'indexedDB' in window,
      serviceworker: 'serviceWorker' in navigator,
      crypto: 'crypto' in window && 'subtle' in window.crypto
    }
    
    const allSupported = Object.values(apis).every(Boolean)
    const someSupported = Object.values(apis).some(Boolean)
    
    let status: 'healthy' | 'degraded' | 'unhealthy' = 'unhealthy'
    if (allSupported) {
      status = 'healthy'
    } else if (someSupported) {
      status = 'degraded'
    }
    
    const missing = Object.entries(apis)
      .filter(([, supported]) => !supported)
      .map(([api]) => api)
    
    return {
      id: 'runtime.browser_apis',
      name: 'Browser API Support',
      category: 'runtime',
      status,
      criticality: 'high',
      validation_method: 'feature_detection',
      monitoring_available: true,
      details: {
        apis,
        missing,
        browser: navigator.userAgent,
        all_supported: allSupported
      },
      timestamp: Date.now()
    }
  }
  
  /**
   * Validate browser extension status
   */
  async function validateExtension(): Promise<ClientValidationResult[]> {
    const results: ClientValidationResult[] = []
    
    try {
      // Check if extension communication is possible
      const extensionInstalled = await checkExtensionInstalled()
      
      results.push({
        id: 'extension.installed',
        name: 'Extension Installed',
        category: 'extension',
        status: extensionInstalled ? 'healthy' : 'unhealthy',
        criticality: 'critical',
        validation_method: 'postmessage_ping',
        monitoring_available: true,
        details: {
          installed: extensionInstalled,
          method: 'window.postMessage ping/pong'
        },
        timestamp: Date.now()
      })
      
      if (extensionInstalled) {
        // Get detailed extension status
        const extensionStatus = await getExtensionStatus()
        
        results.push({
          id: 'extension.service_worker',
          name: 'Service Worker Active',
          category: 'extension',
          status: extensionStatus.serviceWorkerActive ? 'healthy' : 'unhealthy',
          criticality: 'critical',
          validation_method: 'extension_status_query',
          monitoring_available: true,
          details: extensionStatus.serviceWorker || {},
          timestamp: Date.now()
        })
        
        results.push({
          id: 'extension.post_message',
          name: 'postMessage Communication',
          category: 'extension',
          status: 'healthy', // If we got here, communication works
          criticality: 'critical',
          validation_method: 'postmessage_test',
          monitoring_available: true,
          details: {
            latency_ms: extensionStatus.latency || 0,
            working: true
          },
          timestamp: Date.now()
        })
        
        // WASM/OPFS checks if extension provides them
        if (extensionStatus.opfsAvailable !== undefined) {
          results.push({
            id: 'wasm.opfs',
            name: 'OPFS Service Available',
            category: 'wasm',
            status: extensionStatus.opfsAvailable ? 'healthy' : 'unhealthy',
            criticality: 'high',
            validation_method: 'extension_opfs_check',
            monitoring_available: true,
            details: {
              available: extensionStatus.opfsAvailable,
              quota_info: extensionStatus.opfsQuota || {}
            },
            timestamp: Date.now()
          })
        }
      } else {
        // Extension not installed - mark all extension prerequisites as unhealthy
        results.push({
          id: 'extension.service_worker',
          name: 'Service Worker Active',
          category: 'extension',
          status: 'unhealthy',
          criticality: 'critical',
          validation_method: 'extension_not_available',
          monitoring_available: false,
          details: {
            reason: 'Extension not installed or not responding'
          },
          timestamp: Date.now()
        })
        
        results.push({
          id: 'extension.post_message',
          name: 'postMessage Communication',
          category: 'extension',
          status: 'unhealthy',
          criticality: 'critical',
          validation_method: 'extension_not_available',
          monitoring_available: false,
          details: {
            reason: 'Extension not installed or not responding'
          },
          timestamp: Date.now()
        })
      }
      
    } catch (error) {
      log.error('Extension validation failed', { error })
      
      results.push({
        id: 'extension.installed',
        name: 'Extension Installed',
        category: 'extension',
        status: 'unknown',
        criticality: 'critical',
        validation_method: 'error',
        monitoring_available: false,
        details: {
          error: error instanceof Error ? error.message : 'Unknown error'
        },
        timestamp: Date.now()
      })
    }
    
    return results
  }
  
  /**
   * Check if browser extension is installed and responding
   */
  async function checkExtensionInstalled(): Promise<boolean> {
    return new Promise((resolve) => {
      const timeout = setTimeout(() => {
        window.removeEventListener('message', messageHandler)
        resolve(false)
      }, 1000) // 1 second timeout
      
      const messageHandler = (event: MessageEvent) => {
        if (event.source !== window) return
        
        if (event.data?.source === 'scareverse-extension' && event.data?.type === 'PONG') {
          clearTimeout(timeout)
          window.removeEventListener('message', messageHandler)
          resolve(true)
        }
      }
      
      window.addEventListener('message', messageHandler)
      
      // Send ping
      window.postMessage({
        source: 'scareverse-wasm',
        type: 'PING',
        timestamp: Date.now()
      }, window.location.origin)
    })
  }
  
  /**
   * Get detailed status from extension
   */
  async function getExtensionStatus(): Promise<any> {
    return new Promise((resolve) => {
      const timeout = setTimeout(() => {
        window.removeEventListener('message', messageHandler)
        resolve({
          serviceWorkerActive: false,
          latency: null
        })
      }, 2000) // 2 second timeout
      
      const startTime = performance.now()
      
      const messageHandler = (event: MessageEvent) => {
        if (event.source !== window) return
        
        if (event.data?.source === 'scareverse-extension' && event.data?.type === 'STATUS_RESPONSE') {
          clearTimeout(timeout)
          window.removeEventListener('message', messageHandler)
          
          const latency = performance.now() - startTime
          
          resolve({
            ...event.data.payload,
            latency
          })
        }
      }
      
      window.addEventListener('message', messageHandler)
      
      // Request status
      window.postMessage({
        source: 'scareverse-wasm',
        type: 'GET_STATUS',
        timestamp: Date.now()
      }, window.location.origin)
    })
  }
  
  return {
    // State
    validationResults,
    isValidating,
    lastError,
    
    // Methods
    validateAll,
    validateUseCellFactory,
    validateUseExtension,
    validateCellRegistry,
    validateBrowserAPIs,
    validateExtension
  }
}
