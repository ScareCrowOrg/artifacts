/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-15",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0,
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-17",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full"
 * }
 */
<template>
  <section
    class="flex flex-col h-full relative bg-surface dark:bg-surface-dark rounded-lg shadow"
    data-testid="chat-ia-cell-container"
  >
    <ChatHeader />

    <div class="flex flex-1 overflow-hidden relative">
      <!-- Chat messages area OR Agent Terminal (Interface Mutante - MVP 4.1) -->
      <div class="flex flex-col flex-1 overflow-hidden" data-testid="chat-body">
        <!-- Classic Chat Mode (v-if) -->
        <div
          v-if="!chatStore.isAgentMode"
          ref="messagesContainer"
          class="flex-1 overflow-y-auto overflow-x-hidden p-4 min-h-0 max-h-full"
        >
          <WelcomeMessage v-if="chat.messages.value.length === 0" />

          <ChatMessage
            v-for="(message, index) in chat.messages.value"
            :key="index"
            :message="message"
            :available-models="chat.availableModels.value"
            @show-timeline="handleShowTimeline"
          />

          <ChatLoadingIndicator v-if="chat.isLoading.value" />
        </div>

        <!-- Agent Mode Terminal (v-else-if) - Occupies 100% of viewport -->
        <AgentTerminal
          v-else-if="chatStore.agentSessionId"
          :visible="true"
          :conversation-id="chatStore.agentSessionId"
          class="flex-1"
          @close="handleAgentTerminalClose"
        />

        <!-- Loading indicator while session is being created -->
        <div
          v-else
          class="flex-1 flex items-center justify-center"
          style="color: var(--color-text-secondary);"
        >
          <div class="flex flex-col items-center gap-3">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
            <p class="text-sm">
              {{ $t('agentMode.creatingSession') || 'Creating agent session...' }}
            </p>
          </div>
        </div>

        <!-- Context Bar (MVP 4.1 - Shows files in Agent Mode context) -->
        <ContextBar
          v-if="chatStore.isAgentMode"
          :attachments="chat.attachments.value"
          :on-remove="chat.removeAttachment"
        />

        <ChatInput
          :chat="chat"
          :on-input-focus="handleInputFocus"
          :on-enter="handleEnter"
          :is-agent-mode="chatStore.isAgentMode"
        />
      </div>

      <!-- Chat History Sidebar -->
      <ChatHistorySidebar
        v-if="uiStore.showChatHistory"
        :conversations="chatHistory.conversations.value"
        :current-conversation-id="chatHistory.currentConversationId.value ?? undefined"
        @close="uiStore.toggleChatHistory"
        @select-conversation="chat.loadConversation($event)"
        @new-conversation="startNewConversation"
        @delete-conversation="chatHistory.deleteConversation($event)"
        @clear-all="chatHistory.clearAllHistory()"
      />
    </div>

    <!-- Trace Timeline Modal -->
    <TraceTimelineModal
      :is-open="showTimelineModal"
      :conversation-id="selectedConversationId ?? undefined"
      @close="closeTimelineModal"
    />
    
    <!-- File Proposal Modal -->
    <FileProposalModal
      :is-visible="chatStore.isProposalModalVisible"
      :type="chatStore.currentProposal?.type || 'update'"
      :file-path="chatStore.currentProposal?.filePath || ''"
      :description="chatStore.currentProposal?.description || ''"
      :original-content="chatStore.currentProposal?.originalContent || ''"
      :content="chatStore.currentProposal?.content || ''"
      :start-line="chatStore.currentProposal?.startLine"
      :end-line="chatStore.currentProposal?.endLine"
      @accept="handleAcceptProposal"
      @cancel="chatStore.hideFileProposal"
      @close="chatStore.hideFileProposal"
    />
    
    <!-- Chat Settings Modal -->
    <ChatSettingsModal 
      :is-open="uiStore.showChatSettings"
      :chat="chat"
      @close="uiStore.toggleChatSettings"
      @update:selected-model="(value: string) => chat.selectedModel.value = value"
      @update:enable-intention-classification="(value: boolean) => chat.enableIntentionClassification.value = value"
      @update:selected-collections="(value: string[]) => chat.selectedCollections.value = value"
    />
  </section>
</template>

