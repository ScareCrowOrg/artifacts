/**
 * Tests for sessionsActions.js
 *
 * Tests cover:
 * - registerSessionsActions registration
 * - create_session action: success, missing params, API error, HTTP error
 * - list_user_sessions action: success, missing params, API error, empty list
 * - close_session action: success, missing params, API error
 * - chatStore integration (insertContentIntoInput, addAttachment)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { registerSessionsActions } from '../sessionsActions.js'

// ── Mock dependencies ─────────────────────────────────────────────────────────

vi.mock('@/utils/logger', () => ({
  createLogger: () => ({
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  }),
}))

vi.mock('@/services/apiService', () => ({
  default: {
    fetch: vi.fn(),
  },
}))

import apiService from '@/services/apiService'

// ── Helper factories ──────────────────────────────────────────────────────────

/**
 * Build a mock registerAction function that captures the registered actions.
 * Returns an object with the registry map and the registerAction spy.
 */
function buildRegistry() {
  const actions = {}
  const registerAction = vi.fn((name, handler, meta) => {
    actions[name] = { handler, meta }
  })
  return { actions, registerAction }
}

/**
 * Create a minimal mock chatStore.
 */
function makeChatStore() {
  return {
    insertContentIntoInput: vi.fn(),
    addAttachment: vi.fn(),
  }
}

/**
 * Create a minimal context object passed as the second argument to each action.
 */
function makeCtx(chatStore = null) {
  return { chatStore }
}

/**
 * Build a minimal successful fetch Response mock.
 */
function makeOkResponse(body) {
  return {
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue(body),
  }
}

/**
 * Build a failed fetch Response mock with an error body.
 */
function makeErrorResponse(status, detail) {
  return {
    ok: false,
    status,
    statusText: 'Error',
    json: vi.fn().mockResolvedValue({ detail }),
  }
}

// ── Setup ─────────────────────────────────────────────────────────────────────

describe('registerSessionsActions', () => {
  let actions
  let registerAction

  beforeEach(() => {
    vi.clearAllMocks()
    const registry = buildRegistry()
    actions = registry.actions
    registerAction = registry.registerAction
    registerSessionsActions(registerAction)
  })

  it('registers exactly three actions', () => {
    expect(registerAction).toHaveBeenCalledTimes(3)
  })

  it('registers create_session action', () => {
    expect(actions).toHaveProperty('create_session')
  })

  it('registers list_user_sessions action', () => {
    expect(actions).toHaveProperty('list_user_sessions')
  })

  it('registers close_session action', () => {
    expect(actions).toHaveProperty('close_session')
  })

  it('create_session has correct metadata', () => {
    const { meta } = actions['create_session']
    expect(meta.category).toBe('sessions')
    expect(meta.params.some(p => p.name === 'user_id' && p.required)).toBe(true)
  })

  it('list_user_sessions has correct metadata', () => {
    const { meta } = actions['list_user_sessions']
    expect(meta.category).toBe('sessions')
    expect(meta.params.some(p => p.name === 'user_id' && p.required)).toBe(true)
  })

  it('close_session has correct metadata', () => {
    const { meta } = actions['close_session']
    expect(meta.category).toBe('sessions')
    expect(meta.params.some(p => p.name === 'session_id' && p.required)).toBe(true)
  })
})

// ── create_session ─────────────────────────────────────────────────────────────

