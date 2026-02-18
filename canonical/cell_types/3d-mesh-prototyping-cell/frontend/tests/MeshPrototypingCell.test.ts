/**
 * @file MeshPrototypingCell.test.ts
 * @description Unit tests for MeshPrototypingCell
 * 
 * Tests the MeshPrototypingCell BaseCell implementation
 * Part of BaseCell v1.0 Framework Implementation
 * Task: [3D-FE-001] Create MeshPrototypingCell TypeScript Implementation
 */

import { describe, it, expect, beforeAll, vi } from 'vitest'
import { MeshPrototypingCell } from '../MeshPrototypingCell'
import type { MeshPrototypingInput } from '../MeshPrototypingCell'

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

describe('MeshPrototypingCell', () => {
  let meshCell: MeshPrototypingCell

  beforeAll(() => {
    meshCell = new MeshPrototypingCell()
  })

  describe('describe', () => {
    it('should return correct metadata', async () => {
      const metadata = await meshCell.describe()

      expect(metadata.id).toBe('3d-mesh-prototyping-cell')
      expect(metadata.name).toBe('Mesh Prototyping Cell')
      expect(metadata.version).toBe('1.0.0')
      expect(metadata.tags).toContain('3d-generation')
      expect(metadata.tags).toContain('mesh-generation')
      expect(metadata.tags).toContain('2d-to-3d')
      expect(metadata.tags).toContain('glb')
      expect(metadata.required_resources).toContain('backend')
      expect(metadata.required_resources).toContain('gpu')
    })

    it('should describe all supported generation modes', async () => {
      const metadata = await meshCell.describe()

      expect(metadata.inputs.generationMode.enum).toEqual([
        'cloud-api',
        'local-gpu',
        'manual-upload'
      ])
    })

    it('should describe reconstruction parameters', async () => {
      const metadata = await meshCell.describe()

      expect(metadata.inputs.reconstructionParams).toBeDefined()
      expect(metadata.inputs.reconstructionParams.properties).toBeDefined()
      expect(metadata.inputs.reconstructionParams.properties.targetFaces).toBeDefined()
      expect(metadata.inputs.reconstructionParams.properties.enableDracoCompression).toBeDefined()
    })
  })

  describe('validate', () => {
    it('should require inputImage field', () => {
      const errors = meshCell.validate({})

      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('inputImage')
      expect(errors[0].message).toContain('required')
    })

    it('should reject empty inputImage', () => {
      const errors = meshCell.validate({ inputImage: '' })

      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('inputImage')
      expect(errors[0].message).toContain('required')
    })

    it('should reject invalid base64 format', () => {
      const errors = meshCell.validate({ inputImage: 'not-valid-base64!!!' })

      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('inputImage')
      expect(errors[0].message).toContain('valid base64')
    })

    it('should accept valid base64 string', () => {
      const errors = meshCell.validate({
        inputImage: 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
      })

      expect(errors).toHaveLength(0)
    })

    it('should accept valid base64 with data URI prefix', () => {
      const errors = meshCell.validate({
        inputImage: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
      })

      expect(errors).toHaveLength(0)
    })

    it('should reject invalid generation mode', () => {
      const errors = meshCell.validate({
        inputImage: 'validbase64data==',
        generationMode: 'invalid-mode'
      })

      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('generationMode')
      expect(errors[0].message).toContain('must be one of')
    })

    it('should accept valid generation modes', () => {
      const modes = ['cloud-api', 'local-gpu', 'manual-upload']
      
      modes.forEach(mode => {
        const errors = meshCell.validate({
          inputImage: 'validbase64data==',
          generationMode: mode
        })
        expect(errors).toHaveLength(0)
      })
    })

    it('should validate reconstruction parameters - targetFaces range', () => {
      const errors = meshCell.validate({
        inputImage: 'validbase64data==',
        reconstructionParams: {
          targetFaces: 50 // Too small
        }
      })

      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toContain('targetFaces')

      const errors2 = meshCell.validate({
        inputImage: 'validbase64data==',
        reconstructionParams: {
          targetFaces: 200000 // Too large
        }
      })

      expect(errors2.length).toBeGreaterThan(0)
      expect(errors2[0].field).toContain('targetFaces')
    })

    it('should validate reconstruction parameters - compressionLevel range', () => {
      const errors = meshCell.validate({
        inputImage: 'validbase64data==',
        reconstructionParams: {
          compressionLevel: 15 // Too high
        }
      })

      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toContain('compressionLevel')
    })

    it('should validate reconstruction parameters - enableDracoCompression type', () => {
      const errors = meshCell.validate({
        inputImage: 'validbase64data==',
        reconstructionParams: {
          enableDracoCompression: 'yes' as any // Wrong type
        }
      })

      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toContain('enableDracoCompression')
    })

    it('should accept valid reconstruction parameters', () => {
      const errors = meshCell.validate({
        inputImage: 'validbase64data==',
        reconstructionParams: {
          targetFaces: 10000,
          enableDracoCompression: true,
          compressionLevel: 7,
          targetFileSizeMB: 5
        }
      })

      expect(errors).toHaveLength(0)
    })
  })

  describe('execute', () => {
    it('should return validation error for invalid input', async () => {
      const result = await meshCell.execute({})

      expect(result.success).toBe(false)
      expect(result.error).toBe('Validation failed')
      expect(result.output.errors).toBeDefined()
    })

    it('should call backend API with correct payload', async () => {
      const mockResponse = {
        ok: true,
        json: vi.fn().mockResolvedValue({
          success: true,
          glb_url: 'http://example.com/model.glb',
          message: 'Mesh generated successfully'
        })
      }
      
      vi.mocked(apiService.fetch).mockResolvedValue(mockResponse as any)

      const input: MeshPrototypingInput = {
        inputImage: 'base64imagedata==',
        generationMode: 'cloud-api',
        reconstructionParams: {
          targetFaces: 10000,
          enableDracoCompression: true
        }
      }

      const result = await meshCell.execute(input)

      expect(apiService.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json'
          }),
          body: expect.stringContaining('3d-mesh-prototyping-cell')
        })
      )

      expect(result.success).toBe(true)
      expect(result.output.glb_url).toBe('http://example.com/model.glb')
      expect(result.artifacts).toHaveLength(1)
      expect(result.artifacts![0]).toBe('http://example.com/model.glb')
    })

    it('should handle local-gpu mode with job_id', async () => {
      const mockResponse = {
        ok: true,
        json: vi.fn().mockResolvedValue({
          success: true,
          job_id: 'job-12345',
          message: 'Job queued for processing'
        })
      }
      
      vi.mocked(apiService.fetch).mockResolvedValue(mockResponse as any)

      const input: MeshPrototypingInput = {
        inputImage: 'base64imagedata==',
        generationMode: 'local-gpu'
      }

      const result = await meshCell.execute(input)

      expect(result.success).toBe(true)
      expect(result.output.job_id).toBe('job-12345')
      expect(result.artifacts).toHaveLength(0) // No GLB yet
    })

    it('should handle backend errors gracefully', async () => {
      const mockResponse = {
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        text: vi.fn().mockResolvedValue('Error details')
      }
      
      vi.mocked(apiService.fetch).mockResolvedValue(mockResponse as any)

      const input: MeshPrototypingInput = {
        inputImage: 'base64imagedata=='
      }

      const result = await meshCell.execute(input)

      expect(result.success).toBe(false)
      expect(result.error).toContain('Backend execution failed')
    })

    it('should handle network exceptions', async () => {
      vi.mocked(apiService.fetch).mockRejectedValue(new Error('Connection timeout'))

      const input: MeshPrototypingInput = {
        inputImage: 'base64imagedata=='
      }

      const result = await meshCell.execute(input)

      expect(result.success).toBe(false)
      expect(result.error).toContain('Connection timeout')
    })
  })

  describe('health_check', () => {
    it('should return healthy when backend is available', async () => {
      const mockResponse = {
        ok: true
      }
      
      vi.mocked(apiService.fetch).mockResolvedValue(mockResponse as any)

      const health = await meshCell.health_check()

      expect(health.status).toBe('healthy')
      expect(health.can_execute).toBe(true)
    })

    it('should return degraded when backend returns error', async () => {
      const mockResponse = {
        ok: false,
        status: 503
      }
      
      vi.mocked(apiService.fetch).mockResolvedValue(mockResponse as any)

      const health = await meshCell.health_check()

      expect(health.status).toBe('degraded')
      expect(health.can_execute).toBe(false)
      expect(health.reason).toContain('unreachable')
    })

    it('should return unavailable on network exception', async () => {
      vi.mocked(apiService.fetch).mockRejectedValue(new Error('Network unreachable'))

      const health = await meshCell.health_check()

      expect(health.status).toBe('unavailable')
      expect(health.can_execute).toBe(false)
      expect(health.reason).toContain('Network unreachable')
    })
  })

  describe('lifecycle', () => {
    it('should support setup', async () => {
      await expect(meshCell.setup({
        has_gpu: true,
        gpu_vram_mb: 12000,
        cpu_cores: 16,
        headless_mode: false,
        timeout_seconds: 600
      })).resolves.toBeUndefined()
    })

    it('should support teardown', async () => {
      await expect(meshCell.teardown()).resolves.toBeUndefined()
    })
  })
})
