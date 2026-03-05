/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-17",
 *   "console_calls_found": 4,
 *   "console_calls_migrated": 4,
 *   "migration_rate": 100,
 *   "logger_namespace": "composables:settings",
 *   "validation_status": "excellent"
 * }
 */
import { ref, computed } from 'vue'
import authService from '../services/authService.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('composables:settings')

/**
 * Composable for managing settings panel OAuth configuration
 * Encapsulates OAuth config state and operations for SettingsPanel component
 * 
 * @returns {Object} OAuth configuration state and methods
 */
export function useSettings() {
  // ===== State =====
  const localConfig = ref({
    googleClientId: '',
    googleClientSecret: '',
  })

  const originalConfig = ref(null)

  const authStatus = ref({
    authEnabled: false,
    configured: false,
  })

  const isSaving = ref(false)
  const saveMessage = ref('')
  const saveMessageType = ref('success')

  // ===== Computed =====
  const isConfigChanged = computed(() => {
    if (!originalConfig.value) return true

    const clientIdChanged =
      localConfig.value.googleClientId !== originalConfig.value.googleClientId
    const secretProvided =
      localConfig.value.googleClientSecret.trim().length > 0

    return clientIdChanged || secretProvided
  })

  // ===== Methods =====

  /**
   * Load OAuth configuration from backend
   */
  async function loadConfig() {
    try {
      const [config, status] = await Promise.all([
        authService.getOAuthConfig(),
        authService.checkAuthStatus(),
      ])

      originalConfig.value = {
        googleClientId: config.googleClientId || '',
      }

      localConfig.value = {
        googleClientId: config.googleClientId || '',
        googleClientSecret: '',
      }

      authStatus.value = status

      if (import.meta.env.DEV) {
        log.debug('Config loaded', {
          clientIdConfigured: !!config.googleClientId,
          authEnabled: status.authEnabled,
        })
      }
    } catch (error) {
      log.error('Error loading config', error)
      showMessage('Erro ao carregar configuração', 'error')
      throw error
    }
  }

  /**
   * Save OAuth configuration to backend
   * @param {Function} onSuccess - Callback to execute on successful save
   */
  async function saveConfig(onSuccess) {
    if (isSaving.value) return

    // Validate
    if (!localConfig.value.googleClientId) {
      showMessage('Client ID é obrigatório', 'error')
      return
    }

    isSaving.value = true
    saveMessage.value = ''

    try {
      const result = await authService.updateOAuthConfig(
        localConfig.value.googleClientId,
        localConfig.value.googleClientSecret || undefined,
      )

      showMessage('Configuração salva com sucesso!', 'success')

      // Update auth status
      authStatus.value = {
        authEnabled: result.authEnabled,
        configured: true,
      }

      // Update original config
      originalConfig.value = {
        googleClientId: localConfig.value.googleClientId,
      }

      // Clear secret field after save
      localConfig.value.googleClientSecret = ''

      if (import.meta.env.DEV) {
        log.debug('Config saved successfully')
      }

      // Call success callback if provided
      if (onSuccess && typeof onSuccess === 'function') {
        onSuccess(result)
      }

      return result
    } catch (error) {
      log.error('Error saving config', error)
      showMessage('Erro ao salvar configuração', 'error')
      throw error
    } finally {
      isSaving.value = false
    }
  }

  /**
   * Display a message to user
   * @param {string} message - Message text
   * @param {string} type - Message type ('success' or 'error')
   */
  function showMessage(message, type = 'success') {
    saveMessage.value = message
    saveMessageType.value = type

    setTimeout(() => {
      saveMessage.value = ''
    }, 5000)
  }

  /**
   * Clear all messages
   */
  function clearMessage() {
    saveMessage.value = ''
  }

  /**
   * Reset configuration to initial state
   */
  function resetConfig() {
    localConfig.value = {
      googleClientId: originalConfig.value?.googleClientId || '',
      googleClientSecret: '',
    }
  }

  return {
    // State
    localConfig,
    originalConfig,
    authStatus,
    isSaving,
    saveMessage,
    saveMessageType,

    // Computed
    isConfigChanged,

    // Methods
    loadConfig,
    saveConfig,
    showMessage,
    clearMessage,
    resetConfig,
  }
}
