/**
 * Roles Actions
 * 
 * Actions for roles and permissions management:
 * - list_roles: List all available roles
 * - get_role: Get details of a specific role
 * - list_permissions: List all available permissions
 * - create_role: Create a new role with permissions
 * - update_role: Update an existing role's properties
 * - delete_role: Delete a custom role
 * - assign_role_to_user: Assign a role to a user
 * - remove_role_from_user: Remove a role from a user
 */

import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'

const log = createLogger('action:roles')

/**
 * Register roles management actions
 * @param {Function} registerAction - Function to register an action
 */
export function registerRolesActions(registerAction) {
  // Action: List Roles
  registerAction(
    'list_roles',
    async (params, ctx) => {
      log.debug('list_roles - Fetching roles list')
      
      try {
        const response = await apiService.fetch('/api/roles/')
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the roles list for display
        let formattedOutput = `👥 **Roles List** (${data.length} role${data.length !== 1 ? 's' : ''})\n\n`
        
        if (data.length === 0) {
          formattedOutput += '*No roles found*'
        } else {
          data.forEach(role => {
            formattedOutput += `**${role.name}**\n`
            formattedOutput += `  ID: ${role.id}\n`
            if (role.description) {
              formattedOutput += `  Description: ${role.description}\n`
            }
            if (role.permissions && role.permissions.length > 0) {
              formattedOutput += `  Permissions: ${role.permissions.length}\n`
              // List first few permissions
              const previewPerms = role.permissions.slice(0, 3)
              previewPerms.forEach(perm => {
                formattedOutput += `    • ${perm}\n`
              })
              if (role.permissions.length > 3) {
                formattedOutput += `    ... and ${role.permissions.length - 3} more\n`
              }
            }
            formattedOutput += '\n'
          })
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length > 5000) {
            const filename = `roles_list_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('list_roles - Results attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          }
        }
        
        log.success('list_roles - Roles list fetched successfully:', { count: data.length })
        return { success: true, data, message: `Retrieved ${data.length} roles` }
      } catch (error) {
        log.error('list_roles - Error:', error)
        throw new Error(`Failed to fetch roles list: ${error.message}`)
      }
    },
    {
      description: 'List all available roles in the system',
      params: [],
      category: 'roles',
      available: true
    }
  )
  
  // Action: Get Role
  registerAction(
    'get_role',
    async (params, ctx) => {
      const { role_name } = params
      
      if (!role_name) {
        throw new Error('Missing required parameter: role_name')
      }
      
      log.debug('get_role - Fetching role:', { role_name })
      
      try {
        const response = await apiService.fetch(`/api/roles/${encodeURIComponent(role_name)}`)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const role = await response.json()
        
        // Format role details
        let formattedOutput = `👥 **Role Details**\n\n`
        formattedOutput += `**Name:** ${role.name}\n`
        formattedOutput += `**ID:** ${role.id}\n`
        if (role.description) {
          formattedOutput += `**Description:** ${role.description}\n`
        }
        
        if (role.permissions && role.permissions.length > 0) {
          formattedOutput += `\n**Permissions** (${role.permissions.length}):\n`
          role.permissions.forEach(perm => {
            formattedOutput += `  • ${perm}\n`
          })
        } else {
          formattedOutput += `\n**Permissions:** None\n`
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('get_role - Role fetched successfully:', { role_name })
        return { success: true, data: role, message: 'Role retrieved successfully' }
      } catch (error) {
        log.error('get_role - Error:', error)
        throw new Error(`Failed to fetch role: ${error.message}`)
      }
    },
    {
      description: 'Get details of a specific role',
      params: [
        { name: 'role_name', type: 'string', required: true }
      ],
      category: 'roles',
      available: true
    }
  )
  
  // Action: List Permissions
  registerAction(
    'list_permissions',
    async (params, ctx) => {
      log.debug('list_permissions - Fetching permissions list')
      
      try {
        const response = await apiService.fetch('/api/roles/permissions/')
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the permissions list for display
        let formattedOutput = `🔐 **Permissions List** (${data.length} permission${data.length !== 1 ? 's' : ''})\n\n`
        
        if (data.length === 0) {
          formattedOutput += '*No permissions found*'
        } else {
          // Group permissions by resource (e.g., "cells", "books", etc.)
          const byResource = {}
          data.forEach(perm => {
            const parts = perm.name.split('.')
            const resource = parts[0] || 'other'
            if (!byResource[resource]) byResource[resource] = []
            byResource[resource].push(perm)
          })
          
          // Display by resource groups
          Object.entries(byResource).sort().forEach(([resource, perms]) => {
            formattedOutput += `**${resource.toUpperCase()}** (${perms.length})\n`
            perms.forEach(perm => {
              formattedOutput += `  • **${perm.name}**\n`
              if (perm.description) {
                formattedOutput += `    ${perm.description}\n`
              }
            })
            formattedOutput += '\n'
          })
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length > 5000) {
            const filename = `permissions_list_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('list_permissions - Results attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          }
        }
        
        log.success('list_permissions - Permissions list fetched successfully:', { count: data.length })
        return { success: true, data, message: `Retrieved ${data.length} permissions` }
      } catch (error) {
        log.error('list_permissions - Error:', error)
        throw new Error(`Failed to fetch permissions list: ${error.message}`)
      }
    },
    {
      description: 'List all available permissions in the system',
      params: [],
      category: 'roles',
      available: true
    }
  )
  
  // Action: Create Role
  registerAction(
    'create_role',
    async (params, ctx) => {
      const { name, description, permissions = [] } = params
      
      if (!name) {
        throw new Error('Missing required parameter: name')
      }
      if (!description) {
        throw new Error('Missing required parameter: description')
      }
      
      log.debug('create_role - Creating role:', { name, description, permissions })
      
      try {
        // Prepare role data
        const roleData = {
          name,
          description,
          permissions
        }
        
        const response = await apiService.fetch('/api/roles/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(roleData)
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          // Handle specific error cases
          if (response.status === 400 && errorData.detail?.includes('já existe')) {
            throw new Error(`Role '${name}' already exists`)
          }
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const role = await response.json()
        
        // Format success message
        let formattedOutput = `✅ **Role Created Successfully**\n\n`
        formattedOutput += `**Name:** ${role.name}\n`
        formattedOutput += `**ID:** ${role.id}\n`
        formattedOutput += `**Description:** ${role.description}\n`
        
        if (role.permissions && role.permissions.length > 0) {
          formattedOutput += `\n**Permissions** (${role.permissions.length}):\n`
          role.permissions.forEach(perm => {
            formattedOutput += `  • ${perm}\n`
          })
        } else {
          formattedOutput += `\n**Permissions:** None\n`
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('create_role - Role created successfully:', { name, id: role.id })
        return { success: true, data: role, message: 'Role created successfully' }
      } catch (error) {
        log.error('create_role - Error:', error)
        throw new Error(`Failed to create role: ${error.message}`)
      }
    },
    {
      description: 'Create a new role with specified permissions',
      params: [
        { name: 'name', type: 'string', required: true },
        { name: 'description', type: 'string', required: true },
        { name: 'permissions', type: 'array', required: false }
      ],
      category: 'roles',
      available: true
    }
  )
  
  // Action: Update Role
  registerAction(
    'update_role',
    async (params, ctx) => {
      const { role_id, name, description, permissions } = params
      
      if (!role_id) {
        throw new Error('Missing required parameter: role_id')
      }
      
      // Build update object with only provided fields
      const updateData = {}
      if (name !== undefined) updateData.name = name
      if (description !== undefined) updateData.description = description
      if (permissions !== undefined) updateData.permissions = permissions
      
      if (Object.keys(updateData).length === 0) {
        throw new Error('At least one field must be provided for update (name, description, or permissions)')
      }
      
      log.debug('update_role - Updating role:', { role_id, updateData })
      
      try {
        const response = await apiService.fetch(`/api/roles/${encodeURIComponent(role_id)}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(updateData)
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          // Handle specific error cases
          if (response.status === 404) {
            throw new Error('Role not found')
          }
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const role = await response.json()
        
        // Format success message
        let formattedOutput = `✅ **Role Updated Successfully**\n\n`
        formattedOutput += `**Name:** ${role.name}\n`
        formattedOutput += `**ID:** ${role.id}\n`
        formattedOutput += `**Description:** ${role.description}\n`
        
        if (role.permissions && role.permissions.length > 0) {
          formattedOutput += `\n**Permissions** (${role.permissions.length}):\n`
          role.permissions.forEach(perm => {
            formattedOutput += `  • ${perm}\n`
          })
        } else {
          formattedOutput += `\n**Permissions:** None\n`
        }
        
        formattedOutput += `\n💡 *Permission cache has been invalidated for all users with this role.*`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('update_role - Role updated successfully:', { role_id })
        return { success: true, data: role, message: 'Role updated successfully' }
      } catch (error) {
        log.error('update_role - Error:', error)
        throw new Error(`Failed to update role: ${error.message}`)
      }
    },
    {
      description: 'Update an existing role\'s properties',
      params: [
        { name: 'role_id', type: 'string', required: true },
        { name: 'name', type: 'string', required: false },
        { name: 'description', type: 'string', required: false },
        { name: 'permissions', type: 'array', required: false }
      ],
      category: 'roles',
      available: true
    }
  )
  
  // Action: Delete Role
  registerAction(
    'delete_role',
    async (params, ctx) => {
      const { role_id } = params
      
      if (!role_id) {
        throw new Error('Missing required parameter: role_id')
      }
      
      log.debug('delete_role - Deleting role:', { role_id })
      
      try {
        const response = await apiService.fetch(`/api/roles/${encodeURIComponent(role_id)}`, {
          method: 'DELETE'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          // Handle specific error cases
          if (response.status === 404) {
            throw new Error('Role not found')
          }
          if (response.status === 400 && errorData.detail?.includes('padrão')) {
            throw new Error('Cannot delete system role (admin, user, viewer, guest)')
          }
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        // Format success message
        const formattedOutput = `✅ **Role Deleted Successfully**\n\n` +
          `Role **${role_id}** has been permanently deleted.\n\n` +
          `⚠️ *Users who had this role have lost those permissions immediately.*`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('delete_role - Role deleted successfully:', { role_id })
        return { success: true, message: 'Role deleted successfully' }
      } catch (error) {
        log.error('delete_role - Error:', error)
        throw new Error(`Failed to delete role: ${error.message}`)
      }
    },
    {
      description: 'Delete a custom role (cannot delete system roles)',
      params: [
        { name: 'role_id', type: 'string', required: true }
      ],
      category: 'roles',
      available: true
    }
  )
  
  // Action: Assign Role to User
  registerAction(
    'assign_role_to_user',
    async (params, ctx) => {
      const { user_id, role_name } = params
      
      if (!user_id) {
        throw new Error('Missing required parameter: user_id')
      }
      if (!role_name) {
        throw new Error('Missing required parameter: role_name')
      }
      
      log.debug('assign_role_to_user - Assigning role:', { user_id, role_name })
      
      try {
        const response = await apiService.fetch(
          `/api/roles/users/${encodeURIComponent(user_id)}/roles?role_name=${encodeURIComponent(role_name)}`,
          {
            method: 'PUT'
          }
        )
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          // Handle specific error cases
          if (response.status === 404) {
            if (errorData.detail?.includes('Role')) {
              throw new Error(`Role '${role_name}' not found`)
            }
            throw new Error('User not found')
          }
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const user = await response.json()
        
        // Format success message
        let formattedOutput = `✅ **Role Assigned Successfully**\n\n`
        formattedOutput += `**User ID:** ${user.id}\n`
        formattedOutput += `**Username:** ${user.username}\n`
        
        if (user.roles && user.roles.length > 0) {
          formattedOutput += `\n**Current Roles** (${user.roles.length}):\n`
          user.roles.forEach(role => {
            if (role === role_name) {
              formattedOutput += `  • **${role}** ⭐ (just assigned)\n`
            } else {
              formattedOutput += `  • ${role}\n`
            }
          })
        }
        
        formattedOutput += `\n💡 *User's permission cache has been invalidated. Changes are effective immediately.*`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('assign_role_to_user - Role assigned successfully:', { user_id, role_name })
        return { success: true, data: user, message: 'Role assigned successfully' }
      } catch (error) {
        log.error('assign_role_to_user - Error:', error)
        throw new Error(`Failed to assign role: ${error.message}`)
      }
    },
    {
      description: 'Assign a role to a user',
      params: [
        { name: 'user_id', type: 'string', required: true },
        { name: 'role_name', type: 'string', required: true }
      ],
      category: 'roles',
      available: true
    }
  )
  
  // Action: Remove Role from User
  registerAction(
    'remove_role_from_user',
    async (params, ctx) => {
      const { user_id, role_name } = params
      
      if (!user_id) {
        throw new Error('Missing required parameter: user_id')
      }
      if (!role_name) {
        throw new Error('Missing required parameter: role_name')
      }
      
      log.debug('remove_role_from_user - Removing role:', { user_id, role_name })
      
      try {
        const response = await apiService.fetch(
          `/api/roles/users/${encodeURIComponent(user_id)}/roles/${encodeURIComponent(role_name)}`,
          {
            method: 'DELETE'
          }
        )
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          // Handle specific error cases
          if (response.status === 404) {
            throw new Error('User not found')
          }
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const user = await response.json()
        
        // Format success message
        let formattedOutput = `✅ **Role Removed Successfully**\n\n`
        formattedOutput += `**User ID:** ${user.id}\n`
        formattedOutput += `**Username:** ${user.username}\n`
        formattedOutput += `**Removed Role:** ${role_name}\n`
        
        if (user.roles && user.roles.length > 0) {
          formattedOutput += `\n**Remaining Roles** (${user.roles.length}):\n`
          user.roles.forEach(role => {
            formattedOutput += `  • ${role}\n`
          })
        } else {
          formattedOutput += `\n⚠️ *User has no remaining roles.*`
        }
        
        formattedOutput += `\n💡 *User's permission cache has been invalidated. Changes are effective immediately.*`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('remove_role_from_user - Role removed successfully:', { user_id, role_name })
        return { success: true, data: user, message: 'Role removed successfully' }
      } catch (error) {
        log.error('remove_role_from_user - Error:', error)
        throw new Error(`Failed to remove role: ${error.message}`)
      }
    },
    {
      description: 'Remove a role from a user',
      params: [
        { name: 'user_id', type: 'string', required: true },
        { name: 'role_name', type: 'string', required: true }
      ],
      category: 'roles',
      available: true
    }
  )
}
