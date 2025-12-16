/**
 * useFileEditor Composable
 * 
 * Business logic for file editing operations in the File Editor cell type.
 * Handles file loading, saving, and state management.
 */

import { ref, computed, type Ref } from 'vue'
import apiService from '@/services/apiService.js'
import { ENDPOINTS } from '@/config/endpoints.js'
import { useCellsStore } from '@/stores/cells.js'
import { useChatStore } from '@/stores/chat.js'
import type { FileEditorCell, FileEditorCellData } from '@/types'

/**
 * Return type for useFileEditor composable
 */
export interface UseFileEditorReturn {
  /** File content as reactive string */
  fileContent: Ref<string>
  /** Loading state indicator */
  isLoading: Ref<boolean>
  /** Saving state indicator */
  isSaving: Ref<boolean>
  /** Error message if any */
  errorMessage: Ref<string | null>
  /** Success message if any */
  successMessage: Ref<string | null>
  /** File name computed from cell data */
  fileName: Ref<string>
  /** File path computed from cell data */
  filePath: Ref<string>
  /** Full file path (filePath/fileName) */
  fullPath: Ref<string>
  /** Load file content from backend */
  loadFile: () => Promise<void>
  /** Save file content to backend */
  saveFile: () => Promise<void>
  /** Delete ephemeral cell (close editor) */
  deleteEphemeral: () => void
  /** Send file to chat */
  sendToChat: () => void
}

/**
 * File Editor Composable
 * 
 * @param cell - The file editor cell instance (as a Ref)
 * @returns File editor state and methods
 */
export function useFileEditor(cell: Ref<FileEditorCell>): UseFileEditorReturn {
  // Use the cell ref directly without additional wrapping
  const cellRef = cell
  
  // Stores
  const cellsStore = useCellsStore()
  const chatStore = useChatStore()
  
  // State
  const fileContent = ref<string>('')
  const isLoading = ref<boolean>(false)
  const isSaving = ref<boolean>(false)
  const errorMessage = ref<string | null>(null)
  const successMessage = ref<string | null>(null)
  
  // Computed properties
  const fileName = computed<string>(() => {
    const data = cellRef.value?.initial_data as FileEditorCellData
    return data?.fileName || 'arquivo'
  })
  
  const filePath = computed<string>(() => {
    const data = cellRef.value?.initial_data as FileEditorCellData
    return data?.filePath || ''
  })
  
  const fullPath = computed<string>(() => {
    if (filePath.value) {
      return `${filePath.value}/${fileName.value}`
    }
    return fileName.value
  })
  
  /**
   * Load file content from backend
   */
  async function loadFile(): Promise<void> {
    isLoading.value = true
    errorMessage.value = null
    
    try {
      const folder = filePath.value
      const filename = fileName.value
      
      console.log('[FILE-EDITOR] Loading file:', { 
        folder, 
        filename, 
        folderLength: folder.length,
        fullPath: fullPath.value 
      })
      
      // Load file content from backend
      const url = `${ENDPOINTS.loadFile}?folder=${encodeURIComponent(folder)}&filename=${encodeURIComponent(filename)}`
      console.log('[FILE-EDITOR] Request URL:', url)
      
      const response = await apiService.fetch(url)
      
      if (!response.ok) {
        const errorText = await response.text()
        console.error('[FILE-EDITOR] ❌ File load failed:', { 
          status: response.status, 
          statusText: response.statusText,
          errorText 
        })
        throw new Error('Falha ao carregar arquivo')
      }
      
      const data = await response.json()
      console.log('[FILE-EDITOR] File loaded successfully, content length:', data.content?.length || 0)
      fileContent.value = data.content || ''
      
      // Sync to cell object via store for CellToolbar access
      if (cellRef.value) {
        cellsStore.updateCellData(cellRef.value.id, {
          content: fileContent.value,
          filename: fileName.value,
        })
      }
    } catch (error) {
      const err = error as Error
      console.error('Erro ao carregar arquivo:', err)
      errorMessage.value = `Erro ao carregar arquivo: ${err.message}`
    } finally {
      isLoading.value = false
    }
  }
  
  /**
   * Save file content to backend
   */
  async function saveFile(): Promise<void> {
    isSaving.value = true
    errorMessage.value = null
    successMessage.value = null
    
    try {
      const folder = filePath.value
      const filename = fileName.value
      
      // Save file content via backend API
      const response = await apiService.fetch(ENDPOINTS.saveFile, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          folder: folder,
          filename: filename,
          content: fileContent.value,
        }),
      })
      
      if (!response.ok) {
        throw new Error('Falha ao salvar arquivo')
      }
      
      successMessage.value = 'Arquivo salvo com sucesso!'
      
      // Notify file saved through store
      cellsStore.notifyFileSaved()
      
      // Clear success message after 3 seconds
      setTimeout(() => {
        successMessage.value = null
      }, 3000)
    } catch (error) {
      const err = error as Error
      console.error('Erro ao salvar arquivo:', err)
      errorMessage.value = `Erro ao salvar arquivo: ${err.message}`
    } finally {
      isSaving.value = false
    }
  }
  
  /**
   * Delete ephemeral cell (close editor, doesn't delete file)
   */
  function deleteEphemeral(): void {
    if (!confirm(`Fechar o editor do arquivo "${fileName.value}"? (O arquivo não será excluído)`)) {
      return
    }
    
    // Close cell view through store
    if (cellRef.value) {
      cellsStore.closeCellView(cellRef.value.id)
    }
  }
  
  /**
   * Send file content to chat as attachment
   */
  function sendToChat(): void {
    // chatStore.addAttachment expects (filename: string, content: string, type: string)
    // Note: Metadata like filePath is not supported in current API
    chatStore.addAttachment(
      fileName.value,
      fileContent.value,
      'text'
    )
  }
  
  return {
    fileContent,
    isLoading,
    isSaving,
    errorMessage,
    successMessage,
    fileName,
    filePath,
    fullPath,
    loadFile,
    saveFile,
    deleteEphemeral,
    sendToChat,
  }
}
