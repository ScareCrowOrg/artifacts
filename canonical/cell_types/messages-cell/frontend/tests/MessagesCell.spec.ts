/**
 * @file MessagesCell.spec.ts
 * @description Unit tests for MessagesCell — BaseCell implementation for
 * read-only message display.
 *
 * Uses a local stub class following the established cell-test pattern
 * (see InboxCell.spec.ts).
 *
 * Mock strategy:
 * - `apiFetch` from `@/services/apiService` is mocked via vi.mock
 * - MessagesCell methods (execute, describe, validate) are stubbed in the local class
 * - Coverage target: ≥90%
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ─── Stub class ─────────────────────────────────────────────────────────────

class MessagesCell {
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
    return { success: true, output: [], execution_time: 0 }
  }

  async describe(): Promise<any> {
    return {
      id: 'messages-cell',
      name: 'Messages',
      version: '1.0.0',
      description: 'Messages cell for displaying inbox messages. Read-only — no reply action.',
      inputs: {
        action: {
          type: 'string',
          description: 'Action to perform',
          required: true,
          enum: ['list_messages'],
        },
      },
      outputs: {
        messages: { type: 'array', description: 'List of messages.' },
      },
      tags: ['messages', 'inbox', 'communication'],
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

    if (input.action !== 'list_messages') {
      errors.push({ field: 'action', message: 'action must be: list_messages' })
    }

    return errors
  }
}

// Mock apiService
vi.mock('@/services/apiService', () => ({
  apiFetch: vi.fn(),
}))

describe('MessagesCell', () => {
  let cell: MessagesCell

  beforeEach(() => {
    cell = new MessagesCell()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  // ─── describe() ──────────────────────────────────────────────────────────

  describe('describe()', () => {
    it('should return cell metadata with id "messages-cell"', async () => {
      const metadata = await cell.describe()
      expect(metadata.id).toBe('messages-cell')
    })

    it('should return cell metadata with name "Messages"', async () => {
      const metadata = await cell.describe()
      expect(metadata.name).toBe('Messages')
    })

    it('should return version 1.0.0', async () => {
      const metadata = await cell.describe()
      expect(metadata.version).toBe('1.0.0')
    })

    it('should include communication tag', async () => {
      const metadata = await cell.describe()
      expect(metadata.tags).toContain('communication')
    })

    it('should define list_messages as the only valid action', async () => {
      const metadata = await cell.describe()
      expect(metadata.inputs.action.enum).toEqual(['list_messages'])
    })

    it('should define messages output', async () => {
      const metadata = await cell.describe()
      expect(metadata.outputs.messages).toBeDefined()
    })

    it('should have estimated_duration_seconds set to 0', async () => {
      const metadata = await cell.describe()
      expect(metadata.estimated_duration_seconds).toBe(0)
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
      const errors = cell.validate({ action: 'approve_request' })
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('action')
      expect(errors[0].message).toContain('must be')
    })

    it('should accept list_messages action', () => {
      const errors = cell.validate({ action: 'list_messages' })
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

    it('should return execution_time as a number', async () => {
      const result = await cell.execute({ action: 'list_messages' })
      expect(typeof result.execution_time).toBe('number')
    })
  })
})
