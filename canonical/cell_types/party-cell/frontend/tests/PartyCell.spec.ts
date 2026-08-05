/**
 * @file PartyCell.spec.ts
 * @description Unit tests for PartyCell — BaseCell implementation for Cloudflare
 * Calls (WebRTC).  Uses a REAL import (not a stub) so it validates the INC-1
 * fix: `tracks_update` is now a recognized PartyCellAction in validate() and
 * describe(), so the presence publication sent by usePartyCalls is no longer
 * rejected by the cell runtime.
 *
 * Mock strategy:
 * - `@/services/apiService` and `@/config/endpoints` are vi.mock'd (the vitest
 *   config aliases them to stubs; each test overrides fetch via the factory).
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
  },
}))

// ── Imports ───────────────────────────────────────────────────────────────

import { PartyCell } from '../PartyCell'
import apiService from '@/services/apiService.js'

const mockFetch = vi.mocked(apiService.fetch)

function makeSuccessResponse(result: Record<string, unknown> = {}) {
  return {
    ok: true,
    json: async () => ({ result }),
  } as unknown as Response
}

describe('PartyCell', () => {
  let cell: PartyCell

  beforeEach(() => {
    cell = new PartyCell()
    mockFetch.mockReset()
  })

  // ── validate() ────────────────────────────────────────────────────────────

  describe('validate()', () => {
    it('accepts tracks_update (INC-1 fix)', () => {
      const errors = cell.validate({ action: 'tracks_update', roomId: 'lobby' })
      expect(errors).toHaveLength(0)
    })

    it('accepts all five supported actions', () => {
      for (const action of [
        'join_room',
        'leave_room',
        'mute_toggle',
        'tracks_update',
        'snapshot_request',
      ]) {
        const errors = cell.validate({ action, roomId: 'lobby' })
        expect(errors, action).toHaveLength(0)
      }
    })

    it('rejects unknown actions', () => {
      const errors = cell.validate({ action: 'fly_to_the_moon', roomId: 'lobby' })
      expect(errors.some((e) => e.field === 'action')).toBe(true)
    })

    it('rejects missing action', () => {
      const errors = cell.validate({ roomId: 'lobby' })
      expect(errors.some((e) => e.field === 'action')).toBe(true)
    })

    it('rejects missing roomId', () => {
      const errors = cell.validate({ action: 'tracks_update' })
      expect(errors.some((e) => e.field === 'roomId')).toBe(true)
    })

    it('rejects whitespace-only roomId', () => {
      const errors = cell.validate({ action: 'tracks_update', roomId: '   ' })
      expect(errors.some((e) => e.field === 'roomId')).toBe(true)
    })
  })

  // ── describe() ────────────────────────────────────────────────────────────

  describe('describe()', () => {
    it('lists tracks_update in the action enum (INC-1 fix)', async () => {
      const meta = await cell.describe()
      expect(meta.inputs.action.enum).toEqual([
        'join_room',
        'leave_room',
        'mute_toggle',
        'tracks_update',
        'snapshot_request',
      ])
    })

    it('documents the count + participants outputs for tracks_update', async () => {
      const meta = await cell.describe()
      expect(meta.outputs.count).toBeDefined()
      expect(meta.outputs.participants).toBeDefined()
    })

    it('returns the correct id/name', async () => {
      const meta = await cell.describe()
      expect(meta.id).toBe('party-cell')
      expect(meta.name).toBe('Party')
    })
  })

  // ── execute() ─────────────────────────────────────────────────────────────

  describe('execute()', () => {
    it('executes tracks_update against the backend (INC-1)', async () => {
      mockFetch.mockResolvedValue(
        makeSuccessResponse({ success: true, output: { participants: [], count: 0 } }),
      )

      const result = await cell.execute({
        action: 'tracks_update',
        roomId: 'lobby',
        tracks: ['mic', 'camera', 'screen'],
      })

      expect(result.success).toBe(true)
      expect(mockFetch).toHaveBeenCalledTimes(1)
      const [url, opts] = mockFetch.mock.calls[0]
      expect(url).toBe('/api/v1/cells/execute-ephemeral')
      expect(opts).toBeDefined()
      const options = opts as RequestInit
      expect(options.method).toBe('POST')
      const payload = JSON.parse(String(options.body))
      expect(payload.cell_type).toBe('party-cell')
      expect(payload.input_data.action).toBe('tracks_update')
      expect(payload.input_data.tracks).toEqual(['mic', 'camera', 'screen'])
    })

    it('returns a validation error without calling the backend', async () => {
      const result = await cell.execute({ action: 'bogus', roomId: 'lobby' })
      expect(result.success).toBe(false)
      expect(result.error).toContain('Validation failed')
      expect(mockFetch).not.toHaveBeenCalled()
    })

    it('surfaces backend failures as unsuccessful results', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
        text: async () => 'boom',
      } as unknown as Response)

      const result = await cell.execute({ action: 'tracks_update', roomId: 'lobby' })
      expect(result.success).toBe(false)
      expect(result.error).toContain('Backend execution failed')
    })

    it('defaults success to true when the backend omits it', async () => {
      // A result without a `success` field exercises the `?? true` fallback.
      mockFetch.mockResolvedValue(
        makeSuccessResponse({ output: { status: 'ok' } }),
      )

      const result = await cell.execute({ action: 'tracks_update', roomId: 'lobby' })
      expect(result.success).toBe(true)
      expect(result.output).toEqual({ status: 'ok' })
    })

    it('falls back to a generic message for non-Error throws', async () => {
      mockFetch.mockRejectedValue('raw-string-failure')

      const result = await cell.execute({ action: 'tracks_update', roomId: 'lobby' })
      expect(result.success).toBe(false)
      expect(result.error).toBe('Unexpected error in PartyCell.execute()')
    })
  })
})
