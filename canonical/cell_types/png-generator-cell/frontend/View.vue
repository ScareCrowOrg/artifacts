/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-01-15",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-01-15",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div class="png-generator-cell bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg p-4 shadow-sm">
    <div class="cell-header mb-4">
      <h3 class="text-lg font-semibold text-primary dark:text-primary-light">
        {{ $t('pngGeneratorCell.title') }}
      </h3>
      <p class="text-sm text-text-secondary dark:text-text-secondary-dark mt-1">
        {{ $t('pngGeneratorCell.description') }}
      </p>
    </div>

    <div class="cell-content space-y-4">
      <!-- 3D Asset Mode Toggle -->
      <div class="asset-3d-mode-section flex items-center gap-3 p-3 bg-surface-light dark:bg-surface-dark-light border border-border dark:border-border-dark rounded">
        <input
          id="asset3dMode"
          v-model="localAsset3dMode"
          type="checkbox"
          :disabled="localIsGenerating"
          class="w-5 h-5 rounded border-border dark:border-border-dark text-primary focus:ring-2 focus:ring-primary"
        />
        <label for="asset3dMode" class="flex-1 cursor-pointer">
          <div class="text-sm font-medium text-text-primary dark:text-text-primary-dark">
            {{ $t('pngGeneratorCell.asset3dModeLabel') }}
          </div>
          <div class="text-xs text-text-secondary dark:text-text-secondary-dark mt-1">
            {{ $t('pngGeneratorCell.asset3dModeDescription') }}
          </div>
        </label>
      </div>

      <!-- Prompt Input Section -->
      <div class="prompt-section">
        <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-2">
          {{ $t('pngGeneratorCell.promptLabel') }}
        </label>
        <textarea
          v-model="localPrompt"
          :disabled="localIsGenerating"
          :placeholder="$t('pngGeneratorCell.promptPlaceholder')"
          class="w-full px-3 py-2 border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark rounded focus:outline-none focus:ring-2 focus:ring-primary resize-none"
          rows="3"
          @keydown.ctrl.enter="handleGenerate"
          @keydown.meta.enter="handleGenerate"
        />
      </div>

      <!-- Negative Prompt Input Section -->
      <div class="negative-prompt-section">
        <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-2">
          {{ $t('pngGeneratorCell.negativePromptLabel') }}
          <span class="text-xs text-text-secondary dark:text-text-secondary-dark ml-1">({{ $t('pngGeneratorCell.optional') }})</span>
        </label>
        <textarea
          v-model="localNegativePrompt"
          :disabled="localIsGenerating"
          :placeholder="$t('pngGeneratorCell.negativePromptPlaceholder')"
          class="w-full px-3 py-2 border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark rounded focus:outline-none focus:ring-2 focus:ring-primary resize-none"
          rows="2"
        />
      </div>

      <!-- Generation Parameters -->
      <div class="parameters-section grid grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-1">
            {{ $t('pngGeneratorCell.widthLabel') }}
          </label>
          <input
            v-model.number="localParams.width"
            type="number"
            :disabled="localIsGenerating"
            :min="256"
            :max="1024"
            :step="64"
            class="w-full px-3 py-2 border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark rounded focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-1">
            {{ $t('pngGeneratorCell.heightLabel') }}
          </label>
          <input
            v-model.number="localParams.height"
            type="number"
            :disabled="localIsGenerating"
            :min="256"
            :max="1024"
            :step="64"
            class="w-full px-3 py-2 border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark rounded focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-1">
            {{ $t('pngGeneratorCell.stepsLabel') }}
          </label>
          <input
            v-model.number="localParams.steps"
            type="number"
            :disabled="localIsGenerating"
            :min="10"
            :max="50"
            class="w-full px-3 py-2 border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark rounded focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-1">
            {{ $t('pngGeneratorCell.cfgScaleLabel') }}
          </label>
          <input
            v-model.number="localParams.cfg_scale"
            type="number"
            :disabled="localIsGenerating"
            :min="1"
            :max="20"
            :step="0.5"
            class="w-full px-3 py-2 border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark rounded focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
      </div>

      <!-- Generate Button -->
      <div class="action-section">
        <button
          :disabled="!localPrompt.trim() || localIsGenerating"
          class="px-4 py-2 bg-primary dark:bg-primary-hover text-white rounded hover:bg-primary-hover dark:hover:bg-primary-light transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          @click="handleGenerate"
        >
          <svg
            v-if="localIsGenerating"
            class="animate-spin h-5 w-5"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <span>{{ localIsGenerating ? $t('pngGeneratorCell.generating') : $t('pngGeneratorCell.generateButton') }}</span>
        </button>
      </div>
      <div v-if="localError" class="error-section p-3 bg-error-light dark:bg-error-dark text-error-dark dark:text-error-light rounded border border-error">
        <p class="text-sm">{{ localError }}</p>
      </div>

      <!-- Job History Section (substitui preview inline) -->
      <div class="job-history-section mt-4">
        <h4 class="text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-2">
          {{ $t('pngGeneratorCell.recentJobs') }}
        </h4>

        <!-- Loading -->
        <div v-if="localJobsLoading" class="text-center py-4">
          <svg class="animate-spin h-5 w-5 text-primary mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        </div>

        <!-- Empty state -->
        <div v-else-if="localRecentJobs.length === 0" class="text-center py-6 text-text-secondary dark:text-text-secondary-dark text-sm">
          {{ $t('pngGeneratorCell.noRecentJobs') }}
        </div>

        <!-- Job list -->
        <div v-else class="space-y-1">
          <div v-for="job in localRecentJobs" :key="job.id || job.job_id"
               class="flex items-center gap-2 py-1.5 px-2 rounded text-xs hover:bg-surface-light dark:hover:bg-surface-dark-light">
            <!-- Status indicator -->
            <span v-if="job.status === 'processing' || job.status === 'queued'"
                  class="w-2 h-2 rounded-full bg-blue-500 animate-pulse inline-block"></span>
            <span v-else-if="job.status === 'success' || job.status === 'completed'"
                  class="w-2 h-2 rounded-full bg-green-500 inline-block"></span>
            <span v-else-if="job.status === 'failed'"
                  class="w-2 h-2 rounded-full bg-red-500 inline-block"></span>
            <span v-else class="w-2 h-2 rounded-full bg-gray-400 inline-block"></span>

            <!-- Status text -->
            <span class="text-text-secondary min-w-[60px]">{{ job.status }}</span>

            <!-- Date -->
            <span class="text-text-secondary font-mono">{{ formatJobDate(job.enqueued_at) }}</span>

            <!-- Completed job → link to Job Manager -->
            <span v-if="(job.status === 'success' || job.status === 'completed') && (job.relative_url || job.content_id)"
                  class="ml-auto text-primary hover:underline cursor-pointer" @click="openJobManager">
              {{ $t('pngGeneratorCell.viewResult') }}
            </span>
          </div>
        </div>

        <!-- Open full Job Manager -->
        <button v-if="cellFactory && localRecentJobs.length > 0"
                @click="openJobManager"
                class="mt-3 text-xs text-primary hover:underline">
          {{ $t('pngGeneratorCell.viewAllJobs') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted, onUnmounted, inject } from 'vue'
import { createLogger } from '@/utils/logger'
import { PngGeneratorCell } from './PngGeneratorCell'
import type { PngGeneratorInput } from './PngGeneratorCell'
import { CELL_FACTORY_KEY, type CellFactory } from '#canonical/shared/cellFactory'
import { useJobPolling } from '#shared/composables/useJobPolling'
import apiService from '@/services/apiService.js'

const logger = createLogger('component:png-generator-cell')

// Initialize PngGeneratorCell instance
const cellInstance = new PngGeneratorCell()

// Props
interface CellObject {
  id?: string
  cellId?: string
  initial_data?: {
    prompt?: string
    generatedPng?: string | null
    isGenerating?: boolean
    error?: string | null
    negativePrompt?: string
    asset3dMode?: boolean
    generationParams?: {
      width: number
      height: number
      steps: number
      cfg_scale: number
      seed: number
    }
  }
  data?: any  // Legacy support
}

interface Props {
  cell?: CellObject  // Cell object from DynamicCellView (contains id, initial_data, etc.)
  cellId?: string    // Optional direct cellId (for backward compatibility)
  prompt?: string
  generatedPng?: string | null
  isGenerating?: boolean
  error?: string | null
  negativePrompt?: string
  asset3dMode?: boolean
  generationParams?: {
    width: number
    height: number
    steps: number
    cfg_scale: number
    seed: number
  }
}

const props = withDefaults(defineProps<Props>(), {
  cell: undefined,
  cellId: undefined,
  prompt: '',
  generatedPng: null,
  isGenerating: false,
  error: null,
  negativePrompt: '',
  asset3dMode: false,
  generationParams: () => ({
    width: 1024,
    height: 1024,
    steps: 20,
    cfg_scale: 7.0,
    seed: -1
  })
})

// Computed: Extract cell ID from cell object or direct prop
const effectiveCellId = computed(() => {
  return props.cellId || props.cell?.id || props.cell?.cellId || 'unknown'
})

// Computed: Extract initial data from cell object
// NOTE: Supports both initial_data (primary) and data (legacy) properties
// Priority: cell.initial_data > cell.data > empty object
const initialData = computed(() => {
  return props.cell?.initial_data || props.cell?.data || {}
})

// Emits
const emit = defineEmits<{
  (e: 'update:cell', value: any): void
  (e: 'update:prompt', value: string): void
  (e: 'update:isGenerating', value: boolean): void
  (e: 'update:error', value: string | null): void
  (e: 'update:negativePrompt', value: string): void
  (e: 'update:asset3dMode', value: boolean): void
  (e: 'update:generationParams', value: any): void
  (e: 'generate', params: any): void
}>()

// Default generation parameters
const DEFAULT_GENERATION_PARAMS = {
  width: 1024,
  height: 1024,
  steps: 20,
  cfg_scale: 7.0,
  seed: -1
}

// Local state - Initialize from props or initial_data
const localPrompt = ref(props.prompt || initialData.value.prompt || '')
const localIsGenerating = ref(props.isGenerating || initialData.value.isGenerating || false)
const localError = ref(props.error || initialData.value.error || null)
const localNegativePrompt = ref(props.negativePrompt || initialData.value.negativePrompt || '')
const localAsset3dMode = ref(props.asset3dMode || initialData.value.asset3dMode || false)
const localParams = ref({
  ...DEFAULT_GENERATION_PARAMS,
  ...(initialData.value.generationParams || {}),
  ...props.generationParams
})

// Job history state
const localRecentJobs = ref<any[]>([])
const localJobsLoading = ref(false)

// Job polling state (async flow v6.0)
const localJobId = ref<string | null>(null)
const {
  jobStatus: pollingJobStatus,
  startPolling,
  stopPolling,
} = useJobPolling(
  async (path: string, options?: RequestInit) => {
    return apiService.fetch(path, options) as Promise<Response>
  }
)

// Stop polling on unmount
onUnmounted(() => {
  stopPolling()
})

// Inject CellFactory for creating child cells (job-manager-cell)
const cellFactory = inject<CellFactory>(CELL_FACTORY_KEY)

// Watch for prop changes
watch(() => props.prompt, (newVal) => { if (newVal !== undefined) localPrompt.value = newVal })
watch(() => props.isGenerating, (newVal) => { if (newVal !== undefined) localIsGenerating.value = newVal })
watch(() => props.error, (newVal) => { if (newVal !== undefined) localError.value = newVal })
watch(() => props.negativePrompt, (newVal) => { if (newVal !== undefined) localNegativePrompt.value = newVal })
watch(() => props.asset3dMode, (newVal) => { if (newVal !== undefined) localAsset3dMode.value = newVal })
watch(() => props.generationParams, (newVal) => { if (newVal) localParams.value = { ...newVal } }, { deep: true })

// Watch for initial_data changes from cell object
watch(() => props.cell?.initial_data, (newVal) => {
  if (newVal) {
    if (newVal.prompt !== undefined) localPrompt.value = newVal.prompt
    if (newVal.isGenerating !== undefined) localIsGenerating.value = newVal.isGenerating
    if (newVal.error !== undefined) localError.value = newVal.error
    if (newVal.negativePrompt !== undefined) localNegativePrompt.value = newVal.negativePrompt
    if (newVal.asset3dMode !== undefined) localAsset3dMode.value = newVal.asset3dMode
    if (newVal.generationParams) localParams.value = { ...localParams.value, ...newVal.generationParams }
  }
}, { deep: true })

// Watch for local changes and emit updates (update cell object)
// Use debounced updates to prevent excessive emit calls
let updateTimeout: ReturnType<typeof setTimeout> | null = null
watch([localPrompt, localIsGenerating, localError, localNegativePrompt, localAsset3dMode, localParams], () => {
  // Debounce updates to avoid excessive emit calls (waits for 100ms of inactivity)
  if (updateTimeout) {
    clearTimeout(updateTimeout)
  }

  updateTimeout = setTimeout(() => {
    if (props.cell) {
      emit('update:cell', {
        ...props.cell,
        initial_data: {
          ...props.cell.initial_data,
          prompt: localPrompt.value,
          isGenerating: localIsGenerating.value,
          error: localError.value,
          negativePrompt: localNegativePrompt.value,
          asset3dMode: localAsset3dMode.value,
          generationParams: localParams.value
        }
      })
    }

    // Also emit individual updates for backward compatibility
    emit('update:prompt', localPrompt.value)
    emit('update:isGenerating', localIsGenerating.value)
    emit('update:error', localError.value)
    emit('update:negativePrompt', localNegativePrompt.value)
    emit('update:asset3dMode', localAsset3dMode.value)
    emit('update:generationParams', localParams.value)
  }, 100) // 100ms debounce
}, { deep: true })

// Fetch recent jobs from backend
const fetchRecentJobs = async () => {
  localJobsLoading.value = true
  try {
    const response = await apiService.fetch(
      '/api/cells/jobs?job_type=comfyui_generate&limit=10',
      { method: 'GET' }
    )
    const data = await response.json()
    const now = Date.now()
    const TWENTY_FOUR_HOURS = 24 * 60 * 60 * 1000
    localRecentJobs.value = (data.jobs || []).filter((job: any) => {
      const enqueuedAt = new Date(job.enqueued_at || job.created_at).getTime()
      return (now - enqueuedAt) < TWENTY_FOUR_HOURS
    })
  } catch (err: any) {
    logger.error('Failed to fetch recent jobs', { error: err.message })
    // Graceful fallback: don't show error, just hide the section
    localRecentJobs.value = []
  } finally {
    localJobsLoading.value = false
  }
}

// Open Job Manager Cell contextualized for PNG jobs
const openJobManager = async () => {
  if (!cellFactory) return
  try {
    await cellFactory.addChildCell('job-manager-cell', {
      job_type_filter: 'comfyui_generate',
    })
    logger.info('Job Manager Cell created from PNG Generator')
  } catch (err: any) {
    logger.warn('Failed to open Job Manager', { error: err.message })
  }
}

// Format date for compact display
const formatJobDate = (dateStr?: string): string => {
  if (!dateStr) return '—'
  try {
    const d = new Date(dateStr)
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return dateStr.substring(0, 10)
  }
}

// Methods
const handleGenerate = async () => {
  if (!localPrompt.value.trim() || localIsGenerating.value) {
    return
  }

  logger.info('Generating PNG image via BaseCell', {
    prompt: localPrompt.value,
    cellId: effectiveCellId.value
  })

  // Emit generate event for backward compatibility
  emit('generate', {
    prompt: localPrompt.value,
    negativePrompt: localNegativePrompt.value,
    asset3dMode: localAsset3dMode.value,
    generationParams: localParams.value
  })

  localIsGenerating.value = true
  localError.value = null

  try {
    // Validate input using cell's validate method
    const input: PngGeneratorInput = {
      action: 'generate',
      prompt: localPrompt.value,
      negativePrompt: localNegativePrompt.value,
      asset3dMode: localAsset3dMode.value,
      generationParams: localParams.value
    }

    const validationErrors = cellInstance.validate(input)

    if (validationErrors.length > 0) {
      const errorMessages = validationErrors.map(e => `${e.field}: ${e.message}`).join(', ')
      throw new Error(`Validation failed: ${errorMessages}`)
    }

    // Execute using cell instance
    const result = await cellInstance.execute(input)

    logger.info('PNG generation completed', {
      success: result.success,
      jobId: result.output?.job_id,
      executionTime: result.execution_time
    })

    if (result.success && result.output) {
      const output = result.output as any

      // ASYNC FLOW (v6.0): Backend returned job_id — start polling
      if (output.job_id) {
        localJobId.value = output.job_id
        logger.info('Starting job polling for job_id=' + output.job_id)
        startPolling(output.job_id, {
          intervalMs: 2000,
          onComplete: async (job) => {
            logger.info('Job completed, refreshing job list', { job })
            localIsGenerating.value = false

            // Refresh the recent jobs list to show the completed job
            await fetchRecentJobs()
          },
          onError: (err) => {
            logger.error('Job failed', { error: err })
            localError.value = err
            localIsGenerating.value = false
          },
        })
        return  // Polling handles the rest
      }

      // SYNC FLOW (legacy): Backend returned content directly
      if (output.generatedPng) {
        logger.info('Sync generation completed')
      } else {
        throw new Error('No image data in response')
      }

      localError.value = null

      // Refresh recent jobs after sync generation as well
      await fetchRecentJobs()
    } else {
      throw new Error(result.error || 'Generation failed')
    }
  } catch (error: any) {
    logger.error('PNG generation failed', { error: error.message })
    localError.value = error.message || 'Failed to generate image'
  } finally {
    // Only reset isGenerating if not in async polling flow
    if (!localJobId.value) {
      localIsGenerating.value = false
    }
  }
}

// Check cell health and load recent jobs on mount
onMounted(async () => {
  logger.debug('PNG Generator Cell mounted to DOM')

  logger.debug('PNG Generator Cell mounted', {
    cellId: effectiveCellId.value,
    hasCell: !!props.cell,
    hasCellId: !!props.cellId
  })

  // Perform health check
  try {
    const health = await cellInstance.health_check()
    if (health.status !== 'healthy') {
      logger.warn('Cell health check warning', {
        status: health.status,
        reason: health.reason
      })
    } else {
      logger.debug('Cell health check passed')
    }
  } catch (error: any) {
    logger.error('Cell health check failed', { error: error.message })
  }

  // Fetch recent PNG jobs
  await fetchRecentJobs()
})

// HandleGenerate is no longer responsible for creating auto-viewers or managing preview state
</script>

<style scoped>
.png-generator-cell {
  /* Additional component-specific styles if needed */
}
</style>
