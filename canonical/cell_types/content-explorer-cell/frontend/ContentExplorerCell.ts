/**
 * @file ContentExplorerCell.ts
 * @description ContentExplorerCell - BaseCell implementation for browsing assets by type
 * 
 * This cell composes ContentTypeManagerCell and ContentManagerCell to provide
 * a unified asset browsing experience with type selection, asset listing,
 * and management actions.
 * 
 * Features:
 * - Browse available content types
 * - Filter assets by selected type
 * - View asset details and metadata
 * - Delete assets (via ContentManagerCell composition)
 * - Ephemeral execution (no persistent cell instance required)
 * 
 * Part of content-explorer-cell implementation following BaseCell interface
 */

import { BaseCell } from '@/types/BaseCell'
import type {
  CellResult,
  CellMetadata,
  ValidationError,
  EnvironmentConfig,
  HealthCheckResult
} from '@/types/BaseCell'
import { apiFetch } from '@/services/apiService'

/**
 * Content Type metadata structure (from ContentTypeManagerCell)
 */
export interface ContentTypeMetadata {
  id: string
  name: string
  description: string
  mime_type: string
  version: string
  max_size_bytes: number
  allowed_extensions: string[]
  render_hints?: Record<string, any>
}

/**
 * Content Explorer actions
 */
export type ContentExplorerAction = 'list'

/**
 * Asset item from ContentManagerCell
 */
export interface AssetItem {
  id: string
  content_type_id: string
  filename: string
  size_bytes: number
  created_at: string | null
  fragments: Record<string, any>
  data_ref: string
  tags: string[]
  version: number
  is_latest: boolean
  assignee_id: string | null
  origin_cell_id: string | null
}

/**
 * Filter options for asset listing
 */
export interface ExplorerFilters {
  assignee_id?: string | null
  tags?: string[]
  is_latest?: boolean
}

/**
 * Input for list action
 */
export interface ListExplorerInput {
  action: 'list'
  /** Optional: preselect a content type */
  selected_type_id?: string | null
  /** Filters for asset listing */
  filters?: ExplorerFilters
  /** Pagination limit */
  limit?: number
  /** Pagination offset */
  offset?: number
}

/**
 * Union type for all content explorer inputs
 */
export type ContentExplorerInput = ListExplorerInput

/**
 * Types response structure
 */
export interface TypesResponse {
  types: ContentTypeMetadata[]
  total: number
}

/**
 * Assets response structure
 */
export interface AssetsResponse {
  items: AssetItem[]
  total: number
  limit: number
  offset: number
}

/**
 * Output for list action
 */
export interface ListExplorerOutput {
  types: TypesResponse
  assets: AssetsResponse | null
  selected_type_id: string | null
}

/**
 * ContentExplorerCell - BaseCell implementation for content browsing
 * 
 * This cell composes ContentTypeManagerCell and ContentManagerCell
 * to provide a unified browsing experience for typed assets.
 * Designed as an ephemeral utility for asset exploration.
 */
