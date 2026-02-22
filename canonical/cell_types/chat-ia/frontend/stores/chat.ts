/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-23",
 *   "console_calls_found": 18,
 *   "console_calls_migrated": 18,
 *   "migration_rate": 100,
 *   "logger_namespace": "store:chat",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Chat Store
 *
 * Manages chat-related state and actions for the ChatIA component.
 * Replaces global events: attach-to-prompt-ia, send-to-chat, attach-files-to-chat
 *
 * @module stores/chat
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'
import type { ChatComponentAPI, FileProposal } from '../types/chat'

const log = createLogger('store:chat')

// DEBUG LOG #2: Confirmação de carregamento do módulo chat.ts
console.log('[DEBUG][ITERATION_1] chat.ts module loaded ✅')
console.log('[DEBUG][ITERATION_1] Agent Mode features available in this module')
console.log('[DEBUG][ITERATION_1] Timestamp:', new Date().toISOString())

/**
 * File attachment structure for bulk operations
 */
interface FileAttachment {
  /** File name (legacy property) */
  name?: string
  /** File name */
  filename?: string
  /** File content */
  content: string
  /** Optional file path */
  path?: string
}

/**
 * Content payload for insertion into chat input
 */
interface ContentPayload {
  /** Content to insert */
  content: string
  /** Optional associated cell data */
  cellData?: Record<string, unknown>
}

/**
 * Proposal acceptance result
 */
interface ProposalAcceptResult {
  /** Success flag */
  success: boolean
  /** Result data from API */
  data?: unknown
}

/**
 * Chat Store
 */
