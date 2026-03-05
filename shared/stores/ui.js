/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-01-26",
 *   "console_calls_found": 3,
 *   "console_calls_migrated": 3,
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

// DEBUG LOG (ITERATION #2): Confirmação de carregamento do módulo ui.js
log.debug('[DEBUG][ITERATION_2] ui.js module loaded')
log.debug('[DEBUG][ITERATION_2] This should NOT appear if ui.ts is being used')
log.debug('[DEBUG][ITERATION_2] Timestamp:', new Date().toISOString())

export const useUIStore = defineStore('ui', () => {
  // ===== Panel Visibility State =====
  const showChatHistory = ref(false)
  const showSettings = ref(false)
  // showIssuesDashboard removed - migrated to issues-dashboard-cell
  // See: artifacts/canonical/cell_types/issues-dashboard-cell/
  // showNotebookCellsAdmin removed - migrated to notebook-cells-admin-cell
  // See: artifacts/canonical/cell_types/notebook-cells-admin-cell/
  // showRolesManagement removed - migrated to roles-management-cell

  // Chat settings panel visibility (with localStorage persistence)
  const showChatSettings = ref(
    localStorage.getItem('showChatSettings') === 'true',
  )

  // ===== Workspace Layout State =====
  // Triggers for workspace actions
  const clearActiveCellTrigger = ref(0)
  const contentCapturedTrigger = ref(0)
  const capturedContent = ref('')

  // File-related triggers
  const fileLoadedTrigger = ref(0)
  const fileLoadedData = ref(null)

  const createNewFileTrigger = ref(0)
  const createNewFileData = ref(null)

  // ===== Panel Toggle Actions =====

  /**
   * Toggle chat history visibility
   * Replaces: toggle-history event
   */
  function toggleChatHistory() {
    showChatHistory.value = !showChatHistory.value
    if (import.meta.env.DEV) {
      log.debug('Chat history toggled', showChatHistory.value)
    }
  }

  /**
   * Toggle settings panel visibility
   * Replaces: toggle-settings event
   */
  function toggleSettings() {
    showSettings.value = !showSettings.value
    if (import.meta.env.DEV) {
      log.debug('Settings toggled', showSettings.value)
    }
  }

  /**
   * Close settings panel
   * Replaces: 'close' emit from settings components
   */
  function closeSettings() {
    showSettings.value = false
    if (import.meta.env.DEV) {
      log.debug('Settings closed')
    }
  }

  /**
   * Toggle issues dashboard visibility
   * 
   * ⚠️ DEPRECATED: IssuesDashboard overlay has been migrated to issues-dashboard-cell
   * This function is kept for backward compatibility but should not be used.
   * 
   * TODO: Remove after confirming all consumers are updated
   * 
   * See: artifacts/canonical/cell_types/issues-dashboard-cell/
   */
  function toggleIssuesDashboard() {
    log.warn('toggleIssuesDashboard is deprecated - use issues-dashboard-cell instead')
    // No-op - cell should be launched via DynamicWorkspace instead
  }

  /**
   * Toggle notebook cells admin visibility
   * 
   * ⚠️ DEPRECATED: NotebookCellsAdmin overlay has been migrated to notebook-cells-admin-cell
   * This function is kept for backward compatibility but should not be used.
   * 
   * TODO: Remove after confirming FooterWindowManager is updated
   * 
   * See: artifacts/canonical/cell_types/notebook-cells-admin-cell/
   */
  function toggleNotebookCellsAdmin() {
    log.warn('toggleNotebookCellsAdmin is deprecated - use notebook-cells-admin-cell instead')
    // No-op - cell should be launched via DynamicWorkspace instead
  }

  /**
   * Toggle roles management visibility
   * 
   * ⚠️ DEPRECATED: RolesManagement overlay has been migrated to roles-management-cell
   * This function is kept for backward compatibility but should not be used.
   * 
   * TODO: Remove after confirming FooterWindowManager is updated
   * 
   * See: roles-management-cell
   */
  function toggleRolesManagement() {
    log.warn('toggleRolesManagement is deprecated - use roles-management-cell instead')
    // No-op - cell should be launched via DynamicWorkspace instead
  }

  /**
   * Toggle chat settings panel visibility
   * Persists preference in localStorage
   */
  function toggleChatSettings() {
    showChatSettings.value = !showChatSettings.value
    localStorage.setItem('showChatSettings', showChatSettings.value.toString())
    if (import.meta.env.DEV) {
      log.debug('Chat settings toggled', showChatSettings.value)
    }
  }

  /**
   * Clear chat messages
   * Replaces: clear-chat event
   * This triggers the chat component to clear its messages
   */
  function clearChat() {
    if (import.meta.env.DEV) {
      log.debug('Clear chat triggered')
    }
    // Store emits this as a reactive signal
    clearChatTrigger.value = Date.now()
  }

  // Reactive trigger for clear chat action
  const clearChatTrigger = ref(0)

  // ===== Workspace Actions =====

  /**
   * Trigger clear active cell action
   * Replaces: 'clear-active-cell' emit from WorkspaceArea
   */
  function triggerClearActiveCell() {
    clearActiveCellTrigger.value = Date.now()
    if (import.meta.env.DEV) {
      log.debug('Clear active cell triggered')
    }
  }

  /**
   * Handle content captured from ManualCapture
   * Replaces: 'content-captured' emit from ManualCapture
   * @param {string} content - The captured content
   */
  function handleContentCaptured(content) {
    capturedContent.value = content
    contentCapturedTrigger.value = Date.now()
    if (import.meta.env.DEV) {
      log.debug('Content captured', content.substring(0, 50) + '...')
    }
  }

  /**
   * Handle file loaded
   * Replaces: 'file-loaded' emit from WorkspaceArea/FileBrowser
   * @param {Object} data - File data
   */
  function handleFileLoaded(data) {
    fileLoadedData.value = data
    fileLoadedTrigger.value = Date.now()
    if (import.meta.env.DEV) {
      log.debug('File loaded', data)
    }
  }

  /**
   * Handle create new file
   * Replaces: 'create-new-file' emit from WorkspaceArea/FileBrowser
   * @param {Object} data - New file data
   */
  function handleCreateNewFile(data) {
    createNewFileData.value = data
    createNewFileTrigger.value = Date.now()
    if (import.meta.env.DEV) {
      log.debug('Create new file', data)
    }
  }

  /**
   * Clear captured content after it has been processed
   */
  function clearCapturedContent() {
    capturedContent.value = ''
    if (import.meta.env.DEV) {
      log.debug('Captured content cleared')
    }
  }

  return {
    // ===== State =====
    showChatHistory,
    showSettings,
    // showIssuesDashboard removed - migrated to issues-dashboard-cell
    // showNotebookCellsAdmin removed - migrated to notebook-cells-admin-cell
    // showRolesManagement removed - migrated to roles-management-cell
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
