/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-17",
 *   "console_calls_found": 3,
 *   "console_calls_migrated": 3,
 *   "migration_rate": 100,
 *   "logger_namespace": "store:workspace",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Workspace Store
 *
 * Manages workspace UI state using pure reactive state pattern.
 * Components react to state changes via watchers instead of events.
 * Replaces global events: toggle-manual-capture, toggle-file-explorer, clear-active-cell
 *
 * @module stores/workspace
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createLogger } from '@/utils/logger'

const log = createLogger('store:workspace')

export const useWorkspaceStore = defineStore('workspace', () => {
  // State - Pure reactive state without component refs
  const showManualCapture = ref(false)
  const showFileBrowser = ref(false)
  const clearActiveCellTrigger = ref(0)

  /**
   * Toggle manual capture visibility
   * Components watch showManualCapture state and react accordingly
   */
  function toggleManualCapture() {
    showManualCapture.value = !showManualCapture.value

    if (import.meta.env?.DEV) {
      log.debug('Manual capture toggled', showManualCapture.value)
    }
  }

  /**
   * Toggle file browser visibility
   * Components watch showFileBrowser state and react accordingly
   */
  function toggleFileBrowser() {
    showFileBrowser.value = !showFileBrowser.value

    if (import.meta.env?.DEV) {
      log.debug('File browser toggled', showFileBrowser.value)
    }
  }

  /**
   * Trigger clear active cell action
   * Uses timestamp-based trigger pattern for event-like behavior
   * Components watch clearActiveCellTrigger and react when value changes
   */
  function clearActiveCell() {
    clearActiveCellTrigger.value = Date.now()

    if (import.meta.env?.DEV) {
      log.debug('Clear active cell triggered')
    }
  }

  return {
    // State - All reactive, no component refs
    showManualCapture,
    showFileBrowser,
    clearActiveCellTrigger,

    // Actions - Pure state management, no emits
    toggleManualCapture,
    toggleFileBrowser,
    clearActiveCell,
  }
})
