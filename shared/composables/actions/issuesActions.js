/**
 * Issues Actions
 * 
 * Actions for issues management: trigger_manual_ingest, trigger_manual_processing,
 * start_automatic_monitoring, stop_automatic_monitoring, pause_queue_processing,
 * resume_queue_processing
 */

import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'

const log = createLogger('action:issues')

/**
 * Register issues management actions
 * @param {Function} registerAction - Function to register an action
 */
export function registerIssuesActions(registerAction) {
  // Action: Trigger Manual Ingest
  registerAction(
    'trigger_manual_ingest',
    async (params, ctx) => {
      const { source_dir, dry_run } = params
      
      log.debug('trigger_manual_ingest - Triggering ingest:', { source_dir, dry_run })
      
      try {
        const response = await apiService.fetch('/api/issues/ingest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source_dir: source_dir || null,
            dry_run: dry_run || false
          })
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        const formattedOutput = `📥 **Manual Ingest Triggered**\n\n` +
          `**Status:** ${data.status}\n` +
          `${data.message ? `**Message:** ${data.message}\n` : ''}` +
          `${source_dir ? `**Source:** ${source_dir}\n` : ''}` +
          `${dry_run ? `**Mode:** Dry Run (no actual ingestion)\n` : ''}` +
          `\n✅ Ingestion process started`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('trigger_manual_ingest - Ingest triggered successfully')
        return { success: true, data, message: 'Ingest triggered successfully' }
      } catch (error) {
        log.error('trigger_manual_ingest - Error:', error)
        throw new Error(`Failed to trigger ingest: ${error.message}`)
      }
    },
    {
      description: 'Trigger manual ingestion of documents',
      params: [
        { name: 'source_dir', type: 'string', required: false },
        { name: 'dry_run', type: 'boolean', required: false }
      ],
      category: 'issues',
      available: true
    }
  )
  
  // Action: Trigger Manual Processing
  registerAction(
    'trigger_manual_processing',
    async (params, ctx) => {
      log.debug('trigger_manual_processing - Triggering processing')
      
      try {
        const response = await apiService.fetch('/api/issues/process', {
          method: 'POST'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        const formattedOutput = `⚡ **Manual Processing Triggered**\n\n` +
          `**Status:** ${data.status}\n` +
          `**Processed:** ${data.processed} cell(s)\n` +
          `\n✅ Processing completed`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('trigger_manual_processing - Processing triggered successfully')
        return { success: true, data, message: 'Processing triggered successfully' }
      } catch (error) {
        log.error('trigger_manual_processing - Error:', error)
        throw new Error(`Failed to trigger processing: ${error.message}`)
      }
    },
    {
      description: 'Trigger manual processing of pending cells',
      params: [],
      category: 'issues',
      available: true
    }
  )
  
  // Action: Start Automatic Monitoring
  registerAction(
    'start_automatic_monitoring',
    async (params, ctx) => {
      log.debug('start_automatic_monitoring - Starting monitoring')
      
      try {
        const response = await apiService.fetch('/api/issues/monitoring/start', {
          method: 'POST'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        const formattedOutput = `▶️ **Automatic Monitoring Started**\n\n` +
          `**Status:** ${data.status}\n` +
          `\n✅ Background monitoring loop is now active`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('start_automatic_monitoring - Monitoring started')
        return { success: true, data, message: 'Monitoring started successfully' }
      } catch (error) {
        log.error('start_automatic_monitoring - Error:', error)
        throw new Error(`Failed to start monitoring: ${error.message}`)
      }
    },
    {
      description: 'Start automatic monitoring loop',
      params: [],
      category: 'issues',
      available: true
    }
  )
  
  // Action: Stop Automatic Monitoring
  registerAction(
    'stop_automatic_monitoring',
    async (params, ctx) => {
      log.debug('stop_automatic_monitoring - Stopping monitoring')
      
      try {
        const response = await apiService.fetch('/api/issues/monitoring/stop', {
          method: 'POST'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        const formattedOutput = `⏹️ **Automatic Monitoring Stopped**\n\n` +
          `**Status:** ${data.status}\n` +
          `\n✅ Background monitoring loop has been stopped`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('stop_automatic_monitoring - Monitoring stopped')
        return { success: true, data, message: 'Monitoring stopped successfully' }
      } catch (error) {
        log.error('stop_automatic_monitoring - Error:', error)
        throw new Error(`Failed to stop monitoring: ${error.message}`)
      }
    },
    {
      description: 'Stop automatic monitoring loop',
      params: [],
      category: 'issues',
      available: true
    }
  )
  
  // Action: Pause Queue Processing
  registerAction(
    'pause_queue_processing',
    async (params, ctx) => {
      log.debug('pause_queue_processing - Pausing processing')
      
      try {
        const response = await apiService.fetch('/api/issues/processing/pause', {
          method: 'POST'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        const formattedOutput = `⏸️ **Queue Processing Paused**\n\n` +
          `**Status:** ${data.status}\n` +
          `\n✅ Cell processing is now paused (monitoring continues)`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('pause_queue_processing - Processing paused')
        return { success: true, data, message: 'Processing paused successfully' }
      } catch (error) {
        log.error('pause_queue_processing - Error:', error)
        throw new Error(`Failed to pause processing: ${error.message}`)
      }
    },
    {
      description: 'Pause queue processing',
      params: [],
      category: 'issues',
      available: true
    }
  )
  
  // Action: Resume Queue Processing
  registerAction(
    'resume_queue_processing',
    async (params, ctx) => {
      log.debug('resume_queue_processing - Resuming processing')
      
      try {
        const response = await apiService.fetch('/api/issues/processing/resume', {
          method: 'POST'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        const formattedOutput = `▶️ **Queue Processing Resumed**\n\n` +
          `**Status:** ${data.status}\n` +
          `\n✅ Cell processing has been resumed`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.success('resume_queue_processing - Processing resumed')
        return { success: true, data, message: 'Processing resumed successfully' }
      } catch (error) {
        log.error('resume_queue_processing - Error:', error)
        throw new Error(`Failed to resume processing: ${error.message}`)
      }
    },
    {
      description: 'Resume queue processing',
      params: [],
      category: 'issues',
      available: true
    }
  )
  
  // Action: Get Issues Queue Cells
  registerAction(
    'get_issues_queue_cells',
    async (params, ctx) => {
      const { page = 1, limit = 20, status, item_type } = params
      
      log.debug('get_issues_queue_cells - Fetching issues queue cells:', { page, limit, status, item_type })
      
      try {
        // Build query parameters
        const queryParams = new URLSearchParams()
        queryParams.append('page', page.toString())
        queryParams.append('limit', limit.toString())
        if (status) queryParams.append('status', status)
        if (item_type) queryParams.append('item_type', item_type)
        
        const response = await apiService.fetch(`/api/issues-dashboard/cells?${queryParams}`)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the paginated results
        let formattedOutput = `📋 **Issues Queue - Page ${data.current_page}/${data.total_pages}**\n\n`
        
        // Add issue counts summary
        if (data.issue_counts) {
          formattedOutput += `**Queue Status:**\n`
          formattedOutput += `- ⏳ Pending: ${data.issue_counts.pendente}\n`
          formattedOutput += `- 🔄 Running: ${data.issue_counts.executando}\n`
          formattedOutput += `- ✅ Completed: ${data.issue_counts.finalizado}\n`
          formattedOutput += `- ❌ Error: ${data.issue_counts.erro}\n`
          formattedOutput += `- **Total:** ${data.total_items}\n\n`
        }
        
        // Add filter info
        if (status) {
          formattedOutput += `**Filter:** Status = ${status}\n`
        }
        if (item_type) {
          formattedOutput += `**Filter:** Type = ${item_type}\n`
        }
        if (status || item_type) {
          formattedOutput += `\n`
        }
        
        // List cells
        if (data.items.length === 0) {
          formattedOutput += `*No cells found*\n`
        } else {
          formattedOutput += `**Cells (${data.items.length} on this page):**\n\n`
          
          data.items.forEach((cell, index) => {
            const statusIcon = {
              'pending': '⏳',
              'running': '🔄',
              'completed': '✅',
              'error': '❌'
            }[cell.status] || '❓'
            
            const cellNum = (data.current_page - 1) * data.items_per_page + index + 1
            formattedOutput += `${cellNum}. ${statusIcon} **${cell.title || cell.id.substring(0, 8)}**\n`
            formattedOutput += `   - ID: \`${cell.id}\`\n`
            formattedOutput += `   - Status: ${cell.status}\n`
            if (cell.notebook_item_type_id) {
              formattedOutput += `   - Type: ${cell.notebook_item_type_id}\n`
            }
            formattedOutput += `   - Assignee: ${cell.assignee_id}\n`
            formattedOutput += `\n`
          })
        }
        
        // Add pagination info
        if (data.total_pages > 1) {
          formattedOutput += `\n---\n`
          formattedOutput += `**Pagination:** Page ${data.current_page} of ${data.total_pages} (${data.total_items} total items)\n`
          if (data.current_page < data.total_pages) {
            formattedOutput += `💡 *To see next page, use page: ${data.current_page + 1}*\n`
          }
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length > 5000) {
            // Large result - use attachment
            const filename = `issues_queue_page${data.current_page}_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('get_issues_queue_cells - Results attached to chat:', filename)
          } else {
            // Small result - insert into input
            chatStore.insertContentIntoInput({ content: formattedOutput })
            log.debug('get_issues_queue_cells - Results inserted into input')
          }
        }
        
        log.success('get_issues_queue_cells - Successfully fetched cells')
        return { success: true, data, message: 'Issues queue cells fetched successfully' }
      } catch (error) {
        log.error('get_issues_queue_cells - Error:', error)
        throw new Error(`Failed to fetch issues queue cells: ${error.message}`)
      }
    },
    {
      description: 'Get paginated list of issues-queue cells with optional filtering',
      params: [
        { name: 'page', type: 'integer', required: false },
        { name: 'limit', type: 'integer', required: false },
        { name: 'status', type: 'string', required: false },
        { name: 'item_type', type: 'string', required: false }
      ],
      category: 'issues',
      available: true
    }
  )
  
  // Action: Get Cell Details
  registerAction(
    'get_cell_details',
    async (params, ctx) => {
      const { cell_id } = params
      
      if (!cell_id) {
        throw new Error('Missing required parameter: cell_id')
      }
      
      log.debug('get_cell_details - Fetching cell details:', { cell_id })
      
      try {
        const response = await apiService.fetch(`/api/issues-dashboard/cells/${encodeURIComponent(cell_id)}`)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const cell = await response.json()
        
        // Format cell details
        const statusIcon = {
          'pending': '⏳',
          'running': '🔄',
          'completed': '✅',
          'error': '❌'
        }[cell.status] || '❓'
        
        let formattedOutput = `🔍 **Cell Details**\n\n`
        formattedOutput += `**${statusIcon} ${cell.title || 'Untitled Cell'}**\n\n`
        
        // Basic info
        formattedOutput += `**Metadata:**\n`
        formattedOutput += `- ID: \`${cell.id}\`\n`
        formattedOutput += `- Status: ${cell.status}\n`
        formattedOutput += `- Assignee: ${cell.assignee_id}\n`
        if (cell.book_id) {
          formattedOutput += `- Book: ${cell.book_id}\n`
        }
        if (cell.notebook_item_type_id) {
          formattedOutput += `- Type: ${cell.notebook_item_type_id}\n`
        }
        formattedOutput += `\n`
        
        // Timestamps
        formattedOutput += `**Timeline:**\n`
        formattedOutput += `- Created: ${new Date(cell.created_at).toLocaleString()}\n`
        formattedOutput += `- Updated: ${new Date(cell.updated_at).toLocaleString()}\n`
        formattedOutput += `\n`
        
        // Fragments
        if (cell.fragments && cell.fragments.length > 0) {
          formattedOutput += `**Fragments (${cell.fragments.length}):**\n`
          cell.fragments.forEach((fragment, index) => {
            formattedOutput += `${index + 1}. Type: ${fragment.type || 'unknown'}\n`
            if (fragment.content) {
              const preview = fragment.content.substring(0, 100)
              formattedOutput += `   Preview: ${preview}${fragment.content.length > 100 ? '...' : ''}\n`
            }
          })
          formattedOutput += `\n`
        }
        
        // Initial data
        if (cell.initial_data && Object.keys(cell.initial_data).length > 0) {
          formattedOutput += `**Initial Data:**\n`
          formattedOutput += `\`\`\`json\n${JSON.stringify(cell.initial_data, null, 2)}\n\`\`\`\n\n`
        }
        
        // Refs
        if (cell.refs && Object.keys(cell.refs).length > 0) {
          formattedOutput += `**References:**\n`
          Object.entries(cell.refs).forEach(([key, value]) => {
            formattedOutput += `- ${key}: ${value}\n`
          })
          formattedOutput += `\n`
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length > 5000) {
            // Large result - use attachment
            const filename = `cell_${cell.id.substring(0, 8)}_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('get_cell_details - Results attached to chat:', filename)
          } else {
            // Small result - insert into input
            chatStore.insertContentIntoInput({ content: formattedOutput })
            log.debug('get_cell_details - Results inserted into input')
          }
        }
        
        log.success('get_cell_details - Successfully fetched cell details')
        return { success: true, data: cell, message: 'Cell details fetched successfully' }
      } catch (error) {
        log.error('get_cell_details - Error:', error)
        throw new Error(`Failed to fetch cell details: ${error.message}`)
      }
    },
    {
      description: 'Get detailed information about a specific cell',
      params: [
        { name: 'cell_id', type: 'string', required: true }
      ],
      category: 'issues',
      available: true
    }
  )

  // ========================================
  // ISSUES DASHBOARD - MONITORING ACTIONS
  // ========================================

  // Action: Get Monitoring Status
  registerAction(
    'get_monitoring_status',
    async (params, ctx) => {
      log.debug('get_monitoring_status - Fetching monitoring status')
      
      try {
        // Call backend endpoint (GET /issues/dashboard/monitoring/status)
        const response = await apiService.fetch('/api/issues/dashboard/monitoring/status')
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format results with markdown
        let formattedOutput = `## 📊 Monitoring Status\n\n`
        formattedOutput += `**Active:** ${data.active ? '✅ Yes' : '❌ No'}\n`
        formattedOutput += `**Task Running:** ${data.task_running ? '✅ Yes' : '❌ No'}\n`
        formattedOutput += `**Polling Interval:** ${data.polling_interval} seconds\n`
        formattedOutput += `**Max Concurrent Cells:** ${data.max_concurrent_cells}\n\n`
        
        if (data.active) {
          formattedOutput += `🟢 **Status:** Monitoring is active and processing cells automatically\n`
        } else {
          formattedOutput += `🔴 **Status:** Monitoring is inactive - no automatic processing\n`
        }
        
        // Apply intelligent output strategy
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
          log.debug('get_monitoring_status - Results inserted into input')
        }
        
        log.success('get_monitoring_status - Successfully fetched status')
        return { success: true, data, message: 'Monitoring status fetched successfully' }
      } catch (error) {
        log.error('get_monitoring_status - Error:', error)
        throw new Error(`Failed to fetch monitoring status: ${error.message}`)
      }
    },
    {
      description: 'Get current status of the orchestrator monitoring loop',
      params: [],
      category: 'issues',
      available: true
    }
  )

  // Action: Start Monitoring
  registerAction(
    'start_monitoring',
    async (params, ctx) => {
      log.debug('start_monitoring - Starting orchestrator monitoring')
      
      try {
        // Call backend endpoint (POST /issues/dashboard/monitoring/start)
        const response = await apiService.fetch('/api/issues/dashboard/monitoring/start', {
          method: 'POST'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format results with markdown
        let formattedOutput = `## ▶️ Monitoring Started\n\n`
        formattedOutput += `**Status:** ${data.status}\n`
        formattedOutput += `**Message:** ${data.message}\n\n`
        formattedOutput += `🟢 Automatic cell processing is now **ACTIVE**\n\n`
        formattedOutput += `The orchestrator will continuously monitor the issues-queue\n`
        formattedOutput += `and process pending cells automatically.\n`
        
        // Apply intelligent output strategy
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
          log.debug('start_monitoring - Results inserted into input')
        }
        
        log.success('start_monitoring - Successfully started monitoring')
        return { success: true, data, message: 'Monitoring started successfully' }
      } catch (error) {
        log.error('start_monitoring - Error:', error)
        throw new Error(`Failed to start monitoring: ${error.message}`)
      }
    },
    {
      description: 'Start the orchestrator monitoring loop for automatic cell processing',
      params: [],
      category: 'issues',
      available: true
    }
  )

  // Action: Stop Monitoring
  registerAction(
    'stop_monitoring',
    async (params, ctx) => {
      log.debug('stop_monitoring - Stopping orchestrator monitoring')
      
      try {
        // Call backend endpoint (POST /issues/dashboard/monitoring/stop)
        const response = await apiService.fetch('/api/issues/dashboard/monitoring/stop', {
          method: 'POST'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format results with markdown
        let formattedOutput = `## ⏸️ Monitoring Stopped\n\n`
        formattedOutput += `**Status:** ${data.status}\n`
        formattedOutput += `**Message:** ${data.message}\n\n`
        formattedOutput += `🔴 Automatic cell processing is now **PAUSED**\n\n`
        formattedOutput += `The orchestrator has stopped monitoring the issues-queue.\n`
        formattedOutput += `Pending cells will not be processed until monitoring restarts.\n`
        
        // Apply intelligent output strategy
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
          log.debug('stop_monitoring - Results inserted into input')
        }
        
        log.success('stop_monitoring - Successfully stopped monitoring')
        return { success: true, data, message: 'Monitoring stopped successfully' }
      } catch (error) {
        log.error('stop_monitoring - Error:', error)
        throw new Error(`Failed to stop monitoring: ${error.message}`)
      }
    },
    {
      description: 'Stop the orchestrator monitoring loop to pause automatic cell processing',
      params: [],
      category: 'issues',
      available: true
    }
  )
}
