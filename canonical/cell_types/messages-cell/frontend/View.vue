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

    <!-- Messages list -->
    <div v-else class="flex-1 overflow-y-auto px-4 py-3 space-y-3">
      <div
        v-for="msg in displayMessages"
        :key="msg._id || msg.id"
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
          {{ msg.body || msg.payload?.text || msg.payload?.body || '' }}
        </p>

        <!-- Reply button (only when readOnly=false) -->
        <button
          v-if="!props.readOnly && msg.sender_id"
          class="mt-2 text-xs text-primary dark:text-primary-light hover:underline"
          @click="emit('reply', msg)"
        >
          {{ $t('messagesCell.reply') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
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
  /** External messages array for state sync (e.g. from planet-hall) */
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

// ─── Display computed ──────────────────────────────────────────────────────
// Priority: external messages (prop sync) > local messages (self-loaded)
const displayMessages = computed(() => {
  if (props.messages) return props.messages
  return localMessages.value
})

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
