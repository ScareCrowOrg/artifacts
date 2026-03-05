/**
 * System Actions
 * 
 * Actions for system management and monitoring: get_system_status
 */

import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'

const log = createLogger('action:system')

/**
 * Register system management actions
 * @param {Function} registerAction - Function to register an action
 */
export function registerSystemActions(registerAction) {
  // Action: Get System Status
  registerAction(
    'get_system_status',
    async (params, ctx) => {
      log.debug('get_system_status - Fetching system status')
      
      try {
        const response = await apiService.fetch('/api/system/status')
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format results with markdown
        const statusIcon = data.status === 'operational' ? '✅' : '❌'
        
        let formattedOutput = `## ${statusIcon} System Status\n\n`
        formattedOutput += `**Status:** ${data.status}\n`
        formattedOutput += `**Version:** ${data.version}\n\n`
        
        if (data.statistics) {
          formattedOutput += `**📊 Statistics:**\n`
          formattedOutput += `- **Users:** ${data.statistics.users}\n`
          formattedOutput += `- **Cells:** ${data.statistics.cells}\n`
          formattedOutput += `- **Books:** ${data.statistics.books}\n`
          formattedOutput += `- **Notebook Item Types:** ${data.statistics.notebook_item_types}\n`
          formattedOutput += `\n`
        }
        
        if (data.status === 'operational') {
          formattedOutput += `🟢 **All systems operational**\n`
        } else if (data.error) {
          formattedOutput += `🔴 **Error:** ${data.error}\n`
        }
        
        // Apply intelligent output strategy
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
          log.debug('get_system_status - Results inserted into input')
        }
        
        log.success('get_system_status - Successfully fetched status')
        return { success: true, data, message: 'System status fetched successfully' }
      } catch (error) {
        log.error('get_system_status - Error:', error)
        throw new Error(`Failed to fetch system status: ${error.message}`)
      }
    },
    {
      description: 'Get overall system status and statistics',
      params: [],
      category: 'system',
      available: true
    }
  )
}