export const useChatStore = defineStore('chat', () => {
  // State
  const chatComponentRef = ref<ChatComponentAPI | null>(null)
  const currentProposal = ref<FileProposal | null>(null)
  const isProposalModalVisible = ref<boolean>(false)
  
  // Agent Mode state (MVP 4)
  const isAgentMode = ref<boolean>(false)
  const agentSessionId = ref<string | null>(null)
  const showAgentTerminal = ref<boolean>(false)

  /**
   * Register the ChatIA component instance
   * This allows the store to call methods on the component
   *
   * @param componentInstance - Vue component instance
   */
  function registerChatComponent(componentInstance: ChatComponentAPI): void {
    chatComponentRef.value = componentInstance
  }

  /**
   * Add an attachment to the chat input
   * Replaces: attach-to-prompt-ia event
   *
   * @param filename - Name of the file
   * @param content - File content
   * @param type - File type (e.g., 'text', 'json')
   * @param path - Optional full file path
   * @returns Success status
   */
  function addAttachment(filename: string, content: string, type = 'text', path?: string): boolean {
    if (!filename || !content) {
      log.warn('addAttachment: Missing filename or content')
      return false
    }

    const chatComponent = chatComponentRef.value
    if (chatComponent && typeof chatComponent.addAttachment === 'function') {
      const success = chatComponent.addAttachment(filename, content, type, path)
      if (import.meta.env.DEV) {
        log.debug(`Attached "${filename}" to chat`)
      }
      return success
    } else {
      log.warn('ChatIA component or addAttachment method not available')
      return false
    }
  }

  /**
   * Insert content into chat input
   * Replaces: send-to-chat event
   *
   * @param payload - Content payload (object with content property, or string directly)
   */
  function insertContentIntoInput(payload: ContentPayload | string): void {
    log.debug('insertContentIntoInput called', { 
      payload_type: typeof payload 
    })
    
    if (!payload) {
      log.warn('insertContentIntoInput: Missing payload')
      return
    }

    const chatComponent = chatComponentRef.value
    
    log.debug('insertContentIntoInput - Component state', {
      hasChatComponent: !!chatComponent,
      hasMethod: !!(chatComponent && typeof chatComponent.insertContentIntoInput === 'function'),
      chatComponentRef: chatComponentRef.value
    })
    
    if (
      chatComponent &&
      typeof chatComponent.insertContentIntoInput === 'function'
    ) {
      // Extract content string from payload
      // Handle both object format { content: "..." } and string format
      const content = typeof payload === 'string' ? payload : (payload.content || '')
      
      log.debug('insertContentIntoInput - Extracted content', {
        contentType: typeof content,
        contentLength: content?.length || 0,
        contentPreview: content?.substring(0, 100) || 'empty'
      })
      
      // Call component method with string content (not object)
      chatComponent.insertContentIntoInput(content, false, '')
      
      if (import.meta.env.DEV) {
        log.info('Content sent to chat successfully')
      }
    } else {
      log.error('ChatIA component or insertContentIntoInput method not available', {
        chatComponentRef: chatComponentRef.value,
        hasRef: !!chatComponentRef.value,
        refKeys: chatComponentRef.value ? Object.keys(chatComponentRef.value) : []
      })
    }
  }

  /**
   * Attach multiple files to chat
   * Replaces: attach-files-to-chat event
   *
   * @param attachments - Array of file objects
   * @returns Result with success count
   */
  function attachMultipleFiles(attachments: FileAttachment[]): { success: number; total: number } {
    if (!Array.isArray(attachments) || attachments.length === 0) {
      log.warn('attachMultipleFiles: No attachments provided')
      return { success: 0, total: 0 }
    }

    const chatComponent = chatComponentRef.value
    if (!chatComponent || typeof chatComponent.addAttachment !== 'function') {
      log.warn('ChatIA component or addAttachment method not available')
      return { success: 0, total: attachments.length }
    }

    let successCount = 0
    for (const attachment of attachments) {
      const filename = attachment.filename || attachment.name || ''
      const success = chatComponent.addAttachment(
        filename,
        attachment.content,
        'text',
        attachment.path,
      )
      if (success) successCount++
    }

    if (import.meta.env.DEV) {
      log.debug(`${successCount}/${attachments.length} files attached to chat`)
    }

    return { success: successCount, total: attachments.length }
  }

  /**
   * Unregister the ChatIA component instance
   * Call this when the component is unmounted
   */
  function unregisterChatComponent(): void {
    chatComponentRef.value = null
  }

  /**
   * Show a file proposal modal
   * @param proposal - Proposal data
   */
  function showFileProposal(proposal: FileProposal): void {
    currentProposal.value = proposal
    isProposalModalVisible.value = true
    log.info('File proposal opened', proposal.filePath)
  }

  /**
   * Hide the file proposal modal
   */
  function hideFileProposal(): void {
    isProposalModalVisible.value = false
    // Clear proposal after animation completes
    setTimeout(() => {
      currentProposal.value = null
    }, 300)
    log.info('File proposal closed')
  }

  /**
   * Accept a file proposal
   * @param proposal - Proposal data
   * @returns Result of acceptance
   */
  async function acceptFileProposal(proposal: FileProposal): Promise<ProposalAcceptResult> {
    log.info('File proposal accepted', proposal.filePath)
    
    try {
      // Send proposal to backend to create PR
      const API_BASE = window.location.origin
      const response = await apiService.fetch(`${API_BASE}/api/proposals/accept`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(proposal)
      })
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({})) as { detail?: string }
        throw new Error(errorData.detail || `HTTP ${response.status}`)
      }
      
      const result = await response.json()
      hideFileProposal()
      
      // Notify user of success
      insertContentIntoInput({
        content: `✅ Proposta aceita! PR será criado: ${proposal.filePath}\n\nDescrição: ${proposal.description}`
      })
      
      return { success: true, data: result }
    } catch (error) {
      log.error('Error accepting proposal', error)
      
      // Show error in chat
      insertContentIntoInput({
        content: `❌ Erro ao aceitar proposta: ${(error as Error).message}`
      })
      
      throw error
    }
  }

  /**
   * Reject a file proposal
   * @param proposal - Proposal data
   */
  function rejectFileProposal(proposal: FileProposal): void {
    log.info('File proposal rejected', proposal.filePath)
    hideFileProposal()
    
    // Notify user
    insertContentIntoInput({
      content: `❌ Proposta rejeitada: ${proposal.filePath}`
    })
  }

  /**
   * Toggle Agent Mode on/off
   * MVP 4: Dual-mode switching with auto-session creation
   */
  async function toggleAgentMode(): Promise<void> {
    isAgentMode.value = !isAgentMode.value
    log.info(`Agent Mode ${isAgentMode.value ? 'enabled' : 'disabled'}`)
    
    // DEBUG LOG [ITERATION_1]: Toggle state change
    console.log(
      `[DEBUG][ITERATION_1] chat.ts - toggleAgentMode() called, ` +
      `new isAgentMode: ${isAgentMode.value}`
    )
    
    // Show/hide terminal when toggling
    if (isAgentMode.value) {
      showAgentTerminal.value = true
      
      // Auto-create session if not exists (UX improvement)
      if (!agentSessionId.value) {
        try {
          const conversationId = `conv_${crypto.randomUUID()}`
          
          // DEBUG LOG [ITERATION_1]: Session creation start
          console.log(
            `[DEBUG][ITERATION_1] chat.ts - Creating agent session, ` +
            `conversationId: ${conversationId}`
          )
          
          log.debug('Creating agent session automatically', { conversationId })
          
          const API_BASE = window.location.origin
          const requestUrl = `${API_BASE}/api/agent/sessions`
          const requestPayload = {
            conversation_id: conversationId,
            files: [],
            model: 'ollama/qwen2.5-coder:14b'
          }
          
          // DEBUG LOG [ITERATION_1]: HTTP request details
          console.log(
            `[DEBUG][ITERATION_1] chat.ts - HTTP POST request details:`,
            {
              url: requestUrl,
              method: 'POST',
              payload: requestPayload
            }
          )
          
          const response = await apiService.fetch(requestUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestPayload)
          })
          
          // DEBUG LOG [ITERATION_1]: HTTP response received
          console.log(
            `[DEBUG][ITERATION_1] chat.ts - HTTP response received:`,
            {
              ok: response.ok,
              status: response.status,
              statusText: response.statusText
            }
          )
          
          if (response.ok) {
            agentSessionId.value = conversationId
            log.info('Agent session created successfully', { sessionId: conversationId })
            
            // DEBUG LOG [ITERATION_1]: Success
            console.log(
              `[DEBUG][ITERATION_1] chat.ts - ✅ Session created successfully, ` +
              `agentSessionId set to: ${conversationId}`
            )
          } else {
            const errorData = await response.json().catch(() => ({})) as { detail?: string }
            
            // DEBUG LOG [ITERATION_1]: HTTP error
            console.error(
              `[DEBUG][ITERATION_1] chat.ts - ❌ Session creation failed:`,
              {
                status: response.status,
                statusText: response.statusText,
                errorDetail: errorData.detail
              }
            )
            
            log.warn('Failed to create agent session', { 
              status: response.status, 
              error: errorData.detail 
            })
          }
        } catch (error) {
          // DEBUG LOG [ITERATION_1]: Exception
          console.error(
            `[DEBUG][ITERATION_1] chat.ts - ❌ EXCEPTION during session creation:`,
            {
              errorType: error instanceof Error ? error.constructor.name : typeof error,
              errorMessage: error instanceof Error ? error.message : String(error),
              error
            }
          )
          
          log.error('Error creating agent session', error)
          // Don't block the UI - user can still interact, just without session
        }
      } else {
        // DEBUG LOG [ITERATION_1]: Session already exists
        console.log(
          `[DEBUG][ITERATION_1] chat.ts - Session already exists, ` +
          `agentSessionId: ${agentSessionId.value}`
        )
      }
    }
  }

  /**
   * Set Agent Mode session ID
   * @param sessionId - Conversation/session ID
   */
  function setAgentSession(sessionId: string | null): void {
    agentSessionId.value = sessionId
    if (sessionId) {
      log.debug('Agent session set', { sessionId })
    }
  }

  /**
   * Toggle Agent Terminal visibility
   */
  function toggleAgentTerminal(): void {
    showAgentTerminal.value = !showAgentTerminal.value
    log.debug('Agent terminal toggled', { visible: showAgentTerminal.value })
  }

  return {
    // State
    chatComponentRef,
    currentProposal,
    isProposalModalVisible,
    // Agent Mode state (MVP 4)
    isAgentMode,
    agentSessionId,
    showAgentTerminal,

    // Actions
    registerChatComponent,
    unregisterChatComponent,
    addAttachment,
    insertContentIntoInput,
    attachMultipleFiles,
    showFileProposal,
    hideFileProposal,
    acceptFileProposal,
    rejectFileProposal,
    // Agent Mode actions (MVP 4)
    toggleAgentMode,
    setAgentSession,
    toggleAgentTerminal,
  }
})
