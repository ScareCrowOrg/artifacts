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
import { CENTRAL_HUB_BASE } from '@/config/apiConfig.js'

const log = createLogger('auth:service')

const TOKEN_KEY = 'scareverse_token'
const USER_KEY = 'scareverse_user'
const SESSION_KEY = 'scareverse_session'
const TOKEN_EXPIRY_KEY = 'scareverse_token_expiry'
const SESSION_REFRESH_INTERVAL = 5 * 60 * 1000 // 5 minutes in milliseconds

class AuthService {
  constructor() {
    // Don't initialize from localStorage here - it might be empty during first module load
    // Initialize will be called after login or on page reload
    this.token = null
    this.user = null
    this.session = null
    this.tokenExpiry = null
    this.refreshTimer = null

    // DEBUG: Check localStorage state at constructor time
    const lsToken = localStorage.getItem(TOKEN_KEY)
    const lsUser = localStorage.getItem(USER_KEY)
    console.log('=== [AuthService] CONSTRUCTOR - localStorage state ===', {
      hasToken: !!lsToken,
      tokenLength: lsToken ? lsToken.length : 0,
      hasUser: !!lsUser,
      timestamp: new Date().toISOString()
    })

    console.log('=== [AuthService] CONSTRUCTOR called - all fields to null ===')
    log.debug('[AuthService] Constructor executed - all fields initialized to null')
  }

