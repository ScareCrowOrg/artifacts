<template>
  <div class="inbox-cell bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg flex flex-col h-full min-h-[400px]">
    <!-- Tabs -->
    <div class="flex border-b border-border dark:border-border-dark">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="flex-1 px-4 py-3 text-sm font-medium transition-colors"
        :class="localActiveTab === tab.id
          ? 'text-primary border-b-2 border-primary bg-surface-alt dark:bg-surface-alt-dark'
          : 'text-text-secondary dark:text-text-secondary-dark hover:text-primary hover:bg-surface-alt dark:hover:bg-surface-alt-dark'"
        @click="switchTab(tab.id)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Loading state -->
    <div
      v-if="localIsLoading"
      class="flex-1 flex items-center justify-center"
    >
      <p class="text-sm text-text-secondary dark:text-text-secondary-dark">Loading…</p>
    </div>

    <!-- Error state -->
    <div
      v-else-if="localError"
      class="flex-1 flex flex-col items-center justify-center gap-3 px-4"
    >
      <p class="text-sm text-error dark:text-error-light text-center">
        {{ localError }}
      </p>
      <button
        class="px-3 py-1 text-xs bg-primary dark:bg-primary-hover text-white rounded hover:bg-primary-hover transition"
        @click="handleRefresh"
      >
        Retry
      </button>
    </div>

    <!-- Messages tab -->
    <template v-else-if="localActiveTab === 'messages'">
      <MessagesCellView
        :readOnly="false"
        :messages="localMessages"
        @reply="handleStartReply"
      />

      <!-- Inline reply form (overlay) -->
      <div
        v-if="localReplyTarget"
        class="border-t border-border dark:border-border-dark px-4 py-3"
      >
        <p class="text-xs font-semibold text-text-secondary dark:text-text-secondary-dark mb-2">
          Reply to {{ localReplyTarget.sender_id }}
        </p>
        <input
          v-model="localReplySubject"
          type="text"
          placeholder="Subject (optional)"
          class="w-full px-2 py-1 mb-2 text-xs border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark rounded focus:outline-none focus:ring-1 focus:ring-primary"
        />
        <textarea
          v-model="localReplyBody"
          placeholder="Type your reply…"
          rows="3"
          class="w-full px-2 py-1 mb-2 text-xs border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark rounded focus:outline-none focus:ring-1 focus:ring-primary resize-none"
        ></textarea>
        <div class="flex gap-2 justify-end">
          <button
            class="px-3 py-1 text-xs bg-surface-alt dark:bg-surface-alt-dark border border-border dark:border-border-dark rounded hover:bg-surface-alt-dark dark:hover:bg-surface-alt transition"
            @click="handleCancelReply"
          >
            Cancel
          </button>
          <button
            :disabled="!localReplyBody.trim()"
            class="px-3 py-1 text-xs bg-primary dark:bg-primary-hover text-white rounded hover:bg-primary-hover transition disabled:opacity-50 disabled:cursor-not-allowed"
            @click="handleSendReply(localReplyTarget)"
          >
            Send
          </button>
        </div>
        <p v-if="localReplyError" class="mt-1 text-xs text-error dark:text-error-light">
          {{ localReplyError }}
        </p>
      </div>
    </template>

    <!-- Requests tab -->
    <template v-else-if="localActiveTab === 'requests'">
      <RequestsCellView
        :readOnly="false"
        :requests="localRequests"
        @approve="handleApprove"
        @reject="handleReject"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useInboxCell } from './composables/useInboxCell'
import MessagesCellView from '#canonical/cell_types/messages-cell/frontend/View.vue'
import RequestsCellView from '#canonical/cell_types/requests-cell/frontend/View.vue'

// ─────────────────────────────────────────────────────────────────────────────
// Buffer Local Pattern (REACTIVITY_ISOLATION.md)
// All interactivity state lives in local refs; synced to cell only on actions.
// ─────────────────────────────────────────────────────────────────────────────

interface Props {
  cell?: any
  cellId?: string
}

const props = withDefaults(defineProps<Props>(), {
  cell: undefined,
  cellId: undefined,
})

// ─── Tab state ─────────────────────────────────────────────────────────────

const tabs = [
  { id: 'messages', label: 'Messages' },
  { id: 'requests', label: 'Requests' },
]
const localActiveTab = ref('messages')

// ─── Reply state ────────────────────────────────────────────────────────────
const localReplyTarget = ref<any>(null)
const localReplySubject = ref('')
const localReplyBody = ref('')
const localReplyError = ref<string | null>(null)

// ─── Data ────────────────────────────────────────────────────────────────────
const inbox = useInboxCell()
const localMessages = ref<any[]>([])
const localRequests = ref<any[]>([])
const localIsLoading = ref(false)
const localError = ref<string | null>(null)

// ─── Data loading ──────────────────────────────────────────────────────────

async function loadData() {
  localIsLoading.value = true
  localError.value = null

  if (localActiveTab.value === 'messages') {
    await inbox.loadMessages()
    localMessages.value = [...inbox.messages.value]
  } else {
    await inbox.loadRequests()
    localRequests.value = [...inbox.requests.value]
  }

  if (inbox.error.value) {
    localError.value = inbox.error.value
    localIsLoading.value = inbox.isLoading.value
  } else {
    localIsLoading.value = false
  }
}

// ─── Handlers ──────────────────────────────────────────────────────────────

function switchTab(tabId: string) {
  localActiveTab.value = tabId
  loadData()
}

function handleRefresh() {
  loadData()
}

function handleStartReply(msg: any) {
  localReplyTarget.value = msg
  localReplySubject.value = ''
  localReplyBody.value = ''
  localReplyError.value = null
}

function handleCancelReply() {
  localReplyTarget.value = null
  localReplySubject.value = ''
  localReplyBody.value = ''
  localReplyError.value = null
}

async function handleSendReply(msg: any) {
  localReplyError.value = null
  const success = await inbox.replyToMessage(
    msg.sender_id,
    localReplySubject.value || 'Re: ' + (msg.subject || ''),
    localReplyBody.value,
  )
  if (success) {
    localReplyTarget.value = null
    localReplySubject.value = ''
    localReplyBody.value = ''
  } else {
    localReplyError.value = inbox.error.value || 'Failed to send reply'
  }
}

async function handleApprove(requestId: string) {
  localError.value = null
  const success = await inbox.approveRequest(requestId)
  if (success) {
    localRequests.value = [...inbox.requests.value]
  } else {
    localError.value = inbox.error.value || 'Failed to approve request'
  }
}

async function handleReject(requestId: string) {
  localError.value = null
  const success = await inbox.rejectRequest(requestId)
  if (success) {
    localRequests.value = [...inbox.requests.value]
  } else {
    localError.value = inbox.error.value || 'Failed to reject request'
  }
}

// ─── Lifecycle ─────────────────────────────────────────────────────────────

onMounted(() => {
  loadData()
})
</script>
