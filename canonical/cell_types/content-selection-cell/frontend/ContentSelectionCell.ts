/**
 * @file ContentSelectionCell.ts
 * @description ContentSelectionCell — BaseCell implementation for browsing and selecting persisted content.
 *
 * Delegates all list/load operations to ContentManagerCell via execute-ephemeral API.
 * This cell provides a selection UI wrapper so other cells can use it:
 *   const selector = new ContentSelectionCell()
 *   selector.cell_instance = { assignee_id: '...' }
 *   const result = await selector.execute({ action: 'list', content_type_id: 'image-png' })
 *   // result.output = { contents: [...], count, total }
 *
 * The View.vue handles the interactive selection flow, returning:
 *   { content_id, filename, content_type_id, size_bytes, data_ref, tags, version }
 *
 * Part of content-selection-cell feature implementation
 */

import { BaseCell, createHealthyResult } from '@/types/BaseCell'
import type { CellResult, CellMetadata, ValidationError, HealthCheckResult } from '@/types/BaseCell'
import { apiFetch } from '@/services/apiService'
import { createLogger } from '@/utils/logger'

const logger = createLogger('cells:ContentSelection')

export class ContentSelectionCell extends BaseCell {
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

      const action = input.action || 'list'

      // 2. Delegate to ContentManagerCell via execute-ephemeral
      const response = await apiFetch('/api/cells/execute-ephemeral', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cell_type: 'content-manager-cell',
          input_data: {
            action,
            filters: {
              ...(input.filters || {}),
              ...(input.content_type_id ? { content_type_id: input.content_type_id } : {})
            },
            limit: input.limit || 20,
            offset: input.offset || 0,
            ...(action === 'load'
              ? { content_id: input.content_id, direct_download: input.direct_download }
              : {})
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
          error: result.error || `${action} failed`,
          execution_time: performance.now() - startTime
        }
      }

      return {
        success: true,
        output: result.output || result.data || {},
        execution_time: performance.now() - startTime,
        execution_steps: ['validate', action],
        metadata: { action }
      }
    } catch (error: any) {
      logger.error('ContentSelectionCell.execute error:', error)
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
      id: 'content-selection-cell',
      name: 'Content Selection',
      version: '1.0.0',
      description: 'Browse and select persisted content. Delegates to ContentManagerCell for list/load. Returns content_id and metadata for use by other cells.',
      inputs: {
        action: { type: 'string', enum: ['list', 'load'], default: 'list', description: 'Action: list contents or load a specific content' },
        content_type_id: { type: 'string', description: 'Filter by content type (e.g. image-png, vector-svg, 3d-glb)', required: false },
        filters: { type: 'object', description: 'Additional filters (tags, assignee_id, is_latest)', required: false },
        limit: { type: 'number', default: 20, description: 'Max items per page', required: false },
        offset: { type: 'number', default: 0, description: 'Pagination offset', required: false },
        content_id: { type: 'string', description: 'Content ID to load (for load action)', required: false },
        direct_download: { type: 'boolean', default: false, description: 'If true, returns binary; if false, returns presigned URL', required: false }
      },
      outputs: {
        contents: { type: 'array', description: 'List of content items (list action)' },
        count: { type: 'number', description: 'Number of items in this page' },
        total: { type: 'number', description: 'Total items matching query' },
        selected_content_id: { type: 'string', description: 'Selected content ID (after user selection)' },
        selected_filename: { type: 'string', description: 'Selected filename' },
        selected_content_type_id: { type: 'string', description: 'Selected content type ID' },
        selected_size_bytes: { type: 'number', description: 'Selected content size in bytes' },
        selected_data_ref: { type: 'string', description: 'Selected content storage reference' }
      },
      tags: ['content', 'selection', 'browse', 'utility']
    }
  }

  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    const action = input.action || 'list'

    if (!['list', 'load'].includes(action)) {
      errors.push({ field: 'action', message: `Invalid action '${action}'. Must be 'list' or 'load'.` })
    }

    if (action === 'load' && !input.content_id) {
      errors.push({ field: 'content_id', message: 'content_id is required for load action' })
    }

    if (input.limit !== undefined) {
      const limit = Number(input.limit)
      if (isNaN(limit) || limit < 1 || limit > 100) {
        errors.push({ field: 'limit', message: 'limit must be between 1 and 100' })
      }
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
      logger.error('ContentSelectionCell.health_check error:', error)
      return { status: 'unavailable', can_execute: false, reason: error.message, estimated_recovery_seconds: 60 }
    }
  }
}
