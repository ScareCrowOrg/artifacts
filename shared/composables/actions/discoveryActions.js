/**
 * Discovery Actions
 * 
 * Meta-action for discovering available actions
 */

import { createLogger } from '@/utils/logger'

const log = createLogger('action:discovery')

/**
 * Register discovery actions
 * @param {Function} registerAction - Function to register an action
 */
export function registerDiscoveryActions(registerAction) {
  // ========================================
  // DISCOVER_ACTIONS: Meta-action for LLM discovery
  // ========================================
  registerAction(
    'discover_actions',
    async (params, ctx) => {
      const { mode, filter_label, filter_action } = params
      
      log.info('[DISCOVER_ACTIONS] Discovery request', { mode, filter_label, filter_action })
      
      if (!mode) {
        throw new Error('Parâmetro "mode" é obrigatório (list_all, by_label, action_details)')
      }
      
      // Import discovery composable dynamically to avoid circular dependencies
      const { useActionDiscovery } = await import('@/composables/useActionDiscovery')
      const discovery = useActionDiscovery()
      
      try {
        let result
        let formattedOutput
        
        switch (mode) {
          case 'list_all': {
            // List all labels and actions
            result = await discovery.discoverAll()
            
            // Format for display
            formattedOutput = '🔍 **Available Action Categories:**\n\n'
            const sortedLabels = Object.keys(result).sort()
            
            sortedLabels.forEach(labelKey => {
              const actions = result[labelKey]
              formattedOutput += `**${labelKey}** (${actions.length} actions):\n`
              actions.forEach(actionName => {
                formattedOutput += `  • ${actionName}\n`
              })
              formattedOutput += '\n'
            })
            
            formattedOutput += `\n📊 Total: ${sortedLabels.length} categories, ${
              Object.values(result).flat().length
            } actions`
            
            break
          }
          
          case 'by_label': {
            // Get actions by label
            if (!filter_label) {
              throw new Error('Parâmetro "filter_label" é obrigatório para mode="by_label"')
            }
            
            result = await discovery.discoverByLabel(filter_label)
            
            if (result.length === 0) {
              formattedOutput = `⚠️ No actions found for label: "${filter_label}"`
            } else {
              formattedOutput = `🏷️ **Actions for label "${filter_label}":**\n\n`
              
              result.forEach(action => {
                formattedOutput += `**${action.name}**\n`
                formattedOutput += `  ${action.description.split('\n')[0]}\n`
                
                if (action.parameters && action.parameters.length > 0) {
                  formattedOutput += '  Parameters:\n'
                  action.parameters.forEach(param => {
                    const req = param.required ? '(required)' : '(optional)'
                    formattedOutput += `    • ${param.name}: ${param.type} ${req}\n`
                  })
                }
                
                if (action.labels && action.labels.length > 1) {
                  formattedOutput += `  Labels: ${action.labels.join(', ')}\n`
                }
                
                formattedOutput += '\n'
              })
              
              formattedOutput += `📊 Found ${result.length} action(s)`
            }
            
            break
          }
          
          case 'action_details': {
            // Get specific action details
            if (!filter_label || !filter_action) {
              throw new Error(
                'Parâmetros "filter_label" e "filter_action" são obrigatórios para mode="action_details"'
              )
            }
            
            result = await discovery.discoverAction(filter_label, filter_action)
            
            if (!result) {
              formattedOutput = `⚠️ Action "${filter_action}" not found in label "${filter_label}"`
            } else {
              formattedOutput = `📋 **Action Details: ${result.name}**\n\n`
              
              // Description
              formattedOutput += `**Description:**\n${result.description}\n\n`
              
              // Parameters
              if (result.parameters && result.parameters.length > 0) {
                formattedOutput += '**Parameters:**\n'
                result.parameters.forEach(param => {
                  const req = param.required ? '✓ Required' : '○ Optional'
                  formattedOutput += `  ${req} **${param.name}** (${param.type})\n`
                  if (param.description) {
                    formattedOutput += `    ${param.description}\n`
                  }
                  if (param.default !== null && param.default !== undefined) {
                    formattedOutput += `    Default: ${JSON.stringify(param.default)}\n`
                  }
                })
                formattedOutput += '\n'
              }
              
              // Metadata
              if (result.metadata) {
                formattedOutput += '**Metadata:**\n'
                formattedOutput += `  Version: ${result.metadata.version}\n`
                formattedOutput += `  Type: ${result.metadata.action_type}\n`
                formattedOutput += `  Status: ${result.metadata.status}\n`
                formattedOutput += `  Labels: ${result.metadata.labels.join(', ')}\n\n`
              }
              
              // Examples
              if (result.examples && result.examples.length > 0) {
                formattedOutput += '**Examples:**\n'
                result.examples.forEach((example, idx) => {
                  formattedOutput += `  ${idx + 1}. ${example.name || 'Example'}\n`
                  if (example.description) {
                    formattedOutput += `     ${example.description}\n`
                  }
                })
                formattedOutput += '\n'
              }
              
              // Best Practices
              if (result.best_practices && result.best_practices.length > 0) {
                formattedOutput += '**Best Practices:**\n'
                result.best_practices.forEach(practice => {
                  formattedOutput += `  ✓ ${practice}\n`
                })
                formattedOutput += '\n'
              }
              
              // Tips
              if (result.tips && result.tips.length > 0) {
                formattedOutput += '**Tips:**\n'
                result.tips.forEach(tip => {
                  formattedOutput += `  💡 ${tip}\n`
                })
              }
            }
            
            break
          }
          
          default:
            throw new Error(`Modo inválido: "${mode}". Use: list_all, by_label, ou action_details`)
        }
        
        log.success('[DISCOVER_ACTIONS] Discovery completed', { mode, resultSize: result?.length || 0 })
        
        // Apply intelligent output feedback strategy
        const chatStore = ctx.chatStore
        if (chatStore) {
          // Check output size to determine feedback method
          if (formattedOutput.length < 5000) {
            // Prompt-based feedback for concise results
            chatStore.insertContentIntoInput({ content: formattedOutput })
            log.debug('[DISCOVER_ACTIONS] Results inserted into input')
          } else {
            // Attachment-based feedback for larger results
            const filename = `action_discovery_${mode}_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('[DISCOVER_ACTIONS] Results attached to chat:', filename)
          }
        }
        
        // Return both the raw result and formatted output
        return {
          success: true,
          mode,
          filter_label,
          filter_action,
          data: result,
          formatted: formattedOutput,
          message: formattedOutput
        }
        
      } catch (error) {
        log.error('[DISCOVER_ACTIONS] Discovery failed', { error: error.message })
        throw error
      }
    },
    {
      description: 'Descobre ações disponíveis no sistema (meta-ação para LLM)',
      params: [
        { 
          name: 'mode', 
          type: 'string', 
          required: true,
          description: 'Modo de descoberta: list_all, by_label, action_details'
        },
        { 
          name: 'filter_label', 
          type: 'string', 
          required: false,
          description: 'Label para filtrar (obrigatório para by_label e action_details)'
        },
        { 
          name: 'filter_action', 
          type: 'string', 
          required: false,
          description: 'Nome da ação específica (obrigatório para action_details)'
        }
      ],
      category: 'discovery',
      available: true
    }
  )
}
