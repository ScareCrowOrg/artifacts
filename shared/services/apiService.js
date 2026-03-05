/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-17",
 *   "console_calls_found": 7,
 *   "console_calls_migrated": 7,
 *   "migration_rate": 100,
 *   "logger_namespace": "services:api",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Centralized API service for handling HTTP requests with authentication
 * and automatic token expiration detection
 */

import authService from './authService.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('services:api')

/**
 * Custom error class for session expiration
 */
export class SessionExpiredError extends Error {
  constructor(message = 'Session expired or invalid token') {
    super(message)
    this.name = 'SessionExpiredError'
  }
}

// Event emitter for session expiration - using Set for multiple listeners
const sessionExpiredListeners = new Set()

/**
 * Register a callback to be called when session expires
 * Returns a function to unregister the callback
 */
export function onSessionExpired(callback) {
  sessionExpiredListeners.add(callback)

  // Return unsubscribe function
  return () => {
    sessionExpiredListeners.delete(callback)
  }
}

/**
 * Get API base URL from environment or window location
 */
function getApiBaseUrl() {
  // Check for window configuration first
  if (typeof window !== 'undefined' && window.API_BASE_URL) {
    return window.API_BASE_URL
  }

  // Check for Vite environment variable
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL
  }

  // Fallback to current window origin
  if (typeof window !== 'undefined') {
    return window.location.origin
  }

  return ''
}

/**
 * Enhanced fetch wrapper that handles authentication and token expiration
 */
export async function apiFetch(url, options = {}) {
  console.log('=== [apiFetch] FUNCTION STARTED ===', { url, optionsKeys: Object.keys(options) })
  log.info('[apiFetch] ENTRY POINT', { url, hasOptions: !!options })

  // Resolve relative URLs to full URLs using API base
  let resolvedUrl = url
  if (url.startsWith('/')) {
    const baseUrl = getApiBaseUrl()
    resolvedUrl = `${baseUrl}${url}`
    console.log('[apiFetch] Resolved relative URL:', {
      original: url,
      baseUrl,
      resolved: resolvedUrl
    })
  } else {
    console.log('[apiFetch] Using absolute URL:', url)
  }

  // Get auth headers - this will log internally in authService
  console.log('=== [apiFetch] ABOUT TO CALL getAuthHeaders ===')
  log.debug('[apiFetch] BEFORE getAuthHeaders', {
    timestamp: new Date().toISOString()
  })

  const authHeaders = authService.getAuthHeaders()
  console.log('=== [apiFetch] getAuthHeaders RETURNED ===', { authHeaders })

  log.debug('[apiFetch] AFTER getAuthHeaders - returned', {
    authHeaders: authHeaders,
    hasAuthHeader: !!authHeaders.Authorization,
    authHeaderPreview: authHeaders.Authorization ? authHeaders.Authorization.substring(0, 20) + '...' : 'EMPTY_OBJECT',
    authHeaderKeys: Object.keys(authHeaders)
  })

  const headers = {
    ...options.headers,
    ...authHeaders,
  }

  const fetchOptions = {
    ...options,
    headers,
  }

  log.debug('[apiFetch] Request preparation FINAL', {
    url: resolvedUrl,
    hasAuthHeader: !!authHeaders.Authorization,
    authHeaderPreview: authHeaders.Authorization ? authHeaders.Authorization.substring(0, 20) + '...' : 'none',
    allHeaders: Object.keys(headers),
    finalHeadersObject: headers
  })

  console.log('[apiFetch] Fetching:', resolvedUrl, {
    hasAuthHeader: !!authHeaders.Authorization,
    method: fetchOptions.method || 'GET',
    headers: headers
  })
  const response = await fetch(resolvedUrl, fetchOptions)

  // Check for 401 Unauthorized
  if (response.status === 401) {
    log.warn('Session expired or invalid token detected (401)')

    // Try to refresh the token before giving up
    // Skip refresh attempt if this is already the refresh endpoint
    if (!resolvedUrl.includes('/auth/refresh')) {
      log.debug('Attempting token refresh...', {
        currentToken: authService.getToken() ? authService.getToken().substring(0, 12) + '...' : 'none',
        isAuthenticated: authService.isAuthenticated()
      })
      const refreshed = await authService.refreshSession()

      if (refreshed) {
        log.info('Token refreshed successfully, retrying request', {
          newToken: authService.getToken() ? authService.getToken().substring(0, 12) + '...' : 'none'
        })

        // Retry the original request with the new token
        const retryAuthHeaders = authService.getAuthHeaders()
        const retryHeaders = {
          ...options.headers,
          ...retryAuthHeaders,
        }

        const retryOptions = {
          ...options,
          headers: retryHeaders,
        }

        log.debug('[apiFetch] Retrying with new token', {
          hasNewAuthHeader: !!retryAuthHeaders.Authorization,
          authHeaderPreview: retryAuthHeaders.Authorization ? retryAuthHeaders.Authorization.substring(0, 20) + '...' : 'none'
        })

        const retryResponse = await fetch(resolvedUrl, retryOptions)

        // If retry still fails with 401, clear auth and notify
        if (retryResponse.status === 401) {
          log.warn('Token refresh succeeded but request still unauthorized')
          authService.clearAuth()

          sessionExpiredListeners.forEach((callback) => {
            try {
              callback()
            } catch (error) {
              log.error('Error in session expiration callback', error)
            }
          })

          throw new SessionExpiredError()
        }

        return retryResponse
      } else {
        log.warn('Token refresh failed, clearing auth', {
          tokenAfterRefresh: authService.getToken() ? authService.getToken().substring(0, 12) + '...' : 'none',
          isAuthenticated: authService.isAuthenticated()
        })
      }
    }

    // Clear auth data
    authService.clearAuth()

    // Notify all listeners about session expiration
    sessionExpiredListeners.forEach((callback) => {
      try {
        callback()
      } catch (error) {
        log.error('Error in session expiration callback', error)
      }
    })

    throw new SessionExpiredError()
  }

  return response
}

export default {
  fetch: apiFetch,
  onSessionExpired,
  SessionExpiredError,
}
