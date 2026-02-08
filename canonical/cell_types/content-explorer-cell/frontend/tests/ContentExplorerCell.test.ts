/**
 * @file ContentExplorerCell.test.ts
 * @description Unit tests for ContentExplorerCell
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { ContentExplorerCell } from '../ContentExplorerCell'

describe('ContentExplorerCell', () => {
  let cell: ContentExplorerCell
  let fetchMock: any
  
  beforeEach(() => {
    cell = new ContentExplorerCell()
    // Mock fetch
    fetchMock = vi.fn()
    global.fetch = fetchMock
    vi.clearAllMocks()
  })
  
  afterEach(() => {
    vi.restoreAllMocks()
  })
  
  describe('describe()', () => {
    it('should return correct cell metadata', async () => {
      const metadata = await cell.describe()

      expect(metadata.id).toBe('content-explorer-cell')
      expect(metadata.name).toBe('Content Explorer')
      expect(metadata.version).toBe('1.0.0')
      expect(metadata.category).toBe('content-management')
      expect(metadata.description).toContain('Browse and manage assets')
    })

    it('should define required inputs', async () => {
      const metadata = await cell.describe()

      expect(metadata.inputs.type).toBe('object')
      expect(metadata.inputs.properties).toBeDefined()
      expect(metadata.inputs.properties.action).toBeDefined()
      expect(metadata.inputs.properties.action.type).toBe('string')
    })

    it('should define optional inputs', async () => {
      const metadata = await cell.describe()

      expect(metadata.inputs.properties.selected_type_id).toBeDefined()
      expect(metadata.inputs.properties.filters).toBeDefined()
      expect(metadata.inputs.properties.limit).toBeDefined()
      expect(metadata.inputs.properties.offset).toBeDefined()
    })

    it('should define expected outputs', async () => {
      const metadata = await cell.describe()

      expect(metadata.outputs.type).toBe('object')
      expect(metadata.outputs.properties.types).toBeDefined()
      expect(metadata.outputs.properties.assets).toBeDefined()
      expect(metadata.outputs.properties.selected_type_id).toBeDefined()
    })
  })
  
  describe('validate()', () => {
    it('should validate correct list input', () => {
      const input = { action: 'list' }
      const errors = cell.validate(input)

      expect(errors).toHaveLength(0)
    })

    it('should validate list input with optional parameters', () => {
      const input = {
        action: 'list',
        selected_type_id: 'image-png',
        limit: 50,
        offset: 10
      }
      const errors = cell.validate(input)

      expect(errors).toHaveLength(0)
    })

    it('should default to list action if not provided', () => {
      const input = {}
      const errors = cell.validate(input)

      expect(errors).toHaveLength(0)
    })

    it('should reject invalid action', () => {
      const input = { action: 'invalid' }
      const errors = cell.validate(input)

      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('action')
      expect(errors[0].message).toContain('Invalid action')
    })

    it('should reject limit below 1', () => {
      const input = { action: 'list', limit: 0 }
      const errors = cell.validate(input)

      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('limit')
      expect(errors[0].message).toContain('between 1 and 100')
    })

    it('should reject limit above 100', () => {
      const input = { action: 'list', limit: 200 }
      const errors = cell.validate(input)

      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('limit')
    })

    it('should reject negative offset', () => {
      const input = { action: 'list', offset: -1 }
      const errors = cell.validate(input)

      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('offset')
      expect(errors[0].message).toContain('>= 0')
    })
  })
  
  describe('execute()', () => {
    it('should call backend with correct parameters', async () => {
      const mockResponse = {
        success: true,
        output: {
          types: {
            types: [
              {
                id: 'image-png',
                name: 'PNG Image',
                description: 'PNG image files',
                mime_type: 'image/png',
                version: '1.0.0',
                max_size_bytes: 10485760,
                allowed_extensions: ['.png'],
                render_hints: {}
              }
            ],
            total: 1
          },
          assets: null,
          selected_type_id: null
        }
      }

      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      const result = await cell.execute({ action: 'list' })

      expect(fetchMock).toHaveBeenCalledWith('/api/cells/execute-ephemeral', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          cell_type: 'content-explorer-cell',
          input_data: { action: 'list' }
        })
      })

      expect(result.success).toBe(true)
      expect(result.output.types).toBeDefined()
      expect(result.output.types.total).toBe(1)
    })

    it('should handle validation errors', async () => {
      const result = await cell.execute({ action: 'invalid' })

      expect(result.success).toBe(false)
      expect(result.output.errors).toBeDefined()
      expect(result.output.errors.length).toBeGreaterThan(0)
    })

    it('should handle fetch errors', async () => {
      fetchMock.mockRejectedValueOnce(new Error('Network error'))

      const result = await cell.execute({ action: 'list' })

      expect(result.success).toBe(false)
      expect(result.output.error).toContain('Network error')
    })

    it('should handle HTTP errors', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Server error' })
      })

      const result = await cell.execute({ action: 'list' })

      expect(result.success).toBe(false)
      expect(result.output.error).toBeDefined()
    })

    it('should include execution time', async () => {
      const mockResponse = {
        success: true,
        output: {
          types: { types: [], total: 0 },
          assets: null,
          selected_type_id: null
        }
      }

      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      const result = await cell.execute({ action: 'list' })

      expect(result.execution_time).toBeGreaterThanOrEqual(0)
    })

    it('should pass selected_type_id to backend', async () => {
      const mockResponse = {
        success: true,
        output: {
          types: { types: [], total: 0 },
          assets: { items: [], total: 0, limit: 20, offset: 0 },
          selected_type_id: 'image-png'
        }
      }

      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      await cell.execute({
        action: 'list',
        selected_type_id: 'image-png'
      })

      expect(fetchMock).toHaveBeenCalledWith(
        '/api/cells/execute-ephemeral',
        expect.objectContaining({
          body: expect.stringContaining('image-png')
        })
      )
    })

    it('should pass filters to backend', async () => {
      const mockResponse = {
        success: true,
        output: {
          types: { types: [], total: 0 },
          assets: { items: [], total: 0, limit: 20, offset: 0 },
          selected_type_id: 'image-png'
        }
      }

      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      await cell.execute({
        action: 'list',
        selected_type_id: 'image-png',
        filters: {
          assignee_id: 'user-123',
          is_latest: true
        }
      })

      const callBody = JSON.parse(fetchMock.mock.calls[0][1].body)
      expect(callBody.input_data.filters).toBeDefined()
      expect(callBody.input_data.filters.assignee_id).toBe('user-123')
    })
  })

  describe('setup()', () => {
    it('should complete without errors', async () => {
      await expect(cell.setup({})).resolves.toBeUndefined()
    })
  })

  describe('teardown()', () => {
    it('should complete without errors', async () => {
      await expect(cell.teardown()).resolves.toBeUndefined()
    })
  })

  describe('health_check()', () => {
    it('should return healthy when backend is reachable', async () => {
      fetchMock.mockResolvedValueOnce({ ok: true })

      const result = await cell.health_check()

      expect(result.healthy).toBe(true)
      expect(result.message).toContain('operational')
      expect(result.timestamp).toBeDefined()
    })

    it('should return unhealthy when backend is not responding', async () => {
      fetchMock.mockResolvedValueOnce({ ok: false })

      const result = await cell.health_check()

      expect(result.healthy).toBe(false)
      expect(result.message).toContain('not responding')
    })

    it('should return unhealthy on fetch error', async () => {
      fetchMock.mockRejectedValueOnce(new Error('Connection failed'))

      const result = await cell.health_check()

      expect(result.healthy).toBe(false)
      expect(result.message).toContain('Connection failed')
    })
  })
})
