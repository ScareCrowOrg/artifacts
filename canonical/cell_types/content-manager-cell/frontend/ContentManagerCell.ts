/**
 * @file ContentManagerCell.ts
 * @description ContentManagerCell - BaseCell implementation for content management
 * 
 * This cell provides a reusable interface for content persistence and retrieval,
 * enabling other cells (png-generator, svg-generator, etc.) to easily manage
 * their output artifacts in Cloudflare R2 storage.
 * 
 * Features:
 * - List contents with filters (by type, assignee, tags)
 * - Load content from R2 (presigned URLs or direct download)
 * - Persist content to R2 with schema validation
 * - Ephemeral execution (no persistent cell instance required)
 * 
 * Part of content-manager-cell refactoring to implement BaseCell interface
 */

import type { 
  BaseCell, 
  CellResult, 
  CellMetadata, 
  ValidationError, 
  EnvironmentConfig,
  HealthCheckResult 
} from '@/types/BaseCell'
import { createHealthyResult } from '@/types/BaseCell'

/**
 * Content Manager actions
 */
export type ContentManagerAction = 'list' | 'load' | 'persist'

/**
 * Filter options for list action
 */
export interface ContentQueryFilters {
  /** Filter by content type ID */
  content_type_id?: string | null
  /** Filter by assignee ID */
  assignee_id?: string | null
  /** Filter by origin cell ID */
  origin_cell_id?: string | null
  /** Filter by tags */
  tags?: string[]
  /** Filter by latest version only */
  is_latest?: boolean
}

/**
 * Input for list action
 */
export interface ListContentInput {
  action: 'list'
  filters?: ContentQueryFilters
  limit?: number
  offset?: number
}

/**
 * Input for load action
 */
export interface LoadContentInput {
  action: 'load'
  content_id: string
  direct_download?: boolean
}

/**
 * Input for persist action
 */
export interface PersistContentInput {
  action: 'persist'
  content_type_id: string
  filename: string
  binary: string | ArrayBuffer  // Base64 string or ArrayBuffer
  fragments?: Record<string, any>
  tags?: string[]
  metadata?: Record<string, any>
  origin_cell_id?: string
  assignee_id?: string
}

/**
 * Union type for all content manager inputs
 */
export type ContentManagerInput = ListContentInput | LoadContentInput | PersistContentInput

/**
 * Content item metadata
 */
export interface ContentItem {
  id: string
  content_type_id: string
  filename: string
  size_bytes: number
  created_at?: string
  fragments: Record<string, any>
  data_ref: string
  tags: string[]
  version: number
  is_latest: boolean
  origin_cell_id?: string
}

/**
 * Output for list action
 */
export interface ListContentOutput {
  contents: ContentItem[]
  count: number
  limit: number
  offset: number
  total: number
}

/**
 * Output for load action
 */
export interface LoadContentOutput {
  content_id: string
  filename: string
  presigned_url?: string
  presigned_expires_in?: number
  binary?: string  // Base64 encoded
  size_bytes: number
  mime_type: string
  fragments: Record<string, any>
}

/**
 * Output for persist action
 */
export interface PersistContentOutput {
  id: string
  content_type_id: string
  filename: string
  size_bytes: number
  data_ref: string
  version: number
  created_at?: string
  fragments: Record<string, any>
  tags: string[]
  origin_cell_id?: string
}

