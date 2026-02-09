/**
 * @file SvgGeneratorCell.ts
 * @description SvgGeneratorCell - BaseCell implementation for AI-powered SVG generation
 * 
 * This cell generates SVG visualizations from text prompts using LLM services.
 * It implements the BaseCell interface for headless execution and composability.
 * 
 * Part of BaseCell v1.0 Framework Implementation
 * Category: visualization
 */

import type { 
  BaseCell, 
  CellResult, 
  CellMetadata, 
  ValidationError, 
  HealthCheckResult 
} from '@/types/BaseCell'
import { processMessage, fetchAvailableModels } from '@/services/aiChatService'

/**
 * SVG Generator input interface
 */
export interface SvgGeneratorInput {
  /** Text description of the desired SVG visualization */
  prompt: string
  
  /** LLM model to use for generation (default: 'mistral') */
  model?: string
  
  /** Temperature for generation (0.0-1.0, default: 0.7) */
  temperature?: number
  
  /** Maximum tokens for generation (default: 2000) */
  maxTokens?: number
}

/**
 * SVG Generator output interface
 */
export interface SvgGeneratorOutput {
  /** Generated SVG code */
  svg: string
  
  /** Original prompt */
  prompt: string
  
  /** Model used for generation */
  model: string
  
  /** Whether fallback SVG was used */
  fallback?: boolean
}

/**
 * Minimal fallback SVG (red circle) for when LLM service is unavailable
 */
const MINIMAL_FALLBACK_SVG = `<svg viewBox="0 0 100 100" width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="40" fill="red"/>
</svg>`

/**
 * SvgGeneratorCell - BaseCell implementation for SVG generation
 * 
 * Demonstrates BaseCell interface with:
 * - LLM integration for SVG generation
 * - Input validation (prompt requirements)
 * - Health checking (LLM service availability)
 * - Fallback mechanism for service failures
 * - Model selection support
 * 
 * Perfect for:
 * - Generating custom visualizations from text
 * - Creating dynamic graphics in workflows
 * - Prototyping UI elements
 * 
 * @example
 * ```typescript
 * const svgCell = new SvgGeneratorCell()
 * 
 * // Execute headless
 * const result = await svgCell.execute({
 *   prompt: 'A blue circle with radius 50',
 *   model: 'mistral'
 * })
 * // => { success: true, output: { svg: '<svg>...</svg>', ... }, execution_time: 2500 }
 * 
 * // Validate before execute
 * const errors = svgCell.validate({ prompt: '' })
 * // => [{ field: 'prompt', message: 'Prompt is required' }]
 * ```
 */
