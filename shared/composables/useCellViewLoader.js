/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-24",
 *   "console_calls_found": 16,
 *   "console_calls_migrated": 16,
 *   "migration_rate": 100,
 *   "logger_namespace": "cells:viewloader",
 *   "validation_status": "excellent"
 * }
 */
/**
 * @file useCellViewLoader.js
 * @description Composable for dynamically loading cell view components
 * 
 * This composable handles the async loading of cell view components based on
 * cell type, with error handling and fallback support.
 * 
 * Part of Phase 5: Dynamic Cell Content Loading (Issue #1034)
 */

import { ref, shallowRef, watch, onMounted, markRaw } from 'vue'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:viewloader')

/**
 * Canonical cell modules discovery
 *
 * NOTE: import.meta.glob cannot use aliases and won't work in Kubernetes
 * where cells are not available locally. Instead, rely on dynamic loading
 * via useCellTypeLoader which fetches from ScareRunner via HTTP.
 *
 * Cells are discovered at runtime when loaded, not at build time.
 */
const canonicalCellModules = {}

/**
 * Build dynamic loaders map from discovered canonical cell modules
 * Extracts cell type ID from file path and creates loader function
 */
const CANONICAL_LOADERS = Object.entries(canonicalCellModules).reduce((acc, [path, loader]) => {
  // Extract cell type from path: ../../../artifacts/canonical/cell_types/{cellType}/frontend/View.vue
  const match = path.match(/cell_types\/([^/]+)\/frontend\/View\.vue$/)
  if (match) {
    const cellTypeId = match[1]
    acc[cellTypeId] = loader
    // Log discovery in development mode only
    if (import.meta.env.DEV) {
      log.debug('Discovered canonical cell type', { cellTypeId })
    }
  }
  return acc
}, {})

/**
 * Legacy and special cell types with custom paths
 * These require explicit registration due to non-standard locations
 */
const LEGACY_CELL_VIEW_PATHS = {
  // === Base Cell Components (Subviews) ===
  'fragments-manager': () => import('#artifacts/canonical/base_cell_components/frontend/views/BaseFragmentsManager.vue'),

  // === Other Cell Types (Not yet migrated) ===
  'code-fragment': () => import('@/components/DefaultCellView.vue'),
  'notebook': () => import('@/components/NotebookContainer.vue'),
  'default': () => import('@/components/DefaultCellView.vue'),
}

/**
 * Unified map of cell type IDs to their View component paths
 * Automatically includes all dynamically discovered canonical cell types + legacy types
 */
const CELL_VIEW_PATHS = {
  ...LEGACY_CELL_VIEW_PATHS,
  // Add all dynamically discovered canonical cell types
  ...CANONICAL_LOADERS
}

/**
 * Fallback component for unknown cell types
 * Shows helpful message when cell type doesn't have a registered view
 */
const FallbackComponent = {
  template: `
    <div class="cell-view-fallback p-6 text-center border-2 border-dashed border-gray-300 rounded-lg m-4">
      <p class="text-5xl mb-3">📦</p>
      <p class="font-bold text-lg theme-text-primary mb-2">Cell View Not Available</p>
      <p class="text-sm theme-text-secondary mb-3">
        No view component registered for cell type: <code class="px-2 py-1 bg-gray-100 rounded">{{ cellType }}</code>
      </p>
      <details class="text-left mt-4">
        <summary class="cursor-pointer text-sm font-semibold theme-text-primary mb-2">
          Troubleshooting Information
        </summary>
        <div class="text-xs theme-text-secondary space-y-2 pl-4">
          <p><strong>Possible causes:</strong></p>
          <ul class="list-disc pl-4 space-y-1">
            <li>Backend returned an unexpected cell type ID</li>
            <li>Cell type not registered in <code>useCellViewLoader.js</code></li>
            <li>Component import path incorrect or file missing</li>
          </ul>
          <p class="mt-3"><strong>What to check:</strong></p>
          <ul class="list-disc pl-4 space-y-1">
            <li>Open browser console for detailed logs</li>
            <li>Verify backend <code>/api/cells/types/list</code> response</li>
            <li>Check <code>CELL_VIEW_PATHS</code> in useCellViewLoader.js</li>
          </ul>
        </div>
      </details>
    </div>
  `,
  props: {
    cell: Object,
    cellType: String,
  },
}

