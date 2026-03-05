/**
 * Sessions Actions
 * 
 * Actions for session management: create_session, list_user_sessions, close_session
 */

import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'

const log = createLogger('action:sessions')

/**
 * Register sessions management actions
 * @param {Function} registerAction - Function to register an action
 */
export function registerSessionsActions(registerAction) {
  // Action: Create Session
  registerAction(
    'create_session',
    async (params, ctx) => {
      const { user_id } = params
      
      // Validate required parameters
      if (!user_id) {
        log.error('create_session - Missing required parameter: user_id')
        throw new Error('user_id is required')
      }
      
      log.debug('create_session - Creating session for user:', { user_id })
      
      try {
        const response = await apiService.fetch('/api/sessions/create', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ user_id })
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the session creation result
        let formattedOutput = `🔑 **Session Created Successfully**\n\n`
        formattedOutput += `**Session ID:** ${data.session.id}\n`
        formattedOutput += `**User ID:** ${data.session.user_id}\n`
        formattedOutput += `**Created:** ${new Date(data.session.created_at).toLocaleString()}\n`
        formattedOutput += `**Expires:** ${new Date(data.session.expires_at).toLocaleString()}\n`
        formattedOutput += `**Active:** ${data.session.active ? '✅ Yes' : '❌ No'}\n\n`
        
        // Token info (masked for security)
        const tokenPreview = data.token ? `${data.token.substring(0, 10)}...${data.token.substring(data.token.length - 10)}` : 'N/A'
        formattedOutput += `**Token Preview:** ${tokenPreview}\n\n`
        
        // User info
        if (data.user) {
          formattedOutput += `**User Details:**\n`
          formattedOutput += `  • Name: ${data.user.name || 'N/A'}\n`
          formattedOutput += `  • Email: ${data.user.email || 'N/A'}\n`
        }
        
        formattedOutput += `\n✨ Token generated and ready for use in authenticated requests.`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          // Sessions info is concise, use prompt-based feedback
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.info('create_session - Session created successfully:', { session_id: data.session.id })
        return { success: true, data }
      } catch (error) {
        log.error('create_session - Error creating session:', error)
        throw error
      }
    },
    {
      description: 'Create a new user session and generate JWT token',
      params: [
        { name: 'user_id', type: 'string', required: true, description: 'User UUID to create session for' }
      ],
      category: 'sessions'
    }
  )

  // Action: List User Sessions
  registerAction(
    'list_user_sessions',
    async (params, ctx) => {
      const { user_id } = params
      
      // Validate required parameters
      if (!user_id) {
        log.error('list_user_sessions - Missing required parameter: user_id')
        throw new Error('user_id is required')
      }
      
      log.debug('list_user_sessions - Fetching sessions for user:', { user_id })
      
      try {
        const response = await apiService.fetch(`/api/sessions/user/${encodeURIComponent(user_id)}`)
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Group by active status
        const activeSessions = data.filter(s => s.active)
        const inactiveSessions = data.filter(s => !s.active)
        
        // Format the sessions list
        let formattedOutput = `📋 **Sessions for User ${user_id}**\n\n`
        formattedOutput += `**Total Sessions:** ${data.length}\n\n`
        
        if (data.length === 0) {
          formattedOutput += '*No sessions found*'
        } else {
          if (activeSessions.length > 0) {
            formattedOutput += `**✅ Active Sessions** (${activeSessions.length})\n`
            activeSessions.forEach(session => {
              formattedOutput += `  • **Session ${session.id.substring(0, 8)}...**\n`
              formattedOutput += `    Created: ${new Date(session.created_at).toLocaleString()}\n`
              formattedOutput += `    Expires: ${new Date(session.expires_at).toLocaleString()}\n`
              formattedOutput += `    Updated: ${new Date(session.updated_at).toLocaleString()}\n`
              
              // Check if expired
              const now = new Date()
              const expiresAt = new Date(session.expires_at)
              if (expiresAt < now) {
                formattedOutput += `    ⚠️ **EXPIRED** (but still marked active)\n`
              }
              
              formattedOutput += '\n'
            })
          }
          
          if (inactiveSessions.length > 0) {
            formattedOutput += `**❌ Inactive Sessions** (${inactiveSessions.length})\n`
            inactiveSessions.forEach(session => {
              formattedOutput += `  • **Session ${session.id.substring(0, 8)}...**\n`
              formattedOutput += `    Created: ${new Date(session.created_at).toLocaleString()}\n`
              formattedOutput += `    Closed: ${new Date(session.updated_at).toLocaleString()}\n`
              formattedOutput += '\n'
            })
          }
        }
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          // Sessions list can vary in size
          if (formattedOutput.length > 5000) {
            const filename = `user_sessions_${user_id}_${Date.now()}.txt`
            chatStore.addAttachment(filename, formattedOutput, 'text')
          } else {
            chatStore.insertContentIntoInput({ content: formattedOutput })
          }
        }
        
        log.info('list_user_sessions - Sessions listed successfully:', { 
          user_id, 
          total: data.length,
          active: activeSessions.length,
          inactive: inactiveSessions.length
        })
        return { success: true, data }
      } catch (error) {
        log.error('list_user_sessions - Error listing sessions:', error)
        throw error
      }
    },
    {
      description: 'List all sessions for a specific user',
      params: [
        { name: 'user_id', type: 'string', required: true, description: 'User UUID to list sessions for' }
      ],
      category: 'sessions'
    }
  )

  // Action: Close Session
  registerAction(
    'close_session',
    async (params, ctx) => {
      const { session_id } = params
      
      // Validate required parameters
      if (!session_id) {
        log.error('close_session - Missing required parameter: session_id')
        throw new Error('session_id is required')
      }
      
      log.debug('close_session - Closing session:', { session_id })
      
      try {
        const response = await apiService.fetch(`/api/sessions/${encodeURIComponent(session_id)}/close`, {
          method: 'POST'
        })
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Format the result
        let formattedOutput = `🔒 **Session Closed Successfully**\n\n`
        formattedOutput += `**Session ID:** ${data.sessionId}\n`
        formattedOutput += `**Status:** Inactive\n\n`
        formattedOutput += `✅ ${data.message}\n\n`
        formattedOutput += `*Note: This session can no longer be used for authentication.*`
        
        const chatStore = ctx.chatStore
        if (chatStore) {
          // Session close result is concise
          chatStore.insertContentIntoInput({ content: formattedOutput })
        }
        
        log.info('close_session - Session closed successfully:', { session_id: data.sessionId })
        return { success: true, data }
      } catch (error) {
        log.error('close_session - Error closing session:', error)
        throw error
      }
    },
    {
      description: 'Close/deactivate a specific session',
      params: [
        { name: 'session_id', type: 'string', required: true, description: 'Session UUID to close' }
      ],
      category: 'sessions'
    }
  )
}
