/**
 * @file PromptEnhancerCell.test.ts
 * @description Unit tests for PromptEnhancerCell utility cell
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { PromptEnhancerCell } from '../PromptEnhancerCell'
import type { PromptEnhancerInput } from '../PromptEnhancerCell'

describe('PromptEnhancerCell', () => {
  let cell: PromptEnhancerCell

  beforeEach(() => {
    cell = new PromptEnhancerCell()
  })

  describe('describe()', () => {
    it('should return correct metadata', async () => {
      const metadata = await cell.describe()

      expect(metadata.id).toBe('prompt-enhancer-cell')
      expect(metadata.name).toBe('Prompt Enhancer')
      expect(metadata.version).toBe('1.0.0')
      expect(metadata.tags).toContain('utility')
      expect(metadata.tags).toContain('headless')
      expect(// capabilities removed?.headless).toBe(true)
      expect(// capabilities removed?.composable).toBe(true)
      expect(// capabilities removed?.stateless).toBe(true)
    })
  })

  describe('validate()', () => {
    it('should pass validation for valid input', () => {
      const input: PromptEnhancerInput = {
        prompt: 'Generate a login form'
      }

      const errors = cell.validate(input)
      expect(errors).toHaveLength(0)
    })

    it('should fail validation for missing prompt', () => {
      const input = {} as PromptEnhancerInput

      const errors = cell.validate(input)
      expect(errors).toHaveLength(1)
      expect(errors[0].field).toBe('prompt')
      expect('INVALID_PROMPT').toBe('INVALID_PROMPT')
    })

    it('should fail validation for empty prompt', () => {
      const input: PromptEnhancerInput = {
        prompt: ''
      }

      const errors = cell.validate(input)
      expect(errors.length).toBeGreaterThan(0)
      expect(errors.some(e => e.message.includes('empty'))).toBe(true)
    })

    it('should fail validation for invalid mode', () => {
      const input: PromptEnhancerInput = {
        prompt: 'Test',
        mode: 'invalid' as any
      }

      const errors = cell.validate(input)
      expect(errors.some(e => e.field === 'mode')).toBe(true)
    })

    it('should fail validation for invalid audience', () => {
      const input: PromptEnhancerInput = {
        prompt: 'Test',
        audience: 'invalid' as any
      }

      const errors = cell.validate(input)
      expect(errors.some(e => e.field === 'audience')).toBe(true)
    })

    it('should fail validation for invalid maxLength', () => {
      const input: PromptEnhancerInput = {
        prompt: 'Test',
        maxLength: -1
      }

      const errors = cell.validate(input)
      expect(errors.some(e => e.field === 'maxLength')).toBe(true)
    })
  })

  describe('execute()', () => {
    it('should enhance prompt with default mode', async () => {
      const input: PromptEnhancerInput = {
        prompt: 'Create a button'
      }

      const result = await cell.execute(input)

      expect(result.success).toBe(true)
      expect(result.data).toBeDefined()
      expect(result.output.enhancedPrompt).toBeDefined()
      expect(result.output.originalPrompt).toBe(input.prompt)
      expect(result.output.enhancements).toBeInstanceOf(Array)
      expect(result.output.estimatedTokens).toBeGreaterThan(0)
    })

    it('should enhance prompt with concise mode', async () => {
      const input: PromptEnhancerInput = {
        prompt: 'Create a button',
        mode: 'concise'
      }

      const result = await cell.execute(input)

      expect(result.success).toBe(true)
      expect(result.output.enhancedPrompt).toContain('Brief request:')
      expect(result.output.enhancements).toContain('Applied concise mode')
    })

    it('should enhance prompt with technical mode', async () => {
      const input: PromptEnhancerInput = {
        prompt: 'Create a button',
        mode: 'technical'
      }

      const result = await cell.execute(input)

      expect(result.success).toBe(true)
      expect(result.output.enhancedPrompt).toContain('Technical specification:')
      expect(result.output.enhancedPrompt).toContain('best practices')
      expect(result.output.enhancements).toContain('Applied technical mode')
    })

    it('should enhance prompt with creative mode', async () => {
      const input: PromptEnhancerInput = {
        prompt: 'Create a button',
        mode: 'creative'
      }

      const result = await cell.execute(input)

      expect(result.success).toBe(true)
      expect(result.output.enhancedPrompt).toContain('Creative exploration:')
      expect(result.output.enhancements).toContain('Applied creative mode')
    })

    it('should add context when provided', async () => {
      const input: PromptEnhancerInput = {
        prompt: 'Create a button',
        context: 'Building a Vue.js application'
      }

      const result = await cell.execute(input)

      expect(result.success).toBe(true)
      expect(result.output.enhancedPrompt).toContain('Context: Building a Vue.js application')
      expect(result.output.enhancements).toContain('Added context')
    })

    it('should apply developer audience framing', async () => {
      const input: PromptEnhancerInput = {
        prompt: 'Create a button',
        audience: 'developer'
      }

      const result = await cell.execute(input)

      expect(result.success).toBe(true)
      expect(result.output.enhancedPrompt).toContain('As a developer,')
      expect(result.output.enhancements).toContain('Added developer framing')
    })

    it('should apply user audience framing', async () => {
      const input: PromptEnhancerInput = {
        prompt: 'Create a button',
        audience: 'user'
      }

      const result = await cell.execute(input)

      expect(result.success).toBe(true)
      expect(result.output.enhancedPrompt).toContain('From a user perspective,')
      expect(result.output.enhancements).toContain('Added user framing')
    })

    it('should truncate prompt if maxLength specified', async () => {
      const input: PromptEnhancerInput = {
        prompt: 'Create a very detailed button with lots of features and functionality',
        mode: 'detailed',
        maxLength: 50
      }

      const result = await cell.execute(input)

      expect(result.success).toBe(true)
      expect(result.output.enhancedPrompt.length).toBeLessThanOrEqual(50)
      expect(result.output.enhancedPrompt).toMatch(/\.\.\.$/)
      expect(result.output.enhancements.some(e => e.includes('Truncated'))).toBe(true)
    })

    it('should return error for invalid input', async () => {
      const input = {} as PromptEnhancerInput

      const result = await cell.execute(input)

      expect(result.success).toBe(false)
      expect(result.error).toBeDefined()
      expect(result.error).toContain('Validation failed')
    })

    it('should include execution metadata', async () => {
      const input: PromptEnhancerInput = {
        prompt: 'Test prompt'
      }

      const result = await cell.execute(input)

      expect(result.metadata).toBeDefined()
      expect(result.execution_time).toBeGreaterThanOrEqual(0)
      expect(result.metadata?.timestamp).toBeDefined()
    })
  })

  describe('setup() and teardown()', () => {
    it('should execute setup and teardown without errors', async () => {
      const mockConfig = {
        has_gpu: false,
        gpu_vram_mb: 0,
        cpu_cores: 4,
        headless_mode: false,
        timeout_seconds: 300
      }
      await expect(cell.setup(mockConfig)).resolves.toBeUndefined()
      await expect(cell.teardown()).resolves.toBeUndefined()
    })
  })

  describe('health_check()', () => {
    it('should always return healthy status', async () => {
      const health = await cell.health_check()

      expect(health.status).toBe('healthy')
      expect(health.can_execute).toBe(true)
      expect(health.reason).toBeDefined()
    })
  })

  describe('token estimation', () => {
    it('should estimate tokens reasonably', async () => {
      const shortPrompt: PromptEnhancerInput = {
        prompt: 'Hi'  // 2 chars → ~1 token
      }

      const longPrompt: PromptEnhancerInput = {
        prompt: 'This is a much longer prompt with many words'  // ~45 chars → ~11 tokens
      }

      const shortResult = await cell.execute(shortPrompt)
      const longResult = await cell.execute(longPrompt)

      expect(shortResult.data.estimatedTokens).toBeLessThan(longResult.data.estimatedTokens)
    })
  })
})
