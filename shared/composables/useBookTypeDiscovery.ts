/**
 * Book Type Discovery Composable
 * 
 * Provides lazy-loading discovery of book types from ScareRunner.
 * Same pattern as useCellTypeDiscovery.
 * 
 * Architecture:
 * - Discovery endpoint: GET /local/book-types/
 * - Returns: id, title, description, origin (canonical/sandbox)
 * - Cached for 5 minutes to reduce server load
 * - Full type definitions loaded on-demand via useBookTypeLoader
 * 
 * Usage:
 * ```ts
 * const { bookTypes, loading, error, discover, refresh } = useBookTypeDiscovery()
 * 
 * // On modal open
 * await discover()  // Fast - uses cache if available
 * 
 * // Force refresh (e.g., after creating new book type)
 * await refresh()
 * ```
 */

import { ref, Ref } from 'vue'
import { createLogger } from '@/utils/logger'

const log = createLogger('books:discovery')

export interface BookTypeDiscovery {
  id: string
  title: string
  description: string
  origin: 'canonical' | 'sandbox'
}

export interface BookTypeDiscoveryState {
  bookTypes: Ref<BookTypeDiscovery[]>
  loading: Ref<boolean>
  error: Ref<string | null>
  discover: (forceRefresh?: boolean) => Promise<BookTypeDiscovery[]>
  refresh: () => Promise<BookTypeDiscovery[]>
  getType: (id: string) => BookTypeDiscovery | undefined
  lastDiscoveryTime: Ref<number | null>
}

// Singleton state (shared across all component instances)
const bookTypes = ref<BookTypeDiscovery[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const lastDiscoveryTime = ref<number | null>(null)

// Cache TTL: 5 minutes
const DISCOVERY_CACHE_TTL = 5 * 60 * 1000

// ScareRunner base URL (from environment or default)
const SCARERUNNER_URL = import.meta.env.VITE_SCARERUNNER_URL || 'http://localhost:5050'

export function useBookTypeDiscovery(): BookTypeDiscoveryState {
  /**
   * Discover book types from ScareRunner.
   * Uses cache if still valid, unless forceRefresh = true.
   * 
   * @param forceRefresh - Bypass cache and fetch fresh data
   * @returns Array of book type discovery objects
   */
  const discover = async (forceRefresh = false): Promise<BookTypeDiscovery[]> => {
    const now = Date.now()
    
    // Use cache if still valid
    if (
      !forceRefresh &&
      lastDiscoveryTime.value &&
      now - lastDiscoveryTime.value < DISCOVERY_CACHE_TTL &&
      bookTypes.value.length > 0
    ) {
      log.debug('Using cached book types discovery', {
        count: bookTypes.value.length,
        age_ms: now - lastDiscoveryTime.value,
      })
      return bookTypes.value
    }
    
    // Fetch fresh data
    loading.value = true
    error.value = null
    
    try {
      log.debug('Fetching book types discovery from ScareRunner', {
        url: `${SCARERUNNER_URL}/local/book-types/`,
        forceRefresh,
      })
      
      const response = await fetch(`${SCARERUNNER_URL}/local/book-types/`)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      bookTypes.value = data.book_types || []
      lastDiscoveryTime.value = now
      
      log.info('Book types discovered successfully', {
        count: bookTypes.value.length,
        canonical: bookTypes.value.filter(t => t.origin === 'canonical').length,
        sandbox: bookTypes.value.filter(t => t.origin === 'sandbox').length,
      })
      
      return bookTypes.value
    } catch (e: any) {
      const errorMessage = e.message || 'Unknown error'
      error.value = errorMessage
      bookTypes.value = []
      
      log.error('Failed to discover book types', {
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
   * @returns Array of book type discovery objects
   */
  const refresh = (): Promise<BookTypeDiscovery[]> => {
    log.debug('Forcing book types discovery refresh')
    return discover(true)
  }
  
  /**
   * Get a specific book type by ID from cached discovery data.
   * 
   * @param id - Book type ID
   * @returns Book type discovery object or undefined
   */
  const getType = (id: string): BookTypeDiscovery | undefined => {
    return bookTypes.value.find(t => t.id === id)
  }
  
  return {
    bookTypes,
    loading,
    error,
    discover,
    refresh,
    getType,
    lastDiscoveryTime,
  }
}