describe('create_session action', () => {
  let handler

  beforeEach(() => {
    vi.clearAllMocks()
    const registry = buildRegistry()
    registerSessionsActions(registry.registerAction)
    handler = registry.actions['create_session'].handler
  })

  it('throws when user_id is missing', async () => {
    await expect(handler({}, makeCtx())).rejects.toThrow('user_id is required')
  })

  it('throws when user_id is undefined', async () => {
    await expect(handler({ user_id: undefined }, makeCtx())).rejects.toThrow(
      'user_id is required'
    )
  })

  it('calls apiService.fetch with correct path and method', async () => {
    const mockSession = {
      id: 'session-001',
      user_id: 'user-abc',
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 7 * 86400 * 1000).toISOString(),
      active: true,
    }
    const mockResponse = {
      session: mockSession,
      token: 'eyJhbGciOiJFZERTQSJ9.abc.def',
      user: { name: 'Alice', email: 'alice@example.com' },
    }

    apiService.fetch.mockResolvedValue(makeOkResponse(mockResponse))

    await handler({ user_id: 'user-abc' }, makeCtx())

    expect(apiService.fetch).toHaveBeenCalledWith(
      '/api/sessions/create',
      expect.objectContaining({ method: 'POST' })
    )

    const callArgs = apiService.fetch.mock.calls[0]
    const body = JSON.parse(callArgs[1].body)
    expect(body.user_id).toBe('user-abc')
  })

  it('returns success: true with data on success', async () => {
    const mockSession = {
      id: 'session-001',
      user_id: 'user-abc',
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 7 * 86400 * 1000).toISOString(),
      active: true,
    }
    const mockResponse = {
      session: mockSession,
      token: 'eyJhbGciOiJFZERTQSJ9.abc.def',
      user: { name: 'Alice', email: 'alice@example.com' },
    }

    apiService.fetch.mockResolvedValue(makeOkResponse(mockResponse))

    const result = await handler({ user_id: 'user-abc' }, makeCtx())

    expect(result.success).toBe(true)
    expect(result.data).toEqual(mockResponse)
  })

  it('calls chatStore.insertContentIntoInput with formatted output', async () => {
    const mockSession = {
      id: 'session-abc-123',
      user_id: 'user-abc',
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 7 * 86400 * 1000).toISOString(),
      active: true,
    }
    const mockResponse = {
      session: mockSession,
      token: 'eyJhbGciOiJFZERTQSJ9.longtoken.signature',
      user: { name: 'Alice', email: 'alice@example.com' },
    }

    apiService.fetch.mockResolvedValue(makeOkResponse(mockResponse))
    const chatStore = makeChatStore()

    await handler({ user_id: 'user-abc' }, makeCtx(chatStore))

    expect(chatStore.insertContentIntoInput).toHaveBeenCalledOnce()
    const content = chatStore.insertContentIntoInput.mock.calls[0][0].content
    expect(content).toContain('Session Created Successfully')
    expect(content).toContain('session-abc-123')
    expect(content).toContain('user-abc')
  })

  it('does not call chatStore when chatStore is null', async () => {
    const mockSession = {
      id: 'session-001',
      user_id: 'user-abc',
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 7 * 86400 * 1000).toISOString(),
      active: true,
    }
    apiService.fetch.mockResolvedValue(
      makeOkResponse({
        session: mockSession,
        token: 'tok',
        user: { name: 'Alice', email: 'alice@example.com' },
      })
    )

    // Should not throw
    const result = await handler({ user_id: 'user-abc' }, makeCtx(null))
    expect(result.success).toBe(true)
  })

  it('throws an error when HTTP response is not ok', async () => {
    apiService.fetch.mockResolvedValue(
      makeErrorResponse(404, 'User not found')
    )

    await expect(handler({ user_id: 'ghost' }, makeCtx())).rejects.toThrow(
      'User not found'
    )
  })

  it('propagates network errors', async () => {
    apiService.fetch.mockRejectedValue(new Error('Network failure'))

    await expect(handler({ user_id: 'user-abc' }, makeCtx())).rejects.toThrow(
      'Network failure'
    )
  })

  it('uses fallback detail when JSON parse fails on error response', async () => {
    const errorResponse = {
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: vi.fn().mockRejectedValue(new SyntaxError('invalid json')),
    }
    apiService.fetch.mockResolvedValue(errorResponse)

    await expect(handler({ user_id: 'user-abc' }, makeCtx())).rejects.toThrow(
      'HTTP 500: Internal Server Error'
    )
  })

  it('shows N/A for missing user name and email in formatted output', async () => {
    // Covers the `|| 'N/A'` branch (lines 62-63) when name/email are absent
    const mockSession = {
      id: 'session-no-user-details',
      user_id: 'user-abc',
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 7 * 86400 * 1000).toISOString(),
      active: true,
    }
    const mockResponse = {
      session: mockSession,
      token: 'tok.some.jwt',
      // name and email deliberately omitted to cover the `|| 'N/A'` branch
      user: {},
    }

    apiService.fetch.mockResolvedValue(makeOkResponse(mockResponse))
    const chatStore = makeChatStore()

    await handler({ user_id: 'user-abc' }, makeCtx(chatStore))

    const content = chatStore.insertContentIntoInput.mock.calls[0][0].content
    expect(content).toContain('Name: N/A')
    expect(content).toContain('Email: N/A')
  })
})

// ── list_user_sessions ────────────────────────────────────────────────────────

