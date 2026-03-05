/**
 * Book Type Loader Composable
 * 
 * Loads full type definitions on-demand from ScareRunner.
 * Same pattern as useCellTypeLoader.
 * 
 * Architecture:
 * - Type definition endpoint: GET /local/book-types/{type_id}/type.json
 * - Returns: Full book type definition
 * - Cached indefinitely (until manual cache clear or page reload)
 * - Validates required fields before returning
 * 
 * Usage:
 * ```ts
 * const { loadType, clearCache, cached } = useBookTypeLoader()
 * 
 * // Load full type definition
 * const typeDef = await loadType('notebook-book')
 * 
 * // Check cached types
 * console.log('Cached:', cached())
 * 
 * // Clear cache
 * clearCache()
 * ```
 */

import { createLogger } from '@/utils/logger'

const log = createLogger('books:typeloader')

export interface BookType {
  id: string
  name: string
  description: string
  version: string
  category: string
  default_refs: {
    view?: string[]
    scripts?: string[]
    docs?: string[]
  }
  default_initial_data: Record<string, any>
  properties_schema: Record<string, any>
  [key: string]: any
}

export interface BookTypeLoaderState {
  loadType: (typeId: string, baseUrl?: string) => Promise<BookType>
  clearCache: () => void
  cached: () => string[]
}

// Type definition cache (Map for O(1) lookup)
const typeCache = new Map<string, BookType>()

// ScareRunner base URL (from environment or default)
const SCARERUNNER_URL = import.meta.env.VITE_SCARERUNNER_URL || 'http://localhost:5050'

export function useBookTypeLoader(): BookTypeLoaderState {
  /**
   * Load full type definition for a book type.
   * Uses cache if available.
   * 
   * @param typeId - Book type ID
   * @param baseUrl - Optional base URL (defaults to SCARERUNNER_URL)
   * @returns Full type definition
   * @throws Error if type not found or invalid
   */
  const loadType = async (
    typeId: string,
    baseUrl: string = SCARERUNNER_URL
  ): Promise<BookType> => {
    // Check cache first
    if (typeCache.has(typeId)) {
      log.debug('Type definition loaded from cache', { typeId })
      return typeCache.get(typeId)!
    }
    
    // Fetch from server
    try {
      log.debug('Fetching type definition from ScareRunner', {
        typeId,
        url: `${baseUrl}/local/book-types/${typeId}/type.json`,
      })
      
      const response = await fetch(`${baseUrl}/local/book-types/${typeId}/type.json`)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const typeDef = await response.json()
      
      // Validate required fields
      if (!typeDef.id) {
        throw new Error('Invalid type definition: missing id')
      }
      if (!typeDef.name) {
        throw new Error('Invalid type definition: missing name')
      }
      
      // Cache the type definition
      typeCache.set(typeId, typeDef)
      
      log.info('Type definition loaded and cached', {
        typeId,
        name: typeDef.name,
        version: typeDef.version,
        category: typeDef.category,
      })
      
      return typeDef
    } catch (error: any) {
      const errorMessage = error.message || 'Unknown error'
      log.error('Failed to load book type definition', {
        typeId,
        error: errorMessage,
        stack: error.stack,
      })
      throw error
    }
  }
  
  /**
   * Clear all cached type definitions.
   * Useful after hot reload or when types are updated.
   */
  const clearCache = (): void => {
    const count = typeCache.size
    typeCache.clear()
    log.debug('Type definition cache cleared', { count })
  }
  
  /**
   * Get list of cached type IDs.
   * 
   * @returns Array of cached type IDs
   */
  const cached = (): string[] => {
    return Array.from(typeCache.keys())
  }
  
  return {
    loadType,
    clearCache,
    cached,
  }
}
