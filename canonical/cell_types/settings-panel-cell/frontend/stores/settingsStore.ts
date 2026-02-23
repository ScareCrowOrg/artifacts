/**
 * Settings Store - Cell-local state management
 * 
 * Migrated from cockpit-vue/src/stores/settings.js
 * Manages theme, OAuth configuration, and UI preferences
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ENDPOINTS } from '@/config/endpoints'
import apiService from '@/services/apiService'
import { createLogger } from '@/utils/logger'

const log = createLogger('cell:settings-panel')

export const useSettingsPanelStore = defineStore('settings-panel', () => {
  // ===== State =====
  
  // Active settings tab
  const activeTab = ref<'user' | 'admin'>('user')
  
  // Theme settings
  const selectedTheme = ref<'auto' | 'light' | 'dark'>('auto')
  const effectiveTheme = ref<'light' | 'dark'>('light')
  
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
  const oauthSaveMessageType = ref<'success' | 'error'>('success')
  
  // ===== Computed =====
  
  const effectiveThemeDisplay = computed(() => {
    if (selectedTheme.value === 'auto') {
      return `Auto (${effectiveTheme.value === 'dark' ? 'Dark' : 'Light'})`
    }
    return selectedTheme.value === 'dark' ? 'Dark' : 'Light'
  })
  
  const isOAuthConfigChanged = computed(() => {
    return (
      oauthConfig.value.googleClientId !== originalOAuthConfig.value.googleClientId ||
      oauthConfig.value.googleClientSecret !== originalOAuthConfig.value.googleClientSecret
    )
  })
  
  // ===== Actions =====
  
  /**
   * Change active settings tab
   */
  function setActiveTab(tabId: 'user' | 'admin') {
    activeTab.value = tabId
    log.debug('Tab changed to', tabId)
  }
  
  /**
   * Load settings from localStorage and API
   */
  async function loadSettings() {
    // Load theme from localStorage
    const savedTheme = localStorage.getItem('theme') as 'auto' | 'light' | 'dark' || 'auto'
    selectedTheme.value = savedTheme
    applyTheme(savedTheme)
    
    // Load OAuth status
    await loadOAuthStatus()
  }
  
  /**
   * Apply theme to DOM
   */
  function applyTheme(theme: 'auto' | 'light' | 'dark') {
    if (theme === 'auto') {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      effectiveTheme.value = prefersDark ? 'dark' : 'light'
    } else {
      effectiveTheme.value = theme
    }
    document.documentElement.setAttribute('data-theme', effectiveTheme.value)
    
    log.debug('Theme applied', effectiveTheme.value)
  }
  
  /**
   * Change theme
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
        document.documentElement.setAttribute('data-theme', effectiveTheme.value)
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
        oauthSaveMessage.value = 'Configuration saved successfully!'
        oauthSaveMessageType.value = 'success'
        originalOAuthConfig.value = { ...oauthConfig.value }
        
        // Clear secret field after save
        oauthConfig.value.googleClientSecret = ''
        
        // Reload status
        await loadOAuthStatus()
        
        log.debug('OAuth config saved', result)
        
        return result
      } else {
        throw new Error('Failed to save configuration')
      }
    } catch (err) {
      log.error('Error saving OAuth config', err)
      oauthSaveMessage.value = 'Error saving configuration'
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
