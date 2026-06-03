/**
 * @file MeshPrototypingCell.ts
 * @description MeshPrototypingCell - BaseCell implementation for 3D mesh generation
 * 
 * This cell implements 3D mesh prototyping from 2D images via backend integration.
 * It supports multiple generation modes (cloud-api, local-gpu, manual-upload) and
 * delegates execution to the `/api/cells/execute-ephemeral` endpoint.
 * 
 * Part of BaseCell v1.0 Framework Implementation
 * Task: [3D-FE-001] Create MeshPrototypingCell TypeScript Implementation
 */

import { BaseCell, createHealthyResult } from '@/types/BaseCell'
import type { CellResult, CellMetadata, ValidationError, EnvironmentConfig, HealthCheckResult } from '@/types/BaseCell'
import apiService from '@/services/apiService.js'
import { ENDPOINTS } from '@/config/endpoints.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:MeshPrototyping')

/**
 * Supported 3D mesh generation modes
 */
export type GenerationMode = 'cloud-api' | 'local-gpu' | 'manual-upload'

/**
 * Supported 3D mesh generation models
 */
export type MeshGenerationModel = 'hunyuan3d'

/**
 * Reconstruction parameters for mesh generation
 */
export interface ReconstructionParams {
  /** Target number of faces for mesh simplification */
  targetFaces?: number
  
  /** Enable Draco compression for smaller file size */
  enableDracoCompression?: boolean
  
  /** Compression level (0-10, higher = more compression) */
  compressionLevel?: number
  
  /** Target file size in megabytes */
  targetFileSizeMB?: number
}

/**
 * MeshPrototypingCell input interface
 */
export interface MeshPrototypingInput {
  /** Base64-encoded PNG image (optional if input_content_id provided) */
  inputImage?: string

  /** Content ID from ContentManagerCell (optional if inputImage provided) */
  input_content_id?: string

  /** Reconstruction parameters (optional) */
  reconstructionParams?: ReconstructionParams

  /** Generation mode (optional, defaults to 'cloud-api') */
  generationMode?: GenerationMode

  /** 3D mesh generation model (optional, defaults to 'sf3d') */
  modelType?: MeshGenerationModel

  /** Solidify silhouette to fix incomplete geometry (optional, defaults to false) */
  solidifySilhouette?: boolean
}

/**
 * MeshPrototypingCell output interface
 */
export interface MeshPrototypingOutput {
  /** Whether execution was successful */
  success: boolean

  /** Job ID for async local-gpu processing */
  job_id?: string

  /** URL to download the generated GLB file (cloud-api) */
  glb_url?: string

  /** Base64-encoded mesh data (alternative to glb_url) */
  mesh_data?: string

  /** Success message */
  message?: string

  /** Error message if failed */
  error?: string

  /** Additional metadata from backend */
  metadata?: Record<string, any>

  /** Generation mode used */
  mode?: string
}

/**
 * MeshPrototypingCell - Backend-integrated BaseCell for 3D mesh generation
 * 
 * Capabilities:
 * - 3D mesh generation from 2D images
 * - Multiple generation modes: cloud-api, local-gpu, manual-upload
 * - Configurable reconstruction parameters
 * - Mesh simplification and Draco compression
 * - Async job management for local-gpu mode
 * 
 * Execution Model:
 * - Delegates to backend via HTTP POST to /api/cells/execute-ephemeral
 * - Cell type: 'meshprototyping'
 * - Supports synchronous (cloud-api) and asynchronous (local-gpu) workflows
 * 
 * @example
 * ```typescript
 * const meshCell = new MeshPrototypingCell()
 * 
 * // Generate 3D mesh from image (cloud-api mode)
 * const result = await meshCell.execute({
 *   inputImage: '<base64-png-data>',
 *   generationMode: 'cloud-api',
 *   reconstructionParams: {
 *     targetFaces: 10000,
 *     enableDracoCompression: true,
 *     compressionLevel: 7
 *   }
 * })
 * 
 * // Local GPU mode (returns job_id for polling)
 * const jobResult = await meshCell.execute({
 *   inputImage: '<base64-png-data>',
 *   generationMode: 'local-gpu'
 * })
 * // Poll backend with job_id to get final GLB URL
 * ```
 */
