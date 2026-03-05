/**
 * Users Actions
 * 
 * Actions for user management: list_users, get_user_cells, save_user_layout, get_user_layout
 */

import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'

const log = createLogger('action:users')

/**
 * Register users management actions
 * @param {Function} registerAction - Function to register an action
 */
export function registerUsersActions(registerAction) {
  // Action: List Users
  registerAction(
    'list_users',
    async (params, ctx) => {
      const { page = 1, limit = 20 } = params
      
      log.debug('list_users - Fetching users list:', { page, limit })
      
      try {
        const queryParams = new URLSearchParams({
          page: page.toString(),
          limit: limit.toString()
        })
        
        const response = await apiService.fetch(`/api/users/?${queryParams}`)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the users list for display
        let formattedOutput = `👥 **Users List** (${data.length} user${data.length !== 1 ? 's' : ''} on page ${page})\n\n`
        
        if (data.length === 0) {
          formattedOutput += '*No users found on this page*'
        } else {
          data.forEach(user => {
            formattedOutput += `**${user.name}**\n`
            formattedOutput += `  ID: ${user.id}\n`
            formattedOutput += `  Email: ${user.email}\n`
            if (user.galaxy) {
              formattedOutput += `  Galaxy: ${user.galaxy}\n`
            }
            if (user.roles && user.roles.length > 0) {
              formattedOutput += `  Roles: ${user.roles.join(', ')}\n`
            }
            if (user.created_at) {
              const createdDate = new Date(user.created_at).toLocaleDateString()
              formattedOutput += `  Created: ${createdDate}\n`
            }
            formattedOutput += '\n'
          })
          
          // Add pagination hint
          formattedOutput += `\n📄 **Page ${page}** (${limit} items per page)\n`
          if (data.length === limit) {
            formattedOutput += `💡 *More users may be available. Use page=${page + 1} to see next page.*`
          }
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length > 5000) {
            const filename = `users_list_page${page}_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('list_users - Results attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          }
        }
        
        log.success('list_users - Users list fetched successfully:', { count: data.length, page })
        return { success: true, data, message: `Retrieved ${data.length} users (page ${page})` }
      } catch (error) {
        log.error('list_users - Error:', error)
        throw new Error(`Failed to fetch users list: ${error.message}`)
      }
    },
    {
      description: 'List all users with pagination (admin only)',
      params: [
        { name: 'page', type: 'integer', required: false },
        { name: 'limit', type: 'integer', required: false }
      ],
      category: 'users',
      available: true
    }
  )

  // Action: Get User Cells
  registerAction(
    'get_user_cells',
    async (params, ctx) => {
      const { user_id } = params
      
      if (!user_id) {
        throw new Error('user_id parameter is required')
      }
      
      log.debug('get_user_cells - Fetching cells for user:', { user_id })
      
      try {
        const response = await apiService.fetch(`/api/users/${encodeURIComponent(user_id)}/cells`)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const cells = await response.json()
        
        // Format the cells list for display
        let formattedOutput = `📋 **User Cells** (${cells.length} cell${cells.length !== 1 ? 's' : ''} found)\n\n`
        
        if (cells.length === 0) {
          formattedOutput += '*No cells found for this user*'
        } else {
          cells.forEach(cell => {
            const title = cell.title || cell.id
            formattedOutput += `**${title}**\n`
            formattedOutput += `  ID: ${cell.id}\n`
            if (cell.notebook_item_type_id) {
              formattedOutput += `  Type: ${cell.notebook_item_type_id}\n`
            }
            formattedOutput += `  Status: ${cell.status}\n`
            if (cell.category) {
              formattedOutput += `  Category: ${cell.category}\n`
            }
            if (cell.content) {
              const contentPreview = cell.content.length > 100 
                ? cell.content.substring(0, 100) + '...' 
                : cell.content
              formattedOutput += `  Content: ${contentPreview}\n`
            }
            if (cell.created_at) {
              const createdDate = new Date(cell.created_at).toLocaleDateString()
              formattedOutput += `  Created: ${createdDate}\n`
            }
            formattedOutput += '\n'
          })
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          // Use attachment for large cell lists or if total size exceeds 5KB
          if (cells.length >= 10 || formattedOutput.length > 5000) {
            const filename = `user_cells_${user_id.substring(0, 8)}_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('get_user_cells - Results attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          }
        }
        
        log.success('get_user_cells - Cells fetched successfully:', { count: cells.length, user_id })
        return { success: true, data: cells, message: `Retrieved ${cells.length} cells for user ${user_id}` }
      } catch (error) {
        log.error('get_user_cells - Error:', error)
        throw new Error(`Failed to fetch user cells: ${error.message}`)
      }
    },
    {
      description: 'Retrieve all cells owned by a specific user',
      params: [
        { name: 'user_id', type: 'string', required: true }
      ],
      category: 'users',
      available: true
    }
  )

  // Action: Save User Layout
  registerAction(
    'save_user_layout',
    async (params, ctx) => {
      const { user_id, layout } = params
      
      if (!user_id) {
        throw new Error('user_id parameter is required')
      }
      if (!layout || typeof layout !== 'object') {
        throw new Error('layout parameter is required and must be an object')
      }
      
      log.debug('save_user_layout - Saving layout for user:', { user_id })
      
      try {
        const response = await apiService.fetch(
          `/api/users/${encodeURIComponent(user_id)}/layout`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ layout })
          }
        )
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format success message
        const updatedAt = new Date(data.updated_at).toLocaleString()
        const formattedOutput = `✅ **Layout Saved Successfully**\n\n` +
          `User: ${user_id}\n` +
          `Updated: ${updatedAt}\n\n` +
          `Layout configuration has been saved and will persist across sessions.`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('save_user_layout - Layout saved successfully:', { user_id })
        return { success: true, data, message: `Layout saved for user ${user_id}` }
      } catch (error) {
        log.error('save_user_layout - Error:', error)
        
        // Provide user-friendly error messages
        let errorMessage = error.message
        if (error.message.includes('403') || error.message.includes('Forbidden')) {
          errorMessage = 'You can only save your own layout. Current user ID does not match target user ID.'
        } else if (error.message.includes('404') || error.message.includes('Not Found')) {
          errorMessage = 'User not found.'
        }
        
        throw new Error(`Failed to save user layout: ${errorMessage}`)
      }
    },
    {
      description: "Save user's dynamic workspace layout preferences",
      params: [
        { name: 'user_id', type: 'string', required: true },
        { name: 'layout', type: 'object', required: true }
      ],
      category: 'users',
      available: true
    }
  )

  // Action: Get User Layout
  registerAction(
    'get_user_layout',
    async (params, ctx) => {
      const { user_id } = params
      
      if (!user_id) {
        throw new Error('user_id parameter is required')
      }
      
      log.debug('get_user_layout - Fetching layout for user:', { user_id })
      
      try {
        const response = await apiService.fetch(`/api/users/${encodeURIComponent(user_id)}/layout`)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          
          // Handle 404 specially (no saved layout)
          if (response.status === 404) {
            const noLayoutMessage = `ℹ️ **No Saved Layout Found**\n\n` +
              `User: ${user_id}\n\n` +
              `No layout configuration has been saved yet.\n` +
              `The default workspace layout will be used.`
            
            const chatStore = ctx.chatStore
            if (chatStore) {
              chatStore.insertContentIntoInput({ content: noLayoutMessage })
            }
            
            return { success: true, data: null, message: 'No saved layout found' }
          }
          
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        const layout = data.layout
        
        // Format layout information for display
        const updatedAt = new Date(data.updated_at).toLocaleString()
        let formattedOutput = `🎨 **User Layout Configuration**\n\n`
        formattedOutput += `User: ${user_id}\n`
        formattedOutput += `Last Updated: ${updatedAt}\n\n`
        
        // Add layout details
        if (layout.version) {
          formattedOutput += `Layout version: ${layout.version}\n`
        }
        
        if (layout.gridLayout && Array.isArray(layout.gridLayout)) {
          formattedOutput += `\n**Grid Layout:**\n`
          formattedOutput += `- ${layout.gridLayout.length} cells configured\n`
          layout.gridLayout.forEach(item => {
            formattedOutput += `- ${item.i}: Position (${item.x},${item.y}), Size ${item.w}x${item.h}\n`
          })
        }
        
        if (layout.openCells && Array.isArray(layout.openCells)) {
          formattedOutput += `\n**Open Cells:** ${layout.openCells.length}\n`
          layout.openCells.forEach(cellId => {
            formattedOutput += `- ${cellId}\n`
          })
        }
        
        if (layout.activeCellId) {
          formattedOutput += `\n**Active Cell:** ${layout.activeCellId}\n`
        }
        
        if (typeof layout.footerVisible === 'boolean') {
          formattedOutput += `**Footer Visible:** ${layout.footerVisible ? 'Yes' : 'No'}\n`
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          // Use attachment for large layouts
          if (formattedOutput.length > 5000 || JSON.stringify(layout).length > 5000) {
            const filename = `user_layout_${user_id.substring(0, 8)}_${Date.now()}.json`
            chatStore.addAttachment(filename, JSON.stringify(layout, null, 2), 'json')
            log.debug('get_user_layout - Layout attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          }
        }
        
        log.success('get_user_layout - Layout fetched successfully:', { user_id })
        return { success: true, data, message: `Retrieved layout for user ${user_id}` }
      } catch (error) {
        log.error('get_user_layout - Error:', error)
        
        // Provide user-friendly error messages
        let errorMessage = error.message
        if (error.message.includes('403') || error.message.includes('Forbidden')) {
          errorMessage = 'You can only access your own layout. Current user ID does not match target user ID.'
        } else if (error.message.includes('404') || error.message.includes('Not Found')) {
          errorMessage = 'User not found or no saved layout exists.'
        }
        
        throw new Error(`Failed to fetch user layout: ${errorMessage}`)
      }
    },
    {
      description: "Retrieve user's saved dynamic workspace layout preferences",
      params: [
        { name: 'user_id', type: 'string', required: true }
      ],
      category: 'users',
      available: true
    }
  )
}
