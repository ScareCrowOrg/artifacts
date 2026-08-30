/**
 * @file PuyoPartyCell.ts
 * @description PuyoPartyCell — BaseCell implementation for the puyo-party-cell.
 *
 * Pure cell logic with NO Vue / UI dependencies.  View.vue is the presentation
 * layer; this class handles execution, validation and metadata.
 *
 * Execution model
 * ---------------
 * - `execute()` delegates to the backend via POST /api/v1/cells/execute-ephemeral.
 * - The backend `main.py` is server-authoritative: it validates every action,
 *   persists the game state and publishes snapshot envelopes to the Redis
 *   channel `puyo:game:{roomId}`, which the WSS router (forward-only) forwards
 *   to all connected clients.  `usePuyoRealtime` (puyoStore) applies those
 *   envelopes to the `game` branch.
 * - The deterministic engine (`engine/PuyoBoard`) simulates the shared piece
 *   sequence locally from the backend-issued `seed` (lockstep).
 *
 * Supported actions (passed in `input.action`)
 * ---------------------------------------------
 *   ready            — mark the caller ready (auto-starts when all are ready)
 *   start_game       — validate ≥2 ready players, generate `seed`, start running
 *   submit_garbage   — deliver a garbage attack to a target (server-arbitrated)
 *   piece_locked     — report the caller's locked grid (remote board render)
 *   game_over        — report a top-out; the backend arbitrates the winner
 *   snapshot_request — re-publish the current snapshot (hydration)
 */

import { BaseCell } from '@/types/BaseCell'
import type {
  CellResult,
  CellMetadata,
  ValidationError,
  EnvironmentConfig,
  HealthCheckResult,
} from '@/types/BaseCell'
import apiService from '@/services/apiService.js'
import { ENDPOINTS } from '@/config/endpoints.js'
import { createLogger } from '@/utils/logger'

const logger = createLogger('cell:puyo-party')

// ── Action identifiers ──────────────────────────────────────────────────────

export const PUYO_ACTIONS = [
  'ready',
  'start_game',
  'submit_garbage',
  'piece_locked',
  'game_over',
  'snapshot_request',
  'close_room',
] as const

export type PuyoAction = (typeof PUYO_ACTIONS)[number]

// ── Cell ────────────────────────────────────────────────────────────────────

export class PuyoPartyCell extends BaseCell {
  /**
   * Execute a game action against the backend.
   *
   * Calls POST /api/v1/cells/execute-ephemeral and returns the backend result.
   * The backend publishes the resulting snapshot to Redis; all connected
   * clients (including the caller) receive it via WebSocket.
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()
    try {
      const errors = this.validate(input)
      if (errors.length > 0) {
        return {
          success: false,
          output: {},
          execution_time: performance.now() - startTime,
          error: `Validation failed: ${errors.map((e) => e.message).join(', ')}`,
        }
      }

      const payload = { cell_type: 'puyo-party-cell', input_data: input }
      const response = (await apiService.fetch(ENDPOINTS.executeEphemeralCell, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })) as Response

      if (!response.ok) {
        const errText = await response.text()
        throw new Error(`Backend execution failed (${response.status}): ${errText}`)
      }

      const responseData = (await response.json()) as any
      const result = responseData.result ?? responseData

      return {
        success: result.success ?? true,
        output: result.output ?? result,
        execution_time: performance.now() - startTime,
        error: result.error,
      }
    } catch (error: any) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: error.message ?? 'Unexpected error in PuyoPartyCell.execute()',
      }
    }
  }

  // ── Convenience action wrappers ───────────────────────────────────────────
  // Every wrapper carries an optional ``participantId`` so the backend can
  // resolve a stable identity for unauthenticated guests (``_caller_id`` falls
  // back to ``user_id`` when present, else the client-supplied id — A07).

  /** Mark the caller ready.  Auto-starts the match when everyone is ready.
   *  ``participants`` is an optional roster fallback (see backend ``_roster``). */
  async markReady(
    roomId: string,
    participants?: Array<{ participantId: string; displayName?: string }>,
    participantId?: string,
  ): Promise<CellResult> {
    return this.execute({
      action: 'ready',
      roomId,
      ...(participants ? { participants } : {}),
      ...(participantId ? { participantId } : {}),
    })
  }

  /** Start (or restart) a match — the backend issues the lockstep seed. */
  async startGame(roomId: string, participantId?: string): Promise<CellResult> {
    return this.execute({ action: 'start_game', roomId, ...(participantId ? { participantId } : {}) })
  }

