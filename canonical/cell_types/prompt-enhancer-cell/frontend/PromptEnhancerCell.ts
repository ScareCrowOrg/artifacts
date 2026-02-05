/**
 * @file PromptEnhancerCell.ts
 * @description Utility cell for enhancing prompts with context and best practices
 * 
 * This is a headless utility cell (no View.vue) that demonstrates the utility cell pattern.
 * It can be used as a building block for other cells that need prompt enhancement capabilities.
 * 
 * Part of BaseCell v1.0 Framework - Phase 3: Utilities
 * Task: [UTIL-CELLS] Implement utility cells
 */

import type { BaseCell, CellResult, CellMetadata, ValidationError, EnvironmentConfig, HealthCheckResult } from '@/types/BaseCell'
import { createLogger } from '@/utils/logger'

const log = createLogger('cell:prompt-enhancer')

/**
 * Input structure for PromptEnhancerCell
 */
export interface PromptEnhancerInput {
  /** Original prompt to enhance */
  prompt: string
  
  /** Optional context to add to the prompt */
  context?: string
  
  /** Enhancement mode */
  mode?: 'concise' | 'detailed' | 'technical' | 'creative'
  
  /** Target audience */
  audience?: 'developer' | 'user' | 'ai' | 'general'
  
  /** Maximum length of enhanced prompt (optional) */
  maxLength?: number
}

/**
 * Output structure for PromptEnhancerCell
 */
export interface PromptEnhancerOutput {
  /** Enhanced prompt */
  enhancedPrompt: string
  
  /** Original prompt */
  originalPrompt: string
  
  /** Applied enhancements */
  enhancements: string[]
  
  /** Token count estimate */
  estimatedTokens: number
}

/**
 * PromptEnhancerCell - Utility cell for prompt enhancement
 * 
 * This cell demonstrates the utility cell pattern:
 * - No View.vue component (headless execution only)
 * - Implements BaseCell interface
 * - Used as a building block for composed cells
 * - Stateless and deterministic
 * 
 * @example
 * ```typescript
 * const enhancer = new PromptEnhancerCell()
 * 
 * // Use headless
 * const result = await enhancer.execute({
 *   prompt: 'Generate a login form',
 *   mode: 'technical',
 *   audience: 'developer'
 * })
 * 
 * console.log(result.data.enhancedPrompt)
 * // Output: "Create a secure login form component with the following requirements:..."
 * ```
 */
export class PromptEnhancerCell implements BaseCell {
  private isSetup = false

  // ============================================================
  // BaseCell Interface Implementation
  // ============================================================

  /**
   * Execute prompt enhancement
   */
  async execute(input: PromptEnhancerInput): Promise<CellResult> {
    log.debug('Executing prompt enhancement', { mode: input.mode, audience: input.audience })

    try {
      // Validate input
      const errors = this.validate(input)
      if (errors.length > 0) {
        return {
          success: false,
          data: null,
          error: {
            message: 'Validation failed',
            details: errors.map(e => e.message).join('; ')
          },
          metadata: {
            executionTime: 0,
            timestamp: new Date().toISOString()
          }
        }
      }

      const startTime = performance.now()

      // Build enhanced prompt
      const enhancements: string[] = []
      let enhancedPrompt = input.prompt

      // Add context if provided
      if (input.context) {
        enhancedPrompt = `Context: ${input.context}\n\n${enhancedPrompt}`
        enhancements.push('Added context')
      }

      // Apply mode-specific enhancements
      enhancedPrompt = this.applyModeEnhancements(enhancedPrompt, input.mode || 'detailed', enhancements)

      // Apply audience-specific framing
      enhancedPrompt = this.applyAudienceFraming(enhancedPrompt, input.audience || 'general', enhancements)

      // Truncate if maxLength specified
      if (input.maxLength && enhancedPrompt.length > input.maxLength) {
        enhancedPrompt = enhancedPrompt.substring(0, input.maxLength - 3) + '...'
        enhancements.push(`Truncated to ${input.maxLength} characters`)
      }

      const executionTime = performance.now() - startTime

      const output: PromptEnhancerOutput = {
        enhancedPrompt,
        originalPrompt: input.prompt,
        enhancements,
        estimatedTokens: this.estimateTokens(enhancedPrompt)
      }

      log.info('Prompt enhanced successfully', { 
        originalLength: input.prompt.length, 
        enhancedLength: enhancedPrompt.length,
        enhancements: enhancements.length
      })

      return {
        success: true,
        data: output,
        metadata: {
          executionTime,
          timestamp: new Date().toISOString()
        }
      }
    } catch (error: any) {
      log.error('Prompt enhancement failed', error)
      return {
        success: false,
        data: null,
        error: {
          message: error.message || 'Unknown error during prompt enhancement'
        },
        metadata: {
          executionTime: 0,
          timestamp: new Date().toISOString()
        }
      }
    }
  }

