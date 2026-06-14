/**
 * @file PngGeneratorCell.ts
 * @description PngGeneratorCell - BaseCell implementation for PNG generation
 * 
 * This cell implements text-to-image generation and background removal operations
 * via backend integration. It delegates execution to the `/api/cells/execute-ephemeral`
 * endpoint, supporting both 'generate' and 'removeBackground' actions.
 * 
 * Part of BaseCell v1.0 Framework Implementation
 * Task: [PNG-FE-001] Create PngGeneratorCell TypeScript Implementation
 */

import { BaseCell, createHealthyResult } from '@/types/BaseCell'
import type { CellResult, CellMetadata, ValidationError, EnvironmentConfig, HealthCheckResult, ShowConfig } from '@/types/BaseCell'
import apiService from '@/services/apiService.js'
import { ENDPOINTS } from '@/config/endpoints.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:PngGenerator')

/**
 * Supported PNG generation actions
 */
export type PngGeneratorAction = 'generate' | 'removeBackground'

/**
 * Generation parameters for text-to-image
 */
export interface GenerationParams {
  /** Image width in pixels */
  width?: number
  
  /** Image height in pixels */
  height?: number
  
  /** Number of diffusion steps */
  steps?: number
  
  /** CFG scale (guidance strength) */
  cfg_scale?: number
  
  /** Random seed for reproducibility */
  seed?: number
}

/**
 * PngGeneratorCell input interface
 */
export interface PngGeneratorInput {
  /** Action to perform */
  action: PngGeneratorAction
  
  /** Text prompt for image generation (required for 'generate' action) */
  prompt?: string
  
  /** Base64-encoded PNG for background removal (required for 'removeBackground' action) */
  generatedPng?: string
  
  /** Generation parameters (optional, for 'generate' action) */
  generationParams?: GenerationParams
  
  /** Negative prompt to exclude unwanted features */
  negativePrompt?: string
  
  /** Enable 3D asset mode (optimized for 3D workflows) */
  asset3dMode?: boolean
  
  /** Enable alpha matting for better edge quality (for 'removeBackground' action) */
  alpha_matting?: boolean
}

/**
 * PngGeneratorCell output interface
 */
export interface PngGeneratorOutput {
  /** Whether execution was successful */
  success: boolean

  /** Base64-encoded generated/processed PNG (legacy inline format) */
  generatedPng?: string

  /** Content reference URL for Redis Magro mode (e.g. /artifacts/runtime/user/.../file.png) */
  relative_url?: string

  /** Content identifier when using Redis Magro mode */
  content_id?: string

  /** Whether PNG data is available */
  has_png?: boolean
  
  /** Original or processed prompt */
  prompt?: string
  
  /** Success message */
  message?: string
  
  /** Error message if failed */
  error?: string
  
  /** Additional metadata from backend */
  metadata?: Record<string, any>

  /** ASYNC FLOW (v6.0): Job ID for frontend polling */
  job_id?: string
  /** ASYNC FLOW (v6.0): Job status (queued, processing, success, failed) */
  status?: string
}

/**
 * PngGeneratorCell - Backend-integrated BaseCell for PNG operations
 * 
 * Capabilities:
 * - Text-to-image generation via Stable Diffusion
 * - Background removal via rembg
 * - Configurable generation parameters
 * - 3D asset optimization mode
 * - Backend health checking
 * 
 * Execution Model:
 * - Delegates to backend via HTTP POST to /api/cells/execute-ephemeral
 * - Cell type: 'pnggenerator'
 * - Supports both 'generate' and 'removeBackground' actions
 * 
 * @example
 * ```typescript
 * const pngGen = new PngGeneratorCell()
 * 
 * // Generate image from text
 * const result = await pngGen.execute({
 *   action: 'generate',
 *   prompt: 'A majestic lion in a savanna',
 *   generationParams: {
 *     width: 512,
 *     height: 512,
 *     steps: 30,
 *     cfg_scale: 7.5
 *   }
 * })
 * 
 * // Remove background
 * const bgRemoved = await pngGen.execute({
 *   action: 'removeBackground',
 *   generatedPng: '<base64-png-data>',
 *   alpha_matting: true
 * })
 * ```
 */
export class PngGeneratorCell extends BaseCell {
  private _isSetup: boolean = false
  
