/**
 * @file PartyGameCell.ts
 * @description PartyGameCell — BaseCell implementation for the party-game cell.
 *
 * Pure cell logic with NO Vue / UI dependencies.  View.vue is the presentation
 * layer; this class handles execution, validation and metadata.
 *
 * Execution model
 * ---------------
 * - `execute()` delegates to the backend via POST /api/v1/cells/execute-ephemeral.
 * - The backend `main.py` is server-authoritative: it publishes snapshot/patch
 *   envelopes to the game channels (`game:room:{roomId}:state|strokes|guesses`),
 *   which the WSS endpoint forwards to all connected clients.
 * - `useDistributedState` (wired by `useGameRealtime` in gameStore.ts) applies
 *   those envelopes to the Pinia store branches.
 *
 * Supported actions (passed in `input.action`)
 * ---------------------------------------------
 *   join_game · leave_game — party presence (party-cell contract)
 *   start_game · start_round · next_round · end_game — game lifecycle
 *   get_secret — return the secret word ONLY to the drawer
 *   submit_guess · hint — judging + hints (AI)
 *   append_stroke · clear_canvas — drawing
 *   snapshot_request — re-publish current snapshots (hydration)
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

const logger = createLogger('cell:party-game')

// ── Action identifiers ──────────────────────────────────────────────────────

export const GAME_ACTIONS = [
  'join_game',
  'leave_game',
  'start_game',
  'start_round',
  'next_round',
  'end_game',
  'get_secret',
  'submit_guess',
  'hint',
  'append_stroke',
  'clear_canvas',
  'snapshot_request',
] as const

export type GameAction = (typeof GAME_ACTIONS)[number]

// ── Cell ────────────────────────────────────────────────────────────────────

export class PartyGameCell extends BaseCell {
  /**
   * Execute a game action against the backend.
   *
   * Calls POST /api/v1/cells/execute-ephemeral and returns the backend result.
   * The backend publishes the resulting snapshots/patches to Redis; all
   * connected clients (including the caller) receive them via WebSocket.
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

      const payload = { cell_type: 'party-game', input_data: input }
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
        error: error.message ?? 'Unexpected error in PartyGameCell.execute()',
      }
    }
  }

  // ── Convenience action wrappers ───────────────────────────────────────────

  async joinGame(roomId: string, sessionId: string): Promise<CellResult> {
    return this.execute({ action: 'join_game', roomId, sessionId })
  }

  async leaveGame(roomId: string, sessionId: string): Promise<CellResult> {
    return this.execute({ action: 'leave_game', roomId, sessionId })
  }

  async startGame(roomId: string, totalRounds?: number): Promise<CellResult> {
    return this.execute({ action: 'start_game', roomId, totalRounds })
  }

  async nextRound(roomId: string): Promise<CellResult> {
    return this.execute({ action: 'next_round', roomId })
  }

  async endGame(roomId: string): Promise<CellResult> {
    return this.execute({ action: 'end_game', roomId })
  }

  async getSecret(roomId: string): Promise<CellResult> {
    return this.execute({ action: 'get_secret', roomId })
  }

  async submitGuess(roomId: string, guess: string): Promise<CellResult> {
    return this.execute({ action: 'submit_guess', roomId, guess })
  }

  async requestHint(roomId: string): Promise<CellResult> {
    return this.execute({ action: 'hint', roomId })
  }

  async appendStroke(roomId: string, stroke: Record<string, unknown>): Promise<CellResult> {
    return this.execute({ action: 'append_stroke', roomId, stroke })
  }

  async clearCanvas(roomId: string): Promise<CellResult> {
    return this.execute({ action: 'clear_canvas', roomId })
  }

  async requestSnapshot(roomId: string): Promise<CellResult> {
    return this.execute({ action: 'snapshot_request', roomId })
  }

  // ── BaseCell contract ─────────────────────────────────────────────────────

  /**
   * Describe this cell's capabilities and interface contract.
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'party-game',
      name: 'Party Game',
      version: '1.0.0',
      description:
        'Real-time drawing / guessing party game (Gartic-like) where AI picks the word, ' +
        'judges guesses and gives hints.  Composes the existing realtime building blocks.',
      inputs: {
        action: {
          type: 'string',
          description: 'Action to perform',
          required: true,
          enum: GAME_ACTIONS,
        },
        roomId: {
          type: 'string',
          description: 'Room identifier.  Scopes the game to a specific party.',
          required: true,
        },
        guess: {
          type: 'string',
          description: 'Guess text (submit_guess action).',
          required: false,
        },
        stroke: {
          type: 'object',
          description: 'Stroke to append (append_stroke action).',
          required: false,
        },
      },
      outputs: {
        state: {
          type: 'object',
          description: 'Game state snapshot (snapshot_request / start_game).',
        },
        secretWord: {
          type: 'string',
          description: 'Secret word — returned ONLY to the drawer (get_secret).',
        },
        correct: {
          type: 'boolean',
          description: 'Whether a guess was correct (submit_guess).',
        },
      },
      tags: ['game', 'realtime', 'drawing', 'guessing', 'ai', 'party', 'distributed-state'],
      estimated_duration_seconds: 1,
      required_resources: ['redis', 'websocket', 'ollama'],
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
    } else if (!GAME_ACTIONS.includes(input.action as GameAction)) {
      errors.push({
        field: 'action',
        message: `Invalid action '${input.action}'. Must be one of: ${GAME_ACTIONS.join(', ')}`,
      })
    }

    if (!input.roomId || typeof input.roomId !== 'string' || input.roomId.trim() === '') {
      errors.push({ field: 'roomId', message: 'roomId is required and must be a non-empty string' })
    }

    return errors
  }

  // ── Optional lifecycle hooks ──────────────────────────────────────────────

  async setup(config: EnvironmentConfig): Promise<void> {
    logger.info('[PartyGameCell] setup', { headless: config.headless_mode })
  }

  async teardown(): Promise<void> {
    // No-op for party-game-cell
  }

  async health_check(): Promise<HealthCheckResult> {
    return {
      status: 'healthy',
      can_execute: true,
      reason: 'PartyGameCell is ready.  Backend health depends on Redis, WSS and Ollama.',
    }
  }
}