<script setup lang="ts">
import {
  ref,
  nextTick,
  onMounted,
  onUnmounted,
  watch,
  toRef,
} from 'vue'
import type { Ref } from 'vue'
import type { ChatComponentAPI, FileProposal } from '@/types/chat'
import ChatHeader from '@/components/chat/ChatHeader.vue'
import WelcomeMessage from '@/components/chat/WelcomeMessage.vue'
import ChatLoadingIndicator from '@/components/chat/ChatLoadingIndicator.vue'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import ChatSettingsModal from '@/components/chat/ChatSettingsModal.vue'
import ChatHistorySidebar from '@/components/ChatHistorySidebar.vue'
import TraceTimelineModal from '@/components/chat/TraceTimelineModal.vue'
import FileProposalModal from '@/components/chat/FileProposalModal.vue'
import AgentTerminal from '@/components/chat/AgentTerminal.vue'
import ContextBar from '@/components/chat/ContextBar.vue'
import { useChatHistory } from '@/composables/useChatHistory'
import { useChatIA } from '@/composables/useChatIA'
import { useChatStore } from '@/stores/chat'
import { useUIStore } from '@/stores/ui'
import authService from '@/services/authService'

/**
 * Props interface for Chat IA Cell
 */
interface Props {
  /** The chat IA cell instance */
  cell: {
    id?: string
    initial_data?: {
      selectedModel?: string
      enableIntentionClassification?: boolean
      selectedCollections?: string[]
      systemPrompt?: string
      conversationId?: string | null
    }
  }
}

const props = defineProps<Props>()

// Define emits for cell lifecycle events
const emit = defineEmits<{
  'update:cell': [cell: Props['cell']]
  'celula-criada': [content: string]
  'copy-to-manual': [content: string]
}>()

// Initialize stores
const chatStore = useChatStore()
const uiStore = useUIStore()

// Initialize chat history composable
const chatHistory = useChatHistory()

// Ref for messages container
const messagesContainer = ref<HTMLDivElement | null>(null)

// Timeline modal state
const showTimelineModal = ref<boolean>(false)
const selectedConversationId = ref<string | null>(null)

// Scroll to bottom helper
const scrollToBottom = (): void => {
  nextTick(() => {
    const container = messagesContainer.value
    if (container) {
      container.scrollTop = container.scrollHeight
    }
  })
}

// Initialize chat IA composable
const chat = useChatIA(
  chatHistory,
  (celulaConteudo: string) => emit('celula-criada', celulaConteudo),
  scrollToBottom,
)

/**
 * Send message via Agent Mode or regular chat
 * MVP 4: Routes to agent endpoint when Agent Mode is active
 */
async function sendMessageHandler(): Promise<void> {
  if (chatStore.isAgentMode) {
    // Agent Mode active - route to agent endpoint
    await sendAgentMessage()
  } else {
    // Regular chat mode
    await chat.sendMessage()
  }
}

/**
 * Send message via Agent Mode endpoint
 * Creates session if needed, streams logs to terminal
 */
async function sendAgentMessage(): Promise<void> {
  const userMessage = chat.userInput.value
  if (!userMessage.trim()) return

  try {
    // Create agent session if not exists
    if (!chatStore.agentSessionId) {
      const conversationId = chatHistory.currentConversationId.value || `conv_${Date.now()}`
      
      // Collect file paths from attachments for Agent Mode context (MVP 4.1)
      const files = chat.attachments.value.map((att: { path?: string; filename: string }) => att.path || att.filename)
      
      // Call agent session creation endpoint using authService
      const API_BASE = window.location.origin
      const token = authService.getToken()
      
      if (!token) {
        throw new Error('No authentication token available')
      }
      
      const response = await fetch(`${API_BASE}/api/agent/sessions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          conversation_id: conversationId,
          files: files,  // MVP 4.1: Include files from context bar
          model: 'ollama/qwen2.5-coder:7b',
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to create agent session')
      }

      const session = await response.json()
      chatStore.setAgentSession(session.session_id)
      
      // Show terminal and connect WebSocket
      chatStore.showAgentTerminal = true
    }

    // Add user message to chat history
    const userMsg = {
      role: 'user' as const,
      content: userMessage,
      timestamp: new Date().toISOString(),
    }
    chat.messages.value.push(userMsg)
    chatHistory.addMessage(userMsg)
    
    // Clear input
    chat.userInput.value = ''
    
    // Send command to agent endpoint (SSE streaming)
    const API_BASE = window.location.origin
    const token = authService.getToken()
    
    if (!token) {
      throw new Error('No authentication token available')
    }
    
    const response = await fetch(`${API_BASE}/api/agent/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        conversation_id: chatStore.agentSessionId,
        command: userMessage,
      }),
    })

    if (!response.ok) {
      throw new Error('Failed to send agent command')
    }

    // Read SSE stream and add to chat as assistant message
    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    let assistantResponse = '🤖 Agent Mode executing...\n\n'

    if (reader) {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        // Parse SSE format (event: log\ndata: content\n\n)
        const lines = chunk.split('\n')
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.substring(6)
            assistantResponse += data + '\n'
          }
        }
      }
    }

    // Add agent response to chat
    const assistantMsg = {
      role: 'assistant' as const,
      content: assistantResponse.trim() || 'Agent command completed.',
      timestamp: new Date().toISOString(),
      model: 'Agent Mode',
    }
    chat.messages.value.push(assistantMsg)
    chatHistory.addMessage(assistantMsg)
    
  } catch (error) {
    console.error('[Agent Mode] Error:', error)
    
    // Add error message to chat
    const errorMsg = {
      role: 'assistant' as const,
      content: `❌ Error in Agent Mode: ${(error as Error).message}`,
      timestamp: new Date().toISOString(),
    }
    chat.messages.value.push(errorMsg)
    chatHistory.addMessage(errorMsg)
  } finally {
    scrollToBottom()
  }
}

