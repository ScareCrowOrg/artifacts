/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-17",
 *   "console_calls_found": 3,
 *   "console_calls_migrated": 3,
 *   "migration_rate": 100,
 *   "logger_namespace": "store:actions",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Actions Store
 *
 * Manages data manipulation actions like edit, delete, retry.
 * Replaces global events: edit, delete, retry
 *
 * @module stores/actions
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createLogger } from '@/utils/logger'

const log = createLogger('store:actions')

export const useActionsStore = defineStore('actions', () => {
  // State: Action triggers and data
  const editAction = ref(null)
  const deleteAction = ref(null)
  const retryAction = ref(null)

  /**
   * Trigger edit action
   * Replaces: edit event
   *
   * @param {Object} item - Item to edit (model, cell, etc.)
   */
  function triggerEdit(item) {
    editAction.value = {
      item,
      timestamp: Date.now(),
    }
    if (import.meta.env.DEV) {
      log.debug('Edit triggered for item', item)
    }
  }

  /**
   * Trigger delete action
   * Replaces: delete event
   *
   * @param {Object} item - Item to delete (model, cell, etc.)
   */
  function triggerDelete(item) {
    deleteAction.value = {
      item,
      timestamp: Date.now(),
    }
    if (import.meta.env.DEV) {
      log.debug('Delete triggered for item', item)
    }
  }

  /**
   * Trigger retry action
   * Replaces: retry event
   */
  function triggerRetry() {
    retryAction.value = Date.now()
    if (import.meta.env.DEV) {
      log.debug('Retry triggered')
    }
  }

  /**
   * Clear edit action
   */
  function clearEditAction() {
    editAction.value = null
  }

  /**
   * Clear delete action
   */
  function clearDeleteAction() {
    deleteAction.value = null
  }

  /**
   * Clear retry action
   */
  function clearRetryAction() {
    retryAction.value = null
  }

  return {
    // State
    editAction,
    deleteAction,
    retryAction,

    // Actions
    triggerEdit,
    triggerDelete,
    triggerRetry,
    clearEditAction,
    clearDeleteAction,
    clearRetryAction,
  }
})
