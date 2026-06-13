/**
 * @file ImageContentCell.ts
 * @description ImageContentCell - BaseCell implementation for image viewer, metadata editor & download
 *
 * This cell provides:
 * - 'load' action: Load content data by content_id or relative_url
 * - 'update-metadata' action: PATCH /api/contents/{id} with tags, metadata, name
 * - 'download' action: postMessage FILE_DOWNLOAD for cross-origin iframe compat
 * - 'copy' action: Fetch image and write to clipboard
 *
 * Part of BaseCell v1.0 Framework Implementation
 * Cell type: image-content-cell (ephemeral)
 */

import { BaseCell } from '@/types/BaseCell'
import type { CellResult, CellMetadata, ValidationError } from '@/types/BaseCell'
import { apiFetch } from '@/services/apiService'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:ImageContent')

/**
 * Supported ImageContentCell actions
 */
export type ImageContentAction = 'load' | 'update-metadata' | 'download' | 'copy'

/**
 * ImageContentCell input interface
 */
export interface ImageContentInput {
  /** Action to perform */
  action: ImageContentAction

  /** UUID of the persisted content (for 'load' action) */
  content_id?: string | null

  /** Relative URL for direct file serving (for 'load' action) */
  relative_url?: string | null

  /** Tags to set (for 'update-metadata' action) */
  tags?: string[]

  /** Custom metadata (for 'update-metadata' action) */
  metadata?: Record<string, any>

  /** Content name (for 'update-metadata' action) */
  name?: string

  /** Base64 or URL of the image data (for 'download' and 'copy' actions) */
  imageUrl?: string | null
}

/**
 * ImageContentCell output interface
 */
export interface ImageContentOutput {
  /** Whether execution was successful */
  success: boolean

  /** Content data (from 'load' action) */
  content?: Record<string, any>

  /** Full URL of the image for display (from 'load' action) */
  imageUrl?: string

  /** Updated content after metadata save (from 'update-metadata' action) */
  updatedContent?: Record<string, any>

  /** Error message if failed */
  error?: string
}

/**
 * ImageContentCell - Viewer for persisted image content with metadata editing and download
 *
 * Capabilities:
 * - Load persisted content by content_id or relative_url
 * - Edit metadata (tags, name, description) via PATCH /api/contents/{id}
 * - Download image to local machine via postMessage FILE_DOWNLOAD
 * - Copy image to clipboard
 *
 * Execution Model:
 * - 'load': Fetches content via GET /api/contents/{id} or builds URL from relative_url
 * - 'update-metadata': PATCH /api/contents/{id} with provided fields
 * - 'download': Delegates to host shell via postMessage (cross-origin iframe compat)
 * - 'copy': Fetches image blob and uses clipboard.write()
 */
