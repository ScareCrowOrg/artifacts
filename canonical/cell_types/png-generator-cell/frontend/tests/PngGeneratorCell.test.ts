/**
 * @file PngGeneratorCell.test.ts
 * @description Unit tests for PngGeneratorCell
 * 
 * Tests the PngGeneratorCell BaseCell implementation
 * Part of BaseCell v1.0 Framework Implementation
 * Task: [PNG-FE-001] Create PngGeneratorCell TypeScript Implementation
 */

import { describe, it, expect, beforeAll, vi } from 'vitest'
import { PngGeneratorCell } from '../PngGeneratorCell'
import type { PngGeneratorInput } from '../PngGeneratorCell'

// Mock apiService - use cockpit-vue global path since it's shared
vi.mock('@/services/apiService.js', () => ({
  default: {
    fetch: vi.fn()
  }
}))

// Mock endpoints - use cockpit-vue global path since it's shared
vi.mock('@/config/endpoints.js', () => ({
  ENDPOINTS: {
    executeEphemeralCell: 'http://localhost:3000/api/cells/execute-ephemeral',
    systemStatus: 'http://localhost:3000/api/status'
  }
}))

// Mock logger - use cockpit-vue global path since it's shared
vi.mock('@/utils/logger', () => ({
  createLogger: () => ({
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn()
  })
}))

import apiService from '@/services/apiService.js'