  /** Deliver a garbage attack to *targetId* (server-arbitrated). */
  async submitGarbage(roomId: string, amount: number, targetId: string, participantId?: string): Promise<CellResult> {
    return this.execute({
      action: 'submit_garbage',
      roomId,
      amount,
      targetId,
      ...(participantId ? { participantId } : {}),
    })
  }

  /** Report the caller's locked grid (renders the opponent's board). */
  async lockPiece(roomId: string, grid: number[], score: number, participantId?: string): Promise<CellResult> {
    return this.execute({ action: 'piece_locked', roomId, grid, score, ...(participantId ? { participantId } : {}) })
  }

  /** Report a top-out; the backend arbitrates the winner. */
  async gameOver(roomId: string, reason = 'top-out', participantId?: string): Promise<CellResult> {
    return this.execute({ action: 'game_over', roomId, reason, ...(participantId ? { participantId } : {}) })
  }

  /** Re-publish the current snapshot (hydration via HTTP body).
   *  ``isHost`` (Abrir Sala) fixes the room creator on the backend in the same
   *  request — the hostId is returned in ``output.hostId`` (no separate race). */
  async requestSnapshot(roomId: string, participantId?: string, isHost = false): Promise<CellResult> {
    return this.execute({
      action: 'snapshot_request',
      roomId,
      ...(participantId ? { participantId } : {}),
      ...(isHost ? { isHost: true } : {}),
    })
  }

  /** Close a room — host-gated on the backend (returns success:false for non-host). */
  async closeRoom(roomId: string): Promise<CellResult> {
    return this.execute({ action: 'close_room', roomId })
  }

  // ── BaseCell contract ─────────────────────────────────────────────────────

  /**
   * Describe this cell's capabilities and interface contract.
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'puyo-party-cell',
      name: 'Puyo Party',
      version: '1.0.0',
      description:
        'Real-time competitive Puyo Puyo 1v1 cell (Canvas 2D). Two players share a room, ' +
        'receive a deterministic seed from the backend, simulate the same piece sequence ' +
        'locally (lockstep), attack each other with garbage and end when a board tops out.',
      inputs: {
        action: {
          type: 'string',
          description: 'Action to perform',
          required: true,
          enum: PUYO_ACTIONS,
        },
        roomId: {
          type: 'string',
          description: 'Room identifier. Scopes the match to a specific party.',
          required: true,
        },
        amount: {
          type: 'number',
          description: 'Garbage units to deliver (submit_garbage).',
          required: false,
        },
        targetId: {
          type: 'string',
          description: 'Participant receiving the garbage (submit_garbage).',
          required: false,
        },
        grid: {
          type: 'array',
          description: 'Compact 72-cell grid of the caller (piece_locked).',
          required: false,
        },
      },
      outputs: {
        state: {
          type: 'object',
          description: 'Game state snapshot (snapshot_request / start_game).',
        },
        participantId: {
          type: 'string',
          description: 'Authoritative caller id (snapshot_request).',
        },
        status: {
          type: 'string',
          description: 'Result status (ready / start_game / game_over).',
        },
      },
      tags: ['game', 'puyo', 'realtime', 'canvas', 'distributed-state', 'lockstep'],
      estimated_duration_seconds: 1,
      required_resources: ['redis', 'websocket', 'webrtc'],
    }
  }

  /**
   * Validate input before execution.
   *
   * Rules:
   * - `action` is required and must be a known game action
   * - `roomId` is required and must be a non-empty string
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []

    if (!input.action || typeof input.action !== 'string') {
      errors.push({ field: 'action', message: 'action is required and must be a string' })
    } else if (!PUYO_ACTIONS.includes(input.action as PuyoAction)) {
      errors.push({
        field: 'action',
        message: `Invalid action '${input.action}'. Must be one of: ${PUYO_ACTIONS.join(', ')}`,
      })
    }

    if (!input.roomId || typeof input.roomId !== 'string' || input.roomId.trim() === '') {
      errors.push({ field: 'roomId', message: 'roomId is required and must be a non-empty string' })
    }

    return errors
  }

  // ── Optional lifecycle hooks ──────────────────────────────────────────────

  async setup(config: EnvironmentConfig): Promise<void> {
    logger.info('[PuyoPartyCell] setup', { headless: config.headless_mode })
  }

  async teardown(): Promise<void> {
    // No-op for puyo-party-cell
  }

  async health_check(): Promise<HealthCheckResult> {
    return {
      status: 'healthy',
      can_execute: true,
      reason: 'PuyoPartyCell is ready. Backend health depends on Redis and WSS.',
    }
  }
}
