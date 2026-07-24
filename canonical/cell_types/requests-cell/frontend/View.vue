<template>
  <div class="requests-cell border border-border dark:border-border-dark rounded-lg flex flex-col h-full min-h-[200px]">
    <!-- Loading state -->
    <div
      v-if="localIsLoading"
      class="flex-1 flex items-center justify-center"
    >
      <p class="text-sm text-text-secondary dark:text-text-secondary-dark">
        {{ $t('requestsCell.loading') }}
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
        {{ $t('requestsCell.retry') }}
      </button>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="displayRequests.length === 0"
      class="flex-1 flex items-center justify-center"
    >
      <p class="text-sm text-text-secondary dark:text-text-secondary-dark">
        {{ $t('requestsCell.empty') }}
      </p>
    </div>

    <!-- Requests list -->
    <div v-else class="flex-1 overflow-y-auto px-4 py-3 space-y-3">
      <div
        v-for="req in displayRequests"
        :key="req._id || req.id"
        class="request-item border border-border dark:border-border-dark rounded-lg p-3"
      >
        <div class="flex items-baseline justify-between gap-2 mb-1">
          <span class="text-xs font-semibold text-primary dark:text-primary-light">
            {{ req.sender_name || req.sender_id }}
          </span>
          <span
            class="text-xs px-2 py-0.5 rounded-full"
            :class="statusBadgeClass(req.status)"
          >
            {{ req.status }}
          </span>
        </div>
        <p class="text-xs text-text-secondary dark:text-text-secondary-dark mb-1">
          {{ $t('requestsCell.type') }}: {{ req.request_type }}
        </p>
        <p v-if="req.payload?.message" class="text-sm text-text-primary dark:text-text-primary-dark break-words mb-2">
          {{ req.payload.message }}
        </p>
        <p v-if="req.created_at" class="text-xs text-text-secondary dark:text-text-secondary-dark">
          {{ formatDate(req.created_at) }}
        </p>

        <!-- Approve/Reject buttons (only when readOnly=false and pending) -->
        <div
          v-if="!props.readOnly && req.status === 'pending'"
          class="flex gap-2 mt-2 pt-2 border-t border-border dark:border-border-dark"
        >
          <button
            :disabled="localActionInProgress === req._id"
            class="flex-1 px-3 py-1.5 text-xs bg-success dark:bg-success text-white rounded hover:opacity-90 transition disabled:opacity-50 disabled:cursor-not-allowed"
            @click="emit('approve', req._id)"
          >
            <span v-if="localActionInProgress === req._id">…</span>
            <span v-else>{{ $t('requestsCell.approve') }}</span>
          </button>
          <button
            :disabled="localActionInProgress === req._id"
            class="flex-1 px-3 py-1.5 text-xs bg-error dark:bg-error text-white rounded hover:opacity-90 transition disabled:opacity-50 disabled:cursor-not-allowed"
            @click="emit('reject', req._id)"
          >
            <span v-if="localActionInProgress === req._id">…</span>
            <span v-else>{{ $t('requestsCell.reject') }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { loadCellI18n } from '#canonical/shared/utils/cellI18nLoader'
import { useRequestsCell } from './composables/useRequestsCell'

// ─────────────────────────────────────────────────────────────────────────────
// Buffer Local Pattern (REACTIVITY_ISOLATION.md)
// All interactivity state lives in local refs; synced to cell only on actions.
// ─────────────────────────────────────────────────────────────────────────────

interface Props {
  cell?: any
  cellId?: string
  /** When false, shows Approve/Reject buttons and emits @approve/@reject events */
  readOnly?: boolean
  /** External requests array for state sync (e.g. from planet-hall) */
  requests?: any[]
  /**
   * BaseCell instance passed by useCellViewProvider.resolveViewSpec().
   * Provides waitForReady() to coordinate data loading with MFE handshake.
   */
  cellInstance?: { waitForReady?: () => Promise<void> }
}

const props = withDefaults(defineProps<Props>(), {
  cell: undefined,
  cellId: undefined,
  readOnly: true,
  requests: undefined,
  cellInstance: undefined,
})

const emit = defineEmits<{
  approve: [requestId: string]
  reject: [requestId: string]
}>()

// ─── Local state ────────────────────────────────────────────────────────────
const requestsApi = useRequestsCell()
const localRequests = ref<any[]>([])
const localIsLoading = ref(false)
const localError = ref<string | null>(null)
const localActionInProgress = ref<string | null>(null)

// ─── Display computed ──────────────────────────────────────────────────────
// Priority: external requests (prop sync) > local requests (self-loaded)
const displayRequests = computed(() => {
  if (props.requests) return props.requests
  return localRequests.value
})

// ─── Data loading ──────────────────────────────────────────────────────────

async function loadData() {
  localIsLoading.value = true
  localError.value = null
  await requestsApi.loadRequests()
  localRequests.value = [...requestsApi.requests.value]
  if (requestsApi.error.value) {
    localError.value = requestsApi.error.value
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
  // Load own i18n translations for $t('requestsCell.*') keys
  loadCellI18n('requests-cell')
  // Only self-load if no external requests provided
  if (!props.requests) {
    // Wait for MFE handshake before making authenticated requests.
    // If handshake already completed, waitForReady() resolves immediately.
    // cellInstance is passed as a prop by useCellViewProvider.resolveViewSpec()
    ;(async () => {
      if (props.cellInstance?.waitForReady) {
        await props.cellInstance.waitForReady()
      }
      loadData()
    })()
  }
})
</script>

<style scoped>
.requests-cell {
  background-color: var(--color-surface, #ffffff);
}
</style>