export class SvgGeneratorCell implements BaseCell {
  /**
   * Execute SVG generation from text prompt
   * 
   * Calls LLM service to generate SVG code. Falls back to placeholder
   * if service is unavailable or generation fails.
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()
    
    try {
      // Validate input
      const errors = this.validate(input)
      if (errors.length > 0) {
        return {
          success: false,
          output: { errors },
          execution_time: performance.now() - startTime,
          error: 'Validation failed'
        }
      }
      
      const { 
        prompt, 
        model = 'mistral', 
        temperature = 0.7,
        maxTokens = 2000 
      } = input as SvgGeneratorInput
      
      // Create specialized prompt for SVG generation
      const svgPrompt = `Generate a clean, valid SVG visualization based on this description: "${prompt}"

IMPORTANT: Return ONLY the SVG code, no explanations. Start with <svg> and end with </svg>.
Include proper viewBox and dimensions. Keep it simple and readable.`
      
      try {
        // Call LLM service
        const response = await processMessage({
          intention: svgPrompt,
          assignee_id: '', // Backend uses authenticated user from JWT token
          history: [],
          model,
          classifyIntention: false,
          attachments: [],
          thread_id: '',
          assistant_id: '',
          selected_collections: [],
          conversation_id: '',
        })
        
        // Extract SVG from response
        const content = (response as any).message || (response as any).response || ''
        
        // Try to extract SVG (handle code blocks or direct SVG)
        let extractedSvg = content
        const svgMatch = content.match(/```(?:svg|xml)?\s*\n?([\s\S]*?)\n?```/) || 
                         content.match(/<svg[\s\S]*?<\/svg>/i)
        
        if (svgMatch) {
          extractedSvg = svgMatch[1] || svgMatch[0]
        }
        
        // Validate that we have SVG
        if (!extractedSvg.trim().startsWith('<svg')) {
          throw new Error('Generated content is not valid SVG')
        }
        
        const output: SvgGeneratorOutput = {
          svg: extractedSvg.trim(),
          prompt,
          model
        }
        
        const executionTime = performance.now() - startTime
        
        return {
          success: true,
          output,
          execution_time: executionTime,
          execution_steps: ['validate', 'generate_prompt', 'call_llm', 'extract_svg'],
          metadata: {
            model,
            prompt_length: prompt.length,
            svg_length: output.svg.length
          }
        }
      } catch (llmError: any) {
        // LLM service failed, use fallback
        console.warn('[SvgGeneratorCell] LLM service failed, using fallback:', llmError.message)
        
        const output: SvgGeneratorOutput = {
          svg: MINIMAL_FALLBACK_SVG,
          prompt,
          model,
          fallback: true
        }
        
        return {
          success: true,
          output,
          execution_time: performance.now() - startTime,
          execution_steps: ['validate', 'generate_prompt', 'call_llm_failed', 'use_fallback'],
          metadata: {
            model,
            prompt_length: prompt.length,
            fallback_reason: llmError.message
          }
        }
      }
    } catch (error: any) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: error.message || 'SVG generation failed'
      }
    }
  }
  
  /**
   * Describe SVG generator capabilities
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'svg-generator-cell',
      name: 'SVG Generator Cell',
      version: '1.0.0',
      description: 'Interactive cell for generating SVG visualizations from text prompts using AI. Supports multiple LLM models and includes fallback mechanism.',
      inputs: {
        prompt: {
          type: 'string',
          description: 'Text description of the desired SVG visualization',
          required: true
        },
        model: {
          type: 'string',
          description: 'LLM model to use for generation',
          required: false,
          default: 'mistral'
        },
        temperature: {
          type: 'number',
          description: 'Temperature for generation (0.0-1.0)',
          required: false,
          default: 0.7
        },
        maxTokens: {
          type: 'number',
          description: 'Maximum tokens for generation',
          required: false,
          default: 2000
        }
      },
      outputs: {
        svg: {
          type: 'string',
          description: 'Generated SVG code'
        },
        prompt: {
          type: 'string',
          description: 'Original prompt used for generation'
        },
        model: {
          type: 'string',
          description: 'Model used for generation'
        },
        fallback: {
          type: 'boolean',
          description: 'Whether fallback SVG was used',
          optional: true
        }
      },
      tags: ['visualization', 'svg', 'ai', 'generation', 'graphics'],
      estimated_duration_seconds: 3, // Average 2-5 seconds for LLM
      required_resources: ['llm-service'] // Depends on LLM service
    }
  }
  
  /**
   * Validate SVG generator input
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    
    // Check required fields
    if (!input.prompt) {
      errors.push({ field: 'prompt', message: 'Prompt is required' })
    } else if (typeof input.prompt !== 'string') {
      errors.push({ field: 'prompt', message: 'Prompt must be a string' })
    } else if (input.prompt.trim().length === 0) {
      errors.push({ field: 'prompt', message: 'Prompt cannot be empty' })
    } else if (input.prompt.length > 5000) {
      errors.push({ field: 'prompt', message: 'Prompt is too long (max 5000 characters)' })
    }
    
    // Validate optional fields
    if (input.model !== undefined && typeof input.model !== 'string') {
      errors.push({ field: 'model', message: 'Model must be a string' })
    }
    
    if (input.temperature !== undefined) {
      if (typeof input.temperature !== 'number' || input.temperature < 0 || input.temperature > 1) {
        errors.push({ field: 'temperature', message: 'Temperature must be a number between 0 and 1' })
      }
    }
    
    if (input.maxTokens !== undefined) {
      if (typeof input.maxTokens !== 'number' || input.maxTokens < 100 || input.maxTokens > 10000) {
        errors.push({ field: 'maxTokens', message: 'Max tokens must be a number between 100 and 10000' })
      }
    }
    
    return errors
  }
  
  /**
   * Health check - Verify LLM service availability
   */
  async health_check(): Promise<HealthCheckResult> {
    try {
      // Try to fetch available models to verify service is up
      const models = await fetchAvailableModels()
      
      if (models && models.length > 0) {
        return {
          status: 'healthy',
          can_execute: true,
          reason: `LLM service available with ${models.length} models`
        }
      } else {
        return {
          status: 'degraded',
          can_execute: true,
          reason: 'LLM service available but no models found. Will use fallback.'
        }
      }
    } catch (error: any) {
      return {
        status: 'degraded',
        can_execute: true,
        reason: `LLM service unavailable: ${error.message}. Will use fallback SVG.`
      }
    }
  }
}
