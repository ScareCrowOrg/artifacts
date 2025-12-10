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
import apiService from '@/services/apiService.js'
import { ENDPOINTS } from '@/config/endpoints.js'

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
  saveCell: () => Promise<void>
  closeCell: () => void
  sendFragmentToChat: (fragment: any, index: number) => void
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
   * Makes an actual API call to persist the cell data
   */
  async function saveCell(): Promise<void> {
    console.group('[useUnclassifiedCell] 💾 Saving cell')
    
    if (!cell.value?.id) {
      console.warn('⚠️ Cannot save cell without ID')
      errorMessage.value = 'Não é possível salvar célula sem ID'
      console.groupEnd()
      return
    }

    isSaving.value = true
    errorMessage.value = null
    successMessage.value = null

    try {
      console.log('📤 Saving cell data:', cellData.value)
      console.log('📦 Cell ID:', cell.value.id)
      
      // Build the API endpoint
      const endpoint = ENDPOINTS.updateCell(cell.value.id)
      console.log('🌐 API endpoint:', endpoint)
      
      // Make the actual API call to persist data to backend
      const response = await apiService.fetch(endpoint, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          initial_data: cellData.value,
        }),
      })

      console.log('📡 Response status:', response.status)

      if (!response.ok) {
        const errorText = await response.text()
        console.error('❌ API call failed:', {
          status: response.status,
          statusText: response.statusText,
          error: errorText,
        })
        throw new Error(`Falha ao salvar célula: ${response.statusText}`)
      }

      const updatedCell = await response.json()
      console.log('✅ Cell saved successfully to backend:', updatedCell.id)
      
      // Update the in-memory cell object with the response
      if (cell.value) {
        Object.assign(cell.value, updatedCell)
      }
      
      // Update store with the persisted data
      cellsStore.updateCellData(cell.value.id, cellData.value)
      
      successMessage.value = 'Célula salva com sucesso!'
      console.log('✅ Success message displayed')
      
      // Clear success message after 3 seconds
      setTimeout(() => {
        successMessage.value = null
      }, 3000)
    } catch (error: any) {
      console.error('❌ Error saving cell:', error)
      errorMessage.value = error.message || 'Erro ao salvar célula'
    } finally {
      isSaving.value = false
      console.groupEnd()
    }
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
    console.group('[useUnclassifiedCell] 💬 Sending fragment to chat')
    console.log('📦 Fragment:', { index, type: fragment.type, contentLength: fragment.conteudo?.length })

    try {
      // Add fragment as attachment to chat
      chatStore.addAttachment({
        type: 'fragment',
        content: fragment.conteudo,
        metadata: {
          fragmentIndex: index,
          cellId: cell.value?.id,
          fragmentType: fragment.type,
        },
      })

      successMessage.value = `Fragmento #${index + 1} enviado para o chat!`
      console.log('✅ Fragment sent to chat')
      
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
    saveCell,
    closeCell,
    sendFragmentToChat,
    formatDate,
  }
}
