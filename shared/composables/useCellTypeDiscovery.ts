/**
 * Cell Type Discovery Composable
 * 
 * Provides lazy-loading discovery of cell types from ScareRunner.
 * Fetches minimal metadata for fast modal rendering (<100ms).
 * 
 * Architecture:
 * - Discovery endpoint: GET /local/cell-types/
 * - Returns: id, title, description, origin (canonical/sandbox)
 * - Cached for 5 minutes to reduce server load
 * - Full type definitions loaded on-demand via useCellTypeLoader
 * 
 * Usage:
 * ```ts
 * const { cellTypes, loading, error, discover, refresh } = useCellTypeDiscovery()
 * 
 * // On modal open
 * await discover()  // Fast - uses cache if available
 * 
 * // Force refresh (e.g., after creating new cell type)
 * await refresh()
 * ```
 */

import { ref, Ref } from 'vue'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:discovery')

export interface CellTypeDiscovery {
  id: string
  title: string
  description: string
  origin: 'canonical' | 'sandbox'
}

export interface CellTypeDiscoveryState {
  cellTypes: Ref<CellTypeDiscovery[]>
  loading: Ref<boolean>
  error: Ref<string | null>
  discover: (forceRefresh?: boolean) => Promise<CellTypeDiscovery[]>
  refresh: () => Promise<CellTypeDiscovery[]>
  getType: (id: string) => CellTypeDiscovery | undefined
  lastDiscoveryTime: Ref<number | null>
}

// Singleton state (shared across all component instances)
const cellTypes = ref<CellTypeDiscovery[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const lastDiscoveryTime = ref<number | null>(null)

// Cache TTL: 5 minutes
const DISCOVERY_CACHE_TTL = 5 * 60 * 1000

// ScareRunner base URL (from environment or default)
const SCARERUNNER_URL = import.meta.env.VITE_SCARERUNNER_URL || 'http://localhost:5050'

export function useCellTypeDiscovery(): CellTypeDiscoveryState {
  /**
   * Discover cell types from ScareRunner.
   * Uses cache if still valid, unless forceRefresh = true.
   * 
   * @param forceRefresh - Bypass cache and fetch fresh data
   * @returns Array of cell type discovery objects
   */
  const discover = async (forceRefresh = false): Promise<CellTypeDiscovery[]> => {
    const now = Date.now()
    
    // Use cache if still valid
    if (
      !forceRefresh &&
      lastDiscoveryTime.value &&
      now - lastDiscoveryTime.value < DISCOVERY_CACHE_TTL &&
      cellTypes.value.length > 0
    ) {
      log.debug('Using cached cell types discovery', {
        count: cellTypes.value.length,
        age_ms: now - lastDiscoveryTime.value,
      })
      return cellTypes.value
    }
    
    // Fetch fresh data
    loading.value = true
    error.value = null
    
    try {
      log.debug('Fetching cell types discovery from ScareRunner', {
        url: `${SCARERUNNER_URL}/local/cell-types/`,
        forceRefresh,
      })
      
      const response = await fetch(`${SCARERUNNER_URL}/local/cell-types/`)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      cellTypes.value = data.cell_types || []
      lastDiscoveryTime.value = now
      
      log.info('Cell types discovered successfully', {
        count: cellTypes.value.length,
        canonical: cellTypes.value.filter(t => t.origin === 'canonical').length,
        sandbox: cellTypes.value.filter(t => t.origin === 'sandbox').length,
      })
      
      return cellTypes.value
    } catch (e: any) {
      const errorMessage = e.message || 'Unknown error'
      error.value = errorMessage
      cellTypes.value = []
      
      log.error('Failed to discover cell types', {
        error: errorMessage,
        stack: e.stack,
      })
      
      throw e
    } finally {
      loading.value = false
    }
  }
  
  /**
   * Force refresh discovery data.
   * Bypasses cache and fetches fresh data from server.
   * 
   * @returns Array of cell type discovery objects
   */
  const refresh = (): Promise<CellTypeDiscovery[]> => {
    log.debug('Forcing cell types discovery refresh')
    return discover(true)
  }
  
  /**
   * Get a specific cell type by ID from cached discovery data.
   * 
   * @param id - Cell type ID
   * @returns Cell type discovery object or undefined
   */
  const getType = (id: string): CellTypeDiscovery | undefined => {
    return cellTypes.value.find(t => t.id === id)
  }
  
  return {
    cellTypes,
    loading,
    error,
    discover,
    refresh,
    getType,
    lastDiscoveryTime,
  }
}
