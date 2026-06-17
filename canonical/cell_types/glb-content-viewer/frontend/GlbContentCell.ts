/**
 * @file GlbContentCell.ts
 * @description GlbContentCell - BaseCell implementation for 3D GLB/GLTF model viewer
 *
 * This cell provides:
 * - 'load' action: Load 3D model data by content_id or relative_url
 * - 'download' action: postMessage FILE_DOWNLOAD for cross-origin iframe compat
 * - 'update-metadata' action: PATCH /api/contents/{id} with tags, metadata, name
 *
 * Part of BaseCell v1.0 Framework Implementation
 * Cell type: glb-content-viewer (ephemeral)
 */

import { BaseCell } from '@/types/BaseCell'
import type { CellResult, CellMetadata, ValidationError } from '@/types/BaseCell'
import { apiFetch } from '@/services/apiService'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:GlbContent')

/**
 * Supported GlbContentCell actions
 */
export type GlbContentAction = 'load' | 'download' | 'update-metadata'

/**
 * GlbContentCell input interface
 */
export interface GlbContentInput {
  /** Action to perform */
  action: GlbContentAction

  /** UUID of the persisted content (for 'load' action) */
  content_id?: string | null

  /** Relative URL for direct file serving (for 'load' action) */
  relative_url?: string | null

  /** Full URL of the 3D model (for 'download' action) */
  modelUrl?: string | null

  /** Tags to set (for 'update-metadata' action) */
  tags?: string[]

  /** Custom metadata (for 'update-metadata' action) */
  metadata?: Record<string, any>

  /** Content name (for 'update-metadata' action) */
  name?: string
}

/**
 * GlbContentCell output interface
 */
export interface GlbContentOutput {
  /** Whether execution was successful */
  success: boolean

  /** Content data (from 'load' action) */
  content?: Record<string, any>

  /** Full URL of the 3D model for display (from 'load' action) */
  modelUrl?: string

  /** Updated content after metadata save (from 'update-metadata' action) */
  updatedContent?: Record<string, any>

  /** Error message if failed */
  error?: string
}

/**
 * GlbContentCell - Viewer for persisted 3D GLB/GLTF model content
 *
 * Capabilities:
 * - Load persisted 3D content by content_id or relative_url
 * - Download model to local machine via postMessage FILE_DOWNLOAD
 * - Edit metadata (tags, name, description) via PATCH /api/contents/{id}
 *
 * Execution Model:
 * - 'load': Fetches content via GET /api/contents/{id} or builds URL from relative_url
 * - 'download': Delegates to host shell via postMessage (cross-origin iframe compat)
 * - 'update-metadata': PATCH /api/contents/{id} with provided fields
 */
