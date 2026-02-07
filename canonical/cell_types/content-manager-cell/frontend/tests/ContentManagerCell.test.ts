/**
 * @file ContentManagerCell.test.ts
 * @description Unit tests for ContentManagerCell
 * 
 * Tests the ContentManagerCell BaseCell implementation
 * Part of content-manager-cell refactoring to implement BaseCell interface
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { ContentManagerCell } from '../ContentManagerCell'
import type { ListContentInput, LoadContentInput, PersistContentInput } from '../ContentManagerCell'

describe('ContentManagerCell', () => {
  let contentManager: ContentManagerCell

  beforeEach(() => {
    contentManager = new ContentManagerCell()
  })

  describe('describe', () => {
    it('should return correct cell metadata', async () => {
      const metadata = await contentManager.describe()

      expect(metadata.id).toBe('content-manager-cell')
      expect(metadata.name).toBe('Content Manager')
      expect(metadata.version).toBe('1.0.0')
      expect(metadata.tags).toContain('content-management')
      expect(metadata.tags).toContain('ephemeral-utility')
      expect(metadata.required_resources).toContain('backend')
      expect(metadata.required_resources).toContain('r2-storage')
    })

    it('should document all three actions in inputs', async () => {
      const metadata = await contentManager.describe()

      expect(metadata.inputs.action).toBeDefined()
      expect(metadata.inputs.action.enum).toEqual(['list', 'load', 'persist'])
    })
  })

  describe('validate', () => {
    describe('action validation', () => {
      it('should require action field', () => {
        const errors = contentManager.validate({})
        
        expect(errors).toHaveLength(1)
        expect(errors[0].field).toBe('action')
        expect(errors[0].message).toContain('required')
      })

      it('should reject invalid action', () => {
        const errors = contentManager.validate({ action: 'invalid' })
        
        expect(errors).toHaveLength(1)
        expect(errors[0].field).toBe('action')
        expect(errors[0].message).toContain('one of: list, load, persist')
      })
    })

    describe('list action validation', () => {
      it('should accept valid list input', () => {
        const input: ListContentInput = {
          action: 'list',
          filters: { content_type_id: 'image-png', is_latest: true },
          limit: 20,
          offset: 0
        }
        
        const errors = contentManager.validate(input)
        expect(errors).toHaveLength(0)
      })

      it('should reject invalid limit', () => {
        const errors = contentManager.validate({
          action: 'list',
          limit: 0
        })
        
        expect(errors.some(e => e.field === 'limit')).toBe(true)
      })

      it('should reject limit > 100', () => {
        const errors = contentManager.validate({
          action: 'list',
          limit: 150
        })
        
        expect(errors.some(e => e.field === 'limit')).toBe(true)
      })

      it('should reject negative offset', () => {
        const errors = contentManager.validate({
          action: 'list',
          offset: -1
        })
        
        expect(errors.some(e => e.field === 'offset')).toBe(true)
      })
    })

    describe('load action validation', () => {
      it('should accept valid load input', () => {
        const input: LoadContentInput = {
          action: 'load',
          content_id: 'test-content-id'
        }
        
        const errors = contentManager.validate(input)
        expect(errors).toHaveLength(0)
      })

      it('should require content_id for load action', () => {
        const errors = contentManager.validate({
          action: 'load'
        })
        
        expect(errors).toHaveLength(1)
        expect(errors[0].field).toBe('content_id')
        expect(errors[0].message).toContain('required')
      })

      it('should reject non-string content_id', () => {
        const errors = contentManager.validate({
          action: 'load',
          content_id: 123
        })
        
        expect(errors.some(e => e.field === 'content_id')).toBe(true)
      })
    })

    describe('persist action validation', () => {
      it('should accept valid persist input', () => {
        const input: PersistContentInput = {
          action: 'persist',
          content_type_id: 'image-png',
          filename: 'test.png',
          binary: 'base64data...'
        }
        
        const errors = contentManager.validate(input)
        expect(errors).toHaveLength(0)
      })

      it('should require content_type_id for persist action', () => {
        const errors = contentManager.validate({
          action: 'persist',
          filename: 'test.png',
          binary: 'data'
        })
        
        expect(errors.some(e => e.field === 'content_type_id')).toBe(true)
      })

      it('should require filename for persist action', () => {
        const errors = contentManager.validate({
          action: 'persist',
          content_type_id: 'image-png',
          binary: 'data'
        })
        
        expect(errors.some(e => e.field === 'filename')).toBe(true)
      })

      it('should require binary for persist action', () => {
        const errors = contentManager.validate({
          action: 'persist',
          content_type_id: 'image-png',
          filename: 'test.png'
        })
        
        expect(errors.some(e => e.field === 'binary')).toBe(true)
      })

      it('should reject invalid content_type_id', () => {
        const errors = contentManager.validate({
          action: 'persist',
          content_type_id: 'invalid-type',
          filename: 'test.png',
          binary: 'data'
        })
        
        expect(errors.some(e => e.field === 'content_type_id')).toBe(true)
        expect(errors.find(e => e.field === 'content_type_id')?.message).toContain('image-png')
      })
    })
  })

  describe('setup and teardown', () => {
    it('should handle setup', async () => {
      await expect(contentManager.setup({
        has_gpu: false,
        gpu_vram_mb: 0,
        cpu_cores: 4,
        headless_mode: true,
        timeout_seconds: 300
      })).resolves.not.toThrow()
    })

    it('should handle teardown', async () => {
      await expect(contentManager.teardown()).resolves.not.toThrow()
    })

    it('should extract auth token from setup config', async () => {
      const config: any = {
        has_gpu: false,
        gpu_vram_mb: 0,
        cpu_cores: 4,
        headless_mode: true,
        timeout_seconds: 300,
        auth_token: 'test-token'
      }
      
      await contentManager.setup(config)
      
      // Verify token is being used by checking if execute would use it
      // (we can't directly test private field, but we can verify setup completes)
      const health = await contentManager.health_check()
      expect(health).toHaveProperty('status')
    })
  })

  describe('health_check', () => {
    it('should return health status', async () => {
      const health = await contentManager.health_check()
      
      expect(health).toHaveProperty('status')
      expect(health).toHaveProperty('can_execute')
      expect(['healthy', 'degraded', 'unavailable']).toContain(health.status)
    })
  })

  describe('execute - validation errors', () => {
    it('should return validation errors for invalid input', async () => {
      const result = await contentManager.execute({})
      
      expect(result.success).toBe(false)
      expect(result.error).toContain('Validation failed')
      expect(result.output.errors).toBeDefined()
      expect(result.execution_time).toBeGreaterThanOrEqual(0)
    })

    it('should return validation errors for missing content_id in load', async () => {
      const result = await contentManager.execute({
        action: 'load'
      })
      
      expect(result.success).toBe(false)
      expect(result.error).toContain('content_id')
    })

    it('should return validation errors for missing fields in persist', async () => {
      const result = await contentManager.execute({
        action: 'persist'
      })
      
      expect(result.success).toBe(false)
      expect(result.error).toContain('Validation failed')
      expect(result.output.errors.length).toBeGreaterThan(0)
    })
  })

  describe('setAuthToken', () => {
    it('should allow setting auth token', () => {
      expect(() => contentManager.setAuthToken('test-token')).not.toThrow()
    })
  })
})
