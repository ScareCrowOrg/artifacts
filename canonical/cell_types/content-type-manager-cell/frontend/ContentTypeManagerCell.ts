/**
 * @file ContentTypeManagerCell.ts
 * @description ContentTypeManagerCell - BaseCell implementation for content type discovery
 * 
 * This cell provides a reusable interface for listing available content types,
 * enabling other cells (ContentExplorerCell, etc.) to build type-aware asset browsers
 * and filters.
 * 
 * Features:
 * - List all available content types with metadata
 * - Ephemeral execution (no persistent cell instance required)
 * - Headless-first design (no UI component)
 * - Type-safe inputs and outputs
 * 
 * Part of content-type-manager-cell implementation following BaseCell interface
 */

import { BaseCell, createHealthyResult } from '@/types/BaseCell'
import type {
  CellResult,
  CellMetadata,
  ValidationError,
  EnvironmentConfig,
  HealthCheckResult
} from '@/types/BaseCell'
import { apiFetch } from '@/services/apiService'

/**
 * Content Type Manager actions
 */
export type ContentTypeManagerAction = 'list'

/**
 * Content Type metadata structure
 */
export interface ContentTypeMetadata {
  /** Unique content type identifier */
  id: string
  /** Human-readable name */
  name: string
  /** Description of the content type */
  description: string
  /** MIME type */
  mime_type: string
  /** Version number */
  version: string
  /** Maximum file size in bytes */
  max_size_bytes: number
  /** Allowed file extensions */
  allowed_extensions: string[]
  /** Optional rendering hints for frontend */
  render_hints?: Record<string, any>
}

/**
 * Input for list action
 */
export interface ListContentTypesInput {
  action: 'list'
  /** Optional limit for number of types to return (default: 100, max: 100) */
  limit?: number
}

/**
 * Union type for all content type manager inputs
 */
export type ContentTypeManagerInput = ListContentTypesInput

/**
 * Output for list action
 */
export interface ListContentTypesOutput {
  /** Array of content type metadata */
  types: ContentTypeMetadata[]
  /** Total number of content types available */
  total: number
}

/**
 * ContentTypeManagerCell - BaseCell implementation for content type discovery
 * 
 * This cell is designed as an ephemeral utility that can be imported and used
 * by other cells to discover available content types. It delegates execution
 * to the backend via the execute-ephemeral endpoint.
 */
export class ContentTypeManagerCell extends BaseCell {
  /**
   * Execute content type manager action
   * 
   * @param input - Action and parameters
   * @returns Cell result with content types or error
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()
    
    try {
      // Validate input
      const validationErrors = await this.validate(input)
      if (validationErrors.length > 0) {
        return {
          success: false,
          output: {
            error: 'Validation failed',
            validation_errors: validationErrors
          },
          execution_time: performance.now() - startTime
        }
      }
      
      // Type-cast after validation
      const typedInput = input as ContentTypeManagerInput
      
      // Route to action handler
      if (typedInput.action === 'list') {
        return await this.executeList(typedInput, startTime)
      }
      
      // Should never reach here after validation
      return {
        success: false,
        output: {
          error: `Unknown action: ${typedInput.action}`
        },
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
   * Execute list action
   * 
   * @param input - List input parameters
   * @param startTime - Execution start time for metrics
   * @returns Cell result with content types
   */
  private async executeList(
    input: ListContentTypesInput, 
    startTime: number
  ): Promise<CellResult> {
    try {
      // Call backend execute-ephemeral endpoint
      // Using apiFetch ensures Authorization header is included automatically
      const response = await apiFetch('/api/cells/execute-ephemeral', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          cell_type: 'content-type-manager-cell',
          input_data: {
            action: 'list',
            limit: input.limit || 100
          }
        })
      })
      
      if (!response.ok) {
        const errorText = await response.text()
        return {
          success: false,
          output: {
            error: `API request failed: ${response.status} - ${errorText}`
          },
          execution_time: performance.now() - startTime
        }
      }
      
      const result = await response.json()
      
      if (!result.success) {
        return {
          success: false,
          output: {
            error: result.error || 'Unknown error from backend'
          },
          execution_time: performance.now() - startTime
        }
      }

      // Return successful result
      // Result structure: { success, output, ... } or legacy { success, data, ... }
      return {
        success: true,
        output: result.output || result.data || {},
        execution_time: performance.now() - startTime
      }
      
    } catch (error) {
      return {
        success: false,
        output: {
          error: error instanceof Error ? error.message : 'Network error'
        },
        execution_time: performance.now() - startTime
      }
    }
  }
  
  /**
   * Describe cell capabilities
   *
   * @returns Cell metadata
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'content-type-manager-cell',
      name: 'Content Type Manager',
      version: '1.0.0',
      description: 'List available content types with metadata',
      inputs: {
        action: {
          type: 'string',
          required: true,
          description: 'Action to perform (list)'
        },
        limit: {
          type: 'number',
          required: false,
          description: 'Maximum number of types to return (default: 100, max: 100)'
        }
      },
      outputs: {
        types: {
          type: 'array',
          description: 'Array of content type metadata objects'
        },
        total: {
          type: 'number',
          description: 'Total number of content types available'
        }
      },
      tags: ['content-types', 'metadata', 'utility']
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
    
    // Check action is present
    if (!input.action) {
      errors.push({
        field: 'action',
        message: 'Action is required'
      })
      return errors
    }
    
    // Check action is valid
    if (input.action !== 'list') {
      errors.push({
        field: 'action',
        message: `Invalid action '${input.action}'. Must be: list`
      })
      return errors
    }
    
    // Validate limit if provided
    if (input.limit !== undefined) {
      if (typeof input.limit !== 'number') {
        errors.push({
          field: 'limit',
          message: 'Limit must be a number'
        })
      } else if (input.limit < 1 || input.limit > 100) {
        errors.push({
          field: 'limit',
          message: 'Limit must be between 1 and 100'
        })
      }
    }
    
    return errors
  }
  
  /**
   * Setup cell (optional)
   * No setup required for this ephemeral cell
   */
  async setup(config?: EnvironmentConfig): Promise<void> {
    // No setup needed
  }
  
  /**
   * Teardown cell (optional)
   * No teardown required for this ephemeral cell
   */
  async teardown(): Promise<void> {
    // No teardown needed
  }
  
  /**
   * Health check (optional)
   * 
   * @returns Health check result
   */
  async health_check(): Promise<HealthCheckResult> {
    return createHealthyResult()
  }
}

/**
 * Create a new ContentTypeManagerCell instance
 * 
 * @returns New cell instance
 */
export function createContentTypeManagerCell(): ContentTypeManagerCell {
  return new ContentTypeManagerCell()
}
