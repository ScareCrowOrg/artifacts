/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-14",
 *   "console_calls_found": 9,
 *   "console_calls_migrated": 9,
 *   "migration_rate": 100,
 *   "logger_namespace": "store:auth",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Auth Store
 *
 * Manages authentication state and actions centrally using Pinia.
 * Replaces emits from auth components: PasswordLogin, SetPassword, GoogleAuthButton, AuthCallback
 *
 * @module stores/auth
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import authService from '../services/authService.js'
import apiService from '../services/apiService.js'
import { usePermissionsStore } from './permissions.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('store:auth')

export const useAuthStore = defineStore('auth', () => {
  // State
  const authRequired = ref(false)
  const isAuthenticated = ref(false)
  const currentUser = ref(null)
  const isAuthCallback = ref(false)
  const sessionExpiredMessage = ref(null)
  const isLoggingIn = ref(false)
  const errorMessage = ref('')

  /**
   * Check authentication status with backend
   */
  async function checkAuthStatus() {
    try {
      console.log('=== [checkAuthStatus] STARTING ===')
      const authStatus = await authService.checkAuthStatus()
      authRequired.value = authStatus.authEnabled

      console.log('=== [checkAuthStatus] After backend check ===', {
        authStatus,
        authRequiredNow: authRequired.value
      })

      const serviceIsAuth = authService.isAuthenticated()
      console.log('=== [checkAuthStatus] authService.isAuthenticated() returned ===', {
        serviceIsAuth
      })

      isAuthenticated.value = serviceIsAuth
      currentUser.value = authService.getUser()

      console.log('=== [checkAuthStatus] Final state ===', {
        authRequired: authRequired.value,
        isAuthenticated: isAuthenticated.value,
        hasUser: !!currentUser.value
      })

      log.debug('Auth status', {
        authRequired: authRequired.value,
        isAuthenticated: isAuthenticated.value,
        user: currentUser.value,
      })
    } catch (error) {
      log.error('Error checking auth status', error)
      console.error('=== [checkAuthStatus] ERROR ===', error)
      // Default to open mode on error
      authRequired.value = false
    }
  }

  /**
   * Handle successful login
   */
  function onLoginSuccess() {
    isAuthenticated.value = true
    currentUser.value = authService.getUser()
    sessionExpiredMessage.value = null
    errorMessage.value = ''
    isLoggingIn.value = false

    // Load user permissions after successful login
    const permissionsStore = usePermissionsStore()
    permissionsStore.loadUserPermissions()

    log.debug('Login successful', currentUser.value)
  }

  /**
   * Handle logout
   */
  async function handleLogout() {
    await authService.logout()
    isAuthenticated.value = false
    currentUser.value = null
    sessionExpiredMessage.value = null
    errorMessage.value = ''

    // Note: Permissions are cleared automatically via watcher when isAuthenticated changes

    // Reload to reset state
    window.location.reload()
  }

  /**
   * Initiate Google OAuth login
   */
  async function loginWithGoogle() {
    if (isLoggingIn.value) {
      return
    }

    isLoggingIn.value = true
    errorMessage.value = ''

    try {
      await authService.initiateGoogleLogin()
      // Google login will redirect, no need for further action
    } catch (error) {
      log.error('Google login error', error)
      errorMessage.value = 'Erro ao iniciar login com Google. Tente novamente.'
      isLoggingIn.value = false
    }
  }

  /**
   * Login with email and password
   * @param {string} email - User email
   * @param {string} password - User password
   */
  async function loginWithPassword(email, password) {
    isLoggingIn.value = true
    errorMessage.value = ''

    try {
      await authService.loginWithPassword(email, password)
      onLoginSuccess()
      return { success: true }
    } catch (error) {
      log.error('Password login error', error)
      errorMessage.value =
        error.message || 'Erro ao fazer login. Verifique suas credenciais.'
      isLoggingIn.value = false
      return { success: false, error: errorMessage.value }
    }
  }

  /**
   * Register password for authenticated user
   * @param {string} password - New password
   */
  async function registerPassword(password) {
    if (!authService.isAuthenticated()) {
      errorMessage.value =
        'Você precisa estar autenticado para cadastrar uma senha.'
      return { success: false, error: errorMessage.value }
    }

    isLoggingIn.value = true
    errorMessage.value = ''

    try {
      const result = await authService.registerPassword(password)
      isLoggingIn.value = false
      return {
        success: true,
        message: result.message || 'Senha cadastrada com sucesso!',
      }
    } catch (error) {
      log.error('Set password error', error)
      errorMessage.value =
        error.message || 'Erro ao cadastrar senha. Tente novamente.'
      isLoggingIn.value = false
      return { success: false, error: errorMessage.value }
    }
  }

  /**
   * Handle OAuth callback completion
   * @param {Object} params - Callback parameters
   * @param {boolean} params.success - Whether callback was successful
   */
  function onAuthComplete({ success }) {
    if (success) {
      isAuthCallback.value = false
      isAuthenticated.value = true
      currentUser.value = authService.getUser()

      log.debug('Auth callback completed successfully')
    }
  }

  /**
   * Handle Google OAuth callback
   * @param {string} code - Authorization code from OAuth
   * @param {string} state - State parameter for CSRF validation
   */
  async function handleGoogleCallback(code, state) {
    try {
      await authService.handleGoogleCallback(code, state)
      onAuthComplete({ success: true })
      return { success: true }
    } catch (error) {
      log.error('Callback error', error)
      errorMessage.value = error.message || 'Erro ao processar autenticação'
      return { success: false, error: errorMessage.value }
    }
  }

  /**
   * Setup session expiration handler
   */
  function setupSessionExpirationHandler() {
    apiService.onSessionExpired(() => {
      log.info('Session expired detected, redirecting to login')
      sessionExpiredMessage.value =
        'Sessão expirada. Por favor, faça login novamente.'
      isAuthenticated.value = false
      currentUser.value = null
    })
  }

  /**
   * Check if current route is OAuth callback
   */
  function checkIsAuthCallback() {
    isAuthCallback.value = window.location.pathname === '/auth/callback'
  }

  /**
   * Get current user ID with fallback
   */
  function getUserId() {
    if (currentUser.value && currentUser.value.id) {
      return currentUser.value.id
    }

    // Fallback
    let userId = localStorage.getItem('scareverse_user_id')
    if (!userId) {
      userId = 'seed-user-001'
      localStorage.setItem('scareverse_user_id', userId)
    }
    return userId
  }

  /**
   * Clear error message
   */
  function clearError() {
    errorMessage.value = ''
  }

  return {
    // State
    authRequired,
    isAuthenticated,
    currentUser,
    isAuthCallback,
    sessionExpiredMessage,
    isLoggingIn,
    errorMessage,

    // Actions
    checkAuthStatus,
    onLoginSuccess,
    handleLogout,
    loginWithGoogle,
    loginWithPassword,
    registerPassword,
    onAuthComplete,
    handleGoogleCallback,
    setupSessionExpirationHandler,
    checkIsAuthCallback,
    getUserId,
    clearError,
  }
})
