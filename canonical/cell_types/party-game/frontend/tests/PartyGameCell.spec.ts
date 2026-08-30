/**
 * @file PartyGameCell.spec.ts
 * @description Unit tests for PartyGameCell — BaseCell implementation for the
 * party-game cell.  Uses the same vi.mock strategy as PartyCell.spec.ts.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'

vi.mock('@/services/apiService.js', () => {
  class SessionExpiredError extends Error {
    constructor(message = 'Session expired or invalid token') {
      super(message)
      this.name = 'SessionExpiredError'
    }
  }
  return { default: { fetch: vi.fn() }, SessionExpiredError }
})

vi.mock('@/config/endpoints.js', () => ({
  ENDPOINTS: {
    executeEphemeralCell: '/api/v1/cells/execute-ephemeral',
    listActiveRooms: '/api/calls/rooms',
    roomSessions: (roomId: string) => `/api/calls/rooms/${roomId}/sessions`,
    roomSession: (roomId: string, sessionId: string) => `/api/calls/rooms/${roomId}/sessions/${sessionId}`,
  },
}))

import { PartyGameCell, GAME_ACTIONS, resolveCanClose } from '../PartyGameCell'
import apiService from '@/services/apiService.js'

const mockFetch = vi.mocked(apiService.fetch)

function makeResponse(overrides: Partial<{ ok: boolean; result: Record<string, unknown> }> = {}) {
  const { ok = true, result = { success: true, output: {} } } = overrides
  return {
    ok,
    json: async () => ({ result }),
    text: async () => 'boom',
  } as unknown as Response
}

function makeJsonResponse(body: unknown, ok = true) {
  return {
    ok,
    json: async () => body,
    text: async () => 'boom',
  } as unknown as Response
}

/** Parse the ``input_data`` of the last executed fetch call. */
function lastInputData(): Record<string, any> {
  const call = mockFetch.mock.calls[0]
  if (!call || !call[1]) throw new Error('fetch was not called with arguments')
  return (JSON.parse(String(call[1].body)) as { input_data: Record<string, any> }).input_data
}

