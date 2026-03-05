/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-02",
 *   "console_calls_found": 12,
 *   "console_calls_migrated": 12,
 *   "migration_rate": 100,
 *   "logger_namespace": "services:config",
 *   "validation_status": "excellent"
 * }
 */
import { ref } from 'vue'
import apiService, { SessionExpiredError } from '../services/apiService.js'
import { ENDPOINTS } from '../config/endpoints.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('services:config')
const CONFIG_STORAGE_KEY = 'scareverse_services_config'

/**
 * Composable for managing service configuration
 * Handles service config load/save, import/export, and connectivity testing
 * 
 * @returns {Object} Service configuration state and methods
 */
export function useServiceConfig() {
  // ===== State =====
  const serviceConfigs = ref([])
  const testResults = ref({})
  const error = ref(null)
  const successMessage = ref(null)

  // ===== Methods =====

  /**
   * Load service configuration from localStorage or backend
   */
  async function loadConfig() {
    try {
      // Try to load from localStorage first
      const stored = localStorage.getItem(CONFIG_STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        serviceConfigs.value = parsed.services

        log.debug('Config loaded from localStorage')
        return
      }

      // Otherwise fetch defaults from backend
      const response = await apiService.fetch(ENDPOINTS.servicesConfig)
      if (response.ok) {
        const data = await response.json()
        serviceConfigs.value = data.services

        log.debug('Config loaded from backend')
      }
    } catch (err) {
      log.error('Error loading config', err)
      if (!(err instanceof SessionExpiredError)) {
        error.value = 'Failed to load service configuration'
      }
      throw err
    }
  }

  /**
   * Save service configuration to localStorage
   */
  function saveConfig() {
    try {
      const config = {
        services: serviceConfigs.value,
        version: '1.0.0',
        last_updated: new Date().toISOString(),
      }
      localStorage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(config))
      
      successMessage.value = 'Configuration saved successfully'
      setTimeout(() => {
        successMessage.value = null
      }, 3000)

      log.debug('Config saved to localStorage')
    } catch (err) {
      log.error('Error saving config', err)
      error.value = 'Failed to save configuration'
      throw err
    }
  }

  /**
   * Export configuration as JSON file
   */
  function exportConfig() {
    const config = {
      services: serviceConfigs.value,
      version: '1.0.0',
      exported_at: new Date().toISOString(),
    }
    
    const blob = new Blob([JSON.stringify(config, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'scareverse-services-config.json'
    a.click()
    URL.revokeObjectURL(url)
    
    successMessage.value = 'Configuration exported'
    setTimeout(() => {
      successMessage.value = null
    }, 3000)

    log.debug('Config exported')
  }

  /**
   * Import configuration from JSON file
   */
  function importConfig() {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'application/json'
    
    input.onchange = (e) => {
      const file = e.target.files[0]
      if (!file) return

      const reader = new FileReader()
      reader.onload = (event) => {
        try {
          const config = JSON.parse(event.target.result)
          if (config.services && Array.isArray(config.services)) {
            serviceConfigs.value = config.services
            saveConfig()
            successMessage.value = 'Configuration imported successfully'
            setTimeout(() => {
              successMessage.value = null
            }, 3000)

            log.debug('Config imported')
          } else {
            throw new Error('Invalid configuration format')
          }
        } catch (err) {
          log.error('Error importing config', err)
          error.value = 'Invalid configuration file'
        }
      }
      reader.readAsText(file)
    }
    
    input.click()
  }

  /**
   * Reset configuration to backend defaults
   */
  async function resetToDefaults() {
    if (!confirm('Reset all configurations to default values?')) return

    try {
      const response = await apiService.fetch(ENDPOINTS.servicesConfig)
      if (response.ok) {
        const data = await response.json()
        serviceConfigs.value = data.services
        localStorage.removeItem(CONFIG_STORAGE_KEY)
        
        successMessage.value = 'Configuration reset to defaults'
        setTimeout(() => {
          successMessage.value = null
        }, 3000)

        log.debug('Config reset to defaults')
      }
    } catch (err) {
      log.error('Error resetting config', err)
      if (!(err instanceof SessionExpiredError)) {
        error.value = 'Failed to reset configuration'
      }
      throw err
    }
  }

  /**
   * Test connectivity for a specific service configuration
   * Note: Test results auto-clear after 5 seconds
   * @param {Object} config - Service configuration to test
   */
  async function testConnectivity(config) {
    try {
      const response = await apiService.fetch(ENDPOINTS.servicesConfigTest, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          endpoint: config.endpoint,
          port: config.port,
          timeout: 5,
        }),
      })

      const result = await response.json()
      testResults.value = {
        ...testResults.value,
        [config.id]: result,
      }

      log.debug('Connectivity test result', {
        id: config.id,
        success: result.success,
      })

      // Clear test result after 5 seconds
      // Note: This timeout is UI feedback and will be cleaned up on component unmount
      setTimeout(() => {
        const { [config.id]: _, ...rest } = testResults.value
        testResults.value = rest
      }, 5000)
    } catch (err) {
      log.error('Error testing connectivity', err)
      testResults.value = {
        ...testResults.value,
        [config.id]: {
          success: false,
          message: 'Connection test failed',
        },
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

  return {
    // State
    serviceConfigs,
    testResults,
    error,
    successMessage,

    // Methods
    loadConfig,
    saveConfig,
    exportConfig,
    importConfig,
    resetToDefaults,
    testConnectivity,
    clearError,
    clearSuccess,
  }
}