/**
 * ContentManagerCell - BaseCell implementation for content management
 * 
 * This cell is designed as an ephemeral utility that can be imported and used
 * by other cells to manage their content persistence. It delegates execution
 * to the backend via the /api/cells/execute-ephemeral endpoint.
 * 
 * Usage Pattern:
 * ```typescript
 * // In png-generator-cell:
 * import { ContentManagerCell } from '@/cells/content-manager-cell/frontend/ContentManagerCell'
 * 
 * export class PngGeneratorCell implements BaseCell {
 *   private contentManager = new ContentManagerCell()
 * 
 *   async execute(input: Record<string, any>): Promise<CellResult> {
 *     // Generate PNG
 *     const pngData = await this.generatePNG(input)
 *     
 *     // Persist using ContentManagerCell
 *     const persistResult = await this.contentManager.execute({
 *       action: 'persist',
 *       content_type_id: 'image-png',
 *       filename: 'generated.png',
 *       binary: pngData,
 *       fragments: { prompt: input.prompt },
 *       origin_cell_id: this.cell_instance?.id
 *     })
 *     
 *     return persistResult
 *   }
 * }
 * ```
 * 
 * @example
 * ```typescript
 * const cm = new ContentManagerCell()
 * 
 * // List PNG images
 * const listResult = await cm.execute({
 *   action: 'list',
 *   filters: { content_type_id: 'image-png', is_latest: true },
 *   limit: 20
 * })
 * 
 * // Load a specific content
 * const loadResult = await cm.execute({
 *   action: 'load',
 *   content_id: 'content-uuid'
 * })
 * 
 * // Persist new content
 * const persistResult = await cm.execute({
 *   action: 'persist',
 *   content_type_id: 'image-png',
 *   filename: 'my-image.png',
 *   binary: base64Data,
 *   tags: ['generated', 'png']
 * })
 * ```
 */
export class ContentManagerCell implements BaseCell {
  private _apiBaseUrl: string = '/api/cells'
  private _authToken?: string
  
  /**
   * Set authentication token for API calls
   */
  setAuthToken(token: string): void {
    this._authToken = token
  }
  
