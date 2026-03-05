/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-14",
 *   "console_calls_found": 6,
 *   "console_calls_migrated": 6,
 *   "migration_rate": 100,
 *   "logger_namespace": "store:file-browser",
 *   "validation_status": "excellent"
 * }
 */
/**
 * File Browser Store
 *
 * Manages file browser state and actions, replacing emits and refs.
 * Handles file tree navigation, selection, sharing, and modal states.
 *
 * @module stores/fileBrowser
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ENDPOINTS } from '@/config/endpoints.js'
import apiService, { SessionExpiredError } from '@/services/apiService.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('store:file-browser')

export const useFileBrowserStore = defineStore('fileBrowser', () => {
  // ===== File Tree State =====
  const tree = ref([])
  const filteredTree = ref([])
  const expandedPaths = ref(new Set())
  const loading = ref(false)
  const error = ref(null)

  // ===== Navigation & Selection State =====
  const currentFolder = ref('')
  const selectedFiles = ref([])
  const searchQuery = ref('')

  // ===== Share State =====
  const shareActive = ref(false)
  const shareUrl = ref('')
  const sharedFiles = ref([])
  const shareLoading = ref(false)
  const shareStatus = ref({ text: '', type: '' })

  // ===== Create File Modal State =====
  const createFileLoading = ref(false)
  const createFileStatus = ref({ text: '', type: '' })

  // ===== Move Item Modal State =====
  const moveLoading = ref(false)
  const moveStatus = ref({ text: '', type: '' })

  // ===== Constants =====
  const MODAL_AUTO_CLOSE_DELAY = 1500
  const STATUS_CLEAR_DELAY = 2000
  const PATH_SEPARATOR = '/'

  // ===== Computed =====
  const displayTree = computed(() => {
    if (!searchQuery.value || searchQuery.value.trim() === '') {
      return tree.value
    }
    return filteredTree.value
  })

  const hasNoMatches = computed(() => {
    return (
      searchQuery.value &&
      searchQuery.value.trim() !== '' &&
      filteredTree.value.length === 0
    )
  })

  const selectedCount = computed(() => selectedFiles.value.length)

  // ===== File Tree Actions =====

  /**
   * Load the file tree from the API
   */
  async function loadTree() {
    loading.value = true
    error.value = null

    try {
      const url = `${ENDPOINTS.tree}?format=flat&include_hidden=true`
      const response = await apiService.fetch(url)
      const data = await response.json()

      const items = data.data || []
      tree.value = buildTreeFromFlatList(items)
    } catch (err) {
      error.value = err.message || 'Erro ao carregar árvore de arquivos'
      log.error('Error loading file tree', err)
    } finally {
      loading.value = false
    }
  }

  /**
   * Build hierarchical tree structure from flat list
   */
  function buildTreeFromFlatList(items) {
    const nodeMap = new Map()
    const root = []

    // Create all nodes and map by path
    for (const item of items) {
      // Ignore specific folders
      if (
        item.path.startsWith('actions-runner') ||
        item.path.startsWith('actions-runner-tests')
      ) {
        continue
      }

      const isDirectory = item.type === 'directory' || item.path.endsWith('/')
      const node = {
        name: item.name,
        path: item.path,
        isDirectory,
        children: [],
        loaded: true,
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
        root.push(nodeMap.get(path))
      } else {
        // Has parent
        const parentPath = parts.slice(0, -1).join('/')
        const parentNode = nodeMap.get(parentPath)
        if (parentNode) {
          parentNode.children.push(nodeMap.get(path))
        } else {
          // Fallback: add to root if parent not found
          root.push(nodeMap.get(path))
        }
      }
    }

    // Sort nodes recursively (directories first, then alphabetically)
    const sortNodes = (nodes) => {
      nodes.sort((a, b) => {
        if (a.isDirectory !== b.isDirectory) {
          return a.isDirectory ? -1 : 1
        }
        return a.name.localeCompare(b.name)
      })
      for (const node of nodes) {
        if (node.children.length > 0) {
          sortNodes(node.children)
        } else if (!node.isDirectory) {
          node.children = null
        }
      }
    }
    sortNodes(root)
    return root
  }

  /**
   * Refresh the file tree
   */
  async function refreshTree() {
    await loadTree()
    log.debug('Tree refreshed')
  }

  /**
   * Toggle expansion of a directory node
   */
  function toggleExpand(node) {
    if (!node.isDirectory) return

    if (expandedPaths.value.has(node.path)) {
      expandedPaths.value.delete(node.path)
    } else {
      expandedPaths.value.add(node.path)
    }
    // Force reactivity update
    expandedPaths.value = new Set(expandedPaths.value)
  }

  /**
   * Expand all parent directories leading to a target path
   */
  function expandToPath(targetPath) {
    if (!targetPath) return

    const pathParts = targetPath.split('/').filter((p) => p)
    let currentPath = ''

    for (const part of pathParts) {
      currentPath = currentPath ? `${currentPath}/${part}` : part
      expandedPaths.value.add(currentPath)
      expandedPaths.value.add(currentPath + '/')
    }

    // Force reactivity update
    expandedPaths.value = new Set(expandedPaths.value)
  }

  /**
   * Collapse all expanded directories
   */
  function collapseAll() {
    expandedPaths.value.clear()
    // Force reactivity update
    expandedPaths.value = new Set(expandedPaths.value)
  }

  // ===== Selection Actions =====

  /**
   * Handle node selection (file or directory)
   */
  function selectNode(path) {
    if (path.endsWith('/')) {
      // Navigate to directory
      currentFolder.value = path.slice(0, -1)
    } else {
      // Toggle file selection
      toggleFileSelection(path)
    }
  }

  /**
   * Toggle selection of a file
   */
  function toggleFileSelection(arquivo) {
    // Detect if arquivo is already a full path or just a filename
    let fullPath

    if (currentFolder.value && arquivo.startsWith(currentFolder.value + '/')) {
      fullPath = arquivo
    } else if (arquivo.includes('/') && !currentFolder.value) {
      fullPath = arquivo
    } else {
      fullPath = currentFolder.value
        ? `${currentFolder.value}/${arquivo}`
        : arquivo
    }

    // Check if already selected
    const existingIndex = selectedFiles.value.findIndex(
      (f) => f === fullPath || f === arquivo,
    )

    if (existingIndex > -1) {
      // Remove from selection
      selectedFiles.value.splice(existingIndex, 1)
    } else {
      // Validate before adding
      if (isValidPath(fullPath) && !arquivo.endsWith('/')) {
        selectedFiles.value.push(fullPath)
      }
    }
  }

  /**
   * Clear all file selections
   */
  function clearSelection() {
    selectedFiles.value = []
    log.debug('Selection cleared')
  }

  /**
   * Validate path format and prevent path traversal
   */
  function isValidPath(path) {
    if (!path || typeof path !== 'string') {
      return false
    }

    const trimmedPath = path.trim()
    if (trimmedPath.length === 0) {
      return false
    }

    // Check for invalid characters and path traversal attempts
    const invalidPatterns = [
      /\.\./, // Parent directory reference
      /\/\//, // Double slashes
      /^\//, // Absolute path (should be relative)
      /[\0\n\r]/, // Null bytes and newlines
      /<|>/, // Angle brackets
    ]

    for (const pattern of invalidPatterns) {
      if (pattern.test(trimmedPath)) {
        return false
      }
    }

    return true
  }

  // ===== Search & Filter Actions =====

  /**
   * Update search query and filter tree
   */
  function updateSearchQuery(query) {
    searchQuery.value = query
    filterTree(query)
  }

  /**
   * Filter tree based on search query
   */
  function filterTree(query) {
    if (!query || query.trim().length < 5) {
      filteredTree.value = []
      return
    }

    const searchTerm = query.toLowerCase().trim()

    // Recursively search and collect matching nodes
    const searchNodes = (nodes) => {
      const matches = []

      for (const node of nodes) {
        const nameMatches = node.name.toLowerCase().includes(searchTerm)
        const pathMatches = node.path.toLowerCase().includes(searchTerm)

        // Search in children
        let childMatches = []
        if (node.children && node.children.length > 0) {
          childMatches = searchNodes(node.children)
        }

        if (nameMatches || pathMatches || childMatches.length > 0) {
          matches.push({
            ...node,
            children: childMatches.length > 0 ? childMatches : node.children,
          })
        }
      }

      return matches
    }

    filteredTree.value = searchNodes(tree.value)

    // Auto-expand all paths to show search results
    if (filteredTree.value.length > 0) {
      const expandPaths = (nodes) => {
        for (const node of nodes) {
          const pathParts = node.path.split('/').filter((p) => p)
          let currentPath = ''
          for (const part of pathParts) {
            currentPath = currentPath ? `${currentPath}/${part}` : part
            expandedPaths.value.add(currentPath)
            expandedPaths.value.add(currentPath + '/')
          }
          if (node.children && node.children.length > 0) {
            expandPaths(node.children)
          }
        }
      }
      expandPaths(filteredTree.value)
      expandedPaths.value = new Set(expandedPaths.value)
    }
  }

  // ===== Share Actions =====

  /**
   * Check share status on mount
   */
  async function checkShareStatus() {
    try {
      const response = await apiService.fetch(ENDPOINTS.shareStatus)
      const data = await response.json()

      if (data.status === 'ok') {
        shareActive.value = data.active
        shareUrl.value = data.url || ''
        sharedFiles.value = data.shared_files || []
      }
    } catch (error) {
      if (!(error instanceof SessionExpiredError)) {
        log.error('Error checking share status', error)
      }
    }
  }

  /**
   * Start sharing selected files
   */
  async function startShare() {
    if (selectedFiles.value.length === 0) {
      shareStatus.value = {
        text: '❌ Nenhum arquivo selecionado',
        type: 'error',
      }
      return
    }

    shareLoading.value = true
    shareStatus.value = { text: '⏳ Iniciando compartilhamento...', type: '' }

    try {
      const normalizedFiles = selectedFiles.value.map((f) =>
        f.replace(/^\//, ''),
      )
      const response = await apiService.fetch(ENDPOINTS.shareStart, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          files: normalizedFiles,
        }),
      })

      const data = await response.json()

      if (data.status === 'ok') {
        shareActive.value = true
        shareUrl.value = data.url
        sharedFiles.value = data.shared_files || []
        shareStatus.value = {
          text: `✅ Compartilhamento iniciado! ${data.shared_files?.length || 0} arquivo(s) compartilhado(s).`,
          type: 'success',
        }

        // Clear selection
        selectedFiles.value = []
      } else {
        shareStatus.value = {
          text: `❌ ${data.message || 'Erro ao iniciar compartilhamento'}`,
          type: 'error',
        }
      }
    } catch (error) {
      if (!(error instanceof SessionExpiredError)) {
        shareStatus.value = {
          text: `❌ Erro na requisição: ${error.message}`,
          type: 'error',
        }
      }
    } finally {
      shareLoading.value = false
    }
  }

  /**
   * Stop sharing all files
   */
  async function stopShare() {
    shareLoading.value = true
    shareStatus.value = { text: '⏳ Encerrando compartilhamento...', type: '' }

    try {
      const response = await apiService.fetch(ENDPOINTS.shareStop, {
        method: 'POST',
      })

      const data = await response.json()

      if (data.status === 'ok') {
        shareActive.value = false
        shareUrl.value = ''
        sharedFiles.value = []
        shareStatus.value = {
          text: '✅ Compartilhamento encerrado',
          type: 'success',
        }
      } else {
        shareStatus.value = {
          text: `❌ ${data.message || 'Erro ao encerrar compartilhamento'}`,
          type: 'error',
        }
      }
    } catch (error) {
      if (!(error instanceof SessionExpiredError)) {
        shareStatus.value = {
          text: `❌ Erro na requisição: ${error.message}`,
          type: 'error',
        }
      }
    } finally {
      shareLoading.value = false
    }
  }

  /**
   * Add file to share
   */
  async function addToShare(file) {
    shareLoading.value = true
    shareStatus.value = { text: '⏳ Adicionando arquivo...', type: '' }

    try {
      const response = await apiService.fetch(ENDPOINTS.shareAdd, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          files: [file],
        }),
      })

      const data = await response.json()

      if (data.status === 'ok') {
        sharedFiles.value = data.shared_files || []
        shareStatus.value = {
          text: '✅ Arquivo adicionado ao compartilhamento',
          type: 'success',
        }

        // Remove from selection
        const index = selectedFiles.value.indexOf(file)
        if (index > -1) {
          selectedFiles.value.splice(index, 1)
        }

        clearStatusAfterDelay()
      } else {
        shareStatus.value = {
          text: `❌ ${data.message || 'Erro ao adicionar arquivo'}`,
          type: 'error',
        }
      }
    } catch (error) {
      if (!(error instanceof SessionExpiredError)) {
        shareStatus.value = {
          text: `❌ Erro na requisição: ${error.message}`,
          type: 'error',
        }
      }
    } finally {
      shareLoading.value = false
    }
  }

  /**
   * Remove file from share
   */
  async function removeFromShare(file) {
    shareLoading.value = true
    shareStatus.value = { text: '⏳ Removendo arquivo...', type: '' }

    try {
      const response = await apiService.fetch(ENDPOINTS.shareRemove, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          files: [file],
        }),
      })

      const data = await response.json()

      if (data.status === 'ok') {
        sharedFiles.value = data.shared_files || []
        shareStatus.value = {
          text: '✅ Arquivo removido do compartilhamento',
          type: 'success',
        }

        clearStatusAfterDelay()
      } else {
        shareStatus.value = {
          text: `❌ ${data.message || 'Erro ao remover arquivo'}`,
          type: 'error',
        }
      }
    } catch (error) {
      if (!(error instanceof SessionExpiredError)) {
        shareStatus.value = {
          text: `❌ Erro na requisição: ${error.message}`,
          type: 'error',
        }
      }
    } finally {
      shareLoading.value = false
    }
  }

  /**
   * Clear status message after delay
   */
  function clearStatusAfterDelay(delay = null) {
    const timeoutDelay = delay !== null ? delay : STATUS_CLEAR_DELAY
    setTimeout(() => {
      shareStatus.value = { text: '', type: '' }
    }, timeoutDelay)
  }

  // ===== File Operations =====

  /**
   * Build file load URL
   */
  function buildFileLoadUrl(folder, filename) {
    return `${ENDPOINTS.loadFile}?folder=${encodeURIComponent(folder)}&filename=${encodeURIComponent(filename)}`
  }

  /**
   * Load selected files and return their content
   * Used for attaching to chat or loading to editor
   */
  async function loadSelectedFilesContent() {
    if (selectedFiles.value.length === 0) {
      return []
    }

    const attachments = []

    for (const filePath of selectedFiles.value) {
      // Skip directories
      if (filePath.endsWith(PATH_SEPARATOR)) continue

      try {
        // Split path into folder and filename
        const pathParts = filePath.split(PATH_SEPARATOR)
        const filename = pathParts[pathParts.length - 1]
        const folder = pathParts.slice(0, -1).join(PATH_SEPARATOR)

        const url = buildFileLoadUrl(folder, filename)
        const response = await apiService.fetch(url)
        const data = await response.json()

        if (data.status === 'ok') {
          attachments.push({
            name: filename,
            content: data.content,
            path: filePath,
          })
        } else {
          log.error(`Erro ao carregar arquivo ${filePath}`, data.details)
        }
      } catch (error) {
        if (!(error instanceof SessionExpiredError)) {
          log.error(`Erro ao carregar arquivo ${filePath}`, error)
        }
      }
    }

    return attachments
  }

  // ===== Modal State Management =====

  /**
   * Reset create file modal state
   */
  function resetCreateFileModal() {
    createFileLoading.value = false
    createFileStatus.value = { text: '', type: '' }
  }

  /**
   * Set create file loading state
   */
  function setCreateFileLoading(loading) {
    createFileLoading.value = loading
  }

  /**
   * Set create file status
   */
  function setCreateFileStatus(status) {
    createFileStatus.value = status
  }

  /**
   * Reset move item modal state
   */
  function resetMoveModal() {
    moveLoading.value = false
    moveStatus.value = { text: '', type: '' }
  }

  /**
   * Set move loading state
   */
  function setMoveLoading(loading) {
    moveLoading.value = loading
  }

  /**
   * Set move status
   */
  function setMoveStatus(status) {
    moveStatus.value = status
  }

  /**
   * Execute move operation
   */
  async function moveItem(source, destination) {
    if (!source || !source.trim()) {
      moveStatus.value = {
        text: '❌ Caminho de origem é obrigatório',
        type: 'error',
      }
      return false
    }

    if (!destination || !destination.trim()) {
      moveStatus.value = {
        text: '❌ Caminho de destino é obrigatório',
        type: 'error',
      }
      return false
    }

    moveLoading.value = true
    moveStatus.value = { text: '⏳ Movendo...', type: '' }

    try {
      const response = await apiService.fetch(ENDPOINTS.moveItem, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          source: source.trim(),
          destination: destination.trim(),
        }),
      })

      const responseData = await response.json()

      if (responseData.status === 'ok') {
        moveStatus.value = {
          text: `✅ ${responseData.message}`,
          type: 'success',
        }
        // Refresh tree after successful move
        await refreshTree()
        return true
      } else {
        moveStatus.value = {
          text: `❌ ${responseData.details}`,
          type: 'error',
        }
        return false
      }
    } catch (error) {
      if (!(error instanceof SessionExpiredError)) {
        moveStatus.value = {
          text: `❌ Erro na requisição: ${error.message}`,
          type: 'error',
        }
      }
      return false
    } finally {
      moveLoading.value = false
    }
  }

  return {
    // State
    tree,
    filteredTree,
    expandedPaths,
    loading,
    error,
    currentFolder,
    selectedFiles,
    searchQuery,
    shareActive,
    shareUrl,
    sharedFiles,
    shareLoading,
    shareStatus,
    createFileLoading,
    createFileStatus,
    moveLoading,
    moveStatus,

    // Computed
    displayTree,
    hasNoMatches,
    selectedCount,

    // Constants
    MODAL_AUTO_CLOSE_DELAY,
    STATUS_CLEAR_DELAY,
    PATH_SEPARATOR,

    // Actions - Tree
    loadTree,
    refreshTree,
    toggleExpand,
    expandToPath,
    collapseAll,
    buildTreeFromFlatList,

    // Actions - Selection
    selectNode,
    toggleFileSelection,
    clearSelection,
    isValidPath,

    // Actions - Search
    updateSearchQuery,
    filterTree,

    // Actions - Share
    checkShareStatus,
    startShare,
    stopShare,
    addToShare,
    removeFromShare,
    clearStatusAfterDelay,

    // Actions - File Operations
    buildFileLoadUrl,
    loadSelectedFilesContent,

    // Actions - Modal State
    resetCreateFileModal,
    setCreateFileLoading,
    setCreateFileStatus,
    resetMoveModal,
    setMoveLoading,
    setMoveStatus,
    moveItem,
  }
})
