/**
 * @file PartyCell.ts
 * @description PartyCell — BaseCell implementation for Cloudflare Calls WebRTC.
 *
 * Pure cell logic with NO Vue / UI dependencies.
 * View.vue is the presentation layer; this class handles execution, validation,
 * and metadata.
 *
 * Execution model
 * ---------------
 * - `execute()` delegates to the backend via POST /api/v1/cells/execute-ephemeral.
 * - Room presence is synchronised via `useDistributedState` (Redis Pub/Sub).
 * - Media (voice/video/screen) flows directly through Cloudflare Calls SFU.
 *
 * Supported actions (passed in `input.action`)
 * ---------------------------------------------
 *   join_room     — Join a party call room.
 *   leave_room    — Leave the current room.
 *   mute_toggle   — Toggle microphone mute state.
 *   tracks_update — Publish the caller's current published media tracks.
 *   snapshot_request — Request the current participants list.
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

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export type PartyCellAction = 'join_room' | 'leave_room' | 'mute_toggle' | 'tracks_update' | 'snapshot_request'

export interface PartyCellInput {
  /** Discriminant action */
  action: PartyCellAction

  /**
   * Room identifier.
   * Scopes the call to a specific room.  Required for all actions.
   */
  roomId: string
}

// ─────────────────────────────────────────────────────────────────────────────
// Cell
// ─────────────────────────────────────────────────────────────────────────────

export class PartyCell extends BaseCell {
  /**
   * Execute a party action against the backend.
   *
   * Calls POST /api/v1/cells/execute-ephemeral and returns the backend result.
   * Room presence patches are published to Redis via the backend; all connected
   * clients receive the update via WebSocket (useDistributedState).
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

      const payload = {
        cell_type: 'party-cell',
        input_data: input,
      }

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
        error: error.message ?? 'Unexpected error in PartyCell.execute()',
      }
    }
  }

  /**
   * Describe this cell's capabilities and interface contract.
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'party-cell',
      name: 'Party',
      version: '1.0.0',
      description:
        'Real-time voice, video, and screen sharing cell powered by Cloudflare Calls SFU. ' +
        'Supports multiple concurrent users in the same room with < 200 ms media latency.',
      inputs: {
        action: {
          type: 'string',
          description: 'Action to perform',
          required: true,
          enum: ['join_room', 'leave_room', 'mute_toggle', 'tracks_update', 'snapshot_request'],
        },
        roomId: {
          type: 'string',
          description:
            'Room identifier.  Scopes the call to a specific party.  ' +
            'Required for all actions.',
          required: true,
        },
      },
      outputs: {
        participants: {
          type: 'array',
          description:
            'List of room participants (snapshot_request / tracks_update actions)',
        },
        count: {
          type: 'number',
          description: 'Number of participants in the room (tracks_update action)',
        },
        status: {
          type: 'string',
          description: 'Result status (join_room / leave_room / mute_toggle actions)',
        },
      },
      tags: [
        'realtime',
        'calls',
        'party',
        'webrtc',
        'cloudflare',
        'voice',
        'video',
        'screen-sharing',
      ],
      estimated_duration_seconds: 2,
      required_resources: ['webrtc', 'cloudflare-calls'],
    }
  }

  /**
   * Validate input before execution.
   *
   * Rules:
   * - `action` is required and must be a valid action
   * - `roomId` is required and must be a non-empty string
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []

    // action validation
    if (!input.action || typeof input.action !== 'string') {
      errors.push({
        field: 'action',
        message: 'action is required and must be a string',
      })
    } else if (!['join_room', 'leave_room', 'mute_toggle', 'tracks_update', 'snapshot_request'].includes(input.action)) {
      errors.push({
        field: 'action',
        message: `Invalid action '${input.action}'. Must be one of: join_room, leave_room, mute_toggle, tracks_update, snapshot_request`,
      })
    }

    // roomId validation
    if (!input.roomId || typeof input.roomId !== 'string' || input.roomId.trim() === '') {
      errors.push({
        field: 'roomId',
        message: 'roomId is required and must be a non-empty string',
      })
    }

    return errors
  }
}
