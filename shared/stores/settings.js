/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-14",
 *   "console_calls_found": 7,
 *   "console_calls_migrated": 7,
 *   "migration_rate": 100,
 *   "logger_namespace": "store:settings",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Settings Store
 *
 * Manages application settings including theme, OAuth configuration, and UI preferences.
 * Replaces emits: close, config-updated, theme-change from settings components.
 *
 * @module stores/settings
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ENDPOINTS } from '../config/endpoints.js'
import apiService from '../services/apiService.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('store:settings')

export const useSettingsStore = defineStore('settings', () => {
  // ===== State =====

  // Active settings tab
  const activeTab = ref('appearance')

  // Theme settings
  const selectedTheme = ref('auto')
  const effectiveTheme = ref('light')

  // OAuth configuration
  const oauthConfig = ref({
    googleClientId: '',
    googleClientSecret: '',
  })

  const originalOAuthConfig = ref({
    googleClientId: '',
    googleClientSecret: '',
  })

  const authStatus = ref({
    authEnabled: false,
    configured: false,
  })

  // UI state
  const isSavingOAuth = ref(false)
  const oauthSaveMessage = ref('')
  const oauthSaveMessageType = ref('success')

  // ===== Computed =====

  const effectiveThemeDisplay = computed(() => {
    if (selectedTheme.value === 'auto') {
      return `Auto (${effectiveTheme.value === 'dark' ? 'Escuro' : 'Claro'})`
    }
    return selectedTheme.value === 'dark' ? 'Escuro' : 'Claro'
  })

  const isOAuthConfigChanged = computed(() => {
    return (
      oauthConfig.value.googleClientId !==
        originalOAuthConfig.value.googleClientId ||
      oauthConfig.value.googleClientSecret !==
        originalOAuthConfig.value.googleClientSecret
    )
  })

  // ===== Actions =====

  /**
   * Change active settings tab
   * Replaces: 'change' emit from SettingsTabNav
   * @param {string} tabId - Tab identifier
   */
  function setActiveTab(tabId) {
    activeTab.value = tabId
    log.debug('Tab changed to', tabId)
  }

  /**
   * Load settings from localStorage and API
   */
  async function loadSettings() {
    // Load theme from localStorage
    const savedTheme = localStorage.getItem('theme') || 'auto'
    selectedTheme.value = savedTheme
    applyTheme(savedTheme)

    // Load OAuth status
    await loadOAuthStatus()
  }

  /**
   * Apply theme to DOM
   * @param {string} theme - Theme identifier ('auto', 'light', 'dark')
   */
  function applyTheme(theme) {
    if (theme === 'auto') {
      const prefersDark = window.matchMedia(
        '(prefers-color-scheme: dark)',
      ).matches
      effectiveTheme.value = prefersDark ? 'dark' : 'light'
    } else {
      effectiveTheme.value = theme
    }
    document.documentElement.setAttribute('data-theme', effectiveTheme.value)

    log.debug('Theme applied', effectiveTheme.value)
  }

  /**
   * Change theme
   * Replaces: 'theme-change' emit from UnifiedSettingsPanelRefactored
   */
  function changeTheme() {
    localStorage.setItem('theme', selectedTheme.value)
    applyTheme(selectedTheme.value)

    log.debug('Theme changed to', selectedTheme.value)
  }

  /**
   * Set up system theme detection
   */
  function detectSystemTheme() {
    const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)')
    darkModeQuery.addEventListener('change', (e) => {
      if (selectedTheme.value === 'auto') {
        effectiveTheme.value = e.matches ? 'dark' : 'light'
        document.documentElement.setAttribute(
          'data-theme',
          effectiveTheme.value,
        )
      }
    })
  }

  /**
   * Load OAuth configuration and status from API
   */
  async function loadOAuthStatus() {
    try {
      const response = await apiService.fetch(ENDPOINTS.authGoogleStatus)
      if (response.ok) {
        const data = await response.json()
        authStatus.value = data
        oauthConfig.value.googleClientId = data.client_id || ''
        originalOAuthConfig.value = { ...oauthConfig.value }

        log.debug('OAuth status loaded', data)
      }
    } catch (err) {
      log.error('Error loading OAuth status', err)
    }
  }

  /**
   * Save OAuth configuration
   * Replaces: 'config-updated' emit from SettingsPanel
   */
  async function saveOAuthConfig() {
    isSavingOAuth.value = true
    oauthSaveMessage.value = ''

    try {
      const response = await apiService.fetch(ENDPOINTS.authGoogleConfig, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(oauthConfig.value),
      })

      if (response.ok) {
        const result = await response.json()
        oauthSaveMessage.value = 'Configuração salva com sucesso!'
        oauthSaveMessageType.value = 'success'
        originalOAuthConfig.value = { ...oauthConfig.value }

        // Clear secret field after save
        oauthConfig.value.googleClientSecret = ''

        // Reload status
        await loadOAuthStatus()

        log.debug('OAuth config saved', result)

        return result
      } else {
        throw new Error('Erro ao salvar configuração')
      }
    } catch (err) {
      log.error('Error saving OAuth config', err)
      oauthSaveMessage.value = 'Erro ao salvar configuração'
      oauthSaveMessageType.value = 'error'
      throw err
    } finally {
      isSavingOAuth.value = false
      setTimeout(() => {
        oauthSaveMessage.value = ''
      }, 3000)
    }
  }

  /**
   * Reset OAuth save message
   */
  function clearOAuthMessage() {
    oauthSaveMessage.value = ''
  }

  /**
   * Initialize settings store
   * Should be called on app mount
   */
  async function initialize() {
    await loadSettings()
    detectSystemTheme()
  }

  return {
    // State
    activeTab,
    selectedTheme,
    effectiveTheme,
    oauthConfig,
    originalOAuthConfig,
    authStatus,
    isSavingOAuth,
    oauthSaveMessage,
    oauthSaveMessageType,

    // Computed
    effectiveThemeDisplay,
    isOAuthConfigChanged,

    // Actions
    setActiveTab,
    loadSettings,
    applyTheme,
    changeTheme,
    detectSystemTheme,
    loadOAuthStatus,
    saveOAuthConfig,
    clearOAuthMessage,
    initialize,
  }
})
