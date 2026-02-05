/**
 * @file AssetPrototypingCell.test.ts
 * @description Unit tests for AssetPrototypingCell
 * 
 * Tests cover:
 * - Composition of sub-cells (PNG + Mesh)
 * - Coordinated lifecycle (setup/teardown)
 * - Headless execution
 * - Error handling and partial failures
 * - Health checking across sub-cells
 * 
 * Part of BaseCell v1.0 Framework Implementation - Phase 2: Composition
 * Task: [ASSET-001] AssetPrototypingCell Tests
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { AssetPrototypingCell } from '../AssetPrototypingCell'
import type { CellResult, HealthCheckResult } from '@/types/BaseCell'

// Mock sub-cells
vi.mock('../../png-generator-cell/frontend/PngGeneratorCell', () => ({
  PngGeneratorCell: vi.fn().mockImplementation(() => ({
    execute: vi.fn().mockResolvedValue({
      success: true,
      output: { generatedPng: 'mock-base64-png-data' },
      execution_time: 100
    }),
    describe: vi.fn().mockResolvedValue({
      id: 'png-generator-cell',
      name: 'PNG Generator',
      version: '1.0.0'
    }),
    validate: vi.fn().mockReturnValue([]),
    setup: vi.fn().mockResolvedValue(undefined),
    teardown: vi.fn().mockResolvedValue(undefined),
    health_check: vi.fn().mockResolvedValue({
      status: 'healthy',
      can_execute: true
    })
  }))
}))

vi.mock('../../3d-mesh-prototyping-cell/frontend/MeshPrototypingCell', () => ({
  MeshPrototypingCell: vi.fn().mockImplementation(() => ({
    execute: vi.fn().mockResolvedValue({
      success: true,
      output: { glb_url: 'https://example.com/asset.glb' },
      execution_time: 200
    }),
    describe: vi.fn().mockResolvedValue({
      id: '3d-mesh-prototyping-cell',
      name: '3D Mesh Prototyping',
      version: '1.0.0'
    }),
    validate: vi.fn().mockReturnValue([]),
    setup: vi.fn().mockResolvedValue(undefined),
    teardown: vi.fn().mockResolvedValue(undefined),
    health_check: vi.fn().mockResolvedValue({
      status: 'healthy',
      can_execute: true
    })
  }))
}))

describe('AssetPrototypingCell', () => {
  let cell: AssetPrototypingCell
  
  beforeEach(() => {
    vi.clearAllMocks()
    cell = new AssetPrototypingCell()
  })
  
  // ===== INSTANTIATION =====
  
  describe('instantiation', () => {
    it('should create cell with sub-cells', () => {
      expect(cell).toBeDefined()
      expect(cell).toHaveProperty('execute')
      expect(cell).toHaveProperty('describe')
      expect(cell).toHaveProperty('validate')
      expect(cell).toHaveProperty('setup')
      expect(cell).toHaveProperty('teardown')
      expect(cell).toHaveProperty('health_check')
    })
  })
  
  // ===== DESCRIBE =====
  
  describe('describe()', () => {
    it('should return metadata', async () => {
      const metadata = await cell.describe()
      
      expect(metadata.id).toBe('asset-prototyping-cell')
      expect(metadata.name).toBe('Asset Prototyping Cell')
      expect(metadata.version).toBe('1.0.0')
      expect(metadata.description).toContain('composition')
      expect(metadata.tags).toContain('composition')
      expect(metadata.tags).toContain('pipeline')
      expect(metadata.required_resources).toContain('backend')
      expect(metadata.llm_config?.composedCells).toEqual([
        'png-generator-cell',
        'mesh-prototyping-cell'
      ])
    })
    
    it('should declare inputs correctly', async () => {
      const metadata = await cell.describe()
      
      expect(metadata.inputs.prompt).toBeDefined()
      expect(metadata.inputs.prompt.required).toBe(true)
      expect(metadata.inputs.negativePrompt).toBeDefined()
      expect(metadata.inputs.asset3dMode).toBeDefined()
      expect(metadata.inputs.reconstructionParams).toBeDefined()
      expect(metadata.inputs.generationMode).toBeDefined()
    })
    
    it('should declare outputs correctly', async () => {
      const metadata = await cell.describe()
      
      expect(metadata.outputs.texturePng).toBeDefined()
      expect(metadata.outputs.meshGlbUrl).toBeDefined()
      expect(metadata.outputs.stepsCompleted).toBeDefined()
    })
  })
  
  // ===== VALIDATE =====
  
  describe('validate()', () => {
    it('should accept valid input', () => {
      const errors = cell.validate({
        prompt: 'a fantasy sword'
      })
      
      expect(errors).toHaveLength(0)
    })
    
    it('should reject missing prompt', () => {
      const errors = cell.validate({})
      
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('prompt')
      expect(errors[0].message).toContain('required')
    })
    
    it('should reject empty prompt', () => {
      const errors = cell.validate({ prompt: '   ' })
      
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('prompt')
      expect(errors[0].message).toContain('empty')
    })
    
    it('should reject prompt too long', () => {
      const errors = cell.validate({ 
        prompt: 'a'.repeat(1001) 
      })
      
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('prompt')
      expect(errors[0].message).toContain('1000 characters')
    })
    
    it('should validate optional fields', () => {
      const errors = cell.validate({
        prompt: 'a sword',
        negativePrompt: 'blurry',
        asset3dMode: true,
        generationMode: 'cloud-api'
      })
      
      expect(errors).toHaveLength(0)
    })
    
    it('should reject invalid generation mode', () => {
      const errors = cell.validate({
        prompt: 'a sword',
        generationMode: 'invalid-mode'
      })
      
      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toBe('generationMode')
    })
    
    it('should validate reconstruction params', () => {
      const errors = cell.validate({
        prompt: 'a sword',
        reconstructionParams: {
          targetFaces: 5000,
          enableDracoCompression: true,
          compressionLevel: 7
        }
      })
      
      expect(errors).toHaveLength(0)
    })
    
    it('should reject invalid reconstruction params', () => {
      const errors = cell.validate({
        prompt: 'a sword',
        reconstructionParams: {
          targetFaces: 50, // too low
          compressionLevel: 15 // too high
        }
      })
      
      expect(errors.length).toBeGreaterThan(0)
    })
  })
  
  // ===== EXECUTE =====
  
  describe('execute()', () => {
    it('should execute complete pipeline', async () => {
      const result = await cell.execute({
        prompt: 'a fantasy sword with ornate handle',
        asset3dMode: true
      })
      
      expect(result.success).toBe(true)
      expect(result.output.texturePng).toBe('mock-base64-png-data')
      expect(result.output.meshGlbUrl).toBe('https://example.com/asset.glb')
      expect(result.output.stepsCompleted).toEqual([
        'generate_texture',
        'generate_mesh',
        'combine_asset'
      ])
      expect(result.execution_time).toBeGreaterThan(0)
    })
    
    it('should pass correct params to PNG cell', async () => {
      const { PngGeneratorCell } = await import('../../png-generator-cell/frontend/PngGeneratorCell')
      const mockPngCell = new PngGeneratorCell()
      
      await cell.execute({
        prompt: 'test prompt',
        negativePrompt: 'test negative',
        asset3dMode: true
      })
      
      expect(mockPngCell.execute).toHaveBeenCalledWith({
        action: 'generate',
        prompt: 'test prompt',
        negativePrompt: 'test negative',
        asset3dMode: true
      })
    })
    
    it('should pass texture to Mesh cell', async () => {
      const { MeshPrototypingCell } = await import('../../3d-mesh-prototyping-cell/frontend/MeshPrototypingCell')
      const mockMeshCell = new MeshPrototypingCell()
      
      await cell.execute({
        prompt: 'test prompt',
        reconstructionParams: { targetFaces: 5000 },
        generationMode: 'cloud-api'
      })
      
      expect(mockMeshCell.execute).toHaveBeenCalledWith({
        inputImage: 'mock-base64-png-data',
        reconstructionParams: { targetFaces: 5000 },
        generationMode: 'cloud-api'
      })
    })
    
    it('should fail validation early', async () => {
      const result = await cell.execute({})
      
      expect(result.success).toBe(false)
      expect(result.error).toContain('Validation failed')
      expect(result.output.stepsCompleted).toHaveLength(0)
    })
    
    it('should handle PNG generation failure', async () => {
      const { PngGeneratorCell } = await import('../../png-generator-cell/frontend/PngGeneratorCell')
      const mockPngCell = new PngGeneratorCell()
      
      vi.mocked(mockPngCell.execute).mockResolvedValueOnce({
        success: false,
        output: {},
        execution_time: 50,
        error: 'PNG generation failed'
      })
      
      const result = await cell.execute({
        prompt: 'test prompt'
      })
      
      expect(result.success).toBe(false)
      expect(result.error).toContain('Texture generation failed')
      expect(result.output.stepsCompleted).toHaveLength(0)
    })
    
    it('should handle mesh generation failure (partial success)', async () => {
      const { MeshPrototypingCell } = await import('../../3d-mesh-prototyping-cell/frontend/MeshPrototypingCell')
      const mockMeshCell = new MeshPrototypingCell()
      
      vi.mocked(mockMeshCell.execute).mockResolvedValueOnce({
        success: false,
        output: {},
        execution_time: 100,
        error: 'Mesh generation failed'
      })
      
      const result = await cell.execute({
        prompt: 'test prompt'
      })
      
      expect(result.success).toBe(false)
      expect(result.error).toContain('Mesh generation failed')
      // Should have texture PNG even though mesh failed
      expect(result.output.texturePng).toBe('mock-base64-png-data')
      expect(result.output.stepsCompleted).toEqual(['generate_texture'])
    })
    
    it('should include execution metadata', async () => {
      const result = await cell.execute({
        prompt: 'test prompt'
      })
      
      expect(result.metadata).toBeDefined()
      expect(result.metadata?.prompt).toBe('test prompt')
      expect(result.metadata?.textureGenTime).toBeGreaterThan(0)
      expect(result.metadata?.meshGenTime).toBeGreaterThan(0)
    })
  })
  
  // ===== LIFECYCLE =====
  
  describe('setup()', () => {
    it('should setup all sub-cells', async () => {
      const { PngGeneratorCell } = await import('../../png-generator-cell/frontend/PngGeneratorCell')
      const { MeshPrototypingCell } = await import('../../3d-mesh-prototyping-cell/frontend/MeshPrototypingCell')
      
      const mockPngCell = new PngGeneratorCell()
      const mockMeshCell = new MeshPrototypingCell()
      
      const config = {
        has_gpu: false,
        gpu_vram_mb: 0,
        cpu_cores: 4,
        headless_mode: true,
        timeout_seconds: 300
      }
      
      await cell.setup(config)
      
      expect(mockPngCell.setup).toHaveBeenCalledWith(config)
      expect(mockMeshCell.setup).toHaveBeenCalledWith(config)
    })
    
    it('should not setup twice', async () => {
      const { PngGeneratorCell } = await import('../../png-generator-cell/frontend/PngGeneratorCell')
      const mockPngCell = new PngGeneratorCell()
      
      const config = {
        has_gpu: false,
        gpu_vram_mb: 0,
        cpu_cores: 4,
        headless_mode: true,
        timeout_seconds: 300
      }
      
      await cell.setup(config)
      await cell.setup(config)
      
      // Should only be called once
      expect(mockPngCell.setup).toHaveBeenCalledTimes(1)
    })
  })
  
  describe('teardown()', () => {
    it('should teardown all sub-cells', async () => {
      const { PngGeneratorCell } = await import('../../png-generator-cell/frontend/PngGeneratorCell')
      const { MeshPrototypingCell } = await import('../../3d-mesh-prototyping-cell/frontend/MeshPrototypingCell')
      
      const mockPngCell = new PngGeneratorCell()
      const mockMeshCell = new MeshPrototypingCell()
      
      const config = {
        has_gpu: false,
        gpu_vram_mb: 0,
        cpu_cores: 4,
        headless_mode: true,
        timeout_seconds: 300
      }
      
      await cell.setup(config)
      await cell.teardown()
      
      expect(mockPngCell.teardown).toHaveBeenCalled()
      expect(mockMeshCell.teardown).toHaveBeenCalled()
    })
    
    it('should handle teardown without setup', async () => {
      await expect(cell.teardown()).resolves.not.toThrow()
    })
  })
  
  // ===== HEALTH CHECK =====
  
  describe('health_check()', () => {
    it('should be healthy when all sub-cells are healthy', async () => {
      const result = await cell.health_check()
      
      expect(result.status).toBe('healthy')
      expect(result.can_execute).toBe(true)
    })
    
    it('should be unavailable when PNG cell is unavailable', async () => {
      const { PngGeneratorCell } = await import('../../png-generator-cell/frontend/PngGeneratorCell')
      const mockPngCell = new PngGeneratorCell()
      
      vi.mocked(mockPngCell.health_check).mockResolvedValueOnce({
        status: 'unavailable',
        can_execute: false,
        reason: 'Backend not responding'
      })
      
      const result = await cell.health_check()
      
      expect(result.status).toBe('unavailable')
      expect(result.can_execute).toBe(false)
      expect(result.reason).toContain('unavailable')
    })
    
    it('should be unavailable when Mesh cell is unavailable', async () => {
      const { MeshPrototypingCell } = await import('../../3d-mesh-prototyping-cell/frontend/MeshPrototypingCell')
      const mockMeshCell = new MeshPrototypingCell()
      
      vi.mocked(mockMeshCell.health_check).mockResolvedValueOnce({
        status: 'unavailable',
        can_execute: false,
        reason: '3D API not responding'
      })
      
      const result = await cell.health_check()
      
      expect(result.status).toBe('unavailable')
      expect(result.can_execute).toBe(false)
    })
    
    it('should be degraded when one sub-cell is degraded', async () => {
      const { PngGeneratorCell } = await import('../../png-generator-cell/frontend/PngGeneratorCell')
      const mockPngCell = new PngGeneratorCell()
      
      vi.mocked(mockPngCell.health_check).mockResolvedValueOnce({
        status: 'degraded',
        can_execute: false,
        reason: 'High backend latency'
      })
      
      const result = await cell.health_check()
      
      expect(result.status).toBe('degraded')
      expect(result.can_execute).toBe(false)
      expect(result.reason).toContain('degraded')
    })
  })
  
  // ===== COMPOSITION PATTERNS =====
  
  describe('composition patterns', () => {
    it('should demonstrate sequential execution', async () => {
      const { PngGeneratorCell } = await import('../../png-generator-cell/frontend/PngGeneratorCell')
      const { MeshPrototypingCell } = await import('../../3d-mesh-prototyping-cell/frontend/MeshPrototypingCell')
      
      const mockPngCell = new PngGeneratorCell()
      const mockMeshCell = new MeshPrototypingCell()
      
      await cell.execute({
        prompt: 'test'
      })
      
      // PNG should be called before Mesh
      const pngCallOrder = vi.mocked(mockPngCell.execute).mock.invocationCallOrder[0]
      const meshCallOrder = vi.mocked(mockMeshCell.execute).mock.invocationCallOrder[0]
      
      expect(pngCallOrder).toBeLessThan(meshCallOrder)
    })
    
    it('should demonstrate data flow between cells', async () => {
      const { MeshPrototypingCell } = await import('../../3d-mesh-prototyping-cell/frontend/MeshPrototypingCell')
      const mockMeshCell = new MeshPrototypingCell()
      
      await cell.execute({
        prompt: 'test'
      })
      
      // Mesh cell should receive PNG output
      const meshInput = vi.mocked(mockMeshCell.execute).mock.calls[0][0]
      expect(meshInput.inputImage).toBe('mock-base64-png-data')
    })
  })
})
