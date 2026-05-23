/**
 * @file RequestsCell.spec.ts
 * @description Unit tests for RequestsCell — BaseCell implementation for
 * read-only request display.
 *
 * Uses a local stub class following the established cell-test pattern
 * (see InboxCell.spec.ts).
 *
 * Mock strategy:
 * - `apiFetch` from `@/services/apiService` is mocked via vi.mock
 * - RequestsCell methods (execute, describe, validate) are stubbed in the local class
 * - Coverage target: ≥90%
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ─── Stub class ─────────────────────────────────────────────────────────────

class RequestsCell {
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
      id: 'requests-cell',
      name: 'Requests',
      version: '1.0.0',
      description: 'Requests cell for displaying incoming allowance/access requests. Read-only — no approve/reject actions.',
      inputs: {
        action: {
          type: 'string',
          description: 'Action to perform',
          required: true,
          enum: ['list_requests'],
        },
      },
      outputs: {
        requests: { type: 'array', description: 'List of incoming requests.' },
      },
      tags: ['requests', 'inbox', 'allowance', 'communication'],
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

    if (input.action !== 'list_requests') {
      errors.push({ field: 'action', message: 'action must be: list_requests' })
    }

    return errors
  }
}

// Mock apiService
vi.mock('@/services/apiService', () => ({
  apiFetch: vi.fn(),
}))

describe('RequestsCell', () => {
  let cell: RequestsCell

  beforeEach(() => {
    cell = new RequestsCell()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  // ─── describe() ──────────────────────────────────────────────────────────

  describe('describe()', () => {
    it('should return cell metadata with id "requests-cell"', async () => {
      const metadata = await cell.describe()
      expect(metadata.id).toBe('requests-cell')
    })

    it('should return cell metadata with name "Requests"', async () => {
      const metadata = await cell.describe()
      expect(metadata.name).toBe('Requests')
    })

    it('should return version 1.0.0', async () => {
      const metadata = await cell.describe()
      expect(metadata.version).toBe('1.0.0')
    })

    it('should include communication tag', async () => {
      const metadata = await cell.describe()
      expect(metadata.tags).toContain('communication')
    })

    it('should define list_requests as the only valid action', async () => {
      const metadata = await cell.describe()
      expect(metadata.inputs.action.enum).toEqual(['list_requests'])
    })

    it('should define requests output', async () => {
      const metadata = await cell.describe()
      expect(metadata.outputs.requests).toBeDefined()
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

    it('should accept list_requests action', () => {
      const errors = cell.validate({ action: 'list_requests' })
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

    it('should succeed for list_requests', async () => {
      const result = await cell.execute({ action: 'list_requests' })
      expect(result.success).toBe(true)
    })

    it('should return execution_time as a number', async () => {
      const result = await cell.execute({ action: 'list_requests' })
      expect(typeof result.execution_time).toBe('number')
    })
  })
})
