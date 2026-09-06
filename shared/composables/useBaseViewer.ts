/**
 * useBaseViewer.ts
 *
 * Base composable for standalone viewers. Provides:
 * - MFE handshake management (INIT_WORKSPACE via postMessage)
 * - HTTP client delegating to apiService.ts
 * - Loading/error state management
 * - Utility helpers (formatDate)
 *
 * The handshake is transparent: onMounted registers a postMessage listener,
 * and loadData() internally waits for the handshake before executing the loader.
 *
 * Two validation modes:
 * - 'immediate' (default): INIT_WORKSPACE → setReady → RUNNER_READY
 * - 'validated': INIT_WORKSPACE → requestValidation → VALIDATION_RESULT → setReady
 *
 * Dependencies:
 * - vue (ref, computed, watch, onMounted, onUnmounted)
 * - pinia (useWorkspaceStore)
 * - @/services/apiService (getApiBaseUrl, normalizePath, apiFetch)
 * - @/utils/logger (createLogger)
 */

import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { getApiBaseUrl, normalizePath, apiFetch as apiServiceFetch } from '@/services/apiService'
import { createLogger } from '@/utils/logger'
import { normalizeLocale } from '@/utils/i18nUtils'
import i18nInstance from '@/i18n'
import type {
  InitWorkspaceMessage,
  SwitchThemeMessage,
  SwitchLocaleMessage,
  SyncConfigMessage,
  ValidationResultMessage,
  WorkspaceReadyMessage,
  WorkspaceErrorMessage,
  ValidateSessionRequestMessage,
} from '@/types/handshake'

const log = createLogger('base:viewer')

// ── Constants ────────────────────────────────────────────────────────────────

const RUNNER_VERSION = 'v2.0.0-phase1'
const HANDSHAKE_TIMEOUT_MS = 5000

/**
 * Allowed Cockpit origins. Messages from other origins are silently dropped.
 * Must be set via VITE_COCKPIT_ORIGINS env var (comma-separated list).
 * Preserves DeepSeek Pro security patch: .split(',').map(s => s.trim())
 */
const EXPECTED_COCKPIT_ORIGINS: string[] = (() => {
  const env = typeof import.meta !== 'undefined' ? (import.meta as any).env : {}
  const origins = env.VITE_COCKPIT_ORIGINS

  if (typeof origins === 'string' && origins.length > 0) {
    return origins.split(',').map((o: string) => o.trim()).filter(Boolean)
  }

  return ['http://localhost:5173', 'http://localhost:8000', 'http://127.0.0.1:5173', 'http://localhost:5052']
})()

// ── Options Interface ────────────────────────────────────────────────────────

export interface UseBaseViewerOptions {
  /**
   * Handshake validation mode.
   * - 'immediate': INIT_WORKSPACE → setReady immediately (for simple viewers)
   * - 'validated': INIT_WORKSPACE → request validation from Cockpit → setReady on result
   * @default 'immediate'
   */
  validationMode?: 'immediate' | 'validated'

  /**
   * i18n configuration for viewer-specific translations.
   * Messages are merged into the shared i18n instance (from @/i18n)
   * using normalizeLocale() to bridge locale code formats.
   */
  i18n?: {
    /** Viewer-specific messages to merge into the shared i18n instance.
     *  Each entry's locale is normalized (e.g., 'pt' → 'pt-BR') before merge. */
    messages?: { locale: string; messages: Record<string, any> }[]
  }
}

// ── Composable ───────────────────────────────────────────────────────────────