  /**
   * Execute PNG generation or background removal
   * 
   * Delegates to backend via /api/cells/execute-ephemeral endpoint.
   * Returns CellResult with PNG data or error information.
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()
    
    try {
      log.debug('Executing PngGeneratorCell', { action: input.action })
      
      // Validate input
      const errors = this.validate(input)
      if (errors.length > 0) {
        log.warn('Validation failed', { errors })
        return {
          success: false,
          output: { 
            success: false,
            errors,
            error: 'Validation failed'
          },
          execution_time: performance.now() - startTime,
          error: 'Validation failed'
        }
      }
      
      // Prepare backend request payload
      const payload = {
        cell_type: 'png-generator-cell',
        input_data: input
      }
      
      log.debug('Sending request to backend', { 
        endpoint: ENDPOINTS.executeEphemeralCell,
        action: input.action 
      })
      
      // Call backend API
      const response = await apiService.fetch(
        ENDPOINTS.executeEphemeralCell,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        }
      ) as Response
      
      if (!response.ok) {
        const errorText = await response.text()
        log.error('Backend request failed', {
          status: response.status,
          statusText: response.statusText,
          errorText
        })
        throw new Error(`Backend execution failed: ${response.statusText}`)
      }

      const responseData = await response.json() as any
      // Extract the result field if it exists (API wraps response in 'result' field)
      const result = (responseData.result || responseData) as PngGeneratorOutput

      // ======================================================================
      // REDIS MAGRO (Content Reference): If the backend returned a relative_url
      // instead of inline base64, convert it to a full URL for the <img> tag.
      //
      // The Runtime File Server serves files at:
      //   {origin}/artifacts/runtime/user/{assignee}/contents/{id}/{file}
      //
      // We also set generatedPng from the URL for backward compatibility with
      // View.vue which uses localGeneratedPng for both data-URI and HTTP URLs.
      // ======================================================================
      if (result.relative_url) {
        log.info('REDIS MAGRO: Converting relative_url to full URL', {
          relative_url: result.relative_url
        })
        // Build the full URL from the current origin
        // FIX: Prepend /artifacts so the URL routes through auth-proxy's
        // RuntimeFileServer which provides CORS headers for cross-origin downloads.
        // Without this prefix, the URL goes directly to the runtime file server
        // which does not set CORS headers → FILE_DOWNLOAD fails with CORS error.
        // See DEBUG_FLOW_ANALYSIS_6.md for full chain analysis.
        const origin = window.location.origin.replace(/\/+$/, '')
        result.generatedPng = `${origin}/artifacts${result.relative_url}`
      }

      const executionTime = performance.now() - startTime

      // ASYNC FLOW (v6.0): Backend returned { job_id, status } — pass through
      if (result.job_id) {
        log.info('Async job created', {
          jobId: result.job_id,
          status: result.status,
          executionTime,
        })
        return {
          success: true,
          output: result,
          artifacts: [],
          execution_time: executionTime,
          execution_steps: ['validate', 'prepare-request', 'backend-execute', 'job-queued'],
          quality_score: 1.0,
        }
      }

      log.info('Execution completed', {
        success: result.success,
        hasPng: result.has_png,
        relativeUrl: result.relative_url || null,
        executionTime
      })

      // Map backend response to CellResult
      // artifacts: use generatedPng (now either data-URI or full URL) for preview
      return {
        success: result.success,
        output: result,
        artifacts: result.generatedPng ? [result.generatedPng] : [],
        execution_time: executionTime,
        execution_steps: ['validate', 'prepare-request', 'backend-execute', 'process-response'],
        quality_score: result.success ? 1.0 : 0.0,
        error: result.error,
        metadata: result.metadata
      }
    } catch (error: any) {
      log.error('Execution failed with exception', error)
      return {
        success: false,
        output: {
          success: false,
          error: error.message || 'Unknown error'
        },
        execution_time: performance.now() - startTime,
        error: error.message || 'Execution failed'
      }
    }
  }
  
  /**
   * Describe PngGeneratorCell capabilities
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'png-generator-cell',
      name: 'PNG Generator Cell',
      version: '1.0.0',
      description: 'Generate images from text prompts using Stable Diffusion or remove backgrounds from existing images using rembg.',
      inputs: {
        action: {
          type: 'string',
          description: 'Action to perform',
          required: true,
          enum: ['generate', 'removeBackground']
        },
        prompt: {
          type: 'string',
          description: 'Text prompt for image generation',
          required: false,
          note: 'Required for "generate" action'
        },
        generatedPng: {
          type: 'string',
          description: 'Base64-encoded PNG for background removal',
          required: false,
          note: 'Required for "removeBackground" action'
        },
        generationParams: {
          type: 'object',
          description: 'Generation parameters (width, height, steps, cfg_scale, seed)',
          required: false,
          properties: {
            width: { type: 'number', default: 512 },
            height: { type: 'number', default: 512 },
            steps: { type: 'number', default: 30 },
            cfg_scale: { type: 'number', default: 7.5 },
            seed: { type: 'number', default: null }
          }
        },
        negativePrompt: {
          type: 'string',
          description: 'Negative prompt to exclude unwanted features',
          required: false
        },
        asset3dMode: {
          type: 'boolean',
          description: 'Enable 3D asset mode',
          required: false,
          default: false
        },
        alpha_matting: {
          type: 'boolean',
          description: 'Enable alpha matting for better edge quality',
          required: false,
          default: false
        }
      },
      outputs: {
        success: {
          type: 'boolean',
          description: 'Whether execution was successful'
        },
        generatedPng: {
          type: 'string',
          description: 'Base64-encoded generated/processed PNG'
        },
        has_png: {
          type: 'boolean',
          description: 'Whether PNG data is available'
        },
        prompt: {
          type: 'string',
          description: 'Original or processed prompt'
        },
        message: {
          type: 'string',
          description: 'Success message'
        },
        error: {
          type: 'string',
          description: 'Error message if failed'
        },
        metadata: {
          type: 'object',
          description: 'Additional metadata from backend'
        }
      },
      tags: ['image-generation', 'stable-diffusion', 'background-removal', 'rembg', 'backend-integrated'],
      estimated_duration_seconds: 30, // ~30 seconds for image generation
      required_resources: ['backend', 'gpu', 'internet']
    }
  }
  
  /**
   * Validate PngGeneratorCell input
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    
    // Check required action field
    if (!input.action) {
      errors.push({ field: 'action', message: 'Action is required' })
      return errors // Early return if action is missing
    }
    
    const validActions: PngGeneratorAction[] = ['generate', 'removeBackground']
    if (!validActions.includes(input.action as PngGeneratorAction)) {
      errors.push({
        field: 'action',
        message: `Action must be one of: ${validActions.join(', ')}`
      })
      return errors // Early return if action is invalid
    }
    
    // Action-specific validation
    if (input.action === 'generate') {
      if (!input.prompt || typeof input.prompt !== 'string' || input.prompt.trim().length === 0) {
        errors.push({ field: 'prompt', message: 'Prompt is required for "generate" action' })
      }
      
      // Validate generation parameters if provided
      if (input.generationParams) {
        const params = input.generationParams as GenerationParams
        
        if (params.width !== undefined && (params.width < 128 || params.width > 2048)) {
          errors.push({ field: 'generationParams.width', message: 'Width must be between 128 and 2048 pixels' })
        }
        
        if (params.height !== undefined && (params.height < 128 || params.height > 2048)) {
          errors.push({ field: 'generationParams.height', message: 'Height must be between 128 and 2048 pixels' })
        }
        
        if (params.steps !== undefined && (params.steps < 1 || params.steps > 100)) {
          errors.push({ field: 'generationParams.steps', message: 'Steps must be between 1 and 100' })
        }
        
        if (params.cfg_scale !== undefined && (params.cfg_scale < 1 || params.cfg_scale > 20)) {
          errors.push({ field: 'generationParams.cfg_scale', message: 'CFG scale must be between 1 and 20' })
        }
      }
    }
    
    if (input.action === 'removeBackground') {
      if (!input.generatedPng || typeof input.generatedPng !== 'string' || input.generatedPng.trim().length === 0) {
        errors.push({ field: 'generatedPng', message: 'Base64-encoded PNG is required for "removeBackground" action' })
      }
    }
    
    return errors
  }
  
  /**
   * Setup (optional) - PngGeneratorCell needs no initialization
   */
  async setup(config: EnvironmentConfig): Promise<void> {
    log.debug('Setup called', { config })
    this._isSetup = true
  }
  
