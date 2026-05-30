/**
 * @file MessagesCell.ts
 * @description MessagesCell — BaseCell implementation for displaying inbox messages
 * (read-only, no reply action).
 *
 * Pure cell logic with NO Vue / UI dependencies.
 *
 * Supported actions (passed in `input.action`)
 * ---------------------------------------------
 *   list_messages  — GET /api/inbox/messages
 */

import { BaseCell } from '@/types/BaseCell'
import type {
  CellResult,
  CellMetadata,
  ValidationError,
  EnvironmentConfig,
  HealthCheckResult,
} from '@/types/BaseCell'
import { apiFetch } from '@/services/apiService'

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export type MessagesAction = 'list_messages'

export interface MessagesInput {
  /** Discriminant action */
  action: MessagesAction
}

// ─────────────────────────────────────────────────────────────────────────────
// Cell
// ─────────────────────────────────────────────────────────────────────────────

export class MessagesCell extends BaseCell {
  /**
   * Execute a messages action.
   * Currently only supports list_messages.
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

      const response = await apiFetch('/api/inbox/messages?direction=all', { method: 'GET' })

      if (!response.ok) {
        const errText = await response.text().catch(() => '')
        throw new Error(`Backend request failed (${response.status}): ${errText}`)
      }

      const data = await response.json()

      return {
        success: true,
        output: data || {},
        execution_time: performance.now() - startTime,
      }
    } catch (error: any) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: error.message ?? 'Unexpected error in MessagesCell.execute()',
      }
    }
  }

  /**
   * Describe this cell's capabilities and interface contract.
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'messages-cell',
      name: 'Messages',
      version: '1.0.0',
      description:
        'Messages cell for displaying inbox messages. Read-only — no reply action.',
      inputs: {
        action: {
          type: 'string',
          description: 'Action to perform',
          required: true,
          enum: ['list_messages'],
        },
      },
      outputs: {
        messages: {
          type: 'array',
          description: 'List of messages (list_messages action)',
        },
      },
      tags: ['messages', 'inbox', 'communication'],
      estimated_duration_seconds: 0,
      required_resources: [],
    }
  }

  /**
   * Validate input before execution.
   *
   * Rules:
   * - `action` is required and must be 'list_messages'
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []

    if (!input.action) {
      errors.push({ field: 'action', message: 'action is required' })
      return errors
    }

    if (input.action !== 'list_messages') {
      errors.push({
        field: 'action',
        message: 'action must be: list_messages',
      })
    }

    return errors
  }

  async setup(config: EnvironmentConfig): Promise<void> {
    // No-op for messages-cell
  }

  async teardown(): Promise<void> {
    // No-op for messages-cell
  }

  async health_check(): Promise<HealthCheckResult> {
    return {
      status: 'healthy',
      can_execute: true,
      message: 'MessagesCell is ready.',
    }
  }
}