describe('PngGeneratorCell', () => {
  let pngGen: PngGeneratorCell

  beforeAll(() => {
    pngGen = new PngGeneratorCell()
  })

  describe('describe', () => {
    it('should return correct metadata', async () => {
      const metadata = await pngGen.describe()

      expect(metadata.id).toBe('png-generator-cell')
      expect(metadata.name).toBe('PNG Generator Cell')
      expect(metadata.version).toBe('1.0.0')
      expect(metadata.tags).toContain('image-generation')
      expect(metadata.tags).toContain('stable-diffusion')
      expect(metadata.tags).toContain('background-removal')
      expect(metadata.required_resources).toContain('backend')
      expect(metadata.required_resources).toContain('gpu')
    })

    it('should describe both supported actions', async () => {
      const metadata = await pngGen.describe()

      expect(metadata.inputs.action.enum).toEqual(['generate', 'removeBackground'])
    })
  })

  describe('validate', () => {
    it('should require action field', () => {
      const errors = pngGen.validate({})

      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('action')
      expect(errors[0].message).toContain('required')
    })

    it('should reject invalid action', () => {
      const errors = pngGen.validate({ action: 'invalid-action' })

      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('action')
      expect(errors[0].message).toContain('must be one of')
    })

    it('should require prompt for generate action', () => {
      const errors = pngGen.validate({ action: 'generate' })

      expect(errors.length).toBeGreaterThan(0)
      const promptError = errors.find(e => e.field === 'prompt')
      expect(promptError).toBeDefined()
      expect(promptError?.message).toContain('required')
    })

    it('should accept valid generate input', () => {
      const errors = pngGen.validate({
        action: 'generate',
        prompt: 'A beautiful sunset'
      })

      expect(errors).toHaveLength(0)
    })

    it('should require generatedPng for removeBackground action', () => {
      const errors = pngGen.validate({ action: 'removeBackground' })

      expect(errors.length).toBeGreaterThan(0)
      const pngError = errors.find(e => e.field === 'generatedPng')
      expect(pngError).toBeDefined()
      expect(pngError?.message).toContain('required')
    })

    it('should accept valid removeBackground input', () => {
      const errors = pngGen.validate({
        action: 'removeBackground',
        generatedPng: 'base64encodeddata=='
      })

      expect(errors).toHaveLength(0)
    })

    it('should validate generation parameters', () => {
      const errors = pngGen.validate({
        action: 'generate',
        prompt: 'Test prompt',
        generationParams: {
          width: 50, // Too small
          height: 3000, // Too large
          steps: 150, // Too many
          cfg_scale: 25 // Too high
        }
      })

      expect(errors.length).toBeGreaterThan(0)
      expect(errors.some(e => e.field.includes('width'))).toBe(true)
      expect(errors.some(e => e.field.includes('height'))).toBe(true)
      expect(errors.some(e => e.field.includes('steps'))).toBe(true)
      expect(errors.some(e => e.field.includes('cfg_scale'))).toBe(true)
    })

    it('should accept valid generation parameters', () => {
      const errors = pngGen.validate({
        action: 'generate',
        prompt: 'Test prompt',
        generationParams: {
          width: 512,
          height: 512,
          steps: 30,
          cfg_scale: 7.5,
          seed: 42
        }
      })

      expect(errors).toHaveLength(0)
    })
  })

  describe('execute', () => {
    it('should return validation error for invalid input', async () => {
      const result = await pngGen.execute({ action: 'invalid' })

      expect(result.success).toBe(false)
      expect(result.error).toBe('Validation failed')
      expect(result.output.errors).toBeDefined()
    })

    it('should call backend API for generate action', async () => {
      const mockResponse = {
        ok: true,
        json: vi.fn().mockResolvedValue({
          success: true,
          generatedPng: 'base64data',
          has_png: true,
          prompt: 'A beautiful sunset'
        })
      }
      
      vi.mocked(apiService.fetch).mockResolvedValue(mockResponse as any)

      const input: PngGeneratorInput = {
        action: 'generate',
        prompt: 'A beautiful sunset',
        generationParams: {
          width: 512,
          height: 512
        }
      }

      const result = await pngGen.execute(input)

      expect(apiService.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json'
          }),
          body: expect.stringContaining('png-generator-cell')
        })
      )

      expect(result.success).toBe(true)
      expect(result.output.generatedPng).toBe('base64data')
      expect(result.artifacts).toHaveLength(1)
    })

    it('should handle backend errors gracefully', async () => {
      const mockResponse = {
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        text: vi.fn().mockResolvedValue('Error details')
      }
      
      vi.mocked(apiService.fetch).mockResolvedValue(mockResponse as any)

      const input: PngGeneratorInput = {
        action: 'generate',
        prompt: 'Test prompt'
      }

      const result = await pngGen.execute(input)

      expect(result.success).toBe(false)
      expect(result.error).toContain('Backend execution failed')
    })

    it('should handle network exceptions', async () => {
      vi.mocked(apiService.fetch).mockRejectedValue(new Error('Network error'))

      const input: PngGeneratorInput = {
        action: 'generate',
        prompt: 'Test prompt'
      }

      const result = await pngGen.execute(input)

      expect(result.success).toBe(false)
      expect(result.error).toContain('Network error')
    })
  })

  describe('health_check', () => {
    it('should return healthy when backend is available', async () => {
      const mockResponse = {
        ok: true
      }
      
      vi.mocked(apiService.fetch).mockResolvedValue(mockResponse as any)

      const health = await pngGen.health_check()

      expect(health.status).toBe('healthy')
      expect(health.can_execute).toBe(true)
    })

    it('should return degraded when backend returns error', async () => {
      const mockResponse = {
        ok: false,
        status: 503
      }
      
      vi.mocked(apiService.fetch).mockResolvedValue(mockResponse as any)

      const health = await pngGen.health_check()

      expect(health.status).toBe('degraded')
      expect(health.can_execute).toBe(false)
      expect(health.reason).toContain('unreachable')
    })

    it('should return unavailable on network exception', async () => {
      vi.mocked(apiService.fetch).mockRejectedValue(new Error('Connection refused'))

      const health = await pngGen.health_check()

      expect(health.status).toBe('unavailable')
      expect(health.can_execute).toBe(false)
      expect(health.reason).toContain('Connection refused')
    })
  })

  describe('lifecycle', () => {
    it('should support setup', async () => {
      await expect(pngGen.setup({
        has_gpu: true,
        gpu_vram_mb: 8000,
        cpu_cores: 8,
        headless_mode: false,
        timeout_seconds: 300
      })).resolves.toBeUndefined()
    })

    it('should support teardown', async () => {
      await expect(pngGen.teardown()).resolves.toBeUndefined()
    })
  })
})