/**
 * Error component for failed loads
 * Shows detailed error information when component loading fails
 */
const ErrorComponent = {
  template: `
    <div class="cell-view-error p-6 text-center border-2 border-red-300 rounded-lg m-4 bg-red-50">
      <p class="text-5xl mb-3">⚠️</p>
      <p class="font-bold text-lg text-red-700 mb-2">Component Load Failed</p>
      <p class="text-sm text-red-600 mb-3">
        {{ error?.message || 'Unknown error occurred while loading cell view' }}
      </p>
      <details class="text-left mt-4">
        <summary class="cursor-pointer text-sm font-semibold text-red-700 mb-2">
          Error Details
        </summary>
        <div class="text-xs text-red-600 space-y-2 pl-4">
          <p v-if="error?.stack" class="font-mono text-xs bg-red-100 p-2 rounded overflow-auto max-h-32">
            {{ error.stack }}
          </p>
          <p class="mt-3"><strong>What to do:</strong></p>
          <ul class="list-disc pl-4 space-y-1">
            <li>Check browser console for full error details</li>
            <li>Verify component file exists at import path</li>
            <li>Check for syntax errors in component file</li>
            <li>Ensure all required dependencies are installed</li>
          </ul>
        </div>
      </details>
    </div>
  `,
  props: {
    error: Object,
  },
}

/**
 * Loading component
 */
const LoadingComponent = {
  template: `
    <div class="cell-view-loading p-4 flex items-center justify-center">
      <div class="text-center">
        <div class="spinner mb-2"></div>
        <p class="text-sm theme-text-secondary">Loading cell view...</p>
      </div>
    </div>
  `,
}

/**
 * Convert class name to cell type ID
 * ChatIACell → chat-ia
 * PngGeneratorCell → png-generator
 * @param {string} className - Class name
 * @returns {string} Cell type ID
 */
function classNameToCellTypeId(className) {
  // Remove 'Cell' suffix if present
  let typeId = className.replace(/Cell$/, '')

  // Convert CamelCase to kebab-case
  // ChatIA → chat-ia, PngGenerator → png-generator
  typeId = typeId
    .replace(/([A-Z])([A-Z][a-z])/g, '$1-$2')  // Handle consecutive capitals
    .replace(/([a-z\d])([A-Z])/g, '$1-$2')     // Handle normal CamelCase
    .toLowerCase()

  return typeId
}

/**
 * Composable for loading cell view components
 *
 * Preferred flow: cell.show() → BaseCell handles rendering its own View.vue
 * Fallback flow: useCellViewLoader → manual View.vue loading for legacy cells
 *
 * Supports three input modes:
 * 1. Cell class mode: useCellViewLoader(ChatIACell) - instantiates and calls show()
 * 2. Cell instance mode: useCellViewLoader(chatIAInstance) - uses instance directly and calls show()
 * 3. Cell ref mode: useCellViewLoader(cellRef) - cell ref object with notebook_item_type_id
 *
 * @param {Object|Function} cellInput - Cell class, cell instance, or cell ref object
 * @param {Object} [options] - Configuration options
 * @param {Function} [options.onShowFailed] - Callback if show() fails (fallback to manual loading)
 * @returns {Object} Cell view loader interface
 */
