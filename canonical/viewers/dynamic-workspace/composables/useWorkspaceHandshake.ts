/**
 * useWorkspaceHandshake.ts
 *
 * Composable for the Runner-side of the Cockpit ↔ Runner handshake.
 *
 * Responsibilities:
 * 1. Listen for INIT_WORKSPACE postMessage from Cockpit.
 * 2. Validate event.origin against EXPECTED_COCKPIT_ORIGINS before processing.
 * 3. Validate the session token with the CentralHub backend.
 * 4. Reply with RUNNER_READY (success) or RUNNER_ERROR (failure).
 * 5. Persist workspace state via workspaceStore.
 *
 * Phase 1 – Hello World + Handshake only.
 */

import { onMounted, onUnmounted } from 'vue'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import type { ThemeMode } from '@/stores/workspaceStore'
import { createLogger } from '@/utils/logger'

const log = createLogger('workspace:handshake')

// ── Message interfaces ──────────────────────────────────────────────────────

export interface InitWorkspaceMessage {
  type: 'INIT_WORKSPACE'
  payload: {
    workspaceId: string
    sessionToken: string
    cockpitOrigin: string
    userId: string
  }
  timestamp: number
}

export interface SwitchThemeMessage {
  type: 'SWITCH_THEME'
  payload: {
    theme: ThemeMode
  }
  timestamp: number
}

export interface SwitchLocaleMessage {
  type: 'SWITCH_LOCALE'
  payload: {
    locale: string
  }
  timestamp: number
}

export interface SyncConfigMessage {
  type: 'SYNC_CONFIG'
  payload: {
    theme: ThemeMode
    locale: string
  }
  timestamp: number
}

export interface WorkspaceReadyMessage {
  type: 'RUNNER_READY'
  payload: {
    workspaceId: string
    runnerOrigin: string
    version: string
    capabilities: string[]
    status: 'ready'
  }
  timestamp: number
}

export interface WorkspaceErrorMessage {
  type: 'RUNNER_ERROR'
  payload: {
    workspaceId: string
    errorCode: string
    message: string
  }
  timestamp: number
}

export interface ValidateSessionRequestMessage {
  type: 'VALIDATE_SESSION_REQUEST'
  payload: {
    workspaceId: string
    sessionToken: string
  }
  timestamp: number
}

export interface ValidationResultMessage {
  type: 'VALIDATION_RESULT'
  payload: {
    workspaceId: string
    success: boolean
    userId?: string
    error?: string
  }
  timestamp: number
}

// ── Constants ───────────────────────────────────────────────────────────────

const RUNNER_VERSION = 'v2.0.0-phase1'
const VALIDATE_SESSION_URL = (() => {
  const url = typeof import.meta !== 'undefined' ? (import.meta as any).env?.VITE_CENTRALHUB_URL : undefined
  const result = typeof url === 'string' ? url : 'http://localhost:8000'
  console.log('[useWorkspaceHandshake] VITE_CENTRALHUB_URL:', {
    raw: url,
    type: typeof url,
    resolved: result,
  })
  return result
})()

/**
 * Allowed Cockpit origins. Messages from other origins are silently dropped.
 * Must be set via VITE_COCKPIT_ORIGINS env var (comma-separated list).
 */
const EXPECTED_COCKPIT_ORIGINS: string[] = (() => {
  const env = typeof import.meta !== 'undefined' ? (import.meta as any).env : {}
  const origins = env.VITE_COCKPIT_ORIGINS

  console.log('[useWorkspaceHandshake] 🔍 VITE_COCKPIT_ORIGINS:', {
    raw: origins,
    type: typeof origins,
  })

  if (typeof origins === 'string' && origins.length > 0) {
    const parsed = origins.split(',').map((o: string) => o.trim()).filter(Boolean)
    console.log('[useWorkspaceHandshake] ✅ VITE_COCKPIT_ORIGINS resolved:', parsed)
    return parsed
  }

  const fallback = ['http://localhost:5173', 'http://localhost:8000', 'http://127.0.0.1:5173', 'http://localhost:5052']
  console.log('[useWorkspaceHandshake] ⚠️ VITE_COCKPIT_ORIGINS not set, using fallback:', fallback)
  return fallback
})()

