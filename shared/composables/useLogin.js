/**
 * Composable for login functionality
 * Encapsulates authentication logic for login components
 */

import { ref } from 'vue'
import authService from '@/services/authService.js'

export function useLogin() {
  const isLoggingIn = ref(false)
  const errorMessage = ref('')

  /**
   * Initiate Google OAuth login
   * @returns {Promise<void>}
   */
  const loginWithGoogle = async () => {
    if (isLoggingIn.value) return

    isLoggingIn.value = true
    errorMessage.value = ''

    try {
      await authService.initiateGoogleLogin()
    } catch (error) {
      console.error('Login error:', error)
      errorMessage.value = 'Erro ao iniciar login com Google. Tente novamente.'
      isLoggingIn.value = false
    }
  }

  /**
   * Clear error message
   */
  const clearError = () => {
    errorMessage.value = ''
  }

  return {
    isLoggingIn,
    errorMessage,
    loginWithGoogle,
    clearError,
  }
}