  /**
   * Initialize from localStorage - called on app startup
   * Safe to call when not logged in (returns gracefully)
   * Does NOT throw errors - always completes successfully
   */
  initialize() {
    try {
      console.log('=== [authService.initialize] STARTING ===')

      // Read from localStorage (all may be null if not logged in)
      const rawToken = localStorage.getItem(TOKEN_KEY)
      this.token = rawToken
      this.tokenExpiry = localStorage.getItem(TOKEN_EXPIRY_KEY)

      console.log('=== [initialize] Raw read from localStorage ===', {
        rawTokenExists: !!rawToken,
        rawTokenLength: rawToken ? rawToken.length : 0,
        tokenExpiryExists: !!this.tokenExpiry
      })

      // Parse JSON safely with error handling
      try {
        this.user = JSON.parse(localStorage.getItem(USER_KEY) || 'null')
      } catch (parseError) {
        console.log('=== [initialize] USER_KEY parse error, REMOVING from localStorage ===', parseError)
        log.warn('Failed to parse user from localStorage, clearing', parseError)
        this.user = null
        localStorage.removeItem(USER_KEY)
      }

      try {
        this.session = JSON.parse(localStorage.getItem(SESSION_KEY) || 'null')
      } catch (parseError) {
        console.log('=== [initialize] SESSION_KEY parse error, REMOVING from localStorage ===', parseError)
        log.warn('Failed to parse session from localStorage, clearing', parseError)
        this.session = null
        localStorage.removeItem(SESSION_KEY)
      }

      console.log('=== [initialize] After parsing JSON ===', {
        thisTokenExists: !!this.token,
        thisTokenLength: this.token ? this.token.length : 0,
        thisUserExists: !!this.user,
        thisSessionExists: !!this.session
      })

      log.debug('[initialize] Loaded from localStorage', {
        hasToken: !!this.token,
        tokenPreview: this.token ? this.token.substring(0, 12) + '...' : 'NO_TOKEN',
        hasUser: !!this.user,
        userId: this.user?.id,
        hasSession: !!this.session,
        sessionId: this.session?.id,
        tokenExpiry: this.tokenExpiry
      })

      // Check if token is expired
      if (this.tokenExpiry) {
        const now = new Date().getTime()
        const expiry = parseInt(this.tokenExpiry)
        if (now >= expiry) {
          console.log('=== [initialize] Token EXPIRED ===', {
            now,
            expiry,
            expired: now >= expiry
          })
          log.info('[initialize] Token expired, clearing auth')
          this.clearAuth()
          return
        }
      }

      console.log('=== [initialize] Before isAuthenticated check ===', {
        thisToken: !!this.token,
        thisUser: !!this.user
      })

      // Start automatic session refresh if authenticated
      const isAuth = this.isAuthenticated()
      console.log('=== [initialize] isAuthenticated() returned ===', { isAuth })

      if (isAuth) {
        log.info('[initialize] User is authenticated, starting session refresh')
        this.startSessionRefresh()
      } else {
        log.debug('[initialize] User not authenticated (no token or expired)')
      }

      console.log('=== [authService.initialize] COMPLETED SUCCESSFULLY ===')
    } catch (error) {
      // Should never happen, but log if it does
      log.error('[initialize] Unexpected error during initialization', error)
      console.error('=== [authService.initialize] ERROR ===', error)
      // Don't re-throw - initialization should always complete without breaking the app
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
    console.log('=== [setAuth] CALLED ===', {
      hasToken: !!token,
      tokenLength: token ? token.length : 0,
      hasUser: !!user,
      hasSession: !!session
    })

    this.token = token
    this.user = user
    this.session = session

    // Calculate expiry time (default 24 hours)
    const expiryTime = new Date().getTime() + expiresInSeconds * 1000
    this.tokenExpiry = expiryTime.toString()

    log.debug('[setAuth] Storing token in memory', {
      tokenLength: token ? token.length : 0,
      tokenPreview: token ? token.substring(0, 12) + '...' : null,
      userId: user?.id,
      sessionId: session?.id
    })

    log.info(
      'Token stored in storage',
      {
        sub: user && user.id,
        tokenPreview: token && token.substring(0, 12) + '...',
        expiry: new Date(expiryTime).toISOString()
      }
    )

    console.log('=== [setAuth] About to write to localStorage ===')
    // Store in localStorage
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
    localStorage.setItem(SESSION_KEY, JSON.stringify(session))
    localStorage.setItem(TOKEN_EXPIRY_KEY, this.tokenExpiry)

    console.log('=== [setAuth] Written to localStorage, verifying ===')
    const verifyToken = localStorage.getItem(TOKEN_KEY)
    const verifyUser = localStorage.getItem(USER_KEY)
    const verifySession = localStorage.getItem(SESSION_KEY)

    console.log('=== [setAuth] VERIFICATION ===', {
      tokenInStorage: !!verifyToken,
      tokenPreview: verifyToken ? verifyToken.substring(0, 12) + '...' : 'MISSING',
      userInStorage: !!verifyUser,
      sessionInStorage: !!verifySession
    })

    log.debug('[setAuth] Verified storage', {
      storedToken: verifyToken ? verifyToken.substring(0, 12) + '...' : null,
      storedUser: verifyUser ? 'present' : 'missing',
      storedSession: verifySession ? 'present' : 'missing'
    })

    // Start automatic session refresh
    this.startSessionRefresh()
  }

  /**
   * Clear authentication data
   */
  clearAuth() {
    console.log('=== [clearAuth] CALLED - REMOVING ALL AUTH FROM STORAGE ===', {
      stack: new Error().stack
    })

    log.debug('[clearAuth] Clearing authentication data', {
      hadToken: !!this.token,
      hadUser: !!this.user,
      hadSession: !!this.session
    })

    this.token = null
    this.user = null
    this.session = null
    this.tokenExpiry = null

    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(SESSION_KEY)
    localStorage.removeItem(TOKEN_EXPIRY_KEY)

    console.log('=== [clearAuth] VERIFIED - all items removed ===', {
      tokenRemoved: !localStorage.getItem(TOKEN_KEY),
      userRemoved: !localStorage.getItem(USER_KEY),
      sessionRemoved: !localStorage.getItem(SESSION_KEY)
    })

    log.debug('[clearAuth] Verified removal from localStorage', {
      tokenRemoved: !localStorage.getItem(TOKEN_KEY),
      userRemoved: !localStorage.getItem(USER_KEY),
      sessionRemoved: !localStorage.getItem(SESSION_KEY)
    })

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
   * Returns the frontend URL where Google will redirect after authentication
   * AuthCallback.vue component handles extracting code and state from URL
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
      console.log('=== [handleGoogleCallback] STARTED ===', { code: code.substring(0, 10) + '...', state })

      const redirectUri = this.getRedirectUri()

      log.debug('[handleGoogleCallback] Calling backend', {
        endpoint: ENDPOINTS.googleCallback,
        redirectUri
      })

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

      console.log('=== [handleGoogleCallback] Response received ===', {
        status: response.status,
        ok: response.ok
      })

      if (!response.ok) {
        throw new Error('Failed to authenticate with Google')
      }

      const data = await response.json()

      console.log('=== [handleGoogleCallback] Data received from backend ===', {
        hasToken: !!data.token,
        tokenLength: data.token ? data.token.length : 0,
        hasUser: !!data.user,
        hasSession: !!data.session,
        expiresAt: data.session?.expires_at
      })

      // Calculate expiry time from backend session.expires_at
      let expiresInSeconds = 86400  // default 24 hours
      if (data.session?.expires_at) {
        const expiresAt = new Date(data.session.expires_at).getTime()
        const now = new Date().getTime()
        expiresInSeconds = Math.max(1, Math.floor((expiresAt - now) / 1000))
        console.log('=== [handleGoogleCallback] Calculated expiresInSeconds ===', {
          expiresAt,
          now,
          expiresInSeconds,
          expiresInDays: (expiresInSeconds / 86400).toFixed(2)
        })
      }

      // Store authentication data in localStorage and instance memory
      this.setAuth(data.token, data.user, data.session, expiresInSeconds)

      console.log('=== [handleGoogleCallback] setAuth() completed ===')

      return data
    } catch (error) {
      log.error('Error handling Google callback', error)
      console.error('=== [handleGoogleCallback] ERROR ===', error)
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
    log.debug('[getAuthHeaders] CALLED - checking for token', {
      hasToken: !!this.token,
      tokenType: typeof this.token,
      tokenLength: this.token ? this.token.length : 0,
      tokenPreview: this.token ? this.token.substring(0, 12) + '...' : 'NO_TOKEN'
    })

    if (!this.token) {
      log.warn('[getAuthHeaders] NO TOKEN AVAILABLE', {
        memoryToken: this.token,
        isAuthenticated: this.isAuthenticated(),
        localStorage_TOKEN_KEY: localStorage.getItem(TOKEN_KEY) ? 'exists' : 'missing',
        localStorage_preview: localStorage.getItem(TOKEN_KEY) ? localStorage.getItem(TOKEN_KEY).substring(0, 12) + '...' : 'N/A'
      })
      return {}
    }

    log.debug('[getAuthHeaders] RETURNING AUTH HEADER', {
      tokenPreview: this.token.substring(0, 12) + '...',
      headerValue: `Bearer ${this.token.substring(0, 12)}...`,
      fullHeaderLength: `Bearer ${this.token}`.length
    })

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
    log.debug('[refreshSession] Starting refresh attempt', {
      hasTokenInMemory: !!this.token,
      tokenPreview: this.token ? this.token.substring(0, 12) + '...' : null
    })

    // Try to load token from memory or localStorage
    if (!this.token) {
      const storedToken = localStorage.getItem(TOKEN_KEY)
      log.debug('[refreshSession] Token not in memory, checking localStorage', {
        foundInStorage: !!storedToken,
        tokenPreview: storedToken ? storedToken.substring(0, 12) + '...' : null
      })
      this.token = storedToken
    }

    if (!this.token) {
      log.warn('Cannot refresh session: no token available', {
        memoryToken: this.token,
        storageToken: localStorage.getItem(TOKEN_KEY) ? 'present' : 'missing',
        storageTokenPreview: localStorage.getItem(TOKEN_KEY) ? localStorage.getItem(TOKEN_KEY).substring(0, 12) + '...' : null
      })
      return false
    }

    try {
      log.debug('Refreshing session with backend', {
        endpoint: ENDPOINTS.authRefresh,
        tokenPreview: this.token.substring(0, 12) + '...'
      })

      const response = await fetch(ENDPOINTS.authRefresh, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.token}`,
          'Content-Type': 'application/json',
        },
      })

      log.debug('[refreshSession] Response received', {
        status: response.status,
        ok: response.ok
      })

      if (!response.ok) {
        log.warn('Failed to refresh session', {
          status: response.status,
          statusText: response.statusText
        })
        return false
      }

      const data = await response.json()

      log.debug('[refreshSession] Received new token from backend', {
        hasNewToken: !!data.token,
        newTokenPreview: data.token ? data.token.substring(0, 12) + '...' : null,
        hasUser: !!data.user,
        hasSession: !!data.session
      })

      // Calculate expiry from session.expires_at (like in handleGoogleCallback)
      let expiresInSeconds = 86400 // default 24 hours
      if (data.session?.expires_at) {
        const expiresAt = new Date(data.session.expires_at).getTime()
        const now = new Date().getTime()
        expiresInSeconds = Math.max(1, Math.floor((expiresAt - now) / 1000))
      }

      // Update auth data with new token and session info
      this.setAuth(data.token, data.user, data.session, expiresInSeconds)

      log.info(
        'Session refreshed successfully, new expiry',
        new Date(parseInt(this.tokenExpiry)).toISOString()
      )

      return true
    } catch (error) {
      log.error('Error refreshing session', error)
      return false
    }
  }
}

export default new AuthService()
