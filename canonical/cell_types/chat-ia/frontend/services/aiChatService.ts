/**
 * AI Chat Service
 * Handles API communication for chat functionality
 */

import { ENDPOINTS } from '@/config/endpoints.js'
import apiService from '@/services/apiService.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('services:chat')

interface ChatMessage {
  role: string
  content: string
}

interface ChatAttachment {
  filename?: string
  name?: string
  content: string
  type: string
}

interface ProcessMessageParams {
  intention: string
  assignee_id: string
  history: Array<{ role: string; content: string }>
  model: string
  classifyIntention?: boolean
  attachments?: ChatAttachment[]
  thread_id?: string | null
  assistant_id?: string | null
  selected_collections?: string[] | null
  conversation_id?: string | null
}

interface AIModel {
  value: string
  label: string
  type: string
  provider: string
  name: string
}

/**
 * Prepare conversation history for backend API
 * Converts full message objects to simple role/content format
 * @param messages - Array of message objects
 * @param excludeLast - Number of messages to exclude from the end
 * @returns Formatted history for API
 */
export function prepareConversationHistory(messages: ChatMessage[], excludeLast = 0): Array<{ role: string; content: string }> {
  const messagesToInclude =
    excludeLast > 0 ? messages.slice(0, -excludeLast) : messages

  return messagesToInclude.map((msg) => ({
    role: msg.role,
    content: msg.content,
  }))
}

/**
 * Prepare attachments for API
 * Converts attachment objects to API format
 * @param attachments - Array of attachment objects
 * @returns Formatted attachments for API
 */
export function prepareAttachmentsForAPI(attachments: ChatAttachment[]): Array<{ name: string; content: string; type: string }> {
  return attachments.map((att) => ({
    name: att.filename || att.name || '',
    content: att.content,
    type: att.type,
  }))
}

/**
 * Process chat message with AI
 * @param params - Message processing parameters
 * @returns API response with AI message
 */
export async function processMessage({
  intention,
  assignee_id,
  history,
  model,
  classifyIntention = false,
  attachments = [],
  thread_id = null,
  assistant_id = null,
  selected_collections = null,
  conversation_id = null,
}: ProcessMessageParams): Promise<any> {
  const payload: any = {
    purpose: intention,
    assignee_id,
    history,
    model,
    classify_intent: classifyIntention,
    attachments: attachments.length > 0 ? attachments : undefined,
    use_rag: true, // Enable RAG (Retrieval-Augmented Generation)
  }

  // Include optional OpenAI Assistants API fields only if provided
  if (thread_id) {
    payload.thread_id = thread_id
  }
  if (assistant_id) {
    payload.assistant_id = assistant_id
  }

  // Include selected RAG collections if provided (empty array = all collections)
  if (selected_collections && selected_collections.length > 0) {
    payload.selected_collections = selected_collections
  }

  // Include conversation_id for session tracking (critical for InterpreterProvider)
  if (conversation_id) {
    payload.conversation_id = conversation_id
  }
  
  log.debug('[CONV_ID] aiChatService.processMessage - Final payload', {
    has_conversation_id: 'conversation_id' in payload,
    conversation_id_value: payload.conversation_id || 'undefined',
    payload_keys: Object.keys(payload),
    payload_size: JSON.stringify(payload).length
  })

  const response = await apiService.fetch(ENDPOINTS.chatProcess, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    throw new Error(`Erro na API: ${response.status}`)
  }

  return await response.json()
}

/**
 * Fetch available AI models
 * @returns List of available models
 */
export async function fetchAvailableModels(): Promise<AIModel[]> {
  const response = await apiService.fetch(ENDPOINTS.aiModelsList)

  if (!response.ok) {
    throw new Error('Failed to fetch available models')
  }

  const models = await response.json()

  // Transform models to dropdown format
  return models.map((model: any) => {
    // Determine icon based on type
    let icon = '🤖'
    if (model.type === 'local') {
      icon = '🏠'
    } else if (model.type === 'cloud' || model.type === 'byok') {
      icon = '☁️'
    }

    return {
      value: model.modelId,
      label: `${icon} ${model.name}`,
      type: model.type,
      provider: model.provider,
      name: model.name,
    }
  })
}

export default {
  prepareConversationHistory,
  prepareAttachmentsForAPI,
  processMessage,
  fetchAvailableModels,
}
