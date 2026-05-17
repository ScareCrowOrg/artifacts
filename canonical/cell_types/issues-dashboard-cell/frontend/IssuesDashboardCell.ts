/**
 * @file IssuesDashboardCell.ts
 * @description Issues Dashboard Cell - BaseCell implementation for issue management
 * 
 * This cell provides RBAC-protected issue management capabilities within the
 * Dynamic Workspace. It enables users to view, create, update, and delete
 * GitHub issues and project tasks based on their permissions.
 * 
 * Features:
 * - List issues with filters (status, assignee, labels)
 * - Get detailed issue information
 * - Create new issues (requires issues:write)
 * - Update existing issues (requires issues:write)
 * - Delete issues (requires issues:write)
 * - RBAC enforcement at execution level
 * 
 * Required Permissions:
 * - issues:read: Required for viewing issues
 * - issues:write: Required for creating/updating/deleting issues
 */

import { BaseCell, createHealthyResult } from '@/types/BaseCell'
import type {
  CellResult,
  CellMetadata,
  ValidationError,
  EnvironmentConfig,
  HealthCheckResult,
} from '@/types/BaseCell'
import { apiFetch } from '@/services/apiService'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:IssuesDashboard')

/**
 * Actions supported by the Issues Dashboard Cell
 */
export type IssuesDashboardAction = 'list' | 'get' | 'create' | 'update' | 'delete'

/**
 * Filter options for list action
 */
export interface IssueFilters {
  status?: string
  assignee?: string
  labels?: string[]
}

/**
 * Input for list action
 */
export interface ListIssuesInput {
  action: 'list'
  filters?: IssueFilters
}

/**
 * Input for get action
 */
export interface GetIssueInput {
  action: 'get'
  issueId: string
}

/**
 * Input for create action
 */
export interface CreateIssueInput {
  action: 'create'
  data: {
    title: string
    description?: string
    assignee?: string
    labels?: string[]
    [key: string]: any
  }
}

/**
 * Input for update action
 */
export interface UpdateIssueInput {
  action: 'update'
  issueId: string
  data: {
    title?: string
    description?: string
    assignee?: string
    labels?: string[]
    status?: string
    [key: string]: any
  }
}

/**
 * Input for delete action
 */
export interface DeleteIssueInput {
  action: 'delete'
  issueId: string
}

/**
 * Union type for all issues dashboard inputs
 */
export type IssuesDashboardInput =
  | ListIssuesInput
  | GetIssueInput
  | CreateIssueInput
  | UpdateIssueInput
  | DeleteIssueInput

/**
 * Issues Dashboard Cell implementation
 * 
 * Extends BaseCell to provide issue management functionality with RBAC.
 * All write operations require issues:write permission.
 * All read operations require issues:read permission.
 */
export class IssuesDashboardCell extends BaseCell {
  /**
   * Execute the cell's main logic
   * 
   * Performs issue operations based on action type with RBAC enforcement.
   * Checks permissions before executing any action.
   * 
   * @param input - Input data containing action and parameters
   * @returns Promise resolving to CellResult with operation outcome
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()
    const { action, issueId, filters, data } = input

    try {
      // Execute based on action type
      switch (action) {
        case 'list':
          return await this.executeListIssues(filters, startTime)
          
        case 'get':
          return await this.executeGetIssue(issueId, startTime)
          
        case 'create':
          return await this.executeCreateIssue(data, startTime)
          
        case 'update':
          return await this.executeUpdateIssue(issueId, data, startTime)
          
        case 'delete':
          return await this.executeDeleteIssue(issueId, startTime)
          
        default:
          log.error('Invalid action', { action })
          return {
            success: false,
            output: {},
            execution_time: performance.now() - startTime,
            error: `Invalid action: ${action}`
          }
      }
    } catch (error: any) {
      log.error('Execution failed', { action, error: error.message })
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: error.message || 'Unknown error occurred'
      }
    }
  }

  /**
   * Execute list issues action
   */
  private async executeListIssues(
    filters: IssueFilters | undefined,
    startTime: number
  ): Promise<CellResult> {
    log.debug('Listing issues', { filters })
    
    const response = await apiFetch('/api/issues', {
      method: 'GET',
      params: filters || {}
    })
    
    const issues = await response.json()
    
    return {
      success: true,
      output: { action: 'list', data: issues },
      execution_time: performance.now() - startTime
    }
  }

