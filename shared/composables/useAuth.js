import { ref } from 'vue'
import authService from '../services/authService.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('auth')

/**
 * Composable for managing authentication state and operations
 * @returns {Object} Authentication state and methods
 */
export function useAuth() {
  const authRequired = ref(false)
  const isAuthenticated = ref(false)
  const currentUser = ref(null)
  const isAuthCallback = ref(false)
  const sessionExpiredMessage = ref(null)

  /**
   * Check authentication status with backend
   */
  async function checkAuthStatus() {
    try {
      const authStatus = await authService.checkAuthStatus()
      authRequired.value = authStatus.authEnabled

      isAuthenticated.value = authService.isAuthenticated()
      currentUser.value = authService.getUser()

      log.debug('Auth status:', {
        authRequired: authRequired.value,
        isAuthenticated: isAuthenticated.value,
        user: currentUser.value,
      })
    } catch (error) {
      log.error('Error checking auth status:', error)
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
  }

  /**
   * Handle logout
   */
  async function handleLogout() {
    await authService.logout()
    isAuthenticated.value = false
    currentUser.value = null
    sessionExpiredMessage.value = null

    // Reload to reset state
    window.location.reload()
  }

  /**
   * Handle OAuth callback completion
   */
  function onAuthComplete({ success }) {
    if (success) {
      isAuthCallback.value = false
      isAuthenticated.value = true
      currentUser.value = authService.getUser()
    }
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

  return {
    // State
    authRequired,
    isAuthenticated,
    currentUser,
    isAuthCallback,
    sessionExpiredMessage,

    // Methods
    checkAuthStatus,
    onLoginSuccess,
    handleLogout,
    onAuthComplete,
    checkIsAuthCallback,
    getUserId,
  }
}
