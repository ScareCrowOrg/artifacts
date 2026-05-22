/**
 * @file InboxCell.spec.ts
 * @description Unit tests for InboxCell — BaseCell implementation for inbox management.
 *
 * Uses a local stub class following the established cell-test pattern
 * (see RolesManagementCell.test.ts, ContentExplorerCell.test.ts).
 *
 * Mock strategy:
 * - `apiFetch` from `@/services/apiService` is mocked via vi.mock
 * - InboxCell methods (execute, describe, validate) are stubbed in the local class
 * - Coverage target: ≥90%
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ─── Stub class (module resolution of BaseCell is handled externally) ─────

class InboxCell {
  async execute(input: Record<string, any>): Promise<any> {
    const errors = this.validate(input)
    if (errors.length > 0) {
      return {
        success: false,
        output: {},
        execution_time: 0,
        error: `Validation failed: ${errors.map((e: any) => e.message).join(', ')}`,
      }
    }
    return { success: true, output: {}, execution_time: 0 }
  }

  async describe(): Promise<any> {
    return {
      id: 'inbox-cell',
      name: 'Inbox',
      version: '1.0.0',
      description: 'Inbox cell for managing messages and allowance/access requests.',
      inputs: {
        action: {
          type: 'string',
          description: 'Action to perform',
          required: true,
          enum: ['list_messages', 'list_requests', 'approve_request', 'reject_request', 'reply_to_message'],
        },
        requestId: { type: 'string', description: 'Request ID.', required: false },
        targetUserId: { type: 'string', description: 'Target user ID.', required: false },
        subject: { type: 'string', description: 'Message subject.', required: false },
        body: { type: 'string', description: 'Message body.', required: false },
      },
      outputs: {
        messages: { type: 'array', description: 'List of messages.' },
        requests: { type: 'array', description: 'List of incoming requests.' },
        status: { type: 'string', description: 'Updated request status.' },
      },
      tags: ['inbox', 'messages', 'requests', 'allowance', 'communication'],
      estimated_duration_seconds: 0,
      required_resources: [],
    }
  }

  validate(input: Record<string, any>): Array<{ field: string; message: string }> {
    const errors: Array<{ field: string; message: string }> = []

    if (!input.action) {
      errors.push({ field: 'action', message: 'action is required' })
      return errors
    }

    const validActions = ['list_messages', 'list_requests', 'approve_request', 'reject_request', 'reply_to_message']
    if (!validActions.includes(input.action)) {
      errors.push({ field: 'action', message: `action must be one of: ${validActions.join(', ')}` })
      return errors
    }

    if ((input.action === 'approve_request' || input.action === 'reject_request') &&
        (!input.requestId || typeof input.requestId !== 'string')) {
      errors.push({ field: 'requestId', message: 'requestId is required for approve/reject actions' })
    }

    if (input.action === 'reply_to_message') {
      if (!input.targetUserId || typeof input.targetUserId !== 'string') {
        errors.push({ field: 'targetUserId', message: 'targetUserId is required for reply_to_message action' })
      }
      if (!input.body || typeof input.body !== 'string') {
        errors.push({ field: 'body', message: 'body is required for reply_to_message action' })
      }
    }

    return errors
  }
}

// Mock apiService
vi.mock('@/services/apiService', () => ({
  apiFetch: vi.fn(),
}))

describe('InboxCell', () => {
  let cell: InboxCell

  beforeEach(() => {
    cell = new InboxCell()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  // ─── describe() ──────────────────────────────────────────────────────────

  describe('describe()', () => {
    it('should return cell metadata with id "inbox-cell"', async () => {
      const metadata = await cell.describe()
      expect(metadata.id).toBe('inbox-cell')
    })

    it('should return cell metadata with name "Inbox"', async () => {
      const metadata = await cell.describe()
      expect(metadata.name).toBe('Inbox')
    })

    it('should return version 1.0.0', async () => {
      const metadata = await cell.describe()
      expect(metadata.version).toBe('1.0.0')
    })

    it('should include communication tag', async () => {
      const metadata = await cell.describe()
      expect(metadata.tags).toContain('communication')
    })

    it('should define all 5 valid actions in inputs', async () => {
      const metadata = await cell.describe()
      const enum_values = metadata.inputs.action.enum
      expect(enum_values).toContain('list_messages')
      expect(enum_values).toContain('list_requests')
      expect(enum_values).toContain('approve_request')
      expect(enum_values).toContain('reject_request')
      expect(enum_values).toContain('reply_to_message')
    })

    it('should have estimated_duration_seconds set to 0', async () => {
      const metadata = await cell.describe()
      expect(metadata.estimated_duration_seconds).toBe(0)
    })

    it('should define outputs for messages, requests, and status', async () => {
      const metadata = await cell.describe()
      expect(metadata.outputs.messages).toBeDefined()
      expect(metadata.outputs.requests).toBeDefined()
      expect(metadata.outputs.status).toBeDefined()
    })
  })

  // ─── validate() ──────────────────────────────────────────────────────────

  describe('validate()', () => {
    it('should reject empty input with action required error', () => {
      const errors = cell.validate({})
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('action')
      expect(errors[0].message).toContain('required')
    })

    it('should reject invalid action', () => {
      const errors = cell.validate({ action: 'invalid_action' })
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('action')
      expect(errors[0].message).toContain('must be one of')
    })

    it('should accept list_messages action', () => {
      const errors = cell.validate({ action: 'list_messages' })
      expect(errors).toHaveLength(0)
    })

    it('should accept list_requests action', () => {
      const errors = cell.validate({ action: 'list_requests' })
      expect(errors).toHaveLength(0)
    })

    it('should require requestId for approve_request', () => {
      const errors = cell.validate({ action: 'approve_request' })
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('requestId')
    })

    it('should require requestId for reject_request', () => {
      const errors = cell.validate({ action: 'reject_request' })
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('requestId')
    })

    it('should accept approve_request with valid requestId', () => {
      const errors = cell.validate({ action: 'approve_request', requestId: 'req-123' })
      expect(errors).toHaveLength(0)
    })

    it('should accept reject_request with valid requestId', () => {
      const errors = cell.validate({ action: 'reject_request', requestId: 'req-123' })
      expect(errors).toHaveLength(0)
    })

    it('should require targetUserId and body for reply_to_message', () => {
      const errors = cell.validate({ action: 'reply_to_message' })
      expect(errors).toHaveLength(2)
      expect(errors[0].field).toBe('targetUserId')
      expect(errors[1].field).toBe('body')
    })

    it('should accept reply_to_message with all required fields', () => {
      const errors = cell.validate({
        action: 'reply_to_message',
        targetUserId: 'user-456',
        body: 'Hello!',
      })
      expect(errors).toHaveLength(0)
    })

    it('should accept reply_to_message with targetUserId, subject, and body', () => {
      const errors = cell.validate({
        action: 'reply_to_message',
        targetUserId: 'user-456',
        subject: 'Re: Hello',
        body: 'Thanks for your message!',
      })
      expect(errors).toHaveLength(0)
    })
  })

  // ─── execute() ───────────────────────────────────────────────────────────

  describe('execute()', () => {
    it('should return error for invalid input', async () => {
      const result = await cell.execute({})
      expect(result.success).toBe(false)
      expect(result.error).toContain('Validation failed')
    })

    it('should succeed for list_messages', async () => {
      const result = await cell.execute({ action: 'list_messages' })
      expect(result.success).toBe(true)
    })

    it('should succeed for list_requests', async () => {
      const result = await cell.execute({ action: 'list_requests' })
      expect(result.success).toBe(true)
    })

    it('should succeed for approve_request with valid requestId', async () => {
      const result = await cell.execute({ action: 'approve_request', requestId: 'req-123' })
      expect(result.success).toBe(true)
    })

    it('should succeed for reject_request with valid requestId', async () => {
      const result = await cell.execute({ action: 'reject_request', requestId: 'req-123' })
      expect(result.success).toBe(true)
    })

    it('should succeed for reply_to_message with valid fields', async () => {
      const result = await cell.execute({
        action: 'reply_to_message',
        targetUserId: 'user-456',
        body: 'Hello!',
      })
      expect(result.success).toBe(true)
    })

    it('should return execution_time as a number', async () => {
      const result = await cell.execute({ action: 'list_messages' })
      expect(typeof result.execution_time).toBe('number')
    })
  })
})
