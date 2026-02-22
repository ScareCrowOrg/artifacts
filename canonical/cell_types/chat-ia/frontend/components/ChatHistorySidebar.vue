/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-17",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-11",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues": 0,
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <aside
    class="flex flex-col h-full bg-surface dark:bg-surface-dark border-l border-border dark:border-border-dark w-[300px] max-w-full md:max-w-full"
    data-testid="chat-history-sidebar"
  >
    <div
      class="flex items-center justify-between p-4 border-b border-border dark:border-border-dark flex-shrink-0"
    >
      <h3 class="text-base font-semibold text-text-primary dark:text-text-primary-dark m-0">
        {{ $t('chatHistory.title') }}
      </h3>
      <button
        class="btn-close px-2 py-1 bg-transparent border border-border dark:border-border-dark rounded cursor-pointer text-base transition-all hover:bg-error/10 hover:border-error hover:text-error focus:outline-none focus:ring-2 focus:ring-error focus:ring-offset-2"
        :title="$t('chatHistory.closeTooltip')"
        :aria-label="$t('chatHistory.closeAriaLabel')"
        @click="$emit('close')"
      >
        ✕
      </button>
    </div>

    <div class="flex flex-col flex-1 overflow-hidden p-4 gap-2">
      <!-- Search bar -->
      <div class="flex-shrink-0">
        <input
          v-model="searchQuery"
          type="text"
          :placeholder="$t('chatHistory.searchPlaceholder')"
          class="search-input w-full px-3 py-2 border border-border dark:border-border-dark rounded-md bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
          :aria-label="$t('chatHistory.searchAriaLabel')"
        />
      </div>

      <!-- New conversation button -->
      <button
        class="new-conversation-btn w-full inline-flex items-center justify-center gap-1 px-3 py-2 h-9 bg-primary text-text-on-primary font-medium text-sm rounded-md border-0 cursor-pointer transition-all hover:bg-primary-hover active:translate-y-0 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap select-none flex-shrink-0"
        :aria-label="$t('chatHistory.newConversationAriaLabel')"
        @click="handleNewConversation"
      >
        {{ $t('chatHistory.newConversationButton') }}
      </button>

      <!-- Conversations list -->
      <div class="flex-1 overflow-y-auto flex flex-col gap-2">
        <div
          v-if="filteredConversations.length === 0"
          class="text-center py-6 text-text-secondary dark:text-text-secondary-dark text-sm"
        >
          <p v-if="searchQuery">{{ $t('chatHistory.noConversationsFound') }}</p>
          <p v-else>{{ $t('chatHistory.noConversationsYet') }}</p>
        </div>

        <div
          v-for="conversation in filteredConversations"
          :key="conversation.id"
          :class="[
            'conversation-item p-3 border border-border dark:border-border-dark rounded-md bg-surface dark:bg-surface-dark cursor-pointer transition-all',
            'hover:bg-surface-hover dark:hover:bg-surface-hover-dark hover:border-primary',
            conversation.id === currentConversationId
              ? 'active bg-primary/8 dark:bg-primary/10 border-primary ring-2 ring-primary/10'
              : '',
            'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
          ]"
          role="button"
          tabindex="0"
          :aria-label="$t('chatHistory.conversationAriaLabel', { title: conversation.title })"
          @click="editingConversationId !== conversation.id ? handleSelectConversation(conversation.id) : null"
          @keydown.enter="editingConversationId !== conversation.id ? handleSelectConversation(conversation.id) : null"
        >
          <div class="flex items-center justify-between gap-2 mb-1">
            <!-- Title (editable) -->
            <input
              v-if="editingConversationId === conversation.id"
              :ref="(el) => setRenameInputRef(el, conversation.id)"
              v-model="editingTitle"
              type="text"
              class="flex-1 text-sm font-medium text-text-primary dark:text-text-primary-dark px-2 py-1 border border-primary rounded bg-surface dark:bg-surface-dark focus:outline-none focus:ring-2 focus:ring-primary"
              :placeholder="$t('chatHistory.renamePlaceholder')"
              :aria-label="$t('chatHistory.renameAriaLabel')"
              @click.stop
              @keydown="handleRenameKeydown($event, conversation.id)"
            />
            <span
              v-else
              class="flex-1 text-sm font-medium text-text-primary dark:text-text-primary-dark whitespace-nowrap overflow-hidden text-ellipsis"
            >
              {{ conversation.title }}
            </span>

            <!-- Action buttons -->
            <div class="flex items-center gap-1 flex-shrink-0">
              <!-- Rename/Save/Cancel buttons -->
              <button
                v-if="editingConversationId !== conversation.id"
                class="btn-rename px-2 py-1 bg-transparent border border-transparent rounded cursor-pointer text-xs transition-all hover:bg-primary/10 hover:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                :title="$t('chatHistory.renameTooltip')"
                :aria-label="$t('chatHistory.renameAriaLabel')"
                @click.stop="startRenaming(conversation.id, conversation.title)"
              >
                ✏️
              </button>
              <button
                v-if="editingConversationId === conversation.id"
                class="btn-save-rename px-2 py-1 bg-transparent border border-transparent rounded cursor-pointer text-xs transition-all hover:bg-success/10 hover:border-success focus:outline-none focus:ring-2 focus:ring-success"
                :title="$t('chatHistory.saveRenameTooltip')"
                :aria-label="$t('chatHistory.saveRenameAriaLabel')"
                @click.stop="saveRename(conversation.id)"
              >
                ✓
              </button>
              <button
                v-if="editingConversationId === conversation.id"
                class="btn-cancel-rename px-2 py-1 bg-transparent border border-transparent rounded cursor-pointer text-xs transition-all hover:bg-error/10 hover:border-error focus:outline-none focus:ring-2 focus:ring-error"
                :title="$t('chatHistory.cancelRenameTooltip')"
                :aria-label="$t('chatHistory.cancelRenameAriaLabel')"
                @click.stop="cancelRenaming()"
              >
                ✕
              </button>

              <!-- Delete button -->
              <button
                v-if="editingConversationId !== conversation.id"
                class="btn-delete px-2 py-1 bg-transparent border border-transparent rounded cursor-pointer text-xs transition-all hover:bg-error/10 hover:border-error focus:outline-none focus:ring-2 focus:ring-error"
                :title="$t('chatHistory.deleteTooltip')"
                :aria-label="$t('chatHistory.deleteAriaLabel')"
                @click.stop="handleDeleteConversation(conversation.id)"
              >
                🗑️
              </button>
            </div>
          </div>
          <div
            class="flex items-center justify-between text-xs text-text-secondary dark:text-text-secondary-dark gap-2"
          >
            <span class="whitespace-nowrap"
              >{{ $t('chatHistory.messagesCount', { count: conversation.messages.length }) }}</span
            >
            <span class="whitespace-nowrap">{{
              formatDate(conversation.updatedAt)
            }}</span>
          </div>
          <div
            v-if="conversation.model"
            class="mt-1 text-xs text-primary font-medium"
          >
            🤖 {{ conversation.model }}
          </div>
        </div>
      </div>

      <!-- Clear all button -->
      <button
        v-if="conversations.length > 0"
        class="clear-all-btn w-full inline-flex items-center justify-center gap-1 px-3 py-2 h-9 bg-error text-text-on-primary font-medium text-sm rounded-md border-0 cursor-pointer transition-all hover:bg-error/90 active:translate-y-0 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap select-none mt-2 flex-shrink-0"
        :aria-label="$t('chatHistory.clearAllAriaLabel')"
        @click="handleClearAll"
      >
        {{ $t('chatHistory.clearAllButton') }}
      </button>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  conversations: {
    type: Array,
    required: true,
  },
  currentConversationId: {
    type: String,
    default: null,
  },
})

