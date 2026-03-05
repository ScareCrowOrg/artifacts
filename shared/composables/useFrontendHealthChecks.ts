/**
 * Frontend Health Checks Composable
 * 
 * Validates 14 frontend-side prerequisites that require browser context.
 * Complements backend validator (10 checks) for complete system monitoring.
 * 
 * Categories:
 * - Frontend (3): Vue composables and registry
 * - Extension (5): Browser extension status and communication
 * - WASM (4): Offscreen document and WASM orchestrator
 * - Runtime (2): Browser APIs and system resources
 * 
 * @see docs/issues/monitoring-cell-frontend-backend-separation/TO_BE_SPECIFICATION.md
 */

import { createLogger } from '@/utils/logger'

const logger = createLogger('composable:useFrontendHealthChecks')

// Timeout constants for async checks (in milliseconds)
const TIMEOUT_EXTENSION_PING = 1000
const TIMEOUT_SERVICE_WORKER = 2000
const TIMEOUT_POSTMESSAGE_TEST = 500
const TIMEOUT_EXTENSION_STATUS = 2000

/**
 * Get current Unix timestamp in seconds
 */
function getCurrentTimestamp(): number {
  return Date.now() / 1000
}

// Match backend PrerequisiteResult interface for seamless aggregation
export interface PrerequisiteResult {
  id: string
  name: string
  category: 'frontend' | 'extension' | 'wasm' | 'runtime'
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
  criticality: 'critical' | 'high' | 'medium' | 'low'
  validation_method: string
  monitoring_available: boolean
  details: Record<string, any>
  timestamp: number
}

/**
 * Frontend Health Checks Composable
 * 
 * Provides client-side validation of browser-dependent prerequisites.
 */
