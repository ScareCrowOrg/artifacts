/**
 * Use Cell View Composable
 *
 * @deprecated This composable is part of the Classic Workspace and will be removed
 * in favor of useCellViewLoader for Dynamic Workspace.
 * See: docs/issues/classic-workspace-deprecation/sub-issues/07-refactor-usecellview.md
 *
 * Composable for managing dynamic cell view component loading based on NotebookItemType.
 * Uses notebook_item_type_id for all type identification.
 *
 * For new code, use:
 * - useCellViewLoader: Modern cell view loading with BaseCell support
 * - useCellDisplay: Utility functions for cell display (icons, names, etc.)
 */

import { ref, computed, watch } from 'vue'
import { useCellViewLoader } from './useCellViewLoader.js'
import { useCellDisplay } from './useCellDisplay.js'
import { getNotebookItemTypeId } from '../types/notebook.js'
import { createLogger } from '@/utils/logger'
import cellTypesService from '../services/cellTypesService.js'

const log = createLogger('cells:view')

export function useCellView(_activeCell) {
  const cellType = ref(null)
  const viewComponent = ref(null)
  const isLoading = ref(false)
  const error = ref(null)

  // Delegate to modern cell view loader for actual loading
  // Initialize with null to avoid undefined issues
  const cellRef = ref(_activeCell || null)
  const cellViewLoader = useCellViewLoader(cellRef)

  // Reactively sync loading state from loader
  watch(
    () => cellViewLoader.isLoading.value,
    (newValue) => {
      isLoading.value = newValue
    }
  )

  /**
   * Load cell type and determine view component
   * Delegates to useCellViewLoader for modern cell loading
   * 
   * @deprecated Use useCellViewLoader directly for new code
   */
  const loadCellView = async (cell) => {
    if (!cell) {
      viewComponent.value = null
      cellType.value = null
      return
    }

    const typeId = getNotebookItemTypeId(cell)
    if (!typeId) {
      viewComponent.value = null
      cellType.value = null
      return
    }

    // Update cell ref to trigger loader
    cellRef.value = cell

    try {
      // Fetch full cell type info for backward compatibility
      // This ensures cellType has icon, category, and other properties
      const fullCellType = await cellTypesService.getCellType(typeId)
      
      // Wait for loader to complete
      await cellViewLoader.loadCellView(typeId)

      // Sync state from loader
      viewComponent.value = cellViewLoader.cellViewComponent.value
      // Only sync error if loader encountered one
      if (cellViewLoader.error.value) {
        error.value = cellViewLoader.error.value
      }
      // Note: isLoading is already synced via watch
      
      // Set full cellType for backward compatibility
      // This ensures getCellIcon, isEphemeral, etc. work correctly
      cellType.value = fullCellType || {
        id: typeId,
        name: typeId,
        icon: '📦',
        category: 'persistida'
      }
    } catch (err) {
      log.error('Erro ao carregar view da célula:', err)
      error.value = err.message
      viewComponent.value = null
      cellType.value = null
    }
  }

  // Use useCellDisplay for utility functions
  const cellDisplay = useCellDisplay()

  /**
   * Get display name for cell (uses initial_data for cells, name for books).
   * @deprecated Use useCellDisplay().getCellDisplayName() instead
   */
  const getCellDisplayName = (cell) => {
    return cellDisplay.getCellDisplayName(cell)
  }

  /**
   * Get icon for cell type
   * @deprecated Use useCellDisplay().getCellIcon() instead
   * 
   * Note: Returns cellType icon if available, otherwise default.
   * For full functionality, migrate to useCellDisplay which requires cell object.
   */
  const getCellIcon = computed(() => {
    return cellType.value?.icon || '📦'
  })

  /**
   * Check if cell is ephemeral
   * @deprecated Check cellType.category === 'efemera' directly or use useCellDisplay
   * 
   * Note: This logic remains for backward compatibility until classic workspace removal.
   */
  const isEphemeral = computed(() => {
    return cellType.value?.category === 'efemera'
  })

  /**
   * Get cell category badge
   * @deprecated Use useCellDisplay().getCellCategory() instead
   * 
   * Note: This logic remains for backward compatibility until classic workspace removal.
   */
  const getCategoryBadge = computed(() => {
    if (!cellType.value) return ''
    return cellType.value.category === 'efemera'
      ? '⚡ Efêmera'
      : '💾 Persistida'
  })

  return {
    cellType,
    viewComponent,
    isLoading,
    error,
    loadCellView,
    getCellDisplayName,
    getCellIcon,
    isEphemeral,
    getCategoryBadge,
  }
}
