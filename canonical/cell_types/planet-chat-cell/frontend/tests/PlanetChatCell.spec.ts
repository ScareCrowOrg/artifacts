/**
 * @file PlanetChatCell.spec.ts
 * @description Unit tests for PlanetChatCell TypeScript class.
 *
 * Coverage:
 * - execute() calls apiFetch with correct parameters
 * - validate() rejects invalid input
 * - describe() returns correct metadata
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'

// ── Module mocks (must be hoisted before imports) ─────────────────────────

vi.mock('@/services/apiService.js', () => ({
  default: {
    fetch: vi.fn(),
  },
}))

vi.mock('@/config/endpoints.js', () => ({
  ENDPOINTS: {
    executeEphemeralCell: '/api/v1/cells/execute-ephemeral',
    systemStatus: '/api/v1/status',
  },
}))

// ── Imports ───────────────────────────────────────────────────────────────

import { PlanetChatCell } from '../PlanetChatCell'
import apiService from '@/services/apiService.js'

const mockFetch = vi.mocked(apiService.fetch)

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function makeSuccessResponse(output: Record<string, unknown> = {}) {
  return {
    ok: true,
    json: async () => ({ success: true, output }),
  } as unknown as Response
}

function makeErrorResponse(status = 500, text = 'Internal Server Error') {
  return {
    ok: false,
    status,
    statusText: text,
    text: async () => text,
  } as unknown as Response
}

// ─────────────────────────────────────────────────────────────────────────────
// describe()
// ─────────────────────────────────────────────────────────────────────────────

describe('PlanetChatCell.describe()', () => {
  let cell: PlanetChatCell

  beforeEach(() => {
    cell = new PlanetChatCell()
  })

  it('returns id = "planet-chat-cell"', async () => {
    const meta = await cell.describe()
    expect(meta.id).toBe('planet-chat-cell')
  })

  it('returns name = "Planet Chat"', async () => {
    const meta = await cell.describe()
    expect(meta.name).toBe('Planet Chat')
  })

  it('lists both supported actions in inputs.action.enum', async () => {
    const meta = await cell.describe()
    expect(meta.inputs.action.enum).toContain('send_message')
    expect(meta.inputs.action.enum).toContain('snapshot_request')
  })

  it('includes required resources', async () => {
    const meta = await cell.describe()
    expect(meta.required_resources).toContain('redis')
    expect(meta.required_resources).toContain('websocket')
  })

  it('includes relevant tags', async () => {
    const meta = await cell.describe()
    expect(meta.tags).toContain('chat')
    expect(meta.tags).toContain('realtime')
    expect(meta.tags).toContain('distributed-state')
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// validate()
// ─────────────────────────────────────────────────────────────────────────────

describe('PlanetChatCell.validate()', () => {
  let cell: PlanetChatCell

  beforeEach(() => {
    cell = new PlanetChatCell()
  })

  it('returns no errors for valid send_message input', () => {
    const errors = cell.validate({
      action: 'send_message',
      contextId: 'room-abc',
      message: 'Hello',
    })
    expect(errors).toHaveLength(0)
  })

  it('returns no errors for valid snapshot_request input', () => {
    const errors = cell.validate({
      action: 'snapshot_request',
      contextId: 'room-abc',
    })
    expect(errors).toHaveLength(0)
  })

  it('rejects input without contextId', () => {
    const errors = cell.validate({
      action: 'send_message',
      contextId: '',
      message: 'Hello',
    })
    const fields = errors.map((e) => e.field)
    expect(fields).toContain('contextId')
  })

  it('rejects input without action', () => {
    const errors = cell.validate({ contextId: 'room-abc' })
    const fields = errors.map((e) => e.field)
    expect(fields).toContain('action')
  })

  it('rejects unknown action', () => {
    const errors = cell.validate({ action: 'delete_everything', contextId: 'room-abc' })
    const fields = errors.map((e) => e.field)
    expect(fields).toContain('action')
  })

  it('rejects send_message without message', () => {
    const errors = cell.validate({
      action: 'send_message',
      contextId: 'room-abc',
      message: '',
    })
    const fields = errors.map((e) => e.field)
    expect(fields).toContain('message')
  })

  it('rejects send_message with whitespace-only message', () => {
    const errors = cell.validate({
      action: 'send_message',
      contextId: 'room-abc',
      message: '   ',
    })
    const fields = errors.map((e) => e.field)
    expect(fields).toContain('message')
  })

  it('does not require message for snapshot_request', () => {
    const errors = cell.validate({
      action: 'snapshot_request',
      contextId: 'room-abc',
    })
    expect(errors.every((e) => e.field !== 'message')).toBe(true)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// execute()
// ─────────────────────────────────────────────────────────────────────────────

describe('PlanetChatCell.execute()', () => {
  let cell: PlanetChatCell

  beforeEach(() => {
    cell = new PlanetChatCell()
    vi.clearAllMocks()
  })

  it('calls apiService.fetch with correct endpoint and cell_type', async () => {
    mockFetch.mockResolvedValueOnce(makeSuccessResponse({ message: 'ok' }))

    await cell.execute({
      action: 'send_message',
      contextId: 'room-abc',
      message: 'Hello',
    })

    expect(mockFetch).toHaveBeenCalledTimes(1)
    const [endpoint, options] = mockFetch.mock.calls[0]
    expect(endpoint).toBe('/api/v1/cells/execute-ephemeral')

    const body = JSON.parse((options as RequestInit).body as string)
    expect(body.cell_type).toBe('planet-chat-cell')
  })

  it('passes input_data with action and contextId to backend', async () => {
    mockFetch.mockResolvedValueOnce(makeSuccessResponse())

    await cell.execute({
      action: 'send_message',
      contextId: 'room-xyz',
      message: 'Test',
    })

    const body = JSON.parse((mockFetch.mock.calls[0][1] as RequestInit).body as string)
    expect(body.input_data.action).toBe('send_message')
    expect(body.input_data.contextId).toBe('room-xyz')
    expect(body.input_data.message).toBe('Test')
  })

  it('returns success=false when validation fails (no contextId)', async () => {
    const result = await cell.execute({ action: 'send_message', contextId: '', message: 'Hi' })
    expect(result.success).toBe(false)
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('returns success=true when backend responds 200', async () => {
    mockFetch.mockResolvedValueOnce(makeSuccessResponse({ message: 'hi' }))
    const result = await cell.execute({
      action: 'send_message',
      contextId: 'room-abc',
      message: 'Hi',
    })
    expect(result.success).toBe(true)
  })

  it('returns success=false when backend responds with non-ok status', async () => {
    mockFetch.mockResolvedValueOnce(makeErrorResponse(500))
    const result = await cell.execute({
      action: 'send_message',
      contextId: 'room-abc',
      message: 'Hi',
    })
    expect(result.success).toBe(false)
    expect(result.error).toBeDefined()
  })

  it('handles network errors gracefully', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'))
    const result = await cell.execute({
      action: 'send_message',
      contextId: 'room-abc',
      message: 'Hi',
    })
    expect(result.success).toBe(false)
    expect(result.error).toContain('Network error')
  })
})
