/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-28",
 *   "console_calls_found": 13,
 *   "console_calls_migrated": 13,
 *   "migration_rate": 100,
 *   "logger_namespace": "store:ui",
 *   "validation_status": "excellent"
 * }
 */
/**
 * UI Store
 *
 * Manages UI state and navigation-related actions.
 * Replaces global events: toggle-history, toggle-settings, toggle-issues-dashboard, clear-chat
 * Replaces emits from layout components: content-captured, clear-active-cell
 *
 * @module stores/ui
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createLogger } from '@/utils/logger'

const log = createLogger('store:ui')

// DEBUG LOG (ITERATION #2): Confirmação de carregamento do módulo ui.ts
console.log('[DEBUG][ITERATION_2] ui.ts module loaded ✅')
console.log('[DEBUG][ITERATION_2] All UI features available in this module')
console.log('[DEBUG][ITERATION_2] Timestamp:', new Date().toISOString())

/**
 * File loaded data structure
 */
interface FileLoadedData {
  /** File path */
  path?: string
  /** File content */
  content?: string
  /** File language/type */
  language?: string
  [key: string]: unknown
}

/**
 * Create new file data structure
 */
interface CreateNewFileData {
  /** File name */
  name?: string
  /** File path */
  path?: string
  /** File type */
  type?: string
  [key: string]: unknown
}

/**
 * UI Store
 */
export const useUIStore = defineStore('ui', () => {
  // ===== Panel Visibility State =====
  const showChatHistory = ref<boolean>(false)
  const showSettings = ref<boolean>(false)
  const showIssuesDashboard = ref<boolean>(false)
  const showNotebookCellsAdmin = ref<boolean>(false)
  const showRolesManagement = ref<boolean>(false)

  // Chat settings panel visibility (with localStorage persistence)
  const showChatSettings = ref<boolean>(
    localStorage.getItem('showChatSettings') === 'true',
  )

  // ===== Workspace Layout State =====
  // Triggers for workspace actions
  const clearActiveCellTrigger = ref<number>(0)
  const contentCapturedTrigger = ref<number>(0)
  const capturedContent = ref<string>('')

  // File-related triggers
  const fileLoadedTrigger = ref<number>(0)
  const fileLoadedData = ref<FileLoadedData | null>(null)

  const createNewFileTrigger = ref<number>(0)
  const createNewFileData = ref<CreateNewFileData | null>(null)

  // ===== Panel Toggle Actions =====

  /**
   * Toggle chat history visibility
   * Replaces: toggle-history event
   */
  function toggleChatHistory(): void {
    showChatHistory.value = !showChatHistory.value
    if (import.meta.env.DEV) {
      log.debug('Chat history toggled', showChatHistory.value)
    }
  }

  /**
   * Toggle settings panel visibility
   * Replaces: toggle-settings event
   */
  function toggleSettings(): void {
    showSettings.value = !showSettings.value
    if (import.meta.env.DEV) {
      log.debug('Settings toggled', showSettings.value)
    }
  }

  /**
   * Close settings panel
   * Replaces: 'close' emit from settings components
   */
  function closeSettings(): void {
    showSettings.value = false
    if (import.meta.env.DEV) {
      log.debug('Settings closed')
    }
  }

  /**
   * Toggle issues dashboard visibility
   * Replaces: toggle-issues-dashboard event
   */
  function toggleIssuesDashboard(): void {
    showIssuesDashboard.value = !showIssuesDashboard.value
    if (import.meta.env.DEV) {
      log.debug('Issues dashboard toggled', showIssuesDashboard.value)
    }
  }

  /**
   * Toggle notebook cells admin visibility
   */
  function toggleNotebookCellsAdmin(): void {
    showNotebookCellsAdmin.value = !showNotebookCellsAdmin.value
    if (import.meta.env.DEV) {
      log.debug('Notebook Cells Admin toggled', showNotebookCellsAdmin.value)
    }
  }

  /**
   * Toggle roles management visibility
   */
  function toggleRolesManagement(): void {
    showRolesManagement.value = !showRolesManagement.value
    if (import.meta.env.DEV) {
      log.debug('Roles Management toggled', showRolesManagement.value)
    }
  }

  /**
   * Toggle chat settings panel visibility
   * Persists preference in localStorage
   */
  function toggleChatSettings(): void {
    showChatSettings.value = !showChatSettings.value
    localStorage.setItem('showChatSettings', showChatSettings.value.toString())
    if (import.meta.env.DEV) {
      log.debug('Chat settings toggled', showChatSettings.value)
    }
  }

  // Reactive trigger for clear chat action
  const clearChatTrigger = ref<number>(0)

  /**
   * Clear chat messages
   * Replaces: clear-chat event
   * This triggers the chat component to clear its messages
   */
  function clearChat(): void {
    if (import.meta.env.DEV) {
      log.debug('Clear chat triggered')
    }
    // Store emits this as a reactive signal
    clearChatTrigger.value = Date.now()
  }

  // ===== Workspace Actions =====

  /**
   * Trigger clear active cell action
   * Replaces: 'clear-active-cell' emit from WorkspaceArea
   */
  function triggerClearActiveCell(): void {
    clearActiveCellTrigger.value = Date.now()
    if (import.meta.env.DEV) {
      log.debug('Clear active cell triggered')
    }
  }

  /**
   * Handle content captured from ManualCapture
   * Replaces: 'content-captured' emit from ManualCapture
   * @param content - The captured content
   */
  function handleContentCaptured(content: string): void {
    capturedContent.value = content
    contentCapturedTrigger.value = Date.now()
    if (import.meta.env.DEV) {
      log.debug('Content captured', content.substring(0, 50) + '...')
    }
  }

  /**
   * Handle file loaded
   * Replaces: 'file-loaded' emit from WorkspaceArea/FileBrowser
   * @param data - File data
   */
  function handleFileLoaded(data: FileLoadedData): void {
    fileLoadedData.value = data
    fileLoadedTrigger.value = Date.now()
    if (import.meta.env.DEV) {
      log.debug('File loaded', data)
    }
  }

  /**
   * Handle create new file
   * Replaces: 'create-new-file' emit from WorkspaceArea/FileBrowser
   * @param data - New file data
   */
  function handleCreateNewFile(data: CreateNewFileData): void {
    createNewFileData.value = data
    createNewFileTrigger.value = Date.now()
    if (import.meta.env.DEV) {
      log.debug('Create new file', data)
    }
  }

  /**
   * Clear captured content after it has been processed
   */
  function clearCapturedContent(): void {
    capturedContent.value = ''
    if (import.meta.env.DEV) {
      log.debug('Captured content cleared')
    }
  }

  return {
    // ===== State =====
    showChatHistory,
    showSettings,
    showIssuesDashboard,
    showNotebookCellsAdmin,
    showRolesManagement,
    showChatSettings,
    clearChatTrigger,

    // Workspace triggers and data
    clearActiveCellTrigger,
    contentCapturedTrigger,
    capturedContent,
    fileLoadedTrigger,
    fileLoadedData,
    createNewFileTrigger,
    createNewFileData,

    // ===== Actions =====
    toggleChatHistory,
    toggleSettings,
    closeSettings,
    toggleIssuesDashboard,
    toggleNotebookCellsAdmin,
    toggleRolesManagement,
    toggleChatSettings,
    clearChat,

    // Workspace actions
    triggerClearActiveCell,
    handleContentCaptured,
    handleFileLoaded,
    handleCreateNewFile,
    clearCapturedContent,
  }
})
