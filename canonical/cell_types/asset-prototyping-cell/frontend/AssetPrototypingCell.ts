/**
 * @file AssetPrototypingCell.ts
 * @description AssetPrototypingCell - Composed BaseCell implementation
 * 
 * ⚠️ DEPRECATED: This cell is maintained for backward compatibility only.
 * New code should use AssetPrototypingBook instead.
 * 
 * Migration: Replace with AssetPrototypingBook from
 * artifacts/canonical/book_types/asset-prototyping-book/frontend/AssetPrototypingBook.ts
 * 
 * Reason: This cell violates the Single Responsibility Principle by acting
 * as an orchestrator (Book pattern) rather than an atomic executor (Cell pattern).
 * The orchestration logic has been moved to AssetPrototypingBook, which properly
 * separates concerns and enables better reusability and testability.
 * 
 * This cell demonstrates cell composition by orchestrating PNG generation
 * and 3D mesh prototyping cells to create complete 3D assets from text prompts.
 * 
 * Part of BaseCell v1.0 Framework Implementation - Phase 2: Composition
 * Task: [ASSET-001] Implement AssetPrototypingCell
 * Superseded by: BaseBook v1.0 - AssetPrototypingBook
 * 
 * Note: File is 554 lines (slightly over 500-line guideline).
 * Justification: Complete cell implementation with comprehensive documentation,
 * error handling, and lifecycle management. Splitting would reduce cohesion.
 */

import { BaseCell, createHealthyResult } from '@/types/BaseCell'
import type { CellResult, CellMetadata, ValidationError, EnvironmentConfig, HealthCheckResult } from '@/types/BaseCell'
import { PngGeneratorCell } from '#canonical/cell_types/png-generator-cell/frontend/PngGeneratorCell'
import { MeshPrototypingCell } from '#canonical/cell_types/3d-mesh-prototyping-cell/frontend/MeshPrototypingCell'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:AssetPrototyping')

/**
 * Asset prototyping pipeline steps
 */
export type AssetPipelineStep = 'generate_texture' | 'generate_mesh' | 'combine_asset'

/**
 * AssetPrototypingCell input interface
 */
export interface AssetPrototypingInput {
  /** Text prompt describing the asset to generate */
  prompt: string
  
  /** Optional negative prompt to exclude unwanted features */
  negativePrompt?: string
  
  /** Enable 3D asset mode for PNG generation */
  asset3dMode?: boolean
  
  /** Mesh reconstruction parameters */
  reconstructionParams?: {
    targetFaces?: number
    enableDracoCompression?: boolean
    compressionLevel?: number
  }
  
  /** Generation mode for mesh creation */
  generationMode?: 'cloud-api' | 'local-gpu' | 'manual-upload'
}

/**
 * AssetPrototypingCell output interface
 */
export interface AssetPrototypingOutput {
  /** Whether execution was successful */
  success: boolean
  
  /** Base64-encoded generated texture PNG */
  texturePng?: string
  
  /** URL to download the generated GLB file */
  meshGlbUrl?: string
  
  /** Job ID for async processing (local-gpu mode) */
  jobId?: string
  
  /** Pipeline execution steps completed */
  stepsCompleted: AssetPipelineStep[]
  
  /** Success message */
  message?: string
  
  /** Error message if failed */
  error?: string
  
  /** Execution metadata */
  metadata?: {
    textureGenTime?: number
    meshGenTime?: number
    totalTime?: number
    prompt?: string
  }
}

/**
 * AssetPrototypingCell - Composed BaseCell for complete asset creation
 * 
 * ⚠️ DEPRECATED: Use AssetPrototypingBook instead
 * @deprecated This cell acts as an orchestrator, which violates the Cell pattern.
 *             Use AssetPrototypingBook from book_types/asset-prototyping-book instead.
 * 
 * This cell demonstrates the power of composition in the BaseCell framework.
 * It orchestrates two specialized cells (PngGeneratorCell and MeshPrototypingCell)
 * to create a complete 3D asset from a text prompt.
 * 
 * Composition Pattern:
 * 1. Instantiate sub-cells (PngGeneratorCell, MeshPrototypingCell)
 * 2. Execute sub-cells in sequence
 * 3. Coordinate lifecycle (setup/teardown) across all cells
 * 4. Aggregate results into unified output
 * 
 * Execution Flow:
 * - Step 1: Generate texture using PngGeneratorCell
 * - Step 2: Generate mesh using MeshPrototypingCell with the texture
 * - Step 3: Combine results into complete asset
 * 
 * @example
 * ```typescript
 * const assetCell = new AssetPrototypingCell()
 * await assetCell.setup({ headless_mode: true })
 * 
 * const result = await assetCell.execute({
 *   prompt: 'a fantasy sword with ornate handle',
 *   asset3dMode: true,
 *   generationMode: 'cloud-api'
 * })
 * 
 * console.log(result.output.texturePng) // Base64 PNG
 * console.log(result.output.meshGlbUrl) // URL to GLB file
 * 
 * await assetCell.teardown()
 * ```
 */
