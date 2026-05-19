/**
 * @vitest-environment jsdom
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'

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
// apiFetch delegates to global.fetch so tests can control responses
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

import { useBaseViewer } from '../useBaseViewer'

describe('useBaseViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    // Default mock fetch: 200 OK with empty JSON
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

  // ── Auth ────────────────────────────────────────────────────────────────

  describe('checkAuth', () => {
    let originalFetch: typeof globalThis.fetch

    beforeEach(() => {
      originalFetch = globalThis.fetch
      globalThis.fetch = vi.fn()
    })

    afterEach(() => {
      globalThis.fetch = originalFetch
    })

    it('binds session when localStorage token exists and session-bind succeeds', async () => {
      localStorage.setItem('scareverse_token', 'test-jwt')
      ;(globalThis.fetch as any).mockResolvedValue({ ok: true })

      const { checkAuth, isAuthenticated, sessionToken } = useBaseViewer()
      await checkAuth()

      expect(isAuthenticated.value).toBe(true)
      expect(sessionToken.value).toBe('test-jwt')
    })

    it('falls back to cookie probe when session-bind fails', async () => {
      localStorage.setItem('scareverse_token', 'test-jwt')
      // session-bind fails, cookie probe succeeds
      ;(globalThis.fetch as any)
        .mockResolvedValueOnce({ ok: false })
        .mockResolvedValueOnce({ ok: true })

      const { checkAuth, isAuthenticated } = useBaseViewer()
      await checkAuth()

      expect(isAuthenticated.value).toBe(true)
    })

    it('sets isAuthenticated to false when no token and cookie probe fails', async () => {
      ;(globalThis.fetch as any).mockResolvedValue({ ok: false })

      const { checkAuth, isAuthenticated } = useBaseViewer()
      await checkAuth()

      expect(isAuthenticated.value).toBe(false)
    })

    it('sets isAuthenticated to false on network error in cookie probe', async () => {
      ;(globalThis.fetch as any).mockRejectedValue(new Error('Network error'))

      const { checkAuth, isAuthenticated } = useBaseViewer()
      await checkAuth()

      expect(isAuthenticated.value).toBe(false)
    })
  })

  describe('bindSession', () => {
    let originalFetch: typeof globalThis.fetch

    beforeEach(() => {
      originalFetch = globalThis.fetch
      globalThis.fetch = vi.fn()
    })

    afterEach(() => {
      globalThis.fetch = originalFetch
    })

    it('returns true when session-bind succeeds', async () => {
      ;(globalThis.fetch as any).mockResolvedValue({ ok: true })

      const { bindSession } = useBaseViewer()
      const result = await bindSession('test-jwt')

      expect(result).toBe(true)
    })

    it('returns false when session-bind fails', async () => {
      ;(globalThis.fetch as any).mockResolvedValue({ ok: false })

      const { bindSession } = useBaseViewer()
      const result = await bindSession('test-jwt')

      expect(result).toBe(false)
    })

    it('returns false on network error', async () => {
      ;(globalThis.fetch as any).mockRejectedValue(new Error('Network error'))

      const { bindSession } = useBaseViewer()
      const result = await bindSession('test-jwt')

      expect(result).toBe(false)
    })
  })

  // ── Lifecycle ───────────────────────────────────────────────────────────

  describe('loadData', () => {
    it('sets loadingState true, calls loader, then sets loadingState false', async () => {
      const { loadData, loadingState } = useBaseViewer()
      const loader = vi.fn().mockResolvedValue(undefined)

      const promise = loadData(loader)
      expect(loadingState.value).toBe(true)
      await promise

      expect(loader).toHaveBeenCalledOnce()
      expect(loadingState.value).toBe(false)
    })

    it('clears errorMessage before loading and sets it on error', async () => {
      const { loadData, loadingState, errorMessage } = useBaseViewer()
      errorMessage.value = 'old error'
      const loader = vi.fn().mockRejectedValue(new Error('Load failed'))

      await loadData(loader)

      expect(errorMessage.value).toBe('Load failed')
      expect(loadingState.value).toBe(false)
    })

    it('finishes loading even if loader throws', async () => {
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

    it('isAuthenticated starts false', () => {
      const { isAuthenticated } = useBaseViewer()
      expect(isAuthenticated.value).toBe(false)
    })

    it('API_BASE resolves to mocked value', () => {
      const { API_BASE } = useBaseViewer()
      expect(API_BASE).toBe('http://localhost:5050')
    })
  })

  describe('return shape', () => {
    it('exposes loadingState but NOT loadingMessage', () => {
      const result = useBaseViewer()
      expect(result).toHaveProperty('loadingState')
      expect(result).not.toHaveProperty('loadingMessage')
    })

    it('exposes apiFetch, bindSession, checkAuth', () => {
      const result = useBaseViewer()
      expect(result).toHaveProperty('apiFetch')
      expect(result).toHaveProperty('bindSession')
      expect(result).toHaveProperty('checkAuth')
    })

    it('does NOT expose TOKEN_KEY', () => {
      const result = useBaseViewer()
      expect(result).not.toHaveProperty('TOKEN_KEY')
    })
  })
})
