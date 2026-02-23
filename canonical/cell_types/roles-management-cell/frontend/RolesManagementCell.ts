/**
 * @file RolesManagementCell.ts
 * @description Roles Management Cell - BaseCell implementation for RBAC role management
 * 
 * Provides secure, permission-protected interface for managing system roles and permissions.
 * Requires 'roles:admin' permission for all operations.
 * 
 * Part of BaseCell v1.0 Framework - Admin cells category
 */

import { BaseCell } from '@/types/BaseCell'
import type {
  CellResult,
  CellMetadata,
  ValidationError,
  HealthCheckResult
} from '@/types/BaseCell'
import { apiFetch } from '@/services/apiService'
import { useAuthStore } from '@/stores/auth'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:RolesManagement')

/**
 * Roles Management actions
 */
export type RolesManagementAction = 'list' | 'get' | 'create' | 'update' | 'delete' | 'assign' | 'unassign'

/**
 * Role data structure
 */
export interface RoleData {
  name: string
  permissions: string[]
  description?: string
}

/**
 * Input for roles management cell
 */
export interface RolesManagementInput {
  action: RolesManagementAction
  roleId?: string
  userId?: string
  data?: RoleData
}

/**
 * Roles Management Cell
 * 
 * RBAC-protected cell for managing system roles and permissions.
 * All operations require 'roles:admin' permission.
 */
export class RolesManagementCell extends BaseCell {
  /**
   * Check if user has required permission
   * @private
   */
  private async checkPermission(permission: string): Promise<boolean> {
    const authStore = useAuthStore()
    
    if (!authStore.isAuthenticated || !authStore.currentUser) {
      log.warn('Permission check failed: User not authenticated')
      return false
    }
    
    try {
      const { usePermissions } = await import('@/composables/usePermissions')
      const permissions = usePermissions()
      const hasPermission = await permissions.can(permission)
      
      log.debug('Permission check', {
        permission,
        hasPermission,
        user: authStore.currentUser.email
      })
      
      return hasPermission
    } catch (error) {
      log.error('Permission check error', error)
      return false
    }
  }