  /**
   * Execute content manager action
   * 
   * Routes to appropriate backend handler based on action type.
   * All execution is performed via backend to ensure security and
   * proper transaction handling for storage operations.
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
          error: 'Validation failed: ' + errors.map(e => `${e.field}: ${e.message}`).join(', ')
        }
      }
      
      const action = input.action as ContentManagerAction
      
      // Call backend via execute-ephemeral endpoint
      const response = await fetch(`${this._apiBaseUrl}/execute-ephemeral`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(this._authToken ? { 'Authorization': `Bearer ${this._authToken}` } : {})
        },
        body: JSON.stringify({
          cell_type: 'content-manager-cell',
          input_data: input
        })
      })
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(`Backend execution failed: ${errorData.detail || response.statusText}`)
      }
      
      const result = await response.json()
      
      // Check if backend execution was successful
      if (!result.success) {
        return {
          success: false,
          output: result.data || {},
          execution_time: performance.now() - startTime,
          error: result.error || 'Backend execution failed'
        }
      }
      
      // Return successful result
      return {
        success: true,
        output: result.data || {},
        execution_time: performance.now() - startTime,
        execution_steps: ['validate', 'backend_call', `action_${action}`],
        metadata: {
          action,
          backend_execution: true
        }
      }
    } catch (error: any) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: error.message || 'Content manager execution failed'
      }
    }
  }
  
  /**
   * Describe content manager capabilities
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'content-manager-cell',
      name: 'Content Manager',
      version: '1.0.0',
      description: 'Persistent content management with Cloudflare R2 storage. Provides list, load, and persist operations for typed content assets (images, vectors, 3D models).',
      inputs: {
        action: {
          type: 'string',
          description: 'Action to perform',
          required: true,
          enum: ['list', 'load', 'persist']
        },
        // List action inputs
        filters: {
          type: 'object',
          description: 'Query filters for list action',
          required: false,
          properties: {
            content_type_id: { type: 'string', description: 'Filter by content type' },
            assignee_id: { type: 'string', description: 'Filter by assignee' },
            origin_cell_id: { type: 'string', description: 'Filter by origin cell' },
            tags: { type: 'array', items: { type: 'string' }, description: 'Filter by tags' },
            is_latest: { type: 'boolean', description: 'Filter by latest version only' }
          }
        },
        limit: {
          type: 'number',
          description: 'Maximum number of results (1-100)',
          required: false,
          default: 20
        },
        offset: {
          type: 'number',
          description: 'Pagination offset',
          required: false,
          default: 0
        },
        // Load action inputs
        content_id: {
          type: 'string',
          description: 'Content ID to load (required for load action)',
          required: false
        },
        direct_download: {
          type: 'boolean',
          description: 'Download binary directly (vs presigned URL)',
          required: false,
          default: false
        },
        // Persist action inputs
        content_type_id: {
          type: 'string',
          description: 'Content type ID (required for persist action)',
          required: false,
          enum: ['image-png', 'vector-svg', '3d-glb']
        },
        filename: {
          type: 'string',
          description: 'Filename with extension (required for persist action)',
          required: false
        },
        binary: {
          type: 'string',
          description: 'Base64 encoded binary data (required for persist action)',
          required: false
        },
        fragments: {
          type: 'object',
          description: 'Metadata fragments for persist action',
          required: false
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: 'Tags for persist action',
          required: false
        },
        metadata: {
          type: 'object',
          description: 'Additional metadata for persist action',
          required: false
        },
        origin_cell_id: {
          type: 'string',
          description: 'Origin cell ID for persist action',
          required: false
        },
        assignee_id: {
          type: 'string',
          description: 'Assignee ID for persist action',
          required: false
        }
      },
      outputs: {
        // List action outputs
        contents: {
          type: 'array',
          description: 'Array of content items (list action)'
        },
        count: {
          type: 'number',
          description: 'Number of items returned (list action)'
        },
        total: {
          type: 'number',
          description: 'Total number of matching items (list action)'
        },
        // Load action outputs
        presigned_url: {
          type: 'string',
          description: 'Presigned R2 URL (load action)'
        },
        // Persist action outputs
        id: {
          type: 'string',
          description: 'Created content ID (persist action)'
        },
        data_ref: {
          type: 'string',
          description: 'Storage reference (persist action)'
        }
      },
      tags: ['content-management', 'storage', 'ephemeral-utility', 'r2'],
      estimated_duration_seconds: 1.0,
      required_resources: ['backend', 'r2-storage']
    }
  }
  
  /**
   * Validate content manager input
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    
    // Check required action field
    if (!input.action) {
      errors.push({ field: 'action', message: 'Action is required' })
      return errors  // Can't validate further without action
    }
    
    const action = input.action as ContentManagerAction
    const validActions: ContentManagerAction[] = ['list', 'load', 'persist']
    
    if (!validActions.includes(action)) {
      errors.push({
        field: 'action',
        message: `Action must be one of: ${validActions.join(', ')}`
      })
      return errors
    }
    
    // Validate action-specific inputs
    switch (action) {
      case 'list':
        // Validate pagination parameters
        if (input.limit !== undefined) {
          if (typeof input.limit !== 'number' || input.limit < 1 || input.limit > 100) {
            errors.push({ field: 'limit', message: 'Limit must be between 1 and 100' })
          }
        }
        if (input.offset !== undefined) {
          if (typeof input.offset !== 'number' || input.offset < 0) {
            errors.push({ field: 'offset', message: 'Offset must be >= 0' })
          }
        }
        break
        
      case 'load':
        // Validate content_id is provided
        if (!input.content_id) {
          errors.push({ field: 'content_id', message: 'content_id is required for load action' })
        } else if (typeof input.content_id !== 'string') {
          errors.push({ field: 'content_id', message: 'content_id must be a string' })
        }
        break
        
      case 'persist':
        // Validate required persist fields
        if (!input.content_type_id) {
          errors.push({ field: 'content_type_id', message: 'content_type_id is required for persist action' })
        } else {
          const validTypes = ['image-png', 'vector-svg', '3d-glb']
          if (!validTypes.includes(input.content_type_id)) {
            errors.push({
              field: 'content_type_id',
              message: `content_type_id must be one of: ${validTypes.join(', ')}`
            })
          }
        }
        
        if (!input.filename) {
          errors.push({ field: 'filename', message: 'filename is required for persist action' })
        } else if (typeof input.filename !== 'string') {
          errors.push({ field: 'filename', message: 'filename must be a string' })
        }
        
        if (!input.binary) {
          errors.push({ field: 'binary', message: 'binary is required for persist action' })
        }
        break
    }
    
    return errors
  }
  
  /**
   * Setup (optional) - Content manager needs no initialization
   * 
   * Note: In production, consider using a proper logging framework
   * instead of console.log
   */
  async setup(config: EnvironmentConfig): Promise<void> {
    if (process.env.NODE_ENV === 'development') {
      console.log('[ContentManagerCell] Setup called')
    }
    
    // Extract auth token from environment if available
    if (config && 'auth_token' in config) {
      this._authToken = (config as any).auth_token
    }
  }
  
