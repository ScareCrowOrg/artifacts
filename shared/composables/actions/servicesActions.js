/**
 * Services Actions
 * 
 * Actions for service management and monitoring: get_services_status, get_services_config,
 * update_services_config, test_service_connectivity, get_service_logs, start_service,
 * stop_service, restart_service
 */

import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'

const log = createLogger('action:services')

/**
 * Register services management actions
 * @param {Function} registerAction - Function to register an action
 */
export function registerServicesActions(registerAction) {
  // ========================================
  // SERVICE STATUS AND MONITORING
  // ========================================

  // Action: Get Services Status
  registerAction(
    'get_services_status',
    async (params, ctx) => {
      log.debug('get_services_status - Fetching services status')
      
      try {
        const response = await apiService.fetch('/api/services/status')
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const services = await response.json()
        
        // Format results with markdown
        let formattedOutput = `## 📊 Services Status\n\n`
        formattedOutput += `**Total Services:** ${services.length}\n\n`
        
        // Count by status
        const statusCounts = services.reduce((acc, svc) => {
          acc[svc.status] = (acc[svc.status] || 0) + 1
          return acc
        }, {})
        
        formattedOutput += `**Overview:**\n`
        if (statusCounts.running) formattedOutput += `- 🟢 Running: ${statusCounts.running}\n`
        if (statusCounts.stopped) formattedOutput += `- 🔴 Stopped: ${statusCounts.stopped}\n`
        if (statusCounts.error) formattedOutput += `- ⚠️ Error: ${statusCounts.error}\n`
        if (statusCounts.unknown) formattedOutput += `- ❓ Unknown: ${statusCounts.unknown}\n`
        formattedOutput += `\n`
        
        // List each service
        formattedOutput += `**Service Details:**\n\n`
        services.forEach(svc => {
          const statusIcon = {
            'running': '🟢',
            'stopped': '🔴',
            'error': '⚠️',
            'unknown': '❓'
          }[svc.status] || '❓'
          
          formattedOutput += `### ${statusIcon} ${svc.name}\n`
          formattedOutput += `- **ID:** ${svc.id}\n`
          formattedOutput += `- **Status:** ${svc.status}\n`
          if (svc.port) formattedOutput += `- **Port:** ${svc.port}\n`
          
          if (svc.status === 'running') {
            if (svc.pid) formattedOutput += `- **PID:** ${svc.pid}\n`
            if (svc.uptime !== null && svc.uptime !== undefined) {
              const uptimeHours = (svc.uptime / 3600).toFixed(1)
              formattedOutput += `- **Uptime:** ${uptimeHours}h\n`
            }
            if (svc.memory_mb !== null && svc.memory_mb !== undefined) {
              formattedOutput += `- **Memory:** ${svc.memory_mb.toFixed(1)} MB\n`
            }
            if (svc.cpu_percent !== null && svc.cpu_percent !== undefined) {
              formattedOutput += `- **CPU:** ${svc.cpu_percent.toFixed(1)}%\n`
            }
          }
          
          formattedOutput += `- **Last Check:** ${new Date(svc.last_check).toLocaleString()}\n`
          formattedOutput += `\n`
        })
        
        // Apply intelligent output strategy
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length < 5000) {
            chatStore.insertContentIntoInput({ content: formattedOutput })
            log.debug('get_services_status - Results inserted into input')
          } else {
            const filename = `services_status_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('get_services_status - Results attached to chat:', filename)
          }
        }
        
        log.success('get_services_status - Successfully fetched status')
        return { success: true, data: services, message: 'Services status fetched successfully' }
      } catch (error) {
        log.error('get_services_status - Error:', error)
        throw new Error(`Failed to fetch services status: ${error.message}`)
      }
    },
    {
      description: 'Get current status of all monitored services',
      params: [],
      category: 'services',
      available: true
    }
  )

  // Action: Get Services Config
  registerAction(
    'get_services_config',
    async (params, ctx) => {
      log.debug('get_services_config - Fetching services configuration')
      
      try {
        const response = await apiService.fetch('/api/services/config')
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format results with markdown
        let formattedOutput = `## ⚙️ Services Configuration\n\n`
        formattedOutput += `**Version:** ${data.version || '1.0.0'}\n`
        formattedOutput += `**Last Updated:** ${new Date(data.last_updated).toLocaleString()}\n\n`
        formattedOutput += `**Configured Services:** ${data.services.length}\n\n`
        
        // List each service config
        formattedOutput += `**Service Configurations:**\n\n`
        data.services.forEach(svc => {
          formattedOutput += `### ${svc.name}\n`
          formattedOutput += `- **ID:** ${svc.id}\n`
          formattedOutput += `- **Endpoint:** ${svc.endpoint}\n`
          formattedOutput += `- **Port:** ${svc.port}\n`
          formattedOutput += `- **Enabled:** ${svc.enabled ? '✅ Yes' : '❌ No'}\n`
          formattedOutput += `- **Auto-start:** ${svc.auto_start ? '✅ Yes' : '❌ No'}\n`
          formattedOutput += `\n`
        })
        
        // Apply intelligent output strategy
        const chatStore = ctx.chatStore
        if (chatStore) {
          if (formattedOutput.length < 5000) {
            chatStore.insertContentIntoInput({ content: formattedOutput })
            log.debug('get_services_config - Results inserted into input')
          } else {
            const filename = `services_config_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
            log.debug('get_services_config - Results attached to chat:', filename)
          }
        }
        
        log.success('get_services_config - Successfully fetched configuration')
        return { success: true, data, message: 'Services configuration fetched successfully' }
      } catch (error) {
        log.error('get_services_config - Error:', error)
        throw new Error(`Failed to fetch services configuration: ${error.message}`)
      }
    },
    {
      description: 'Get service configurations',
      params: [],
      category: 'services',
      available: true
    }
  )

  // ========================================
  // SERVICE CONTROL ACTIONS (Placeholder)
  // ========================================

  // Action: Start Service
  registerAction(
    'start_service',
    async (params, ctx) => {
      const { service_id } = params
      
      if (!service_id) {
        throw new Error('Missing required parameter: service_id')
      }
      
      log.debug('start_service - Starting service:', { service_id })
      
      try {
        const response = await apiService.fetch(`/api/services/${encodeURIComponent(service_id)}/start`, {
          method: 'POST'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format results
        const icon = data.success ? '✅' : '⚠️'
        let formattedOutput = `## ${icon} Start Service: ${service_id}\n\n`
        formattedOutput += `**Result:** ${data.success ? 'Success' : 'Failed'}\n`
        formattedOutput += `**Message:** ${data.message}\n\n`
        
        if (!data.success) {
          formattedOutput += `ℹ️ **Note:** Service management is currently limited. Please start services manually if needed.\n`
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.info('start_service - Response received:', data.message)
        return { success: true, data, message: data.message }
      } catch (error) {
        log.error('start_service - Error:', error)
        throw new Error(`Failed to start service: ${error.message}`)
      }
    },
    {
      description: 'Start a monitored service',
      params: [
        { name: 'service_id', type: 'string', required: true }
      ],
      category: 'services',
      available: true
    }
  )

  // Action: Stop Service
  registerAction(
    'stop_service',
    async (params, ctx) => {
      const { service_id } = params
      
      if (!service_id) {
        throw new Error('Missing required parameter: service_id')
      }
      
      log.debug('stop_service - Stopping service:', { service_id })
      
      try {
        const response = await apiService.fetch(`/api/services/${encodeURIComponent(service_id)}/stop`, {
          method: 'POST'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format results
        const icon = data.success ? '✅' : '⚠️'
        let formattedOutput = `## ${icon} Stop Service: ${service_id}\n\n`
        formattedOutput += `**Result:** ${data.success ? 'Success' : 'Failed'}\n`
        formattedOutput += `**Message:** ${data.message}\n\n`
        
        if (!data.success) {
          formattedOutput += `ℹ️ **Note:** Service management is currently limited. Please stop services manually if needed.\n`
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.info('stop_service - Response received:', data.message)
        return { success: true, data, message: data.message }
      } catch (error) {
        log.error('stop_service - Error:', error)
        throw new Error(`Failed to stop service: ${error.message}`)
      }
    },
    {
      description: 'Stop a monitored service',
      params: [
        { name: 'service_id', type: 'string', required: true }
      ],
      category: 'services',
      available: true
    }
  )

  // Action: Restart Service
  registerAction(
    'restart_service',
    async (params, ctx) => {
      const { service_id } = params
      
      if (!service_id) {
        throw new Error('Missing required parameter: service_id')
      }
      
      log.debug('restart_service - Restarting service:', { service_id })
      
      try {
        const response = await apiService.fetch(`/api/services/${encodeURIComponent(service_id)}/restart`, {
          method: 'POST'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format results
        const icon = data.success ? '✅' : '⚠️'
        let formattedOutput = `## ${icon} Restart Service: ${service_id}\n\n`
        formattedOutput += `**Result:** ${data.success ? 'Success' : 'Failed'}\n`
        formattedOutput += `**Message:** ${data.message}\n\n`
        
        if (!data.success) {
          formattedOutput += `ℹ️ **Note:** Service management is currently limited. Please restart services manually if needed.\n`
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.info('restart_service - Response received:', data.message)
        return { success: true, data, message: data.message }
      } catch (error) {
        log.error('restart_service - Error:', error)
        throw new Error(`Failed to restart service: ${error.message}`)
      }
    },
    {
      description: 'Restart a monitored service',
      params: [
        { name: 'service_id', type: 'string', required: true }
      ],
      category: 'services',
      available: true
    }
  )
}