  /**
   * Describe cell capabilities
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'prompt-enhancer-cell',
      name: 'Prompt Enhancer',
      version: '1.0.0',
      description: 'Utility cell for enhancing prompts with context and best practices',
      author: 'ScareVerse Team',
      tags: ['utility', 'prompt', 'enhancement', 'headless'],
      inputs: {
        prompt: { type: 'string', required: true, description: 'Original prompt to enhance' },
        context: { type: 'string', required: false, description: 'Optional context' },
        mode: { type: 'string', required: false, description: 'Enhancement mode (concise/detailed/technical/creative)' },
        audience: { type: 'string', required: false, description: 'Target audience (developer/user/ai/general)' },
        maxLength: { type: 'number', required: false, description: 'Maximum prompt length' }
      },
      outputs: {
        enhancedPrompt: { type: 'string', description: 'Enhanced prompt text' },
        originalPrompt: { type: 'string', description: 'Original prompt' },
        enhancements: { type: 'array', description: 'List of applied enhancements' },
        estimatedTokens: { type: 'number', description: 'Estimated token count' }
      },
      capabilities: {
        headless: true,
        composable: true,
        stateless: true,
        cacheable: true
      }
    }
  }

  /**
   * Validate input
   */
  validate(input: PromptEnhancerInput): ValidationError[] {
    const errors: ValidationError[] = []

    if (!input.prompt || typeof input.prompt !== 'string') {
      errors.push({
        field: 'prompt',
        message: 'Prompt is required and must be a string',
        code: 'INVALID_PROMPT'
      })
    }

    if (input.prompt && input.prompt.length === 0) {
      errors.push({
        field: 'prompt',
        message: 'Prompt cannot be empty',
        code: 'EMPTY_PROMPT'
      })
    }

    if (input.mode && !['concise', 'detailed', 'technical', 'creative'].includes(input.mode)) {
      errors.push({
        field: 'mode',
        message: 'Mode must be one of: concise, detailed, technical, creative',
        code: 'INVALID_MODE'
      })
    }

    if (input.audience && !['developer', 'user', 'ai', 'general'].includes(input.audience)) {
      errors.push({
        field: 'audience',
        message: 'Audience must be one of: developer, user, ai, general',
        code: 'INVALID_AUDIENCE'
      })
    }

    if (input.maxLength !== undefined && (typeof input.maxLength !== 'number' || input.maxLength <= 0)) {
      errors.push({
        field: 'maxLength',
        message: 'maxLength must be a positive number',
        code: 'INVALID_MAX_LENGTH'
      })
    }

    return errors
  }

  /**
   * Setup (no-op for stateless utility cell)
   */
  async setup(_config: EnvironmentConfig): Promise<void> {
    log.debug('Setup called (no-op for utility cell)')
    this.isSetup = true
  }

  /**
   * Teardown (no-op for stateless utility cell)
   */
  async teardown(): Promise<void> {
    log.debug('Teardown called (no-op for utility cell)')
    this.isSetup = false
  }

  /**
   * Health check
   */
  async health_check(): Promise<HealthCheckResult> {
    return {
      status: 'healthy',
      can_execute: true,
      message: 'Utility cell is always healthy (stateless)'
    }
  }

  // ============================================================
  // Private Helper Methods
  // ============================================================

  /**
   * Apply mode-specific enhancements
   */
  private applyModeEnhancements(prompt: string, mode: string, enhancements: string[]): string {
    switch (mode) {
      case 'concise':
        enhancements.push('Applied concise mode')
        return `Brief request: ${prompt}`

      case 'detailed':
        enhancements.push('Applied detailed mode')
        return `Detailed request with full context:\n\n${prompt}\n\nPlease provide a comprehensive response with examples and explanations.`

      case 'technical':
        enhancements.push('Applied technical mode')
        return `Technical specification:\n\n${prompt}\n\nRequirements:\n- Follow best practices\n- Include error handling\n- Provide type safety\n- Document assumptions`

      case 'creative':
        enhancements.push('Applied creative mode')
        return `Creative exploration:\n\n${prompt}\n\nFeel free to think outside the box and suggest innovative approaches.`

      default:
        return prompt
    }
  }

  /**
   * Apply audience-specific framing
   */
  private applyAudienceFraming(prompt: string, audience: string, enhancements: string[]): string {
    const audienceFrames = {
      developer: 'As a developer, ',
      user: 'From a user perspective, ',
      ai: 'For AI processing: ',
      general: ''
    }

    const frame = audienceFrames[audience as keyof typeof audienceFrames] || audienceFrames.general

    if (frame) {
      enhancements.push(`Added ${audience} framing`)
      return frame + prompt
    }

    return prompt
  }

  /**
   * Estimate token count (rough approximation)
   */
  private estimateTokens(text: string): number {
    // Rough estimation: ~4 characters per token on average
    return Math.ceil(text.length / 4)
  }
}