export class GlbContentCell extends BaseCell {
  /**
   * Execute GLB content cell actions
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()

    try {
      const action = input.action as GlbContentAction
      log.debug('Executing GlbContentCell', { action })

      // Validate input
      const errors = this.validate(input)
      if (errors.length > 0) {
        log.warn('Validation failed', { errors })
        return {
          success: false,
          output: {
            success: false,
            errors,
            error: 'Validation failed',
          },
          execution_time: performance.now() - startTime,
          error: 'Validation failed',
        }
      }

      // Route action
      const glbInput = input as GlbContentInput
      switch (action) {
        case 'load':
          return await this.handleLoad(glbInput, startTime)
        case 'download':
          return await this.handleDownload(glbInput, startTime)
        case 'update-metadata':
          return await this.handleUpdateMetadata(glbInput, startTime)
        default:
          throw new Error(`Unknown action: ${action}`)
      }
    } catch (error: any) {
      log.error('Execution failed', { error: error.message })
      return {
        success: false,
        output: {
          success: false,
          error: error.message || 'Unknown error',
        },
        execution_time: performance.now() - startTime,
        error: error.message || 'Execution failed',
      }
    }
  }

  /**
   * Handle 'load' action — load 3D content by ID or build URL from relative_url
   */
  private async handleLoad(
    input: GlbContentInput,
    startTime: number,
  ): Promise<CellResult> {
    const contentId = input.content_id
    const relativeUrl = input.relative_url

    // DIAG: Log routing decision — which path will be used for loading
    log.debug('DIAG [handleLoad] Choosing path: %s (relative_url=%s, content_id=%s)',
      relativeUrl ? 'relative_url (direct)' : contentId ? 'content_id (API fetch)' : 'neither (empty)',
      relativeUrl || 'null',
      contentId || 'null',
    )

    // Build output scaffolding
    const output: GlbContentOutput = {
      success: false,
    }

    if (relativeUrl) {
      // REDIS MAGRO (Content Reference): Build full URL for auth-proxy serving
      log.info('Loading 3D model from relative_url', { relativeUrl })

      const origin = window.location.origin.replace(/\/+$/, '')
      output.modelUrl = `${origin}/artifacts${relativeUrl}`
      output.success = true
      output.content = { relative_url: relativeUrl }

      log.info('Model URL built from relative_url', { modelUrl: output.modelUrl })

      return {
        success: true,
        output,
        artifacts: output.modelUrl ? [output.modelUrl] : [],
        execution_time: performance.now() - startTime,
        execution_steps: ['validate', 'build-url'],
        quality_score: 1.0,
      }
    }

    if (contentId) {
      // Load content from backend API
      log.info('Loading 3D content by ID', { contentId })

      const response = await apiFetch(`/api/contents/${contentId}`)

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(
          `Failed to load 3D content: ${response.status} ${response.statusText} — ${errorText}`,
        )
      }

      const content = await response.json()
      log.info('3D content loaded successfully', { contentId })

      // Determine model URL from content data
      let modelUrl = ''

      if (content.data_ref && content.data_ref.startsWith('http')) {
        modelUrl = content.data_ref
      } else if (content.data_ref && content.data_ref.startsWith('/')) {
        // If data_ref is a relative path, prefix with /artifacts
        const origin = window.location.origin.replace(/\/+$/, '')
        modelUrl = `${origin}/artifacts${content.data_ref}`
      } else {
        // Fallback: try to construct from content metadata
        modelUrl = content.modelUrl || ''
      }

      output.modelUrl = modelUrl
      output.content = content
      output.success = true

      return {
        success: true,
        output,
        artifacts: modelUrl ? [modelUrl] : [],
        execution_time: performance.now() - startTime,
        execution_steps: ['validate', 'api-fetch', 'process-response'],
        quality_score: 1.0,
      }
    }

    // Neither content_id nor relative_url
    log.warn('Load called without content_id or relative_url')
    output.success = true // Not an error — just empty state
    output.content = {}

