/**
 * @file useUnclassifiedCell.ts
 * @description Composable for managing unclassified cell state and operations
 * 
 * This composable handles:
 * - Cell data loading and initialization
 * - Content editing and validation
 * - Fragment viewing (read-only)
 * - Integration with stores
 * - State management
 * 
 * Part of Phase 2.1.2: Unclassified Cell Migration (Epic #1108)
 */

import { ref, computed, watch, type Ref } from 'vue'
import { useCellsStore } from '@/stores/cells'
import { useChatStore } from '@/stores/chat'

/**
 * Interface for unclassified cell data structure
 */
export interface UnclassifiedCellData {
  title: string
  content: string
  category?: string
  icon?: string
}

/**
 * Interface for unclassified cell object
 */
export interface UnclassifiedCell {
  id: string
  notebook_item_type_id?: string
  type?: string
  initial_data?: UnclassifiedCellData
  data?: UnclassifiedCellData
  fragments?: Array<{
    type: string
    conteudo: string
    [key: string]: any
  }>
  created_at?: string
  updated_at?: string
  [key: string]: any
}

/**
 * Composable return interface
 */
export interface UseUnclassifiedCellReturn {
  // State
  cellData: Ref<UnclassifiedCellData>
  isLoading: Ref<boolean>
  isSaving: Ref<boolean>
  errorMessage: Ref<string | null>
  successMessage: Ref<string | null>
  
  // Computed
  isNewCell: Ref<boolean>
  memoryFragments: Ref<Array<any>>
  fragmentCount: Ref<number>
  
  // Methods
  loadCellData: () => void
  saveCell?: () => Promise<void>  // Optional for backward compatibility
  prepareForSave: () => UnclassifiedCell
  startSaving: () => void
  onSaveComplete: () => void
  onSaveError: (error: Error) => void
  closeCell: () => void
  sendFragmentToChat: (fragment: any, index: number) => void
  sendCellToChat: () => void  // ITERATION 3: Added for main view Send to Chat
  formatDate: (dateString: string | undefined) => string
}

/**
 * Composable for unclassified cell management
 * @param cell - Reactive reference to the cell object
 * @returns Composable interface with state and methods
 */