describe('PartyGameCell', () => {
  let cell: PartyGameCell

  beforeEach(() => {
    cell = new PartyGameCell()
    mockFetch.mockReset()
  })

  describe('validate()', () => {
    it('accepts every known action with a roomId', () => {
      for (const action of GAME_ACTIONS) {
        expect(cell.validate({ action, roomId: 'room1' })).toHaveLength(0)
      }
    })

    it('rejects a missing roomId', () => {
      const errors = cell.validate({ action: 'join_game' })
      expect(errors.some((e) => e.field === 'roomId')).toBe(true)
    })

    it('rejects an unknown action', () => {
      const errors = cell.validate({ action: 'nope', roomId: 'room1' })
      expect(errors.some((e) => e.field === 'action')).toBe(true)
    })

    it('rejects a missing action', () => {
      expect(cell.validate({ roomId: 'room1' }).some((e) => e.field === 'action')).toBe(true)
    })
  })

  describe('execute()', () => {
    it('posts to execute-ephemeral with cell_type party-game and returns the result', async () => {
      mockFetch.mockResolvedValueOnce(makeResponse({ result: { success: true, output: { count: 2 } } }))
      const result = await cell.execute({ action: 'join_game', roomId: 'room1' })
      expect(result.success).toBe(true)
      expect(result.output).toEqual({ count: 2 })
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/cells/execute-ephemeral',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ cell_type: 'party-game', input_data: { action: 'join_game', roomId: 'room1' } }),
        }),
      )
    })

    it('returns a failure when the backend responds non-ok', async () => {
      mockFetch.mockResolvedValueOnce(makeResponse({ ok: false }))
      const result = await cell.execute({ action: 'start_game', roomId: 'room1' })
      expect(result.success).toBe(false)
      expect(result.error).toContain('Backend execution failed')
    })

    it('returns a validation failure without calling the backend', async () => {
      const result = await cell.execute({ action: 'nope', roomId: 'room1' })
      expect(result.success).toBe(false)
      expect(result.error).toContain('Validation failed')
      expect(mockFetch).not.toHaveBeenCalled()
    })

    it('surfaces network errors as a failed result', async () => {
      mockFetch.mockRejectedValueOnce(new Error('network down'))
      const result = await cell.execute({ action: 'join_game', roomId: 'room1' })
      expect(result.success).toBe(false)
      expect(result.error).toBe('network down')
    })
  })

  describe('action wrappers', () => {
    it('joinGame posts join_game', async () => {
      mockFetch.mockResolvedValueOnce(makeResponse({ result: { success: true, output: { participantId: 'u1' } } }))
      const res = await cell.joinGame('room1', 's-1')
      expect(res.output.participantId).toBe('u1')
      expect(lastInputData()).toEqual({ action: 'join_game', roomId: 'room1', sessionId: 's-1', isHost: false })
    })

    it('startGame posts start_game with optional totalRounds', async () => {
      mockFetch.mockResolvedValueOnce(makeResponse())
      await cell.startGame('room1', 4)
      expect(lastInputData()).toEqual({ action: 'start_game', roomId: 'room1', totalRounds: 4 })
    })

    it('submitGuess posts submit_guess', async () => {
      mockFetch.mockResolvedValueOnce(makeResponse({ result: { success: true, output: { correct: false } } }))
      const res = await cell.submitGuess('room1', 'penguin')
      expect(res.output.correct).toBe(false)
      expect(lastInputData()).toEqual({ action: 'submit_guess', roomId: 'room1', guess: 'penguin' })
    })

    it('appendStroke posts append_stroke with the stroke object', async () => {
      mockFetch.mockResolvedValueOnce(makeResponse())
      const stroke = { tool: 'pen', color: '#000', width: 2, points: [{ x: 0, y: 0 }] }
      await cell.appendStroke('room1', stroke)
      expect(lastInputData().stroke).toStrictEqual(stroke)
    })

    it('getSecret / requestSnapshot / clearCanvas / nextRound post the right actions', async () => {
      mockFetch.mockResolvedValue(makeResponse())
      await cell.getSecret('r')
      await cell.requestSnapshot('r')
      await cell.clearCanvas('r')
      await cell.nextRound('r')
      await cell.endGame('r')
      await cell.requestHint('r')
      await cell.leaveGame('r', 's')
      const bodies = mockFetch.mock.calls.map((c) => {
        if (!c[1]) throw new Error('fetch called without args')
        return (JSON.parse(String(c[1].body)) as { input_data: { action: string } }).input_data.action
      })
      expect(bodies).toEqual(['get_secret', 'snapshot_request', 'clear_canvas', 'next_round', 'end_game', 'hint', 'leave_game'])
    })
  })

  describe('room registry + host', () => {
    it('joinGame posts isHost', async () => {
      mockFetch.mockResolvedValueOnce(makeResponse())
      await cell.joinGame('room1', 's-1', true)
      expect(lastInputData()).toEqual({ action: 'join_game', roomId: 'room1', sessionId: 's-1', isHost: true })
    })

    it('closeRoom posts close_room', async () => {
      mockFetch.mockResolvedValueOnce(makeResponse({ result: { success: true, output: { closed: true } } }))
      const res = await cell.closeRoom('room1')
      expect(res.output).toEqual({ closed: true })
      expect(lastInputData()).toEqual({ action: 'close_room', roomId: 'room1' })
    })

    it('listAvailableRooms returns rooms', async () => {
      mockFetch.mockResolvedValueOnce(makeJsonResponse({ rooms: [{ roomId: 'a', sessionCount: 2, sessions: [] }] }))
      const rooms = await cell.listAvailableRooms()
      expect(rooms).toEqual([{ roomId: 'a', sessionCount: 2, sessions: [] }])
      expect(mockFetch).toHaveBeenCalledWith('/api/calls/rooms')
    })

    it('listAvailableRooms returns [] on HTTP failure', async () => {
      mockFetch.mockResolvedValueOnce(makeJsonResponse({}, false))
      expect(await cell.listAvailableRooms()).toEqual([])
    })

    it('listAvailableRooms returns [] on network failure', async () => {
      mockFetch.mockRejectedValueOnce(new Error('down'))
      expect(await cell.listAvailableRooms()).toEqual([])
    })

    it('listAvailableRooms throws on 401 (session expired) — never degrades to empty list', async () => {
      const resp = { ok: false, status: 401, json: async () => ({}), text: async () => 'x' } as unknown as Response
      mockFetch.mockResolvedValueOnce(resp)
      await expect(cell.listAvailableRooms()).rejects.toThrow('Session expired')
    })

    it('registerSession posts to room sessions', async () => {
      mockFetch.mockResolvedValueOnce(makeJsonResponse({ status: 'registered' }))
      const ok = await cell.registerSession('room1', 's-1')
      expect(ok).toBe(true)
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/calls/rooms/room1/sessions',
        expect.objectContaining({ method: 'POST', body: JSON.stringify({ sessionId: 's-1', tracks: [] }) }),
      )
    })

    it('registerSession returns false on failure', async () => {
      mockFetch.mockResolvedValueOnce(makeJsonResponse({}, false))
      expect(await cell.registerSession('room1', 's-1')).toBe(false)
    })

    it('heartbeatSession PUTs the heartbeat endpoint', async () => {
      mockFetch.mockResolvedValueOnce(makeJsonResponse({ status: 'ok' }))
      const ok = await cell.heartbeatSession('room1', 's-1')
      expect(ok).toBe(true)
      expect(mockFetch).toHaveBeenCalledWith('/api/calls/rooms/room1/sessions/s-1/heartbeat', expect.objectContaining({ method: 'PUT' }))
    })

    it('removeSession DELETEs the session', async () => {
      mockFetch.mockResolvedValueOnce(makeJsonResponse({ status: 'removed' }))
      const ok = await cell.removeSession('room1', 's-1')
      expect(ok).toBe(true)
      expect(mockFetch).toHaveBeenCalledWith('/api/calls/rooms/room1/sessions/s-1', expect.objectContaining({ method: 'DELETE' }))
    })

    it('registry helpers return false on network failure', async () => {
      mockFetch.mockRejectedValueOnce(new Error('down'))
      expect(await cell.registerSession('room1', 's-1')).toBe(false)
      mockFetch.mockRejectedValueOnce(new Error('down'))
      expect(await cell.heartbeatSession('room1', 's-1')).toBe(false)
      mockFetch.mockRejectedValueOnce(new Error('down'))
      expect(await cell.removeSession('room1', 's-1')).toBe(false)
    })
  })

  describe('resolveCanClose', () => {
    it('is true only when in a room AND my participant id is the host', () => {
      expect(resolveCanClose('u1', 'u1', true)).toBe(true)
      expect(resolveCanClose('u1', 'u2', true)).toBe(false)
      expect(resolveCanClose(null, 'u1', true)).toBe(false)
      expect(resolveCanClose('u1', null, true)).toBe(false)
      expect(resolveCanClose('u1', undefined, true)).toBe(false)
      // A lingering host id after "Leave" (no active room) never re-enables it.
      expect(resolveCanClose('u1', 'u1', false)).toBe(false)
    })
  })

  describe('describe() / health_check()', () => {
    it('returns the party-game metadata', async () => {
      const meta = await cell.describe()
      expect(meta.id).toBe('party-game')
      expect(meta.name).toBe('Party Game')
      expect(meta.tags).toContain('game')
    })

    it('reports healthy with a readiness message', async () => {
      const check = await cell.health_check()
      expect(check.status).toBe('healthy')
      expect(check.can_execute).toBe(true)
      expect(check.reason).toContain('Ollama')
    })

    it('setup and teardown complete without throwing', async () => {
      await cell.setup({ headless_mode: true, has_gpu: false, gpu_vram_mb: 0, cpu_cores: 2, timeout_seconds: 30 })
      await cell.teardown()
    })
  })
})
