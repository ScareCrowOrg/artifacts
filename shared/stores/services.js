/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-14",
 *   "console_calls_found": 8,
 *   "console_calls_migrated": 8,
 *   "migration_rate": 100,
 *   "logger_namespace": "store:services",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Services Store
 *
 * Manages services state and actions centrally using Pinia.
 * Replaces emits from ServiceCard: start, stop, restart, view-logs, configure
 *
 * @module stores/services
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import apiService, { SessionExpiredError } from '../services/apiService.js'
import { ENDPOINTS } from '../config/endpoints.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('store:services')

export const useServicesStore = defineStore('services', () => {
  // State
  const services = ref([])
  const isLoading = ref(false)
  const error = ref(null)
  const successMessage = ref(null)

  /**
   * Fetch all services status
   */
  async function fetchServices() {
    try {
      const response = await apiService.fetch(ENDPOINTS.servicesStatus)
      if (!response.ok) throw new Error('Failed to fetch services')

      const data = await response.json()
      services.value = data
      error.value = null

      log.debug('Services loaded', { count: services.value.length })
    } catch (err) {
      log.error('Error fetching services', err)
      if (!(err instanceof SessionExpiredError) && !services.value.length) {
        error.value =
          'Failed to load services. Make sure the backend is running.'
      }
    }
  }

  /**
   * Start a service
   * @param {string} serviceId - Service identifier
   */
  async function startService(serviceId) {
    try {
      const response = await apiService.fetch(
        ENDPOINTS.serviceStart(serviceId),
        {
          method: 'POST',
        },
      )
      const result = await response.json()

      if (result.success) {
        successMessage.value = `Service ${serviceId} started`
        await fetchServices()

        // Clear success message after 3 seconds
        setTimeout(() => {
          successMessage.value = null
        }, 3000)
      } else {
        error.value = result.message
      }

      log.debug('Service started', serviceId)
    } catch (err) {
      log.error('Error starting service', err)
      if (!(err instanceof SessionExpiredError)) {
        error.value = `Failed to start service ${serviceId}`
      }
    }
  }

  /**
   * Stop a service
   * @param {string} serviceId - Service identifier
   */
  async function stopService(serviceId) {
    try {
      const response = await apiService.fetch(
        ENDPOINTS.serviceStop(serviceId),
        {
          method: 'POST',
        },
      )
      const result = await response.json()

      if (result.success) {
        successMessage.value = `Service ${serviceId} stopped`
        await fetchServices()

        // Clear success message after 3 seconds
        setTimeout(() => {
          successMessage.value = null
        }, 3000)
      } else {
        error.value = result.message
      }

      log.debug('Service stopped', serviceId)
    } catch (err) {
      log.error('Error stopping service', err)
      if (!(err instanceof SessionExpiredError)) {
        error.value = `Failed to stop service ${serviceId}`
      }
    }
  }

  /**
   * Restart a service
   * @param {string} serviceId - Service identifier
   */
  async function restartService(serviceId) {
    try {
      const response = await apiService.fetch(
        ENDPOINTS.serviceRestart(serviceId),
        {
          method: 'POST',
        },
      )
      const result = await response.json()

      if (result.success) {
        successMessage.value = `Service ${serviceId} restarted`
        await fetchServices()

        // Clear success message after 3 seconds
        setTimeout(() => {
          successMessage.value = null
        }, 3000)
      } else {
        error.value = result.message
      }

      log.debug('Service restarted', serviceId)
    } catch (err) {
      log.error('Error restarting service', err)
      if (!(err instanceof SessionExpiredError)) {
        error.value = `Failed to restart service ${serviceId}`
      }
    }
  }

  /**
   * Clear error message
   */
  function clearError() {
    error.value = null
  }

  /**
   * Clear success message
   */
  function clearSuccess() {
    successMessage.value = null
  }

  /**
   * Set success message
   * @param {string} message - Success message to display
   * @param {number} duration - Duration in ms before auto-clear (default 3000)
   */
  function setSuccessMessage(message, duration = 3000) {
    successMessage.value = message
    if (duration > 0) {
      setTimeout(() => {
        successMessage.value = null
      }, duration)
    }
  }

  /**
   * Set error message
   * @param {string} message - Error message to display
   */
  function setError(message) {
    error.value = message
  }

  return {
    // State
    services,
    isLoading,
    error,
    successMessage,
    // Actions
    fetchServices,
    startService,
    stopService,
    restartService,
    clearError,
    clearSuccess,
    setSuccessMessage,
    setError,
  }
})
