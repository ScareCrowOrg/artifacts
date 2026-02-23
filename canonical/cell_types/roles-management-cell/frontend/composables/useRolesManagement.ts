/**
 * @file useRolesManagement.ts
 * @description Composable for roles management CRUD operations
 * 
 * Provides reactive state and methods for managing roles via RolesManagementCell.
 * Handles loading states, error handling, and data caching.
 */

import { ref, computed } from 'vue'
import { RolesManagementCell } from '../RolesManagementCell'
import type { RoleData } from '../RolesManagementCell'
import { createLogger } from '@/utils/logger'

const log = createLogger('composables:useRolesManagement')

/**
 * Role interface
 */
export interface Role {
  id: string
  name: string
  permissions: string[]
  description?: string
  created_at?: string
  updated_at?: string
  user_count?: number
}

/**
 * Roles management composable
 */
export function useRolesManagement() {
  // State
  const roles = ref<Role[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const cell = new RolesManagementCell()

  // Computed
  const rolesCount = computed(() => roles.value.length)
  const hasRoles = computed(() => roles.value.length > 0)

  /**
   * Fetch all roles
   */
  async function fetchRoles(): Promise<void> {
    loading.value = true
    error.value = null
    
    try {
      const result = await cell.execute({ action: 'list' })
      
      if (!result.success) {
        throw new Error(result.error || 'Failed to fetch roles')
      }
      
      roles.value = result.output.data || []
      log.info('Roles fetched successfully', { count: roles.value.length })
    } catch (err: any) {
      error.value = err.message
      log.error('Failed to fetch roles', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Get specific role by ID
   */
  async function getRole(roleId: string): Promise<Role> {
    loading.value = true
    error.value = null
    
    try {
      const result = await cell.execute({ 
        action: 'get',
        roleId 
      })
      
      if (!result.success) {
        throw new Error(result.error || 'Failed to get role')
      }
      
      log.info('Role fetched successfully', { roleId })
      return result.output.data
    } catch (err: any) {
      error.value = err.message
      log.error('Failed to get role', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Create new role
   */
  async function createRole(data: RoleData): Promise<Role> {
    loading.value = true
    error.value = null
    
    try {
      const result = await cell.execute({ 
        action: 'create',
        data 
      })
      
      if (!result.success) {
        throw new Error(result.error || 'Failed to create role')
      }
      
      const newRole = result.output.data
      roles.value.push(newRole)
      
      log.info('Role created successfully', { roleId: newRole.id, name: data.name })
      return newRole
    } catch (err: any) {
      error.value = err.message
      log.error('Failed to create role', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Update existing role
   */
  async function updateRole(roleId: string, data: RoleData): Promise<Role> {
    loading.value = true
    error.value = null
    
    try {
      const result = await cell.execute({ 
        action: 'update',
        roleId,
        data 
      })
      
      if (!result.success) {
        throw new Error(result.error || 'Failed to update role')
      }
      
      const updatedRole = result.output.data
      
      // Update in local cache
      const index = roles.value.findIndex(r => r.id === roleId)
      if (index !== -1) {
        roles.value[index] = updatedRole
      }
      
      log.info('Role updated successfully', { roleId })
      return updatedRole
    } catch (err: any) {
      error.value = err.message
      log.error('Failed to update role', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Delete role
   */
  async function deleteRole(roleId: string): Promise<void> {
    loading.value = true
    error.value = null
    
    try {
      const result = await cell.execute({ 
        action: 'delete',
        roleId 
      })
      
      if (!result.success) {
        throw new Error(result.error || 'Failed to delete role')
      }
      
      // Remove from local cache
      roles.value = roles.value.filter(r => r.id !== roleId)
      
      log.info('Role deleted successfully', { roleId })
    } catch (err: any) {
      error.value = err.message
      log.error('Failed to delete role', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Assign role to user
   */
  async function assignRole(roleId: string, userId: string): Promise<void> {
    loading.value = true
    error.value = null
    
    try {
      const result = await cell.execute({ 
        action: 'assign',
        roleId,
        userId 
      })
      
      if (!result.success) {
        throw new Error(result.error || 'Failed to assign role')
      }
      
      log.info('Role assigned successfully', { roleId, userId })
    } catch (err: any) {
      error.value = err.message
      log.error('Failed to assign role', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Unassign role from user
   */
  async function unassignRole(roleId: string, userId: string): Promise<void> {
    loading.value = true
    error.value = null
    
    try {
      const result = await cell.execute({ 
        action: 'unassign',
        roleId,
        userId 
      })
      
      if (!result.success) {
        throw new Error(result.error || 'Failed to unassign role')
      }
      
      log.info('Role unassigned successfully', { roleId, userId })
    } catch (err: any) {
      error.value = err.message
      log.error('Failed to unassign role', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Clear error state
   */
  function clearError(): void {
    error.value = null
  }

  return {
    // State
    roles,
    loading,
    error,
    
    // Computed
    rolesCount,
    hasRoles,
    
    // Methods
    fetchRoles,
    getRole,
    createRole,
    updateRole,
    deleteRole,
    assignRole,
    unassignRole,
    clearError
  }
}
