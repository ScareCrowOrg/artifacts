/**
 * useFileBrowser Composable
 *
 * Manages file browser modal operations and file loading/opening logic.
 * Handles create file, move, share modals and file operations.
 *
 * @module composables/useFileBrowser
 */

import { useFileBrowserStore } from '@/stores/fileBrowser.js'
import { useUIStore } from '@/stores/ui.ts'
import { useCellsStore } from '@/stores/cells.js'
import { useModal } from '@/composables/useModal'
import { SessionExpiredError } from '@/services/apiService.js'

/**
 * File browser operations composable
 * @param {Object} emit - Component emit function
 * @returns {Object} File browser operations and modal handlers
 */
export function useFileBrowser(emit) {
  const fileBrowserStore = useFileBrowserStore()
  const uiStore = useUIStore()
  const cellsStore = useCellsStore()

  // Initialize modal composables
  const createFileModal = useModal('createFile', { autoRegister: false })
  const moveItemModal = useModal('moveItem', { autoRegister: false })
  const shareFilesModal = useModal('shareFiles', { autoRegister: false })

  // ===== Modal Setup =====

  /**
   * Setup modal event handlers
   */
  function setupModalHandlers() {
    // Create File Modal
    createFileModal.onConfirm((result) => {
      confirmCreateFile(result)
    })

    // Move Item Modal
    moveItemModal.onConfirm((result) => {
      confirmMove(result)
    })

    // Share Files Modal
    shareFilesModal.onConfirm((result) => {
      handleShareModalAction(result)
    })
  }

  // ===== Create File Modal =====

  /**
   * Open create file modal
   */
  function openCreateFileModal() {
    fileBrowserStore.resetCreateFileModal()
    createFileModal.openModal({
      currentFolder: fileBrowserStore.currentFolder,
      loading: fileBrowserStore.createFileLoading,
      status: fileBrowserStore.createFileStatus,
    })
  }

  /**
   * Confirm file creation
   * @param {Object} data - File creation data
   */
  async function confirmCreateFile(data) {
    if (!data.fileName || !data.fileName.trim()) {
      fileBrowserStore.setCreateFileStatus({
        text: '❌ Nome do arquivo é obrigatório',
        type: 'error',
      })
      updateCreateFileModalConfig()
      return
    }

    fileBrowserStore.setCreateFileLoading(true)
    fileBrowserStore.setCreateFileStatus({
      text: '⏳ Criando arquivo...',
      type: '',
    })
    updateCreateFileModalConfig()

    try {
      // Use UIStore instead of emitting
      uiStore.handleCreateNewFile({
        filename: data.fileName.trim(),
        folder: data.folder
          ? data.folder.trim()
          : fileBrowserStore.currentFolder,
      })

      fileBrowserStore.setCreateFileStatus({
        text: `✅ Célula criada para ${data.fileName}`,
        type: 'success',
      })
      updateCreateFileModalConfig()

      // Auto-close modal
      setTimeout(() => {
        createFileModal.closeModal()
      }, fileBrowserStore.MODAL_AUTO_CLOSE_DELAY)
    } catch (error) {
      fileBrowserStore.setCreateFileStatus({
        text: `❌ Erro: ${error.message}`,
        type: 'error',
      })
      updateCreateFileModalConfig()
    } finally {
      fileBrowserStore.setCreateFileLoading(false)
      updateCreateFileModalConfig()
    }
  }

  /**
   * Update create file modal config
   */
  function updateCreateFileModalConfig() {
    if (createFileModal.isOpen.value) {
      createFileModal.openModal({
        currentFolder: fileBrowserStore.currentFolder,
        loading: fileBrowserStore.createFileLoading,
        status: fileBrowserStore.createFileStatus,
      })
    }
  }

  // ===== Move Item Modal =====

  /**
   * Open move item modal
   */
  function openMoveModal() {
    fileBrowserStore.resetMoveModal()
    moveItemModal.openModal({
      loading: fileBrowserStore.moveLoading,
      status: fileBrowserStore.moveStatus,
    })
  }

  /**
   * Confirm item move
   * @param {Object} data - Move operation data
   */
  async function confirmMove(data) {
    const success = await fileBrowserStore.moveItem(
      data.source,
      data.destination,
    )

    updateMoveModalConfig()

    if (success) {
      // Auto-close modal after successful move
      setTimeout(() => {
        moveItemModal.closeModal()
      }, fileBrowserStore.MODAL_AUTO_CLOSE_DELAY)
    }
  }

  /**
   * Update move modal config
   */
  function updateMoveModalConfig() {
    if (moveItemModal.isOpen.value) {
      moveItemModal.openModal({
        loading: fileBrowserStore.moveLoading,
        status: fileBrowserStore.moveStatus,
      })
    }
  }

  // ===== Share Files Modal =====

  /**
   * Open share files modal
   */
  function openShareModal() {
    fileBrowserStore.shareStatus = { text: '', type: '' }
    shareFilesModal.openModal({
      selectedFiles: [...fileBrowserStore.selectedFiles],
      shareActive: fileBrowserStore.shareActive,
      shareUrl: fileBrowserStore.shareUrl,
      sharedFiles: [...fileBrowserStore.sharedFiles],
      loading: fileBrowserStore.shareLoading,
      status: fileBrowserStore.shareStatus,
    })
  }

  /**
   * Update share modal config
   */
  function updateShareModalConfig() {
    if (shareFilesModal.isOpen.value) {
      shareFilesModal.openModal({
        selectedFiles: [...fileBrowserStore.selectedFiles],
        shareActive: fileBrowserStore.shareActive,
        shareUrl: fileBrowserStore.shareUrl,
        sharedFiles: [...fileBrowserStore.sharedFiles],
        loading: fileBrowserStore.shareLoading,
        status: fileBrowserStore.shareStatus,
      })
    }
  }

  /**
   * Handle share modal action
   * @param {Object} result - Share action result
   */
  async function handleShareModalAction(result) {
    switch (result.action) {
      case 'start':
        await fileBrowserStore.startShare()
        updateShareModalConfig()
        break
      case 'stop':
        await fileBrowserStore.stopShare()
        updateShareModalConfig()
        setTimeout(() => {
          shareFilesModal.closeModal()
        }, fileBrowserStore.MODAL_AUTO_CLOSE_DELAY)
        break
      case 'add-file':
        await fileBrowserStore.addToShare(result.file)
        updateShareModalConfig()
        break
      case 'remove-file':
        await fileBrowserStore.removeFromShare(result.file)
        updateShareModalConfig()
        break
      case 'attach-to-chat':
        await attachFilesToChat()
        break
    }
  }

  // ===== File Operations =====

  /**
   * Load selected files to editor (legacy notebook cells)
   */
  async function loadSelectedFilesToEditor() {
    if (fileBrowserStore.selectedFiles.length === 0) {
      alert('Nenhum arquivo selecionado')
      return
    }

    const files = await fileBrowserStore.loadSelectedFilesContent()

    for (const file of files) {
      // Use cellsStore to create notebook cells with file content
      cellsStore.copyContentForCell(file.content)
    }
  }

  /**
   * Open selected files in cell (file editor cells)
   */
  async function openSelectedFilesInCell() {
    if (fileBrowserStore.selectedFiles.length === 0) {
      alert('Nenhum arquivo selecionado')
      return
    }

    const PATH_SEPARATOR = fileBrowserStore.PATH_SEPARATOR

    for (const filePath of fileBrowserStore.selectedFiles) {
      // Skip directories
      if (filePath.endsWith(PATH_SEPARATOR)) continue

      try {
        // Split path into folder and filename
        const pathParts = filePath.split(PATH_SEPARATOR)
        const fileName = pathParts[pathParts.length - 1]
        const folder = pathParts.slice(0, -1).join(PATH_SEPARATOR)

        // Emit event to create ephemeral file editor cell
        emit('open-file-in-cell', {
          fileName,
          filePath: folder,
          fullPath: filePath,
        })
      } catch (error) {
        console.error(`Erro ao abrir arquivo ${filePath}:`, error)
        alert(`Erro ao abrir arquivo ${filePath}: ${error.message}`)
      }
    }

    fileBrowserStore.clearSelection()
  }

  /**
   * Attach selected files to chat
   */
  async function attachFilesToChat() {
    if (fileBrowserStore.selectedFiles.length === 0) {
      fileBrowserStore.shareStatus = {
        text: '❌ Nenhum arquivo selecionado',
        type: 'error',
      }
      updateShareModalConfig()
      return
    }

    fileBrowserStore.shareLoading = true
    fileBrowserStore.shareStatus = {
      text: '⏳ Carregando arquivos para anexar ao chat...',
      type: '',
    }
    updateShareModalConfig()

    try {
      const attachments = await fileBrowserStore.loadSelectedFilesContent()

      if (attachments.length > 0) {
        // Emit event to parent (App.vue) to attach files to chat
        emit('attach-files-to-chat', attachments)

        fileBrowserStore.shareStatus = {
          text: `✅ ${attachments.length} arquivo(s) anexado(s) ao chat!`,
          type: 'success',
        }
        updateShareModalConfig()

        // Clear selection and close modal after success
        fileBrowserStore.clearSelection()
        setTimeout(() => {
          shareFilesModal.closeModal()
        }, fileBrowserStore.MODAL_AUTO_CLOSE_DELAY)
      } else {
        fileBrowserStore.shareStatus = {
          text: '❌ Não foi possível carregar nenhum arquivo',
          type: 'error',
        }
        updateShareModalConfig()
      }
    } catch (error) {
      if (!(error instanceof SessionExpiredError)) {
        fileBrowserStore.shareStatus = {
          text: `❌ Erro ao processar arquivos: ${error.message}`,
          type: 'error',
        }
        updateShareModalConfig()
      }
    } finally {
      fileBrowserStore.shareLoading = false
      updateShareModalConfig()
    }
  }

  // ===== Lifecycle =====

  /**
   * Initialize file browser
   */
  function initializeFileBrowser() {
    fileBrowserStore.checkShareStatus()
    setupModalHandlers()
  }

  return {
    // Stores
    fileBrowserStore,
    
    // Modals
    createFileModal,
    moveItemModal,
    shareFilesModal,
    
    // Modal operations
    openCreateFileModal,
    openMoveModal,
    openShareModal,
    
    // File operations
    loadSelectedFilesToEditor,
    openSelectedFilesInCell,
    
    // Initialization
    initializeFileBrowser,
  }
}
