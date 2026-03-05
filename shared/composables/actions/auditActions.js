/**
 * Audit Actions
 * 
 * Actions for audit log management: get_audit_logs, get_audit_stats
 */

import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'

const log = createLogger('action:audit')

/**
 * Format a single audit log entry for display
 * @param {Object} logEntry - Audit log entry
 * @returns {string} Formatted log entry
 */
function formatAuditLogEntry(logEntry) {
  let formatted = `**${logEntry.event_type}**\n`
  formatted += `  Timestamp: ${new Date(logEntry.timestamp).toLocaleString()}\n`
  
  if (logEntry.user_id) {
    formatted += `  User ID: ${logEntry.user_id}\n`
  }
  
  if (logEntry.details) {
    formatted += `  Details:\n`
    for (const [key, value] of Object.entries(logEntry.details)) {
      if (typeof value === 'object') {
        formatted += `    ${key}: ${JSON.stringify(value)}\n`
      } else {
        formatted += `    ${key}: ${value}\n`
      }
    }
  }
  
  return formatted
}

/**
 * Register audit management actions
 * @param {Function} registerAction - Function to register an action
 */
export function registerAuditActions(registerAction) {
  // Action: Get Audit Logs
  registerAction(
    'get_audit_logs',
    async (params, ctx) => {
      const { 
        event_type,
        user_id,
        start_date,
        end_date,
        skip = 0,
        limit = 100
      } = params
      
      log.debug('get_audit_logs - Fetching audit logs:', { 
        event_type, 
        user_id, 
        start_date, 
        end_date, 
        skip, 
        limit 
      })
      
      try {
        // Build query parameters
        const queryParams = new URLSearchParams()
        
        if (event_type) queryParams.append('event_type', event_type)
        if (user_id) queryParams.append('user_id', user_id)
        if (start_date) queryParams.append('start_date', start_date)
        if (end_date) queryParams.append('end_date', end_date)
        queryParams.append('skip', skip.toString())
        queryParams.append('limit', limit.toString())
        
        const response = await apiService.fetch(`/api/audit/logs?${queryParams}`)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the audit logs for display
        let formattedOutput = `🔍 **Audit Logs** (${data.logs.length} of ${data.total} total)\n\n`
        
        // Add filter summary if filters are active
        const activeFilters = []
        if (event_type) activeFilters.push(`Event Type: ${event_type}`)
        if (user_id) activeFilters.push(`User: ${user_id}`)
        if (start_date) activeFilters.push(`From: ${start_date}`)
        if (end_date) activeFilters.push(`To: ${end_date}`)
        
        if (activeFilters.length > 0) {
          formattedOutput += `**Filters Applied:**\n${activeFilters.map(f => `  - ${f}`).join('\n')}\n\n`
        }
        
        if (data.logs.length === 0) {
          formattedOutput += '*No audit logs found matching the criteria*'
        } else {
          formattedOutput += `---\n\n`
          data.logs.forEach((logEntry, index) => {
            formattedOutput += formatAuditLogEntry(logEntry)
            if (index < data.logs.length - 1) {
              formattedOutput += '\n---\n\n'
            }
          })
          
          // Add pagination info
          formattedOutput += `\n\n📄 **Pagination:**\n`
          formattedOutput += `  - Showing: ${skip + 1}-${skip + data.logs.length} of ${data.total}\n`
          formattedOutput += `  - Page Size: ${limit}\n`
          
          if (skip + data.logs.length < data.total) {
            const nextSkip = skip + limit
            formattedOutput += `\n💡 *More logs available. Use skip=${nextSkip} to see next page.*`
          }
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          // Use attachment for large results (>5KB or many logs)
          if (formattedOutput.length > 5000 || data.logs.length > 20) {
            const filename = `audit_logs_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('get_audit_logs - Results attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          }
        }
        
        log.success('get_audit_logs - Audit logs fetched successfully:', { 
          count: data.logs.length, 
          total: data.total 
        })
        return { 
          success: true, 
          data, 
          message: `Retrieved ${data.logs.length} of ${data.total} audit logs` 
        }
      } catch (error) {
        log.error('get_audit_logs - Error:', error)
        throw new Error(`Failed to fetch audit logs: ${error.message}`)
      }
    },
    {
      description: 'Retrieve audit logs with filtering and pagination (admin only)',
      params: [
        { name: 'event_type', type: 'string', required: false },
        { name: 'user_id', type: 'string', required: false },
        { name: 'start_date', type: 'string', required: false },
        { name: 'end_date', type: 'string', required: false },
        { name: 'skip', type: 'integer', required: false },
        { name: 'limit', type: 'integer', required: false }
      ],
      category: 'audit',
      available: true
    }
  )

  // Action: Get Audit Stats
  registerAction(
    'get_audit_stats',
    async (params, ctx) => {
      log.debug('get_audit_stats - Fetching audit statistics')
      
      try {
        const response = await apiService.fetch('/api/audit/stats')
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the statistics for display
        let formattedOutput = `📊 **Audit Log Statistics**\n\n`
        
        formattedOutput += `**Event Counts:**\n`
        formattedOutput += `  - Permission Denied: ${data.permission_denied_count}\n`
        formattedOutput += `  - Role Changes: ${data.role_changes_count}\n`
        formattedOutput += `  - Admin Actions: ${data.admin_actions_count}\n`
        
        if (data.top_denied_permissions && data.top_denied_permissions.length > 0) {
          formattedOutput += `\n**Top Denied Permissions:**\n`
          data.top_denied_permissions.forEach((item, index) => {
            formattedOutput += `  ${index + 1}. ${item.permission}: ${item.count} time${item.count !== 1 ? 's' : ''}\n`
          })
        } else {
          formattedOutput += `\n*No denied permissions recorded*\n`
        }
        
        // Add summary insights
        const totalEvents = data.permission_denied_count + data.role_changes_count + data.admin_actions_count
        formattedOutput += `\n**Summary:**\n`
        formattedOutput += `  - Total Events: ${totalEvents}\n`
        
        if (data.permission_denied_count > 0) {
          const deniedPercentage = ((data.permission_denied_count / totalEvents) * 100).toFixed(1)
          formattedOutput += `  - Permission Denials: ${deniedPercentage}% of all events\n`
        }
        
        // Add recommendations based on data
        if (data.permission_denied_count > 10) {
          formattedOutput += `\n💡 **Insight:** High number of permission denials detected. Consider reviewing user permissions.\n`
        }
        
        if (data.top_denied_permissions && data.top_denied_permissions.length > 0) {
          const topPermission = data.top_denied_permissions[0]
          formattedOutput += `💡 **Most Denied Permission:** "${topPermission.permission}" (${topPermission.count} denials)\n`
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          // Stats are typically concise, use prompt-based feedback
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('get_audit_stats - Audit statistics fetched successfully')
        return { 
          success: true, 
          data, 
          message: 'Retrieved audit statistics' 
        }
      } catch (error) {
        log.error('get_audit_stats - Error:', error)
        throw new Error(`Failed to fetch audit statistics: ${error.message}`)
      }
    },
    {
      description: 'Retrieve audit log statistics and insights (admin only)',
      params: [],
      category: 'audit',
      available: true
    }
  )
}
