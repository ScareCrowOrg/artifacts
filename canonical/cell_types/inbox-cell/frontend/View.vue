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
      <div v-if="localMessages.length === 0" class="flex-1 flex items-center justify-center">
        <p class="text-sm text-text-secondary dark:text-text-secondary-dark">No messages yet.</p>
      </div>
      <div v-else class="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        <div
          v-for="msg in localMessages"
          :key="msg._id"
          class="message-item border border-border dark:border-border-dark rounded-lg p-3"
        >
          <div class="flex items-baseline justify-between gap-2 mb-1">
            <span class="text-xs font-semibold text-primary dark:text-primary-light">
              {{ msg.sender_id }}
            </span>
            <span class="text-xs text-text-secondary dark:text-text-secondary-dark">
              {{ msg.created_at ? formatDate(msg.created_at) : '' }}
            </span>
          </div>
          <p v-if="msg.subject" class="text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">
            {{ msg.subject }}
          </p>
          <p class="text-sm text-text-primary dark:text-text-primary-dark break-words">
            {{ msg.body || msg.payload?.text || '' }}
          </p>
          <button
            v-if="msg.sender_id"
            class="mt-2 text-xs text-primary dark:text-primary-light hover:underline"
            @click="handleStartReply(msg)"
          >
            Reply
          </button>

          <!-- Inline reply form -->
          <div v-if="localReplyTarget?._id === msg._id" class="mt-2 border-t border-border dark:border-border-dark pt-2">
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
                @click="handleSendReply(msg)"
              >
                Send
              </button>
            </div>
            <p v-if="localReplyError" class="mt-1 text-xs text-error dark:text-error-light">
              {{ localReplyError }}
            </p>
          </div>
        </div>
      </div>
    </template>

    <!-- Requests tab -->
    <template v-else-if="localActiveTab === 'requests'">
      <div v-if="localRequests.length === 0" class="flex-1 flex items-center justify-center">
        <p class="text-sm text-text-secondary dark:text-text-secondary-dark">No requests yet.</p>
      </div>
      <div v-else class="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        <div
          v-for="req in localRequests"
          :key="req._id"
          class="request-item border border-border dark:border-border-dark rounded-lg p-3"
        >
          <div class="flex items-baseline justify-between gap-2 mb-1">
            <span class="text-xs font-semibold text-primary dark:text-primary-light">
              {{ req.sender_id }}
            </span>
            <span
              class="text-xs px-2 py-0.5 rounded-full"
              :class="statusBadgeClass(req.status)"
            >
              {{ req.status }}
            </span>
          </div>
          <p class="text-xs text-text-secondary dark:text-text-secondary-dark mb-1">
            Type: {{ req.request_type }}
          </p>
          <p v-if="req.payload?.message" class="text-sm text-text-primary dark:text-text-primary-dark break-words mb-2">
            {{ req.payload.message }}
          </p>
          <p v-if="req.created_at" class="text-xs text-text-secondary dark:text-text-secondary-dark">
            {{ formatDate(req.created_at) }}
          </p>

          <!-- Approve/Reject buttons (only for pending requests) -->
          <div v-if="req.status === 'pending'" class="flex gap-2 mt-2 pt-2 border-t border-border dark:border-border-dark">
            <button
              :disabled="localActionInProgress === req._id"
              class="flex-1 px-3 py-1.5 text-xs bg-success dark:bg-success text-white rounded hover:opacity-90 transition disabled:opacity-50 disabled:cursor-not-allowed"
              @click="handleApprove(req._id)"
            >
              <span v-if="localActionInProgress === req._id">…</span>
              <span v-else>Approve</span>
            </button>
            <button
              :disabled="localActionInProgress === req._id"
              class="flex-1 px-3 py-1.5 text-xs bg-error dark:bg-error text-white rounded hover:opacity-90 transition disabled:opacity-50 disabled:cursor-not-allowed"
              @click="handleReject(req._id)"
            >
              <span v-if="localActionInProgress === req._id">…</span>
              <span v-else>Reject</span>
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useInboxCell } from './composables/useInboxCell'

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

// ─── Action state ────────────────────────────────────────────────────────────
const localActionInProgress = ref<string | null>(null)

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
  }
  localIsLoading.value = inbox.isLoading.value
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
  localActionInProgress.value = requestId
  localError.value = null
  const success = await inbox.approveRequest(requestId)
  if (success) {
    localRequests.value = [...inbox.requests.value]
  } else {
    localError.value = inbox.error.value || 'Failed to approve request'
  }
  localActionInProgress.value = null
}

async function handleReject(requestId: string) {
  localActionInProgress.value = requestId
  localError.value = null
  const success = await inbox.rejectRequest(requestId)
  if (success) {
    localRequests.value = [...inbox.requests.value]
  } else {
    localError.value = inbox.error.value || 'Failed to reject request'
  }
  localActionInProgress.value = null
}

// ─── Helpers ───────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case 'pending':
      return 'bg-warning-light dark:bg-warning-dark text-warning-dark dark:text-warning-light'
    case 'approved':
      return 'bg-success-light dark:bg-success-dark text-success-dark dark:text-success-light'
    case 'rejected':
      return 'bg-error-light dark:bg-error-dark text-error-dark dark:text-error-light'
    default:
      return 'bg-surface-alt dark:bg-surface-alt-dark text-text-secondary dark:text-text-secondary-dark'
  }
}

// ─── Lifecycle ─────────────────────────────────────────────────────────────

onMounted(() => {
  loadData()
})
</script>
