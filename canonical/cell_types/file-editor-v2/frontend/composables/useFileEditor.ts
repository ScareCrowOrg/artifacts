/**
 * useFileEditor Composable
 * 
 * Business logic for file editing operations in the File Editor cell type.
 * Handles file loading, saving, and state management.
 */

import { ref, computed, watch, type Ref } from 'vue'
import apiService from '#shared/apiService.js'
import { ENDPOINTS } from '#shared/endpoints.js'
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
  /** Save file content to backend using current cell data */
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
      // ITERATION 3 FIX: Check if content is pre-provided (e.g., from manual-capture-cell)
      const cellData = cellRef.value?.initial_data as FileEditorCellData
      
      if (cellData?.content !== undefined && cellData?.content !== null) {
        // Content was pre-provided - use it directly without backend call
        // This supports creating new files with initial content (manual-capture-cell use case)
        console.log('[FILE-EDITOR] 🔍 DEBUG ITERATION 3 - Using pre-provided content')
        console.log('[FILE-EDITOR] Pre-provided content length:', cellData.content.length)
        console.log('[FILE-EDITOR] Skipping backend load for new file creation')
        
        fileContent.value = cellData.content
        
        // Sync to cell object via store for CellToolbar access
        if (cellRef.value) {
          cellsStore.updateCellData(cellRef.value.id, {
            content: fileContent.value,
            filename: fileName.value,
          })
        }
        
        isLoading.value = false
        return  // Early return - skip backend load
      }
      
      // No pre-provided content - load from backend (existing file scenario)
      console.log('[FILE-EDITOR] 🔍 DEBUG ITERATION 3 - No pre-provided content, loading from backend')
      
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
      
      const responseData = await response.json()
      console.log('[FILE-EDITOR] File loaded successfully, content length:', responseData.content?.length || 0)
      fileContent.value = responseData.content || ''
      
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
   * Save file content to backend using current cell data
   * This reads filename and path from cell's initial_data which is updated by the View
   */
  async function saveFile(): Promise<void> {
    isSaving.value = true
    errorMessage.value = null
    successMessage.value = null
    
    try {
      // Get current filename and path from cell data (may have been edited)
      const currentData = cellRef.value?.initial_data as FileEditorCellData
      const folder = currentData?.filePath || filePath.value
      const filename = currentData?.fileName || fileName.value
      
      console.log('[FILE-EDITOR] Saving file with current values:', {
        folder,
        filename,
        fullPath: folder ? `${folder}/${filename}` : filename,
        contentLength: fileContent.value.length
      })
      
      // Validate filename
      if (!filename || !filename.trim()) {
        errorMessage.value = 'Nome do arquivo não pode estar vazio'
        isSaving.value = false
        return
      }
      
      // Save file content via backend API
      const response = await apiService.fetch(ENDPOINTS.saveFile, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          folder: folder,
          filename: filename.trim(),
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
    console.group('[useFileEditor] 📤 sendToChat - DEBUG ITERATION 1')
    console.log('File info:', {
      fileName: fileName.value,
      filePath: filePath.value,
      fullPath: fullPath.value,
      contentLength: fileContent.value?.length,
    })
    
    // chatStore.addAttachment expects (filename: string, content: string, type: string)
    // Note: Using 'text' type for consistency across all cell types.
    // The chat system currently treats all attachments uniformly regardless of type.
    // Metadata like filePath is not supported in current API.
    console.log('[useFileEditor] 🚀 Calling chatStore.addAttachment with:', {
      filename: fileName.value,
      contentLength: fileContent.value?.length,
      type: 'text'
    })
    
    const result = chatStore.addAttachment(
      fileName.value,
      fileContent.value,
      'text'
    )
    
    console.log('[useFileEditor] Result:', result)
    console.groupEnd()
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
