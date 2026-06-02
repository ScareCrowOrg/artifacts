/**
 * @file ContentUploadCell.ts
 * @description ContentUploadCell — BaseCell implementation for file upload and persist.
 *
 * Delegates all persistence to ContentManagerCell via execute-ephemeral API.
 * This cell's primary role is wrapping the upload flow with a clean BaseCell
 * interface so other cells can use it:
 *   const uploader = new ContentUploadCell()
 *   const result = await uploader.execute({ file, filename, content_type_id, assignee_id })
 *   // result.output = { content_id, data_ref, filename, size_bytes }
 *
 * Part of content-upload-cell feature implementation
 */

import { BaseCell, createHealthyResult } from '@/types/BaseCell'
import type { CellResult, CellMetadata, ValidationError, HealthCheckResult } from '@/types/BaseCell'
import { apiFetch } from '@/services/apiService'
import { createLogger } from '@/utils/logger'

const logger = createLogger('cells:ContentUpload')

export class ContentUploadCell extends BaseCell {
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()
    try {
      // 1. Validate input
      const errors = this.validate(input)
      if (errors.length > 0) {
        return {
          success: false,
          output: {},
          error: errors.map(e => e.message).join('; '),
          execution_time: performance.now() - startTime
        }
      }

      // 2. Delegate to ContentManagerCell via execute-ephemeral
      const response = await apiFetch('/api/cells/execute-ephemeral', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cell_type: 'content-manager-cell',
          input_data: {
            action: 'persist',
            content_type_id: input.content_type_id,
            filename: input.filename,
            binary: input.binary,
            assignee_id: input.assignee_id,
            origin_cell_id: input.origin_cell_id,
            fragments: input.fragments || {},
            tags: input.tags || [],
            metadata: input.metadata || {}
          }
        })
      })

      if (!response.ok) {
        throw new Error(`Backend error: ${response.status} ${response.statusText}`)
      }

      const result = await response.json()

      if (!result.success) {
        return {
          success: false,
          output: {},
          error: result.error || 'Persist failed',
          execution_time: performance.now() - startTime
        }
      }

      return {
        success: true,
        output: result.output || result.data || {},
        execution_time: performance.now() - startTime,
        execution_steps: ['validate', 'persist'],
        metadata: { action: 'persist' }
      }
    } catch (error: any) {
      logger.error('ContentUploadCell.execute error:', error)
      return {
        success: false,
        output: {},
        error: error.message,
        execution_time: performance.now() - startTime
      }
    }
  }

  async describe(): Promise<CellMetadata> {
    return {
      id: 'content-upload-cell',
      name: 'Content Upload',
      version: '1.0.0',
      description: 'Upload and persist files as Content records. Delegates to ContentManagerCell. Returns content_id for use by other cells.',
      inputs: {
        file: { type: 'file', description: 'File to upload (via File input in UI)' },
        content_type_id: { type: 'string', description: 'Content type ID (auto-detected from MIME if not provided)', required: false },
        filename: { type: 'string', description: 'Original filename', required: true },
        binary: { type: 'string', description: 'Base64-encoded file data', required: true },
        assignee_id: { type: 'string', description: 'Assignee ID for runtime path routing', required: true },
        origin_cell_id: { type: 'string', description: 'Origin cell for lineage tracking', required: false }
      },
      outputs: {
        content_id: { type: 'string', description: 'UUID of the persisted Content record' },
        data_ref: { type: 'string', description: 'Storage reference (e.g. /runtime/user/...)' },
        filename: { type: 'string', description: 'Persisted filename' },
        size_bytes: { type: 'number', description: 'File size in bytes' }
      },
      tags: ['upload', 'content', 'persist', 'utility']
    }
  }

  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    if (!input.filename) {
      errors.push({ field: 'filename', message: 'filename is required' })
    }
    if (!input.binary) {
      errors.push({ field: 'binary', message: 'binary data is required' })
    }
    if (!input.assignee_id) {
      errors.push({ field: 'assignee_id', message: 'assignee_id is required' })
    }
    return errors
  }

  async health_check(): Promise<HealthCheckResult> {
    try {
      const response = await apiFetch('/api/cells/execute-ephemeral', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cell_type: 'content-manager-cell',
          input_data: { action: 'list', limit: 1 }
        })
      })
      return response.ok
        ? createHealthyResult()
        : { status: 'degraded', can_execute: true, reason: `Backend status ${response.status}`, estimated_recovery_seconds: 30 }
    } catch (error: any) {
      logger.error('ContentUploadCell.health_check error:', error)
      return { status: 'unavailable', can_execute: false, reason: error.message, estimated_recovery_seconds: 60 }
    }
  }
}