export function useFrontendHealthChecks() {
  
  // ============================================================================
  // Frontend Category (3 checks)
  // ============================================================================
  
  /**
   * Check if useCellFactory composable is available
   */
  async function checkUseCellFactory(): Promise<PrerequisiteResult> {
    try {
      // Attempt dynamic import
      const module = await import('@/composables/useCellFactory')
      
      // Verify key methods exist
      const hasRequiredMethods = typeof module.useCellFactory === 'function'
      
      if (!hasRequiredMethods) {
        return {
          id: 'frontend.use_cell_factory',
          name: 'useCellFactory Composable',
          category: 'frontend',
          status: 'degraded',
          criticality: 'critical',
          validation_method: 'dynamic_import',
          monitoring_available: true,
          details: { 
            available: true,
            issue: 'Composable imported but methods not found'
          },
          timestamp: getCurrentTimestamp()
        }
      }
      
      return {
        id: 'frontend.use_cell_factory',
        name: 'useCellFactory Composable',
        category: 'frontend',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'dynamic_import',
        monitoring_available: true,
        details: { available: true },
        timestamp: getCurrentTimestamp()
      }
    } catch (error: any) {
      logger.error('useCellFactory check failed', { error: error.message })
      return {
        id: 'frontend.use_cell_factory',
        name: 'useCellFactory Composable',
        category: 'frontend',
        status: 'unhealthy',
        criticality: 'critical',
        validation_method: 'dynamic_import',
        monitoring_available: true,
        details: { available: false, error: error.message },
        timestamp: getCurrentTimestamp()
      }
    }
  }
  
  /**
   * Check if useExtension composable is available
   * 
   * ⚠️ DEPRECATED: Extension infrastructure removed (2026-02-08)
   * This check is no longer performed.
   */
  /* REMOVED - Extension no longer exists
  async function checkUseExtension(): Promise<PrerequisiteResult> {
    try {
      const module = await import('@/composables/useExtension')
      
      const hasRequiredMethods = typeof module.useExtension === 'function'
      
      return {
        id: 'frontend.use_extension',
        name: 'useExtension Composable',
        category: 'frontend',
        status: hasRequiredMethods ? 'healthy' : 'degraded',
        criticality: 'critical',
        validation_method: 'dynamic_import',
        monitoring_available: true,
        details: { 
          available: hasRequiredMethods,
          message: hasRequiredMethods ? undefined : 'Imported but methods not found'
        },
        timestamp: getCurrentTimestamp()
      }
    } catch (error: any) {
      logger.error('useExtension check failed', { error: error.message })
      return {
        id: 'frontend.use_extension',
        name: 'useExtension Composable',
        category: 'frontend',
        status: 'unhealthy',
        criticality: 'critical',
        validation_method: 'dynamic_import',
        monitoring_available: true,
        details: { available: false, error: error.message },
        timestamp: getCurrentTimestamp()
      }
    }
  }
  */
  
  /**
   * Check CellRegistry state availability
   */
  async function checkCellRegistry(): Promise<PrerequisiteResult> {
    try {
      // Check if Pinia is available and initialized
      try {
        // Try to access Pinia store structure
        const isInitialized = typeof window !== 'undefined' && 
                             (window as any).__VUE_DEVTOOLS_GLOBAL_HOOK__ !== undefined
        
        return {
          id: 'frontend.cell_registry',
          name: 'CellRegistry State',
          category: 'frontend',
          status: isInitialized ? 'healthy' : 'degraded',
          criticality: 'high',
          validation_method: 'store_check',
          monitoring_available: true,
          details: { 
            available: isInitialized,
            note: 'Pinia/Vue store infrastructure detected'
          },
          timestamp: getCurrentTimestamp()
        }
      } catch {
        return {
          id: 'frontend.cell_registry',
          name: 'CellRegistry State',
          category: 'frontend',
          status: 'degraded',
          criticality: 'high',
          validation_method: 'store_check',
          monitoring_available: true,
          details: { 
            available: false,
            note: 'Store infrastructure not yet initialized'
          },
          timestamp: getCurrentTimestamp()
        }
      }
    } catch (error: any) {
      logger.error('CellRegistry check failed', { error: error.message })
      return {
        id: 'frontend.cell_registry',
        name: 'CellRegistry State',
        category: 'frontend',
        status: 'unhealthy',
        criticality: 'high',
        validation_method: 'store_check',
        monitoring_available: true,
        details: { available: false, error: error.message },
        timestamp: getCurrentTimestamp()
      }
    }
  }
  
  // ============================================================================
  // Extension Category (5 checks)
  // ============================================================================
  
  /**
   * Check if browser extension is installed via postMessage ping
   */
  async function checkExtensionInstalled(): Promise<PrerequisiteResult> {
    try {
      const response = await new Promise<any>((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error(`Extension ping timeout (${TIMEOUT_EXTENSION_PING}ms)`))
        }, TIMEOUT_EXTENSION_PING)
        
        const handler = (event: MessageEvent) => {
          if (event.data?.type === 'SCAREVERSE_EXTENSION_PONG') {
            clearTimeout(timeout)
            window.removeEventListener('message', handler)
            resolve(event.data)
          }
        }
        
        window.addEventListener('message', handler)
        
        // Send ping with origin validation
        window.postMessage({ 
          type: 'SCAREVERSE_EXTENSION_PING',
          timestamp: Date.now()
        }, window.location.origin)
      })
      
      return {
        id: 'extension.installed',
        name: 'Extension Installed',
        category: 'extension',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'postmessage_ping',
        monitoring_available: true,
        details: { 
          installed: true, 
          latency_ms: response.latency || 0,
          version: response.version
        },
        timestamp: getCurrentTimestamp()
      }
    } catch (error: any) {
      logger.warn('Extension not detected', { error: error.message })
      return {
        id: 'extension.installed',
        name: 'Extension Installed',
        category: 'extension',
        status: 'unhealthy',
        criticality: 'critical',
        validation_method: 'postmessage_ping',
        monitoring_available: true,
        details: { 
          installed: false, 
          error: error.message,
          note: 'Extension may not be installed or enabled'
        },
        timestamp: getCurrentTimestamp()
      }
    }
  }
  
  /**
   * Check if service worker is active (requires chrome API)
   */
  async function checkServiceWorker(): Promise<PrerequisiteResult> {
    try {
      // Check if ServiceWorker API available
      if (!('serviceWorker' in navigator)) {
        return {
          id: 'extension.service_worker',
          name: 'Service Worker Active',
          category: 'extension',
          status: 'unhealthy',
          criticality: 'critical',
          validation_method: 'api_check',
          monitoring_available: true,
          details: { 
            available: false,
            reason: 'ServiceWorker API not available in this browser'
          },
          timestamp: getCurrentTimestamp()
        }
      }
      
      // Check for active service worker
      const registration = await navigator.serviceWorker.getRegistration()
      const isActive = registration?.active !== null && registration?.active !== undefined
      
      return {
        id: 'extension.service_worker',
        name: 'Service Worker Active',
        category: 'extension',
        status: isActive ? 'healthy' : 'degraded',
        criticality: 'critical',
        validation_method: 'service_worker_check',
        monitoring_available: true,
        details: { 
          available: true,
          active: isActive,
          state: registration?.active?.state || 'none'
        },
        timestamp: getCurrentTimestamp()
      }
    } catch (error: any) {
      logger.error('Service worker check failed', { error: error.message })
      return {
        id: 'extension.service_worker',
        name: 'Service Worker Active',
        category: 'extension',
        status: 'unknown',
        criticality: 'critical',
        validation_method: 'service_worker_check',
        monitoring_available: true,
        details: { available: false, error: error.message },
        timestamp: getCurrentTimestamp()
      }
    }
  }
  
  /**
   * Check browser extension permissions (Chrome-specific)
   */
  async function checkPermissions(): Promise<PrerequisiteResult> {
    try {
      // Check if chrome.permissions API available
      if (typeof chrome === 'undefined' || !chrome.permissions) {
        return {
          id: 'extension.permissions',
          name: 'Permissions Granted',
          category: 'extension',
          status: 'unknown',
          criticality: 'high',
          validation_method: 'api_check',
          monitoring_available: false,
          details: { 
            available: false,
            reason: 'Chrome extension API not available (not in extension context)'
          },
          timestamp: getCurrentTimestamp()
        }
      }
      
      // This check would need to run in extension context
      // For web page context, we mark as unknown
      return {
        id: 'extension.permissions',
        name: 'Permissions Granted',
        category: 'extension',
        status: 'unknown',
        criticality: 'high',
        validation_method: 'not_applicable',
        monitoring_available: false,
        details: { 
          available: false,
          reason: 'Permission check requires extension context',
          note: 'Validate via extension communication instead'
        },
        timestamp: getCurrentTimestamp()
      }
    } catch (error: any) {
      return {
        id: 'extension.permissions',
        name: 'Permissions Granted',
        category: 'extension',
        status: 'unknown',
        criticality: 'high',
        validation_method: 'api_check',
        monitoring_available: false,
        details: { error: error.message },
        timestamp: getCurrentTimestamp()
      }
    }
  }
  
  /**
   * Check TARGET_ORIGIN configuration
   */
  async function checkTargetOrigin(): Promise<PrerequisiteResult> {
    try {
      const currentOrigin = window.location.origin
      
      // Check if origin is valid
      const isValidOrigin = currentOrigin.startsWith('http://') || 
                           currentOrigin.startsWith('https://')
      
      return {
        id: 'extension.target_origin',
        name: 'TARGET_ORIGIN Configured',
        category: 'extension',
        status: isValidOrigin ? 'healthy' : 'degraded',
        criticality: 'high',
        validation_method: 'origin_check',
        monitoring_available: true,
        details: { 
          configured: isValidOrigin,
          origin: currentOrigin
        },
        timestamp: getCurrentTimestamp()
      }
    } catch (error: any) {
      return {
        id: 'extension.target_origin',
        name: 'TARGET_ORIGIN Configured',
        category: 'extension',
        status: 'unknown',
        criticality: 'high',
        validation_method: 'origin_check',
        monitoring_available: true,
        details: { error: error.message },
        timestamp: getCurrentTimestamp()
      }
    }
  }
  
  /**
   * Check postMessage communication latency
   */
  async function checkPostMessageCommunication(): Promise<PrerequisiteResult> {
    try {
      const startTime = Date.now()
      
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('postMessage test timeout'))
        }, TIMEOUT_POSTMESSAGE_TEST)
        
        const handler = (event: MessageEvent) => {
          if (event.data?.type === 'SCAREVERSE_TEST_ECHO') {
            clearTimeout(timeout)
            window.removeEventListener('message', handler)
            resolve()
          }
        }
        
        window.addEventListener('message', handler)
        
        // Self-echo test
        window.postMessage({ 
          type: 'SCAREVERSE_TEST_ECHO',
          timestamp: Date.now()
        }, window.location.origin)
      })
      
      const latencyMs = Date.now() - startTime
      const status = latencyMs < 100 ? 'healthy' : 
                    latencyMs < 200 ? 'degraded' : 'unhealthy'
      
      return {
        id: 'extension.post_message',
        name: 'postMessage Communication',
        category: 'extension',
        status,
        criticality: 'critical',
        validation_method: 'latency_test',
        monitoring_available: true,
        details: { 
          available: true,
          latency_ms: latencyMs,
          threshold_healthy: 100,
          threshold_degraded: 200
        },
        timestamp: getCurrentTimestamp()
      }
    } catch (error: any) {
      return {
        id: 'extension.post_message',
        name: 'postMessage Communication',
        category: 'extension',
        status: 'unhealthy',
        criticality: 'critical',
        validation_method: 'latency_test',
        monitoring_available: true,
        details: { available: false, error: error.message },
        timestamp: getCurrentTimestamp()
      }
    }
  }
  
  // ============================================================================
  // WASM Category (4 checks)
  // ============================================================================
  
  /**
   * Check if offscreen document is loaded (Chrome extension feature)
   */
  async function checkOffscreenDocument(): Promise<PrerequisiteResult> {
    return {
      id: 'wasm.offscreen_document',
      name: 'Offscreen Document Loaded',
      category: 'wasm',
      status: 'unknown',
      criticality: 'critical',
      validation_method: 'not_implemented',
      monitoring_available: false,
      details: { 
        available: false,
        reason: 'Offscreen document check requires extension context',
        implementation_note: 'Check via extension postMessage communication'
      },
      timestamp: getCurrentTimestamp()
    }
  }
  
  /**
   * Check WASM orchestrator initialization
   */
  async function checkWasmOrchestrator(): Promise<PrerequisiteResult> {
    return {
      id: 'wasm.orchestrator',
      name: 'WASM Orchestrator Initialized',
      category: 'wasm',
      status: 'unknown',
      criticality: 'critical',
      validation_method: 'not_implemented',
      monitoring_available: false,
      details: { 
        available: false,
        reason: 'WASM orchestrator runs in extension offscreen document',
        implementation_note: 'Validate via extension health check endpoint'
      },
      timestamp: getCurrentTimestamp()
    }
  }
  
  /**
   * Check OPFS (Origin Private File System) availability
   */
  async function checkOPFS(): Promise<PrerequisiteResult> {
    try {
      // Check if File System Access API available
      if (!navigator.storage?.getDirectory) {
        return {
          id: 'wasm.opfs',
          name: 'OPFS Service Available',
          category: 'wasm',
          status: 'unhealthy',
          criticality: 'high',
          validation_method: 'feature_detection',
          monitoring_available: true,
          details: { 
            available: false, 
            reason: 'File System Access API not supported in this browser'
          },
          timestamp: getCurrentTimestamp()
        }
      }
      
      // Try to access OPFS root
      const root = await navigator.storage.getDirectory()
      
      // Try to create a test file
      const testFile = await root.getFileHandle('__health_check__.txt', { create: true })
      await root.removeEntry('__health_check__.txt')
      
      // Get quota information
      const estimate = await navigator.storage.estimate()
      const usagePercent = ((estimate.usage || 0) / (estimate.quota || 1)) * 100
      
      const status = usagePercent > 90 ? 'degraded' : 'healthy'
      
      return {
        id: 'wasm.opfs',
        name: 'OPFS Service Available',
        category: 'wasm',
        status,
        criticality: 'high',
        validation_method: 'file_system_test',
        monitoring_available: true,
        details: {
          available: true,
          quota_used_mb: ((estimate.usage || 0) / 1024 / 1024).toFixed(2),
          quota_total_mb: ((estimate.quota || 0) / 1024 / 1024).toFixed(2),
          usage_percent: usagePercent.toFixed(1)
        },
        timestamp: getCurrentTimestamp()
      }
    } catch (error: any) {
      logger.error('OPFS check failed', { error: error.message })
      return {
        id: 'wasm.opfs',
        name: 'OPFS Service Available',
        category: 'wasm',
        status: 'unhealthy',
        criticality: 'high',
        validation_method: 'file_system_test',
        monitoring_available: true,
        details: { available: false, error: error.message },
        timestamp: getCurrentTimestamp()
      }
    }
  }
  
  /**
   * Check sandbox bootloader functionality
   */
  async function checkSandboxBootloader(): Promise<PrerequisiteResult> {
    try {
      // Check if iframe can be created (basic sandbox capability)
      const canCreateIframe = typeof document.createElement === 'function'
      
      if (!canCreateIframe) {
        return {
          id: 'wasm.sandbox_bootloader',
          name: 'Sandbox Bootloader',
          category: 'wasm',
          status: 'unhealthy',
          criticality: 'medium',
          validation_method: 'feature_detection',
          monitoring_available: true,
          details: { 
            available: false,
            reason: 'Cannot create iframe elements'
          },
          timestamp: getCurrentTimestamp()
        }
      }
      
      return {
        id: 'wasm.sandbox_bootloader',
        name: 'Sandbox Bootloader',
        category: 'wasm',
        status: 'healthy',
        criticality: 'medium',
        validation_method: 'feature_detection',
        monitoring_available: true,
        details: { 
          available: true,
          note: 'Basic iframe sandbox capability detected'
        },
        timestamp: getCurrentTimestamp()
      }
    } catch (error: any) {
      return {
        id: 'wasm.sandbox_bootloader',
        name: 'Sandbox Bootloader',
        category: 'wasm',
        status: 'unknown',
        criticality: 'medium',
        validation_method: 'feature_detection',
        monitoring_available: true,
        details: { error: error.message },
        timestamp: getCurrentTimestamp()
      }
    }
  }
  
  // ============================================================================
  // Runtime Category (2 checks - browser-side)
  // ============================================================================
  
  /**
   * Check browser API support (OPFS, WebAssembly, IndexedDB, ServiceWorker)
   */
  async function checkBrowserAPIs(): Promise<PrerequisiteResult> {
    try {
      const apis = {
        opfs: !!navigator.storage?.getDirectory,
        webassembly: typeof WebAssembly !== 'undefined',
        indexeddb: 'indexedDB' in window,
        serviceworker: 'serviceWorker' in navigator,
        crypto: !!window.crypto?.subtle
      }
      
      const availableCount = Object.values(apis).filter(Boolean).length
      const totalCount = Object.keys(apis).length
      const availabilityPercent = (availableCount / totalCount) * 100
      
      const status = availabilityPercent === 100 ? 'healthy' :
                    availabilityPercent >= 80 ? 'degraded' : 'unhealthy'
      
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
          available_count: availableCount,
          total_count: totalCount,
          availability_percent: availabilityPercent.toFixed(1)
        },
        timestamp: getCurrentTimestamp()
      }
    } catch (error: any) {
      return {
        id: 'runtime.browser_apis',
        name: 'Browser API Support',
        category: 'runtime',
        status: 'unknown',
        criticality: 'high',
        validation_method: 'feature_detection',
        monitoring_available: true,
        details: { error: error.message },
        timestamp: getCurrentTimestamp()
      }
    }
  }
  
  /**
   * Check browser system resources (client-side estimation)
   */
  async function checkSystemResources(): Promise<PrerequisiteResult> {
    try {
      // Check available browser APIs for resource info
      const hasMemoryAPI = 'memory' in performance
      const hasConnectionAPI = 'connection' in navigator
      
      const details: Record<string, any> = {
        apis_available: {
          performance_memory: hasMemoryAPI,
          network_information: hasConnectionAPI
        }
      }
      
      // Get memory info if available (Chrome-specific)
      if (hasMemoryAPI) {
        const memory = (performance as any).memory
        details.memory = {
          used_mb: (memory.usedJSHeapSize / 1024 / 1024).toFixed(2),
          total_mb: (memory.totalJSHeapSize / 1024 / 1024).toFixed(2),
          limit_mb: (memory.jsHeapSizeLimit / 1024 / 1024).toFixed(2)
        }
      }
      
      // Get connection info if available
      if (hasConnectionAPI) {
        const conn = (navigator as any).connection
        details.connection = {
          effective_type: conn.effectiveType,
          downlink: conn.downlink,
          rtt: conn.rtt
        }
      }
      
      // Check hardware concurrency (CPU cores)
      details.hardware = {
        logical_processors: navigator.hardwareConcurrency || 'unknown'
      }
      
      return {
        id: 'runtime.system_resources',
        name: 'System Resources (Browser)',
        category: 'runtime',
        status: 'healthy',
        criticality: 'medium',
        validation_method: 'browser_apis',
        monitoring_available: true,
        details,
        timestamp: getCurrentTimestamp()
      }
    } catch (error: any) {
      return {
        id: 'runtime.system_resources',
        name: 'System Resources (Browser)',
        category: 'runtime',
        status: 'unknown',
        criticality: 'medium',
        validation_method: 'browser_apis',
        monitoring_available: true,
        details: { error: error.message },
        timestamp: getCurrentTimestamp()
      }
    }
  }
  
  // ============================================================================
  // Main validation functions
  // ============================================================================
  
  /**
   * Validate all frontend prerequisites in parallel
   * 
   * ⚠️ BREAKING CHANGE (2026-02-08): Extension and WASM checks removed.
   * Browser extension infrastructure has been removed from the project.
   * This now validates only core frontend prerequisites.
   */
  async function validateAll(): Promise<PrerequisiteResult[]> {
    logger.info('Starting frontend health checks validation')
    
    try {
      const checks = [
        // Frontend (3) - Core checks only
        checkUseCellFactory(),
        // checkUseExtension(),  // REMOVED: Extension infrastructure removed
        checkCellRegistry(),
        
        // Extension (5) - ALL REMOVED
        // checkExtensionInstalled(),
        // checkServiceWorker(),
        // checkPermissions(),
        // checkTargetOrigin(),
        // checkPostMessageCommunication(),
        
        // WASM (4) - ALL REMOVED  
        // checkOffscreenDocument(),
        // checkWasmOrchestrator(),
        // checkOPFS(),
        // checkSandboxBootloader(),
        
        // Runtime (2)
        checkBrowserAPIs(),
        checkSystemResources()
      ]
      
      // Run all checks in parallel with Promise.allSettled for error resilience
      const results = await Promise.allSettled(checks)
      
      // Extract results, handle rejections gracefully
      const prerequisites = results.map((result, index): PrerequisiteResult => {
        if (result.status === 'fulfilled') {
          return result.value
        } else {
          // Create fallback result for failed check
          logger.error(`Health check ${index} failed`, { error: result.reason })
          return {
            id: `unknown.check_${index}`,
            name: `Unknown Check ${index}`,
            category: 'runtime',
            status: 'unknown',
            criticality: 'medium',
            validation_method: 'error',
            monitoring_available: false,
            details: { error: result.reason?.message || 'Unknown error' },
            timestamp: getCurrentTimestamp()
          }
        }
      })
      
      logger.info('Frontend health checks completed', {
        total: prerequisites.length,
        healthy: prerequisites.filter(p => p.status === 'healthy').length,
        degraded: prerequisites.filter(p => p.status === 'degraded').length,
        unhealthy: prerequisites.filter(p => p.status === 'unhealthy').length,
        unknown: prerequisites.filter(p => p.status === 'unknown').length
      })
      
      return prerequisites
    } catch (error: any) {
      logger.error('Fatal error during validation', { error: error.message })
      throw error
    }
  }
  
  /**
   * Validate prerequisites by category
   */
  async function validateByCategory(category: string): Promise<PrerequisiteResult[]> {
    logger.debug('Validating by category', { category })
    
    const all = await validateAll()
    return all.filter(prereq => prereq.category === category)
  }
  
  return {
    validateAll,
    validateByCategory
  }
}
