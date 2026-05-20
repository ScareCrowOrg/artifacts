/**
 * @vitest-environment jsdom
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

// Mock localStorage since jsdom in this environment doesn't provide it
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value },
    removeItem: (key: string) => { delete store[key] },
    clear: () => { store = {} },
    get length() { return Object.keys(store).length },
    key: (i: number) => Object.keys(store)[i] ?? null,
  }
})()
Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock, writable: true })

// Mock apiService BEFORE importing useBaseViewer
vi.mock('@/services/apiService', () => ({
  getApiBaseUrl: vi.fn(() => 'http://localhost:5050'),
  normalizePath: vi.fn((path: string) => {
    if (!path.startsWith('/')) return path
    if (path.includes('/api/')) return `http://localhost:5050${path}`
    return `http://localhost:5050/api${path}`
  }),
  apiFetch: vi.fn(async (path: string, options: RequestInit = {}) => {
    return (globalThis as any).__mockFetch(path, options)
  }),
}))

// Mock logger to avoid console noise in tests
vi.mock('@/utils/logger', () => ({
  createLogger: vi.fn(() => ({
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    success: vi.fn(),
    isEnabled: vi.fn(() => false),
    getNamespace: vi.fn(() => 'test'),
  })),
}))

import { useBaseViewer } from '../useBaseViewer'
import { useWorkspaceStore } from '@/stores/workspaceStore'

// ── Helpers ─────────────────────────────────────────────────────────────────

function createTestWrapper(options: { validationMode?: 'immediate' | 'validated' } = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)

  const TestComp = defineComponent({
    setup() {
      return useBaseViewer(options)
    },
    template: '<div></div>',
  })

  const wrapper = mount(TestComp, {
    global: { plugins: [pinia] },
  })

  return { wrapper, pinia }
}

/** Dispatch a postMessage event on window as the Cockpit would. */
function dispatchCockpitMessage(
  type: string,
  payload: Record<string, any>,
  origin = 'http://localhost:5173',
) {
  window.dispatchEvent(new MessageEvent('message', {
    data: { type, payload, timestamp: Date.now() },
    origin,
  }))
}

/**
 * LoadData blocks on handshake when store.status === 'pending'.
 * Call this to set the store to 'ready' before tests that don't test handshake.
 */
function makeStoreReady() {
  const store = useWorkspaceStore()
  // initWorkspace sets status to 'pending' — we need to directly set it to 'ready'
  // to avoid going through the handshake path
  ;(store as any).status = 'ready'
}

