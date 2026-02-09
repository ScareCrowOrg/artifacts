/**
 * @file SvgGeneratorCell.test.ts
 * @description Unit tests for SvgGeneratorCell BaseCell implementation
 * 
 * Tests cover:
 * - Execution with valid inputs
 * - Input validation
 * - Health checking
 * - Metadata description
 * - Error handling and fallback mechanisms
 * - LLM service integration
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { SvgGeneratorCell } from '../SvgGeneratorCell'
import type { CellResult, CellMetadata, ValidationError } from '@/types/BaseCell'
import * as aiChatService from '@/services/aiChatService'

// Mock the AI chat service
vi.mock('@/services/aiChatService', () => ({
  processMessage: vi.fn(),
  fetchAvailableModels: vi.fn(),
}))

describe('SvgGeneratorCell', () => {
  let cell: SvgGeneratorCell
  
  beforeEach(() => {
    cell = new SvgGeneratorCell()
    vi.clearAllMocks()
  })
  
  afterEach(() => {
    vi.restoreAllMocks()
  })
  
  describe('execute()', () => {
    it('should successfully generate SVG from valid prompt', async () => {
      // Mock successful LLM response
      const mockSvg = '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40" fill="blue"/></svg>'
      vi.mocked(aiChatService.processMessage).mockResolvedValue({
        message: mockSvg
      } as any)
      
      const result = await cell.execute({
        prompt: 'A blue circle with radius 40'
      })
      
      expect(result.success).toBe(true)
      expect(result.output.svg).toBe(mockSvg)
      expect(result.output.prompt).toBe('A blue circle with radius 40')
      expect(result.output.model).toBe('mistral') // default model
      expect(result.output.fallback).toBeUndefined()
      expect(result.execution_time).toBeGreaterThan(0)
      expect(result.execution_steps).toContain('validate')
      expect(result.execution_steps).toContain('call_llm')
    })
    
    it('should extract SVG from code blocks', async () => {
      // Mock LLM response with code blocks
      const mockSvg = '<svg viewBox="0 0 100 100"><rect width="100" height="100" fill="red"/></svg>'
      vi.mocked(aiChatService.processMessage).mockResolvedValue({
        message: '```svg\n' + mockSvg + '\n```'
      } as any)
      
      const result = await cell.execute({
        prompt: 'A red square'
      })
      
      expect(result.success).toBe(true)
      expect(result.output.svg).toBe(mockSvg)
    })
    
    it('should use fallback SVG when LLM service fails', async () => {
      // Mock LLM service failure
      vi.mocked(aiChatService.processMessage).mockRejectedValue(
        new Error('LLM service unavailable')
      )
      
      const result = await cell.execute({
        prompt: 'A complex visualization'
      })
      
      expect(result.success).toBe(true)
      expect(result.output.fallback).toBe(true)
      expect(result.output.svg).toContain('<svg')
      expect(result.output.svg).toContain('</svg>')
      expect(result.execution_steps).toContain('use_fallback')
    })
    
    it('should use fallback when generated content is not valid SVG', async () => {
      // Mock LLM returning non-SVG content
      vi.mocked(aiChatService.processMessage).mockResolvedValue({
        message: 'Here is a description instead of SVG code'
      } as any)
      
      const result = await cell.execute({
        prompt: 'A visualization'
      })
      
      expect(result.success).toBe(true)
      expect(result.output.fallback).toBe(true)
    })
    
    it('should respect custom model parameter', async () => {
      const mockSvg = '<svg viewBox="0 0 50 50"><circle cx="25" cy="25" r="20"/></svg>'
      vi.mocked(aiChatService.processMessage).mockResolvedValue({
        message: mockSvg
      } as any)
      
      const result = await cell.execute({
        prompt: 'A small circle',
        model: 'gpt-4'
      })
      
      expect(result.success).toBe(true)
      expect(result.output.model).toBe('gpt-4')
      expect(aiChatService.processMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          model: 'gpt-4'
        })
      )
    })
    
    it('should fail validation with empty prompt', async () => {
      const result = await cell.execute({
        prompt: ''
      })
      
      expect(result.success).toBe(false)
      expect(result.error).toBe('Validation failed')
      expect(result.output.errors).toBeDefined()
      expect(result.output.errors.length).toBeGreaterThan(0)
    })
    
    it('should fail validation with missing prompt', async () => {
      const result = await cell.execute({})
      
      expect(result.success).toBe(false)
      expect(result.error).toBe('Validation failed')
    })
    
    it('should include execution metadata', async () => {
      const mockSvg = '<svg><circle/></svg>'
      vi.mocked(aiChatService.processMessage).mockResolvedValue({
        message: mockSvg
      } as any)
      
      const result = await cell.execute({
        prompt: 'Test prompt'
      })
      
      expect(result.metadata).toBeDefined()
      expect(result.metadata?.model).toBe('mistral')
      expect(result.metadata?.prompt_length).toBe(11)
      expect(result.metadata?.svg_length).toBeGreaterThan(0)
    })
  })
  
  describe('describe()', () => {
    it('should return complete cell metadata', async () => {
      const metadata = await cell.describe()
      
      expect(metadata.id).toBe('svg-generator-cell')
      expect(metadata.name).toBe('SVG Generator Cell')
      expect(metadata.version).toBe('1.0.0')
      expect(metadata.description).toContain('SVG')
      expect(metadata.tags).toContain('visualization')
      expect(metadata.tags).toContain('svg')
      expect(metadata.estimated_duration_seconds).toBeGreaterThan(0)
    })
    
    it('should describe required inputs', async () => {
      const metadata = await cell.describe()
      
      expect(metadata.inputs.prompt).toBeDefined()
      expect(metadata.inputs.prompt.type).toBe('string')
      expect(metadata.inputs.prompt.required).toBe(true)
    })
    
    it('should describe optional inputs', async () => {
      const metadata = await cell.describe()
      
      expect(metadata.inputs.model).toBeDefined()
      expect(metadata.inputs.model.required).toBe(false)
      expect(metadata.inputs.model.default).toBe('mistral')
      
      expect(metadata.inputs.temperature).toBeDefined()
      expect(metadata.inputs.temperature.required).toBe(false)
    })
    
    it('should describe outputs', async () => {
      const metadata = await cell.describe()
      
      expect(metadata.outputs.svg).toBeDefined()
      expect(metadata.outputs.svg.type).toBe('string')
      expect(metadata.outputs.prompt).toBeDefined()
      expect(metadata.outputs.model).toBeDefined()
    })
    
    it('should list required resources', async () => {
      const metadata = await cell.describe()
      
      expect(metadata.required_resources).toBeDefined()
      expect(metadata.required_resources).toContain('llm-service')
    })
  })
  
  describe('validate()', () => {
    it('should pass validation with valid input', () => {
      const errors = cell.validate({
        prompt: 'A valid prompt',
        model: 'mistral'
      })
      
      expect(errors).toHaveLength(0)
    })
    
    it('should fail when prompt is missing', () => {
      const errors = cell.validate({})
      
      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toBe('prompt')
      expect(errors[0].message).toContain('required')
    })
    
    it('should fail when prompt is not a string', () => {
      const errors = cell.validate({
        prompt: 123
      })
      
      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toBe('prompt')
      expect(errors[0].message).toContain('string')
    })
    
    it('should fail when prompt is empty', () => {
      const errors = cell.validate({
        prompt: '   '
      })
      
      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toBe('prompt')
      expect(errors[0].message).toContain('empty')
    })
    
    it('should fail when prompt is too long', () => {
      const longPrompt = 'a'.repeat(5001)
      const errors = cell.validate({
        prompt: longPrompt
      })
      
      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toBe('prompt')
      expect(errors[0].message).toContain('too long')
    })
    
    it('should fail when model is not a string', () => {
      const errors = cell.validate({
        prompt: 'Valid prompt',
        model: 123
      })
      
      expect(errors.length).toBeGreaterThan(0)
      expect(errors[0].field).toBe('model')
    })
    
    it('should fail when temperature is out of range', () => {
      const errors1 = cell.validate({
        prompt: 'Valid prompt',
        temperature: -0.1
      })
      expect(errors1.length).toBeGreaterThan(0)
      expect(errors1[0].field).toBe('temperature')
      
      const errors2 = cell.validate({
        prompt: 'Valid prompt',
        temperature: 1.1
      })
      expect(errors2.length).toBeGreaterThan(0)
      expect(errors2[0].field).toBe('temperature')
    })
    
    it('should fail when maxTokens is out of range', () => {
      const errors1 = cell.validate({
        prompt: 'Valid prompt',
        maxTokens: 50
      })
      expect(errors1.length).toBeGreaterThan(0)
      expect(errors1[0].field).toBe('maxTokens')
      
      const errors2 = cell.validate({
        prompt: 'Valid prompt',
        maxTokens: 20000
      })
      expect(errors2.length).toBeGreaterThan(0)
      expect(errors2[0].field).toBe('maxTokens')
    })
    
    it('should allow valid optional parameters', () => {
      const errors = cell.validate({
        prompt: 'Valid prompt',
        model: 'gpt-4',
        temperature: 0.7,
        maxTokens: 2000
      })
      
      expect(errors).toHaveLength(0)
    })
  })
  
  describe('health_check()', () => {
    it('should return healthy when models are available', async () => {
      vi.mocked(aiChatService.fetchAvailableModels).mockResolvedValue([
        { value: 'mistral', label: 'Mistral', type: 'local', provider: 'ollama' },
        { value: 'gpt-4', label: 'GPT-4', type: 'cloud', provider: 'openai' }
      ] as any)
      
      const health = await cell.health_check()
      
      expect(health.status).toBe('healthy')
      expect(health.can_execute).toBe(true)
      expect(health.reason).toContain('available')
      expect(health.reason).toContain('2 models')
    })
    
    it('should return degraded when no models found', async () => {
      vi.mocked(aiChatService.fetchAvailableModels).mockResolvedValue([])
      
      const health = await cell.health_check()
      
      expect(health.status).toBe('degraded')
      expect(health.can_execute).toBe(true)
      expect(health.reason).toContain('no models')
    })
    
    it('should return degraded when service is unavailable', async () => {
      vi.mocked(aiChatService.fetchAvailableModels).mockRejectedValue(
        new Error('Service unavailable')
      )
      
      const health = await cell.health_check()
      
      expect(health.status).toBe('degraded')
      expect(health.can_execute).toBe(true)
      expect(health.reason).toContain('unavailable')
      expect(health.reason).toContain('Service unavailable')
    })
  })
  
  describe('Integration Tests', () => {
    it('should handle complete workflow: validate -> execute -> success', async () => {
      const mockSvg = '<svg><rect/></svg>'
      vi.mocked(aiChatService.processMessage).mockResolvedValue({
        message: mockSvg
      } as any)
      
      // Step 1: Validate
      const errors = cell.validate({
        prompt: 'A rectangle'
      })
      expect(errors).toHaveLength(0)
      
      // Step 2: Execute
      const result = await cell.execute({
        prompt: 'A rectangle'
      })
      expect(result.success).toBe(true)
      
      // Step 3: Verify output
      expect(result.output.svg).toBe(mockSvg)
    })
    
    it('should handle complete workflow: validate -> execute -> fallback', async () => {
      vi.mocked(aiChatService.processMessage).mockRejectedValue(
        new Error('Service error')
      )
      
      // Step 1: Validate
      const errors = cell.validate({
        prompt: 'Test prompt'
      })
      expect(errors).toHaveLength(0)
      
      // Step 2: Execute with fallback
      const result = await cell.execute({
        prompt: 'Test prompt'
      })
      expect(result.success).toBe(true)
      expect(result.output.fallback).toBe(true)
    })
    
    it('should measure execution time accurately', async () => {
      const mockSvg = '<svg><circle/></svg>'
      vi.mocked(aiChatService.processMessage).mockResolvedValue({
        message: mockSvg
      } as any)
      
      const startTime = performance.now()
      const result = await cell.execute({
        prompt: 'A circle'
      })
      const endTime = performance.now()
      
      expect(result.execution_time).toBeGreaterThan(0)
      expect(result.execution_time).toBeLessThan(endTime - startTime + 10) // Allow 10ms margin
    })
  })
})
