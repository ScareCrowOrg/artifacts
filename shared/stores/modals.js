/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-02",
 *   "console_calls_found": 10,
 *   "console_calls_migrated": 10,
 *   "migration_rate": 100,
 *   "logger_namespace": "store:modals",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Modals Store
 *
 * Manages global modal state for the application.
 * Provides centralized modal management replacing emit-based patterns.
 *
 * @module stores/modals
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createLogger } from '@/utils/logger'

const log = createLogger('store:modals')

export const useModalsStore = defineStore('modals', () => {
  // Modal registry: tracks all registered modals and their state
  const modals = ref({})

  // Active modal stack: manages modal display order
  const activeModalStack = ref([])

  // Store last confirmed data to allow watchers to access it
  const lastConfirmedData = ref({})

  /**
   * Register a modal in the system
   * @param {string} id - Unique modal identifier
   * @param {Object} options - Modal configuration options
   * @param {string} [options.component] - Modal component name
   * @param {boolean} [options.persistent] - Prevent closing on backdrop click
   * @param {number} [options.zIndex] - Custom z-index for modal
   */
  function registerModal(id, options = {}) {
    if (!id) {
      log.warn('Cannot register modal without id')
      return
    }

    modals.value[id] = {
      id,
      isOpen: false,
      config: {},
      data: null,
      timestamp: 0,
      confirmTimestamp: 0,
      closeTimestamp: 0,
      ...options,
    }

    log.debug('Modal registered', { id })
  }

  /**
   * Unregister a modal from the system
   * @param {string} id - Modal identifier to unregister
   */
  function unregisterModal(id) {
    if (modals.value[id]) {
      // Close modal if it's open
      if (modals.value[id].isOpen) {
        closeModal(id)
      }

      delete modals.value[id]
      log.debug('Modal unregistered', { id })
    }
  }

  /**
   * Open a modal with configuration
   * @param {string} id - Modal identifier
   * @param {Object} config - Modal configuration
   * @param {Object} [config.props] - Props to pass to modal component
   * @param {Function} [config.onConfirm] - Callback when modal is confirmed
   * @param {Function} [config.onClose] - Callback when modal is closed
   * @param {Object} [data] - Additional data payload
   * @returns {boolean} Success status
   */
  function openModal(id, config = {}, data = null) {
    if (!modals.value[id]) {
      log.warn('Cannot open unregistered modal', { id })
      return false
    }

    modals.value[id] = {
      ...modals.value[id],
      isOpen: true,
      config,
      data,
      timestamp: Date.now(),
    }

    // Add to active stack if not already present
    if (!activeModalStack.value.includes(id)) {
      activeModalStack.value.push(id)
    }

    log.debug('Modal opened', { id })
    return true
  }

  /**
   * Close a modal
   * @param {string} id - Modal identifier
   * @param {Object} [result] - Optional result data from modal
   */
  function closeModal(id, result = null) {
    if (!modals.value[id]) {
      log.warn('Cannot close unregistered modal', { id })
      return
    }

    const modal = modals.value[id]

    // Call onClose callback if provided
    if (modal.config?.onClose) {
      modal.config.onClose(result)
    }

    modal.isOpen = false
    modal.closeTimestamp = Date.now()
    modal.data = null
    modal.config = {}

    // Remove from active stack
    const index = activeModalStack.value.indexOf(id)
    if (index > -1) {
      activeModalStack.value.splice(index, 1)
    }

    log.debug('Modal closed', { id })
  }

  /**
   * Confirm a modal action
   * @param {string} id - Modal identifier
   * @param {Object} data - Confirmation data
   */
  function confirmModal(id, data = null) {
    if (!modals.value[id]) {
      log.warn('Cannot confirm unregistered modal', { id })
      return
    }

    const modal = modals.value[id]

    // Store confirmation data (use provided data or existing modal data)
    const confirmData = data || modal.data
    lastConfirmedData.value[id] = confirmData

    // Update confirm timestamp first
    modal.confirmTimestamp = Date.now()

    // Call onConfirm callback if provided
    if (modal.config?.onConfirm) {
      modal.config.onConfirm(confirmData)
    }

    log.debug('Modal confirmed', { id })

    // Close modal after confirmation unless persistent
    if (!modal.persistent) {
      closeModal(id, confirmData)
    } else {
      // For persistent modals, keep the data
      modal.data = confirmData
    }
  }

  /**
   * Close all open modals
   */
  function closeAllModals() {
    const openModals = [...activeModalStack.value]
    openModals.forEach((id) => closeModal(id))
    log.debug('All modals closed')
  }

  /**
   * Check if a modal is open
   * @param {string} id - Modal identifier
   * @returns {boolean} True if modal is open
   */
  function isModalOpen(id) {
    return modals.value[id]?.isOpen || false
  }

  /**
   * Get modal state
   * @param {string} id - Modal identifier
   * @returns {Object|null} Modal state or null if not found
   */
  function getModalState(id) {
    return modals.value[id] || null
  }

  /**
   * Get the top-most active modal
   * @returns {string|null} Modal id or null if no modals are active
   */
  function getActiveModal() {
    return activeModalStack.value[activeModalStack.value.length - 1] || null
  }

  /**
   * Get last confirmed data for a modal
   * @param {string} id - Modal identifier
   * @returns {Object|null} Last confirmed data or null
   */
  function getLastConfirmedData(id) {
    return lastConfirmedData.value[id] || null
  }

  return {
    // State
    modals,
    activeModalStack,

    // Actions
    registerModal,
    unregisterModal,
    openModal,
    closeModal,
    confirmModal,
    closeAllModals,

    // Getters
    isModalOpen,
    getModalState,
    getActiveModal,
    getLastConfirmedData,
  }
})