const emit = defineEmits([
  'close',
  'select-conversation',
  'new-conversation',
  'delete-conversation',
  'clear-all',
  'rename-conversation',
])

const searchQuery = ref('')
const editingConversationId = ref(null)
const editingTitle = ref('')
const renameInputRef = ref(null)

function setRenameInputRef(el, conversationId) {
  if (el && editingConversationId.value === conversationId) {
    renameInputRef.value = el
  }
}

const filteredConversations = computed(() => {
  if (!searchQuery.value || searchQuery.value.trim() === '') {
    return props.conversations
  }

  const lowerQuery = searchQuery.value.toLowerCase()

  return props.conversations.filter((conversation) => {
    // Search in title
    if (conversation.title.toLowerCase().includes(lowerQuery)) {
      return true
    }

    // Search in messages
    return conversation.messages.some((msg) =>
      msg.content.toLowerCase().includes(lowerQuery)
    )
  })
})

function handleNewConversation() {
  emit('new-conversation')
}

function handleSelectConversation(conversationId) {
  emit('select-conversation', conversationId)
}

function handleDeleteConversation(conversationId) {
  if (confirm(t('chatHistory.confirmDelete'))) {
    emit('delete-conversation', conversationId)
  }
}

function handleClearAll() {
  if (
    confirm(
      t('chatHistory.confirmClearAll')
    )
  ) {
    emit('clear-all')
  }
}

function startRenaming(conversationId, currentTitle) {
  editingConversationId.value = conversationId
  editingTitle.value = currentTitle
  nextTick(() => {
    // Focus the input element using the ref
    if (renameInputRef.value) {
      renameInputRef.value.focus()
      renameInputRef.value.select()
    }
  })
}

function cancelRenaming() {
  editingConversationId.value = null
  editingTitle.value = ''
}

function saveRename(conversationId) {
  const newTitle = editingTitle.value.trim()
  if (newTitle && newTitle !== '') {
    emit('rename-conversation', conversationId, newTitle)
  }
  cancelRenaming()
}

function handleRenameKeydown(event, conversationId) {
  if (event.key === 'Enter') {
    event.preventDefault()
    saveRename(conversationId)
  } else if (event.key === 'Escape') {
    event.preventDefault()
    cancelRenaming()
  }
}

function formatDate(isoString) {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return t('chatHistory.timeNow')
  if (diffMins < 60) return t('chatHistory.timeMinutesAgo', { minutes: diffMins })
  if (diffHours < 24) return t('chatHistory.timeHoursAgo', { hours: diffHours })
  if (diffDays < 7) return t('chatHistory.timeDaysAgo', { days: diffDays })

  return date.toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: diffDays > 365 ? '2-digit' : undefined,
  })
}
</script>
