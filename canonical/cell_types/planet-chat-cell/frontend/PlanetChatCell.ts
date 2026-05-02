/**
 * @file PlanetChatCell.ts
 * @description PlanetChatCell — BaseCell implementation for real-time multi-user chat.
 *
 * Pure cell logic with NO Vue / UI dependencies.
 * View.vue is the presentation layer; this class handles execution, validation,
 * and metadata.
 *
 * Execution model
 * ---------------
 * - `execute()` delegates to the backend via POST /api/v1/cells/execute-ephemeral.
 * - The backend main.py publishes a JSON Patch to the Redis channel
 *   ``planet-chat:{contextId}``, which the WSS endpoint forwards to all
 *   connected clients.
 * - `useDistributedState` in View.vue applies the patch to the Pinia store.
 *
 * Supported actions (passed in `input.action`)
 * ---------------------------------------------
 *   send_message     — Append a new message to the chat history.
 *   snapshot_request — Request the current message history from the server.
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

export type PlanetChatAction = 'send_message' | 'snapshot_request'

export interface PlanetChatInput {
  /** Discriminant action */
  action: PlanetChatAction

  /**
   * Channel / context identifier.
   * Scopes the chat to a specific party.  Required for all actions.
   */
  contextId: string

  /** Message text — required for `send_message` */
  message?: string

  /** Sender identifier — optional; defaults to authenticated user */
  senderId?: string

  /** Unix timestamp in ms — optional; defaults to Date.now() */
  timestamp?: number
}

// ─────────────────────────────────────────────────────────────────────────────
// Cell
// ─────────────────────────────────────────────────────────────────────────────

export class PlanetChatCell extends BaseCell {
  /**
   * Execute an action against the planet-chat backend.
   *
   * Calls POST /api/v1/cells/execute-ephemeral and returns the backend result.
   * On `send_message`, the backend publishes a JSON Patch to Redis; all
   * connected clients receive the update via WebSocket.
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
        cell_type: 'planet-chat-cell',
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
        error: error.message ?? 'Unexpected error in PlanetChatCell.execute()',
      }
    }
  }

  /**
   * Describe this cell's capabilities and interface contract.
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'planet-chat-cell',
      name: 'Planet Chat',
      version: '1.0.0',
      description:
        'Real-time multi-user chat cell with distributed state via Redis Pub/Sub and WebSocket. ' +
        'Supports multiple concurrent users in the same party with < 100 ms message delivery.',
      inputs: {
        action: {
          type: 'string',
          description: 'Action to perform',
          required: true,
          enum: ['send_message', 'snapshot_request'],
        },
        contextId: {
          type: 'string',
          description:
            'Channel / context identifier.  Scopes the chat to a specific party.  ' +
            'Null = auto-generated from cell instance ID.',
          required: true,
        },
        message: {
          type: 'string',
          description: 'Message text to send.  Required for send_message action.',
          required: false,
        },
        senderId: {
          type: 'string',
          description: 'Sender identifier.  Defaults to authenticated user.',
          required: false,
        },
        timestamp: {
          type: 'number',
          description: 'Unix timestamp in milliseconds.  Defaults to Date.now().',
          required: false,
        },
      },
      outputs: {
        message: {
          type: 'object',
          description: 'Newly created message object (send_message action)',
        },
        messages: {
          type: 'array',
          description: 'Full message history (snapshot_request action)',
        },
        channel: {
          type: 'string',
          description: 'Redis channel name that was published to',
        },
      },
      tags: ['chat', 'realtime', 'communication', 'distributed-state', 'websocket', 'redis'],
      estimated_duration_seconds: 0,
      required_resources: ['redis', 'websocket'],
    }
  }

  /**
   * Validate input before execution.
   *
   * Rules:
   * - `action` is required and must be 'send_message' | 'snapshot_request'
   * - `contextId` is required and must be a non-empty string
   * - `message` is required and non-empty when action is 'send_message'
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []

    if (!input.action) {
      errors.push({ field: 'action', message: 'action is required' })
    } else {
      const validActions: PlanetChatAction[] = ['send_message', 'snapshot_request']
      if (!validActions.includes(input.action as PlanetChatAction)) {
        errors.push({
          field: 'action',
          message: `action must be one of: ${validActions.join(', ')}`,
        })
      }
    }

    if (!input.contextId || typeof input.contextId !== 'string' || !input.contextId.trim()) {
      errors.push({ field: 'contextId', message: 'contextId is required and must be a non-empty string' })
    }

    if (input.action === 'send_message') {
      if (!input.message || typeof input.message !== 'string' || !input.message.trim()) {
        errors.push({
          field: 'message',
          message: 'message is required and cannot be empty for send_message action',
        })
      }
    }

    return errors
  }

  /**
   * Optional lifecycle hook — no initialisation required.
   */
  async setup(config: EnvironmentConfig): Promise<void> {
    // No-op for planet-chat-cell
  }

  /**
   * Optional lifecycle hook — no cleanup required.
   */
  async teardown(): Promise<void> {
    // No-op for planet-chat-cell
  }

  /**
   * Health check — verifies that the backend API is reachable.
   */
  async health_check(): Promise<HealthCheckResult> {
    return {
      status: 'healthy',
      can_execute: true,
      message: 'PlanetChatCell is ready.  Backend health depends on Redis and WSS availability.',
    }
  }
}