export class MeshPrototypingCell extends BaseCell {
  private _isSetup: boolean = false

  // ── Persistence State Fields ─────────────────────────────────────────
  /** Content ID for the input image (auto-persisted on upload or loaded from save) */
  public contentId: string = ''
  /** Data ref URL for direct display of input image (e.g. /runtime/user/...) */
  public contentDataRef: string = ''
  /** Content ID for the generated mesh (set after job completion or loaded from save) */
  public meshContentId: string = ''
  /** Whether a generation job is currently running */
  public isGenerating: boolean = false
  /** Current job ID (set when a generation job is queued) */
  public jobId: string = ''
  /** Error message if the last operation failed */
  public error: string = ''
  
  /**
   * Execute 3D mesh generation from 2D image
   * 
   * Delegates to backend via /api/cells/execute-ephemeral endpoint.
   * Returns CellResult with GLB URL or job_id for async processing.
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()
    
    try {
      log.debug('Executing MeshPrototypingCell', { 
        generationMode: input.generationMode || 'cloud-api' 
      })
      
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
        cell_type: '3d-mesh-prototyping-cell',
        input_data: input
      }
      
      log.debug('Sending request to backend', { 
        endpoint: ENDPOINTS.executeEphemeralCell,
        generationMode: input.generationMode || 'cloud-api'
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
      const result = (responseData.result || responseData) as MeshPrototypingOutput

      const executionTime = performance.now() - startTime

      log.info('Execution completed', {
        success: result.success,
        hasJobId: !!result.job_id,
        hasGlbUrl: !!result.glb_url,
        executionTime
      })
      
      // Collect artifacts
      const artifacts: string[] = []
      if (result.glb_url) {
        artifacts.push(result.glb_url)
      } else if (result.mesh_data) {
        artifacts.push(result.mesh_data)
      }
      
      // Map backend response to CellResult
      return {
        success: result.success,
        output: result,
        artifacts,
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
   * Describe MeshPrototypingCell capabilities
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: '3d-mesh-prototyping-cell',
      name: 'Mesh Prototyping Cell',
      version: '1.0.0',
      description: 'Generate 3D mesh models (GLB) from 2D images using various generation modes (cloud-api, local-gpu, manual-upload).',
      inputs: {
        inputImage: {
          type: 'string',
          description: 'Base64-encoded PNG image (optional if input_content_id provided)',
          required: false
        },
        input_content_id: {
          type: 'string',
          description: 'Content ID from ContentManagerCell (optional if inputImage provided)',
          required: false
        },
        generationMode: {
          type: 'string',
          description: 'Generation mode',
          required: false,
          enum: ['cloud-api', 'local-gpu', 'manual-upload'],
          default: 'cloud-api'
        },
        reconstructionParams: {
          type: 'object',
          description: 'Reconstruction parameters for mesh optimization',
          required: false,
          properties: {
            targetFaces: { 
              type: 'number', 
              description: 'Target number of faces for mesh simplification',
              default: 10000 
            },
            enableDracoCompression: { 
              type: 'boolean', 
              description: 'Enable Draco compression for smaller file size',
              default: false 
            },
            compressionLevel: { 
              type: 'number', 
              description: 'Compression level (0-10, higher = more compression)',
              default: 7 
            },
            targetFileSizeMB: { 
              type: 'number', 
              description: 'Target file size in megabytes',
              default: null 
            }
          }
        }
      },
      outputs: {
        success: {
          type: 'boolean',
          description: 'Whether execution was successful'
        },
        job_id: {
          type: 'string',
          description: 'Job ID for async local-gpu processing'
        },
        glb_url: {
          type: 'string',
          description: 'URL to download the generated GLB file'
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
      tags: ['3d-generation', 'mesh-generation', '2d-to-3d', 'glb', 'backend-integrated'],
      estimated_duration_seconds: 120, // ~2 minutes for cloud-api generation
      required_resources: ['backend', 'internet', 'gpu']
    }
  }
  
  /**
   * Validate MeshPrototypingCell input
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []

    // CRITICAL: At least one of inputImage or input_content_id must be provided
    if (!input.inputImage && !input.input_content_id) {
      errors.push({ field: 'input', message: 'Either inputImage or input_content_id is required' })
    }

    // If inputImage provided, validate format
    if (input.inputImage) {
      if (typeof input.inputImage !== 'string' || input.inputImage.trim().length === 0) {
        errors.push({ field: 'inputImage', message: 'Input image must be a non-empty base64-encoded string' })
      } else {
        // Basic validation: check if it looks like base64
        const base64Pattern = /^[A-Za-z0-9+/=]+$/
        const cleanedImage = input.inputImage.replace(/^data:image\/[a-z]+;base64,/, '')
        if (!base64Pattern.test(cleanedImage)) {
          errors.push({ field: 'inputImage', message: 'Input image must be a valid base64-encoded string' })
        }
      }
    }

    // If input_content_id provided, validate it's non-empty string
    if (input.input_content_id && (typeof input.input_content_id !== 'string' || input.input_content_id.trim().length === 0)) {
      errors.push({ field: 'input_content_id', message: 'input_content_id must be a non-empty string' })
    }
    
    // Validate generation mode if provided
    if (input.generationMode !== undefined) {
      const validModes: GenerationMode[] = ['cloud-api', 'local-gpu', 'manual-upload']
      if (!validModes.includes(input.generationMode as GenerationMode)) {
        errors.push({
          field: 'generationMode',
          message: `Generation mode must be one of: ${validModes.join(', ')}`
        })
      }
    }
    
    // Validate reconstruction parameters if provided
    if (input.reconstructionParams) {
      const params = input.reconstructionParams as ReconstructionParams
      
      if (params.targetFaces !== undefined) {
        if (typeof params.targetFaces !== 'number' || params.targetFaces < 100 || params.targetFaces > 100000) {
          errors.push({ 
            field: 'reconstructionParams.targetFaces', 
            message: 'Target faces must be a number between 100 and 100,000' 
          })
        }
      }
      
      if (params.enableDracoCompression !== undefined && typeof params.enableDracoCompression !== 'boolean') {
        errors.push({ 
          field: 'reconstructionParams.enableDracoCompression', 
          message: 'Enable Draco compression must be a boolean' 
        })
      }
      
      if (params.compressionLevel !== undefined) {
        if (typeof params.compressionLevel !== 'number' || params.compressionLevel < 0 || params.compressionLevel > 10) {
          errors.push({ 
            field: 'reconstructionParams.compressionLevel', 
            message: 'Compression level must be a number between 0 and 10' 
          })
        }
      }
      
      if (params.targetFileSizeMB !== undefined) {
        if (typeof params.targetFileSizeMB !== 'number' || params.targetFileSizeMB <= 0) {
          errors.push({ 
            field: 'reconstructionParams.targetFileSizeMB', 
            message: 'Target file size must be a positive number' 
          })
        }
      }
    }
    
    return errors
  }
  
  /**
   * Setup (optional) - MeshPrototypingCell needs no initialization
   */
  async setup(config: EnvironmentConfig): Promise<void> {
    log.debug('Setup called', { config })
    this._isSetup = true
  }
  