export class ImageContentCell extends BaseCell {
  /**
   * Execute image content cell actions
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()

    try {
      const action = input.action as ImageContentAction
      log.debug('Executing ImageContentCell', { action })

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
      switch (action) {
        case 'load':
          return await this.handleLoad(input, startTime)
        case 'update-metadata':
          return await this.handleUpdateMetadata(input, startTime)
        case 'download':
          return await this.handleDownload(input, startTime)
        case 'copy':
          return await this.handleCopy(input, startTime)
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
   * Handle 'load' action — load content data by ID or build URL from relative_url
   */
  private async handleLoad(
    input: ImageContentInput,
    startTime: number,
  ): Promise<CellResult> {
    const contentId = input.content_id
    const relativeUrl = input.relative_url

    // Build output scaffolding
    const output: ImageContentOutput = {
      success: false,
    }

    if (relativeUrl) {
      // ======================================================================
      // REDIS MAGRO (Content Reference): If relative_url is provided, build a
      // full URL that routes through the RuntimeFileServer (auth-proxy) for
      // CORS support in cross-origin iframes.
      //
      // The Runtime File Server serves files at:
      //   {origin}/artifacts/runtime/user/{assignee}/contents/{id}/{file}
      // ======================================================================
      log.info('Loading image from relative_url', { relativeUrl })

      const origin = window.location.origin.replace(/\/+$/, '')
      output.imageUrl = `${origin}/artifacts${relativeUrl}`
      output.success = true
      output.content = { relative_url: relativeUrl }

      log.info('Image URL built from relative_url', { imageUrl: output.imageUrl })

      return {
        success: true,
        output,
        artifacts: output.imageUrl ? [output.imageUrl] : [],
        execution_time: performance.now() - startTime,
        execution_steps: ['validate', 'build-url'],
        quality_score: 1.0,
      }
    }

    if (contentId) {
      // Load content from backend API
      log.info('Loading content by ID', { contentId })

      const response = await apiFetch(`/api/contents/${contentId}`)

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(
          `Failed to load content: ${response.status} ${response.statusText} — ${errorText}`,
        )
      }

      const content = await response.json()
      log.info('Content loaded successfully', { contentId })

      // Determine image URL from content data
      // Priority: data_ref (if HTTP URL) > build from relative_url
      let imageUrl = ''

      if (content.data_ref && content.data_ref.startsWith('http')) {
        imageUrl = content.data_ref
      } else if (content.data_ref && content.data_ref.startsWith('/')) {
        // If data_ref is a relative path, prefix with /artifacts
        const origin = window.location.origin.replace(/\/+$/, '')
        imageUrl = `${origin}/artifacts${content.data_ref}`
      } else {
        // Fallback: try to construct from content metadata
        imageUrl = content.imageUrl || ''
      }

      output.imageUrl = imageUrl
      output.content = content
      output.success = true

      return {
        success: true,
        output,
        artifacts: imageUrl ? [imageUrl] : [],
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
   * Handle 'update-metadata' action — PATCH /api/contents/{id}
   */
  private async handleUpdateMetadata(
    input: ImageContentInput,
    startTime: number,
  ): Promise<CellResult> {
    const contentId = input.content_id
    if (!contentId) {
      throw new Error('content_id is required for update-metadata action')
    }

    log.info('Updating content metadata', { contentId })

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

      // Map status codes to meaningful errors
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
    log.info('Content metadata updated successfully', { contentId })

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
   * Handle 'download' action — postMessage FILE_DOWNLOAD
   *
   * Cross-origin iframe: Chrome blocks the `download` attribute on anchor
   * elements inside cross-origin iframes. Delegate the download to the host
   * shell (cockpit-vue) via postMessage so it runs in the same-origin context.
   *
   * Same pattern as PngGeneratorCell.handleDownload().
   */
  private async handleDownload(
    input: ImageContentInput,
    startTime: number,
  ): Promise<CellResult> {
    const imageUrl = input.imageUrl
    if (!imageUrl) {
      throw new Error('imageUrl is required for download action')
    }

    log.info('Requesting image download via host shell')

    window.top.postMessage(
      {
        type: 'FILE_DOWNLOAD',
        payload: {
          url: imageUrl,
          filename: `image-${Date.now()}.png`,
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
   * Handle 'copy' action — fetch image and write to clipboard
   *
   * Same pattern as PngGeneratorCell.handleCopy().
   */
  private async handleCopy(
    input: ImageContentInput,
    startTime: number,
  ): Promise<CellResult> {
    const imageUrl = input.imageUrl
    if (!imageUrl) {
      throw new Error('imageUrl is required for copy action')
    }

    log.info('Copying image to clipboard')

    // Fetch the image blob
    const response = await fetch(imageUrl)
    if (!response.ok) {
      throw new Error(`Failed to fetch image for clipboard: ${response.statusText}`)
    }

    const blob = await response.blob()

    // Determine MIME type from blob or default to image/png
    const mimeType = blob.type || 'image/png'

    await navigator.clipboard.write([
      new ClipboardItem({ [mimeType]: blob }),
    ])

    log.info('Image copied to clipboard')

    return {
      success: true,
      output: {
        success: true,
        message: 'Image copied to clipboard',
      },
      execution_time: performance.now() - startTime,
      execution_steps: ['validate', 'fetch-blob', 'clipboard-write'],
      quality_score: 1.0,
    }
  }

  /**
   * Describe ImageContentCell capabilities
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'image-content-cell',
      name: 'Image Content Viewer',
      version: '1.0.0',
      description:
        'View persisted image content with metadata editing and download. Supports loading by content_id or relative_url, editing tags/name/description, downloading via postMessage, and clipboard copy.',
      inputs: {
        action: {
          type: 'string',
          description: 'Action to perform',
          required: true,
          enum: ['load', 'update-metadata', 'download', 'copy'],
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
            'Relative URL for direct file serving (alt-only for load, requires either content_id or relative_url)',
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
        imageUrl: {
          type: 'string',
          description:
            'Full image URL (required for download and copy actions)',
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
        imageUrl: {
          type: 'string',
          description: 'Full URL of the image for display',
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
        'image',
        'viewer',
        'metadata',
        'download',
        'clipboard',
        'frontend-only',
      ],
      estimated_duration_seconds: 2,
      required_resources: ['backend'],
    }
  }

  /**
   * Validate ImageContentCell input
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []

    if (!input.action) {
      errors.push({ field: 'action', message: 'Action is required' })
      return errors
    }

    const validActions: ImageContentAction[] = [
      'load',
      'update-metadata',
      'download',
      'copy',
    ]

    if (!validActions.includes(input.action as ImageContentAction)) {
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
      !input.imageUrl
    ) {
      errors.push({
        field: 'imageUrl',
        message: 'imageUrl is required for "download" action',
      })
    }

    if (
      input.action === 'copy' &&
      !input.imageUrl
    ) {
      errors.push({
        field: 'imageUrl',
        message: 'imageUrl is required for "copy" action',
      })
    }

    return errors
  }
}
