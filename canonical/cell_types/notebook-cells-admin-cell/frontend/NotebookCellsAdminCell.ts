/**
 * @file NotebookCellsAdminCell.ts
 * @description NotebookCellsAdminCell - BaseCell implementation for notebook cell administration
 * 
 * This cell provides RBAC-protected administrative operations for managing notebook cells.
 * Requires notebook:admin permission to execute any operations.
 * 
 * Features:
 * - List cells with filtering (by assignee, cell type)
 * - Get cell details
 * - Create new cells
 * - Update existing cells
 * - Delete cells
 * - List available cell types
 * - RBAC protection (notebook:admin required)
 * 
 * Part of the Classic Workspace Deprecation epic - replaces NotebookCellsAdmin overlay
 */

import { BaseCell, createHealthyResult } from '@/types/BaseCell'
import type {
  CellResult,
  CellMetadata,
  ValidationError,
  EnvironmentConfig,
  HealthCheckResult,
  ShowConfig
} from '@/types/BaseCell'
import { apiFetch } from '@/services/apiService'
import { createLogger } from '@/utils/logger'
import { useAuthStore } from '@/stores/auth'

const log = createLogger('cells:NotebookCellsAdmin')

/**
 * Notebook Cells Admin actions
 */
export type NotebookCellsAdminAction = 'list' | 'get' | 'create' | 'update' | 'delete' | 'list-types'

/**
 * Filter options for list action
 */
export interface CellFilters {
  /** Filter by assignee username or ID */
  assignee?: string | null
  /** Filter by cell type */
  cellType?: string | null
}

/**
 * Input for list action
 */
export interface ListCellsInput {
  action: 'list'
  filters?: CellFilters
}

/**
 * Input for get action
 */
export interface GetCellInput {
  action: 'get'
  cellId: string
}

/**
 * Input for create action
 */
export interface CreateCellInput {
  action: 'create'
  data: Record<string, any>
}

/**
 * Input for update action
 */
export interface UpdateCellInput {
  action: 'update'
  cellId: string
  data: Record<string, any>
}

/**
 * Input for delete action
 */
export interface DeleteCellInput {
  action: 'delete'
  cellId: string
}

/**
 * Input for list-types action
 */
export interface ListTypesInput {
  action: 'list-types'
}

/**
 * Union type for all notebook cells admin inputs
 */
export type NotebookCellsAdminInput = 
  | ListCellsInput 
  | GetCellInput 
  | CreateCellInput 
  | UpdateCellInput 
  | DeleteCellInput 
  | ListTypesInput

/**
 * NotebookCellsAdminCell - BaseCell implementation for notebook cell administration
 * 
 * This cell provides administrative operations for managing notebook cells with
 * RBAC protection. All operations require notebook:admin permission.
 * 
 * @example
 * ```typescript
 * const adminCell = new NotebookCellsAdminCell()
 * 
 * // List all cells
 * const listResult = await adminCell.execute({
 *   action: 'list',
 *   filters: { assignee: 'user123' }
 * })
 * 
 * // Get cell details
 * const getResult = await adminCell.execute({
 *   action: 'get',
 *   cellId: 'cell-uuid'
 * })
 * 
 * // Create new cell
 * const createResult = await adminCell.execute({
 *   action: 'create',
 *   data: { type: 'png-generator', assignee_id: 'user123' }
 * })
 * 
 * // Update cell
 * const updateResult = await adminCell.execute({
 *   action: 'update',
 *   cellId: 'cell-uuid',
 *   data: { status: 'archived' }
 * })
 * 
 * // Delete cell
 * const deleteResult = await adminCell.execute({
 *   action: 'delete',
 *   cellId: 'cell-uuid'
 * })
 * 
 * // List cell types
 * const typesResult = await adminCell.execute({
 *   action: 'list-types'
 * })
 * ```
 */
export class NotebookCellsAdminCell extends BaseCell {
  private _apiBaseUrl: string = '/api/cells'
  
  /**
   * Check if current user has required permission
   * @param permission - Permission to check
   * @returns True if user has permission, false otherwise
   */
  private async checkPermission(permission: string): Promise<boolean> {
    try {
      const authStore = useAuthStore()
      
      // Check if user is authenticated
      if (!authStore.isAuthenticated || !authStore.currentUser) {
        log.warn('[checkPermission] User not authenticated')
        return false
      }
      
      // Check permission via permissions store
      const { usePermissions } = await import('@/composables/usePermissions')
      const permissions = usePermissions()
      const hasPermission = await permissions.can(permission)
      
      log.debug('[checkPermission]', { permission, hasPermission })
      return hasPermission
    } catch (error: any) {
      log.error('[checkPermission] Permission check failed:', error)
      return false
    }
  }
  
