/**
 * @file PartyGameCell.spec.ts
 * @description Unit tests for PartyGameCell — BaseCell implementation for the
 * party-game cell.  Uses the same vi.mock strategy as PartyCell.spec.ts.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'

vi.mock('@/services/apiService.js', () => ({
  default: { fetch: vi.fn() },
}))

vi.mock('@/config/endpoints.js', () => ({
  ENDPOINTS: { executeEphemeralCell: '/api/v1/cells/execute-ephemeral' },
}))

import { PartyGameCell, GAME_ACTIONS } from '../PartyGameCell'
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
      expect(lastInputData()).toEqual({ action: 'join_game', roomId: 'room1', sessionId: 's-1' })
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
