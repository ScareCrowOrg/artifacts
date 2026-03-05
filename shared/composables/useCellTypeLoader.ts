/**
 * Cell Type Loader Composable
 * 
 * Loads full type definitions on-demand from ScareRunner.
 * Complements useCellTypeDiscovery (which provides minimal metadata).
 * 
 * Architecture:
 * - Type definition endpoint: GET /local/cell-types/{type_id}/type.json
 * - Returns: Full NotebookItemType definition
 * - Cached indefinitely (until manual cache clear or page reload)
 * - Validates required fields before returning
 * 
 * Three-Tier Loading Strategy:
 * 1. Discovery: Minimal metadata (id, title, description) - useCellTypeDiscovery
 * 2. Type Definition: Full schema (this composable) - on cell selection
 * 3. Compiled Component: Vue component (useCellViewLoader) - on cell render
 * 
 * Usage:
 * ```ts
 * const { loadType, clearCache, cached } = useCellTypeLoader()
 * 
 * // Load full type definition
 * const typeDef = await loadType('png-generator-cell')
 * 
 * // Check cached types
 * console.log('Cached:', cached())
 * 
 * // Clear cache (e.g., after hot reload)
 * clearCache()
 * ```
 */

import { createLogger } from '@/utils/logger'
import { loadCellTypeJson } from '@/utils/cellTypeLoaderUtil'

const log = createLogger('cells:typeloader')

export interface NotebookItemType {
  id: string
  name: string
  description: string
  version: string
  category: string
  can_render_dynamically: boolean
  default_refs: {
    view: string[]
    scripts?: string[]
    docs?: string[]
    basecell?: string[]
  }
  default_initial_data: Record<string, any>
  allow_instance_override_refs: boolean
  properties_schema: Record<string, any>
  [key: string]: any
}

export interface CellTypeLoaderState {
  loadType: (typeId: string, baseUrl?: string) => Promise<NotebookItemType>
  clearCache: () => void
  cached: () => string[]
}

// Type definition cache (Map for O(1) lookup)
const typeCache = new Map<string, NotebookItemType>()

// ScareRunner base URL (from environment or default)
const SCARERUNNER_URL = import.meta.env.VITE_SCARERUNNER_URL || 'http://localhost:5050'

export function useCellTypeLoader(): CellTypeLoaderState {
  /**
   * Load full type definition for a cell type.
   * Uses cache if available.
   * 
   * @param typeId - Cell type ID
   * @param baseUrl - Optional base URL (defaults to SCARERUNNER_URL)
   * @returns Full type definition
   * @throws Error if type not found or invalid
   */
  const loadType = async (
    typeId: string,
    baseUrl: string = SCARERUNNER_URL
  ): Promise<NotebookItemType> => {
    // Check cache first
    if (typeCache.has(typeId)) {
      log.debug('Type definition loaded from cache', { typeId })
      return typeCache.get(typeId)!
    }
    
    // Fetch from server
    try {
      const typeUrl = `${baseUrl}/local/cell-types/${typeId}/type.json`
      log.debug('Fetching type definition from ScareRunner', {
        typeId,
        url: typeUrl,
      })

      // Use shared utility to handle both JSON and reference files
      const typeDef: NotebookItemType = await loadCellTypeJson(typeUrl)
      
      // Validate required fields
      if (!typeDef.id) {
        throw new Error('Invalid type definition: missing id')
      }
      if (!typeDef.name) {
        throw new Error('Invalid type definition: missing name')
      }
      if (!typeDef.default_refs || !typeDef.default_refs.view) {
        throw new Error('Invalid type definition: missing default_refs.view')
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
      log.error('Failed to load cell type definition', {
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
