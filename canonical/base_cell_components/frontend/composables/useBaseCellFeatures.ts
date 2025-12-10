/**
 * @file useBaseCellFeatures.ts
 * @description Base cell features composable implementing BaseCellAPI
 * 
 * This composable provides common functionality for all cell types in the
 * Plug-and-Play architecture, including:
 * - Cell save operations
 * - Fragment management
 * - Dynamic subview management
 * - Error/success messaging
 * 
 * Part of Epic #1108 (Phase 2.1.2 Extension): Base Cell Architecture
 */

import { ref, computed, type Ref } from 'vue'
import type { BaseCellAPI, CellFragment, BaseCellFeaturesOptions, SubViewConfig, ParentCellContext } from '@/types/baseCell'
import { useNotebookStore } from '@/stores/useNotebookStore'
import { useCellsStore } from '@/stores/cells'
import { useChatStore } from '@/stores/chat'
import { useLayoutStore } from '@/stores/layout'
import apiService from '@/services/apiService.js'
import { ENDPOINTS } from '@/config/endpoints.js'

/**
 * Base cell features composable
 * 
 * Provides common functionality for all cell types following the BaseCellAPI interface.
 * This composable should be used as the foundation for cell-specific composables.
 * 
 * @param cellId - Cell ID (reactive)
 * @param cellType - Cell type identifier (reactive)
 * @param options - Configuration options
 * @returns BaseCellAPI implementation
 * 
 * @example
 * ```typescript
 * // In a cell-specific composable
 * const baseCellApi = useBaseCellFeatures(
 *   computed(() => props.cell.id),
 *   computed(() => 'unclassified-cell')
 * )
 * 
 * // Save cell
 * await baseCellApi.saveCell()
 * 
 * // Show fragments manager
 * baseCellApi.showCellFragmentsManager()
 * ```
 */