describe('list_user_sessions action', () => {
  let handler

  beforeEach(() => {
    vi.clearAllMocks()
    const registry = buildRegistry()
    registerSessionsActions(registry.registerAction)
    handler = registry.actions['list_user_sessions'].handler
  })

  it('throws when user_id is missing', async () => {
    await expect(handler({}, makeCtx())).rejects.toThrow('user_id is required')
  })

  it('calls apiService.fetch with URL-encoded user_id', async () => {
    apiService.fetch.mockResolvedValue(makeOkResponse([]))

    await handler({ user_id: 'user/with/slashes' }, makeCtx())

    const url = apiService.fetch.mock.calls[0][0]
    expect(url).toContain(encodeURIComponent('user/with/slashes'))
  })

  it('returns success: true with data on success', async () => {
    apiService.fetch.mockResolvedValue(makeOkResponse([]))

    const result = await handler({ user_id: 'user-abc' }, makeCtx())

    expect(result.success).toBe(true)
    expect(result.data).toEqual([])
  })

  it('calls insertContentIntoInput for small session lists', async () => {
    const sessions = [
      {
        id: 'sess-1',
        user_id: 'user-abc',
        active: true,
        created_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 86400 * 1000).toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]
    apiService.fetch.mockResolvedValue(makeOkResponse(sessions))
    const chatStore = makeChatStore()

    await handler({ user_id: 'user-abc' }, makeCtx(chatStore))

    expect(chatStore.insertContentIntoInput).toHaveBeenCalledOnce()
  })

  it('shows "No sessions found" message when list is empty', async () => {
    apiService.fetch.mockResolvedValue(makeOkResponse([]))
    const chatStore = makeChatStore()

    await handler({ user_id: 'user-abc' }, makeCtx(chatStore))

    const content = chatStore.insertContentIntoInput.mock.calls[0][0].content
    expect(content).toContain('No sessions found')
  })

  it('groups sessions into active and inactive', async () => {
    const sessions = [
      {
        id: 'sess-active',
        user_id: 'user-abc',
        active: true,
        created_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 86400 * 1000).toISOString(),
        updated_at: new Date().toISOString(),
      },
      {
        id: 'sess-inactive',
        user_id: 'user-abc',
        active: false,
        created_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 86400 * 1000).toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]
    apiService.fetch.mockResolvedValue(makeOkResponse(sessions))
    const chatStore = makeChatStore()

    await handler({ user_id: 'user-abc' }, makeCtx(chatStore))

    const content = chatStore.insertContentIntoInput.mock.calls[0][0].content
    expect(content).toContain('Active Sessions')
    expect(content).toContain('Inactive Sessions')
  })

  it('marks expired but active sessions with EXPIRED warning', async () => {
    const sessions = [
      {
        id: 'sess-expired',
        user_id: 'user-abc',
        active: true,
        created_at: new Date(Date.now() - 14 * 86400 * 1000).toISOString(),
        // Expired 7 days ago
        expires_at: new Date(Date.now() - 7 * 86400 * 1000).toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]
    apiService.fetch.mockResolvedValue(makeOkResponse(sessions))
    const chatStore = makeChatStore()

    await handler({ user_id: 'user-abc' }, makeCtx(chatStore))

    const content = chatStore.insertContentIntoInput.mock.calls[0][0].content
    expect(content).toContain('EXPIRED')
  })

  it('throws on HTTP error response', async () => {
    apiService.fetch.mockResolvedValue(
      makeErrorResponse(403, 'Forbidden: not your sessions')
    )

    await expect(handler({ user_id: 'user-abc' }, makeCtx())).rejects.toThrow(
      'Forbidden: not your sessions'
    )
  })

  it('propagates network errors', async () => {
    apiService.fetch.mockRejectedValue(new Error('Connection refused'))

    await expect(handler({ user_id: 'user-abc' }, makeCtx())).rejects.toThrow(
      'Connection refused'
    )
  })

  it('uses HTTP status fallback when error response has no detail', async () => {
    // Covers the `|| 'HTTP...'` branch at line 109 when detail is absent
    const errorResponse = {
      ok: false,
      status: 500,
      statusText: 'Server Error',
      json: vi.fn().mockResolvedValue({}), // no detail field
    }
    apiService.fetch.mockResolvedValue(errorResponse)

    await expect(handler({ user_id: 'user-abc' }, makeCtx())).rejects.toThrow(
      /HTTP 500/
    )
  })

  it('calls chatStore.addAttachment when formatted output exceeds 5000 chars', async () => {
    // Each session contributes ~145 chars when formatted; 100 sessions ≈ 14 500 chars,
    // which is well above the 5000-char threshold that triggers addAttachment.
    const SESSION_COUNT_TO_TRIGGER_ATTACHMENT = 100
    const manyActiveSessions = Array.from({ length: SESSION_COUNT_TO_TRIGGER_ATTACHMENT }, (_, i) => ({
      id: `session-${i.toString().padStart(5, '0')}-extra-padding`,
      user_id: 'user-abc',
      active: true,
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 86400 * 1000).toISOString(),
      updated_at: new Date().toISOString(),
    }))
    apiService.fetch.mockResolvedValue(makeOkResponse(manyActiveSessions))
    const chatStore = makeChatStore()

    await handler({ user_id: 'user-abc' }, makeCtx(chatStore))

    // When output > 5000 chars, addAttachment is used instead of insertContentIntoInput
    expect(chatStore.addAttachment).toHaveBeenCalledOnce()
    const [filename, , type] = chatStore.addAttachment.mock.calls[0]
    expect(filename).toContain('user_sessions_user-abc')
    expect(type).toBe('text')
  })
})

