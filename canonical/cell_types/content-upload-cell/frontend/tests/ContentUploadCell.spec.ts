/**
 * @file ContentUploadCell.spec.ts
 * @description Unit tests for ContentUploadCell — BaseCell implementation
 *
 * Tests cover:
 * - describe() metadata
 * - validate() input validation
 * - execute() flow (success, error, network failure)
 * - health_check() status detection
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ContentUploadCell } from '../ContentUploadCell'

// ── Mocks ──────────────────────────────────────────────────────────────

const mockApiFetch = vi.fn()

vi.mock('@/services/apiService', () => ({
  apiFetch: (...args: any[]) => mockApiFetch(...args)
}))

vi.mock('@/utils/logger', () => ({
  createLogger: () => ({
    info: vi.fn(),
    error: vi.fn(),
    warn: vi.fn(),
    debug: vi.fn()
  })
}))

// ── Helpers ────────────────────────────────────────────────────────────

const validInput = {
  filename: 'test-image.png',
  binary: 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
  assignee_id: 'user-123',
  content_type_id: 'image-png',
  origin_cell_id: 'cell-456'
}

function createSuccessfulApiResponse(data: any = {}): Response {
  return new Response(JSON.stringify({
    success: true,
    output: {
      content_id: '550e8400-e29b-41d4-a716-446655440000',
      data_ref: '/runtime/user/user-123/contents/image-550e8400.png',
      filename: 'test-image.png',
      size_bytes: 28,
      ...data
    }
  }), { status: 200, headers: { 'Content-Type': 'application/json' } })
}

function createFailedApiResponse(status: number = 500, statusText: string = 'Internal Server Error'): Response {
  return new Response(JSON.stringify({
    success: false,
    error: 'Backend persist failed'
  }), { status, statusText, headers: { 'Content-Type': 'application/json' } })
}

// ── Tests ──────────────────────────────────────────────────────────────

describe('ContentUploadCell', () => {
  let cell: ContentUploadCell

  beforeEach(() => {
    vi.clearAllMocks()
    cell = new ContentUploadCell()
  })

  // ── describe() ──────────────────────────────────────────────────────

  describe('describe()', () => {
    it('returns correct metadata with id, name, version', async () => {
      const metadata = await cell.describe()
      expect(metadata.id).toBe('content-upload-cell')
      expect(metadata.name).toBe('Content Upload')
      expect(metadata.version).toBe('1.0.0')
    })

    it('includes required inputs in metadata', async () => {
      const metadata = await cell.describe()
      expect(metadata.inputs).toBeDefined()
      expect(metadata.inputs.filename).toBeDefined()
      expect(metadata.inputs.binary).toBeDefined()
      expect(metadata.inputs.assignee_id).toBeDefined()
    })

    it('includes outputs in metadata', async () => {
      const metadata = await cell.describe()
      expect(metadata.outputs).toBeDefined()
      expect(metadata.outputs.content_id).toBeDefined()
      expect(metadata.outputs.data_ref).toBeDefined()
      expect(metadata.outputs.filename).toBeDefined()
      expect(metadata.outputs.size_bytes).toBeDefined()
    })

    it('includes upload/utility tags', async () => {
      const metadata = await cell.describe()
      expect(metadata.tags).toContain('upload')
      expect(metadata.tags).toContain('content')
      expect(metadata.tags).toContain('persist')
    })
  })

  // ── validate() ───────────────────────────────────────────────────────

  describe('validate()', () => {
    it('rejects missing filename', () => {
      const errors = cell.validate({ binary: 'data', assignee_id: 'user-1' })
      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toBe('filename')
    })

    it('rejects missing binary', () => {
      const errors = cell.validate({ filename: 'test.png', assignee_id: 'user-1' })
      expect(errors.length).toBeGreaterThan(0)
      expect(errors.some(e => e.field === 'binary')).toBe(true)
    })

    it('rejects missing assignee_id', () => {
      const errors = cell.validate({ filename: 'test.png', binary: 'data' })
      expect(errors.length).toBeGreaterThan(0)
      expect(errors.some(e => e.field === 'assignee_id')).toBe(true)
    })

    it('accepts valid input with all required fields', () => {
      const errors = cell.validate(validInput)
      expect(errors.length).toBe(0)
    })

    it('reports all missing fields at once', () => {
      const errors = cell.validate({})
      expect(errors.length).toBe(3)
      const fields = errors.map(e => e.field)
      expect(fields).toContain('filename')
      expect(fields).toContain('binary')
      expect(fields).toContain('assignee_id')
    })
  })

  // ── execute() ────────────────────────────────────────────────────────

  describe('execute()', () => {
    it('returns error result for empty input (validation fails)', async () => {
      const result = await cell.execute({})
      expect(result.success).toBe(false)
      expect(result.error).toContain('filename is required')
    })

    it('delegates to apiFetch and returns successful result', async () => {
      mockApiFetch.mockResolvedValueOnce(createSuccessfulApiResponse())

      const result = await cell.execute(validInput)

      expect(mockApiFetch).toHaveBeenCalledTimes(1)
      expect(mockApiFetch).toHaveBeenCalledWith('/api/cells/execute-ephemeral', expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: expect.stringContaining('content-manager-cell')
      }))

      expect(result.success).toBe(true)
      expect(result.output).toBeDefined()
      expect(result.output.content_id).toBe('550e8400-e29b-41d4-a716-446655440000')
      expect(result.execution_steps).toContain('validate')
      expect(result.execution_steps).toContain('persist')
    })

    it('handles backend error response (500)', async () => {
      mockApiFetch.mockResolvedValueOnce(createFailedApiResponse(500))

      const result = await cell.execute(validInput)

      expect(result.success).toBe(false)
      expect(result.error).toBeDefined()
    })

    it('passes correct input_data to apiFetch', async () => {
      mockApiFetch.mockResolvedValueOnce(createSuccessfulApiResponse())

      await cell.execute(validInput)

      const callBody = JSON.parse(mockApiFetch.mock.calls[0][1].body)
      expect(callBody.cell_type).toBe('content-manager-cell')
      expect(callBody.input_data.action).toBe('persist')
      expect(callBody.input_data.filename).toBe('test-image.png')
      expect(callBody.input_data.assignee_id).toBe('user-123')
      expect(callBody.input_data.content_type_id).toBe('image-png')
    })

    it('includes optional tags and metadata in apiFetch payload', async () => {
      const inputWithExtras = {
        ...validInput,
        tags: ['test', 'upload'],
        metadata: { source: 'unit-test' }
      }
      mockApiFetch.mockResolvedValueOnce(createSuccessfulApiResponse())

      await cell.execute(inputWithExtras)

      const callBody = JSON.parse(mockApiFetch.mock.calls[0][1].body)
      expect(callBody.input_data.tags).toEqual(['test', 'upload'])
      expect(callBody.input_data.metadata).toEqual({ source: 'unit-test' })
    })

    it('handles network/fetch errors gracefully', async () => {
      mockApiFetch.mockRejectedValueOnce(new Error('Failed to fetch'))

      const result = await cell.execute(validInput)

      expect(result.success).toBe(false)
      expect(result.error).toContain('Failed to fetch')
      expect(result.execution_time).toBeGreaterThanOrEqual(0)
    })

    it('returns execution_time on success', async () => {
      mockApiFetch.mockResolvedValueOnce(createSuccessfulApiResponse())

      const result = await cell.execute(validInput)

      expect(result.success).toBe(true)
      expect(typeof result.execution_time).toBe('number')
      expect(result.execution_time).toBeGreaterThanOrEqual(0)
    })
  })

  // ── health_check() ───────────────────────────────────────────────────

  describe('health_check()', () => {
    it('returns healthy when backend responds ok', async () => {
      mockApiFetch.mockResolvedValueOnce(new Response(null, { status: 200 }))

      const health = await cell.health_check()

      expect(health.status).toBe('healthy')
      expect(health.can_execute).toBe(true)
    })

    it('returns degraded when backend responds with error status', async () => {
      mockApiFetch.mockResolvedValueOnce(new Response(null, { status: 503 }))

      const health = await cell.health_check()

      expect(health.status).toBe('degraded')
      expect(health.can_execute).toBe(true)
      expect(health.reason).toContain('503')
    })

    it('returns unavailable when network error occurs', async () => {
      mockApiFetch.mockRejectedValueOnce(new Error('Network error'))

      const health = await cell.health_check()

      expect(health.status).toBe('unavailable')
      expect(health.can_execute).toBe(false)
    })
  })
})