  /**
   * Teardown (optional) - MeshPrototypingCell needs no cleanup
   */
  async teardown(): Promise<void> {
    log.debug('Teardown called')
    this._isSetup = false
  }
  
  /**
   * Get serializable state for persistence.
   * Returns content_ids + textual state fields (no binary).
   * Used by App.vue extractCellStateForRuntime() as baseline.
   */
  getState(): Record<string, any> {
    return {
      status: this.isGenerating ? 'generating' : 'idle',
      jobId: this.jobId,
      input_content_id: this.contentId,
      input_data_ref: this.contentDataRef,
      mesh_content_id: this.meshContentId,
      error: this.error,
      isGenerating: this.isGenerating,
    }
  }

  /**
   * Restore state from persisted data.
   * Hydrates content_ids and state from saved record.
   * View.vue uses these to reconstruct direct URLs.
   */
  setState(state: Record<string, any>): void {
    this.contentId = state.input_content_id || state.content_id || ''
    this.contentDataRef = state.input_data_ref || ''
    this.meshContentId = state.mesh_content_id || ''
    this.jobId = state.jobId || ''
    this.isGenerating = state.isGenerating || false
    this.error = state.error || ''
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
      
      // Check if backend is reachable by calling system status endpoint
      const response = await apiService.fetch(ENDPOINTS.systemStatus) as Response
      
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
}

export default MeshPrototypingCell
