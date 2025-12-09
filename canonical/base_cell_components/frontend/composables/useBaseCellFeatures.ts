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
import type { BaseCellAPI, CellFragment, BaseCellFeaturesOptions } from '@/types/baseCell'
import { useNotebookStore } from '@/stores/useNotebookStore'
import { useCellsStore } from '@/stores/cells'
import { useChatStore } from '@/stores/chat'
import { useLayoutStore } from '@/stores/layout'

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

  // Auto-clear timers
  let successTimer: ReturnType<typeof setTimeout> | null = null
  let errorTimer: ReturnType<typeof setTimeout> | null = null

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

        // Trigger save through cells store
        // NOTE: This assumes the cell component is watching cellsStore.saveCellTrigger
        // and will handle the actual save operation
        cellsStore.triggerSaveCell()
        
        console.log('✅ Save triggered')
      }

      showSuccess('Célula salva com sucesso!')
      console.log('✅ Cell saved successfully')
    } catch (error: any) {
      console.error('❌ Error saving cell:', error)
      showError(error.message || 'Erro ao salvar célula')
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
      // Create a unique ID for the fragments manager view
      const fragmentsManagerId = `fragments-manager-${cellId.value}`
      
      console.log('🆔 Fragments Manager ID:', fragmentsManagerId)

      // Check if already open
      if (layoutStore.getCellById(fragmentsManagerId)) {
        console.log('ℹ️ Fragments manager already open, focusing...')
        layoutStore.setActiveCellId(fragmentsManagerId)
        console.groupEnd()
        return
      }

      // Add to layout as a new grid item
      const added = layoutStore.addCell({
        cellId: fragmentsManagerId,
        type: 'fragments-manager',
        title: `📚 Fragmentos - ${cellId.value}`,
        state: {
          sourceCellId: cellId.value,
          cellType: cellType.value,
        },
      })

      if (added) {
        console.log('✅ Fragments manager opened successfully')
        showSuccess('Gerenciador de fragmentos aberto!')
      } else {
        console.warn('⚠️ Failed to open fragments manager')
        showError('Não foi possível abrir o gerenciador de fragmentos')
      }
    } catch (error: any) {
      console.error('❌ Error opening fragments manager:', error)
      showError(error.message || 'Erro ao abrir gerenciador de fragmentos')
    }

    console.groupEnd()
  }

  /**
   * Add a new fragment to the cell
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
        throw new Error('Célula não encontrada')
      }

      // Initialize fragments array if it doesn't exist
      if (!cell.fragments) {
        cell.fragments = []
      }

      // Add fragment
      cell.fragments.push(fragmentData)

      console.log('✅ Fragment added, total fragments:', cell.fragments.length)
      
      // Trigger save to persist the change
      await saveCell()
      
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
    
    // Core Methods
    saveCell,
    closeCell,
    showCellFragmentsManager,
    addFragment,
    sendFragmentToChat,
    
    // Utility Methods
    showSuccess,
    showError,
    clearMessages,
  }
}
