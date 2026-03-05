/**
 * AI Models Actions
 * 
 * Actions for AI models management:
 * - list_ai_models: List all AI models
 * - get_ai_model: Get details of a specific model
 * - create_ai_model: Create a new AI model configuration
 * - update_ai_model: Update an existing model configuration
 * - activate_ai_model: Activate or deactivate a model
 * - delete_ai_model: Delete a model configuration
 */

import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'

const log = createLogger('action:ai-models')

/**
 * Register AI models management actions
 * @param {Function} registerAction - Function to register an action
 */
export function registerAIModelsActions(registerAction) {
  // Action: List AI Models
  registerAction(
    'list_ai_models',
    async (params, ctx) => {
      log.debug('list_ai_models - Fetching AI models list')
      
      try {
        const response = await apiService.fetch('/api/ai-models/list')
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the AI models list for display
        let formattedOutput = `🤖 **AI Models List** (${data.length} model${data.length !== 1 ? 's' : ''})\n\n`
        
        if (data.length === 0) {
          formattedOutput += '*No AI models found*'
        } else {
          data.forEach(model => {
            const statusIcon = model.active ? '✅' : '❌'
            formattedOutput += `${statusIcon} **${model.name}**\n`
            formattedOutput += `  ID: ${model.id}\n`
            if (model.description) {
              formattedOutput += `  Description: ${model.description}\n`
            }
            if (model.provider) {
              formattedOutput += `  Provider: ${model.provider}\n`
            }
            if (model.model_type) {
              formattedOutput += `  Type: ${model.model_type}\n`
            }
            formattedOutput += `  Active: ${model.active ? 'Yes' : 'No'}\n`
            if (model.max_tokens) {
              formattedOutput += `  Max Tokens: ${model.max_tokens}\n`
            }
            if (model.temperature) {
              formattedOutput += `  Temperature: ${model.temperature}\n`
            }
            formattedOutput += '\n'
          })
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length > 5000) {
            const filename = `ai_models_list_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('list_ai_models - Results attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          }
        }
        
        log.success('list_ai_models - AI models list fetched successfully:', { count: data.length })
        return { success: true, data, message: `Retrieved ${data.length} AI models` }
      } catch (error) {
        log.error('list_ai_models - Error:', error)
        throw new Error(`Failed to fetch AI models list: ${error.message}`)
      }
    },
    {
      description: 'List all available AI models',
      params: [],
      category: 'ai-models',
      available: true
    }
  )
  
  // Action: Get AI Model
  registerAction(
    'get_ai_model',
    async (params, ctx) => {
      const { model_id } = params
      
      if (!model_id) {
        throw new Error('Missing required parameter: model_id')
      }
      
      log.debug('get_ai_model - Fetching AI model:', { model_id })
      
      try {
        const response = await apiService.fetch(`/api/ai-models/${encodeURIComponent(model_id)}`)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const model = await response.json()
        
        // Format AI model details
        const statusIcon = model.active ? '✅' : '❌'
        let formattedOutput = `🤖 **AI Model Details**\n\n`
        formattedOutput += `${statusIcon} **${model.name}**\n\n`
        formattedOutput += `**ID:** ${model.id}\n`
        if (model.description) {
          formattedOutput += `**Description:** ${model.description}\n`
        }
        if (model.provider) {
          formattedOutput += `**Provider:** ${model.provider}\n`
        }
        if (model.model_type) {
          formattedOutput += `**Type:** ${model.model_type}\n`
        }
        if (model.api_key_name) {
          formattedOutput += `**API Key Name:** ${model.api_key_name}\n`
        }
        formattedOutput += `**Active:** ${model.active ? 'Yes' : 'No'}\n`
        
        if (model.max_tokens) {
          formattedOutput += `**Max Tokens:** ${model.max_tokens}\n`
        }
        if (model.temperature !== null && model.temperature !== undefined) {
          formattedOutput += `**Temperature:** ${model.temperature}\n`
        }
        if (model.top_p !== null && model.top_p !== undefined) {
          formattedOutput += `**Top P:** ${model.top_p}\n`
        }
        
        if (model.config && Object.keys(model.config).length > 0) {
          formattedOutput += `\n**Configuration:**\n`
          Object.entries(model.config).forEach(([key, value]) => {
            formattedOutput += `  • ${key}: ${JSON.stringify(value)}\n`
          })
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('get_ai_model - AI model fetched successfully:', { model_id })
        return { success: true, data: model, message: 'AI model retrieved successfully' }
      } catch (error) {
        log.error('get_ai_model - Error:', error)
        throw new Error(`Failed to fetch AI model: ${error.message}`)
      }
    },
    {
      description: 'Get details of a specific AI model',
      params: [
        { name: 'model_id', type: 'string', required: true }
      ],
      category: 'ai-models',
      available: true
    }
  )
  
  // Action: Create AI Model
  registerAction(
    'create_ai_model',
    async (params, ctx) => {
      const { name, description, type, provider, modelId, apiKey, version, active, configuration, metadata } = params
      
      // Validate required parameters
      if (!name || !description || !type || !provider || !modelId) {
        throw new Error('Missing required parameters: name, description, type, provider, modelId')
      }
      
      // Validate type enum
      const validTypes = ['openai', 'gemini', 'ollama', 'groq']
      if (!validTypes.includes(type)) {
        throw new Error(`Invalid type: ${type}. Must be one of: ${validTypes.join(', ')}`)
      }
      
      log.debug('create_ai_model - Creating AI model:', { name, provider, modelId })
      
      try {
        const requestBody = {
          name,
          description,
          type,
          provider,
          modelId,
          ...(apiKey && { apiKey }),
          version: version || '1.0.0',
          active: active !== undefined ? active : true,
          configuration: configuration || {},
          metadata: metadata || {}
        }
        
        const response = await apiService.fetch('/api/ai-models/create', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(requestBody)
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          
          // Handle specific error cases
          if (response.status === 409) {
            throw new Error(`Model ${modelId} from provider ${provider} already exists`)
          }
          
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const model = await response.json()
        
        // Format success message (never display API key)
        let formattedOutput = `✅ **AI Model Created Successfully**\n\n`
        formattedOutput += `**Name:** ${model.name}\n`
        formattedOutput += `**ID:** ${model.id}\n`
        formattedOutput += `**Provider:** ${model.provider}\n`
        formattedOutput += `**Model ID:** ${model.modelId}\n`
        formattedOutput += `**Type:** ${model.type}\n`
        formattedOutput += `**Version:** ${model.version}\n`
        formattedOutput += `**Active:** ${model.active ? 'Yes' : 'No'}\n`
        
        if (model.description) {
          formattedOutput += `**Description:** ${model.description}\n`
        }
        
        if (apiKey) {
          formattedOutput += `**API Key:** ✓ Configured (encrypted)\n`
        }
        
        if (model.configuration && Object.keys(model.configuration).length > 0) {
          formattedOutput += `\n**Configuration:**\n`
          Object.entries(model.configuration).forEach(([key, value]) => {
            formattedOutput += `  • ${key}: ${JSON.stringify(value)}\n`
          })
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('create_ai_model - AI model created successfully:', { id: model.id, name: model.name })
        return { success: true, data: model, message: 'AI model created successfully' }
      } catch (error) {
        log.error('create_ai_model - Error:', error)
        throw new Error(`Failed to create AI model: ${error.message}`)
      }
    },
    {
      description: 'Create a new AI model configuration',
      params: [
        { name: 'name', type: 'string', required: true },
        { name: 'description', type: 'string', required: true },
        { name: 'type', type: 'string', required: true },
        { name: 'provider', type: 'string', required: true },
        { name: 'modelId', type: 'string', required: true },
        { name: 'apiKey', type: 'string', required: false, sensitive: true },
        { name: 'version', type: 'string', required: false },
        { name: 'active', type: 'boolean', required: false },
        { name: 'configuration', type: 'object', required: false },
        { name: 'metadata', type: 'object', required: false }
      ],
      category: 'ai-models',
      available: true
    }
  )
  
  // Action: Update AI Model
  registerAction(
    'update_ai_model',
    async (params, ctx) => {
      const { model_id, name, description, type, provider, modelId, apiKey, version, active, configuration, metadata } = params
      
      // Validate required parameter
      if (!model_id) {
        throw new Error('Missing required parameter: model_id')
      }
      
      // Validate type enum if provided
      if (type) {
        const validTypes = ['openai', 'gemini', 'ollama', 'groq']
        if (!validTypes.includes(type)) {
          throw new Error(`Invalid type: ${type}. Must be one of: ${validTypes.join(', ')}`)
        }
      }
      
      log.debug('update_ai_model - Updating AI model:', { model_id })
      
      try {
        // Build request body with only provided fields
        const requestBody = {}
        if (name !== undefined) requestBody.name = name
        if (description !== undefined) requestBody.description = description
        if (type !== undefined) requestBody.type = type
        if (provider !== undefined) requestBody.provider = provider
        if (modelId !== undefined) requestBody.modelId = modelId
        if (apiKey !== undefined) requestBody.apiKey = apiKey
        if (version !== undefined) requestBody.version = version
        if (active !== undefined) requestBody.active = active
        if (configuration !== undefined) requestBody.configuration = configuration
        if (metadata !== undefined) requestBody.metadata = metadata
        
        // Ensure at least one field is being updated
        if (Object.keys(requestBody).length === 0) {
          throw new Error('No fields provided to update. Provide at least one field.')
        }
        
        const response = await apiService.fetch(`/api/ai-models/${encodeURIComponent(model_id)}/update`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(requestBody)
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          
          if (response.status === 404) {
            throw new Error(`Model ${model_id} not found`)
          }
          
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const model = await response.json()
        
        // Format success message (never display API key)
        let formattedOutput = `✅ **AI Model Updated Successfully**\n\n`
        formattedOutput += `**Name:** ${model.name}\n`
        formattedOutput += `**ID:** ${model.id}\n`
        formattedOutput += `**Provider:** ${model.provider}\n`
        formattedOutput += `**Model ID:** ${model.modelId}\n`
        formattedOutput += `**Type:** ${model.type}\n`
        formattedOutput += `**Version:** ${model.version}\n`
        formattedOutput += `**Active:** ${model.active ? 'Yes' : 'No'}\n`
        
        if (model.description) {
          formattedOutput += `**Description:** ${model.description}\n`
        }
        
        if (apiKey) {
          formattedOutput += `**API Key:** ✓ Updated (encrypted)\n`
        }
        
        if (model.configuration && Object.keys(model.configuration).length > 0) {
          formattedOutput += `\n**Configuration:**\n`
          Object.entries(model.configuration).forEach(([key, value]) => {
            formattedOutput += `  • ${key}: ${JSON.stringify(value)}\n`
          })
        }
        
        formattedOutput += `\n**Updated Fields:**\n`
        Object.keys(requestBody).forEach(key => {
          if (key !== 'apiKey') { // Never display API key
            formattedOutput += `  • ${key}\n`
          } else {
            formattedOutput += `  • apiKey (updated)\n`
          }
        })
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('update_ai_model - AI model updated successfully:', { id: model.id, name: model.name })
        return { success: true, data: model, message: 'AI model updated successfully' }
      } catch (error) {
        log.error('update_ai_model - Error:', error)
        throw new Error(`Failed to update AI model: ${error.message}`)
      }
    },
    {
      description: 'Update an existing AI model configuration',
      params: [
        { name: 'model_id', type: 'string', required: true },
        { name: 'name', type: 'string', required: false },
        { name: 'description', type: 'string', required: false },
        { name: 'type', type: 'string', required: false },
        { name: 'provider', type: 'string', required: false },
        { name: 'modelId', type: 'string', required: false },
        { name: 'apiKey', type: 'string', required: false, sensitive: true },
        { name: 'version', type: 'string', required: false },
        { name: 'active', type: 'boolean', required: false },
        { name: 'configuration', type: 'object', required: false },
        { name: 'metadata', type: 'object', required: false }
      ],
      category: 'ai-models',
      available: true
    }
  )
  
  // Action: Activate AI Model
  registerAction(
    'activate_ai_model',
    async (params, ctx) => {
      const { model_id, active } = params
      
      // Validate required parameters
      if (!model_id) {
        throw new Error('Missing required parameter: model_id')
      }
      
      if (active === undefined || active === null) {
        throw new Error('Missing required parameter: active (boolean)')
      }
      
      if (typeof active !== 'boolean') {
        throw new Error('Parameter "active" must be a boolean (true or false)')
      }
      
      log.debug('activate_ai_model - Setting model status:', { model_id, active })
      
      try {
        const response = await apiService.fetch(
          `/api/ai-models/${encodeURIComponent(model_id)}/activate?active=${active}`,
          {
            method: 'POST'
          }
        )
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          
          if (response.status === 404) {
            throw new Error(`Model ${model_id} not found`)
          }
          
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const model = await response.json()
        
        // Format success message
        const statusIcon = model.active ? '✅' : '❌'
        const statusText = model.active ? 'Activated' : 'Deactivated'
        
        let formattedOutput = `${statusIcon} **AI Model ${statusText}**\n\n`
        formattedOutput += `**Name:** ${model.name}\n`
        formattedOutput += `**ID:** ${model.id}\n`
        formattedOutput += `**Provider:** ${model.provider}\n`
        formattedOutput += `**Model ID:** ${model.modelId}\n`
        formattedOutput += `**Active Status:** ${model.active ? 'Active' : 'Inactive'}\n`
        
        if (model.description) {
          formattedOutput += `**Description:** ${model.description}\n`
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('activate_ai_model - AI model status updated:', { id: model.id, active: model.active })
        return { success: true, data: model, message: `AI model ${statusText.toLowerCase()} successfully` }
      } catch (error) {
        log.error('activate_ai_model - Error:', error)
        throw new Error(`Failed to update AI model status: ${error.message}`)
      }
    },
    {
      description: 'Activate or deactivate an AI model',
      params: [
        { name: 'model_id', type: 'string', required: true },
        { name: 'active', type: 'boolean', required: true }
      ],
      category: 'ai-models',
      available: true
    }
  )
  
  // Action: Delete AI Model
  registerAction(
    'delete_ai_model',
    async (params, ctx) => {
      const { model_id } = params
      
      // Validate required parameter
      if (!model_id) {
        throw new Error('Missing required parameter: model_id')
      }
      
      log.debug('delete_ai_model - Deleting AI model:', { model_id })
      
      try {
        const response = await apiService.fetch(`/api/ai-models/${encodeURIComponent(model_id)}/delete`, {
          method: 'DELETE'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          
          if (response.status === 404) {
            throw new Error(`Model ${model_id} not found`)
          }
          
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        // Successful deletion returns 204 No Content
        let formattedOutput = `🗑️ **AI Model Deleted Successfully**\n\n`
        formattedOutput += `**Model ID:** ${model_id}\n`
        formattedOutput += `**Status:** Permanently deleted\n\n`
        formattedOutput += `⚠️ **Note:** This operation cannot be undone.\n`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('delete_ai_model - AI model deleted successfully:', { model_id })
        return { success: true, message: 'AI model deleted successfully' }
      } catch (error) {
        log.error('delete_ai_model - Error:', error)
        throw new Error(`Failed to delete AI model: ${error.message}`)
      }
    },
    {
      description: 'Delete an AI model configuration (destructive operation)',
      params: [
        { name: 'model_id', type: 'string', required: true }
      ],
      category: 'ai-models',
      available: true,
      destructive: true
    }
  )
}