export class ContentExplorerCell extends BaseCell {
  /**
   * Execute content explorer action
   * 
   * @param input - Action and parameters
   * @returns Cell result with types and assets or error
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()
    
    try {
      // Validate input
      const validationErrors = this.validate(input)
      if (validationErrors.length > 0) {
        return {
          success: false,
          output: {
            errors: validationErrors
          },
          execution_time: performance.now() - startTime
        }
      }
      
      const typedInput = input as ContentExplorerInput
      const action = typedInput.action || 'list'
      
      if (action !== 'list') {
        return {
          success: false,
          output: {
            error: `Unknown action '${action}'. Only 'list' is supported.`
          },
          execution_time: performance.now() - startTime
        }
      }
      
      // Call backend via execute-ephemeral endpoint
      // Using apiFetch ensures Authorization header is included automatically
      const response = await apiFetch('/api/cells/execute-ephemeral', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          cell_type: 'content-explorer-cell',
          input_data: input
        })
      })
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `HTTP ${response.status}`)
      }
      
      const data = await response.json()
      
      return {
        success: data.success !== false,
        output: data.output || data,
        execution_time: performance.now() - startTime
      }
      
    } catch (error) {
      return {
        success: false,
        output: {
          error: error instanceof Error ? error.message : 'Unknown error'
        },
        execution_time: performance.now() - startTime
      }
    }
  }
  
  /**
   * Describe the cell's capabilities and metadata
   * 
   * @returns Cell metadata
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'content-explorer-cell',
      name: 'Content Explorer',
      description: 'Browse and manage assets by content type',
      version: '1.0.0',
      tags: ['content', 'assets', 'browser', 'explorer'],
      inputs: {
        type: 'object',
        properties: {
          action: {
            type: 'string',
            enum: ['list'],
            default: 'list',
            description: 'Action to perform'
          },
          selected_type_id: {
            type: 'string',
            description: 'Optional content type ID to filter assets'
          },
          filters: {
            type: 'object',
            properties: {
              assignee_id: {
                type: 'string',
                description: 'Filter by assignee'
              },
              tags: {
                type: 'array',
                items: { type: 'string' },
                description: 'Filter by tags'
              },
              is_latest: {
                type: 'boolean',
                default: true,
                description: 'Show only latest versions'
              }
            }
          },
          limit: {
            type: 'number',
            minimum: 1,
            maximum: 100,
            default: 20,
            description: 'Max assets to return'
          },
          offset: {
            type: 'number',
            minimum: 0,
            default: 0,
            description: 'Pagination offset'
          }
        },
        required: ['action']
      },
      outputs: {
        type: 'object',
        properties: {
          types: {
            type: 'object',
            description: 'Available content types'
          },
          assets: {
            type: 'object',
            description: 'Assets for selected type (if any)'
          },
          selected_type_id: {
            type: 'string',
            description: 'Currently selected type ID'
          }
        }
      }
    }
  }
  
  /**
   * Validate input parameters
   * 
   * @param input - Input to validate
   * @returns Array of validation errors (empty if valid)
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    
    // Validate action
    const action = input.action || 'list'
    if (action !== 'list') {
      errors.push({
        field: 'action',
        message: `Invalid action '${action}'. Only 'list' is supported.`
      })
    }
    
    // Validate limit if provided
    if (input.limit !== undefined) {
      const limit = Number(input.limit)
      if (isNaN(limit) || limit < 1 || limit > 100) {
        errors.push({
          field: 'limit',
          message: 'Limit must be between 1 and 100'
        })
      }
    }
    
    // Validate offset if provided
    if (input.offset !== undefined) {
      const offset = Number(input.offset)
      if (isNaN(offset) || offset < 0) {
        errors.push({
          field: 'offset',
          message: 'Offset must be >= 0'
        })
      }
    }
    
    return errors
  }
  
  /**
   * Optional: Setup the cell environment
   * 
   * @param config - Environment configuration
   */
  async setup(config: EnvironmentConfig): Promise<void> {
    // No setup required for ephemeral cell
  }
  
  /**
   * Optional: Cleanup resources
   */
  async teardown(): Promise<void> {
    // No cleanup required for ephemeral cell
  }
  
  /**
   * Optional: Health check
   * 
   * @returns Health status
   */
  async health_check(): Promise<HealthCheckResult> {
    try {
      // Verify backend is reachable
      // Using apiFetch ensures Authorization header is included automatically
      const response = await apiFetch('/api/health', {
        method: 'GET'
      })
      
      if (response.ok) {
        return {
          status: 'healthy',
          can_execute: true
        }
      } else {
        return {
          status: 'unavailable',
          can_execute: false,
          reason: 'Backend not responding'
        }
      }
    } catch (error) {
      return {
        status: 'unavailable',
        can_execute: false,
        reason: error instanceof Error ? error.message : 'Health check failed'
      }
    }
  }
}

/**
 * Create a new ContentExplorerCell instance
 */
export function createContentExplorerCell(): ContentExplorerCell {
  return new ContentExplorerCell()
}
