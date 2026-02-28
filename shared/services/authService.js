/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-23",
 *   "console_calls_found": 20,
 *   "console_calls_migrated": 20,
 *   "migration_rate": 100,
 *   "logger_namespace": "auth:service",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Authentication service for managing user sessions and OAuth
 */

import { createLogger } from '@/utils/logger'
import { ENDPOINTS } from '@/config/endpoints.js'

const log = createLogger('auth:service')

const TOKEN_KEY = 'scareverse_token'
const USER_KEY = 'scareverse_user'
const SESSION_KEY = 'scareverse_session'
const TOKEN_EXPIRY_KEY = 'scareverse_token_expiry'
const SESSION_REFRESH_INTERVAL = 5 * 60 * 1000 // 5 minutes in milliseconds

class AuthService {
  constructor() {
    this.token = localStorage.getItem(TOKEN_KEY)
    this.user = JSON.parse(localStorage.getItem(USER_KEY) || 'null')
    this.session = JSON.parse(localStorage.getItem(SESSION_KEY) || 'null')
    this.tokenExpiry = localStorage.getItem(TOKEN_EXPIRY_KEY)
    this.refreshTimer = null

    // Start automatic session refresh if authenticated
    if (this.isAuthenticated()) {
      this.startSessionRefresh()
    }
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated() {
    // Check if token exists and is not expired
    if (!this.token || !this.user) {
      return false
    }

    // Check token expiry if set
    if (this.tokenExpiry) {
      const now = new Date().getTime()
      const expiry = parseInt(this.tokenExpiry)
      if (now >= expiry) {
        log.warn('Token expired, clearing auth')
        this.clearAuth()
        return false
      }
    }

    return true
  }

  /**
   * Get current user
   */
  getUser() {
    return this.user
  }

  /**
   * Get current session
   */
  getSession() {
    return this.session
  }

  /**
   * Get auth token
   */
  getToken() {
    return this.token
  }

  /**
   * Set authentication data
   */
  setAuth(token, user, session, expiresInSeconds = 86400) {
    this.token = token
    this.user = user
    this.session = session

    // Calculate expiry time (default 24 hours)
    const expiryTime = new Date().getTime() + expiresInSeconds * 1000
    this.tokenExpiry = expiryTime.toString()

    log.info(
      'Token stored in storage',
      { 
        sub: user && user.id, 
        tokenPreview: token && token.substring(0, 12) + '...', 
        expiry: new Date(expiryTime).toISOString() 
      }
    )
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
    localStorage.setItem(SESSION_KEY, JSON.stringify(session))
    localStorage.setItem(TOKEN_EXPIRY_KEY, this.tokenExpiry)

    // Start automatic session refresh
    this.startSessionRefresh()
  }

  /**
   * Clear authentication data
   */
  clearAuth() {
    this.token = null
    this.user = null
    this.session = null
    this.tokenExpiry = null

    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(SESSION_KEY)
    localStorage.removeItem(TOKEN_EXPIRY_KEY)

    // Stop session refresh
    this.stopSessionRefresh()
  }

  /**
   * Check authentication status from server
   */
  async checkAuthStatus() {
    try {
      const response = await fetch(ENDPOINTS.authStatus)
      return await response.json()
    } catch (error) {
      log.error('Error checking auth status', error)
      return { authEnabled: false, configured: false }
    }
  }

  /**
   * Get OAuth configuration
   */
  async getOAuthConfig() {
    try {
      const response = await fetch(ENDPOINTS.oauthConfig)
      return await response.json()
    } catch (error) {
      log.error('Error getting OAuth config', error)
      return { googleClientId: null, authEnabled: false }
    }
  }

  /**
   * Update OAuth configuration
   */
  async updateOAuthConfig(clientId, clientSecret) {
    try {
      const response = await fetch(ENDPOINTS.oauthConfig, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          googleClientId: clientId,
          googleClientSecret: clientSecret,
        }),
      })
      return await response.json()
    } catch (error) {
      log.error('Error updating OAuth config', error)
      throw error
    }
  }

  /**
   * Get OAuth redirect URI
   */
  getRedirectUri() {
    return `${window.location.origin}/auth/callback`
  }

  /**
   * Initiate Google OAuth login
   */
  async initiateGoogleLogin() {
    try {
      const redirectUri = this.getRedirectUri()
      log.debug('Initiating Google login with redirect URI', redirectUri)
      const response = await fetch(
        `${ENDPOINTS.googleLogin}?redirect_uri=${encodeURIComponent(redirectUri)}`,
      )
      const data = await response.json()
      log.debug('Received auth URL from server', data)
      if (data.authUrl) {
        // Redirect to Google OAuth
        log.info('Redirecting to Google OAuth URL', data.authUrl)
        window.location.href = data.authUrl
      } else {
        throw new Error('Failed to get auth URL')
      }
    } catch (error) {
      log.error('Error initiating Google login', error)
      throw error
    }
  }

  /**
   * Handle Google OAuth callback
   */
  async handleGoogleCallback(code, state) {
    try {
      const redirectUri = this.getRedirectUri()

      const response = await fetch(ENDPOINTS.googleCallback, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          code: code,
          redirect_uri: redirectUri,
          state: state,
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to authenticate with Google')
      }

      const data = await response.json()

      // Store authentication data
      this.setAuth(data.token, data.user, data.session)

      return data
    } catch (error) {
      log.error('Error handling Google callback', error)
      throw error
    }
  }

  /**
   * Register password for authenticated user
   */
  async registerPassword(password) {
    try {
      if (!this.token) {
        throw new Error('User must be authenticated to register password')
      }

      const response = await fetch(ENDPOINTS.passwordRegister, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.token}`,
        },
        body: JSON.stringify({ password }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to register password')
      }

      const data = await response.json()
      return data
    } catch (error) {
      log.error('Error registering password', error)
      throw error
    }
  }

  /**
   * Login with email and password
   */
  async loginWithPassword(email, password) {
    try {
      const response = await fetch(ENDPOINTS.passwordLogin, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to login with password')
      }

      const data = await response.json()

      // Store authentication data
      this.setAuth(data.token, data.user, data.session)

      return data
    } catch (error) {
      log.error('Error logging in with password', error)
      throw error
    }
  }

  /**
   * Logout user
   */
  async logout() {
    // Close session if available
    if (this.session && this.session.id) {
      try {
        await fetch(ENDPOINTS.closeSession(this.session.id), {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${this.token}`,
          },
        })
      } catch (error) {
        log.error('Error closing session', error)
      }
    }

    // Clear local auth data
    this.clearAuth()
  }

  /**
   * Get authorization headers for API requests
   */
  getAuthHeaders() {
    if (!this.token) {
      return {}
    }

    return {
      Authorization: `Bearer ${this.token}`,
    }
  }

  /**
   * Start automatic session refresh
   * Refreshes the session periodically to keep it alive
   */
  startSessionRefresh() {
    // Clear any existing timer
    this.stopSessionRefresh()

    // Don't start refresh if no session
    if (!this.session || !this.session.id) {
      return
    }

    log.info('Starting automatic session refresh')

    // Set up periodic refresh
    this.refreshTimer = setInterval(() => {
      this.refreshSession()
    }, SESSION_REFRESH_INTERVAL)

    // Also refresh immediately if token is close to expiry
    if (this.tokenExpiry) {
      const now = new Date().getTime()
      const expiry = parseInt(this.tokenExpiry)
      const timeUntilExpiry = expiry - now

      // Refresh if less than 10 minutes until expiry
      if (timeUntilExpiry < 10 * 60 * 1000) {
        this.refreshSession()
      }
    }
  }

  /**
   * Stop automatic session refresh
   */
  stopSessionRefresh() {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer)
      this.refreshTimer = null
    }
  }

  /**
   * Refresh the current session to keep it alive
   * Now calls the backend to get a new token
   */
  async refreshSession() {
    // Try to load token from memory or localStorage
    if (!this.token) {
      this.token = localStorage.getItem(TOKEN_KEY)
    }
    if (!this.token) {
      log.warn('Cannot refresh session: no token available')
      return false
    }

    try {
      log.debug('Refreshing session with backend')
      const response = await fetch(ENDPOINTS.authRefresh, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.token}`,
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        log.warn('Failed to refresh session', response.status)
        return false
      }

      const data = await response.json()

      // Update auth data with new token and session info
      this.setAuth(data.token, data.user, data.session)

      // Validate tokenExpiry before using it
      if (isNaN(new Date(this.tokenExpiry))) {
        log.warn('Invalid token expiry value', this.tokenExpiry)
        this.tokenExpiry = null // Or set a default value if appropriate
      } else {
        log.info(
          'Session refreshed successfully, new expiry',
          new Date(this.tokenExpiry).toISOString()
        )
      }

      return true
    } catch (error) {
      log.error('Error refreshing session', error)
      return false
    }
  }
}

export default new AuthService()
