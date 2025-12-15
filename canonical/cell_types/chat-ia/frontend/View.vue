/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-15",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0,
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-15",
 *   "theme_compliance": 99,
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
      <!-- Chat messages area -->
      <div class="flex flex-col flex-1 overflow-hidden" data-testid="chat-body">
        <div
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

        <!-- Settings Panel (collapsible) -->
        <ChatSettingsPanel 
          :visible="showSettingsPanel" 
          :chat="chat"
          @update:selected-model="(value: string) => chat.selectedModel.value = value"
          @update:enable-intention-classification="(value: boolean) => chat.enableIntentionClassification.value = value"
          @update:selected-collections="(value: string[]) => chat.selectedCollections.value = value"
        />

        <ChatInput
          :chat="chat"
          :on-input-focus="handleInputFocus"
          :on-enter="handleEnter"
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
import ChatSettingsPanel from '@/components/chat/ChatSettingsPanel.vue'
import ChatHistorySidebar from '@/components/ChatHistorySidebar.vue'
import TraceTimelineModal from '@/components/chat/TraceTimelineModal.vue'
import FileProposalModal from '@/components/chat/FileProposalModal.vue'
import { useChatHistory } from '@/composables/useChatHistory'
import { useChatIA } from '@/composables/useChatIA'
import { useChatStore } from '@/stores/chat'
import { useUIStore } from '@/stores/ui'

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

// Settings panel visibility (dynamic behavior)
const showSettingsPanel = ref<boolean>(false)

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

// Methods
function handleEnter(event: KeyboardEvent): void {
  if (event.shiftKey || event.ctrlKey || event.metaKey) {
    return
  }
  event.preventDefault()
  chat.sendMessage()
  // Hide settings panel after sending message
  showSettingsPanel.value = false
  
  // Update cell data with current conversation
  updateCellData()
}

function handleInputFocus(): void {
  // Show settings panel when input is focused
  showSettingsPanel.value = true
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

// Watch for attachment changes to show settings panel
watch(
  () => chat.attachments.value.length,
  (newLength: number, oldLength: number | undefined) => {
    if (oldLength !== undefined && newLength > oldLength) {
      // New attachment added, show settings panel
      showSettingsPanel.value = true
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