export class AssetPrototypingCell extends BaseCell {
  private pngCell: PngGeneratorCell
  private meshCell: MeshPrototypingCell
  private _isSetup: boolean = false
  
  constructor() {
    super()
    // Instantiate sub-cells
    this.pngCell = new PngGeneratorCell()
    this.meshCell = new MeshPrototypingCell()
    
    log.debug('AssetPrototypingCell instantiated with sub-cells', {
      pngCell: 'PngGeneratorCell',
      meshCell: 'MeshPrototypingCell'
    })
  }
  
  /**
   * Execute complete asset prototyping pipeline
   * 
   * Orchestrates PNG generation and mesh prototyping to create a complete 3D asset.
   * This demonstrates headless composition where multiple cells work together
   * without UI intervention.
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()
    const stepsCompleted: AssetPipelineStep[] = []
    
    try {
      // Validate input
      const errors = this.validate(input)
      if (errors.length > 0) {
        return {
          success: false,
          output: { stepsCompleted },
          execution_time: performance.now() - startTime,
          error: `Validation failed: ${errors.map(e => `${e.field}: ${e.message}`).join(', ')}`
        }
      }
      
      const {
        prompt,
        negativePrompt,
        asset3dMode = true,
        reconstructionParams,
        generationMode = 'cloud-api'
      } = input as AssetPrototypingInput
      
      log.info('Starting asset prototyping pipeline', { prompt, generationMode })
      
      // ===== STEP 1: Generate Texture PNG =====
      const textureStartTime = performance.now()
      log.debug('Step 1: Generating texture PNG')
      
      const pngResult = await this.pngCell.execute({
        action: 'generate',
        prompt,
        negativePrompt,
        asset3dMode
      })
      
      if (!pngResult.success) {
        log.error('Texture generation failed', { error: pngResult.error })
        return {
          success: false,
          output: { stepsCompleted },
          execution_time: performance.now() - startTime,
          error: `Texture generation failed: ${pngResult.error}`
        }
      }
      
      stepsCompleted.push('generate_texture')
      const textureGenTime = performance.now() - textureStartTime
      
      const texturePng = pngResult.output.generatedPng
      if (!texturePng) {
        return {
          success: false,
          output: { stepsCompleted },
          execution_time: performance.now() - startTime,
          error: 'No texture PNG generated'
        }
      }
      
      log.debug('Texture generated successfully', { 
        executionTime: textureGenTime 
      })
      
      // ===== STEP 2: Generate 3D Mesh =====
      const meshStartTime = performance.now()
      log.debug('Step 2: Generating 3D mesh from texture')
      
      const meshResult = await this.meshCell.execute({
        inputImage: texturePng,
        reconstructionParams,
        generationMode
      })
      
      if (!meshResult.success) {
        log.error('Mesh generation failed', { error: meshResult.error })
        // Partial success: we have texture but no mesh
        return {
          success: false,
          output: {
            texturePng,
            stepsCompleted,
            error: meshResult.error
          },
          execution_time: performance.now() - startTime,
          error: `Mesh generation failed: ${meshResult.error}`
        }
      }
      
      stepsCompleted.push('generate_mesh')
      const meshGenTime = performance.now() - meshStartTime
      
      log.debug('Mesh generated successfully', {
        executionTime: meshGenTime,
        glbUrl: meshResult.output.glb_url,
        jobId: meshResult.output.job_id
      })
      
      // ===== STEP 3: Combine Asset =====
      stepsCompleted.push('combine_asset')
      
      const totalTime = performance.now() - startTime
      
      const output: AssetPrototypingOutput = {
        success: true,
        texturePng,
        meshGlbUrl: meshResult.output.glb_url,
        jobId: meshResult.output.job_id,
        stepsCompleted,
        message: 'Asset prototyping completed successfully',
        metadata: {
          textureGenTime,
          meshGenTime,
          totalTime,
          prompt
        }
      }
      
      log.info('Asset prototyping pipeline completed', {
        totalTime,
        stepsCompleted,
        hasTexture: !!output.texturePng,
        hasMesh: !!output.meshGlbUrl
      })
      
      return {
        success: true,
        output,
        execution_time: totalTime,
        execution_steps: stepsCompleted,
        quality_score: 1.0,
        metadata: {
          prompt,
          textureGenTime,
          meshGenTime,
          generationMode
        }
      }
    } catch (error: any) {
      log.error('Asset prototyping pipeline failed', error)
      return {
        success: false,
        output: { stepsCompleted },
        execution_time: performance.now() - startTime,
        error: error.message || 'Asset prototyping failed'
      }
    }
  }
  
  /**
   * Describe asset prototyping capabilities
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'asset-prototyping-cell',
      name: 'Asset Prototyping Cell',
      version: '1.0.0',
      description: 'Complete 3D asset prototyping pipeline. Composes PNG generation and mesh prototyping to create textured 3D assets from text prompts.',
      inputs: {
        prompt: {
          type: 'string',
          description: 'Text description of the asset to generate',
          required: true,
          example: 'a fantasy sword with ornate handle'
        },
        negativePrompt: {
          type: 'string',
          description: 'Features to exclude from generation',
          required: false,
          example: 'blurry, low quality'
        },
        asset3dMode: {
          type: 'boolean',
          description: 'Enable 3D asset optimization mode',
          required: false,
          default: true
        },
        reconstructionParams: {
          type: 'object',
          description: 'Mesh reconstruction parameters',
          required: false,
          properties: {
            targetFaces: { type: 'number', description: 'Target face count for mesh' },
            enableDracoCompression: { type: 'boolean', description: 'Enable Draco compression' },
            compressionLevel: { type: 'number', description: 'Compression level (0-10)' }
          }
        },
        generationMode: {
          type: 'string',
          description: 'Mesh generation mode',
          required: false,
          default: 'cloud-api',
          enum: ['cloud-api', 'local-gpu', 'manual-upload']
        }
      },
      outputs: {
        texturePng: {
          type: 'string',
          description: 'Base64-encoded texture PNG'
        },
        meshGlbUrl: {
          type: 'string',
          description: 'URL to download generated GLB file'
        },
        jobId: {
          type: 'string',
          description: 'Job ID for async processing (local-gpu mode)'
        },
        stepsCompleted: {
          type: 'array',
          description: 'Pipeline steps that were completed'
        },
        message: {
          type: 'string',
          description: 'Success or status message'
        }
      },
      tags: ['3d', 'asset', 'composition', 'pipeline', 'ai-generation', 'headless-capable'],
      estimated_duration_seconds: 30, // PNG (~10s) + Mesh (~20s)
      required_resources: ['backend', 'stable-diffusion', '3d-generation-api'],
      llm_config: {
        composedCells: ['png-generator-cell', 'mesh-prototyping-cell'],
        pipelineType: 'sequential',
        canFailPartially: true
      }
    }
  }
  
  /**
   * Validate asset prototyping input
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    
    // Check required fields
    if (!input.prompt || typeof input.prompt !== 'string') {
      errors.push({ field: 'prompt', message: 'Prompt is required and must be a string' })
    } else if (input.prompt.trim().length === 0) {
      errors.push({ field: 'prompt', message: 'Prompt cannot be empty' })
    } else if (input.prompt.length > 1000) {
      errors.push({ field: 'prompt', message: 'Prompt must be less than 1000 characters' })
    }
    
    // Validate optional fields
    if (input.negativePrompt !== undefined) {
      if (typeof input.negativePrompt !== 'string') {
        errors.push({ field: 'negativePrompt', message: 'Negative prompt must be a string' })
      } else if (input.negativePrompt.length > 1000) {
        errors.push({ field: 'negativePrompt', message: 'Negative prompt must be less than 1000 characters' })
      }
    }
    
    if (input.asset3dMode !== undefined && typeof input.asset3dMode !== 'boolean') {
      errors.push({ field: 'asset3dMode', message: 'asset3dMode must be a boolean' })
    }
    
    if (input.generationMode !== undefined) {
      const validModes = ['cloud-api', 'local-gpu', 'manual-upload']
      if (!validModes.includes(input.generationMode)) {
        errors.push({ 
          field: 'generationMode', 
          message: `Generation mode must be one of: ${validModes.join(', ')}` 
        })
      }
    }
    
    // Validate reconstruction params if provided
    if (input.reconstructionParams !== undefined) {
      if (typeof input.reconstructionParams !== 'object') {
        errors.push({ field: 'reconstructionParams', message: 'Reconstruction params must be an object' })
      } else {
        const params = input.reconstructionParams
        
        if (params.targetFaces !== undefined) {
          if (typeof params.targetFaces !== 'number' || params.targetFaces < 100 || params.targetFaces > 100000) {
            errors.push({ 
              field: 'reconstructionParams.targetFaces', 
              message: 'Target faces must be a number between 100 and 100000' 
            })
          }
        }
        
        if (params.compressionLevel !== undefined) {
          if (typeof params.compressionLevel !== 'number' || params.compressionLevel < 0 || params.compressionLevel > 10) {
            errors.push({ 
              field: 'reconstructionParams.compressionLevel', 
              message: 'Compression level must be a number between 0 and 10' 
            })
          }
        }
      }
    }
    
    return errors
  }
  
  /**
   * Setup coordinated lifecycle for all sub-cells
   * 
   * Initializes both PNG and Mesh cells. This demonstrates how composed cells
   * manage lifecycle across multiple sub-cells.
   */
  async setup(config: EnvironmentConfig): Promise<void> {
    if (this._isSetup) {
      log.debug('AssetPrototypingCell already setup')
      return
    }
    
    log.info('Setting up AssetPrototypingCell with sub-cells', config)
    
    try {
      // Setup all sub-cells in parallel
      await Promise.all([
        this.pngCell.setup(config),
        this.meshCell.setup(config)
      ])
      
      this._isSetup = true
      log.info('AssetPrototypingCell setup complete')
    } catch (error: any) {
      log.error('AssetPrototypingCell setup failed', error)
      throw new Error(`Setup failed: ${error.message}`)
    }
  }
  