  /**
   * Teardown (optional) - Content manager needs no cleanup
   * 
   * Note: In production, consider using a proper logging framework
   * instead of console.log
   */
  async teardown(): Promise<void> {
    if (process.env.NODE_ENV === 'development') {
      console.log('[ContentManagerCell] Teardown called')
    }
    this._authToken = undefined
  }
  
  /**
   * Health check - Verify backend connectivity
   */
  async health_check(): Promise<HealthCheckResult> {
    try {
      // Quick ping to verify backend is accessible
      const response = await fetch(`${this._apiBaseUrl}/types/list`, {
        method: 'GET',
        headers: {
          ...(this._authToken ? { 'Authorization': `Bearer ${this._authToken}` } : {})
        }
      })
      
      if (response.ok) {
        return createHealthyResult()
      } else {
        return {
          status: 'degraded',
          can_execute: false,
          reason: `Backend returned status ${response.status}`,
          estimated_recovery_seconds: 30
        }
      }
    } catch (error: any) {
      return {
        status: 'unavailable',
        can_execute: false,
        reason: `Backend unreachable: ${error.message}`,
        estimated_recovery_seconds: 60
      }
    }
  }
  
  /**
   * Show (optional) - Render modal UI for content management
   * 
   * Supports modal persistence UI for saving assets with naming and metadata.
   * When called with { modal: 'persist-with-naming' }, opens PersistModal
   * component and returns result after user interaction.
   * 
   * @param data - Data to show/persist (asset data with binary content)
   * @param options - Show configuration options
   * @returns Promise resolving to CellResult
   */
  async show(
    data: Record<string, any>,
    options?: { modal?: string; mode?: string }
  ): Promise<CellResult> {
    const startTime = performance.now()
    
    try {
      if (options?.modal === 'persist-with-naming') {
        // Open persist modal with asset data
        return await this.showPersistModal(data)
      }
      
      // Standard preview/display (no-op for headless utility)
      return {
        success: true,
        output: data,
        execution_time: performance.now() - startTime
      }
    } catch (error: any) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: error.message || 'Show operation failed'
      }
    }
  }
  
  /**
   * Show persist modal for asset naming and metadata
   * 
   * Opens a modal dialog using PersistModal component that allows
   * the user to input asset name, description, tags, and visibility.
   * Returns the persistence result after user confirmation.
   * 
   * @param assetData - Asset data to persist
   * @returns Promise resolving to CellResult with persisted asset details
   */
  private async showPersistModal(
    assetData: Record<string, any>
  ): Promise<CellResult> {
    return new Promise((resolve) => {
      // Note: This method is designed to integrate with Vue's modal system.
      // The actual modal rendering is handled by the calling component
      // (e.g., PngGeneratorCell View.vue) via PersistModal component.
      // 
      // For now, we return a success result indicating that the modal
      // should be shown. The actual persistence happens when the user
      // confirms in the modal via ContentManagerCell.execute().
      
      resolve({
        success: true,
        output: {
          modal: 'persist',
          assetData
        },
        execution_time: 0,
        metadata: {
          requiresUI: true,
          modalType: 'persist-with-naming'
        }
      })
    })
  }
}