  /**
   * Teardown (optional) - PngGeneratorCell needs no cleanup
   */
  async teardown(): Promise<void> {
    log.debug('Teardown called')
    this._isSetup = false
  }
  
  /**
   * Health check (optional) - Check backend availability
   * 
   * Performs a lightweight check to verify that the backend is reachable.
   * Returns 'degraded' if backend is unreachable, 'healthy' otherwise.
   */
  async health_check(): Promise<HealthCheckResult> {
    try {
      log.debug('Performing health check')
      
      // Check if backend is reachable by calling the lightweight health endpoint
      // (public endpoint: no auth required, no DB scan, fast ping-only check)
      const response = await apiService.fetch('/api/health') as Response
      
      if (!response.ok) {
        log.warn('Backend health check failed', { status: response.status })
        return {
          status: 'degraded',
          can_execute: false,
          reason: 'Backend is unreachable or unhealthy',
          estimated_recovery_seconds: 60
        }
      }
      
      log.debug('Health check passed')
      return createHealthyResult()
    } catch (error: any) {
      log.error('Health check failed with exception', error)
      return {
        status: 'unavailable',
        can_execute: false,
        reason: `Backend unreachable: ${error.message}`,
        estimated_recovery_seconds: 120
      }
    }
  }
  
  /**
   * Show (optional) - Render or interact with cell UI
   * 
   * Supports modal persistence integration for saving generated assets.
   * When called with { modal: 'persist' }, routes to ContentManagerCell
   * for persistent asset storage.
   * 
   * @param data - Data to show/persist (asset data from execute result)
   * @param options - Show configuration options
   */
  async show(
    data: Record<string, any>,
    options: ShowConfig
  ): Promise<void> {
    // PERMANENTE: Confirm if show() is actually executed in the real flow
    // (suspected dead code -- never called; real persistence goes via
    // PersistModal.handlePersist() -> ContentManagerCell.execute() directly)
    log.warn('PngGeneratorCell-PERMANENTE: show() WAS EXECUTED. If this log appears, '
      + 'show() is NOT dead code. Remove this warning after confirming.',
      { dataKeys: Object.keys(data), options })
    const startTime = performance.now()
    
    try {
      log.debug('Show method called', { options })
      
      // Check for persist modal option (custom extension of ShowConfig)
      const modal = (options as any).modal
      
      if (modal === 'persist') {
        // Route to ContentManagerCell for persistence with modal
        await this.persistAssetWithModal(data)
        return
      }
      
      // Standard preview rendering (no-op in headless mode)
      log.debug('Show completed', {
        mode: options?.mode || 'preview',
        execution_time: performance.now() - startTime
      })
    } catch (error: any) {
      log.error('Show failed with exception', error)
      throw error
    }
  }
  
