/**
 * Cell Actions
 * 
 * Actions for cell management: list_cells, get_cell, execute_cell,
 * update_cell, delete_cell, list_notebook_item_types
 */

import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'

const log = createLogger('action:cells')

// Constants
const MAX_INLINE_RESULT_LENGTH = 5000 // Max length before using attachments

/**
 * Register cell management actions
 * @param {Function} registerAction - Function to register an action
 */
export function registerCellActions(registerAction) {
  // Action: List Cells
  registerAction(
    'list_cells',
    async (params, ctx) => {
      const { assignee_id } = params
      
      log.debug('list_cells - Fetching cells list:', { assignee_id })
      
      try {
        const queryParams = assignee_id ? `?assignee_id=${encodeURIComponent(assignee_id)}` : ''
        const response = await apiService.fetch(`/api/cells/list${queryParams}`)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the cells list for display
        let formattedOutput = `📋 **Cells List** (${data.length} cell${data.length !== 1 ? 's' : ''})\n\n`
        
        if (data.length === 0) {
          formattedOutput += '*No cells found*'
        } else {
          // Group by status
          const byStatus = {}
          data.forEach(cell => {
            const status = cell.status || 'unknown'
            if (!byStatus[status]) byStatus[status] = []
            byStatus[status].push(cell)
          })
          
          // Display by status groups
          Object.entries(byStatus).forEach(([status, cells]) => {
            const statusIcon = {
              'pending': '⏳',
              'running': '🔄',
              'completed': '✅',
              'error': '❌'
            }[status] || '❓'
            
            formattedOutput += `**${statusIcon} ${status.toUpperCase()}** (${cells.length})\n`
            cells.forEach(cell => {
              const title = cell.title || cell.id.substring(0, 8)
              formattedOutput += `  • ${title}\n`
              formattedOutput += `    ID: ${cell.id}\n`
              if (cell.notebook_item_type_id) {
                formattedOutput += `    Type: ${cell.notebook_item_type_id}\n`
              }
              formattedOutput += `    Assignee: ${cell.assignee_id}\n`
            })
            formattedOutput += '\n'
          })
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length > MAX_INLINE_RESULT_LENGTH) {
            const filename = `cells_list_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('list_cells - Results attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          }
        }
        
        log.success('list_cells - Cells list fetched successfully:', { count: data.length })
        return { success: true, data, message: `Retrieved ${data.length} cells` }
      } catch (error) {
        log.error('list_cells - Error:', error)
        throw new Error(`Failed to fetch cells list: ${error.message}`)
      }
    },
    {
      description: 'List cells with RBAC filtering',
      params: [
        { name: 'assignee_id', type: 'string', required: false }
      ],
      category: 'cells',
      available: true
    }
  )
  
  // Action: Get Cell
  registerAction(
    'get_cell',
    async (params, ctx) => {
      const { cell_id } = params
      
      if (!cell_id) {
        throw new Error('Required parameter: cell_id')
      }
      
      log.debug('get_cell - Fetching cell details:', { cell_id })
      
      try {
        const response = await apiService.fetch(`/api/cells/${encodeURIComponent(cell_id)}`)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format cell details for display
        const statusIcon = {
          'pending': '⏳',
          'running': '🔄',
          'completed': '✅',
          'error': '❌'
        }[data.status] || '❓'
        
        let formattedOutput = `🔍 **Cell Details**\n\n`
        formattedOutput += `**ID:** ${data.id}\n`
        formattedOutput += `**Status:** ${statusIcon} ${data.status}\n`
        formattedOutput += `**Title:** ${data.title || '*(No title)*'}\n`
        formattedOutput += `**Assignee:** ${data.assignee_id}\n`
        
        if (data.notebook_item_type_id) {
          formattedOutput += `**Type:** ${data.notebook_item_type_id}\n`
        }
        
        if (data.source_book_id) {
          formattedOutput += `**Source Book:** ${data.source_book_id}\n`
        }
        
        if (data.created_at) {
          formattedOutput += `**Created:** ${data.created_at}\n`
        }
        
        if (data.updated_at) {
          formattedOutput += `**Updated:** ${data.updated_at}\n`
        }
        
        // Content
        const MAX_DISPLAY_LENGTH = 500
        if (data.content) {
          const contentPreview = data.content.length > MAX_DISPLAY_LENGTH 
            ? `${data.content.substring(0, MAX_DISPLAY_LENGTH)}...` 
            : data.content
          formattedOutput += `\n**Content:**\n\`\`\`\n${contentPreview}\n\`\`\`\n`
        }
        
        // Initial Data
        if (data.initial_data && Object.keys(data.initial_data).length > 0) {
          const jsonStr = JSON.stringify(data.initial_data, null, 2)
          const jsonPreview = jsonStr.length > MAX_DISPLAY_LENGTH 
            ? `${jsonStr.substring(0, MAX_DISPLAY_LENGTH)}...` 
            : jsonStr
          formattedOutput += `\n**Initial Data:**\n\`\`\`json\n${jsonPreview}\n\`\`\`\n`
        }
        
        // Fragments
        if (data.fragments && data.fragments.length > 0) {
          formattedOutput += `\n**Fragments:** ${data.fragments.length} fragment(s)\n`
        }
        
        // Refs
        if (data.refs && Object.keys(data.refs).length > 0) {
          formattedOutput += `**Refs:** ${Object.keys(data.refs).length} reference(s)\n`
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length > 5000) {
            const filename = `cell_${cell_id.substring(0, 8)}_details.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('get_cell - Results attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          }
        }
        
        log.success('get_cell - Cell details fetched successfully')
        return { success: true, data, message: 'Cell details retrieved successfully' }
      } catch (error) {
        log.error('get_cell - Error:', error)
        throw new Error(`Failed to fetch cell details: ${error.message}`)
      }
    },
    {
      description: 'Get detailed information about a specific cell',
      params: [
        { name: 'cell_id', type: 'string', required: true }
      ],
      category: 'cells',
      available: true
    }
  )
  
  // Action: Execute Cell
  registerAction(
    'execute_cell',
    async (params, ctx) => {
      const { cell_id, parameters } = params
      
      if (!cell_id) {
        throw new Error('Required parameter: cell_id')
      }
      
      log.debug('execute_cell - Executing cell:', { cell_id, parameters })
      
      try {
        const response = await apiService.fetch(`/api/cells/${encodeURIComponent(cell_id)}/execute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ parameters: parameters || {} })
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        const statusIcon = {
          'completed': '✅',
          'error': '❌',
          'running': '🔄'
        }[data.status] || '❓'
        
        const formattedOutput = `▶️ **Cell Execution Result**\n\n` +
          `**Cell ID:** ${data.id}\n` +
          `**Status:** ${statusIcon} ${data.status}\n` +
          `**Fragments:** ${data.fragments?.length || 0} fragment(s)\n` +
          `\n✅ Execution completed successfully`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('execute_cell - Cell executed successfully')
        return { success: true, data, message: 'Cell executed successfully' }
      } catch (error) {
        log.error('execute_cell - Error:', error)
        throw new Error(`Failed to execute cell: ${error.message}`)
      }
    },
    {
      description: 'Execute a cell using the pipeline architecture',
      params: [
        { name: 'cell_id', type: 'string', required: true },
        { name: 'parameters', type: 'object', required: false }
      ],
      category: 'cells',
      available: true
    }
  )
  
  // Action: Execute Ephemeral Cell
  registerAction(
    'execute_ephemeral',
    async (params, ctx) => {
      const { cell_type, input_data } = params
      
      if (!cell_type) {
        throw new Error('Required parameter: cell_type')
      }
      
      log.debug('execute_ephemeral - Executing ephemeral cell:', { cell_type, input_data })
      
      try {
        const response = await apiService.fetch('/api/cells/execute-ephemeral', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            cell_type,
            input_data: input_data || {} 
          })
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        const formattedOutput = `⚡ **Ephemeral Cell Execution Result**\n\n` +
          `**Cell Type:** ${data.cell_type}\n` +
          `**Success:** ${data.success ? '✅ Yes' : '❌ No'}\n` +
          `**Message:** ${data.message}\n` +
          `\n**Result:**\n\`\`\`json\n${JSON.stringify(data.result, null, 2)}\n\`\`\``
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length > MAX_INLINE_RESULT_LENGTH) {
            const filename = `ephemeral_result_${cell_type}_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('execute_ephemeral - Results attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          }
        }
        
        log.success('execute_ephemeral - Ephemeral cell executed successfully')
        return { success: true, data, message: 'Ephemeral cell executed successfully' }
      } catch (error) {
        log.error('execute_ephemeral - Error:', error)
        throw new Error(`Failed to execute ephemeral cell: ${error.message}`)
      }
    },
    {
      description: 'Execute an ephemeral cell without persistence (for utility cells like asset-prototyping-cell)',
      params: [
        { name: 'cell_type', type: 'string', required: true, description: 'Cell type ID to execute' },
        { name: 'input_data', type: 'object', required: false, description: 'Input data for cell execution' }
      ],
      category: 'cells',
      available: true
    }
  )
  
  // Action: Update Cell
  registerAction(
    'update_cell',
    async (params, ctx) => {
      const { cell_id, title, content, status, initial_data, metadata, fragments } = params
      
      if (!cell_id) {
        throw new Error('Required parameter: cell_id')
      }
      
      // Build update payload (only include provided fields)
      const updateData = {}
      if (title !== undefined) updateData.title = title
      if (content !== undefined) updateData.content = content
      if (status !== undefined) updateData.status = status
      if (initial_data !== undefined) updateData.initial_data = initial_data
      if (metadata !== undefined) updateData.metadata = metadata
      if (fragments !== undefined) updateData.fragments = fragments
      
      if (Object.keys(updateData).length === 0) {
        throw new Error('At least one field must be provided for update')
      }
      
      log.debug('update_cell - Updating cell:', { cell_id, fields: Object.keys(updateData) })
      
      try {
        const response = await apiService.fetch(`/api/cells/${encodeURIComponent(cell_id)}/update`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updateData)
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        const formattedOutput = `✏️ **Cell Updated Successfully**\n\n` +
          `**Cell ID:** ${data.id}\n` +
          `**Updated Fields:** ${Object.keys(updateData).join(', ')}\n` +
          `**Status:** ${data.status}\n` +
          `\n✅ Update completed`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('update_cell - Cell updated successfully')
        return { success: true, data, message: 'Cell updated successfully' }
      } catch (error) {
        log.error('update_cell - Error:', error)
        throw new Error(`Failed to update cell: ${error.message}`)
      }
    },
    {
      description: 'Update cell properties',
      params: [
        { name: 'cell_id', type: 'string', required: true },
        { name: 'title', type: 'string', required: false },
        { name: 'content', type: 'string', required: false },
        { name: 'status', type: 'string', required: false },
        { name: 'initial_data', type: 'object', required: false },
        { name: 'metadata', type: 'object', required: false },
        { name: 'fragments', type: 'array', required: false }
      ],
      category: 'cells',
      available: true
    }
  )
  
  // Action: Delete Cell
  registerAction(
    'delete_cell',
    async (params, ctx) => {
      const { cell_id } = params
      
      if (!cell_id) {
        throw new Error('Required parameter: cell_id')
      }
      
      log.debug('delete_cell - Deleting cell:', { cell_id })
      
      try {
        const response = await apiService.fetch(`/api/cells/${encodeURIComponent(cell_id)}`, {
          method: 'DELETE'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const formattedOutput = `🗑️ **Cell Deleted**\n\n` +
          `**Cell ID:** ${cell_id}\n` +
          `\n✅ Cell permanently removed from database`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('delete_cell - Cell deleted successfully')
        return { success: true, message: 'Cell deleted successfully' }
      } catch (error) {
        log.error('delete_cell - Error:', error)
        throw new Error(`Failed to delete cell: ${error.message}`)
      }
    },
    {
      description: 'Delete a cell permanently',
      params: [
        { name: 'cell_id', type: 'string', required: true }
      ],
      category: 'cells',
      available: true
    }
  )
  
  // Action: List Notebook Item Types
  registerAction(
    'list_notebook_item_types',
    async (params, ctx) => {
      log.debug('list_notebook_item_types - Fetching types')
      
      try {
        const response = await apiService.fetch('/api/cells/types/list')
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        let formattedOutput = `📚 **Notebook Item Types** (${data.length} type${data.length !== 1 ? 's' : ''})\n\n`
        
        if (data.length === 0) {
          formattedOutput += '*No types found*'
        } else {
          data.forEach(type => {
            formattedOutput += `**${type.name}**\n`
            formattedOutput += `  ID: ${type.id}\n`
            if (type.description) {
              formattedOutput += `  Description: ${type.description}\n`
            }
            formattedOutput += `  Override Refs: ${type.allow_instance_override_refs ? '✓' : '✗'}\n`
            formattedOutput += '\n'
          })
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length > 5000) {
            const filename = `notebook_types_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('list_notebook_item_types - Results attached:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          }
        }
        
        log.success('list_notebook_item_types - Types fetched successfully:', { count: data.length })
        return { success: true, data, message: `Retrieved ${data.length} types` }
      } catch (error) {
        log.error('list_notebook_item_types - Error:', error)
        throw new Error(`Failed to fetch types: ${error.message}`)
      }
    },
    {
      description: 'List available notebook item types',
      params: [],
      category: 'cells',
      available: true
    }
  )
  
  // Action: Get Notebook Item Type
  registerAction(
    'get_notebook_item_type',
    async (params, ctx) => {
      const { type_id } = params
      
      if (!type_id) {
        throw new Error('Missing required parameter: type_id')
      }
      
      log.debug('get_notebook_item_type - Fetching type details:', { type_id })
      
      try {
        const response = await apiService.fetch(`/api/notebook-item-types/${encodeURIComponent(type_id)}`)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const type = await response.json()
        
        // Format type details
        let formattedOutput = `🔍 **Notebook Item Type Details**\n\n`
        formattedOutput += `**${type.name}**\n\n`
        
        // Basic info
        formattedOutput += `**Metadata:**\n`
        formattedOutput += `- ID: \`${type.id}\`\n`
        if (type.description) {
          formattedOutput += `- Description: ${type.description}\n`
        }
        if (type.category) {
          formattedOutput += `- Category: ${type.category}\n`
        }
        formattedOutput += `- Override Refs Allowed: ${type.allow_instance_override_refs ? '✅' : '❌'}\n`
        formattedOutput += `- Canonical: ${type.is_canonical ? '✅' : '❌'}\n`
        formattedOutput += `\n`
        
        // Timestamps
        if (type.created_at) {
          formattedOutput += `**Timeline:**\n`
          formattedOutput += `- Created: ${new Date(type.created_at).toLocaleString()}\n`
          if (type.updated_at) {
            formattedOutput += `- Updated: ${new Date(type.updated_at).toLocaleString()}\n`
          }
          formattedOutput += `\n`
        }
        
        // Default initial data
        if (type.default_initial_data && Object.keys(type.default_initial_data).length > 0) {
          formattedOutput += `**Default Initial Data:**\n`
          formattedOutput += `\`\`\`json\n${JSON.stringify(type.default_initial_data, null, 2)}\n\`\`\`\n\n`
        }
        
        // Default refs
        if (type.default_refs && Object.keys(type.default_refs).length > 0) {
          formattedOutput += `**Default References:**\n`
          Object.entries(type.default_refs).forEach(([key, value]) => {
            formattedOutput += `- ${key}: ${value}\n`
          })
          formattedOutput += `\n`
        }
        
        // Validation rules
        if (type.validation_rules && Object.keys(type.validation_rules).length > 0) {
          formattedOutput += `**Validation Rules:**\n`
          formattedOutput += `\`\`\`json\n${JSON.stringify(type.validation_rules, null, 2)}\n\`\`\`\n\n`
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length > 5000) {
            // Large result - use attachment
            const filename = `type_${type.id.substring(0, 8)}_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('get_notebook_item_type - Results attached to chat:', filename)
          } else {
            // Small result - insert into input
            chatStore.insertContentIntoInput({ content: formattedOutput })
            log.debug('get_notebook_item_type - Results inserted into input')
          }
        }
        
        log.success('get_notebook_item_type - Successfully fetched type details')
        return { success: true, data: type, message: 'Type details fetched successfully' }
      } catch (error) {
        log.error('get_notebook_item_type - Error:', error)
        throw new Error(`Failed to fetch type details: ${error.message}`)
      }
    },
    {
      description: 'Get detailed information about a specific notebook item type',
      params: [
        { name: 'type_id', type: 'string', required: true }
      ],
      category: 'cells',
      available: true
    }
  )

  // ========================================
  // CELL FACTORY ACTIONS (AI Generation)
  // ========================================

  // Action: Generate Cell Code
  registerAction(
    'generate_cell',
    async (params, ctx) => {
      const { cell_id, content, format = 'auto', model } = params
      
      // 1. Validate required parameters
      if (!cell_id) {
        throw new Error('Missing required parameter: cell_id')
      }
      if (!content) {
        throw new Error('Missing required parameter: content')
      }
      if (content.length < 10) {
        throw new Error('Content must be at least 10 characters long')
      }
      
      log.debug('generate_cell - Initiating code generation:', { cell_id, content_length: content.length, format, model })
      
      try {
        // 2. Prepare request payload
        const payload = {
          cell_id,
          content,
          format: format || 'auto'
        }
        
        if (model) {
          payload.model = model
        }
        
        // 3. Call backend endpoint (POST /cells/generate)
        const response = await apiService.fetch('/api/cells/generate', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(payload)
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // 4. Format results with markdown
        let formattedOutput = `## 🤖 Cell Code Generation\n\n`
        formattedOutput += `**Cell ID:** ${cell_id}\n\n`
        formattedOutput += `**Status:** ${data.success ? '✅ Success' : '❌ Failed'}\n\n`
        formattedOutput += `**Message:** ${data.message || 'Code generation initiated'}\n\n`
        
        if (data.stream_available) {
          formattedOutput += `**Stream:** Events available on Event Bus\n`
          formattedOutput += `- Listen to: \`cell/generate/progress\`\n`
          formattedOutput += `- Completion: \`cell/generate/response\`\n\n`
        }
        
        formattedOutput += `---\n\n`
        formattedOutput += `**Next Steps:**\n`
        formattedOutput += `1. Wait for generation to complete (check Event Bus)\n`
        formattedOutput += `2. Review generated code in the cell\n`
        formattedOutput += `3. If valid, use \`promote_cell\` action to create cell type\n`
        
        // 5. Apply intelligent output strategy (prompt-based for small results)
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length < 5000) {
            chatStore.insertContentIntoInput({ content: formattedOutput })
            log.debug('generate_cell - Results inserted into input')
          } else {
            const filename = `generate_cell_result_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('generate_cell - Results attached to chat:', filename)
          }
        }
        
        log.success('generate_cell - Successfully initiated code generation')
        return { 
          success: true, 
          data, 
          message: 'Code generation initiated successfully' 
        }
      } catch (error) {
        log.error('generate_cell - Error:', error)
        throw new Error(`Failed to generate cell code: ${error.message}`)
      }
    },
    {
      description: 'Generate code for a cell using AI (Cell Factory MVP 1)',
      params: [
        { name: 'cell_id', type: 'string', required: true },
        { name: 'content', type: 'string', required: true },
        { name: 'format', type: 'string', required: false },
        { name: 'model', type: 'string', required: false }
      ],
      category: 'cells',
      available: true
    }
  )

  // Action: Promote Cell
  registerAction(
    'promote_cell',
    async (params, ctx) => {
      const { cell_id, new_type_name, new_type_description, category = 'generated' } = params
      
      // 1. Validate required parameters
      if (!cell_id) {
        throw new Error('Missing required parameter: cell_id')
      }
      if (!new_type_name) {
        throw new Error('Missing required parameter: new_type_name')
      }
      if (new_type_name.length < 3 || new_type_name.length > 100) {
        throw new Error('new_type_name must be between 3 and 100 characters')
      }
      
      log.debug('promote_cell - Promoting cell to typed cell:', { cell_id, new_type_name, category })
      
      try {
        // 2. Prepare request payload
        const payload = {
          cell_id,
          new_type_name,
          category: category || 'generated'
        }
        
        if (new_type_description) {
          payload.new_type_description = new_type_description
        }
        
        // 3. Call backend endpoint (POST /cells/promote)
        const response = await apiService.fetch('/api/cells/promote', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(payload)
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // 4. Format results with markdown
        let formattedOutput = `## ⬆️ Cell Promotion Successful\n\n`
        formattedOutput += `**Original Cell ID:** ${cell_id}\n\n`
        formattedOutput += `**New Cell Type:** ${new_type_name}\n`
        formattedOutput += `**Cell Type ID:** ${data.cell_type_id || 'N/A'}\n`
        formattedOutput += `**New Cell Instance ID:** ${data.cell_instance_id || 'N/A'}\n\n`
        formattedOutput += `**Status:** ${data.success ? '✅ Success' : '❌ Failed'}\n\n`
        formattedOutput += `**Message:** ${data.message || 'Cell promoted successfully'}\n\n`
        
        formattedOutput += `---\n\n`
        formattedOutput += `**What Happened:**\n`
        formattedOutput += `1. ✅ Created new NotebookItemType definition\n`
        formattedOutput += `2. ✅ Migrated assets from OPFS to MongoDB GridFS\n`
        formattedOutput += `3. ✅ Registered new cell type in system\n`
        formattedOutput += `4. ✅ Updated Layout Book with new cell type\n`
        formattedOutput += `5. ✅ Created new cell instance\n\n`
        
        formattedOutput += `**Next Steps:**\n`
        formattedOutput += `- Use \`list_notebook_item_types\` to see all available cell types\n`
        formattedOutput += `- Create more instances with \`create_cell\` action\n`
        formattedOutput += `- New cell type is now available for all users\n`
        
        // 5. Apply intelligent output strategy (prompt-based for small results)
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length < 5000) {
            chatStore.insertContentIntoInput({ content: formattedOutput })
            log.debug('promote_cell - Results inserted into input')
          } else {
            const filename = `promote_cell_result_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('promote_cell - Results attached to chat:', filename)
          }
        }
        
        log.success('promote_cell - Successfully promoted cell')
        return { 
          success: true, 
          data, 
          message: 'Cell promoted successfully' 
        }
      } catch (error) {
        log.error('promote_cell - Error:', error)
        throw new Error(`Failed to promote cell: ${error.message}`)
      }
    },
    {
      description: 'Promote an unclassified cell to a typed cell (Cell Factory MVP 1)',
      params: [
        { name: 'cell_id', type: 'string', required: true },
        { name: 'new_type_name', type: 'string', required: true },
        { name: 'new_type_description', type: 'string', required: false },
        { name: 'category', type: 'string', required: false }
      ],
      category: 'cells',
      available: true
    }
  )

  // Action: List Cell Types
  registerAction(
    'list_cell_types',
    async (params, ctx) => {
      log.debug('list_cell_types - Fetching cell types list')
      
      try {
        // Call backend endpoint (GET /cells/types/list)
        const response = await apiService.fetch('/api/cells/types/list')
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the cell types list for display
        let formattedOutput = `## 📋 Cell Types Catalog\n\n`
        formattedOutput += `**Total Types:** ${data.length}\n\n`
        
        if (data.length === 0) {
          formattedOutput += '*No cell types found*\n'
        } else {
          // Group by category
          const byCategory = {}
          data.forEach(type => {
            const category = type.category || 'uncategorized'
            if (!byCategory[category]) byCategory[category] = []
            byCategory[category].push(type)
          })
          
          // Display by category groups
          Object.entries(byCategory).sort().forEach(([category, types]) => {
            const categoryIcon = {
              'generated': '🤖',
              'custom': '✨',
              'extension': '🔌',
              'system': '⚙️'
            }[category] || '📦'
            
            formattedOutput += `### ${categoryIcon} ${category.toUpperCase()}\n\n`
            types.forEach(type => {
              formattedOutput += `**${type.name}**\n`
              if (type.description) {
                formattedOutput += `  ${type.description}\n`
              }
              formattedOutput += `  • ID: \`${type.id}\`\n`
              if (type.version) {
                formattedOutput += `  • Version: ${type.version}\n`
              }
              formattedOutput += `\n`
            })
          })
        }
        
        // Apply intelligent output strategy
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length < 5000) {
            chatStore.insertContentIntoInput({ content: formattedOutput })
            log.debug('list_cell_types - Results inserted into input')
          } else {
            const filename = `cell_types_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('list_cell_types - Results attached to chat:', filename)
          }
        }
        
        log.success('list_cell_types - Successfully fetched cell types')
        return { success: true, data, message: 'Cell types fetched successfully' }
      } catch (error) {
        log.error('list_cell_types - Error:', error)
        throw new Error(`Failed to fetch cell types: ${error.message}`)
      }
    },
    {
      description: 'List all available notebook item types (cell types and book types)',
      params: [],
      category: 'cells',
      available: true
    }
  )

  // Action: Update Notebook Item Type
  registerAction(
    'update_notebook_item_type',
    async (params, ctx) => {
      const { type_id, name, description, category, version, ...otherFields } = params
      
      // 1. Validate required parameters
      if (!type_id) {
        throw new Error('Missing required parameter: type_id')
      }
      
      log.debug('update_notebook_item_type - Updating type:', { type_id, name, description, category, version })
      
      try {
        // 2. Build update payload (only include provided fields)
        const payload = { id: type_id }
        if (name !== undefined) payload.name = name
        if (description !== undefined) payload.description = description
        if (category !== undefined) payload.category = category
        if (version !== undefined) payload.version = version
        
        // Include any other fields provided
        Object.assign(payload, otherFields)
        
        // 3. Call backend endpoint (PUT /notebook_item_types/{type_id})
        const response = await apiService.fetch(`/api/notebook_item_types/${encodeURIComponent(type_id)}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(payload)
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // 4. Format results with markdown
        let formattedOutput = `## ✏️ Notebook Item Type Updated\n\n`
        formattedOutput += `**Type ID:** ${type_id}\n`
        formattedOutput += `**Name:** ${data.name}\n`
        if (data.description) {
          formattedOutput += `**Description:** ${data.description}\n`
        }
        if (data.category) {
          formattedOutput += `**Category:** ${data.category}\n`
        }
        if (data.version) {
          formattedOutput += `**Version:** ${data.version}\n`
        }
        formattedOutput += `\n✅ Type updated successfully\n`
        
        // 5. Apply intelligent output strategy
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
          log.debug('update_notebook_item_type - Results inserted into input')
        }
        
        log.success('update_notebook_item_type - Successfully updated type')
        return { success: true, data, message: 'Type updated successfully' }
      } catch (error) {
        log.error('update_notebook_item_type - Error:', error)
        throw new Error(`Failed to update type: ${error.message}`)
      }
    },
    {
      description: 'Update an existing NotebookItemType definition',
      params: [
        { name: 'type_id', type: 'string', required: true },
        { name: 'name', type: 'string', required: false },
        { name: 'description', type: 'string', required: false },
        { name: 'category', type: 'string', required: false },
        { name: 'version', type: 'string', required: false }
      ],
      category: 'cells',
      available: true
    }
  )

  // Action: Delete Notebook Item Type
  registerAction(
    'delete_notebook_item_type',
    async (params, ctx) => {
      const { type_id } = params
      
      // 1. Validate required parameters
      if (!type_id) {
        throw new Error('Missing required parameter: type_id')
      }
      
      log.debug('delete_notebook_item_type - Deleting type:', { type_id })
      
      try {
        // 2. Call backend endpoint (DELETE /notebook_item_types/{type_id})
        const response = await apiService.fetch(`/api/notebook_item_types/${encodeURIComponent(type_id)}`, {
          method: 'DELETE'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        // 3. Format results with markdown
        let formattedOutput = `## 🗑️ Notebook Item Type Deleted\n\n`
        formattedOutput += `**Type ID:** ${type_id}\n\n`
        formattedOutput += `✅ Type deleted successfully\n\n`
        formattedOutput += `**Note:** Existing cells/books referencing this type are not affected.\n`
        
        // 4. Apply intelligent output strategy
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
          log.debug('delete_notebook_item_type - Results inserted into input')
        }
        
        log.success('delete_notebook_item_type - Successfully deleted type')
        return { success: true, message: 'Type deleted successfully' }
      } catch (error) {
        log.error('delete_notebook_item_type - Error:', error)
        throw new Error(`Failed to delete type: ${error.message}`)
      }
    },
    {
      description: 'Delete a NotebookItemType definition',
      params: [
        { name: 'type_id', type: 'string', required: true }
      ],
      category: 'cells',
      available: true
    }
  )

  // ========================================
  // CELL TYPE REGISTRY ACTIONS
  // ========================================

  // Action: List Registered Cell Types
  registerAction(
    'list_registered_cell_types',
    async (params, ctx) => {
      log.debug('list_registered_cell_types - Fetching types from registry')
      
      try {
        const response = await apiService.fetch('/api/notebook-item-types/registry/list')
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format results
        let formattedOutput = `## 📋 Registered Cell Types (Registry)\n\n`
        formattedOutput += `**Total Types:** ${data.length}\n\n`
        
        if (data.length === 0) {
          formattedOutput += '*No types found in registry*\n'
        } else {
          formattedOutput += `**Available Types:**\n\n`
          data.forEach(type => {
            const icon = type.icon || '📄'
            formattedOutput += `### ${icon} ${type.name}\n`
            formattedOutput += `- **ID:** ${type.id}\n`
            if (type.description) {
              formattedOutput += `- **Description:** ${type.description}\n`
            }
            formattedOutput += `\n`
          })
          
          formattedOutput += `💡 **Note:** These types are discovered from \`artifacts/canonical/cell_types/\`\n`
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length < 5000) {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          } else {
            const filename = `registered_cell_types_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
          }
        }
        
        log.success('list_registered_cell_types - Successfully fetched types:', { count: data.length })
        return { success: true, data, message: `Retrieved ${data.length} types from registry` }
      } catch (error) {
        log.error('list_registered_cell_types - Error:', error)
        throw new Error(`Failed to fetch registered types: ${error.message}`)
      }
    },
    {
      description: 'List all cell types from plug-and-play registry',
      params: [],
      category: 'cells',
      available: true
    }
  )

  // Action: Discover Cell Types
  registerAction(
    'discover_cell_types',
    async (params, ctx) => {
      log.debug('discover_cell_types - Triggering cell type discovery')
      
      try {
        const response = await apiService.fetch('/api/notebook-item-types/registry/discover', {
          method: 'POST'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format results
        let formattedOutput = `## 🔍 Cell Types Discovery Complete\n\n`
        formattedOutput += `**Discovered:** ${data.discovered_count} type${data.discovered_count !== 1 ? 's' : ''}\n\n`
        
        if (data.type_ids && data.type_ids.length > 0) {
          formattedOutput += `**Type IDs:**\n`
          data.type_ids.forEach(id => {
            formattedOutput += `- ${id}\n`
          })
          formattedOutput += `\n`
        }
        
        formattedOutput += `✅ Registry refreshed from filesystem\n`
        formattedOutput += `📁 Source: \`artifacts/canonical/cell_types/\`\n\n`
        formattedOutput += `💡 Use \`list_registered_cell_types\` to view all types\n`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('discover_cell_types - Discovery completed:', { count: data.discovered_count })
        return { success: true, data, message: `Discovered ${data.discovered_count} types` }
      } catch (error) {
        log.error('discover_cell_types - Error:', error)
        throw new Error(`Failed to discover cell types: ${error.message}`)
      }
    },
    {
      description: 'Trigger re-discovery of cell types from filesystem',
      params: [],
      category: 'cells',
      available: true
    }
  )
}