export function useUnclassifiedCell(cell: Ref<UnclassifiedCell | null>): UseUnclassifiedCellReturn {
  console.group('[useUnclassifiedCell] 🏗️ Initializing composable')
  console.log('📦 Cell:', cell.value?.id || 'NEW')
  console.groupEnd()

  // Stores
  const cellsStore = useCellsStore()
  const chatStore = useChatStore()

  // State
  const cellData = ref<UnclassifiedCellData>({
    title: '',
    content: '',
    category: 'persistida',
    icon: 'mdi-text-box',
  })

  const isLoading = ref(false)
  const isSaving = ref(false)
  const errorMessage = ref<string | null>(null)
  const successMessage = ref<string | null>(null)

  /**
   * Computed - Check if this is a new cell
   */
  const isNewCell = computed(() => {
    const result = !cell.value || !cell.value.id
    console.log('[useUnclassifiedCell] 🆕 Is new cell?', result)
    return result
  })

  /**
   * Computed - Get memory fragments from cell
   */
  const memoryFragments = computed(() => {
    console.group('[useUnclassifiedCell] 🧩 Computing memory fragments')
    
    const cellFragments = cell.value?.fragments
    if (!cellFragments || !Array.isArray(cellFragments)) {
      console.log('⚠️ No fragments found')
      console.groupEnd()
      return []
    }

    // Filter only "memoria" type fragments
    const memoriaFragments = cellFragments.filter((f: any) => f.type === 'memoria')
    console.log(`✅ Found ${memoriaFragments.length} memoria fragments out of ${cellFragments.length} total`)
    console.groupEnd()
    
    return memoriaFragments
  })

  /**
   * Computed - Fragment count
   */
  const fragmentCount = computed(() => {
    return memoryFragments.value.length
  })

  /**
   * Load cell data from cell object
   */
  function loadCellData(): void {
    console.group('[useUnclassifiedCell] 📥 Loading cell data')
    
    if (!cell.value) {
      console.log('⚠️ No cell provided, using defaults')
      console.groupEnd()
      return
    }

    console.log('📊 Cell object:', {
      id: cell.value.id,
      hasInitialData: !!cell.value.initial_data,
      hasData: !!cell.value.data,
      fragmentCount: cell.value.fragments?.length || 0
    })

    try {
      // Support both initial_data (new) and data (legacy) fields
      const data = cell.value.initial_data || cell.value.data || {}
      
      cellData.value = {
        title: data.title || '',
        content: data.content || '',
        category: data.category || 'persistida',
        icon: data.icon || 'mdi-text-box',
      }

      console.log('✅ Cell data loaded:', cellData.value)
    } catch (error) {
      console.error('❌ Error loading cell data:', error)
      errorMessage.value = 'Erro ao carregar dados da célula'
    }
    
    console.groupEnd()
  }

  /**
   * Save cell data to backend
   * 
   * FIX for Issue #1206: This now returns the updated cell data
   * to be used by the caller (View component) which will pass it
   * to baseCellApi.saveCell() with the cell instance.
   * 
   * This removes the dependency on global "active cell" and store indirection.
   */
  function prepareForSave(): UnclassifiedCell {
    console.group('[useUnclassifiedCell] 📦 Preparing cell data for save')
    
    errorMessage.value = null
    successMessage.value = null

    try {
      console.log('📤 Preparing cell data:', cellData.value)
      console.log('📦 Cell ID:', cell.value?.id || 'NEW CELL')
      console.log('🧩 Fragments count:', cell.value?.fragments?.length || 0)
      
      // Create updated cell object with new data
      const updatedCell: UnclassifiedCell = {
        ...cell.value,
        initial_data: cellData.value,
        data: cellData.value, // Also update legacy data field
      }
      
      console.log('✅ Cell prepared for save')
      console.groupEnd()
      
      return updatedCell
    } catch (error: any) {
      console.error('❌ Error preparing cell:', error)
      errorMessage.value = error.message || 'Erro ao preparar salvamento'
      console.groupEnd()
      throw error
    }
  }
  
  /**
   * Start save operation (show loading state)
   */
  function startSaving(): void {
    isSaving.value = true
    errorMessage.value = null
    successMessage.value = null
  }
  
  /**
   * Handle save completion
   * Called by View component after successful save
   */
  function onSaveComplete(): void {
    console.log('[useUnclassifiedCell] ✅ Save completed successfully')
    successMessage.value = 'Célula salva com sucesso!'
    isSaving.value = false
  }
  
  /**
   * Handle save error
   * Called by View component if save fails
   */
  function onSaveError(error: any): void {
    console.error('[useUnclassifiedCell] ❌ Save failed:', error)
    errorMessage.value = error.message || 'Erro ao salvar célula'
    isSaving.value = false
  }

  /**
   * Close cell view
   */
  function closeCell(): void {
    console.log('[useUnclassifiedCell] ❌ Closing cell:', cell.value?.id)
    
    if (!cell.value?.id) {
      console.warn('⚠️ Cannot close cell without ID')
      return
    }

    // Close cell view through store
    cellsStore.closeCellView(cell.value.id)
  }

  /**
   * Send fragment to chat
   * @param fragment - Fragment object to send
   * @param index - Fragment index
   */
  function sendFragmentToChat(fragment: any, index: number): void {
    console.group('[useUnclassifiedCell] 💬 sendFragmentToChat - DEBUG ITERATION 1')
    console.log('📦 Fragment:', { 
      index, 
      type: fragment.type, 
      contentLength: fragment.conteudo?.length,
      fragment_keys: Object.keys(fragment || {})
    })

    try {
      // Default fragment type constant
      const DEFAULT_FRAGMENT_TYPE = 'unknown'
      
      // Create descriptive filename for the fragment
      const fragmentName = `Fragment #${index + 1} - ${fragment.type || DEFAULT_FRAGMENT_TYPE}`
      
      console.log('[useUnclassifiedCell] 🚀 Calling chatStore.addAttachment with:', {
        fragmentName,
        contentLength: (fragment.conteudo || '').length,
        type: 'text'
      })
      
      // Add fragment as attachment to chat with correct signature
      // chatStore.addAttachment expects (filename: string, content: string, type: string)
      const success = chatStore.addAttachment(
        fragmentName,
        fragment.conteudo || '',
        'text'
      )

      console.log('[useUnclassifiedCell] Result:', success)

      if (success) {
        successMessage.value = `Fragmento #${index + 1} enviado para o chat!`
        console.log('✅ Fragment sent to chat')
      } else {
        throw new Error('Failed to add attachment to chat')
      }
      
      // Clear success message after 3 seconds
      setTimeout(() => {
        successMessage.value = null
      }, 3000)
    } catch (error: any) {
      console.error('❌ Error sending fragment to chat:', error)
      errorMessage.value = error.message || 'Erro ao enviar fragmento para o chat'
    }
    
    console.groupEnd()
  }

  /**
   * Send cell content to chat as attachment
   * ITERATION 3: Added for main view Send to Chat functionality
   */
  function sendCellToChat(): void {
    console.group('[useUnclassifiedCell] 💬 sendCellToChat - ITERATION 3')
    console.log('📦 Cell data:', {
      title: cellData.value.title,
      contentLength: cellData.value.content?.length,
    })

    try {
      // Create filename from title
      const fileName = cellData.value.title 
        ? `${cellData.value.title}.md`
        : 'Célula Sem Título.md'
      
      // Create content with title and content
      const fullContent = cellData.value.title
        ? `# ${cellData.value.title}\n\n${cellData.value.content || ''}`
        : cellData.value.content || ''
      
      console.log('[useUnclassifiedCell] 🚀 Calling chatStore.addAttachment with:', {
        fileName,
        contentLength: fullContent.length,
        type: 'text'
      })
      
      // Send to chat with correct API signature
      const success = chatStore.addAttachment(
        fileName,
        fullContent,
        'text'
      )

      console.log('[useUnclassifiedCell] Result:', success)

      if (success) {
        successMessage.value = 'Célula enviada para o chat!'
        console.log('✅ Cell sent to chat')
      } else {
        throw new Error('Failed to add cell to chat')
      }
      
      // Clear success message after 3 seconds
      setTimeout(() => {
        successMessage.value = null
      }, 3000)
    } catch (error: any) {
      console.error('❌ Error sending cell to chat:', error)
      errorMessage.value = error.message || 'Erro ao enviar célula para o chat'
    }
    
    console.groupEnd()
  }

  /**
   * Format date string for display
   * @param dateString - ISO date string
   * @returns Formatted date string
   */
  function formatDate(dateString: string | undefined): string {
    if (!dateString) return ''
    
    try {
      const date = new Date(dateString)
      return date.toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch (error) {
      console.error('[useUnclassifiedCell] ❌ Error formatting date:', error)
      return ''
    }
  }

  // Watch for cell data changes and update store
  // NOTE: This updates the store's in-memory representation only.
  // Actual persistence happens when saveCell() is called.
  // The deep watch is necessary for nested object changes (title, content).
  watch(cellData, (newData) => {
    console.log('[useUnclassifiedCell] 🔄 Cell data changed (in-memory update):', newData)
    
    // Update cell data in store (in-memory only, no API call)
    if (cell.value?.id) {
      cellsStore.updateCellData(cell.value.id, newData)
    }
  }, { deep: true, flush: 'post' })

  // Load cell data on initialization
  loadCellData()

  // Return composable interface
  return {
    // State
    cellData,
    isLoading,
    isSaving,
    errorMessage,
    successMessage,
    
    // Computed
    isNewCell,
    memoryFragments,
    fragmentCount,
    
    // Methods
    loadCellData,
    prepareForSave,
    startSaving,
    onSaveComplete,
    onSaveError,
    closeCell,
    sendFragmentToChat,
    sendCellToChat,  // ITERATION 3: Added
    formatDate,
  }
}
