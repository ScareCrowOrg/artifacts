/**
 * useFileManager Composable
 * 
 * Provides file management functionality for the FileManagerCell.
 * Handles file tree loading, selection, search, and file operations.
 */

import { ref, computed, type Ref } from 'vue'
import type {
  FileManagerCell,
  FileTreeNode,
  UseFileManagerReturn,
  FileOperationResult
} from '../types'
import { ENDPOINTS } from '@/config/endpoints'
import apiService, { SessionExpiredError } from '@/services/apiService'
import { useDynamicLayout } from '@/composables/useDynamicLayout'
import { useNotebookStore } from '@/stores/useNotebookStore'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'

// Global state to prevent concurrent refresh operations across all FileManagerCell instances
// This prevents infinite loops when async component loading causes component re-creation
let globalRefreshInProgress = false
let globalRefreshPromise: Promise<FileTreeNode[]> | null = null
let cachedTreeData: FileTreeNode[] = []

/**
 * File Manager composable
 * 
 * @param cell - The file manager cell instance (reactive ref)
 * @returns File manager state and actions
 */
export function useFileManager(cell: Ref<FileManagerCell>): UseFileManagerReturn {
  // Composables & Stores
  const { addCell } = useDynamicLayout()
  const notebookStore = useNotebookStore()
  const authStore = useAuthStore()
  
  // State
  const tree = ref<FileTreeNode[]>([])
  const selectedFiles = ref<string[]>(cell.value.initial_data?.selectedFiles || [])
  const expandedPaths = ref<Set<string>>(new Set(cell.value.initial_data?.expandedPaths || []))
  const searchQuery = ref<string>(cell.value.initial_data?.searchQuery || '')
  const isLoading = ref<boolean>(false)
  const errorMessage = ref<string>('')
  const successMessage = ref<string>('')
  
  // Computed
  const selectedCount = computed<number>(() => selectedFiles.value.length)
  
  const displayTree = computed<FileTreeNode[]>(() => {
    if (!searchQuery.value || searchQuery.value.trim() === '') {
      return tree.value
    }
    return filterTree(tree.value, searchQuery.value.toLowerCase())
  })
  
  const hasNoMatches = computed<boolean>(() => {
    return searchQuery.value.trim() !== '' && displayTree.value.length === 0
  })
  
  // Note: FileManagerCell is ephemeral and should NOT persist state changes.
  // State like selectedFiles, searchQuery, expandedPaths are kept in memory only.
  
  /**
   * Filter tree nodes by search query
   */
  function filterTree(nodes: FileTreeNode[], query: string): FileTreeNode[] {
    const result: FileTreeNode[] = []
    
    for (const node of nodes) {
      const nameMatch = node.name.toLowerCase().includes(query)
      const childMatches = node.children ? filterTree(node.children, query) : []
      
      if (nameMatch || childMatches.length > 0) {
        result.push({
          ...node,
          children: childMatches.length > 0 ? childMatches : node.children
        })
      }
    }
    
    return result
  }
  
  /**
   * Build hierarchical tree from flat list
   */
  function buildTreeFromFlatList(items: any[]): FileTreeNode[] {
    const nodeMap = new Map<string, FileTreeNode>()
    const root: FileTreeNode[] = []
    
    // Create all nodes and map by path
    for (const item of items) {
      // Skip actions-runner directories
      if (
        item.path.startsWith('actions-runner') ||
        item.path.startsWith('actions-runner-tests')
      ) {
        continue
      }
      
      const isDirectory = item.type === 'directory' || item.path.endsWith('/')
      const node: FileTreeNode = {
        name: item.name,
        path: item.path,
        isDirectory,
        children: [],
        loaded: true,
        size: item.size,
        modified: item.modified
      }
      nodeMap.set(item.path.replace(/\/$/, ''), node)
    }
    
    // Build hierarchy
    for (const item of items) {
      const path = item.path.replace(/\/$/, '')
      if (
        path.startsWith('actions-runner') ||
        path.startsWith('actions-runner-tests')
      ) {
        continue
      }
      
      const parts = path.split('/')
      if (parts.length === 1) {
        // Root level
        const node = nodeMap.get(path)
        if (node) root.push(node)
      } else {
        // Has parent
        const parentPath = parts.slice(0, -1).join('/')
        const parentNode = nodeMap.get(parentPath)
        const node = nodeMap.get(path)
        if (parentNode && node) {
          parentNode.children?.push(node)
        } else if (node) {
          // Fallback: add to root if parent not found
          root.push(node)
        }
      }
    }
    
    // Sort nodes recursively
    const sortNodes = (nodes: FileTreeNode[]) => {
      nodes.sort((a, b) => {
        if (a.isDirectory !== b.isDirectory) {
          return a.isDirectory ? -1 : 1
        }
        return a.name.localeCompare(b.name)
      })
      nodes.forEach(node => {
        if (node.children) {
          sortNodes(node.children)
        }
      })
    }
    sortNodes(root)
    
    return root
  }
  
  /**
   * Load or refresh the file tree with cache invalidation
   * Protected against concurrent calls to prevent infinite loops
   * Uses a global guard to prevent multiple component instances from refreshing simultaneously
   */
  async function refreshTree(): Promise<void> {
    const timestamp = new Date().toISOString()
    
    console.group(`[useFileManager] 🔄 refreshTree() called at ${timestamp}`)
    console.log('globalRefreshInProgress:', globalRefreshInProgress)
    console.log('isLoading:', isLoading.value)
    console.trace('Call stack trace')
    
    // Global guard: If ANY instance is already refreshing, wait for it
    if (globalRefreshInProgress) {
      console.warn('[FileManagerCell] ⚠️ Global refresh already in progress - reusing existing refresh')
      
      // Wait for the ongoing refresh to complete, then update local state from cache
      if (globalRefreshPromise) {
        try {
          const treeData = await globalRefreshPromise
          tree.value = treeData
          console.log('[FileManagerCell] ✅ Global refresh completed, local state updated from cache')
        } catch (err) {
          console.error('[FileManagerCell] ❌ Global refresh failed:', err)
          errorMessage.value = '❌ Erro ao carregar árvore de arquivos'
        }
      }
      console.groupEnd()
      return
    }
    
    console.log('✅ Guard passed - proceeding with refresh')
    globalRefreshInProgress = true
    isLoading.value = true
    errorMessage.value = ''
    successMessage.value = ''
    
    // Create a promise that other instances can await
    globalRefreshPromise = (async (): Promise<FileTreeNode[]> => {
      try {
        // Step 1: Invalidate backend cache
        console.log('📡 Step 1: Calling tree-refresh endpoint...')
        const refreshUrl = `${ENDPOINTS.treeRefresh}`
        await apiService.fetch(refreshUrl, { method: 'POST' })
        console.log('✅ Cache refresh completed')
        
        // Step 2: Load fresh tree data
        console.log('📡 Step 2: Loading tree data...')
        const url = `${ENDPOINTS.tree}?format=flat&include_hidden=true`
        const response = await apiService.fetch(url)
        const data = await response.json()
        
        const items = data.data || []
        console.log(`📊 Loaded ${items.length} items from backend`)
        const treeData = buildTreeFromFlatList(items)
        console.log(`🌳 Built tree with ${treeData.length} root nodes`)
        
        // Update local state and cache
        tree.value = treeData
        cachedTreeData = treeData
        
        successMessage.value = '✅ Árvore de arquivos atualizada'
        setTimeout(() => {
          successMessage.value = ''
        }, 2000)
        
        return treeData
      } catch (err) {
        console.error('❌ Error during refresh:', err)
        if (err instanceof SessionExpiredError) {
          throw err
        }
        errorMessage.value = '❌ Erro ao carregar árvore de arquivos'
        console.error('Error loading file tree:', err)
        throw err
      } finally {
        // Reset global state FIRST to prevent race conditions
        globalRefreshInProgress = false
        globalRefreshPromise = null
        isLoading.value = false
        console.log('🏁 refreshTree() completed')
        console.groupEnd()
      }
    })()
    
    await globalRefreshPromise
  }
  
  /**
   * Toggle file selection
   */
  function toggleSelection(path: string): void {
    const index = selectedFiles.value.indexOf(path)
    if (index >= 0) {
      selectedFiles.value.splice(index, 1)
    } else {
      selectedFiles.value.push(path)
    }
  }
  
  /**
   * Clear all selections
   */
  function clearSelection(): void {
    selectedFiles.value = []
  }
  
  /**
   * Toggle directory expansion
   */
  function toggleExpanded(path: string): void {
    const newExpandedPaths = new Set(expandedPaths.value)
    if (newExpandedPaths.has(path)) {
      newExpandedPaths.delete(path)
    } else {
      newExpandedPaths.add(path)
    }
    expandedPaths.value = newExpandedPaths
  }
  
  /**
   * Collapse all directories
   */
  function collapseAll(): void {
    expandedPaths.value = new Set()
  }
  
  /**
   * Update search query
   */
  function updateSearchQuery(query: string): void {
    searchQuery.value = query
  }
  
  /**
   * Open selected files in FileEditorCell instances
   */
  async function openSelectedFiles(): Promise<void> {
    if (selectedFiles.value.length === 0) {
      errorMessage.value = '❌ Nenhum arquivo selecionado'
      return
    }
    
    try {
      // Get current user ID
      const userId = authStore.user?.id || notebookStore.getUserId()
      
      if (!userId) {
        throw new Error('User not authenticated')
      }
      
      console.log('[FILE-MANAGER] Opening files:', selectedFiles.value)
      
      // Create ephemeral FileEditorCell instances for each selected file (client-side only)
      // Note: file-editor-v2 cells are ephemeral - they are UI components for editing files,
      // not persistent entities. The Save button saves FILE content, not the cell itself.
      for (const filePath of selectedFiles.value) {
        console.log('[FILE-MANAGER] Processing file path:', filePath)
        
        // Extract file name and directory
        const parts = filePath.split('/')
        const fileName = parts[parts.length - 1]
        const dirPath = parts.slice(0, -1).join('/')
        
        console.log('[FILE-MANAGER] Path extraction:', { 
          filePath, 
          parts, 
          fileName, 
          dirPath,
          dirPathLength: dirPath.length 
        })
        
        // Only open files, not directories
        const node = findNodeByPath(tree.value, filePath)
        if (node && !node.isDirectory) {
          // Create ephemeral cell client-side (no backend call, no DB persistence)
          const ephemeralCellId = `ephemeral-file-editor-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
          
          const initial_data = {
            fileName,
            filePath: dirPath,  // Use actual directory path (empty string for root)
            language: getLanguageFromExtension(fileName),
            readOnly: false,
            icon: '📄'
          }
          
          const ephemeralCell = {
            id: ephemeralCellId,
            notebook_item_type_id: 'file-editor-v2',
            assignee_id: userId,
            initial_data,
            category: 'ephemeral',
            status: 'PENDING',
            fragments: [],
            refs: {},
          }
          
          console.log('[FILE-MANAGER] Created ephemeral cell (client-side, not persisted):', {
            cellId: ephemeralCell.id,
            initial_data: ephemeralCell.initial_data
          })
          
          // Add to local layout
          const cellData = {
            cellId: ephemeralCell.id,
            type: ephemeralCell.notebook_item_type_id,
            title: fileName,
            state: {
              cellInstance: ephemeralCell,
              initial_data: ephemeralCell.initial_data,
            }
          }
          
          addCell(cellData)
          
          // Add to notebook store (in-memory only, not persisted)
          notebookStore.cells[ephemeralCell.id] = ephemeralCell
        }
      }
      
      successMessage.value = `✅ ${selectedFiles.value.length} arquivo(s) aberto(s)`
      setTimeout(() => {
        successMessage.value = ''
      }, 2000)
      
      // Clear selection after opening
      clearSelection()
    } catch (err) {
      errorMessage.value = '❌ Erro ao abrir arquivos'
      console.error('Error opening files:', err)
    }
  }
  
  /**
   * Find tree node by path
   */
  function findNodeByPath(nodes: FileTreeNode[], path: string): FileTreeNode | null {
    for (const node of nodes) {
      if (node.path === path) {
        return node
      }
      if (node.children) {
        const found = findNodeByPath(node.children, path)
        if (found) return found
      }
    }
    return null
  }
  
  /**
   * Get language/syntax from file extension
   */
  function getLanguageFromExtension(fileName: string): string {
    const ext = fileName.split('.').pop()?.toLowerCase()
    const langMap: Record<string, string> = {
      'md': 'markdown',
      'js': 'javascript',
      'ts': 'typescript',
      'vue': 'vue',
      'py': 'python',
      'json': 'json',
      'yaml': 'yaml',
      'yml': 'yaml',
      'html': 'html',
      'css': 'css',
      'sh': 'shell'
    }
    return langMap[ext || ''] || 'plaintext'
  }
  
  /**
   * Create new file
   */
  async function createNewFile(fileName: string, folder: string = 'docs'): Promise<void> {
    if (!fileName || !fileName.trim()) {
      errorMessage.value = '❌ Nome do arquivo é obrigatório'
      return
    }
    
    try {
      // Get current user ID
      const userId = authStore.user?.id || notebookStore.getUserId()
      
      if (!userId) {
        throw new Error('User not authenticated')
      }
      
      // Step 1: Create cell in backend
      // Note: FileEditorCell is persistent (NOT ephemeral) so users can resume
      // editing after page refresh. The `category` field is intentionally omitted.
      const createResponse = await apiService.fetch(ENDPOINTS.createCell, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          notebook_item_type_id: 'file-editor-v2',
          assignee_id: userId,
          initial_data: {
            fileName: fileName.trim(),
            filePath: folder,
            language: getLanguageFromExtension(fileName),
            readOnly: false,
            icon: '📄'
          }
        })
      })
      
      if (!createResponse.ok) {
        const errorText = await createResponse.text()
        console.error('❌ Backend cell creation failed:', errorText)
        throw new Error(`Backend cell creation failed: ${createResponse.statusText}`)
      }
      
      const newCell = await createResponse.json()
      
      // Step 2: Add to local layout
      const cellData = {
        cellId: newCell.id,
        type: newCell.notebook_item_type_id,
        title: fileName.trim(),
        state: {
          cellInstance: newCell,
          initial_data: newCell.initial_data || {},
        }
      }
      
      addCell(cellData)
      
      // Step 3: Add to notebook store
      notebookStore.cells[newCell.id] = newCell
      
      successMessage.value = `✅ Célula criada para ${fileName}`
      setTimeout(() => {
        successMessage.value = ''
        // Refresh tree after creation
        refreshTree()
      }, 1500)
    } catch (err) {
      errorMessage.value = '❌ Erro ao criar arquivo'
      console.error('Error creating file:', err)
    }
  }
  
  /**
   * Move file or directory
   */
  async function moveItem(sourcePath: string, destPath: string): Promise<void> {
    // TODO: Implement move functionality
    // This would call backend endpoint for moving files
    console.log('Move not yet implemented:', sourcePath, destPath)
  }
  
  /**
   * Delete file or directory
   */
  async function deleteItem(path: string): Promise<void> {
    // TODO: Implement delete functionality
    // This would call backend endpoint for deleting files
    console.log('Delete not yet implemented:', path)
  }
  
  /**
   * Send selected files to chat as attachments
   * ITERATION 2: Added for file-manager-cell Send to Chat functionality
   */
  async function sendSelectedToChat(): Promise<void> {
    console.group('[useFileManager] 💬 Sending selected files to chat')
    console.log('📦 Selected files:', selectedFiles.value)
    
    if (selectedFiles.value.length === 0) {
      errorMessage.value = 'Nenhum arquivo selecionado'
      console.warn('⚠️ No files selected')
      console.groupEnd()
      return
    }
    
    const chatStore = useChatStore()
    let successCount = 0
    let failCount = 0
    
    try {
      for (const filePath of selectedFiles.value) {
        console.log(`📄 Processing file: ${filePath}`)
        
        try {
          // Parse folder and filename from filePath
          const pathParts = filePath.split('/')
          const fileName = pathParts.pop() || filePath
          const folder = pathParts.join('/') || ''
          
          console.log(`📂 Parsed path:`, {
            filePath,
            folder,
            fileName
          })
          
          // Read file content from backend using loadFile endpoint
          // Format: /api/files/load?folder=...&filename=...
          const url = `${ENDPOINTS.loadFile}?folder=${encodeURIComponent(folder)}&filename=${encodeURIComponent(fileName)}`
          
          console.log(`🔗 Fetching from:`, url)
          
          // ITERATION 4 FIX: Use apiService.fetch instead of apiService.get
          const response = await apiService.fetch(url, { method: 'GET' })
          
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
          }
          
          const content = await response.text()
          
          console.log(`🚀 Sending to chat:`, {
            filename: fileName,
            contentLength: content.length,
            type: 'text'
          })
          
          // Send to chat with correct API signature
          const success = chatStore.addAttachment(fileName, content, 'text')
          
          if (success) {
            successCount++
            console.log(`✅ File sent: ${fileName}`)
          } else {
            failCount++
            console.warn(`⚠️ Failed to send: ${fileName}`)
          }
        } catch (fileError: any) {
          failCount++
          console.error(`❌ Error reading/sending file ${filePath}:`, fileError)
        }
      }
      
      // Show result message
      if (successCount > 0 && failCount === 0) {
        successMessage.value = `✅ ${successCount} arquivo(s) enviado(s) para o chat!`
      } else if (successCount > 0 && failCount > 0) {
        successMessage.value = `⚠️ ${successCount} enviado(s), ${failCount} falhou(falharam)`
      } else {
        errorMessage.value = `❌ Falha ao enviar ${failCount} arquivo(s)`
      }
      
      // Auto-clear message
      setTimeout(() => {
        successMessage.value = ''
        errorMessage.value = ''
      }, 3000)
      
      console.log(`📊 Result: ${successCount} success, ${failCount} failed`)
    } catch (error: any) {
      console.error('❌ Error in sendSelectedToChat:', error)
      errorMessage.value = error.message || 'Erro ao enviar arquivos para o chat'
    }
    
    console.groupEnd()
  }
  
  return {
    // State
    tree,
    displayTree,
    selectedFiles,
    expandedPaths,
    searchQuery,
    isLoading,
    errorMessage,
    successMessage,
    
    // Computed
    selectedCount,
    hasNoMatches,
    
    // Actions
    refreshTree,
    toggleSelection,
    clearSelection,
    toggleExpanded,
    collapseAll,
    updateSearchQuery,
    openSelectedFiles,
    createNewFile,
    moveItem,
    deleteItem,
    sendSelectedToChat  // ITERATION 2: Added send to chat functionality
  }
}
