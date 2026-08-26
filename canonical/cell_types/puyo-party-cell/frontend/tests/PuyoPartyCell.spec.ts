/**
 * @file PuyoPartyCell.spec.ts
 * @description Unit tests for PuyoPartyCell — BaseCell implementation for the
 * puyo-party-cell.  Uses the same vi.mock strategy as PartyCell.spec.ts.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'

vi.mock('@/services/apiService.js', () => ({
  default: { fetch: vi.fn() },
}))

vi.mock('@/config/endpoints.js', () => ({
  ENDPOINTS: { executeEphemeralCell: '/api/v1/cells/execute-ephemeral' },
}))

import { PuyoPartyCell, PUYO_ACTIONS } from '../PuyoPartyCell'
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

describe('PuyoPartyCell', () => {
  let cell: PuyoPartyCell

  beforeEach(() => {
    cell = new PuyoPartyCell()
    mockFetch.mockReset()
  })

  describe('validate()', () => {
    it('accepts every known action with a roomId', () => {
      for (const action of PUYO_ACTIONS) {
        expect(cell.validate({ action, roomId: 'room1' })).toHaveLength(0)
      }
    })

    it('rejects a missing roomId', () => {
      const errors = cell.validate({ action: 'ready' })
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
    it('posts to execute-ephemeral with cell_type puyo-party-cell and returns the result', async () => {
      mockFetch.mockResolvedValueOnce(makeResponse({ result: { success: true, output: { status: 'running' } } }))
      const result = await cell.execute({ action: 'start_game', roomId: 'room1' })
      expect(result.success).toBe(true)
      expect(result.output).toEqual({ status: 'running' })
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/cells/execute-ephemeral',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ cell_type: 'puyo-party-cell', input_data: { action: 'start_game', roomId: 'room1' } }),
        }),
      )
    })

    it('returns a failure when the backend responds non-ok', async () => {
      mockFetch.mockResolvedValueOnce(makeResponse({ ok: false }))
      const result = await cell.execute({ action: 'ready', roomId: 'room1' })
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
      const result = await cell.execute({ action: 'ready', roomId: 'room1' })
      expect(result.success).toBe(false)
      expect(result.error).toBe('network down')
    })
  })

  describe('action wrappers', () => {
    it('markReady posts ready and forwards the participants fallback', async () => {
      mockFetch.mockResolvedValueOnce(makeResponse({ result: { success: true, output: { status: 'waiting' } } }))
      const res = await cell.markReady('room1', [{ participantId: 'u1', displayName: 'Alice' }])
      expect(res.output.status).toBe('waiting')
      expect(lastInputData()).toEqual({
        action: 'ready',
        roomId: 'room1',
        participants: [{ participantId: 'u1', displayName: 'Alice' }],
      })
    })

    it('startGame posts start_game', async () => {
      mockFetch.mockResolvedValueOnce(makeResponse())
      await cell.startGame('room1')
      expect(lastInputData()).toEqual({ action: 'start_game', roomId: 'room1' })
    })

    it('submitGarbage posts amount + targetId', async () => {
      mockFetch.mockResolvedValueOnce(makeResponse())
      await cell.submitGarbage('room1', 6, 'u2')
      expect(lastInputData()).toEqual({ action: 'submit_garbage', roomId: 'room1', amount: 6, targetId: 'u2' })
    })

    it('lockPiece posts the compact grid + score', async () => {
      mockFetch.mockResolvedValueOnce(makeResponse())
      const grid = Array.from({ length: 72 }, () => 0)
      await cell.lockPiece('room1', grid, 120)
      expect(lastInputData()).toEqual({ action: 'piece_locked', roomId: 'room1', grid, score: 120 })
    })

    it('gameOver posts game_over with a reason', async () => {
      mockFetch.mockResolvedValueOnce(makeResponse())
      await cell.gameOver('room1', 'top-out')
      expect(lastInputData()).toEqual({ action: 'game_over', roomId: 'room1', reason: 'top-out' })
    })

    it('requestSnapshot posts snapshot_request', async () => {
      mockFetch.mockResolvedValueOnce(makeResponse())
      await cell.requestSnapshot('room1')
      expect(lastInputData()).toEqual({ action: 'snapshot_request', roomId: 'room1' })
    })

    it('round-trips participantId on every action wrapper', async () => {
      mockFetch.mockResolvedValue(makeResponse())
      await cell.markReady('r', undefined, 'me-1')
      await cell.startGame('r', 'me-1')
      await cell.submitGarbage('r', 3, 'you-1', 'me-1')
      await cell.lockPiece('r', [], 0, 'me-1')
      await cell.gameOver('r', 'top-out', 'me-1')
      await cell.requestSnapshot('r', 'me-1')
      const inputs = mockFetch.mock.calls.map((c) => {
        if (!c[1]) throw new Error('no body')
        return (JSON.parse(String(c[1].body)) as { input_data: Record<string, any> }).input_data
      })
      expect(inputs).toHaveLength(6)
      for (const input of inputs) expect(input.participantId).toBe('me-1')
    })
  })

  describe('describe() / health_check()', () => {
    it('returns the puyo metadata', async () => {
      const meta = await cell.describe()
      expect(meta.id).toBe('puyo-party-cell')
      expect(meta.name).toBe('Puyo Party')
      expect(meta.tags).toContain('game')
      expect(meta.inputs.action.enum).toEqual(PUYO_ACTIONS)
    })

    it('reports healthy', async () => {
      const check = await cell.health_check()
      expect(check.status).toBe('healthy')
      expect(check.can_execute).toBe(true)
    })

    it('setup and teardown complete without throwing', async () => {
      await cell.setup({ headless_mode: true, has_gpu: false, gpu_vram_mb: 0, cpu_cores: 2, timeout_seconds: 30 })
      await cell.teardown()
    })
  })
})
