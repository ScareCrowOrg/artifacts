/**
 * Import Map Composable
 * 
 * Manages dynamic ES6 import maps for the frontend.
 * Enables native browser resolution of module imports without eval().
 * 
 * Architecture:
 * - Import map endpoint: GET /local/import-map.json (from ScareRunner)
 * - Injects <script type="importmap"> into document head at boot time
 * - Maps module prefixes to actual URLs:
 *   - @/ → http://localhost:8000/ (core services via nginx)
 *   - #artifacts/ → http://localhost:5052/artifacts/ (Vite compilation service)
 * 
 * Benefits:
 * - Native ES6 imports (no eval or custom linker)
 * - Browser handles module caching
 * - Source maps work correctly
 * - DevTools shows real file paths
 * 
 * Usage (in App.vue):
 * ```ts
 * import { useImportMap } from '@/composables/useImportMap'
 * 
 * const { injectImportMap } = useImportMap()
 * 
 * // On app boot (before loading any dynamic modules)
 * await injectImportMap()
 * ```
 * 
 * After injection, dynamic imports work:
 * ```ts
 * // Import from artifacts (compiled by Vite)
 * const module = await import('#artifacts/canonical/cell_types/chat-ia/frontend/View.vue')
 * 
 * // Import from core (cockpit-vue)
 * const composable = await import('@/composables/useAuth')
 * ```
 */

import { createLogger } from '@/utils/logger'

const log = createLogger('core:importmap')

export interface ImportMapConfig {
  imports: Record<string, string>
}

export interface ImportMapState {
  injectImportMap: () => Promise<void>
  isInjected: () => boolean
}

// Track injection state (singleton)
let injected = false

// ScareRunner base URL (from environment or default)
const SCARERUNNER_URL = import.meta.env.VITE_SCARERUNNER_URL || 'http://localhost:5050'

export function useImportMap(): ImportMapState {
  /**
   * Inject dynamic import map into document head.
   * 
   * This must be called ONCE at app boot, before any dynamic imports.
   * Calling multiple times has no effect (idempotent).
   * 
   * @throws Error if fetch fails or injection fails
   */
  const injectImportMap = async (): Promise<void> => {
    if (injected) {
      log.debug('Import map already injected, skipping')
      return
    }
    
    try {
      log.info('Fetching import map from ScareRunner', {
        url: `${SCARERUNNER_URL}/local/import-map.json`,
      })
      
      const response = await fetch(`${SCARERUNNER_URL}/local/import-map.json`)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const mapConfig: ImportMapConfig = await response.json()
      
      log.debug('Import map fetched', { imports: mapConfig.imports })
      
      // Create script tag with type="importmap"
      const script = document.createElement('script')
      script.type = 'importmap'
      script.textContent = JSON.stringify(mapConfig, null, 2)
      
      // Inject into document head
      document.head.appendChild(script)
      
      injected = true
      
      log.info('Import map injected successfully', {
        mappings: Object.keys(mapConfig.imports),
      })
      
      // Log each mapping for debugging
      Object.entries(mapConfig.imports).forEach(([prefix, url]) => {
        log.debug(`Import map: ${prefix} → ${url}`)
      })
    } catch (error: any) {
      const errorMessage = error.message || 'Unknown error'
      log.error('Failed to inject import map', {
        error: errorMessage,
        stack: error.stack,
      })
      throw error
    }
  }
  
  /**
   * Check if import map has been injected.
   * 
   * @returns true if injected, false otherwise
   */
  const isInjected = (): boolean => {
    return injected
  }
  
  return {
    injectImportMap,
    isInjected,
  }
}
