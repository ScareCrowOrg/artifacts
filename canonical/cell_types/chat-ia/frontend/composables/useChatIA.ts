/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-22",
 *   "console_calls_found": 21,
 *   "console_calls_migrated": 21,
 *   "migration_rate": 100,
 *   "logger_namespace": "chat:ia",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Composable for Chat IA logic
 * Manages chat state, messages, models, attachments, and API interactions
 *
 * ⚠️ REFACTORED: Per-Cell Isolated Instances (Issue - Refatorar Chat Composables)
 * 
 * Architecture:
 * - Each cell instance gets its own isolated state (messages, userInput, selectedModel, etc.)
 * - Persistence is managed through chatHistory composable passed as prop
 * - conversationId identifies which conversation this instance belongs to
 *
 * OpenAI Assistants API Conversation Continuity:
 * - Maintains optional threadId and assistantId for OpenAI models
 * - These IDs are only returned by the backend when using OpenAI provider
 * - They enable conversation continuity across multiple messages
 * - IDs are reset when clearing chat or loading different conversations
 * - Non-OpenAI models (Ollama, Gemini) are not affected by these fields
 *
 * NotebookItem Context:
 * - Can accept optional activeCell reference for passing notebook context to AI
 */

import { ref, computed, type Ref, type ComputedRef } from 'vue'
import type { ChatMessage, ChatAttachment, AIModel, RAGCollection, UseChatHistoryReturn, UseChatIAProps } from '../types/chat'
import {
  PROMPT_MAX_CHARS,
  ATTACHMENT_MAX_SIZE,
  ATTACHMENTS_TOTAL_MAX_SIZE,
  MAX_ATTACHMENTS,
  PROMPT_WARNING_THRESHOLD,
  ATTACHMENT_WARNING_THRESHOLD,
  formatBytes,
  validateAttachmentSize,
  validateTotalAttachmentsSize,
  validatePromptLength,
} from '../config/chatLimits.js'
import { SessionExpiredError } from '@/services/apiService.js'
import authService from '@/services/authService.js'
import * as aiChatService from '../services/aiChatService.js'
import { getNotebookItemTypeId } from '../types/notebook.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('chat:ia')

/**
 * Notebook cell reference interface
 */
interface ICelula {
  id: string
  [key: string]: unknown
}

/**
 * AI response data structure
 */
interface AIResponseData {
  response?: string
  cell?: {
    content: string
    [key: string]: unknown
  } | null
  model?: string
  conversation_id?: string | null
  thread_id?: string
  assistant_id?: string
}

/**
 * API payload structure
 */
interface APIPayload {
  intention: string
  assignee_id: string
  history: unknown[]
  model: string
  classifyIntention: boolean
  attachments: unknown[]
  thread_id?: string | null
  assistant_id?: string | null
  notebook_item_id?: string
  notebook_item_type_id?: string
  selected_collections?: string[] | null
  conversation_id?: string | null
}

/**
 * Use Chat IA composable return type
 */
export interface UseChatIAReturn {
  // State
  messages: Ref<ChatMessage[]>
  userInput: Ref<string>
  isLoading: Ref<boolean>
  selectedModel: Ref<string>
  availableModels: Ref<AIModel[]>
  isLoadingModels: Ref<boolean>
  modelsError: Ref<string | null>
  enableIntentionClassification: Ref<boolean>
  attachments: Ref<ChatAttachment[]>
  threadId: Ref<string | null>
  assistantId: Ref<string | null>
  availableCollections: Ref<RAGCollection[]>
  selectedCollections: Ref<string[]>

  // Computed
  localModels: ComputedRef<AIModel[]>
  externalModels: ComputedRef<AIModel[]>
  promptCharCount: ComputedRef<number>
  promptLimitReached: ComputedRef<boolean>
  promptWarning: ComputedRef<boolean>
  totalAttachmentsSize: ComputedRef<number>
  attachmentsSizeExceeded: ComputedRef<boolean>
  attachmentsWarning: ComputedRef<boolean>
  canSend: ComputedRef<boolean>

