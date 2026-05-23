/**
 * @file RequestsCell.ts
 * @description RequestsCell — BaseCell implementation for displaying incoming
 * allowance/access requests (read-only, no approve/reject actions).
 *
 * Pure cell logic with NO Vue / UI dependencies.
 *
 * Supported actions (passed in `input.action`)
 * ---------------------------------------------
 *   list_requests  — GET /api/inbox/requests?direction=received
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

export type RequestsAction = 'list_requests'

export interface RequestsInput {
  /** Discriminant action */
  action: RequestsAction
}

// ─────────────────────────────────────────────────────────────────────────────
// Cell
// ─────────────────────────────────────────────────────────────────────────────

export class RequestsCell extends BaseCell {
  /**
   * Execute a requests action.
   * Currently only supports list_requests.
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

      const response = await apiFetch('/api/inbox/requests?direction=received', { method: 'GET' })

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
        error: error.message ?? 'Unexpected error in RequestsCell.execute()',
      }
    }
  }

  /**
   * Describe this cell's capabilities and interface contract.
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'requests-cell',
      name: 'Requests',
      version: '1.0.0',
      description:
        'Requests cell for displaying incoming allowance/access requests. ' +
        'Read-only — no approve/reject actions.',
      inputs: {
        action: {
          type: 'string',
          description: 'Action to perform',
          required: true,
          enum: ['list_requests'],
        },
      },
      outputs: {
        requests: {
          type: 'array',
          description: 'List of incoming requests (list_requests action)',
        },
      },
      tags: ['requests', 'inbox', 'allowance', 'communication'],
      estimated_duration_seconds: 0,
      required_resources: [],
    }
  }

  /**
   * Validate input before execution.
   *
   * Rules:
   * - `action` is required and must be 'list_requests'
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []

    if (!input.action) {
      errors.push({ field: 'action', message: 'action is required' })
      return errors
    }

    if (input.action !== 'list_requests') {
      errors.push({
        field: 'action',
        message: 'action must be: list_requests',
      })
    }

    return errors
  }

  async setup(config: EnvironmentConfig): Promise<void> {
    // No-op for requests-cell
  }

  async teardown(): Promise<void> {
    // No-op for requests-cell
  }

  async health_check(): Promise<HealthCheckResult> {
    return {
      status: 'healthy',
      can_execute: true,
      message: 'RequestsCell is ready.',
    }
  }
}
