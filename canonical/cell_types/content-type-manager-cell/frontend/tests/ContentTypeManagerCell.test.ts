/**
 * @file ContentTypeManagerCell.test.ts
 * @description Unit tests for ContentTypeManagerCell
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ContentTypeManagerCell, type ContentTypeMetadata } from '../ContentTypeManagerCell'

describe('ContentTypeManagerCell', () => {
  let cell: ContentTypeManagerCell
  
  beforeEach(() => {
    cell = new ContentTypeManagerCell()
    // Clear all mocks before each test
    vi.clearAllMocks()
  })
  
  describe('describe()', () => {
    it('should return correct cell metadata', () => {
      const metadata = cell.describe()
      
      expect(metadata.id).toBe('content-type-manager-cell')
      expect(metadata.name).toBe('Content Type Manager')
      expect(metadata.version).toBe('1.0.0')
      expect(metadata.description).toContain('content types')
      expect(metadata.inputs).toBeDefined()
      expect(metadata.outputs).toBeDefined()
    })
    
    it('should define required inputs', () => {
      const metadata = cell.describe()
      
      expect(metadata.inputs.action).toBeDefined()
      expect(metadata.inputs.action.type).toBe('string')
      expect(metadata.inputs.action.required).toBe(true)
    })
    
    it('should define optional inputs', () => {
      const metadata = cell.describe()
      
      expect(metadata.inputs.limit).toBeDefined()
      expect(metadata.inputs.limit.type).toBe('number')
      expect(metadata.inputs.limit.required).toBe(false)
    })
    
    it('should define expected outputs', () => {
      const metadata = cell.describe()
      
      expect(metadata.outputs.types).toBeDefined()
      expect(metadata.outputs.types.type).toBe('array')
      expect(metadata.outputs.total).toBeDefined()
      expect(metadata.outputs.total.type).toBe('number')
    })
  })
  
  describe('validate()', () => {
    it('should validate correct list input', async () => {
      const input = { action: 'list' }
      const errors = await cell.validate(input)
      
      expect(errors).toHaveLength(0)
    })
    
    it('should validate list input with limit', async () => {
      const input = { action: 'list', limit: 50 }
      const errors = await cell.validate(input)
      
      expect(errors).toHaveLength(0)
    })
    
    it('should reject missing action', async () => {
      const input = {}
      const errors = await cell.validate(input)
      
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('action')
      expect(errors[0].message).toContain('required')
    })
    
    it('should reject invalid action', async () => {
      const input = { action: 'invalid' }
      const errors = await cell.validate(input)
      
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('action')
      expect(errors[0].message).toContain('Invalid action')
    })
    
    it('should reject non-numeric limit', async () => {
      const input = { action: 'list', limit: 'invalid' }
      const errors = await cell.validate(input)
      
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('limit')
      expect(errors[0].message).toContain('must be a number')
    })
    
    it('should reject limit below 1', async () => {
      const input = { action: 'list', limit: 0 }
      const errors = await cell.validate(input)
      
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('limit')
      expect(errors[0].message).toContain('between 1 and 100')
    })
    
    it('should reject limit above 100', async () => {
      const input = { action: 'list', limit: 101 }
      const errors = await cell.validate(input)
      
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('limit')
      expect(errors[0].message).toContain('between 1 and 100')
    })
    
    it('should accept limit of 1', async () => {
      const input = { action: 'list', limit: 1 }
      const errors = await cell.validate(input)
      
      expect(errors).toHaveLength(0)
    })
    
    it('should accept limit of 100', async () => {
      const input = { action: 'list', limit: 100 }
      const errors = await cell.validate(input)
      
      expect(errors).toHaveLength(0)
    })
  })
  
  describe('execute()', () => {
    const mockContentTypes: ContentTypeMetadata[] = [
      {
        id: 'image-png',
        name: 'PNG Image Asset',
        description: 'PNG raster images',
        mime_type: 'image/png',
        version: '1.0.0',
        max_size_bytes: 52428800,
        allowed_extensions: ['.png']
      },
      {
        id: 'vector-svg',
        name: 'SVG Vector Graphic',
        description: 'SVG vector graphics',
        mime_type: 'image/svg+xml',
        version: '1.0.0',
        max_size_bytes: 5242880,
        allowed_extensions: ['.svg']
      }
    ]
    
    beforeEach(() => {
      // Mock global fetch
      global.fetch = vi.fn()
    })
    
    it('should return validation errors for invalid input', async () => {
      const result = await cell.execute({})
      
      expect(result.success).toBe(false)
      expect(result.output.error).toContain('Validation failed')
      expect(result.output.validation_errors).toBeDefined()
      expect(result.execution_time).toBeGreaterThan(0)
    })
    
    it('should execute list action successfully', async () => {
      // Mock successful API response
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          data: {
            types: mockContentTypes,
            total: 2
          }
        })
      })
      
      const result = await cell.execute({ action: 'list' })
      
      expect(result.success).toBe(true)
      expect(result.output.types).toHaveLength(2)
      expect(result.output.total).toBe(2)
      expect(result.execution_time).toBeGreaterThan(0)
      
      // Verify fetch was called correctly
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/cells/execute-ephemeral',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })
      )
    })
    
    it('should pass limit parameter to backend', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          data: { types: [], total: 0 }
        })
      })
      
      await cell.execute({ action: 'list', limit: 50 })
      
      const fetchCall = (global.fetch as any).mock.calls[0]
      const body = JSON.parse(fetchCall[1].body)
      
      expect(body.input_data.limit).toBe(50)
    })
    
    it('should use default limit when not provided', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          data: { types: [], total: 0 }
        })
      })
      
      await cell.execute({ action: 'list' })
      
      const fetchCall = (global.fetch as any).mock.calls[0]
      const body = JSON.parse(fetchCall[1].body)
      
      expect(body.input_data.limit).toBe(100)
    })
    
    it('should handle API errors gracefully', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: async () => 'Internal Server Error'
      })
      
      const result = await cell.execute({ action: 'list' })
      
      expect(result.success).toBe(false)
      expect(result.output.error).toContain('API request failed')
      expect(result.output.error).toContain('500')
    })
    
    it('should handle backend errors in response', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: false,
          error: 'Backend error message'
        })
      })
      
      const result = await cell.execute({ action: 'list' })
      
      expect(result.success).toBe(false)
      expect(result.output.error).toContain('Backend error message')
    })
    
    it('should handle network errors', async () => {
      (global.fetch as any).mockRejectedValueOnce(new Error('Network error'))
      
      const result = await cell.execute({ action: 'list' })
      
      expect(result.success).toBe(false)
      expect(result.output.error).toContain('Network error')
    })
    
    it('should include correct cell type in API request', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          data: { types: [], total: 0 }
        })
      })
      
      await cell.execute({ action: 'list' })
      
      const fetchCall = (global.fetch as any).mock.calls[0]
      const body = JSON.parse(fetchCall[1].body)
      
      expect(body.cell_type).toBe('content-type-manager-cell')
    })
  })
  
  describe('health_check()', () => {
    it('should return healthy status', async () => {
      expect(cell.health_check).toBeDefined()
      
      if (cell.health_check) {
        const health = await cell.health_check()
        
        expect(health).toBeDefined()
        expect(health.status).toBe('healthy')
        expect(health.can_execute).toBe(true)
      }
    })
  })
  
  describe('setup() and teardown()', () => {
    it('should have optional setup method', () => {
      expect(cell.setup).toBeDefined()
    })
    
    it('should have optional teardown method', () => {
      expect(cell.teardown).toBeDefined()
    })
    
    it('should execute setup without errors', async () => {
      if (cell.setup) {
        await expect(cell.setup()).resolves.not.toThrow()
      }
    })
    
    it('should execute teardown without errors', async () => {
      if (cell.teardown) {
        await expect(cell.teardown()).resolves.not.toThrow()
      }
    })
  })
})