  // Methods
  fetchModels: () => Promise<void>
  sendMessage: () => Promise<void>
  clearChat: () => void
  loadConversation: (conversationId: string) => void
  loadLastConversation: () => void
  addAttachment: (name: string, content: string, type?: string, path?: string) => boolean
  removeAttachment: (attachmentId: string) => void
  clearAttachments: () => void
  insertContentIntoInput: (content: string | { content: string }, asAttachment?: boolean, filename?: string) => void

  // Constants
  promptMaxChars: number
  attachmentMaxSize: number
  attachmentsTotalMaxSize: number
  maxAttachments: number
}

/**
 * Use Chat IA composable
 * @param props - Chat IA props containing conversationId, chatHistory, and callbacks
 */
export function useChatIA(props: UseChatIAProps): UseChatIAReturn {
  const conversationId = props.conversationId
  const chatHistory = props.chatHistory
  const emitCellCreated = props.emitCellCreated
  const scrollToBottom = props.scrollToBottom
  const activeCellRef = props.activeCellRef || null
  
  // ✅ State - ISOLATED per instance
  const messages = ref<ChatMessage[]>([])
  const userInput = ref<string>('')
  const isLoading = ref<boolean>(false)
  const selectedModel = ref<string>('mistral')
  const availableModels = ref<AIModel[]>([])
  const isLoadingModels = ref<boolean>(true)
  const modelsError = ref<string | null>(null)
  const enableIntentionClassification = ref<boolean>(false)
  const attachments = ref<ChatAttachment[]>([])

  // OpenAI Assistants API conversation continuity (optional fields)
  const threadId = ref<string | null>(null)
  const assistantId = ref<string | null>(null)

  // RAG Collection Selection
  const availableCollections = ref<RAGCollection[]>([
    { value: 'scareverse_docs', label: 'Documentação', icon: '📚' },
    { value: 'scareverse_code', label: 'Código', icon: '💻' },
    { value: 'scareverse_config', label: 'Configuração', icon: '⚙️' },
  ])
  // Default to all collections selected (user can deselect to narrow or disable RAG)
  const selectedCollections = ref<string[]>([
    'scareverse_docs',
    'scareverse_code',
    'scareverse_config',
  ])

  // Computed properties
  const localModels = computed<AIModel[]>(() =>
    availableModels.value.filter((m) => m.type === 'local'),
  )

  const externalModels = computed<AIModel[]>(() =>
    availableModels.value.filter(
      (m) => m.type === 'cloud' || m.type === 'byok',
    ),
  )

  const promptCharCount = computed<number>(() => userInput.value.length)

  const promptLimitReached = computed<boolean>(
    () => promptCharCount.value > PROMPT_MAX_CHARS,
  )

  const promptWarning = computed<boolean>(
    () => promptCharCount.value >= PROMPT_MAX_CHARS * PROMPT_WARNING_THRESHOLD,
  )

  const totalAttachmentsSize = computed<number>(() =>
    attachments.value.reduce((sum, att) => sum + att.size, 0),
  )

  const attachmentsSizeExceeded = computed<boolean>(
    () => totalAttachmentsSize.value > ATTACHMENTS_TOTAL_MAX_SIZE,
  )

  const attachmentsWarning = computed<boolean>(
    () =>
      totalAttachmentsSize.value >=
      ATTACHMENTS_TOTAL_MAX_SIZE * ATTACHMENT_WARNING_THRESHOLD,
  )

  const canSend = computed<boolean>(
    () =>
      !isLoading.value &&
      (!!userInput.value.trim() || attachments.value.length > 0) &&
      !promptLimitReached.value &&
      !attachmentsSizeExceeded.value,
  )

  // Methods
  async function fetchModels(): Promise<void> {
    isLoadingModels.value = true
    modelsError.value = null

    try {
      availableModels.value = await aiChatService.fetchAvailableModels()

      // Set default model if not already set or if current selection is invalid
      if (availableModels.value.length > 0) {
        const currentModelValid = availableModels.value.some(
          (m) => m.value === selectedModel.value,
        )
        if (!currentModelValid) {
          selectedModel.value = availableModels.value[0].value
        }
      }

      log.info('Modelos IA carregados', { count: availableModels.value.length })
    } catch (error) {
      log.error('Erro ao buscar modelos IA', error)
      modelsError.value = 'Não foi possível carregar os modelos disponíveis'

      // Fallback to default models if API fails
      availableModels.value = [
        {
          value: 'mistral',
          label: '🏠 Mistral (Ollama)',
          type: 'local',
          provider: 'ollama',
        },
        {
          value: 'deepseek-coder',
          label: '🏠 DeepSeek (Ollama)',
          type: 'local',
          provider: 'ollama',
        },
        {
          value: 'phi',
          label: '🏠 Phi (Ollama)',
          type: 'local',
          provider: 'ollama',
        },
        {
          value: 'gemini-pro',
          label: '☁️ Gemini (Google)',
          type: 'cloud',
          provider: 'gemini',
        },
      ]
    } finally {
      isLoadingModels.value = false
    }
  }

  async function sendMessage(): Promise<void> {
    // Validate before sending
    if (!canSend.value) return
    
    log.debug('[CONV_ID] sendMessage - ENTRY', {
      conversationId: conversationId,
      messagesCount: messages.value.length,
      hasHistory: messages.value.length > 0
    })

    // Validate prompt length
    const promptValidation = validatePromptLength(userInput.value)
    if (!promptValidation.valid) {
      alert(promptValidation.message)
      return
    }

    // Validate attachments total size
    const attachmentsValidation = validateTotalAttachmentsSize(
      attachments.value,
    )
    if (!attachmentsValidation.valid) {
      alert(attachmentsValidation.message)
      return
    }

    // Prepare message content
    let displayContent = userInput.value
    if (attachments.value.length > 0) {
      displayContent += '\n\n📎 Anexos:\n'
      attachments.value.forEach((att) => {
        displayContent += `- ${att.filename} (${formatBytes(att.size)})\n`
      })
    }

    const userMessage: ChatMessage = {
      role: 'user',
      content: displayContent,
      timestamp: new Date().toISOString(),
      attachments: [...attachments.value],
    }

    messages.value.push(userMessage)
    chatHistory.addMessage(userMessage)  // ✅ Persists to global bank
    
    log.debug('[CONV_ID] sendMessage - After addMessage', {
      conversationId: conversationId,
      newMessagesCount: messages.value.length
    })

    const intention = userInput.value
    const attachmentsData = [...attachments.value]
    userInput.value = ''
    attachments.value = []
    isLoading.value = true

    scrollToBottom()

    try {
      // Prepare data for API
      const history = aiChatService.prepareConversationHistory(
        messages.value,
        1,
      )
      const attachmentsApi = aiChatService.prepareAttachmentsForAPI(attachmentsData)

      // Prepare payload with optional OpenAI Assistants API fields
      const payload: APIPayload = {
        intention,
        assignee_id: getUserId(),
        history,
        model: selectedModel.value,
        classifyIntention: enableIntentionClassification.value,
        attachments: attachmentsApi,
      }

      // Include thread_id and assistant_id only if they exist (OpenAI continuity)
      if (threadId.value) {
        payload.thread_id = threadId.value
      }
      if (assistantId.value) {
        payload.assistant_id = assistantId.value
      }

      // Include notebook_item context if active cell is available (for NotebookItem awareness)
      if (activeCellRef && activeCellRef.value) {
        payload.notebook_item_id = activeCellRef.value.id
        const typeId = getNotebookItemTypeId(activeCellRef.value)
        if (typeId) {
          payload.notebook_item_type_id = typeId
        }
      }

      // Include selected RAG collections if any are selected
      if (selectedCollections.value && selectedCollections.value.length > 0) {
        payload.selected_collections = selectedCollections.value
      }

      // Include conversation_id for session tracking (critical for InterpreterProvider)
      log.debug('[CONV_ID] sendMessage - Including conversationId in payload', {
        conversationId: conversationId,
        conversationIdType: typeof conversationId
      })
      
      payload.conversation_id = conversationId
      log.debug('[CONV_ID] sendMessage - Added conversation_id to payload', {
        conversation_id: conversationId
      })

      // Call backend
      const data = await aiChatService.processMessage(payload as any) as AIResponseData

      // Add AI response
      const aiMessage: ChatMessage = {
        role: 'assistant',
        content: data.response || 'Intention processed successfully!',
        timestamp: new Date().toISOString(),
        model: data.model || selectedModel.value,
        conversationId: data.conversation_id || undefined,
      }

      messages.value.push(aiMessage)
      chatHistory.addMessage(aiMessage)

      // Store OpenAI Assistants API IDs for conversation continuity (if present)
      // These will only be returned by backend when using OpenAI models
      if (data.thread_id) {
        threadId.value = data.thread_id
        log.debug('OpenAI thread_id stored for conversation continuity', { threadId: threadId.value })
      }
      if (data.assistant_id) {
        assistantId.value = data.assistant_id
        log.debug('OpenAI assistant_id stored for conversation continuity', { assistantId: assistantId.value })
      }

      // Emit cell creation event if applicable
      if (data.cell && data.cell.content) {
        emitCellCreated(data.cell.content)
      }
    } catch (error) {
      log.error('Erro ao processar mensagem', error)

      // Don't show error message if session expired
      if (!(error instanceof SessionExpiredError)) {
        const errorMessage: ChatMessage = {
          role: 'assistant',
          content: `❌ Erro ao processar sua intenção: ${(error as Error).message}. Por favor, tente novamente.`,
          timestamp: new Date().toISOString(),
        }
        messages.value.push(errorMessage)
        chatHistory.addMessage(errorMessage)
      }
    } finally {
      isLoading.value = false
      scrollToBottom()
    }
  }

  function clearChat(): void {
    messages.value = []
    // Reset OpenAI Assistants API IDs to start a new conversation thread
    threadId.value = null
    assistantId.value = null
    // Note: We don't create a new conversation here
    // The conversation is identified by conversationId which is managed by the cell
    log.info('Chat messages cleared, OpenAI thread/assistant IDs reset')
  }

  function loadConversation(convId: string): void {
    // This function is kept for backward compatibility
    // In the new architecture, the cell manages which conversationId to use
    // We just load the messages from the global bank
    const conversation = chatHistory.allConversations.value.find(c => c.id === convId)
    if (conversation) {
      messages.value = conversation.messages.map((msg: ChatMessage) => ({
        ...msg,
        timestamp: msg.timestamp || new Date().toISOString(),
      }))
    } else {
      messages.value = []
    }
    // Reset OpenAI thread/assistant IDs when switching conversations
    // Each conversation should have its own independent thread
    threadId.value = null
    assistantId.value = null
    scrollToBottom()
  }

  function loadLastConversation(): void {
    const mostRecentId = chatHistory.getMostRecentConversationId()
    if (mostRecentId) {
      loadConversation(mostRecentId)
    }
  }

  function addAttachment(name: string, content: string, type = 'text', path?: string): boolean {
    log.debug('addAttachment: chamado', { name, contentLength: content.length, type, path })
    // Validate max attachments count
    if (attachments.value.length >= MAX_ATTACHMENTS) {
      log.warn('addAttachment: máximo de anexos atingido', { count: attachments.value.length })
      alert(`Máximo de ${MAX_ATTACHMENTS} anexos permitidos`)
      return false
    }
    // Calculate size
    const size = new TextEncoder().encode(content).length
    log.debug('addAttachment: tamanho calculado', { size })
    // Validate individual attachment size
    const sizeValidation = validateAttachmentSize(size)
    if (!sizeValidation.valid) {
      log.warn('addAttachment: tamanho individual inválido', sizeValidation)
      alert(sizeValidation.message)
      return false
    }
    // Validate total size after adding
    const futureAttachments = [...attachments.value, { 
      size, 
      filename: name, 
      content, 
      type,
      ...(path && { path })
    }]
    const totalValidation = validateTotalAttachmentsSize(futureAttachments)
    if (!totalValidation.valid) {
      log.warn('addAttachment: tamanho total inválido', totalValidation)
      alert(totalValidation.message)
      return false
    }
    // Add attachment
    const attachment: ChatAttachment = {
      filename: name,
      content,
      size,
      type,
      ...(path && { path }),
    }
    log.debug('addAttachment: anexo criado', { filename: attachment.filename, size: attachment.size })
    attachments.value.push(attachment)
    log.debug('addAttachment: anexo adicionado ao array', { count: attachments.value.length })
    return true
  }

  function removeAttachment(attachmentId: string): void {
    attachments.value = attachments.value.filter(
      (att) => att.filename !== attachmentId,
    )
    log.debug('Anexo removido', { attachmentId })
  }

  function clearAttachments(): void {
    attachments.value = []
    log.debug('Todos os anexos removidos')
  }

  function insertContentIntoInput(
    content: string | { content: string },
    asAttachment = false,
    filename = '',
  ): void {
    log.debug('insertContentIntoInput called', {
      contentType: typeof content,
      contentLength: typeof content === 'string' ? content.length : 'N/A',
      asAttachment,
      filename,
      currentInputLength: userInput.value.length
    })
    
    // Ensure content is always a string
    const actualContent = typeof content === 'string' ? content : (content?.content || '')
    
    log.debug('insertContentIntoInput - Normalized content', {
      actualContentType: typeof actualContent,
      actualContentLength: actualContent.length,
      actualContentPreview: actualContent.substring(0, 100)
    })
    
    if (asAttachment) {
      const name = filename || `Conteúdo ${attachments.value.length + 1}`
      addAttachment(name, actualContent, 'text')
    } else {
      // CONCATENATE to existing input, don't replace
      const currentContent = userInput.value
      const separator = currentContent && currentContent.trim() ? '\n\n' : ''
      userInput.value = currentContent + separator + actualContent
      
      log.debug('insertContentIntoInput - userInput updated', {
        userInputType: typeof userInput.value,
        userInputLength: userInput.value.length,
        wasConcatenated: !!currentContent,
        previousLength: currentContent.length,
        addedLength: actualContent.length
      })
    }
  }

  function getUserId(): string {
    const user = authService.getUser()
    if (user && user.id) {
      log.debug('Using authenticated user ID', { userId: user.id })
      return user.id
    }

    // Fallback
    log.warn('No authenticated user found, using fallback')
    let userId = localStorage.getItem('scareverse_user_id')
    if (!userId) {
      userId = 'seed-user-001'
      localStorage.setItem('scareverse_user_id', userId)
      log.warn('Using seed user ID', { userId })
    }
    return userId
  }

  return {
    // State
    messages,
    userInput,
    isLoading,
    selectedModel,
    availableModels,
    isLoadingModels,
    modelsError,
    enableIntentionClassification,
    attachments,
    threadId,
    assistantId,
    availableCollections,
    selectedCollections,

    // Computed
    localModels,
    externalModels,
    promptCharCount,
    promptLimitReached,
    promptWarning,
    totalAttachmentsSize,
    attachmentsSizeExceeded,
    attachmentsWarning,
    canSend,

    // Methods
    fetchModels,
    sendMessage,
    clearChat,
    loadConversation,
    loadLastConversation,
    addAttachment,
    removeAttachment,
    clearAttachments,
    insertContentIntoInput,

    // Constants
    promptMaxChars: PROMPT_MAX_CHARS,
    attachmentMaxSize: ATTACHMENT_MAX_SIZE,
    attachmentsTotalMaxSize: ATTACHMENTS_TOTAL_MAX_SIZE,
    maxAttachments: MAX_ATTACHMENTS,
  }
}
