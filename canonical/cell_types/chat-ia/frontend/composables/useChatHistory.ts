/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-31",
 *   "console_calls_found": 11,
 *   "console_calls_migrated": 11,
 *   "migration_rate": 100,
 *   "logger_namespace": "chat:history",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Composable for managing chat history persistence and navigation
 * Handles localStorage-based conversation history with metadata
 * 
 * ⚠️ REFACTORED: Global History Bank + Per-Cell Instances (Issue - Refatorar Chat Composables)
 * 
 * Architecture:
 * - Ephemeral: Cells (destroyed on reload/close)
 * - Persistent: conversationId (saved in initial_data)
 * - Eternal: Global history bank (localStorage)
 * 
 * Pattern: Global localStorage-backed conversation history with per-cell isolated instances
 * Each cell instance accesses the global history bank but filters by its own conversationId
 */

import { ref, computed, watch, type Ref, type ComputedRef } from 'vue'
import type { ChatConversation, ChatMessage, ChatHistoryProps, UseChatHistoryReturn } from '../types/chat'
import { createLogger } from '@/utils/logger'

const log = createLogger('chat:history')

const STORAGE_KEY = 'scareverse_global_chat_history'
const MAX_CONVERSATIONS = 50 // Limit to prevent localStorage overflow
const MAX_MESSAGES_PER_CONVERSATION = 100
const MIN_CONVERSATIONS_TO_KEEP = 5 // Always keep at least this many conversations

/**
 * Migrate conversation data from Portuguese to English field names
 * Handles legacy data created before the refactoring to English technical terms
 * @param conversation - Conversation object (potentially with Portuguese fields)
 * @returns Conversation with English field names
 */
function migrateConversationFields(conversation: any): ChatConversation {
  const migrated: any = { ...conversation }
  
  // Migrate field names from Portuguese to English
  if ('titulo' in migrated && !('title' in migrated)) {
    migrated.title = migrated.titulo
    delete migrated.titulo
  }
  
  if ('mensagens' in migrated && !('messages' in migrated)) {
    migrated.messages = migrated.mensagens
    delete migrated.mensagens
  }
  
  if ('criadoEm' in migrated && !('createdAt' in migrated)) {
    migrated.createdAt = migrated.criadoEm
    delete migrated.criadoEm
  }
  
  if ('atualizadoEm' in migrated && !('updatedAt' in migrated)) {
    migrated.updatedAt = migrated.atualizadoEm
    delete migrated.atualizadoEm
  }
  
  // Ensure required fields exist with defaults
  if (!migrated.title) {
    migrated.title = 'Nova Conversa'
  }
  
  if (!migrated.messages) {
    migrated.messages = []
  }
  
  if (!migrated.createdAt) {
    migrated.createdAt = new Date().toISOString()
  }
  
  if (!migrated.updatedAt) {
    migrated.updatedAt = new Date().toISOString()
  }
  
  // Migrate message fields if needed
  if (Array.isArray(migrated.messages)) {
    migrated.messages = migrated.messages.map((msg: any) => {
      const migratedMsg = { ...msg }
      
      // Migrate 'conteudo' to 'content'
      if ('conteudo' in migratedMsg && !('content' in migratedMsg)) {
        migratedMsg.content = migratedMsg.conteudo
        delete migratedMsg.conteudo
      }
      
      return migratedMsg
    })
  }
  
  return migrated as ChatConversation
}

/**
 * Load all chat history from global localStorage
 * Automatically migrates legacy Portuguese field names to English
 */
function loadAllHistoryFromGlobal(): ChatConversation[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) return []
    
    const parsed = JSON.parse(stored)
    if (!Array.isArray(parsed)) return []
    
    // Migrate all conversations to English field names
    const migrated = parsed.map(migrateConversationFields)
    
    // Save migrated data back to localStorage if any Portuguese fields were found
    // Check by comparing first conversation's field presence (optimization)
    const needsMigration = parsed.length > 0 && (
      'titulo' in parsed[0] || 
      'mensagens' in parsed[0] || 
      'criadoEm' in parsed[0] || 
      'atualizadoEm' in parsed[0]
    )
    
    if (needsMigration) {
      log.info('Chat history migrated from Portuguese to English field names')
      localStorage.setItem(STORAGE_KEY, JSON.stringify(migrated))
    }
    
    return migrated
  } catch (error) {
    log.error('Error loading chat history', error)
    return []
  }
}

/**
 * Save all chat history to global localStorage with quota management
 * Automatically reduces history size if quota is exceeded
 */
function saveAllHistoryToGlobal(history: ChatConversation[]): void {
  try {
    // Keep only the most recent conversations
    const workingHistory = history.slice(0, MAX_CONVERSATIONS)
    
    // Try to save
    localStorage.setItem(STORAGE_KEY, JSON.stringify(workingHistory))
  } catch (error) {
    if ((error as Error).name === 'QuotaExceededError') {
      log.warn('Storage quota exceeded. Attempting to reduce history size...')
      
      // Progressive reduction attempts
      const reductionLevels = [0.2, 0.4, 0.6, 0.8]
      
      for (const reduction of reductionLevels) {
        try {
          const reduced = reduceHistorySize(history, reduction)
          localStorage.setItem(STORAGE_KEY, JSON.stringify(reduced))
          
          log.info(`Successfully saved history after ${Math.round(reduction * 100)}% reduction`)
          
          // Update the original array to reflect the reduction
          history.splice(0, history.length, ...reduced)
          return
        } catch (retryError) {
          if ((retryError as Error).name !== 'QuotaExceededError') {
            log.error('Error during retry', retryError)
            break
          }
          // Continue to next reduction level
        }
      }
      
      // If all attempts fail, keep only the current conversation
      log.warn('Unable to save full history. Keeping only most recent conversation.')
      try {
        const minimal = history.slice(0, 1)
        localStorage.setItem(STORAGE_KEY, JSON.stringify(minimal))
        history.splice(0, history.length, ...minimal)
      } catch (finalError) {
        log.error('Critical: Unable to save any chat history', finalError)
        // Clear storage as last resort
        try {
          localStorage.removeItem(STORAGE_KEY)
        } catch (clearError) {
          log.error('Unable to clear storage', clearError)
        }
      }
    } else {
      log.error('Error saving chat history', error)
    }
  }
}