export function useBaseCellFeatures(
  cellId: Ref<string>,
  cellType: Ref<string>,
  options: BaseCellFeaturesOptions = {}
): BaseCellAPI {
  console.group('[useBaseCellFeatures] 🏗️ Initializing base cell features')
  console.log('📦 Cell ID:', cellId.value)
  console.log('🏷️ Cell Type:', cellType.value)
  console.log('⚙️ Options:', options)
  console.groupEnd()

  // ============================================================
  // Stores
  // ============================================================
  const notebookStore = useNotebookStore()
  const cellsStore = useCellsStore()
  const chatStore = useChatStore()
  const layoutStore = useLayoutStore()

  // ============================================================
  // State
  // ============================================================
  const isLoading = ref(false)
  const isSaving = ref(false)
  const errorMessage = ref<string | null>(null)
  const successMessage = ref<string | null>(null)
  
  // Subviews registry
  const subViews = ref<Map<string, SubViewConfig>>(new Map())
  
  // Track rendered subview instances
  const renderedSubViews = ref<Map<string, string>>(new Map()) // instanceId -> subViewId

  // Auto-clear timers
  let successTimer: ReturnType<typeof setTimeout> | null = null
  let errorTimer: ReturnType<typeof setTimeout> | null = null

  // ============================================================
  // Initialization
  // ============================================================
  
  // Auto-register the fragments-manager subview (built-in subview)
  // This is done immediately so it's always available
  const fragmentsManagerConfig: SubViewConfig = {
    id: 'fragments-manager',
    label: '📚 Gerenciador de Fragmentos',
    component: 'base_cell_components/frontend/views/BaseFragmentsManager.vue',
    renderMode: 'grid',
    gridPosition: {
      w: 6,
      h: 8,
    },
  }
  
  // Will be registered after methods are defined
  
  // ============================================================
  // Core Methods
  // ============================================================

  /**
   * Save cell data to backend
   */
  async function saveCell(): Promise<void> {
    console.group('[useBaseCellFeatures] 💾 Saving cell')
    console.log('📦 Cell ID:', cellId.value)
    console.log('🏷️ Cell Type:', cellType.value)

    if (!cellId.value) {
      console.warn('⚠️ Cannot save cell without ID')
      showError('Não é possível salvar célula sem ID')
      console.groupEnd()
      return
    }

    isSaving.value = true
    errorMessage.value = null
    successMessage.value = null

    try {
      // Use custom save handler if provided
      if (options.customSaveHandler) {
        console.log('🔧 Using custom save handler')
        await options.customSaveHandler()
      } else {
        console.log('📤 Using default save handler')
        
        // Get cell from notebook store
        const cell = notebookStore.cells[cellId.value]
        
        if (!cell) {
          throw new Error('Célula não encontrada no store')
        }

        console.log('📊 Cell data to save:', {
          id: cell.id,
          data: cell.data || cell.initial_data,
          fragments: cell.fragments?.length || 0
        })

        // Save cell to backend via API
        const response = await apiService.fetch(
          ENDPOINTS.updateCell(cellId.value),
          {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              initial_data: cell.data || cell.initial_data || {},
              fragments: cell.fragments || []
            }),
          }
        )

        if (!response.ok) {
          const errorText = await response.text()
          console.error('❌ Update cell failed:', {
            status: response.status,
            statusText: response.statusText,
            error: errorText,
          })
          throw new Error('Falha ao salvar célula no backend')
        }

        const updatedCell = await response.json()
        console.log('✅ Cell saved to backend:', updatedCell.id)
        
        // Update the cell in the store with the response from backend
        notebookStore.cells[cellId.value] = updatedCell
      }

      showSuccess('Célula salva com sucesso!')
      console.log('✅ Cell saved successfully')
    } catch (error: any) {
      console.error('❌ Error saving cell:', error)
      showError(error.message || 'Erro ao salvar célula')
      throw error // Re-throw to allow caller to handle
    } finally {
      isSaving.value = false
      console.groupEnd()
    }
  }

  /**
   * Close the cell view
   */
  function closeCell(): void {
    console.log('[useBaseCellFeatures] ❌ Closing cell:', cellId.value)
    
    if (!cellId.value) {
      console.warn('⚠️ Cannot close cell without ID')
      return
    }

    // Close cell through cells store
    cellsStore.closeCellView(cellId.value)
    
    // Also remove from layout if it's there
    layoutStore.removeCell(cellId.value)
  }

  /**
   * Show cell fragments manager as a dynamic subview
   * Uses the new subview rendering system
   * 
   * Passes the complete cell instance directly to the fragments manager
   * to avoid unnecessary backend fetches and ensure data consistency
   */
  function showCellFragmentsManager(): void {
    console.group('[useBaseCellFeatures] 📚 Showing fragments manager')
    console.log('📦 Cell ID:', cellId.value)
    console.log('🏷️ Cell Type:', cellType.value)

    if (!cellId.value) {
      console.warn('⚠️ Cannot show fragments manager without cell ID')
      showError('Não é possível abrir gerenciador sem ID da célula')
      console.groupEnd()
      return
    }

    try {
      // Get the complete cell instance from the store
      const cellInstance = notebookStore.cells[cellId.value]
      
      if (!cellInstance) {
        console.error('❌ Cell not found in store:', cellId.value)
        showError('Célula não encontrada no store')
        console.groupEnd()
        return
      }

      // Check if already open
      const existingInstanceId = `fragments-manager-${cellId.value}`
      if (layoutStore.getCellById(existingInstanceId)) {
        console.log('ℹ️ Fragments manager already open, focusing...')
        layoutStore.setActiveCellId(existingInstanceId)
        console.groupEnd()
        return
      }

      console.log('📦 Passing complete cell instance to fragments manager')

      // Use the new subview rendering system
      // Pass the complete cell instance directly as a prop
      const instanceId = renderSubView('fragments-manager', {
        cellInstance: cellInstance,  // Pass the complete cell object
        cellId: cellId.value,
      })
      
      if (!instanceId) {
        console.warn('⚠️ Failed to render fragments manager')
        console.groupEnd()
        return
      }
      
      console.log('✅ Fragments manager opened successfully with cell instance')
    } catch (error: any) {
      console.error('❌ Error opening fragments manager:', error)
      showError(error.message || 'Erro ao abrir gerenciador de fragmentos')
    }

    console.groupEnd()
  }

  /**
   * Add a new fragment to the cell
   * 
   * Note: This method does NOT automatically save the cell.
   * Fragments are added to the in-memory cell instance only.
   * The caller is responsible for persisting the cell if/when needed.
   */
  async function addFragment(fragmentData: CellFragment): Promise<void> {
    console.group('[useBaseCellFeatures] ➕ Adding fragment')
    console.log('📦 Cell ID:', cellId.value)
    console.log('🧩 Fragment data:', fragmentData)

    if (!cellId.value) {
      console.warn('⚠️ Cannot add fragment without cell ID')
      showError('Não é possível adicionar fragmento sem ID da célula')
      console.groupEnd()
      return
    }

    isLoading.value = true
    errorMessage.value = null

    try {
      // Get cell from notebook store
      const cell = notebookStore.cells[cellId.value]
      
      if (!cell) {
        // Cell not found in store - this indicates a state management issue
        // The cell should always be in the store if we have a valid cellId
        console.error('❌ Cell not found in notebook store:', cellId.value)
        console.error('Available cells:', Object.keys(notebookStore.cells))
        console.error('This indicates a state management issue - cell should exist in store')
        throw new Error('Célula não encontrada no store. Por favor, feche e reabra a célula.')
      }

      console.log('📋 Cell found in store:', cell.id)
      console.log('📊 Current fragments:', cell.fragments?.length || 0)

      // Initialize fragments array if it doesn't exist
      if (!cell.fragments) {
        console.log('🆕 Initializing fragments array')
        cell.fragments = []
      }

      // Add fragment to the cell in the store
      cell.fragments.push(fragmentData)

      console.log('✅ Fragment added to cell, total fragments:', cell.fragments.length)
      console.log('ℹ️ Fragment added to in-memory store only - not persisted to backend')
      console.log('💡 Cell will be persisted when user explicitly saves the cell')
      
      showSuccess('Fragmento adicionado com sucesso!')
    } catch (error: any) {
      console.error('❌ Error adding fragment:', error)
      showError(error.message || 'Erro ao adicionar fragmento')
    } finally {
      isLoading.value = false
      console.groupEnd()
    }
  }

  /**
   * Send a fragment to chat as an attachment
   */
  function sendFragmentToChat(fragment: CellFragment, index: number): void {
    console.group('[useBaseCellFeatures] 💬 Sending fragment to chat')
    console.log('📦 Cell ID:', cellId.value)
    console.log('🧩 Fragment index:', index)
    console.log('📝 Fragment type:', fragment.type)

    try {
      // Add fragment as attachment to chat
      chatStore.addAttachment({
        type: 'fragment',
        content: fragment.conteudo,
        metadata: {
          fragmentIndex: index,
          cellId: cellId.value,
          cellType: cellType.value,
          fragmentType: fragment.type,
        },
      })

      showSuccess(`Fragmento #${index + 1} enviado para o chat!`)
      console.log('✅ Fragment sent to chat')
    } catch (error: any) {
      console.error('❌ Error sending fragment to chat:', error)
      showError(error.message || 'Erro ao enviar fragmento para o chat')
    }

    console.groupEnd()
  }

  // ============================================================
  // Utility Methods
  // ============================================================

  /**
   * Show success message
   */
  function showSuccess(message: string, duration: number = 3000): void {
    console.log('[useBaseCellFeatures] ✅ Success:', message)
    
    // Clear any existing timer
    if (successTimer) {
      clearTimeout(successTimer)
    }
    
    successMessage.value = message
    errorMessage.value = null
    
    // Auto-clear after duration
    if (duration > 0) {
      successTimer = setTimeout(() => {
        successMessage.value = null
      }, duration)
    }
  }

  /**
   * Show error message
   */
  function showError(message: string): void {
    console.error('[useBaseCellFeatures] ❌ Error:', message)
    
    // Clear any existing timer
    if (errorTimer) {
      clearTimeout(errorTimer)
    }
    
    errorMessage.value = message
    successMessage.value = null
  }

  /**
   * Clear all messages
   */
  function clearMessages(): void {
    console.log('[useBaseCellFeatures] 🧹 Clearing messages')
    
    if (successTimer) {
      clearTimeout(successTimer)
      successTimer = null
    }
    
    if (errorTimer) {
      clearTimeout(errorTimer)
      errorTimer = null
    }
    
    successMessage.value = null
    errorMessage.value = null
  }

  // ============================================================
  // Subview Management Methods
  // ============================================================

  /**
   * Register a subview configuration
   */
  function registerSubView(config: SubViewConfig): void {
    console.group('[useBaseCellFeatures] 📋 Registering subview')
    console.log('🆔 Subview ID:', config.id)
    console.log('🏷️ Label:', config.label)
    console.log('🎨 Render mode:', config.renderMode)
    
    if (subViews.value.has(config.id)) {
      console.warn('⚠️ Subview already registered, updating configuration')
    }
    
    subViews.value.set(config.id, config)
    console.log('✅ Subview registered, total subviews:', subViews.value.size)
    console.groupEnd()
  }

  /**
   * Render a registered subview
   */
  function renderSubView(subViewId: string, props: Record<string, any> = {}): string | null {
    console.group('[useBaseCellFeatures] 🎨 Rendering subview')
    console.log('🆔 Subview ID:', subViewId)
    console.log('📦 Cell ID:', cellId.value)
    console.log('🎁 Additional props:', props)

    const config = subViews.value.get(subViewId)
    
    if (!config) {
      console.error('❌ Subview not registered:', subViewId)
      showError(`Subview "${subViewId}" não está registrada`)
      console.groupEnd()
      return null
    }

    try {
      // Generate unique instance ID using crypto.randomUUID() if available,
      // otherwise fallback to timestamp-based ID
      const instanceId = typeof crypto !== 'undefined' && crypto.randomUUID
        ? `${subViewId}-${cellId.value}-${crypto.randomUUID()}`
        : `${subViewId}-${cellId.value}-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
      
      console.log('🆔 Instance ID:', instanceId)
      console.log('🎨 Render mode:', config.renderMode)

      if (config.renderMode === 'grid') {
        // Render as grid item (existing behavior)
        const gridPosition = config.gridPosition || {}
        const added = layoutStore.addCell({
          cellId: instanceId,
          type: subViewId,
          title: config.label,
          position: gridPosition,
          state: {
            sourceCellId: cellId.value,
            cellType: cellType.value,
            ...config.defaultProps,
            ...props,
          },
        })

        if (added) {
          renderedSubViews.value.set(instanceId, subViewId)
          console.log('✅ Subview rendered as grid item')
          showSuccess(`${config.label} aberto!`)
        } else {
          console.warn('⚠️ Failed to render subview as grid item')
          showError(`Não foi possível abrir ${config.label}`)
          console.groupEnd()
          return null
        }
      } else if (config.renderMode === 'inline') {
        // For inline rendering, we just track the instance
        // The parent component is responsible for rendering the subview inline
        renderedSubViews.value.set(instanceId, subViewId)
        console.log('✅ Subview registered for inline rendering')
      } else if (config.renderMode === 'modal') {
        // Modal rendering can be implemented later
        console.warn('⚠️ Modal render mode not yet implemented')
        showError('Modo modal ainda não implementado')
        console.groupEnd()
        return null
      }

      console.groupEnd()
      return instanceId
    } catch (error: any) {
      console.error('❌ Error rendering subview:', error)
      showError(error.message || `Erro ao abrir ${config.label}`)
      console.groupEnd()
      return null
    }
  }

  /**
   * Close a rendered subview
   */
  function closeSubView(instanceId: string): void {
    console.group('[useBaseCellFeatures] 🔒 Closing subview')
    console.log('🆔 Instance ID:', instanceId)

    const subViewId = renderedSubViews.value.get(instanceId)
    
    if (!subViewId) {
      console.warn('⚠️ Subview instance not found:', instanceId)
      console.groupEnd()
      return
    }

    const config = subViews.value.get(subViewId)
    
    if (config?.renderMode === 'grid') {
      // Remove from layout
      layoutStore.removeCell(instanceId)
      console.log('✅ Subview removed from grid')
    }

    renderedSubViews.value.delete(instanceId)
    console.log('✅ Subview instance closed')
    console.groupEnd()
  }

  /**
   * Get parent cell context for subviews
   */
  function getParentContext(): ParentCellContext {
    const cell = notebookStore.cells[cellId.value]
    
    return {
      cellId: cellId.value,
      cellType: cellType.value,
      cellState: cell?.state,
      // Note: We don't pass cellApi here to avoid circular references
      // Subviews can use inject to get the parent API if needed
    }
  }

  // ============================================================
  // Auto-register built-in subviews
  // ============================================================
  
  // Register the fragments manager subview automatically
  registerSubView(fragmentsManagerConfig)
  console.log('[useBaseCellFeatures] ✅ Auto-registered fragments-manager subview')

  // ============================================================
  // Return API
  // ============================================================
  
  return {
    // Core Properties
    cellId: computed(() => cellId.value),
    cellType: computed(() => cellType.value),
    isLoading,
    isSaving,
    errorMessage,
    successMessage,
    subViews,
    
    // Core Methods
    saveCell,
    closeCell,
    showCellFragmentsManager,
    addFragment,
    sendFragmentToChat,
    
    // Subview Methods
    registerSubView,
    renderSubView,
    closeSubView,
    getParentContext,
    
    // Utility Methods
    showSuccess,
    showError,
    clearMessages,
  }
}
