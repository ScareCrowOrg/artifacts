/**
 * useModal Composable
 *
 * Provides modal management logic for Vue components.
 * Simplifies interaction with the modals store and provides
 * reactive modal state management.
 *
 * @module composables/useModal
 * @example
 * // Basic usage
 * import { useModal } from '@/composables/useModal'
 *
 * const { openModal, closeModal, isOpen } = useModal('confirmDelete')
 *
 * // Open modal with config
 * openModal({
 *   title: 'Confirm Delete',
 *   message: 'Are you sure?',
 *   onConfirm: (data) => handleDelete(data)
 * })
 *
 * // Check if modal is open
 * if (isOpen.value) {
 *   // Modal is displayed
 * }
 */

import { computed, watch, onMounted, onUnmounted } from 'vue'
import { useModalsStore } from '@/stores/modals'

/**
 * Modal composable for managing modal state and actions
 * @param {string} modalId - Unique identifier for the modal
 * @param {Object} options - Configuration options
 * @param {boolean} [options.autoRegister=true] - Auto-register modal on mount
 * @param {boolean} [options.autoUnregister=true] - Auto-unregister modal on unmount
 * @param {boolean} [options.persistent=false] - Prevent closing on backdrop click
 * @param {string} [options.component] - Modal component name
 * @param {number} [options.zIndex] - Custom z-index for modal
 * @returns {Object} Modal state and methods
 */
export function useModal(modalId, options = {}) {
  const {
    autoRegister = true,
    autoUnregister = true,
    persistent = false,
    component = null,
    zIndex = null,
  } = options

  const modalsStore = useModalsStore()

  // Auto-register on mount if enabled
  if (autoRegister) {
    onMounted(() => {
      modalsStore.registerModal(modalId, {
        persistent,
        component,
        zIndex,
      })
    })
  }

  // Auto-unregister on unmount if enabled
  if (autoUnregister) {
    onUnmounted(() => {
      modalsStore.unregisterModal(modalId)
    })
  }

  /**
   * Computed property for modal open state
   */
  const isOpen = computed(() => modalsStore.isModalOpen(modalId))

  /**
   * Computed property for modal configuration
   */
  const config = computed(() => {
    const state = modalsStore.getModalState(modalId)
    return state?.config || {}
  })

  /**
   * Computed property for modal data
   */
  const data = computed(() => {
    const state = modalsStore.getModalState(modalId)
    return state?.data || null
  })

  /**
   * Computed property for modal timestamp (useful for watching changes)
   */
  const timestamp = computed(() => {
    const state = modalsStore.getModalState(modalId)
    return state?.timestamp || 0
  })

  /**
   * Open the modal with configuration
   * @param {Object} modalConfig - Modal configuration
   * @param {Object} [modalConfig.props] - Props to pass to modal
   * @param {Function} [modalConfig.onConfirm] - Callback on confirm
   * @param {Function} [modalConfig.onClose] - Callback on close
   * @param {Object} [modalData] - Additional data payload
   * @returns {boolean} Success status
   */
  function openModal(modalConfig = {}, modalData = null) {
    return modalsStore.openModal(modalId, modalConfig, modalData)
  }

  /**
   * Close the modal
   * @param {Object} [result] - Optional result data
   */
  function closeModal(result = null) {
    modalsStore.closeModal(modalId, result)
  }

  /**
   * Confirm modal action
   * @param {Object} [confirmData] - Confirmation data
   */
  function confirmModal(confirmData = null) {
    modalsStore.confirmModal(modalId, confirmData)
  }

  /**
   * Toggle modal open/close state
   */
  function toggleModal() {
    if (isOpen.value) {
      closeModal()
    } else {
      openModal()
    }
  }

  /**
   * Watch for modal open events
   * @param {Function} callback - Callback function(config, data)
   * @returns {Function} Stop watcher function
   */
  function onOpen(callback) {
    return watch(timestamp, (newVal, oldVal) => {
      if (newVal > 0 && newVal !== oldVal && isOpen.value) {
        callback(config.value, data.value)
      }
    })
  }

  /**
   * Watch for modal close events
   * @param {Function} callback - Callback function
   * @returns {Function} Stop watcher function
   */
  function onClose(callback) {
    return watch(isOpen, (newVal, oldVal) => {
      if (oldVal && !newVal) {
        callback()
      }
    })
  }

  /**
   * Watch for modal confirm events
   * @param {Function} callback - Callback function(data)
   * @returns {Function} Stop watcher function
   */
  function onConfirm(callback) {
    let lastConfirmTimestamp = 0
    return watch(
      () => {
        const state = modalsStore.getModalState(modalId)
        return state ? state.confirmTimestamp : 0
      },
      (newTimestamp) => {
        if (newTimestamp > 0 && newTimestamp !== lastConfirmTimestamp) {
          lastConfirmTimestamp = newTimestamp
          // Get the last confirmed data which was stored before modal closed
          const confirmedData = modalsStore.getLastConfirmedData(modalId)
          callback(confirmedData)
        }
      },
    )
  }

  return {
    // State
    isOpen,
    config,
    data,
    timestamp,

    // Methods
    openModal,
    closeModal,
    confirmModal,
    toggleModal,

    // Watchers
    onOpen,
    onClose,
    onConfirm,
  }
}