describe('useBaseViewer', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.clear()
    ;(globalThis as any).__mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
      text: () => Promise.resolve(''),
    })
  })

  // ── URL Resolution ──────────────────────────────────────────────────────

  describe('normalizePath', () => {
    it('adds /api prefix to paths without /api/', () => {
      const { normalizePath } = useBaseViewer()
      const result = normalizePath('/inbox/messages')
      expect(result).toBe('http://localhost:5050/api/inbox/messages')
    })

    it('preserves paths that already contain /api/', () => {
      const { normalizePath } = useBaseViewer()
      const result = normalizePath('/api/v1/auth/session-bind')
      expect(result).toBe('http://localhost:5050/api/v1/auth/session-bind')
    })

    it('returns full URLs as-is when path does not start with /', () => {
      const { normalizePath } = useBaseViewer()
      const result = normalizePath('http://other-host/api/test')
      expect(result).toBe('http://other-host/api/test')
    })
  })

  // ── HTTP Client ─────────────────────────────────────────────────────────

  describe('apiFetch', () => {
    it('returns JSON on successful response', async () => {
      const mockData = { id: 1, name: 'test' }
      ;(globalThis as any).__mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockData),
        text: () => Promise.resolve(''),
      })

      const { apiFetch } = useBaseViewer()
      const result = await apiFetch('/api/inbox/messages')

      expect(result).toEqual(mockData)
    })

    it('sets errorMessage and throws on HTTP error with detail', async () => {
      ;(globalThis as any).__mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        statusText: 'Forbidden',
        json: () => Promise.resolve({ detail: 'Access denied' }),
        text: () => Promise.resolve('Access denied'),
      })

      const { apiFetch, errorMessage } = useBaseViewer()
      await expect(apiFetch('/api/inbox/requests')).rejects.toThrow('Access denied')
      expect(errorMessage.value).toContain('Access denied')
    })

    it('sets errorMessage and throws on HTTP error without detail', async () => {
      ;(globalThis as any).__mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        json: () => Promise.reject(new Error('parse error')),
        text: () => Promise.resolve('Server error'),
      })

      const { apiFetch, errorMessage } = useBaseViewer()
      await expect(apiFetch('/api/data')).rejects.toThrow('HTTP 500')
      expect(errorMessage.value).toContain('HTTP 500')
    })

    it('sets errorMessage and throws on network error', async () => {
      ;(globalThis as any).__mockFetch = vi.fn().mockRejectedValue(new Error('Network failure'))

      const { apiFetch, errorMessage } = useBaseViewer()
      await expect(apiFetch('/api/data')).rejects.toThrow('Network failure')
      expect(errorMessage.value).toBe('Network failure')
    })
  })

  // ── Lifecycle ───────────────────────────────────────────────────────────

  describe('loadData', () => {
    it('sets loadingState true, calls loader, then sets loadingState false', async () => {
      makeStoreReady()
      const { loadData, loadingState } = useBaseViewer()
      const loader = vi.fn().mockResolvedValue(undefined)

      const promise = loadData(loader)
      expect(loadingState.value).toBe(true)
      await promise

      expect(loader).toHaveBeenCalledOnce()
      expect(loadingState.value).toBe(false)
    })

    it('clears errorMessage before loading and sets it on error', async () => {
      makeStoreReady()
      const { loadData, loadingState, errorMessage } = useBaseViewer()
      errorMessage.value = 'old error'
      const loader = vi.fn().mockRejectedValue(new Error('Load failed'))

      await loadData(loader)

      expect(errorMessage.value).toBe('Load failed')
      expect(loadingState.value).toBe(false)
    })

    it('finishes loading even if loader throws', async () => {
      makeStoreReady()
      const { loadData, loadingState } = useBaseViewer()
      const loader = vi.fn().mockRejectedValue(new Error('Any error'))

      await loadData(loader)

      expect(loadingState.value).toBe(false)
    })
  })

  // ── Utilities ───────────────────────────────────────────────────────────

  describe('formatDate', () => {
    it('returns empty string for undefined input', () => {
      const { formatDate } = useBaseViewer()
      expect(formatDate()).toBe('')
    })

    it('returns empty string for empty string input', () => {
      const { formatDate } = useBaseViewer()
      expect(formatDate('')).toBe('')
    })

    it('formats ISO date string to locale date', () => {
      const { formatDate } = useBaseViewer()
      const result = formatDate('2026-05-19T12:00:00Z')
      expect(result).toBeTruthy()
      expect(typeof result).toBe('string')
    })

    it('returns the original string if it cannot be parsed', () => {
      const { formatDate } = useBaseViewer()
      const result = formatDate('not-a-date')
      expect(result).toBe('not-a-date')
    })
  })

  // ── Initial State & API Shape ───────────────────────────────────────────

  describe('initial state', () => {
    it('loadingState starts as true', () => {
      const { loadingState } = useBaseViewer()
      expect(loadingState.value).toBe(true)
    })

    it('errorMessage starts empty', () => {
      const { errorMessage } = useBaseViewer()
      expect(errorMessage.value).toBe('')
    })

    it('API_BASE resolves to mocked value', () => {
      const { API_BASE } = useBaseViewer()
      expect(API_BASE).toBe('http://localhost:5050')
    })
  })

  describe('return shape', () => {
    it('exposes loadingState, errorMessage, isAuthenticated', () => {
      const result = useBaseViewer()
      expect(result).toHaveProperty('loadingState')
      expect(result).toHaveProperty('errorMessage')
      expect(result).toHaveProperty('isAuthenticated')
    })

    it('exposes apiFetch but NOT auth methods (bindSession, checkAuth)', () => {
      const result = useBaseViewer()
      expect(result).toHaveProperty('apiFetch')
      expect(result).not.toHaveProperty('bindSession')
      expect(result).not.toHaveProperty('checkAuth')
    })

    it('does NOT expose TOKEN_KEY or sessionToken', () => {
      const result = useBaseViewer()
      expect(result).not.toHaveProperty('TOKEN_KEY')
      expect(result).not.toHaveProperty('sessionToken')
    })
  })

  // ── Handshake Tests ─────────────────────────────────────────────────────

  describe('handshake (immediate mode)', () => {
    it('INIT_WORKSPACE received → store populated → isAuthenticated = true', async () => {
      const { wrapper } = createTestWrapper()
      const store = useWorkspaceStore()
      expect(store.status).toBe('pending')

      dispatchCockpitMessage('INIT_WORKSPACE', {
        workspaceId: 'ws-123',
        sessionToken: 'tok_abc123',
        cockpitOrigin: 'http://localhost:5173',
        userId: 'user-42',
      })

      await nextTick()

      expect(store.sessionToken).toBe('tok_abc123')
      expect(store.workspaceId).toBe('ws-123')
      expect(store.status).toBe('ready')
      expect((wrapper.vm as any).isAuthenticated).toBe(true)
    })

    it('origin mismatch → message ignored', async () => {
      const { wrapper } = createTestWrapper()
      const store = useWorkspaceStore()

      dispatchCockpitMessage('INIT_WORKSPACE', {
        workspaceId: 'ws-123',
        sessionToken: 'tok_abc123',
        cockpitOrigin: 'http://localhost:5173',
        userId: 'user-42',
      }, 'http://evil.com')

      await nextTick()

      expect(store.sessionToken).toBe('')
      expect(store.status).toBe('pending')
      expect((wrapper.vm as any).isAuthenticated).toBe(false)
    })

    it('missing required fields → error state', async () => {
      const { wrapper } = createTestWrapper()
      const store = useWorkspaceStore()

      dispatchCockpitMessage('INIT_WORKSPACE', {
        sessionToken: 'tok_abc123',
        // missing workspaceId, cockpitOrigin
      })

      await nextTick()

      expect(store.status).toBe('error')
      expect(store.errorCode).toBe('INVALID_PAYLOAD')
    })

    it('SWITCH_THEME received → store.theme updated', async () => {
      const { wrapper } = createTestWrapper()
      const store = useWorkspaceStore()
      expect(store.theme).toBe('auto')

      // First establish handshake
      dispatchCockpitMessage('INIT_WORKSPACE', {
        workspaceId: 'ws-123',
        sessionToken: 'tok_abc123',
        cockpitOrigin: 'http://localhost:5173',
        userId: 'user-42',
      })

      await nextTick()
      expect(store.status).toBe('ready')

      // Send SWITCH_THEME
      dispatchCockpitMessage('SWITCH_THEME', { theme: 'dark' })
      await nextTick()

      expect(store.theme).toBe('dark')
    })
  })

  describe('handshake (validated mode)', () => {
    it('INIT_WORKSPACE → pending → VALIDATION_RESULT success → ready', async () => {
      const { wrapper } = createTestWrapper({ validationMode: 'validated' })
      const store = useWorkspaceStore()

      // Send INIT_WORKSPACE — should not setReady yet
      dispatchCockpitMessage('INIT_WORKSPACE', {
        workspaceId: 'ws-123',
        sessionToken: 'tok_abc123',
        cockpitOrigin: 'http://localhost:5173',
        userId: 'user-42',
      })

      await nextTick()

      expect(store.sessionToken).toBe('tok_abc123')
      expect(store.status).toBe('pending') // not ready yet
      expect((wrapper.vm as any).isAuthenticated).toBe(false)

      // Send VALIDATION_RESULT success
      dispatchCockpitMessage('VALIDATION_RESULT', {
        workspaceId: 'ws-123',
        success: true,
        userId: 'user-42',
      })

      await nextTick()

      expect(store.status).toBe('ready')
      expect((wrapper.vm as any).isAuthenticated).toBe(true)
    })

    it('VALIDATION_RESULT fail → store.status = error', async () => {
      const { wrapper } = createTestWrapper({ validationMode: 'validated' })
      const store = useWorkspaceStore()

      dispatchCockpitMessage('INIT_WORKSPACE', {
        workspaceId: 'ws-123',
        sessionToken: 'tok_abc123',
        cockpitOrigin: 'http://localhost:5173',
        userId: 'user-42',
      })

      await nextTick()
      expect(store.status).toBe('pending')

      // Send VALIDATION_RESULT failure
      dispatchCockpitMessage('VALIDATION_RESULT', {
        workspaceId: 'ws-123',
        success: false,
        error: 'Session expired',
      })

      await nextTick()

      expect(store.status).toBe('error')
      expect(store.errorCode).toBe('VALIDATION_FAILED')
      expect(store.errorMessage).toBe('Session expired')
    })
  })
})
