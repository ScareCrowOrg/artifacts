/**
 * Config Actions
 * 
 * Actions for configuration management: list_warmup_files, list_personas,
 * list_action_files, get_oauth_config
 */

import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'

const log = createLogger('action:config')

/**
 * Register config management actions
 * @param {Function} registerAction - Function to register an action
 */
export function registerConfigActions(registerAction) {
  // Action: List Warm-Up Files
  registerAction(
    'list_warmup_files',
    async (params, ctx) => {
      log.debug('list_warmup_files - Fetching warm-up files')
      
      try {
        const response = await apiService.fetch('/api/config/agentlab/warm-up-files')
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const files = await response.json()
        
        let formattedOutput = `📁 **AgenteLab Warm-Up Files**\n\n`
        
        if (files.length === 0) {
          formattedOutput += '*No warm-up files found*\n'
        } else {
          formattedOutput += `Found ${files.length} warm-up configuration file${files.length !== 1 ? 's' : ''}:\n\n`
          
          files.forEach((file, index) => {
            formattedOutput += `${index + 1}. **${file.filename}**\n`
            formattedOutput += `   - Path: \`${file.path}\`\n`
            formattedOutput += `   - Size: ${(file.size / 1024).toFixed(2)} KB\n`
            formattedOutput += `\n`
          })
          
          formattedOutput += `💡 *These files configure AgenteLab persona behavior*\n`
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('list_warmup_files - Successfully fetched files')
        return { success: true, data: files, message: 'Warm-up files fetched successfully' }
      } catch (error) {
        log.error('list_warmup_files - Error:', error)
        throw new Error(`Failed to fetch warm-up files: ${error.message}`)
      }
    },
    {
      description: 'List available AgenteLab warm-up configuration files',
      params: [],
      category: 'config',
      available: true
    }
  )
  
  // Action: List Personas
  registerAction(
    'list_personas',
    async (params, ctx) => {
      log.debug('list_personas - Fetching personas')
      
      try {
        const response = await apiService.fetch('/api/config/agentlab/personas')
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        let formattedOutput = `🎭 **AgenteLab Personas**\n\n`
        
        if (!data.personas || data.personas.length === 0) {
          formattedOutput += data.message || '*No personas configured*'
          formattedOutput += `\n`
        } else {
          formattedOutput += `**Available Personas (${data.personas.length}):**\n\n`
          
          data.personas.forEach((persona, index) => {
            formattedOutput += `${index + 1}. **${persona.name || persona.id}**\n`
            if (persona.description) {
              formattedOutput += `   - Description: ${persona.description}\n`
            }
            if (persona.capabilities && persona.capabilities.length > 0) {
              formattedOutput += `   - Capabilities: ${persona.capabilities.join(', ')}\n`
            }
            if (persona.warmup_files && persona.warmup_files.length > 0) {
              formattedOutput += `   - Files: ${persona.warmup_files.join(', ')}\n`
            }
            formattedOutput += `\n`
          })
          
          // Add selection guidelines if available
          if (data.selection_guidelines && data.selection_guidelines.description) {
            formattedOutput += `\n**Selection Guidelines:**\n`
            formattedOutput += `${data.selection_guidelines.description}\n`
            
            if (data.selection_guidelines.considerations && Array.isArray(data.selection_guidelines.considerations)) {
              formattedOutput += `\n**Considerations:**\n`
              data.selection_guidelines.considerations.forEach(consideration => {
                formattedOutput += `- ${consideration}\n`
              })
            }
          }
          
          // Add metadata if available
          if (data.metadata) {
            formattedOutput += `\n---\n`
            if (data.metadata.version) {
              formattedOutput += `Version: ${data.metadata.version} | `
            }
            if (data.metadata.last_updated) {
              formattedOutput += `Last Updated: ${data.metadata.last_updated}`
            }
            formattedOutput += `\n`
          }
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length > 5000) {
            const filename = `personas_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('list_personas - Results attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
            log.debug('list_personas - Results inserted into input')
          }
        }
        
        log.success('list_personas - Successfully fetched personas')
        return { success: true, data, message: 'Personas fetched successfully' }
      } catch (error) {
        log.error('list_personas - Error:', error)
        throw new Error(`Failed to fetch personas: ${error.message}`)
      }
    },
    {
      description: 'List available AgenteLab personas with metadata',
      params: [],
      category: 'config',
      available: true
    }
  )
  
  // Action: List Action Files
  registerAction(
    'list_action_files',
    async (params, ctx) => {
      log.debug('list_action_files - Fetching action files')
      
      try {
        const response = await apiService.fetch('/api/config/agentlab/action-files')
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const files = await response.json()
        
        let formattedOutput = `⚡ **AgenteLab Action Files Catalog**\n\n`
        
        if (files.length === 0) {
          formattedOutput += '*No action files found*\n'
        } else {
          formattedOutput += `Found ${files.length} action definition${files.length !== 1 ? 's' : ''}:\n\n`
          
          // Group by action type
          const byType = {}
          files.forEach(file => {
            const type = file.action_type || 'unknown'
            if (!byType[type]) byType[type] = []
            byType[type].push(file)
          })
          
          Object.entries(byType).forEach(([type, actionFiles]) => {
            formattedOutput += `**${type.toUpperCase()} Actions (${actionFiles.length}):**\n`
            
            actionFiles.forEach(file => {
              formattedOutput += `- **${file.action_name}**\n`
              if (file.description) {
                formattedOutput += `  ${file.description.substring(0, 80)}${file.description.length > 80 ? '...' : ''}\n`
              }
              formattedOutput += `  Size: ${(file.size / 1024).toFixed(2)} KB\n`
            })
            formattedOutput += `\n`
          })
          
          formattedOutput += `💡 *Use discover_actions for complete action discovery*\n`
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length > 5000) {
            const filename = `action_files_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('list_action_files - Results attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
            log.debug('list_action_files - Results inserted into input')
          }
        }
        
        log.success('list_action_files - Successfully fetched action files')
        return { success: true, data: files, message: 'Action files fetched successfully' }
      } catch (error) {
        log.error('list_action_files - Error:', error)
        throw new Error(`Failed to fetch action files: ${error.message}`)
      }
    },
    {
      description: 'List available AgenteLab action definition files',
      params: [],
      category: 'config',
      available: true
    }
  )

  // ========================================
  // OAUTH CONFIGURATION ACTIONS
  // ========================================

  // Action: Get OAuth Config
  registerAction(
    'get_oauth_config',
    async (params, ctx) => {
      log.debug('get_oauth_config - Fetching OAuth configuration')
      
      try {
        const response = await apiService.fetch('/api/config/oauth')
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format results
        let formattedOutput = `## 🔐 OAuth Configuration\n\n`
        formattedOutput += `**Google Client ID:** ${data.googleClientId || '*Not configured*'}\n`
        formattedOutput += `**Authentication Enabled:** ${data.authEnabled ? '✅ Yes' : '❌ No'}\n\n`
        
        if (data.authEnabled) {
          formattedOutput += `🟢 **OAuth authentication is fully configured and enabled**\n`
        } else if (data.googleClientId) {
          formattedOutput += `⚠️ **Client ID set but authentication not fully enabled**\n`
          formattedOutput += `   (Client secret may be missing)\n`
        } else {
          formattedOutput += `⚠️ **OAuth not configured**\n`
          formattedOutput += `   Use update_oauth_config to set Client ID and secret\n`
        }
        
        formattedOutput += `\n💡 **Note:** Client secret is never exposed in responses for security.\n`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('get_oauth_config - Successfully fetched configuration')
        return { success: true, data, message: 'OAuth configuration fetched successfully' }
      } catch (error) {
        log.error('get_oauth_config - Error:', error)
        throw new Error(`Failed to fetch OAuth configuration: ${error.message}`)
      }
    },
    {
      description: 'Get OAuth configuration (Client ID and auth status)',
      params: [],
      category: 'config',
      available: true
    }
  )

  // Action: Update OAuth Config
  registerAction(
    'update_oauth_config',
    async (params, ctx) => {
      const { googleClientId, googleClientSecret } = params
      
      log.debug('update_oauth_config - Updating OAuth configuration')
      
      try {
        const requestBody = {}
        if (googleClientId) requestBody.googleClientId = googleClientId
        if (googleClientSecret) requestBody.googleClientSecret = googleClientSecret
        
        if (Object.keys(requestBody).length === 0) {
          throw new Error('At least one parameter (googleClientId or googleClientSecret) must be provided')
        }
        
        const response = await apiService.fetch('/api/config/oauth', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestBody)
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format results
        let formattedOutput = `## ✅ OAuth Configuration Updated\n\n`
        formattedOutput += `**Google Client ID:** ${data.googleClientId || '*Not set*'}\n`
        formattedOutput += `**Authentication Enabled:** ${data.authEnabled ? '✅ Yes' : '❌ No'}\n\n`
        
        if (data.authEnabled) {
          formattedOutput += `🟢 **OAuth authentication is now fully configured and enabled**\n`
        } else {
          formattedOutput += `⚠️ **Authentication not yet fully enabled**\n`
          formattedOutput += `   Both Client ID and secret are required for auth to work\n`
        }
        
        formattedOutput += `\n💾 **Configuration saved to database**\n`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('update_oauth_config - Successfully updated configuration')
        return { success: true, data, message: 'OAuth configuration updated successfully' }
      } catch (error) {
        log.error('update_oauth_config - Error:', error)
        throw new Error(`Failed to update OAuth configuration: ${error.message}`)
      }
    },
    {
      description: 'Update OAuth configuration (Client ID and/or secret)',
      params: [
        { name: 'googleClientId', type: 'string', required: false },
        { name: 'googleClientSecret', type: 'string', required: false }
      ],
      category: 'config',
      available: true
    }
  )
}