// ── close_session ─────────────────────────────────────────────────────────────

describe('close_session action', () => {
  let handler

  beforeEach(() => {
    vi.clearAllMocks()
    const registry = buildRegistry()
    registerSessionsActions(registry.registerAction)
    handler = registry.actions['close_session'].handler
  })

  it('throws when session_id is missing', async () => {
    await expect(handler({}, makeCtx())).rejects.toThrow('session_id is required')
  })

  it('throws when session_id is undefined', async () => {
    await expect(
      handler({ session_id: undefined }, makeCtx())
    ).rejects.toThrow('session_id is required')
  })

  it('calls apiService.fetch with correct path and POST method', async () => {
    apiService.fetch.mockResolvedValue(
      makeOkResponse({
        sessionId: 'sess-abc',
        message: 'Session closed successfully',
      })
    )

    await handler({ session_id: 'sess-abc' }, makeCtx())

    expect(apiService.fetch).toHaveBeenCalledWith(
      expect.stringContaining('sess-abc'),
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('encodes session_id in the URL', async () => {
    apiService.fetch.mockResolvedValue(
      makeOkResponse({
        sessionId: 'sess/special',
        message: 'Session closed successfully',
      })
    )

    await handler({ session_id: 'sess/special' }, makeCtx())

    const url = apiService.fetch.mock.calls[0][0]
    expect(url).toContain(encodeURIComponent('sess/special'))
  })

  it('returns success: true with data on success', async () => {
    const mockResponse = {
      sessionId: 'sess-abc',
      message: 'Session closed successfully',
    }
    apiService.fetch.mockResolvedValue(makeOkResponse(mockResponse))

    const result = await handler({ session_id: 'sess-abc' }, makeCtx())

    expect(result.success).toBe(true)
    expect(result.data).toEqual(mockResponse)
  })

  it('calls chatStore.insertContentIntoInput with formatted message', async () => {
    apiService.fetch.mockResolvedValue(
      makeOkResponse({
        sessionId: 'sess-abc',
        message: 'Session closed successfully',
      })
    )
    const chatStore = makeChatStore()

    await handler({ session_id: 'sess-abc' }, makeCtx(chatStore))

    expect(chatStore.insertContentIntoInput).toHaveBeenCalledOnce()
    const content = chatStore.insertContentIntoInput.mock.calls[0][0].content
    expect(content).toContain('Session Closed Successfully')
    expect(content).toContain('sess-abc')
    expect(content).toContain('Session closed successfully')
  })

  it('does not call chatStore when chatStore is null', async () => {
    apiService.fetch.mockResolvedValue(
      makeOkResponse({
        sessionId: 'sess-abc',
        message: 'Session closed successfully',
      })
    )

    const result = await handler({ session_id: 'sess-abc' }, makeCtx(null))
    expect(result.success).toBe(true)
  })

  it('throws on HTTP error response', async () => {
    apiService.fetch.mockResolvedValue(
      makeErrorResponse(404, 'Session not found')
    )

    await expect(handler({ session_id: 'ghost' }, makeCtx())).rejects.toThrow(
      'Session not found'
    )
  })

  it('propagates network errors', async () => {
    apiService.fetch.mockRejectedValue(new Error('Timeout'))

    await expect(handler({ session_id: 'sess-abc' }, makeCtx())).rejects.toThrow(
      'Timeout'
    )
  })

  it('uses HTTP status fallback when error response has no detail', async () => {
    // Covers the `|| 'HTTP...'` branch at line 208 when detail is absent
    const errorResponse = {
      ok: false,
      status: 403,
      statusText: 'Forbidden',
      json: vi.fn().mockResolvedValue({}), // no detail field
    }
    apiService.fetch.mockResolvedValue(errorResponse)

    await expect(handler({ session_id: 'sess-abc' }, makeCtx())).rejects.toThrow(
      /HTTP 403/
    )
  })
})