/**
 * Progressively reduce history size by removing old conversations and messages
 * Note: history array is ordered with newest conversations first (index 0)
 * @param history - Conversation history array (newest first)
 * @param targetReduction - Approximate percentage to reduce (0.1 = 10%)
 * @returns Reduced history
 */
function reduceHistorySize(history: ChatConversation[], targetReduction = 0.3): ChatConversation[] {
  if (history.length === 0) return history
  
  let reduced = [...history]
  
  // Step 1: Remove oldest conversations (keep at least MIN_CONVERSATIONS_TO_KEEP)
  // Conversations are ordered newest-first, so oldest are at the end
  if (reduced.length > MIN_CONVERSATIONS_TO_KEEP) {
    const conversationsToRemove = Math.max(
      1,
      Math.floor((reduced.length - MIN_CONVERSATIONS_TO_KEEP) * targetReduction)
    )
    // Slice from beginning keeps newest conversations
    reduced = reduced.slice(0, reduced.length - conversationsToRemove)
    log.debug(`Removed ${conversationsToRemove} old conversations to free up space`)
  }
  
  // Step 2: Trim messages from remaining conversations (oldest messages first)
  // Messages within each conversation are also ordered oldest-first, so we keep the most recent
  reduced = reduced.map((conv, index) => {
    if (conv.messages.length > MAX_MESSAGES_PER_CONVERSATION / 2) {
      const trimmedMessages = conv.messages.slice(
        -Math.floor(MAX_MESSAGES_PER_CONVERSATION / 2)
      )
      if (index === 0) {
        // Keep more messages in the most recent conversation (index 0)
        return {
          ...conv,
          messages: conv.messages.slice(-MAX_MESSAGES_PER_CONVERSATION)
        }
      }
      return {
        ...conv,
        messages: trimmedMessages
      }
    }
    return conv
  })
  
  return reduced
}

/**
 * Composable for chat history management with per-cell instances
 * @param props - Chat history props containing conversationId
 */
export function useChatHistory(props: ChatHistoryProps): UseChatHistoryReturn {
  const conversationId = props.conversationId
  
  // ✅ Load ALL conversations from global bank
  const allConversations = ref<ChatConversation[]>(loadAllHistoryFromGlobal())
  
  // ✅ Filter current conversation for this instance with null safety
  const currentConversation = computed<ChatConversation | null>(() => {
    const found = allConversations.value.find(c => c.id === conversationId)
    return found ?? null
  })

  // Auto-save persists to global bank whenever conversations change
  watch(
    allConversations,
    (newValue) => {
      saveAllHistoryToGlobal(newValue)
    },
    { deep: true }
  )

  /**
   * Create a new conversation
   */
  function createConversation(title = 'Nova Conversa'): ChatConversation {
    const conversation: ChatConversation = {
      id: crypto.randomUUID(),
      title,
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }

    allConversations.value.unshift(conversation)
    
    log.debug('[CONV_ID] createConversation', {
      conversationId: conversation.id,
      title: title,
      timestamp: conversation.createdAt,
      totalConversations: allConversations.value.length
    })

    return conversation
  }

  /**
   * Add message to the conversation identified by this instance's conversationId
   */
  function addMessage(message: ChatMessage): void {
    const conversation = allConversations.value.find(c => c.id === conversationId)
    if (!conversation) {
      log.error('[CONV_ID] addMessage - Conversation not found', {
        conversationId: conversationId
      })
      return
    }

    // Add timestamp if not present
    if (!message.timestamp) {
      message.timestamp = new Date().toISOString()
    }

    conversation.messages.push(message)
    conversation.updatedAt = new Date().toISOString()

    // Update conversation title based on first user message
    if (conversation.messages.length === 1 && message.role === 'user') {
      const preview = message.content.substring(0, 50)
      conversation.title = preview + (message.content.length > 50 ? '...' : '')
    }

    // Update model if provided
    if (message.model) {
      conversation.metadata = conversation.metadata || {}
      conversation.metadata.model = message.model
    }

    // Limit messages per conversation
    if (conversation.messages.length > MAX_MESSAGES_PER_CONVERSATION) {
      conversation.messages = conversation.messages.slice(
        -MAX_MESSAGES_PER_CONVERSATION
      )
    }
  }

  /**
   * Delete a conversation from the global bank
   */
  function deleteConversation(convId: string): void {
    const index = allConversations.value.findIndex(c => c.id === convId)
    if (index !== -1) {
      allConversations.value.splice(index, 1)
    }
  }

  /**
   * Get the most recent conversation ID from the global bank
   */
  function getMostRecentConversationId(): string | null {
    return allConversations.value.length > 0 ? allConversations.value[0].id : null
  }

  return {
    allConversations,
    currentConversation,
    createConversation,
    addMessage,
    deleteConversation,
    getMostRecentConversationId
  }
}
