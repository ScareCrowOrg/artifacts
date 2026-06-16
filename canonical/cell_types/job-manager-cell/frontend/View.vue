<template>
  <div class="job-manager-cell bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg p-4 shadow-sm">
    <!-- Embedded Mode: Single Job Progress -->
    <div v-if="isEmbedded && localJobId" class="embedded-mode">
      <div class="flex items-center gap-3 mb-2">
        <svg
          v-if="!isTerminal"
          class="animate-spin h-5 w-5 text-primary"
          xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
        >
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        <svg
          v-else-if="localJobStatus === 'success' || localJobStatus === 'completed'"
          class="h-5 w-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
        </svg>
        <svg
          v-else
          class="h-5 w-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
        <div class="flex-1">
          <div class="text-sm font-medium text-text-primary dark:text-text-primary-dark">
            {{ $t('jobManagerCell.jobStatus', { status: localJobStatus }) }}
          </div>
          <div class="text-xs text-text-secondary dark:text-text-secondary-dark mt-0.5">
            {{ $t('jobManagerCell.jobId', { id: localJobId.substring(0, 8) + '...' }) }}
          </div>
        </div>
      </div>

      <!-- Progress bar (non-terminal states) -->
      <div v-if="!isTerminal" class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
        <div class="bg-primary h-2 rounded-full animate-pulse" style="width: 60%"></div>
      </div>

      <!-- Error message -->
      <div v-if="localError" class="mt-2 text-sm text-red-600 dark:text-red-400">
        {{ localError }}
      </div>
    </div>

    <!-- Standalone Mode: Job List -->
    <div v-else class="standalone-mode">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-primary dark:text-primary-light">
          {{ $t('jobManagerCell.title') }}
        </h3>
        <div class="flex gap-2">
          <select
            v-model="localStatusFilter"
            class="text-sm px-2 py-1 border border-border dark:border-border-dark bg-surface dark:bg-surface-dark rounded"
          >
            <option value="">{{ $t('jobManagerCell.allStatuses') }}</option>
            <option value="queued">{{ $t('jobManagerCell.statusQueued') }}</option>
            <option value="processing">{{ $t('jobManagerCell.statusProcessing') }}</option>
            <option value="success">{{ $t('jobManagerCell.statusSuccess') }}</option>
            <option value="failed">{{ $t('jobManagerCell.statusFailed') }}</option>
            <option value="cancelled">{{ $t('jobManagerCell.statusCancelled') }}</option>
            <option value="archived">{{ $t('jobManagerCell.statusArchived') }}</option>
          </select>
          <select
            v-model="localJobTypeFilter"
            class="text-sm px-2 py-1 border border-border dark:border-border-dark bg-surface dark:bg-surface-dark rounded"
          >
            <option value="">{{ $t('jobManagerCell.allTypes') }}</option>
            <option v-if="jobTypeOptions" v-for="type in jobTypeOptions" :key="type" :value="type">
              {{ type }}
            </option>
          </select>
          <button
            @click="refreshJobs"
            class="px-3 py-1 text-sm bg-primary text-white rounded hover:bg-primary-hover transition"
          >
            {{ $t('jobManagerCell.refresh') }}
          </button>
        </div>
      </div>

      <!-- Loading indicator -->
      <div v-if="isLoading" class="text-center py-4">
        <svg class="animate-spin h-6 w-6 text-primary mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      </div>

      <!-- Empty state -->
      <div v-else-if="localJobs.length === 0" class="text-center py-8 text-text-secondary dark:text-text-secondary-dark">
        <p>{{ $t('jobManagerCell.noJobs') }}</p>
      </div>

      <!-- Job list table -->
      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-text-secondary dark:text-text-secondary-dark border-b border-border dark:border-border-dark">
              <th class="pb-2 pr-3">{{ $t('jobManagerCell.type') }}</th>
              <th class="pb-2 pr-3">{{ $t('jobManagerCell.status') }}</th>
              <th class="pb-2 pr-3">{{ $t('jobManagerCell.planet') }}</th>
              <th class="pb-2 pr-3">{{ $t('jobManagerCell.created') }}</th>
              <th class="pb-2 pr-3">{{ $t('jobManagerCell.result') }}</th>
              <th class="pb-2">{{ $t('jobManagerCell.actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="job in localJobs"
              :key="job.id || job.job_id"
              class="border-b border-border dark:border-border-dark hover:bg-surface-light dark:hover:bg-surface-dark-light"
            >
              <td class="py-2 pr-3 text-text-primary dark:text-text-primary-dark font-mono text-xs">
                {{ job.type || job.cell_type || '—' }}
              </td>
              <td class="py-2 pr-3">
                <span
                  class="inline-block px-2 py-0.5 text-xs rounded"
                  :class="statusClass(job.status)"
                >
                  {{ job.status }}
                </span>
              </td>
              <td class="py-2 pr-3 text-text-secondary dark:text-text-secondary-dark text-xs">
                <span :title="job.planet_id || ''">
                  {{ job.planet_id || '—' }}
                </span>
              </td>
              <td class="py-2 pr-3 text-text-secondary dark:text-text-secondary-dark text-xs">
                {{ formatDate(job.enqueued_at) }}
              </td>
              <td class="py-2 text-xs">
                <span v-if="job.status === 'success' || job.status === 'completed'" class="text-green-600 dark:text-green-400">
                  {{ job.content_id ? '✓ Persisted' : job.relative_url ? '✓ File' : '✓ Done' }}
                </span>
                <span v-else-if="job.status === 'failed'" class="text-red-600 dark:text-red-400" :title="job.error_message">
                  {{ job.error_message ? job.error_message.substring(0, 40) + '...' : 'Failed' }}
                </span>
                <span v-else-if="job.status === 'cancelled'" class="text-gray-500 dark:text-gray-400">
                  {{ $t('jobManagerCell.statusCancelled') }}
                </span>
                <span v-else class="text-text-secondary dark:text-text-secondary-dark">
                  {{ job.status }}
                </span>
              </td>
              <td class="py-2 text-xs whitespace-nowrap">
                <!-- Result View Link — abre no workspace (so visivel dentro do Dynamic Workspace) -->
                <button
                  v-if="cellFactory && job.status === 'success' && (job.content_id || job.relative_url)"
                  @click="handleViewResult(job)"
                  class="inline-block mr-2 px-2 py-1 text-xs bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300 rounded hover:bg-green-200 dark:hover:bg-green-800"
                >
                  {{ $t('jobManagerCell.viewResult') }}
                </button>

                <!-- Archive button (final status only, not already archived) -->
                <button
                  v-if="(job.status === 'success' || job.status === 'failed' || job.status === 'cancelled') && localStatusFilter !== 'archived' && !isActionLoading(job.id || job.job_id)"
                  @click="handleArchive(job)"
                  class="inline-block mr-1 px-2 py-1 text-xs bg-purple-500 text-white rounded hover:bg-purple-600 disabled:opacity-50"
                >
                  Archive
                </button>

                <!-- Cancel button -->
                <button
                  v-if="(job.status === 'queued' || job.status === 'processing') && !isActionLoading(job.id || job.job_id)"
                  @click="handleCancel(job)"
                  class="inline-block mr-1 px-2 py-1 text-xs bg-yellow-500 text-white rounded hover:bg-yellow-600 disabled:opacity-50"
                >
                  {{ $t('jobManagerCell.cancel') }}
                </button>

                <!-- Retry button (failed, cancelled, or stuck queued) -->
                <button
                  v-if="(job.status === 'failed' || job.status === 'cancelled' || job.status === 'queued') && !isActionLoading(job.id || job.job_id)"
                  @click="handleRetry(job)"
                  class="inline-block mr-1 px-2 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
                >
                  {{ $t('jobManagerCell.retry') }}
                </button>

                <!-- Loading spinner for in-progress actions -->
                <span
                  v-if="isActionLoading(job.id || job.job_id)"
                  class="inline-flex items-center gap-1 text-text-secondary dark:text-text-secondary-dark"
                >
                  <svg class="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                </span>

                <!-- Empty state: no actions available -->
                <span
                  v-if="!job.content_id && !job.relative_url && job.status !== 'queued' && job.status !== 'processing' && job.status !== 'failed' && job.status !== 'cancelled' && !isActionLoading(job.id || job.job_id)"
                  class="text-text-secondary dark:text-text-secondary-dark"
                >—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Confirmation Modal -->
    <ConfirmModal
      :visible="confirmModal.visible"
      :title="confirmModal.title"
      :message="confirmModal.message"
      :danger="confirmModal.danger"
      :loading="confirmModal.loading"
      @confirm="onConfirmModalConfirm"
      @cancel="onConfirmModalCancel"
    />

    <!-- Toast notification -->
    <div
      v-if="toastMessage"
      class="fixed bottom-4 right-4 z-50 px-4 py-2 rounded shadow-lg text-sm text-white transition-opacity duration-300"
      :class="toastType === 'success' ? 'bg-green-600' : 'bg-red-600'"
    >
      {{ toastMessage }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted, onUnmounted, reactive, inject } from 'vue'
import { createLogger } from '@/utils/logger'
import { JobManagerCell } from './JobManagerCell'
import type { JobRecord } from './JobManagerCell'
import ConfirmModal from '#artifacts/shared/components/ConfirmModal.vue'
import { CELL_FACTORY_KEY, type CellFactory } from '#artifacts/canonical/shared/cellFactory'

const logger = createLogger('component:job-manager-cell')

const cellInstance = new JobManagerCell()

// Inject CellFactory for opening content in child cells (null if outside workspace)
const cellFactory = inject<CellFactory | null>(CELL_FACTORY_KEY, null)

interface Props {
  cell?: any
  jobId?: string
  jobTypeFilter?: string
  jobTypeOptions?: string[]
  userFilter?: string
  maxItems?: number
  pollIntervalMs?: number
  embedded?: boolean
  status?: string
}

const props = withDefaults(defineProps<Props>(), {
  cell: undefined,
  jobId: undefined,
  jobTypeFilter: undefined,
  jobTypeOptions: undefined,
  userFilter: undefined,
  maxItems: 10,
  pollIntervalMs: 2000,
  embedded: false,
  status: undefined,
})

const emit = defineEmits<{
  (e: 'update:jobId', value: string | null): void
  (e: 'update:status', value: string): void
  (e: 'complete', job: JobRecord): void
  (e: 'error', err: string): void
}>()

const initialData = computed(() => props.cell?.initial_data || {})

// Toast notification state
const toastMessage = ref<string | null>(null)
const toastType = ref<'success' | 'error'>('success')
let toastTimer: ReturnType<typeof setTimeout> | null = null

function showToast(message: string, type: 'success' | 'error' = 'success') {
  toastMessage.value = message
  toastType.value = type
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastMessage.value = null
  }, 3000)
}

// Per-job loading state (keyed by job ID)
const actionLoading = reactive<Record<string, boolean>>({})

function isActionLoading(jobId: string | undefined): boolean {
  return jobId ? !!actionLoading[jobId] : false
}

function setActionLoading(jobId: string | undefined, loading: boolean) {
  if (jobId) {
    actionLoading[jobId] = loading
  }
}

// ── Confirm Modal State ──
const confirmModal = reactive({
  visible: false,
  title: '',
  message: '',
  danger: false,
  loading: false,
  resolve: null as ((value: boolean) => void) | null,
})

function showConfirm(title: string, message: string, danger = false): Promise<boolean> {
  return new Promise((resolve) => {
    confirmModal.title = title
    confirmModal.message = message
    confirmModal.danger = danger
    confirmModal.visible = true
    confirmModal.loading = false
    confirmModal.resolve = resolve
  })
}

function onConfirmModalConfirm() {
  confirmModal.visible = false
  confirmModal.resolve?.(true)
}

function onConfirmModalCancel() {
  confirmModal.visible = false
  confirmModal.resolve?.(false)
}

/**
 * Open the job result in an ImageContentCell inside the workspace.
 * So visivel quando cellFactory esta disponivel (dentro do Dynamic Workspace).
 */
async function handleViewResult(job: JobRecord) {
  const jobId = job.id || job.job_id
  if (!jobId || !cellFactory) return

  try {
      logger.debug('DIAG [handleViewResult] Opening ImageContentCell: job_id=%s, content_id=%s, relative_url=%s',
        jobId,
        job.content_id || 'undefined',
        job.relative_url || 'undefined',
      )
    await cellFactory.addChildCell('image-content-cell', {
      content_id: job.content_id || undefined,
      relative_url: job.relative_url || undefined,
    })
  } catch (err: any) {
    logger.error('[%s] Failed to open ImageContentCell: %s', jobId, err)
  }
}

/**
 * Confirm modal then cancel the job.
 */
async function handleCancel(job: JobRecord) {
  const jobId = job.id || job.job_id
  if (!jobId) return

  const confirmed = await showConfirm(
    'Cancel Job',
    `Cancel job ${jobId.substring(0, 8)}...? This will stop the job and mark it as cancelled.`,
    false,
  )
  if (!confirmed) return

  setActionLoading(jobId, true)
  try {
    const result = await cellInstance.cancelJob(jobId)
    if (result.success) {
      job.status = 'cancelled'
      showToast('Job cancelled', 'success')
    } else {
      showToast(result.error || 'Failed to cancel job', 'error')
    }
  } catch (err: any) {
    showToast(err.message || 'Failed to cancel job', 'error')
  } finally {
    setActionLoading(jobId, false)
  }
}

/**
 * Confirm modal then retry the job.
 */
async function handleRetry(job: JobRecord) {
  const jobId = job.id || job.job_id
  if (!jobId) return

  const confirmed = await showConfirm(
    'Retry Job',
    `Re-enqueue job ${jobId.substring(0, 8)}...? The job will be reprocessed with its original payload.`,
    false,
  )
  if (!confirmed) return

  setActionLoading(jobId, true)
  try {
    const result = await cellInstance.retryJob(jobId)
    if (result.success) {
      job.status = 'queued'
      showToast('Job re-enqueued', 'success')
    } else {
      showToast(result.error || 'Failed to retry job', 'error')
    }
  } catch (err: any) {
    showToast(err.message || 'Failed to retry job', 'error')
  } finally {
    setActionLoading(jobId, false)
  }
}

/**
 * Confirm modal then archive the job.
 * On success, removes the job from the active list.
 */
async function handleArchive(job: JobRecord) {
  const jobId = job.id || job.job_id
  if (!jobId) return

  const confirmed = await showConfirm(
    'Archive Job',
    `Archive job ${jobId.substring(0, 8)}...? The job will be moved to the archive and removed from the active list.`,
    false,
  )
  if (!confirmed) return

  setActionLoading(jobId, true)
  try {
    const result = await cellInstance.archiveJob(jobId)
    if (result.success) {
      // Remove from local list (it's now archived)
      localJobs.value = localJobs.value.filter(j => (j.id || j.job_id) !== jobId)
      showToast('Job archived', 'success')
    } else {
      showToast(result.error || 'Failed to archive job', 'error')
    }
  } catch (err: any) {
    showToast(err.message || 'Failed to archive job', 'error')
  } finally {
    setActionLoading(jobId, false)
  }
}

// Local state
const isEmbedded = computed(() => props.embedded || !!initialData.value.embedded || !!props.jobId)
const localJobId = ref<string | null>(props.jobId || initialData.value.job_id || null)
const localJobStatus = ref<string>('idle')
const localError = ref<string | null>(null)
const isLoading = ref(false)
const localJobs = ref<JobRecord[]>([])
const localStatusFilter = ref(props.status || initialData.value.status || '')
const localJobTypeFilter = ref<string>(props.jobTypeFilter || initialData.value.job_type_filter || '')
const isTerminal = computed(() =>
  ['success', 'completed', 'failed', 'error', 'not_found'].includes(localJobStatus.value)
)

// Standalone: fetch job list
async function refreshJobs() {
  isLoading.value = true
  try {
    if (localStatusFilter.value === 'archived') {
      const result = await cellInstance.listArchivedJobs({
        job_type: localJobTypeFilter.value || undefined,
        limit: props.maxItems || initialData.value.max_items || 10,
      })
      if (result.success && result.output) {
        const data = result.output as any
        localJobs.value = data.jobs || []
      }
    } else {
      const result = await cellInstance.execute({
        status: localStatusFilter.value || undefined,
        job_type: localJobTypeFilter.value || undefined,
        max_items: props.maxItems || initialData.value.max_items || 10,
      })
      if (result.success && result.output) {
        const data = result.output as any
        localJobs.value = data.jobs || []
      }
    }
  } catch (err: any) {
    logger.error('Failed to refresh jobs', err)
  } finally {
    isLoading.value = false  }
}

// Embedded: start polling
let pollTimer: ReturnType<typeof setInterval> | null = null

function startEmbeddedPolling() {
  if (!localJobId.value) return

  pollTimer = setInterval(async () => {
    try {
      const result = await cellInstance.execute({ job_id: localJobId.value })
      if (result.success && result.output) {
        const job = result.output as JobRecord
        localJobStatus.value = job.status

        if (isTerminal.value) {
          stopEmbeddedPolling()
          if (job.status === 'success' || job.status === 'completed') {
            emit('complete', job)
          } else {
            emit('error', job.error_message || 'Job failed')
          }
        }
      }
    } catch (err: any) {
      localError.value = err.message
      stopEmbeddedPolling()
      emit('error', err.message)
    }
  }, props.pollIntervalMs || 2000)
}

function stopEmbeddedPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function statusClass(status: string): string {
  switch (status) {
    case 'queued':
    case 'processing':
      return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
    case 'success':
    case 'completed':
      return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
    case 'failed':
    case 'error':
      return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
    default:
      return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
  }
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return '—'
  try {
    const d = new Date(dateStr)
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return dateStr.substring(0, 10)
  }
}

// Watch for status filter changes
watch(localStatusFilter, () => {
  refreshJobs()
})

// Watch for job type filter changes
watch(localJobTypeFilter, () => {
  refreshJobs()
})

// Lifecycle
onMounted(() => {
  if (isEmbedded.value && localJobId.value) {
    localJobStatus.value = 'processing'
    startEmbeddedPolling()
  } else if (!isEmbedded.value) {
    refreshJobs()
  }
})

onUnmounted(() => {
  stopEmbeddedPolling()
})
</script>

<style scoped>
.job-manager-cell {
  /* Component-specific styles */
}
</style>