  /**
   * Execute roles management action
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = Date.now()
    
    // MANDATORY: Check permission FIRST
    const hasPermission = await this.checkPermission('roles:admin')
    if (!hasPermission) {
      return {
        success: false,
        output: {
          message: 'Permission denied: roles:admin required'
        },
        error: 'Permission denied: roles:admin required',
        execution_time: Date.now() - startTime
      }
    }
    
    // Validate input
    const errors = this.validate(input)
    if (errors.length > 0) {
      return {
        success: false,
        output: {
          errors
        },
        error: 'Validation failed',
        execution_time: Date.now() - startTime
      }
    }
    
    const { action, roleId, userId, data } = input as RolesManagementInput
    
    try {
      let result: any
      
      switch (action) {
        case 'list':
          result = await apiFetch('/api/roles')
          break
          
        case 'get':
          if (!roleId) throw new Error('roleId required for get action')
          result = await apiFetch(`/api/roles/${roleId}`)
          break
          
        case 'create':
          if (!data) throw new Error('data required for create action')
          result = await apiFetch('/api/roles', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
          })
          break
          
        case 'update':
          if (!roleId) throw new Error('roleId required for update action')
          if (!data) throw new Error('data required for update action')
          result = await apiFetch(`/api/roles/${roleId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
          })
          break
          
        case 'delete':
          if (!roleId) throw new Error('roleId required for delete action')
          await apiFetch(`/api/roles/${roleId}`, {
            method: 'DELETE'
          })
          result = { roleId, deleted: true }
          break
          
        case 'assign':
          if (!roleId) throw new Error('roleId required for assign action')
          if (!userId) throw new Error('userId required for assign action')
          result = await apiFetch(`/api/roles/${roleId}/assign`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ userId })
          })
          break
          
        case 'unassign':
          if (!roleId) throw new Error('roleId required for unassign action')
          if (!userId) throw new Error('userId required for unassign action')
          result = await apiFetch(`/api/roles/${roleId}/unassign`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ userId })
          })
          break
          
        default:
          throw new Error(`Invalid action: ${action}`)
      }
      
      log.info('Roles management action executed', {
        action,
        roleId,
        userId,
        success: true
      })
      
      return {
        success: true,
        output: {
          action,
          data: result
        },
        execution_time: Date.now() - startTime
      }
    } catch (error: any) {
      log.error('Roles management action failed', {
        action,
        error: error.message
      })
      
      return {
        success: false,
        output: {
          message: error.message
        },
        error: error.message,
        execution_time: Date.now() - startTime
      }
    }
  }

  /**
   * Describe cell capabilities and metadata
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'roles-management-cell',
      name: 'Roles Management',
      description: 'Manage system roles and permissions (RBAC-protected)',
      version: '1.0.0',
      category: 'admin',
      tags: ['admin', 'roles', 'permissions', 'rbac', 'user-management'],
      author: 'ScareVerse',
      requiredPermissions: ['roles:admin'],
      inputs: {
        action: {
          type: 'enum',
          required: true,
          values: ['list', 'get', 'create', 'update', 'delete', 'assign', 'unassign'],
          description: 'Action to perform'
        },
        roleId: {
          type: 'string',
          required: false,
          description: 'Role ID for get/update/delete/assign/unassign'
        },
        userId: {
          type: 'string',
          required: false,
          description: 'User ID for assign/unassign'
        },
        data: {
          type: 'object',
          required: false,
          description: 'Role data for create/update'
        }
      },
      outputs: {
        success: { type: 'boolean' },
        action: { type: 'string' },
        data: { type: 'object' },
        error: { type: 'string' }
      },
      resources: {
        mongodb: {
          required: true,
          description: 'MongoDB for role storage'
        }
      }
    }
  }

  /**
   * Validate input before execution
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    
    // Action is required
    if (!input.action) {
      errors.push({
        field: 'action',
        message: 'Action is required'
      })
      return errors
    }
    
    // Validate action value
    const validActions: RolesManagementAction[] = [
      'list', 'get', 'create', 'update', 'delete', 'assign', 'unassign'
    ]
    if (!validActions.includes(input.action)) {
      errors.push({
        field: 'action',
        message: `Invalid action. Must be one of: ${validActions.join(', ')}`
      })
      return errors
    }
    
    const { action, roleId, userId, data } = input as RolesManagementInput
    
    // Per-action validation
    switch (action) {
      case 'get':
      case 'update':
      case 'delete':
        if (!roleId) {
          errors.push({
            field: 'roleId',
            message: `roleId is required for ${action} action`
          })
        }
        break
        
      case 'create':
      case 'update':
        if (!data) {
          errors.push({
            field: 'data',
            message: `data is required for ${action} action`
          })
        } else {
          if (!data.name) {
            errors.push({
              field: 'data.name',
              message: 'Role name is required'
            })
          }
          if (!data.permissions || !Array.isArray(data.permissions)) {
            errors.push({
              field: 'data.permissions',
              message: 'Permissions array is required'
            })
          }
        }
        break
        
      case 'assign':
      case 'unassign':
        if (!roleId) {
          errors.push({
            field: 'roleId',
            message: `roleId is required for ${action} action`
          })
        }
        if (!userId) {
          errors.push({
            field: 'userId',
            message: `userId is required for ${action} action`
          })
        }
        break
    }
    
    return errors
  }

  /**
   * Health check - verify cell can execute
   */
  async health_check(): Promise<HealthCheckResult> {
    try {
      const hasPermission = await this.checkPermission('roles:admin')
      
      if (!hasPermission) {
        return {
          status: 'unavailable',
          message: 'Permission denied: roles:admin required',
          details: {
            permission: 'roles:admin',
            granted: false
          }
        }
      }
      
      return {
        status: 'healthy',
        message: 'Cell ready to execute',
        details: {
          permission: 'roles:admin',
          granted: true
        }
      }
    } catch (error: any) {
      return {
        status: 'degraded',
        message: 'Health check failed',
        details: {
          error: error.message
        }
      }
    }
  }
}