    return {
      success: true,
      output,
      execution_time: performance.now() - startTime,
      execution_steps: ['validate', 'no-data'],
    }
  }

  /**
   * Handle 'download' action — postMessage FILE_DOWNLOAD
   *
   * Cross-origin iframe: Chrome blocks the `download` attribute on anchor
   * elements inside cross-origin iframes. Delegate the download to the host
   * shell (cockpit-vue) via postMessage so it runs in the same-origin context.
   */
  private async handleDownload(
    input: GlbContentInput,
    startTime: number,
  ): Promise<CellResult> {
    const modelUrl = input.modelUrl
    if (!modelUrl) {
      throw new Error('modelUrl is required for download action')
    }

    log.info('Requesting 3D model download via host shell')

    if (!window.top) {
      throw new Error('Cannot download: no host shell context available')
    }

    window.top.postMessage(
      {
        type: 'FILE_DOWNLOAD',
        payload: {
          url: modelUrl,
          filename: `model_${Date.now()}.glb`,
        },
        timestamp: Date.now(),
      },
      '*',
    )

    log.info('Download requested')

    return {
      success: true,
      output: {
        success: true,
        message: 'Download requested',
      },
      execution_time: performance.now() - startTime,
      execution_steps: ['validate', 'post-message'],
      quality_score: 1.0,
    }
  }

  /**
   * Handle 'update-metadata' action — PATCH /api/contents/{id}
   */
  private async handleUpdateMetadata(
    input: GlbContentInput,
    startTime: number,
  ): Promise<CellResult> {
    const contentId = input.content_id
    if (!contentId) {
      throw new Error('content_id is required for update-metadata action')
    }

    log.info('Updating 3D content metadata', { contentId })

    // Build PATCH body with only provided fields
    const body: Record<string, any> = {}
    if (input.tags !== undefined) body.tags = input.tags
    if (input.metadata !== undefined) body.metadata = input.metadata
    if (input.name !== undefined) body.name = input.name

    const response = await apiFetch(`/api/contents/${contentId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      const errorText = await response.text()

      if (response.status === 404) {
        throw new Error(`Content not found: ${contentId}`)
      }
      if (response.status === 403) {
        throw new Error('You do not have permission to update this content')
      }

      throw new Error(
        `Failed to update metadata: ${response.status} ${response.statusText} — ${errorText}`,
      )
    }

    const updatedContent = await response.json()
    log.info('3D content metadata updated successfully', { contentId })

    return {
      success: true,
      output: {
        success: true,
        updatedContent,
        content: updatedContent,
      },
      execution_time: performance.now() - startTime,
      execution_steps: ['validate', 'api-patch', 'process-response'],
      quality_score: 1.0,
    }
  }

  /**
   * Describe GlbContentCell capabilities
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'glb-content-viewer',
      name: 'GLB Content Viewer',
      version: '1.0.0',
      description:
        'View 3D GLB/GLTF model content with Babylon.js viewer, download support, and metadata editing. Loads by content_id or relative_url.',
      inputs: {
        action: {
          type: 'string',
          description: 'Action to perform',
          required: true,
          enum: ['load', 'download', 'update-metadata'],
        },
        content_id: {
          type: 'string',
          description:
            'UUID of the persisted content (required for load and update-metadata)',
          required: false,
        },
        relative_url: {
          type: 'string',
          description:
            'Relative URL for direct file serving (alternative for load, requires either content_id or relative_url)',
          required: false,
        },
        modelUrl: {
          type: 'string',
          description:
            'Full 3D model URL (required for download action)',
          required: false,
        },
        tags: {
          type: 'array',
          description: 'Tags to set (for update-metadata action)',
          required: false,
          items: { type: 'string' },
        },
        metadata: {
          type: 'object',
          description: 'Custom metadata key-value pairs (for update-metadata action)',
          required: false,
        },
        name: {
          type: 'string',
          description: 'Content name (for update-metadata action)',
          required: false,
        },
      },
      outputs: {
        success: {
          type: 'boolean',
          description: 'Whether execution was successful',
        },
        content: {
          type: 'object',
          description: 'Content data from load action',
        },
        modelUrl: {
          type: 'string',
          description: 'Full URL of the 3D model for display',
        },
        updatedContent: {
          type: 'object',
          description: 'Updated content after metadata save',
        },
        error: {
          type: 'string',
          description: 'Error message if failed',
        },
      },
      tags: [
        '3d',
        'viewer',
        'glb',
        'gltf',
        'babylon',
        'download',
        'frontend-only',
      ],
      estimated_duration_seconds: 1,
      required_resources: ['babylonjs'],
    }
  }

  /**
   * Validate GlbContentCell input
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []

    if (!input.action) {
      errors.push({ field: 'action', message: 'Action is required' })
      return errors
    }

    const validActions: GlbContentAction[] = [
      'load',
      'download',
      'update-metadata',
    ]

    if (!validActions.includes(input.action as GlbContentAction)) {
      errors.push({
        field: 'action',
        message: `Action must be one of: ${validActions.join(', ')}`,
      })
      return errors
    }

    // Action-specific validation
    if (
      input.action === 'load' &&
      !input.content_id &&
      !input.relative_url
    ) {
      errors.push({
        field: 'content_id',
        message:
          'Either content_id or relative_url is required for "load" action',
      })
    }

    if (
      (input.action === 'update-metadata' || input.action === 'load') &&
      input.content_id !== undefined &&
      input.content_id !== null &&
      typeof input.content_id !== 'string'
    ) {
      errors.push({
        field: 'content_id',
        message: 'content_id must be a string',
      })
    }

    if (input.action === 'update-metadata' && !input.content_id) {
      errors.push({
        field: 'content_id',
        message: 'content_id is required for "update-metadata" action',
      })
    }

    if (
      input.action === 'download' &&
      !input.modelUrl
    ) {
      errors.push({
        field: 'modelUrl',
        message: 'modelUrl is required for "download" action',
      })
    }

    return errors
  }
}