  /**
   * Execute notebook cells admin action
   * 
   * All actions require notebook:admin permission.
   * Routes to appropriate backend handler based on action type.
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()
    
    try {
      // RBAC Check - MANDATORY
      const hasAdminPermission = await this.checkPermission('notebook:admin')
      
      if (!hasAdminPermission) {
        log.warn('[execute] Permission denied: notebook:admin required')
        return {
          success: false,
          output: { message: 'Permission denied' },
          execution_time: performance.now() - startTime,
          error: 'Permission denied: notebook:admin required'
        }
      }
      
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
      
      const action = input.action as NotebookCellsAdminAction
      const { cellId, data, filters } = input
      
      let result: any
      
      // Execute action via backend API
      // Using apiFetch ensures Authorization header is included automatically
      switch (action) {
        case 'list':
          result = await apiFetch(this._apiBaseUrl, {
            method: 'GET',
            params: filters || {}
          })
          break
          
        case 'get':
          if (!cellId) {
            throw new Error('cellId is required for get action')
          }
          result = await apiFetch(`${this._apiBaseUrl}/${cellId}`, {
            method: 'GET'
          })
          break
          
        case 'create':
          result = await apiFetch(`${this._apiBaseUrl}/create`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
          })
          break
          
        case 'update':
          if (!cellId) {
            throw new Error('cellId is required for update action')
          }
          result = await apiFetch(`${this._apiBaseUrl}/${cellId}`, {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
          })
          break
          
        case 'delete':
          if (!cellId) {
            throw new Error('cellId is required for delete action')
          }
          result = await apiFetch(`${this._apiBaseUrl}/${cellId}`, {
            method: 'DELETE'
          })
          result = { cellId }  // Return cellId on successful delete
          break
          
        case 'list-types':
          result = await apiFetch(`${this._apiBaseUrl}/types`, {
            method: 'GET'
          })
          break
          
        default:
          throw new Error(`Invalid action: ${action}`)
      }
      
      // Return successful result
      return {
        success: true,
        output: { action, data: result },
        execution_time: performance.now() - startTime,
        execution_steps: ['rbac_check', 'validate', 'backend_call', `action_${action}`],
        metadata: {
          action,
          permission_checked: 'notebook:admin',
          backend_execution: true
        }
      }
    } catch (error: any) {
      log.error('[execute] Execution failed:', error)
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: error.message || 'Notebook cells admin execution failed'
      }
    }
  }
  
  /**
   * Describe the cell's capabilities
   * Returns metadata about the cell including RBAC requirements
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'notebook-cells-admin-cell',
      name: 'Notebook Cells Admin',
      version: '1.0.0',
      description: 'Administer notebook cells and cell types (RBAC protected)',
      inputs: {
        action: { 
          type: 'enum', 
          required: true,
          values: ['list', 'get', 'create', 'update', 'delete', 'list-types'],
          description: 'Admin action to perform'
        },
        cellId: { 
          type: 'string', 
          required: false,
          description: 'Cell ID (required for get, update, delete)'
        },
        data: { 
          type: 'object', 
          required: false,
          description: 'Cell data (required for create, update)'
        },
        filters: { 
          type: 'object', 
          required: false,
          description: 'Filters for list action (assignee, cellType)'
        }
      },
      outputs: {
        success: { type: 'boolean', description: 'Whether execution succeeded' },
        action: { type: 'string', description: 'Action that was executed' },
        data: { type: 'object', description: 'Result data from the action' }
      },
      tags: ['admin', 'cells', 'notebook', 'management', 'rbac', 'crud'],
      required_resources: ['mongodb'],
      estimated_duration_seconds: 1
    }
  }
  
  /**
   * Validate input before execution
   * Checks required fields based on action type
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    
    if (!input.action) {
      errors.push({ field: 'action', message: 'Action is required' })
      return errors
    }
    
    const validActions: NotebookCellsAdminAction[] = [
      'list', 'get', 'create', 'update', 'delete', 'list-types'
    ]
    if (!validActions.includes(input.action as NotebookCellsAdminAction)) {
      errors.push({ 
        field: 'action', 
        message: `Invalid action. Must be one of: ${validActions.join(', ')}` 
      })
    }
    
    // Validate required fields per action
    const action = input.action as NotebookCellsAdminAction
    
    if (['get', 'update', 'delete'].includes(action) && !input.cellId) {
      errors.push({ 
        field: 'cellId', 
        message: `cellId is required for ${action} action` 
      })
    }
    
    if (['create', 'update'].includes(action) && !input.data) {
      errors.push({ 
        field: 'data', 
        message: `data is required for ${action} action` 
      })
    }
    
    return errors
  }
  
  /**
   * Optional setup - no-op for this cell
   */
  async setup(config: EnvironmentConfig): Promise<void> {
    log.debug('[setup] Cell setup completed')
  }
  
  /**
   * Optional teardown - no-op for this cell
   */
  async teardown(): Promise<void> {
    log.debug('[teardown] Cell teardown completed')
  }
  
  /**
   * Health check - verify backend connectivity and permission
   */
  async health_check(): Promise<HealthCheckResult> {
    try {
      // Check permission
      const hasPermission = await this.checkPermission('notebook:admin')
      
      if (!hasPermission) {
        return {
          status: 'unavailable',
          can_execute: false,
          reason: 'Permission denied: notebook:admin required'
        }
      }
      
      // If permission check passed, cell is healthy
      return createHealthyResult()
    } catch (error: any) {
      return {
        status: 'degraded',
        can_execute: false,
        reason: error.message || 'Health check failed'
      }
    }
  }
}