export function useCellViewLoader(cellInput, options = {}) {
  console.log('[useCellViewLoader] ENTRY POINT - Composable called', {
    inputType: typeof cellInput,
    isFunction: typeof cellInput === 'function',
    isObject: typeof cellInput === 'object',
    hasShow: cellInput?.show !== undefined,
    hasValue: cellInput?.value !== undefined,
    timestamp: new Date().toISOString(),
  })

  log.info('[VIEWLOADER] Composable initialized', {
    inputType: typeof cellInput,
    isFunction: typeof cellInput === 'function',
    isObject: typeof cellInput === 'object',
    hasShow: cellInput?.show !== undefined,
    timestamp: new Date().toISOString(),
  })

  const cellViewComponent = shallowRef(null)
  const cellInstance = shallowRef(null)  // Store instantiated cell instance
  const isLoading = ref(false)
  const error = ref(null)
  const usesShowMethod = ref(false)       // Track if using BaseCell.show() (preferred)

  // Register cell instance when created (for useCellInstancesStore)
  const registerCellInstance = async (instance, cellId, cellType) => {
    if (!instance || !cellId) return
    try {
      const { useCellInstancesStore } = await import('@/shared/stores/cellInstancesStore.ts')
      const store = useCellInstancesStore()
      const success = store.registerInstance(cellId, cellType || 'unknown', instance)
      if (success) {
        log.debug('[REGISTRY] Registered cell instance in Pinia store', { cellId, cellType })
      }
    } catch (err) {
      log.warn('[REGISTRY] Failed to register cell instance', { cellId, error: err.message })
    }
  }

  // Detect input type: class, instance, or cell ref
  const isCellClass = typeof cellInput === 'function' && !!cellInput.prototype
  const isCellInstance = !isCellClass && typeof cellInput === 'object' && cellInput !== null && typeof cellInput.show === 'function'

  // Set cellInstance immediately if input is already an instance
  if (isCellInstance) {
    cellInstance.value = cellInput
  }

  const cell = isCellClass || isCellInstance ? ref(null) : cellInput

  // Async initialization function for class and instance modes
  const executeClassOrInstanceMode = async () => {
    if (isCellClass) {
      // Class mode: instantiate and load immediately
      log.debug('[CLASS_MODE] Loading cell class', { className: cellInput.name })
      const cellType = getCellType(cellInput)
      await loadCellView(cellType, cellInput)
    } else if (isCellInstance) {
      // Instance mode: use instance directly
      log.debug('[INSTANCE_MODE] Loading cell instance', { className: cellInput.constructor.name })
      const cellType = getCellType(cellInput)
      await loadCellView(cellType)
    }
  }

  // Start loading immediately for class/instance mode (non-blocking)
  // This allows tests to work without waiting for onMounted
  if (isCellClass || isCellInstance) {
    executeClassOrInstanceMode()
  }

  /**
   * Get cell type from cell object, class, or instance
   * @param {Object|Function} input - Cell object, Cell class, or Cell instance
   * @returns {string} Cell type ID
   */
  function getCellType(input) {
    // PHASE 7: Check if semantic cellType.name was stored in the instance
    if (input && input.__cellTypeName) {
      console.log('[getCellType] Using semantic cellType.name from instance', {
        cellTypeName: input.__cellTypeName,
        timestamp: new Date().toISOString(),
      })
      log.debug('[GET_CELLTYPE] Using semantic cellType.name from instance', {
        cellTypeName: input.__cellTypeName,
      })
      return input.__cellTypeName
    }

    // PHASE 7: Use semantic cellType from options if provided (preserves folder name)
    if (options.semanticCellType) {
      console.log('[getCellType] Using semantic cellType from options', {
        semanticCellType: options.semanticCellType,
        timestamp: new Date().toISOString(),
      })
      log.debug('[GET_CELLTYPE] Using semantic cellType from options', {
        semanticCellType: options.semanticCellType,
      })
      return options.semanticCellType
    }

    console.log('[getCellType] START', {
      inputType: typeof input,
      inputKeys: typeof input === 'object' ? Object.keys(input).slice(0, 5) : undefined,
      timestamp: new Date().toISOString(),
    })

    log.info('[GET_CELLTYPE] START', {
      inputType: typeof input,
      inputKeys: typeof input === 'object' ? Object.keys(input).slice(0, 5) : undefined,
      timestamp: new Date().toISOString(),
    })

    // Case 1: Cell class (constructor function)
    if (typeof input === 'function' && input.prototype) {
      const cellTypeId = classNameToCellTypeId(input.name)
      log.debug('[CLASS_MODE] Extracted cell type from class name', {
        className: input.name,
        cellTypeId,
      })
      return cellTypeId
    }

    // Case 2: Cell instance (object with show method)
    if (typeof input === 'object' && input !== null && typeof input.show === 'function') {
      const cellTypeId = classNameToCellTypeId(input.constructor.name)
      log.debug('[INSTANCE_MODE] Extracted cell type from instance class name', {
        className: input.constructor.name,
        cellTypeId,
      })
      return cellTypeId
    }

    // Case 3: Cell object/ref
    const cellObj = input?.value || input  // Handle both ref and plain object

    log.debug('[OBJECT_MODE] Getting cell type from cell object', {
      hasCellObj: !!cellObj,
      cellObjKeys: cellObj ? Object.keys(cellObj) : [],
      notebook_item_type_id: cellObj?.notebook_item_type_id,
      type: cellObj?.type,
      cellType: cellObj?.cellType,
    })

    if (!cellObj) {
      log.warn('[OBJECT_MODE] No cell object provided, returning default')
      return 'default'
    }

    // Try multiple possible properties for cell type
    const cellType = (
      cellObj.notebook_item_type_id ||
      cellObj.type ||
      cellObj.cellType ||
      'default'
    )

    log.debug('[OBJECT_MODE] Resolved cell type', {
      resolvedType: cellType,
      source: cellObj.notebook_item_type_id ? 'notebook_item_type_id' :
              cellObj.type ? 'type' :
              cellObj.cellType ? 'cellType' : 'default',
      notebook_item_type_id: cellObj.notebook_item_type_id,
      type: cellObj.type,
      cellTypeProperty: cellObj.cellType
    })

    log.info('[GET_CELLTYPE] RETURNING', { cellType, timestamp: new Date().toISOString() })
    return cellType
  }

  /**
   * PREFERRED: Try to render cell using BaseCell.show() method
   * This allows cell to control its own rendering (custom View.vue or dynamic form)
   *
   * @param {Object} instance - Cell instance with show() method
   * @returns {Promise<boolean>} true if show() succeeded, false if should fallback to manual loading
   */
  async function tryShowMethod(instance) {
    if (!instance || typeof instance.show !== 'function') {
      log.debug('[SHOW_METHOD] Cell does not have show() method, will use manual loading')
      return null
    }

    try {
      log.debug('[SHOW_METHOD] Attempting to render via BaseCell.show()', {
        instanceType: instance.constructor?.name,
        hasShow: !!instance.show,
      })

      // Call show() with empty data and basic config
      // BaseCell.show() returns component info if custom View.vue exists, or void if dynamic form
      const showConfig = {
        container: null,  // Framework will decide where to render
        theme: 'auto',
        readOnly: false,
      }

      const showResult = await instance.show({}, showConfig)

      console.log('[SHOW_METHOD] show() returned:', {
        showResult,
        hasResult: !!showResult,
        resultType: typeof showResult,
        resultKeys: showResult ? Object.keys(showResult) : [],
        componentPath: showResult?.componentPath,
        timestamp: new Date().toISOString(),
      })

      log.info('[SHOW_METHOD] Successfully called cell.show()', {
        instanceType: instance.constructor?.name,
        hasResult: !!showResult,
        resultKeys: showResult ? Object.keys(showResult) : [],
      })

      // If show() returned component info, use it to load the View
      if (showResult && showResult.componentPath) {
        log.debug('[SHOW_METHOD] show() returned component info, loading View.vue', {
          componentPath: showResult.componentPath,
          cellType: showResult.cellType,
        })
        usesShowMethod.value = true
        return showResult // Return component info for caller to load
      }

      // If show() returned nothing, it handled rendering (dynamic form)
      if (showResult === undefined || showResult === null) {
        log.debug('[SHOW_METHOD] show() handled rendering directly (dynamic form)')
        usesShowMethod.value = true
        return { handled: true } // Signal that rendering was handled
      }

      usesShowMethod.value = true
      return showResult
    } catch (showError) {
      log.warn('[SHOW_METHOD] Cell.show() failed, falling back to manual View.vue loading', {
        errorMessage: showError.message,
        instanceType: instance.constructor?.name,
      }, showError)

      // Invoke callback if provided
      if (options.onShowFailed) {
        options.onShowFailed(showError, instance)
      }

      return null
    }
  }

  /**
   * FALLBACK: Load cell view component manually
   * Used when cell doesn't implement BaseCell.show() or show() fails
   *
   * Loading strategy (in order):
   * 1. Pre-compiled canonical types (CELL_VIEW_PATHS)
   * 2. Dynamic import from Vite (for sandbox types and new canonical types)
   * 3. Fallback component (if both fail)
   *
   * @param {string} cellType - Cell type ID
   * @param {Function} [CellClass] - Optional cell class to instantiate (class mode only)
   */
  async function loadCellViewManually(cellType, CellClass = null) {
    console.log('[loadCellViewManually] ENTRY POINT', {
      cellType,
      hasClassToInstantiate: !!CellClass,
      cellViewComponentValue: cellViewComponent.value,
      timestamp: new Date().toISOString()
    })

    log.info('[LOADMANUALLY] ENTRY POINT', {
      cellType,
      hasClassToInstantiate: !!CellClass,
      cellViewComponentValue: cellViewComponent.value,
      timestamp: new Date().toISOString()
    })

    log.debug('[LOADING] Starting cell view load', {
      cellType,
      hasClassToInstantiate: !!CellClass,
      timestamp: new Date().toISOString()
    })

    if (!cellType) {
      log.warn('[LOADING] No cell type provided, using default')
      cellType = 'default'
    }

    isLoading.value = true
    error.value = null
    cellInstance.value = null  // Reset instance

    try {
      // Step 0: Instantiate cell class if provided (class mode)
      if (CellClass) {
        try {
          cellInstance.value = new CellClass()

          // Register cell instance in Pinia store using cellId if available
          const cellId = cell?.value?.id || cell?.value?.cellId
          if (cellId) {
            await registerCellInstance(cellInstance.value, cellId, cellType)
          }

          log.info('[CLASS_MODE] Successfully instantiated cell class', {
            cellType,
            className: CellClass.name,
            hasShow: typeof cellInstance.value.show === 'function',
            registered: !!cellId,
          })
        } catch (instantiateError) {
          log.error('[CLASS_MODE] Failed to instantiate cell class', {
            cellType,
            className: CellClass.name,
            errorMessage: instantiateError.message,
          }, instantiateError)
          error.value = instantiateError
          cellViewComponent.value = markRaw(ErrorComponent)
          isLoading.value = false
          return
        }
      }

      // Step 0.5: If cell instance exists with show() method, call it
      // This is the generic BaseCell rendering path - works for any cell type
      if (cellInstance.value && typeof cellInstance.value.show === 'function') {
        try {
          log.debug('[BASECELL_MODE] Calling cellInstance.show()', { cellType })
          const showResult = await cellInstance.value.show({}, {})

          // show() should return component info
          if (showResult) {
            log.info('[BASECELL_MODE] show() returned component info', {
              cellType,
              hasComponentPath: !!showResult.componentPath,
              hasCellType: !!showResult.cellType,
            })

            // If show() returned component info, load it via Vite
            if (showResult.componentPath && showResult.cellType) {
              const origin = showResult.origin || 'canonical'
              const modulePath = `#artifacts/${origin}/cell_types/${showResult.cellType}/${showResult.componentPath}`

              log.debug('[BASECELL_MODE] Loading component from show() result', {
                modulePath,
                cellType: showResult.cellType,
              })

              const compiled = await import(/* @vite-ignore */ modulePath)
              const ViewComponent = compiled.default || compiled

              // Store cellInstance in component for access during render
              // View.vue will receive it via provide/inject context
              ViewComponent._cellInstance = cellInstance.value

              log.info('[BASECELL_MODE] Successfully loaded View with cellInstance context', {
                cellType: showResult.cellType,
                hasCellInstance: !!cellInstance.value,
              })

              cellViewComponent.value = markRaw(ViewComponent)
              isLoading.value = false
              return
            }
          }

          log.debug('[BASECELL_MODE] show() completed without returning component info')
          isLoading.value = false
          return
        } catch (showError) {
          log.error('[BASECELL_MODE] cellInstance.show() failed', {
            cellType,
            errorMessage: showError.message,
          }, showError)
          // Fall through to manual loading
        }
      }

      // Step 1: Check if we have a pre-compiled component loader for this type
      const componentLoader = CELL_VIEW_PATHS[cellType]

      log.debug('[LOADING] Component loader resolution', {
        cellType,
        hasLoader: !!componentLoader,
        hasSpecificLoader: !!CELL_VIEW_PATHS[cellType],
        usingFallback: !CELL_VIEW_PATHS[cellType],
        availableTypes: Object.keys(CELL_VIEW_PATHS).slice(0, 10), // Log first 10 types
        canonicalLoadersCount: Object.keys(CANONICAL_LOADERS).length,
        legacyLoadersCount: Object.keys(LEGACY_CELL_VIEW_PATHS).length,
      })

      if (componentLoader) {
        // Path A: Pre-compiled component (fast, build-time)
        log.debug('[LOADING] Using pre-compiled component loader', { cellType })

        try {
          const component = await componentLoader()
          log.info('[LOADING] Successfully loaded pre-compiled component', {
            cellType,
            componentName: component.default?.name || 'Unknown',
            hasDefault: !!component.default,
          })

          cellViewComponent.value = markRaw(component.default || component)
          isLoading.value = false
          return
        } catch (importError) {
          log.error('[LOADING] Pre-compiled import FAILED, trying dynamic import', {
            cellType,
            errorMessage: importError.message,
          }, importError)
          // Fall through to dynamic import
        }
      }

      // Step 2: Try dynamic import from Vite (for sandbox types and new canonical types)
      log.debug('[LOADING] Attempting dynamic import from Vite', { cellType })

      try {
        // Load type definition to get component path
        log.debug('[LOADING] Loading type definition', { cellType })
        const { useCellTypeLoader } = await import('./useCellTypeLoader.ts')
        const typeLoader = useCellTypeLoader()
        const typeDef = await typeLoader.loadType(cellType)

        log.debug('[LOADING] Type definition loaded', {
          cellType,
          hasTypeDef: !!typeDef,
          hasView: !!typeDef?.default_refs?.view,
          viewPaths: typeDef?.default_refs?.view,
        })

        if (!typeDef || !typeDef.default_refs || !typeDef.default_refs.view || !typeDef.default_refs.view[0]) {
          throw new Error(`No view component path in type definition for ${cellType}`)
        }

        const componentPath = typeDef.default_refs.view[0]

        // Determine origin (canonical or sandbox)
        const { useCellTypeDiscovery } = await import('./useCellTypeDiscovery.ts')
        const discovery = useCellTypeDiscovery()
        const discoveryData = discovery.getType(cellType)
        const origin = discoveryData?.origin || 'canonical'

        log.debug('[LOADING] Discovery data', {
          cellType,
          discoveryData,
          origin,
        })

        // Build module path for Vite server
        // Browser resolves #artifacts/ via import map → http://localhost:5052/artifacts/
        const modulePath = `#artifacts/${origin}/cell_types/${cellType}/${componentPath}`

        log.debug('[LOADING] About to import module', {
          cellType,
          componentPath,
          origin,
          modulePath,
          timestamp: new Date().toISOString(),
        })

        const compiled = await import(/* @vite-ignore */ modulePath)

        log.debug('[LOADING] Module imported successfully', {
          cellType,
          modulePath,
          hasDefault: !!compiled.default,
          hasKeys: Object.keys(compiled),
        })

        cellViewComponent.value = markRaw(compiled.default || compiled)

        log.info('[LOADING] Successfully loaded from Vite', {
          cellType,
          modulePath,
          componentName: cellViewComponent.value?.name || 'Unknown',
        })

        isLoading.value = false
        return
      } catch (viteError) {
        log.error('[LOADING] Dynamic import from Vite FAILED', {
          cellType,
          errorMessage: viteError.message,
          errorName: viteError.name,
          errorStack: viteError.stack,
          timestamp: new Date().toISOString(),
        }, viteError)
        // Fall through to fallback
      }

      // Step 3: No loader found and Vite import failed - use fallback
      const errorMsg = `No view component found for cell type: ${cellType}`
      log.error('[LOADING] No component available, using fallback', { cellType })
      error.value = new Error(errorMsg)
      cellViewComponent.value = markRaw(FallbackComponent)
      isLoading.value = false

    } catch (err) {
      log.error('[LOADING] CRITICAL ERROR loading cell view', {
        cellType,
        errorMessage: err.message,
        errorStack: err.stack,
        timestamp: new Date().toISOString()
      }, err)
      error.value = err
      cellViewComponent.value = markRaw(FallbackComponent)
      isLoading.value = false
    }
  }

  /**
   * Register a new cell view component
   * @param {string} cellTypeId - Cell type ID
   * @param {Function} componentLoader - Component loader function
   */
  function registerCellView(cellTypeId, componentLoader) {
    CELL_VIEW_PATHS[cellTypeId] = componentLoader
  }

  /**
   * Check if a cell type has a registered view
   * @param {string} cellTypeId - Cell type ID
   * @returns {boolean} True if registered
   */
  function hasCellView(cellTypeId) {
    return !!CELL_VIEW_PATHS[cellTypeId]
  }

  /**
   * Main orchestrator function
   * Tries to render cell using BaseCell.show() (preferred)
   * Falls back to manual View.vue loading if show() unavailable/fails
   *
   * @param {string} cellType - Cell type ID
   * @param {Function} [CellClass] - Optional cell class to instantiate
   */
  async function loadCellView(cellType, CellClass = null) {
    console.log('[loadCellView] ENTRY POINT', {
      cellType,
      hasClassToInstantiate: !!CellClass,
      calledFrom: new Error().stack?.split('\n')[2]?.trim(),
      timestamp: new Date().toISOString()
    })

    log.info('[LOADCELLVIEW] ENTRY POINT', {
      cellType,
      hasClassToInstantiate: !!CellClass,
      calledFrom: new Error().stack?.split('\n')[2]?.trim(),
      timestamp: new Date().toISOString()
    })

    log.debug('[ORCHESTRATOR] Starting cell view load', {
      cellType,
      hasClassToInstantiate: !!CellClass,
      timestamp: new Date().toISOString()
    })

    isLoading.value = true
    error.value = null
    usesShowMethod.value = false

    try {
      // Step 0: Instantiate class if needed
      if (CellClass && !cellInstance.value) {
        try {
          cellInstance.value = new CellClass()
          log.info('[ORCHESTRATOR] Instantiated cell class', { className: CellClass.name })
        } catch (instantiateError) {
          log.error('[ORCHESTRATOR] Failed to instantiate cell class', {
            className: CellClass?.name,
            errorMessage: instantiateError.message,
          }, instantiateError)
          error.value = instantiateError
          cellViewComponent.value = markRaw(ErrorComponent)
          isLoading.value = false
          return
        }
      }

      // Step 1: PREFERRED - Try BaseCell.show() method
      const instanceToUse = cellInstance.value || (cell?.value)
      const showResult = await tryShowMethod(instanceToUse)

      // Check what show() returned
      if (showResult && showResult.componentPath) {
        // show() returned component info - load the View.vue
        log.debug('[ORCHESTRATOR] show() returned component info, loading View component', {
          componentPath: showResult.componentPath,
          cellTypeName: showResult.cellTypeName,
        })

        try {
          // Import View component from the path returned by show()
          const viewModule = await import(
            /* @vite-ignore */
            `#artifacts/canonical/cell_types/${showResult.cellTypeName}/${showResult.componentPath}`
          )
          const ViewComponent = viewModule.default || viewModule

          cellViewComponent.value = markRaw(ViewComponent)
          log.info('[ORCHESTRATOR] Loaded View component from show() result', {
            componentPath: showResult.componentPath,
            componentName: ViewComponent.name,
          })

          isLoading.value = false
          return
        } catch (viewError) {
          log.error('[ORCHESTRATOR] Failed to load View component from show() result', {
            componentPath: showResult.componentPath,
            errorMessage: viewError.message,
          }, viewError)
          error.value = viewError
          cellViewComponent.value = markRaw(ErrorComponent)
          isLoading.value = false
          return
        }
      }

      if (showResult && showResult.handled) {
        // show() handled rendering directly (dynamic form)
        log.debug('[ORCHESTRATOR] show() handled rendering directly (dynamic form)')
        isLoading.value = false
        return
      }

      // Step 2: FALLBACK - Manual View.vue loading if show() not available/failed
      log.debug('[ORCHESTRATOR] Falling back to manual View.vue loading', { cellType })
      await loadCellViewManually(cellType, CellClass)

    } catch (err) {
      log.error('[ORCHESTRATOR] CRITICAL ERROR during cell view load', {
        cellType,
        errorMessage: err.message,
        errorStack: err.stack,
        timestamp: new Date().toISOString()
      }, err)
      error.value = err
      cellViewComponent.value = markRaw(FallbackComponent)
      isLoading.value = false
    }
  }

  // Watch for cell changes and reload view (object mode only)
  function deepEqual(a, b) {
    if (a === b) return true
    if (typeof a !== typeof b) return false
    if (typeof a !== 'object' || a === null || b === null) return false
    const aKeys = Object.keys(a)
    const bKeys = Object.keys(b)
    if (aKeys.length !== bKeys.length) return false
    for (const key of aKeys) {
      if (!bKeys.includes(key) || !deepEqual(a[key], b[key])) return false
    }
    return true
  }

  // Only watch in object mode (not class mode)
  if (!isCellClass) {
    watch(
      () => cell.value,
      (newCell, oldCell) => {
        log.debug('[OBJECT_MODE] cell.value reference changed', {
          hasNewCell: !!newCell,
          hasOldCell: !!oldCell
        })
        if (newCell && !deepEqual(newCell, oldCell)) {
          const cellType = getCellType(newCell)
          loadCellView(cellType)
        }
      },
      { immediate: true }
    )
  }

  // Load initial cell view on mount
  onMounted(async () => {
    if (isCellClass || isCellInstance) {
      // Execute class or instance mode (no await needed, but can be)
      executeClassOrInstanceMode()
    } else if (cell.value) {
      // Object/Ref mode: load from cell ref
      log.debug('[REF_MODE] Loading cell object on mount')
      const cellType = getCellType(cell.value)
      loadCellView(cellType)
    }
  })

  return {
    cellViewComponent,
    cellInstance,           // Instantiated cell instance
    isLoading,
    error,
    usesShowMethod,         // Indicates if using BaseCell.show() (preferred) or manual loading (fallback)
    loadCellView,           // Main orchestrator - tries show() first, then falls back to manual
    loadCellViewManually,   // Direct manual loading (for advanced use)
    tryShowMethod,          // Direct show() attempt (for advanced use)
    registerCellView,
    hasCellView,
    getCellType,
    isCellClassMode: isCellClass,     // Indicates class mode (input was a class)
    isCellInstanceMode: isCellInstance, // Indicates instance mode (input was already an instance)
  }
}

/**
 * Export utility functions for standalone use
 */
export {
  CELL_VIEW_PATHS,
  FallbackComponent,
  ErrorComponent,
  LoadingComponent,
}