  /**
   * Persist asset with modal using ContentManagerCell
   * 
   * Opens a modal dialog (via ContentManagerCell) that allows the user
   * to name, tag, and save the generated asset to persistent storage.
   * 
   * @param assetData - Asset data from execute result
   */
  private async persistAssetWithModal(
    assetData: Record<string, any>
  ): Promise<void> {
    const startTime = performance.now()
    
    try {
      log.debug('Persisting asset with modal', { assetData })
      
      // Dynamically import ContentManagerCell to avoid circular dependencies
      const { ContentManagerCell } = await import(
        '#artifacts/canonical/cell_types/content-manager-cell/frontend/ContentManagerCell'
      )
      
      const contentManager = new ContentManagerCell()
      
      // Call ContentManagerCell.show() with persist modal option
      await contentManager.show(
        {
          action: 'persist',
          content_type_id: 'image-png',
          binary: assetData.generatedPng || assetData.image_data,
          metadata: {
            width: assetData.width,
            height: assetData.height,
            file_size: assetData.file_size,
            generation_timestamp: assetData.timestamp || Date.now(),
            generation_params: assetData.generation_params || assetData.generationParams,
            prompt: assetData.prompt
          }
        },
        { modal: 'persist-with-naming' } as any
      )
      
      log.info('Asset persistence completed', {
        execution_time: performance.now() - startTime
      })
    } catch (error: any) {
      log.error('Asset persistence failed', error)
      throw error
    }
  }
}