  /**
   * Teardown coordinated lifecycle for all sub-cells
   * 
   * Cleans up both PNG and Mesh cells. This demonstrates how composed cells
   * manage cleanup across multiple sub-cells.
   */
  async teardown(): Promise<void> {
    if (!this._isSetup) {
      log.debug('AssetPrototypingCell not setup, skipping teardown')
      return
    }
    
    log.info('Tearing down AssetPrototypingCell and sub-cells')
    
    try {
      // Teardown all sub-cells in parallel
      await Promise.all([
        this.pngCell.teardown(),
        this.meshCell.teardown()
      ])
      
      this._isSetup = false
      log.info('AssetPrototypingCell teardown complete')
    } catch (error: any) {
      log.error('AssetPrototypingCell teardown failed', error)
      throw new Error(`Teardown failed: ${error.message}`)
    }
  }
  
  /**
   * Health check for composed cell
   * 
   * Checks health of all sub-cells. Cell is healthy only if ALL sub-cells are healthy.
   */
  async health_check(): Promise<HealthCheckResult> {
    try {
      // Check health of all sub-cells
      const [pngHealth, meshHealth] = await Promise.all([
        this.pngCell.health_check(),
        this.meshCell.health_check()
      ])
      
      // Cell is healthy only if all sub-cells are healthy
      if (pngHealth.status === 'healthy' && meshHealth.status === 'healthy') {
        log.debug('AssetPrototypingCell health check: healthy')
        return createHealthyResult()
      }
      
      // If any sub-cell is unavailable, we're unavailable
      if (pngHealth.status === 'unavailable' || meshHealth.status === 'unavailable') {
        log.warn('AssetPrototypingCell health check: unavailable', {
          pngStatus: pngHealth.status,
          meshStatus: meshHealth.status
        })
        return {
          status: 'unavailable',
          can_execute: false,
          reason: 'One or more sub-cells are unavailable',
          estimated_recovery_seconds: Math.max(
            pngHealth.estimated_recovery_seconds || 0,
            meshHealth.estimated_recovery_seconds || 0
          )
        }
      }
      
      // Otherwise we're degraded
      log.warn('AssetPrototypingCell health check: degraded', {
        pngStatus: pngHealth.status,
        meshStatus: meshHealth.status
      })
      return {
        status: 'degraded',
        can_execute: false,
        reason: 'One or more sub-cells are degraded',
        estimated_recovery_seconds: Math.max(
          pngHealth.estimated_recovery_seconds || 0,
          meshHealth.estimated_recovery_seconds || 0
        )
      }
    } catch (error: any) {
      log.error('AssetPrototypingCell health check failed', error)
      return {
        status: 'unavailable',
        can_execute: false,
        reason: `Health check failed: ${error.message}`
      }
    }
  }
}