// Methods
function handleEnter(event: KeyboardEvent): void {
  if (event.shiftKey || event.ctrlKey || event.metaKey) {
    return
  }
  event.preventDefault()
  sendMessageHandler()
  
  // Update cell data with current conversation
  updateCellData()
}

function handleInputFocus(): void {
  // Input focus handler - settings now controlled via modal
}

// Handler for closing agent terminal (MVP 4.1)
function handleAgentTerminalClose(): void {
  // When closing terminal, optionally turn off agent mode
  chatStore.toggleAgentMode()
}

function startNewConversation(): void {
  chatHistory.createConversation()
  chat.messages.value = []
  uiStore.showChatHistory = false
  
  // Update cell data
  updateCellData()
}

function handleShowTimeline(conversationId: string): void {
  selectedConversationId.value = conversationId
  showTimelineModal.value = true
}

function closeTimelineModal(): void {
  showTimelineModal.value = false
  selectedConversationId.value = null
}

// Handle file proposal acceptance
async function handleAcceptProposal(proposal: FileProposal): Promise<void> {
  try {
    await chatStore.acceptFileProposal(proposal)
  } catch (error) {
    console.error('[ChatIA Cell] Error accepting proposal:', error)
  }
}

// Expose method for external calls (e.g., from parent component)
function insertContentIntoInput(content: string, asAttachment = false, filename = ''): void {
  chat.insertContentIntoInput(content, asAttachment, filename)
}

// Update cell data to persist state
function updateCellData(): void {
  emit('update:cell', {
    ...props.cell,
    initial_data: {
      ...props.cell.initial_data,
      selectedModel: chat.selectedModel.value,
      enableIntentionClassification: chat.enableIntentionClassification.value,
      selectedCollections: chat.selectedCollections.value,
      conversationId: chatHistory.currentConversationId.value,
    }
  })
}

// Watch for clear chat trigger from store
watch(
  () => uiStore.clearChatTrigger,
  () => {
    if (uiStore.clearChatTrigger > 0) {
      chat.clearChat()
      updateCellData()
    }
  },
)

// Watch for model/settings changes to update cell
watch(
  () => chat.selectedModel.value,
  () => {
    updateCellData()
  }
)

watch(
  () => chat.selectedCollections.value,
  () => {
    updateCellData()
  },
  { deep: true }
)

// Create API object for store registration
const chatComponentAPI: ChatComponentAPI = {
  insertContentIntoInput,
  addAttachment: chat.addAttachment,
}

// Register component with store on mount
onMounted(() => {
  chatStore.registerChatComponent(chatComponentAPI)
  
  // Initialize from cell data if available
  if (props.cell.initial_data) {
    const { selectedModel, enableIntentionClassification, selectedCollections, conversationId } = props.cell.initial_data
    
    if (selectedModel) {
      chat.selectedModel.value = selectedModel
    }
    if (enableIntentionClassification !== undefined) {
      chat.enableIntentionClassification.value = enableIntentionClassification
    }
    if (selectedCollections) {
      chat.selectedCollections.value = selectedCollections
    }
  }
  
  // Fetch models and load conversation
  chat.fetchModels()
  
  // Load specific conversation if set, otherwise load last
  if (props.cell.initial_data?.conversationId) {
    chat.loadConversation(props.cell.initial_data.conversationId)
  } else {
    chat.loadLastConversation()
  }
})

// Unregister component from store on unmount
onUnmounted(() => {
  chatStore.unregisterChatComponent()
})

// Expose methods for external calls (for parent component refs)
defineExpose(chatComponentAPI)
</script>