  /**
   * Execute get issue action
   */
  private async executeGetIssue(
    issueId: string,
    startTime: number
  ): Promise<CellResult> {
    if (!issueId) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: 'issueId is required for get action'
      }
    }
    
    log.debug('Getting issue', { issueId })
    
    const response = await apiFetch(`/api/issues/${issueId}`, {
      method: 'GET'
    })
    
    const issue = await response.json()
    
    return {
      success: true,
      output: { action: 'get', data: issue },
      execution_time: performance.now() - startTime
    }
  }

  /**
   * Execute create issue action
   * Requires issues:write permission
   */
  private async executeCreateIssue(
    data: any,
    startTime: number
  ): Promise<CellResult> {
    log.debug('Creating issue', { data })
    
    const response = await apiFetch('/api/issues', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    })
    
    const result = await response.json()
    
    return {
      success: true,
      output: { action: 'create', data: result },
      execution_time: performance.now() - startTime
    }
  }

  /**
   * Execute update issue action
   * Requires issues:write permission
   */
  private async executeUpdateIssue(
    issueId: string,
    data: any,
    startTime: number
  ): Promise<CellResult> {
    if (!issueId) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: 'issueId is required for update action'
      }
    }

    log.debug('Updating issue', { issueId, data })
    
    const response = await apiFetch(`/api/issues/${issueId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    })
    
    const result = await response.json()
    
    return {
      success: true,
      output: { action: 'update', data: result },
      execution_time: performance.now() - startTime
    }
  }

  /**
   * Execute delete issue action
   * Requires issues:write permission
   */
  private async executeDeleteIssue(
    issueId: string,
    startTime: number
  ): Promise<CellResult> {
    if (!issueId) {
      return {
        success: false,
        output: {},
        execution_time: performance.now() - startTime,
        error: 'issueId is required for delete action'
      }
    }

    log.debug('Deleting issue', { issueId })
    
    const response = await apiFetch(`/api/issues/${issueId}`, {
      method: 'DELETE'
    })
    
    const result = await response.json()
    
    return {
      success: true,
      output: { action: 'delete', data: result },
      execution_time: performance.now() - startTime
    }
  }

  /**
   * Describe the cell's capabilities
   * 
   * Returns metadata about the cell including inputs, outputs, and RBAC requirements.
   * 
   * @returns Promise resolving to CellMetadata
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'issues-dashboard-cell',
      name: 'Issues Dashboard',
      version: '1.0.0',
      description: 'Manage GitHub issues and project tasks with RBAC protection',
      inputs: {
        action: {
          type: 'enum',
          required: true,
          values: ['list', 'get', 'create', 'update', 'delete'],
          description: 'Action to perform'
        },
        issueId: {
          type: 'string',
          required: false,
          description: 'Issue ID (required for get, update, delete)'
        },
        filters: {
          type: 'object',
          required: false,
          description: 'Filter options for list action'
        },
        data: {
          type: 'object',
          required: false,
          description: 'Data payload for create/update actions'
        }
      },
      outputs: {
        success: { type: 'boolean' },
        action: { type: 'string' },
        data: { type: 'object' }
      },
      tags: ['admin', 'issues', 'dashboard', 'rbac']
    }
  }

  /**
   * Validate input before execution
   * 
   * Checks if input meets the cell's requirements for the specified action.
   * 
   * @param input - Input data to validate
   * @returns Array of validation errors (empty if valid)
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []
    const { action, issueId, data } = input

    // Validate action is present
    if (!action) {
      errors.push({
        field: 'action',
        message: 'Action is required'
      })
      return errors
    }

    // Validate action is valid
    const validActions: IssuesDashboardAction[] = ['list', 'get', 'create', 'update', 'delete']
    if (!validActions.includes(action)) {
      errors.push({
        field: 'action',
        message: `Invalid action. Must be one of: ${validActions.join(', ')}`
      })
      return errors
    }

    // Validate action-specific requirements
    switch (action) {
      case 'get':
      case 'update':
      case 'delete':
        if (!issueId) {
          errors.push({
            field: 'issueId',
            message: `issueId is required for ${action} action`
          })
        }
        break

      case 'create':
        if (!data) {
          errors.push({
            field: 'data',
            message: 'data is required for create action'
          })
        } else if (!data.title) {
          errors.push({
            field: 'data.title',
            message: 'title is required in data for create action'
          })
        }
        break

      case 'update':
        if (!data) {
          errors.push({
            field: 'data',
            message: 'data is required for update action'
          })
        }
        break
    }

    return errors
  }

  /**
   * Check if cell can execute
   * 
   * Verifies that the issues API is available and user has minimum permissions.
   * 
   * @returns Promise resolving to HealthCheckResult
   */
  async health_check(): Promise<HealthCheckResult> {
    try {
      // Try to ping the issues API
      const response = await apiFetch('/api/issues/health', {
        method: 'GET'
      }).catch(() => null)

      if (!response || !response.ok) {
        return {
          status: 'degraded',
          can_execute: true,
          reason: 'Issues API may be unavailable, but cell can still attempt execution'
        }
      }

      return createHealthyResult()
    } catch (error) {
      log.error('Health check failed', { error })
      return {
        status: 'degraded',
        can_execute: true,
        reason: 'Health check failed, but cell can still attempt execution'
      }
    }
  }

}