// ── Composable ──────────────────────────────────────────────────────────────

export function useWorkspaceHandshake() {
  const store = useWorkspaceStore()

  // Track pending validation request to match response with request
  let pendingValidationRequest: {
    workspaceId: string
    cockpitOrigin: string
    source: MessageEventSource | null
  } | null = null

  // ── Private helpers ────────────────────────────────────────────────────────

  /**
   * Send VALIDATE_SESSION_REQUEST to Cockpit (parent frame).
   * Cockpit will perform the actual validation fetch to avoid CORS issues with loopback addresses.
   */
  function requestValidation(
    workspaceId: string,
    sessionToken: string,
    cockpitOrigin: string,
    source: MessageEventSource | null,
  ) {
    const message: ValidateSessionRequestMessage = {
      type: 'VALIDATE_SESSION_REQUEST',
      payload: {
        workspaceId,
        sessionToken,
      },
      timestamp: Date.now(),
    }
    console.log('[useWorkspaceHandshake] 📤 Requesting session validation from Cockpit', {
      workspaceId,
      tokenPreview: sessionToken.substring(0, 20) + '...',
      cockpitOrigin,
    })
    if (source) {
      ;(source as Window).postMessage(message, cockpitOrigin)
    } else {
      window.parent.postMessage(message, cockpitOrigin)
    }
  }

  /**
   * Send RUNNER_READY back to Cockpit via the parent frame.
   * Uses cockpitOrigin to restrict the message to the legitimate parent only.
   */
  function sendReady(workspaceId: string, cockpitOrigin: string, source: MessageEventSource | null) {
    const message: WorkspaceReadyMessage = {
      type: 'RUNNER_READY',
      payload: {
        workspaceId,
        runnerOrigin: window.location.origin,
        version: RUNNER_VERSION,
        capabilities: ['hello-world'],
        status: 'ready',
      },
      timestamp: Date.now(),
    }
    log.info('[WORKSPACE] Sending RUNNER_READY', message)
    if (source) {
      ;(source as Window).postMessage(message, cockpitOrigin)
    } else {
      window.parent.postMessage(message, cockpitOrigin)
    }
  }

  /**
   * Send RUNNER_ERROR back to Cockpit via the parent frame.
   * Uses cockpitOrigin to restrict the message to the legitimate parent only.
   */
  function sendError(
    workspaceId: string,
    errorCode: string,
    message: string,
    cockpitOrigin: string,
    source: MessageEventSource | null,
  ) {
    const msg: WorkspaceErrorMessage = {
      type: 'RUNNER_ERROR',
      payload: { workspaceId, errorCode, message },
      timestamp: Date.now(),
    }
    log.error('[WORKSPACE] Sending RUNNER_ERROR', msg)
    if (source) {
      ;(source as Window).postMessage(msg, cockpitOrigin)
    } else {
      window.parent.postMessage(msg, cockpitOrigin)
    }
  }

  // ── Message handler ────────────────────────────────────────────────────────

  async function handleMessage(event: MessageEvent) {
    // ⚠️ CRITICAL: Log ALL incoming messages for debugging origin issues
    console.log('[useWorkspaceHandshake] 📨 postMessage received', {
      timestamp: new Date().toISOString(),
      origin: event.origin,
      dataType: (event.data as any)?.type,
      expectedOrigins: EXPECTED_COCKPIT_ORIGINS,
    })

    // Security: validate origin FIRST before processing any message content
    if (!EXPECTED_COCKPIT_ORIGINS.includes(event.origin)) {
      console.error('[useWorkspaceHandshake] ❌ REJECTED - Origin not in whitelist', {
        origin: event.origin,
        expectedOrigins: EXPECTED_COCKPIT_ORIGINS,
        messageType: (event.data as any)?.type,
        timestamp: new Date().toISOString(),
      })
      log.warn('[WORKSPACE] Rejected message from unexpected origin', { origin: event.origin, expected: EXPECTED_COCKPIT_ORIGINS })
      return
    }

    console.log('[useWorkspaceHandshake] ✅ Origin validated, processing message', {
      origin: event.origin,
      dataType: (event.data as any)?.type,
    })

    const data = event.data as any

    if (!data || !data.type) {
      console.warn('[useWorkspaceHandshake] ⚠️ Message has no type field', { data })
      return
    }

    // ── Handle SWITCH_THEME message ────────────────────────────────────────
    if (data.type === 'SWITCH_THEME') {
      const { theme } = (data as Partial<SwitchThemeMessage>).payload ?? {}
      log.info('[WORKSPACE] SWITCH_THEME received', {
        theme,
        hasTheme: !!theme,
        timestamp: new Date().toISOString(),
      })
      if (theme) {
        store.setTheme(theme)
        log.info('[WORKSPACE] Theme switched in store', {
          newTheme: theme,
          storedTheme: store.theme,
          match: theme === store.theme,
        })
      } else {
        log.warn('[WORKSPACE] SWITCH_THEME received but theme is empty', { payload: data.payload })
      }
      return
    }

    // ── Handle SWITCH_LOCALE message ───────────────────────────────────────
    if (data.type === 'SWITCH_LOCALE') {
      const { locale } = (data as Partial<SwitchLocaleMessage>).payload ?? {}
      log.info('[WORKSPACE] SWITCH_LOCALE received', {
        locale,
        hasLocale: !!locale,
        timestamp: new Date().toISOString(),
      })
      if (locale) {
        store.setLocale(locale)
        log.info('[WORKSPACE] Locale switched in store', {
          newLocale: locale,
          storedLocale: store.locale,
          match: locale === store.locale,
        })
      } else {
        log.warn('[WORKSPACE] SWITCH_LOCALE received but locale is empty', { payload: data.payload })
      }
      return
    }

    // ── Handle SYNC_CONFIG message (cockpit sends current config) ──────────
    if (data.type === 'SYNC_CONFIG') {
      const { theme, locale } = (data as Partial<SyncConfigMessage>).payload ?? {}
      log.info('[WORKSPACE] SYNC_CONFIG received', {
        hasTheme: !!theme,
        hasLocale: !!locale,
        locale,
        theme,
        timestamp: new Date().toISOString(),
      })
      if (theme) store.setTheme(theme)
      if (locale) {
        store.setLocale(locale)
        log.info('[WORKSPACE] Locale synced from config', {
          newLocale: locale,
          storedLocale: store.locale,
        })
      }
      log.debug('[WORKSPACE] Config synchronized', { theme, locale })
      return
    }

    // ── Handle VALIDATION_RESULT message (response from Cockpit validation) ──
    if (data.type === 'VALIDATION_RESULT') {
      const { workspaceId, success, userId, error } = (data as Partial<ValidationResultMessage>).payload ?? {}

      console.log('[useWorkspaceHandshake] 📥 VALIDATION_RESULT received', {
        workspaceId,
        success,
        userId,
        error,
      })

      if (!pendingValidationRequest) {
        console.warn('[useWorkspaceHandshake] ⚠️ VALIDATION_RESULT received but no pending request')
        return
      }

      if (success && userId) {
        store.setReady()
        log.info('[WORKSPACE] Session validation succeeded', { workspaceId, userId })
        console.log('[useWorkspaceHandshake] ✅ Validation succeeded, sending RUNNER_READY')
        sendReady(workspaceId, pendingValidationRequest.cockpitOrigin, pendingValidationRequest.source)
      } else {
        const code = 'VALIDATION_FAILED'
        const message = error || 'Session validation failed'
        store.setError(code, message)
        log.error('[WORKSPACE] Session validation failed', { code, message })
        console.error('[useWorkspaceHandshake] ❌ Validation failed, sending RUNNER_ERROR', { error })
        sendError(workspaceId, code, message, pendingValidationRequest.cockpitOrigin, pendingValidationRequest.source)
      }

      pendingValidationRequest = null
      return
    }

    // ── Handle INIT_WORKSPACE message ──────────────────────────────────────
    if (data.type !== 'INIT_WORKSPACE') {
      return
    }

    console.log('[useWorkspaceHandshake] 🚀 INIT_WORKSPACE message received', {
      timestamp: new Date().toISOString(),
      origin: event.origin,
      fullData: data,
    })

    log.info('[WORKSPACE] INIT_WORKSPACE received', data)

    const { workspaceId, sessionToken, userId, cockpitOrigin } = data.payload ?? {}

    console.log('[useWorkspaceHandshake] 📋 INIT_WORKSPACE payload analysis', {
      hasWorkspaceId: !!workspaceId,
      workspaceId,
      hasSessionToken: !!sessionToken,
      sessionTokenLength: sessionToken ? sessionToken.length : 0,
      sessionTokenPreview: sessionToken ? sessionToken.substring(0, 20) + '...' : 'MISSING',
      hasUserId: !!userId,
      userId,
      hasCockpitOrigin: !!cockpitOrigin,
      cockpitOrigin,
    })

    // Decode JWT to inspect audience and other claims
    if (sessionToken) {
      try {
        const parts = sessionToken.split('.')
        if (parts.length === 3) {
          const payload = JSON.parse(atob(parts[1]))
          console.log('[useWorkspaceHandshake] 🔐 JWT Claims:', {
            aud: payload.aud,
            sub: payload.sub,
            iat: payload.iat,
            exp: payload.exp,
            workspaceId: payload.workspaceId,
            allClaims: Object.keys(payload),
          })
        }
      } catch (e) {
        console.warn('[useWorkspaceHandshake] ⚠️ Failed to decode JWT:', e)
      }
    }

    log.info('[WORKSPACE] INIT_WORKSPACE payload parsed', {
      hasWorkspaceId: !!workspaceId,
      hasSessionToken: !!sessionToken,
      sessionTokenLength: sessionToken ? sessionToken.length : 0,
      sessionTokenPreview: sessionToken ? sessionToken.substring(0, 20) + '...' : 'MISSING',
      hasUserId: !!userId,
      hasCockpitOrigin: !!cockpitOrigin,
    })

    if (!workspaceId || !sessionToken || !cockpitOrigin) {
      const code = 'INVALID_PAYLOAD'
      const msg = 'Missing required fields in INIT_WORKSPACE payload'
      store.setError(code, msg)
      // Use event.origin as fallback if cockpitOrigin is missing in the payload
      sendError(workspaceId ?? '', code, msg, event.origin, event.source)
      return
    }

    store.initWorkspace({ workspaceId, sessionToken, userId: userId ?? '' })
    log.info('[WORKSPACE] Token stored in workspaceStore', {
      storedTokenLength: store.sessionToken.length,
      storedTokenPreview: store.sessionToken.substring(0, 20) + '...',
    })

    // Store pending validation request details for when VALIDATION_RESULT arrives
    pendingValidationRequest = {
      workspaceId,
      cockpitOrigin,
      source: event.source,
    }

    // Request Cockpit to validate the session (avoids CORS issues with loopback)
    requestValidation(workspaceId, sessionToken, cockpitOrigin, event.source)
  }

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  onMounted(() => {
    console.log('[useWorkspaceHandshake] 🎬 Component mounted, registering postMessage listener', {
      expectedOrigins: EXPECTED_COCKPIT_ORIGINS,
      windowLocation: window.location.href,
      timestamp: new Date().toISOString(),
    })
    window.addEventListener('message', handleMessage)
    log.info('[WORKSPACE] useWorkspaceHandshake mounted – listening for INIT_WORKSPACE')
  })

  onUnmounted(() => {
    console.log('[useWorkspaceHandshake] 🔌 Component unmounted, removing postMessage listener')
    window.removeEventListener('message', handleMessage)
  })

  return { store }
}
