/**
 * Chat Type Definitions
 * 
 * TypeScript interfaces for chat functionality, including messages,
 * models, attachments, and conversation history.
 */

/**
 * Chat message structure
 */
export interface ChatMessage {
  /** Message content (Markdown-formatted) */
  content: string
  
  /** Message role */
  role: 'user' | 'assistant' | 'system'
  
  /** Message timestamp */
  timestamp?: string
  
  /** Optional conversation ID */
  conversationId?: string
  
  /** Optional model used for this message */
  model?: string
  
  /** Optional attachments for this message */
  attachments?: ChatAttachment[]
}

/**
 * Chat attachment structure
 */
export interface ChatAttachment {
  /** Attachment filename */
  filename: string
  
  /** Attachment content */
  content: string
  
  /** Attachment type/MIME type */
  type: string
  
  /** Attachment size in bytes */
  size: number
  
  /** Optional full file path (when available) */
  path?: string
}

/**
 * AI Model definition
 */
export interface AIModel {
  /** Model identifier value */
  value: string
  
  /** Human-readable label */
  label: string
  
  /** Model type (local, cloud, byok) */
  type: 'local' | 'cloud' | 'byok'
  
  /** Provider name */
  provider?: string
  
  /** Model description */
  description?: string
  
  /** Model capabilities/tags */
  capabilities?: string[]
}

/**
 * RAG Collection definition
 */
export interface RAGCollection {
  /** Collection identifier */
  value: string
  
  /** Collection display label */
  label: string
  
  /** Collection icon (emoji or icon identifier) */
  icon: string
}

/**
 * Chat conversation metadata
 */
export interface ChatConversation {
  /** Unique conversation ID */
  id: string
  
  /** Conversation title */
  title: string
  
  /** List of messages */
  messages: ChatMessage[]
  
  /** Creation timestamp */
  createdAt: string
  
  /** Last update timestamp */
  updatedAt: string
  
  /** Optional OpenAI thread ID for continuity */
  threadId?: string
  
  /** Optional OpenAI assistant ID for continuity */
  assistantId?: string
  
  /** Optional metadata */
  metadata?: {
    /** Model used in conversation */
    model?: string
    /** Additional context */
    context?: Record<string, unknown>
  }
}

/**
 * Chat history props interface
 */
export interface ChatHistoryProps {
  /** Persistent conversation ID for this instance */
  conversationId: string
}

/**
 * Chat history composable return type
 */
export interface UseChatHistoryReturn {
  /** List of all conversations from global bank */
  allConversations: import('vue').Ref<ChatConversation[]>
  
  /** Current conversation for this instance (computed, filtered by conversationId) */
  currentConversation: import('vue').ComputedRef<ChatConversation | null>
  
  /** Create new conversation */
  createConversation: (title?: string) => ChatConversation
  
  /** Add message to the current conversation (identified by conversationId) */
  addMessage: (message: ChatMessage) => void
  
  /** Delete conversation by ID */
  deleteConversation: (conversationId: string) => void
  
  /** Get most recent conversation ID */
  getMostRecentConversationId: () => string | null
}

/**
 * Conversation summary structure
 */
export interface ConversationSummary {
  id: string
  title: string
  messageCount: number
  createdAt: string
  updatedAt: string
  model?: string
  preview: string
}

/**
 * Chat IA composable props interface
 */
export interface UseChatIAProps {
  /** Persistent conversation ID for this instance */
  conversationId: string
  
  /** Chat history composable instance */
  chatHistory: UseChatHistoryReturn
  
  /** Callback to emit cell creation event */
  emitCellCreated: (content: string) => void
  
  /** Callback to scroll chat to bottom */
  scrollToBottom: () => void
  
  /** Optional active cell ref for notebook context */
  activeCellRef?: import('vue').Ref<any> | null
}

/**
 * Chat IA composable return type
 */
export interface UseChatIAReturn {
  /** List of chat messages */
  messages: import('vue').Ref<ChatMessage[]>
  
  /** User input text */
  userInput: import('vue').Ref<string>
  
  /** Loading state */
  isLoading: import('vue').Ref<boolean>
  
  /** Selected AI model */
  selectedModel: import('vue').Ref<string>
  
  /** Available AI models */
  availableModels: import('vue').Ref<AIModel[]>
  
  /** Models loading state */
  isLoadingModels: import('vue').Ref<boolean>
  
  /** Models error state */
  modelsError: import('vue').Ref<string | null>
  
  /** Intention classification enabled flag */
  enableIntentionClassification: import('vue').Ref<boolean>
  
  /** Chat attachments */
  attachments: import('vue').Ref<ChatAttachment[]>
  
  /** OpenAI thread ID for conversation continuity */
  threadId: import('vue').Ref<string | null>
  
  /** OpenAI assistant ID for conversation continuity */
  assistantId: import('vue').Ref<string | null>
  
  /** Available RAG collections */
  availableCollections: import('vue').Ref<RAGCollection[]>
  
  /** Selected RAG collections */
  selectedCollections: import('vue').Ref<string[]>
  
  /** Local models (computed) */
  localModels: import('vue').ComputedRef<AIModel[]>
  
  /** External models (computed) */
  externalModels: import('vue').ComputedRef<AIModel[]>
  
  /** Prompt character count (computed) */
  promptCharCount: import('vue').ComputedRef<number>
  
  /** Prompt limit reached flag (computed) */
  promptLimitReached: import('vue').ComputedRef<boolean>
  
  /** Prompt warning flag (computed) */
  promptWarning: import('vue').ComputedRef<boolean>
  
  /** Attachments size (computed) */
  attachmentsSize: import('vue').ComputedRef<number>
  
  /** Attachments limit reached flag (computed) */
  attachmentsLimitReached: import('vue').ComputedRef<boolean>
  
  /** Attachments warning flag (computed) */
  attachmentsWarning: import('vue').ComputedRef<boolean>
  
  /** Send message to AI */
  sendMessage: () => Promise<void>
  
  /** Clear chat messages */
  clearChat: () => void
  
  /** Fetch available models */
  fetchModels: () => Promise<void>
  
  /** Load last conversation */
  loadLastConversation: () => void
  
  /** Load conversation by ID */
  loadConversation: (id: string) => void
  
  /** Add attachment */
  addAttachment: (filename: string, content: string, type?: string) => boolean
  
  /** Remove attachment */
  removeAttachment: (attachmentId: string) => void
  
  /** Insert content into input */
  insertContentIntoInput: (content: string, asAttachment?: boolean, filename?: string) => void
}

/**
 * Chat component API (exposed methods)
 */
export interface ChatComponentAPI {
  /** Insert content into chat input */
  insertContentIntoInput: (content: string, asAttachment?: boolean, filename?: string) => void
  
  /** Add attachment to chat */
  addAttachment: (filename: string, content: string, type: string, path?: string) => boolean
}

/**
 * File proposal data structure
 */
export interface FileProposal {
  /** Proposal type */
  type: 'create' | 'update' | 'delete'
  
  /** Target file path */
  filePath: string
  
  /** Proposal description */
  description: string
  
  /** Original file content (for updates) */
  originalContent?: string
  
  /** New/proposed content */
  content: string
  
  /** Starting line for snippet updates (1-indexed) */
  startLine?: number
  
  /** Ending line for snippet updates (1-indexed) */
  endLine?: number
  
  /** Whether this is a snippet update */
  isSnippet?: boolean
}
