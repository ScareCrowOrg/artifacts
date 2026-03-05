/**
 * Traces Actions
 * 
 * Actions for trace management: get_trace_by_conversation_id, get_recent_traces
 */

import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'

const log = createLogger('action:traces')

/**
 * Format a single trace fragment for display
 * @param {Object} fragment - Trace fragment
 * @param {number} index - Fragment index
 * @returns {string} Formatted fragment
 */
function formatTraceFragment(fragment, index) {
  let formatted = `**Fragment ${index + 1}**\n`
  
  if (fragment.stage) {
    formatted += `  Stage: ${fragment.stage}\n`
  }
  
  if (fragment.timestamp) {
    formatted += `  Timestamp: ${new Date(fragment.timestamp).toLocaleString()}\n`
  }
  
  if (fragment.data) {
    // For large data objects, show a preview
    const dataStr = JSON.stringify(fragment.data, null, 2)
    if (dataStr.length > 200) {
      formatted += `  Data: ${dataStr.substring(0, 200)}... (${dataStr.length} chars)\n`
    } else {
      formatted += `  Data: ${dataStr}\n`
    }
  }
  
  // Include any other fragment properties
  const standardKeys = ['stage', 'timestamp', 'data']
  const otherKeys = Object.keys(fragment).filter(k => !standardKeys.includes(k))
  if (otherKeys.length > 0) {
    formatted += `  Other: ${otherKeys.join(', ')}\n`
  }
  
  return formatted
}

/**
 * Format trace summary for display
 * @param {Object} trace - Trace summary object
 * @returns {string} Formatted trace summary
 */
function formatTraceSummary(trace) {
  let formatted = `**${trace.conversation_id}**\n`
  formatted += `  Trace ID: ${trace.trace_id}\n`
  
  if (trace.session_id) {
    formatted += `  Session: ${trace.session_id}\n`
  }
  
  if (trace.user_message) {
    formatted += `  Message: "${trace.user_message}"\n`
  }
  
  if (trace.target_llm) {
    formatted += `  LLM: ${trace.target_llm}\n`
  }
  
  if (trace.created_at) {
    formatted += `  Created: ${new Date(trace.created_at).toLocaleString()}\n`
  }
  
  formatted += `  Fragments: ${trace.fragments_count}\n`
  
  return formatted
}

/**
 * Register traces management actions
 * @param {Function} registerAction - Function to register an action
 */
export function registerTracesActions(registerAction) {
  // Action: Get Trace by Conversation ID
  registerAction(
    'get_trace_by_conversation_id',
    async (params, ctx) => {
      const { conversation_id } = params
      
      if (!conversation_id) {
        throw new Error('Missing required parameter: conversation_id')
      }
      
      log.debug('get_trace_by_conversation_id - Fetching trace:', { conversation_id })
      
      try {
        const response = await apiService.fetch(
          `/api/traces/conversation/${encodeURIComponent(conversation_id)}`
        )
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the trace data for display
        let formattedOutput = `🔍 **Conversation Trace**\n\n`
        
        formattedOutput += `**Metadata:**\n`
        formattedOutput += `  - Trace ID: ${data.trace_id}\n`
        formattedOutput += `  - Conversation ID: ${data.conversation_id}\n`
        
        if (data.session_id) {
          formattedOutput += `  - Session ID: ${data.session_id}\n`
        }
        
        if (data.target_llm) {
          formattedOutput += `  - Target LLM: ${data.target_llm}\n`
        }
        
        if (data.created_at) {
          formattedOutput += `  - Created: ${new Date(data.created_at).toLocaleString()}\n`
        }
        
        if (data.user_message) {
          formattedOutput += `\n**User Message:**\n${data.user_message}\n`
        }
        
        formattedOutput += `\n**Fragments:** ${data.fragments_count} captured\n`
        
        // Format fragments if present
        if (data.fragments && data.fragments.length > 0) {
          formattedOutput += `\n---\n\n`
          
          data.fragments.forEach((fragment, index) => {
            formattedOutput += formatTraceFragment(fragment, index)
            if (index < data.fragments.length - 1) {
              formattedOutput += '\n'
            }
          })
        } else {
          formattedOutput += `\n*No fragments captured*`
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          // Traces can be large with many fragments, use attachment for >5KB
          if (formattedOutput.length > 5000 || (data.fragments && data.fragments.length > 10)) {
            const filename = `trace_${conversation_id}_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('get_trace_by_conversation_id - Results attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          }
        }
        
        log.success('get_trace_by_conversation_id - Trace fetched successfully:', { 
          conversation_id,
          fragments_count: data.fragments_count
        })
        return { 
          success: true, 
          data, 
          message: `Retrieved trace for conversation ${conversation_id}` 
        }
      } catch (error) {
        log.error('get_trace_by_conversation_id - Error:', error)
        throw new Error(`Failed to fetch trace: ${error.message}`)
      }
    },
    {
      description: 'Retrieve trace data for a specific conversation',
      params: [
        { name: 'conversation_id', type: 'string', required: true }
      ],
      category: 'traces',
      available: true
    }
  )

  // Action: Get Recent Traces
  registerAction(
    'get_recent_traces',
    async (params, ctx) => {
      const { 
        limit = 10,
        offset = 0
      } = params
      
      log.debug('get_recent_traces - Fetching recent traces:', { limit, offset })
      
      try {
        // Build query parameters
        const queryParams = new URLSearchParams()
        queryParams.append('limit', limit.toString())
        queryParams.append('offset', offset.toString())
        
        const response = await apiService.fetch(`/api/traces/recent?${queryParams}`)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the traces for display
        let formattedOutput = `📋 **Recent Traces** (${data.traces.length} of ${data.count} total)\n\n`
        
        if (data.traces.length === 0) {
          formattedOutput += '*No traces found*'
        } else {
          formattedOutput += `---\n\n`
          
          data.traces.forEach((trace, index) => {
            formattedOutput += formatTraceSummary(trace)
            if (index < data.traces.length - 1) {
              formattedOutput += '\n---\n\n'
            }
          })
          
          // Add pagination info
          formattedOutput += `\n\n📄 **Pagination:**\n`
          formattedOutput += `  - Showing: ${offset + 1}-${offset + data.traces.length} of ${data.count}\n`
          formattedOutput += `  - Page Size: ${limit}\n`
          
          if (offset + data.traces.length < data.count) {
            const nextOffset = offset + limit
            formattedOutput += `\n💡 *More traces available. Use offset=${nextOffset} to see next page.*`
          }
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          // Use attachment for large results (>5KB or many traces)
          if (formattedOutput.length > 5000 || data.traces.length > 20) {
            const filename = `recent_traces_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('get_recent_traces - Results attached to chat:', filename)
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          }
        }
        
        log.success('get_recent_traces - Traces fetched successfully:', { 
          count: data.traces.length,
          total: data.count
        })
        return { 
          success: true, 
          data, 
          message: `Retrieved ${data.traces.length} of ${data.count} recent traces` 
        }
      } catch (error) {
        log.error('get_recent_traces - Error:', error)
        throw new Error(`Failed to fetch recent traces: ${error.message}`)
      }
    },
    {
      description: 'Retrieve recent trace summaries with pagination',
      params: [
        { name: 'limit', type: 'integer', required: false },
        { name: 'offset', type: 'integer', required: false }
      ],
      category: 'traces',
      available: true
    }
  )
}
