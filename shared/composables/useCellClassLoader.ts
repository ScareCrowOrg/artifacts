/**
 * @file useCellClassLoader.ts
 * @description Composable for dynamically loading cell classes from canonical cell types
 *
 * Handles:
 * - Discovery of available cell types
 * - Dynamic import of cell class implementations
 * - Class instantiation and caching
 */

import { createLogger } from '@/utils/logger'

const log = createLogger('cells:class-loader')

/**
 * Cell type metadata loaded from type.json
 */
interface CellTypeMetadata {
  id: string
  name: string
  version: string
  description: string
  default_refs?: {
    class?: string[]
    view?: string[]
  }
  default_initial_data?: Record<string, any>
  [key: string]: any
}

/**
 * Cache for loaded cell classes
 */
const cellClassCache = new Map<string, any>()

/**
 * Get the cell class by type ID
 * @param cellTypeId - Cell type identifier (e.g., 'chat-ia', 'png-generator')
 * @returns Cell class constructor
 */
export async function getCellClassByType(cellTypeId: string): Promise<any> {
  log.debug('Getting cell class', { cellTypeId })

  // Check cache first
  if (cellClassCache.has(cellTypeId)) {
    log.debug('Cell class found in cache', { cellTypeId })
    return cellClassCache.get(cellTypeId)
  }

  try {
    // Step 1: Try to load type.json to get basecell ref
    let classPath: string | null = null

    try {
      const { useCellTypeLoader } = await import('./useCellTypeLoader')
      const typeLoader = useCellTypeLoader()
      const typeDef = await typeLoader.loadType(cellTypeId)

      if (typeDef?.default_refs?.basecell?.[0]) {
        classPath = typeDef.default_refs.basecell[0]
        log.debug('Class path from type.json', { cellTypeId, classPath })
      }
    } catch (typeError) {
      log.debug('Could not load type.json, falling back to heuristic', {
        cellTypeId,
        error: typeError instanceof Error ? typeError.message : String(typeError),
      })
    }

    // Step 2: If no basecell ref, use heuristic naming convention
    if (!classPath) {
      // Remove '-cell' suffix if present (e.g., '3d-mesh-prototyping-cell' → '3d-mesh-prototyping')
      const typeWithoutSuffix = cellTypeId.endsWith('-cell')
        ? cellTypeId.slice(0, -5)
        : cellTypeId

      // Convert kebab-case to PascalCase: 'mesh-prototyping' → 'MeshPrototyping'
      const className = typeWithoutSuffix
        .split('-')
        .map(w => w[0].toUpperCase() + w.slice(1))
        .join('')

      classPath = `${className}Cell.ts`
      log.debug('Using heuristic class path', { cellTypeId, typeWithoutSuffix, className, classPath })
    }

    // Step 3: Dynamically import from canonical cell types
    // Path: artifacts/canonical/cell_types/{cellType}/{classPath}
    // Note: classPath from default_refs already includes directory (e.g., "frontend/View.vue")
    const modulePath = `#artifacts/canonical/cell_types/${cellTypeId}/${classPath}`
    log.debug('Attempting to import cell class', { cellTypeId, modulePath })

    const module = await import(
      /* @vite-ignore */
      modulePath
    )

    const CellClass = module.default || Object.values(module)[0]

    if (!CellClass) {
      throw new Error(`No default export found for cell type: ${cellTypeId}`)
    }

    // Cache the class
    cellClassCache.set(cellTypeId, CellClass)
    log.info('Cell class loaded successfully', { cellTypeId, className: CellClass.name })

    return CellClass
  } catch (error) {
    log.error('Failed to load cell class', {
      cellTypeId,
      errorMessage: error instanceof Error ? error.message : String(error),
    }, error)

    throw new Error(`Could not load cell class for type: ${cellTypeId}`)
  }
}

/**
 * Instantiate a cell by type ID
 * @param cellTypeId - Cell type identifier
 * @param initialData - Optional initial data to pass to constructor
 * @returns Cell instance
 */
export async function instantiateCellByType(
  cellTypeId: string,
  initialData?: Record<string, any>
): Promise<any> {
  log.debug('Instantiating cell', { cellTypeId, hasInitialData: !!initialData })

  try {
    const CellClass = await getCellClassByType(cellTypeId)
    const instance = new CellClass(initialData)

    log.info('Cell instantiated successfully', {
      cellTypeId,
      className: instance.constructor.name,
      instanceId: instance.id || 'no-id',
    })

    return instance
  } catch (error) {
    log.error('Failed to instantiate cell', {
      cellTypeId,
      errorMessage: error instanceof Error ? error.message : String(error),
    }, error)

    throw error
  }
}

/**
 * Composable for cell class loading and instantiation
 */
export function useCellClassLoader() {
  return {
    getCellClassByType,
    instantiateCellByType,
    /**
     * Clear the class cache (useful for testing or module reloads)
     */
    clearCache: () => {
      cellClassCache.clear()
      log.debug('Cell class cache cleared')
    },
  }
}
