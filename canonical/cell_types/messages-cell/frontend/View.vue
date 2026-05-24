<template>
  <div class="messages-cell border border-border dark:border-border-dark rounded-lg flex flex-col h-full min-h-[200px]">
    <!-- Loading state -->
    <div
      v-if="localIsLoading"
      class="flex-1 flex items-center justify-center"
    >
      <p class="text-sm text-text-secondary dark:text-text-secondary-dark">
        {{ $t('messagesCell.loading') }}
      </p>
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
        {{ $t('messagesCell.retry') }}
      </button>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="displayMessages.length === 0"
      class="flex-1 flex items-center justify-center"
    >
      <p class="text-sm text-text-secondary dark:text-text-secondary-dark">
        {{ $t('messagesCell.empty') }}
      </p>
    </div>

    <!-- Messages list with timeline threading -->
    <div v-else class="flex-1 overflow-y-auto px-4 py-3 space-y-2">
      <template v-for="group in groupedMessages" :key="group.key">
        <!-- Root message (no thread_id) -->
        <div
          class="message-root border border-border dark:border-border-dark rounded-lg p-3"
        >
          <div class="flex items-baseline justify-between gap-2 mb-1">
            <span class="text-xs font-semibold text-primary dark:text-primary-light">
              {{ group.root.sender_name || group.root.sender_id }}
            </span>
            <span class="text-xs text-text-secondary dark:text-text-secondary-dark">
              {{ group.root.created_at ? formatDate(group.root.created_at) : '' }}
            </span>
          </div>
          <p v-if="group.root.subject" class="text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">
            {{ group.root.subject }}
          </p>
          <p class="text-sm text-text-primary dark:text-text-primary-dark break-words">
            {{ group.root.body || group.root.payload?.text || group.root.payload?.body || '' }}
          </p>

          <!-- Reply button (only when readOnly=false) -->
          <button
            v-if="!props.readOnly && group.root.sender_id"
            class="mt-2 text-xs text-primary dark:text-primary-light hover:underline"
            @click="emit('reply', group.root)"
          >
            {{ $t('messagesCell.reply') }}
          </button>
        </div>

        <!-- Replies (indented with connector line) -->
        <div
          v-if="group.replies.length > 0"
          class="thread-replies ml-5 border-l-2 border-border dark:border-border-dark pl-4 space-y-2"
        >
          <template v-for="(reply, rIdx) in visibleReplies(group)" :key="reply._id || reply.id">
            <div class="message-reply relative">
              <!-- Vertical connector dot -->
              <div class="absolute -left-4 top-2 w-2 h-2 rounded-full bg-border dark:bg-border-dark border-2 border-surface dark:border-surface-dark"></div>
              <div class="border border-border dark:border-border-dark rounded-lg p-3 bg-surface-alt dark:bg-surface-alt-dark">
                <div class="flex items-baseline justify-between gap-2 mb-1">
                  <span class="text-xs font-semibold">
                    <span class="text-text-secondary dark:text-text-secondary-dark">—</span>
                    <span class="text-primary dark:text-primary-light ml-1">
                      {{ reply.sender_name || reply.sender_id }}
                    </span>
                  </span>
                  <span class="text-xs text-text-secondary dark:text-text-secondary-dark">
                    {{ reply.created_at ? formatDate(reply.created_at) : '' }}
                  </span>
                </div>
                <p v-if="reply.subject" class="text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">
                  {{ reply.subject }}
                </p>
                <p class="text-sm text-text-primary dark:text-text-primary-dark break-words">
                  {{ reply.body || reply.payload?.text || reply.payload?.body || '' }}
                </p>

                <!-- Reply button on replies (only when readOnly=false) -->
                <button
                  v-if="!props.readOnly && reply.sender_id"
                  class="mt-2 text-xs text-primary dark:text-primary-light hover:underline"
                  @click="emit('reply', reply)"
                >
                  {{ $t('messagesCell.reply') }}
                </button>
              </div>
            </div>
          </template>

          <!-- Expand/collapse for long threads -->
          <button
            v-if="group.replies.length > 3"
            class="text-xs text-primary dark:text-primary-light hover:underline py-1"
            @click="toggleThread(group.key)"
          >
            {{ expandedThreads.has(group.key)
              ? $t('messagesCell.threadCollapse')
              : $t('messagesCell.threadExpand', { count: group.replies.length - 3 })
            }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { loadCellI18n } from '#canonical/shared/utils/cellI18nLoader'
import { useMessagesCell } from './composables/useMessagesCell'

// ─────────────────────────────────────────────────────────────────────────────
// Buffer Local Pattern (REACTIVITY_ISOLATION.md)
// All interactivity state lives in local refs; synced to cell only on actions.
// ─────────────────────────────────────────────────────────────────────────────

interface Props {
  cell?: any
  cellId?: string
  /** When false, shows Reply button and emits @reply events */
  readOnly?: boolean
  /** External messages array for state sync (e.g. from inbox-cell) */
  messages?: any[]
}

const props = withDefaults(defineProps<Props>(), {
  cell: undefined,
  cellId: undefined,
  readOnly: true,
  messages: undefined,
})

const emit = defineEmits<{
  reply: [msg: any]
}>()

// ─── Local state ────────────────────────────────────────────────────────────
const messagesApi = useMessagesCell()
const localMessages = ref<any[]>([])
const localIsLoading = ref(false)
const localError = ref<string | null>(null)
const expandedThreads = ref<Set<string>>(new Set())

// ─── Display computed ──────────────────────────────────────────────────────
// Priority: external messages (prop sync) > local messages (self-loaded)
const displayMessages = computed(() => {
  if (props.messages) return props.messages
  return localMessages.value
})

/**
 * Group messages into timeline threads:
 * - Messages without thread_id are flat root messages (each its own group)
 * - Messages with thread_id are replies grouped under their root
 * - The root message is looked up by matching thread_id to the message's _id
 */
interface ThreadGroup {
  key: string
  root: any
  replies: any[]
}

const groupedMessages = computed<ThreadGroup[]>(() => {
  const msgs = displayMessages.value
  if (!msgs || msgs.length === 0) return []

  // Index messages by id for root lookup
  const byId = new Map<string, any>()
  for (const msg of msgs) {
    byId.set(msg._id || msg.id, msg)
  }

  // Separate threaded (with thread_id) from flat messages
  const threaded: any[] = []
  const flat: any[] = []
  for (const msg of msgs) {
    if (msg.thread_id) {
      threaded.push(msg)
    } else {
      flat.push(msg)
    }
  }

  // Group threaded by thread_id
  const threadMap = new Map<string, any[]>()
  for (const reply of threaded) {
    const tid = reply.thread_id
    if (!threadMap.has(tid)) {
      threadMap.set(tid, [])
    }
    threadMap.get(tid)!.push(reply)
  }

  const groups: ThreadGroup[] = []

  // Sort flat messages by date
  flat.sort((a, b) => (a.created_at || '').localeCompare(b.created_at || ''))

  for (const root of flat) {
    const rootId = root._id || root.id
    const replies = threadMap.get(rootId) || []
    // Sort replies by date
    replies.sort((a, b) => (a.created_at || '').localeCompare(b.created_at || ''))

    groups.push({
      key: `flat-${rootId}`,
      root,
      replies,
    })
    // Remove from threadMap so we don't double-process
    if (threadMap.has(rootId)) {
      threadMap.delete(rootId)
    }
  }

  // Any remaining threads whose root wasn't found (orphan replies)
  for (const [tid, replies] of threadMap.entries()) {
    replies.sort((a, b) => (a.created_at || '').localeCompare(b.created_at || ''))
    // Use the first reply as the "root" display (it's the thread starter from our perspective)
    const first = replies[0]
    groups.push({
      key: `thread-${tid}`,
      root: first,
      replies: replies.slice(1),
    })
  }

  return groups
})

// ─── Visible replies (with expand/collapse) ────────────────────────────────

function visibleReplies(group: ThreadGroup): any[] {
  if (group.replies.length > 3 && !expandedThreads.value.has(group.key)) {
    return group.replies.slice(0, 3) // Show first 3 by default
  }
  return group.replies
}

function toggleThread(key: string) {
  const next = new Set(expandedThreads.value)
  if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }
  expandedThreads.value = next
}

// ─── Data loading ──────────────────────────────────────────────────────────

async function loadData() {
  localIsLoading.value = true
  localError.value = null
  await messagesApi.loadMessages()
  localMessages.value = [...messagesApi.messages.value]
  if (messagesApi.error.value) {
    localError.value = messagesApi.error.value
  }
  localIsLoading.value = false
}

function handleRefresh() {
  loadData()
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

// ─── Expose for parent refresh ────────────────────────────────────────────
defineExpose({ loadData })

// ─── Lifecycle ─────────────────────────────────────────────────────────────

onMounted(() => {
  // Load own i18n translations for $t('messagesCell.*') keys
  loadCellI18n('messages-cell')
  // Only self-load if no external messages provided
  if (!props.messages) {
    loadData()
  }
})
</script>

<style scoped>
.messages-cell {
  background-color: var(--color-surface, #ffffff);
}
</style>
