/**
 * Cell View Resolver Composable
 * 
 * Provides dynamic resolution of Vue components for cell types using the
 * plug-and-play architecture. Automatically loads cell-specific views from
 * artifacts/canonical/cell_types/{type_id}/frontend/View.vue
 */

import { defineAsyncComponent } from 'vue'
import DefaultCellView from '@/components/DefaultCellView.vue'

// Configuration: base path for cell type artifacts
// This can be overridden if the directory structure changes
const CELL_TYPES_BASE_PATH = '../../../artifacts/canonical/cell_types'

// Cache for loaded views to avoid re-importing
const viewCache = new Map()

/**
 * Composable for resolving cell view components dynamically
 * 
 * @returns {Object} Object with resolveView function
 */
export function useCellViewResolver() {
  /**
   * Resolve a Vue component for the given cell type
   * 
   * @param {string} notebookItemTypeId - ID of the cell type
   * @returns {Component} Vue component (async or default)
   */
  function resolveView(notebookItemTypeId) {
    // Return cached view if available
    if (viewCache.has(notebookItemTypeId)) {
      return viewCache.get(notebookItemTypeId)
    }

    // Try to load cell-specific view dynamically
    const viewComponent = defineAsyncComponent({
      loader: async () => {
        try {
          // Dynamically import the View component from the cell type directory
          const module = await import(
            `${CELL_TYPES_BASE_PATH}/${notebookItemTypeId}/frontend/View.vue`
          )
          return module.default || module
        } catch (error) {
          console.warn(
            `No custom view found for cell type '${notebookItemTypeId}', using DefaultCellView`,
            error
          )
          // Return DefaultCellView as fallback
          return DefaultCellView
        }
      },
      errorComponent: DefaultCellView,
      loadingComponent: {
        template: '<div class="p-4 text-text-secondary">Loading cell view...</div>'
      },
      delay: 200,
      timeout: 3000
    })

    // Cache the component
    viewCache.set(notebookItemTypeId, viewComponent)

    return viewComponent
  }

  /**
   * Clear the view cache (useful for hot-reload during development)
   */
  function clearCache() {
    viewCache.clear()
  }

  /**
   * Get cache size (for debugging)
   */
  function getCacheSize() {
    return viewCache.size
  }

  return {
    resolveView,
    clearCache,
    getCacheSize
  }
}
