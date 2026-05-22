/**
 * @file InboxCell.ts
 * @description InboxCell — BaseCell implementation for managing planet inbox
 * (messages and allowance/access requests).
 *
 * Pure cell logic with NO Vue / UI dependencies.
 * View.vue is the presentation layer; this class handles execution, validation,
 * and metadata.
 *
 * Supported actions (passed in `input.action`)
 * ---------------------------------------------
 *   list_messages     — GET /api/inbox/messages
 *   list_requests     — GET /api/inbox/requests?direction=received
 *   approve_request   — PUT /api/inbox/requests/{id}/status {status: "approved"}
 *   reject_request    — PUT /api/inbox/requests/{id}/status {status: "rejected"}
 *   reply_to_message  — POST /api/inbox/messages
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

export type InboxAction =
  | 'list_messages'
  | 'list_requests'
  | 'approve_request'
  | 'reject_request'
  | 'reply_to_message'

export interface InboxInput {
  /** Discriminant action */
  action: InboxAction
  /** Request ID — required for approve_request / reject_request */
  requestId?: string
  /** Target user ID — required for reply_to_message */
  targetUserId?: string
  /** Subject — required for reply_to_message */
  subject?: string
  /** Body — required for reply_to_message */
  body?: string
}

// ─────────────────────────────────────────────────────────────────────────────
// Cell
// ─────────────────────────────────────────────────────────────────────────────

export class InboxCell extends BaseCell {
  /**
   * Execute an inbox action.
   *
   * Dispatches to the appropriate backend endpoint via apiFetch:
   * - list_messages       → GET  /api/inbox/messages
   * - list_requests       → GET  /api/inbox/requests?direction=received
   * - approve_request     → PUT  /api/inbox/requests/{id}/status
   * - reject_request      → PUT  /api/inbox/requests/{id}/status
   * - reply_to_message    → POST /api/inbox/messages
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

      const action = input.action as InboxAction
      let url = ''
      let options: RequestInit = {}

      switch (action) {
        case 'list_messages':
          url = '/api/inbox/messages'
          options = { method: 'GET' }
          break

        case 'list_requests':
          url = '/api/inbox/requests?direction=received'
          options = { method: 'GET' }
          break

        case 'approve_request':
          url = `/api/inbox/requests/${input.requestId}/status`
          options = {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'approved' }),
          }
          break

        case 'reject_request':
          url = `/api/inbox/requests/${input.requestId}/status`
          options = {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'rejected' }),
          }
          break

        case 'reply_to_message':
          url = '/api/inbox/messages'
          options = {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              target_user_id: input.targetUserId,
              subject: input.subject || '',
              body: input.body || '',
            }),
          }
          break
      }

      const response = await apiFetch(url, options)

      if (!response.ok) {
        const errText = await response.text().catch(() => '')
        throw new Error(`Backend request failed (${response.status}): ${errText}`)
      }

      const data = response.status === 204 ? null : await response.json()

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
        error: error.message ?? 'Unexpected error in InboxCell.execute()',
      }
    }
  }

  /**
   * Describe this cell's capabilities and interface contract.
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'inbox-cell',
      name: 'Inbox',
      version: '1.0.0',
      description:
        'Inbox cell for managing messages and allowance/access requests. ' +
        'Planet owners can view incoming requests, approve or reject them, ' +
        'and reply to messages.',
      inputs: {
        action: {
          type: 'string',
          description: 'Action to perform',
          required: true,
          enum: [
            'list_messages',
            'list_requests',
            'approve_request',
            'reject_request',
            'reply_to_message',
          ],
        },
        requestId: {
          type: 'string',
          description:
            'Request ID. Required for approve_request and reject_request actions.',
          required: false,
        },
        targetUserId: {
          type: 'string',
          description:
            'Target user ID. Required for reply_to_message action.',
          required: false,
        },
        subject: {
          type: 'string',
          description:
            'Message subject. Required for reply_to_message action.',
          required: false,
        },
        body: {
          type: 'string',
          description:
            'Message body. Required for reply_to_message action.',
          required: false,
        },
      },
      outputs: {
        messages: {
          type: 'array',
          description: 'List of messages (list_messages action)',
        },
        requests: {
          type: 'array',
          description: 'List of incoming requests (list_requests action)',
        },
        status: {
          type: 'string',
          description: 'Updated request status (approve_request / reject_request action)',
        },
      },
      tags: ['inbox', 'messages', 'requests', 'allowance', 'communication'],
      estimated_duration_seconds: 0,
      required_resources: [],
    }
  }

  /**
   * Validate input before execution.
   *
   * Rules:
   * - `action` is required and must be a valid InboxAction
   * - `requestId` is required when action is approve_request/reject_request
   * - `targetUserId`, `subject`, `body` are required for reply_to_message
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []

    if (!input.action) {
      errors.push({ field: 'action', message: 'action is required' })
      return errors
    }

    const validActions: InboxAction[] = [
      'list_messages',
      'list_requests',
      'approve_request',
      'reject_request',
      'reply_to_message',
    ]
    if (!validActions.includes(input.action as InboxAction)) {
      errors.push({
        field: 'action',
        message: `action must be one of: ${validActions.join(', ')}`,
      })
      return errors
    }

    if (
      (input.action === 'approve_request' || input.action === 'reject_request') &&
      (!input.requestId || typeof input.requestId !== 'string')
    ) {
      errors.push({
        field: 'requestId',
        message: 'requestId is required and must be a non-empty string for approve/reject actions',
      })
    }

    if (input.action === 'reply_to_message') {
      if (!input.targetUserId || typeof input.targetUserId !== 'string') {
        errors.push({
          field: 'targetUserId',
          message: 'targetUserId is required for reply_to_message action',
        })
      }
      if (!input.body || typeof input.body !== 'string') {
        errors.push({
          field: 'body',
          message: 'body is required for reply_to_message action',
        })
      }
    }

    return errors
  }

  async setup(config: EnvironmentConfig): Promise<void> {
    // No-op for inbox-cell
  }

  async teardown(): Promise<void> {
    // No-op for inbox-cell
  }

  async health_check(): Promise<HealthCheckResult> {
    return {
      status: 'healthy',
      can_execute: true,
      message: 'InboxCell is ready.',
    }
  }
}