export function useBaseViewer(options: UseBaseViewerOptions = {}) {
  const validationMode = options.validationMode ?? 'immediate'
  const store = useWorkspaceStore()

  // ── i18n Auto-Setup ──────────────────────────────────────────────────
  if (options.i18n?.messages) {
    for (const { locale, messages } of options.i18n.messages) {
      const normalized = normalizeLocale(locale)
      i18nInstance.global.mergeLocaleMessage(normalized, messages)
    }
  }

  // ── URL Resolution ────────────────────────────────────────────────────
  const API_BASE = getApiBaseUrl()

  // ── Reactive State ────────────────────────────────────────────────────
  const loadingState = ref(true)
  const errorMessage = ref('')

  // ── isAuthenticated ───────────────────────────────────────────────────
  const isAuthenticated = computed(() => store.status === 'ready' && !!store.sessionToken)

  // ── Handshake internals ───────────────────────────────────────────────

  /** Callbacks registered via onReady(), fired once when handshake completes. */
  const _readyCallbacks: (() => void)[] = []

  /**
   * Register a callback that fires when the MFE handshake (INIT_WORKSPACE) completes.
   * If the handshake has already completed, the callback fires immediately.
   * Each callback fires at most once (one-shot registration).
   */
  function onReady(cb: () => void) {
    if (store.status === 'ready') {
      cb()
    } else {
      _readyCallbacks.push(cb)
    }
  }

  /** Fire all registered ready callbacks and clear the registry. */
  function _fireReady() {
    _readyCallbacks.forEach(cb => cb())
    _readyCallbacks.length = 0
  }

  /** Track pending validation request to match response with request. */
  let pendingValidationRequest: {
    workspaceId: string
    cockpitOrigin: string
    source: MessageEventSource | null
  } | null = null

  /**
   * Send RUNNER_READY back to Cockpit via the parent frame.
   * Uses cockpitOrigin to restrict the message to the legitimate parent only.
   * Security patch preserved: targetOrigin uses the validated cockpitOrigin (event.origin),
   * preventing message delivery to a malicious origin if the stored origin was tampered with.
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

  /**
   * Send VALIDATE_SESSION_REQUEST to Cockpit (parent frame).
   * Cockpit performs the actual validation fetch to avoid CORS issues with loopback addresses.
   */
  function requestValidation(
    workspaceId: string,
    sessionToken: string,
    cockpitOrigin: string,
    source: MessageEventSource | null,
  ) {
    const message: ValidateSessionRequestMessage = {
      type: 'VALIDATE_SESSION_REQUEST',
      payload: { workspaceId, sessionToken },
      timestamp: Date.now(),
    }
    log.info('[WORKSPACE] Requesting session validation from Cockpit', {
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

  /** Resolve a promise externally. */
  let handshakeResolve: (() => void) | null = null
  let handshakeReject: ((reason: Error) => void) | null = null
  let handshakeTimeout: ReturnType<typeof setTimeout> | null = null

  function clearHandshakeTimeout() {
    if (handshakeTimeout !== null) {
      clearTimeout(handshakeTimeout)
      handshakeTimeout = null
    }
  }

  /**
   * Wait for the handshake to complete or fail.
   * Returns a promise that resolves when store.status === 'ready' or
   * rejects after HANDSHAKE_TIMEOUT_MS.
   */
  function waitForHandshake(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (store.status === 'ready') {
        resolve()
        return
      }

      if (store.status === 'error') {
        reject(new Error(store.errorMessage || 'Handshake error'))
        return
      }

      handshakeResolve = resolve
      handshakeReject = reject

      handshakeTimeout = setTimeout(() => {
        handshakeTimeout = null
        store.setError('HANDSHAKE_TIMEOUT', 'Handshake timeout: no INIT_WORKSPACE received')
        errorMessage.value = 'Could not connect to workspace. Please try logging in or reloading.'
        reject(new Error('Handshake timeout'))
      }, HANDSHAKE_TIMEOUT_MS)
    })
  }

  // ── Message handler ───────────────────────────────────────────────────

  async function handleMessage(event: MessageEvent) {
    const msgOrigin = event.origin
    const data = event.data as any

    // Security: validate origin FIRST
    if (!EXPECTED_COCKPIT_ORIGINS.includes(msgOrigin)) {
      return
    }

    if (!data || !data.type) {
      return
    }

    // ── Handle SWITCH_THEME (post-handshake only) ───────────────────────
    if (data.type === 'SWITCH_THEME') {
      if (store.status !== 'ready') return
      const { theme } = (data as Partial<SwitchThemeMessage>).payload ?? {}
      if (theme) store.setTheme(theme)
      return
    }

    // ── Handle SWITCH_LOCALE (post-handshake only) ──────────────────────
    if (data.type === 'SWITCH_LOCALE') {
      if (store.status !== 'ready') return
      const { locale } = (data as Partial<SwitchLocaleMessage>).payload ?? {}
      if (locale) store.setLocale(locale)
      return
    }

    // ── Handle SYNC_CONFIG (post-handshake only) ────────────────────────
    if (data.type === 'SYNC_CONFIG') {
      if (store.status !== 'ready') return
      const { theme, locale } = (data as Partial<SyncConfigMessage>).payload ?? {}
      if (theme) store.setTheme(theme)
      if (locale) store.setLocale(locale)
      return
    }

    // ── Handle VALIDATION_RESULT ────────────────────────────────────────
    if (data.type === 'VALIDATION_RESULT') {
      const { workspaceId, success, userId, error: errorVal } = (data as Partial<ValidationResultMessage>).payload ?? {}

      if (!pendingValidationRequest) {
        log.warn('[WORKSPACE] VALIDATION_RESULT received but no pending request')
        return
      }

      clearHandshakeTimeout()

      if (success && userId) {
        store.setReady()
        log.info('[WORKSPACE] Session validation succeeded', { workspaceId, userId })
        sendReady(workspaceId, pendingValidationRequest.cockpitOrigin, pendingValidationRequest.source)
        _fireReady()
        handshakeResolve?.()
      } else {
        const code = 'VALIDATION_FAILED'
        const msg = errorVal || 'Session validation failed'
        store.setError(code, msg)
        log.error('[WORKSPACE] Session validation failed', { code, message: msg })
        sendError(workspaceId, code, msg, pendingValidationRequest.cockpitOrigin, pendingValidationRequest.source)
        handshakeReject?.(new Error(msg))
      }

      pendingValidationRequest = null
      return
    }

    // ── Handle INIT_WORKSPACE ───────────────────────────────────────────
    if (data.type !== 'INIT_WORKSPACE') {
      return
    }

    log.info('[WORKSPACE] INIT_WORKSPACE received', data)

    const { workspaceId, sessionToken, userId, cockpitOrigin, planetOwnerId } =
      (data as Partial<InitWorkspaceMessage>).payload ?? {}

    if (!workspaceId || !sessionToken || !cockpitOrigin) {
      const code = 'INVALID_PAYLOAD'
      const msg = 'Missing required fields in INIT_WORKSPACE payload'
      store.setError(code, msg)
      sendError(workspaceId ?? '', code, msg, event.origin, event.source)
      return
    }

    store.initWorkspace({ workspaceId, sessionToken, userId: userId ?? '', planetOwnerId })

    if (validationMode === 'validated') {
      // Two-step validation: request Cockpit to validate the session
      pendingValidationRequest = {
        workspaceId,
        cockpitOrigin,
        source: event.source,
      }
      requestValidation(workspaceId, sessionToken, cockpitOrigin, event.source)
    } else {
      // Immediate: set ready right away
      clearHandshakeTimeout()
      store.setReady()
      sendReady(workspaceId, cockpitOrigin, event.source)
      _fireReady()
      handshakeResolve?.()
    }
  }

  // ── HTTP Client ───────────────────────────────────────────────────────

  async function apiFetch(path: string, options: RequestInit = {}) {
    try {
      const response = await apiServiceFetch(path, options)

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
      }

      return response.json()
    } catch (err) {
      errorMessage.value = (err as Error).message
      throw err
    }
  }

  // ── Lifecycle Helper ──────────────────────────────────────────────────

  /**
   * Wraps a data-loading function with loading/error state management.
   * Internally waits for the MFE handshake before executing the loader.
   * If the handshake times out, errorMessage is set but the loader still
   * runs (graceful degradation — public data can still load).
   */
  async function loadData(loader: () => Promise<void>) {
    loadingState.value = true
    errorMessage.value = ''

    try {
      // Wait for handshake before executing the loader
      if (store.status === 'pending') {
        try {
          await waitForHandshake()
        } catch {
          // Handshake timed out or failed — continue with graceful degradation
          if (!errorMessage.value) {
            errorMessage.value = 'Connection to workspace failed. Showing public content only.'
          }
        }
      }

      await loader()
    } catch (err) {
      errorMessage.value = (err as Error).message
    } finally {
      loadingState.value = false
    }
  }

  // ── i18n Utilities ───────────────────────────────────────────────────

  /**
   * Load and merge cell type translations into the shared i18n instance.
   * Convenience wrapper around cellI18nLoader.loadCellI18n().
   * Viewers can use this to ensure cell translations are available.
   */
  async function mergeCellI18n(cellTypeName: string): Promise<boolean> {
    const { loadCellI18n } = await import('#canonical/shared/utils/cellI18nLoader')
    return loadCellI18n(cellTypeName)
  }

  // ── Utilities ─────────────────────────────────────────────────────────

  function formatDate(isoStr?: string): string {
    if (!isoStr) return ''
    const d = new Date(isoStr)
    if (isNaN(d.getTime())) return isoStr
    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
  }

  // ── Lifecycle ─────────────────────────────────────────────────────────

  onMounted(() => {
    window.addEventListener('message', handleMessage)
    log.info('[WORKSPACE] useBaseViewer mounted – listening for INIT_WORKSPACE')
  })

  onUnmounted(() => {
    window.removeEventListener('message', handleMessage)
    clearHandshakeTimeout()
    log.info('[WORKSPACE] useBaseViewer unmounted – listener removed')
  })

  // ── Return ────────────────────────────────────────────────────────────

  return {
    // URL resolution
    API_BASE,
    normalizePath,

    // Reactive state
    loadingState,
    errorMessage,
    isAuthenticated,

    // HTTP client (delegates to apiService.ts)
    apiFetch,

    // Lifecycle
    loadData,

    // MFE Ready Lifecycle
    onReady,

    // Utilities
    formatDate,

    // i18n
    mergeCellI18n,
  }
}
