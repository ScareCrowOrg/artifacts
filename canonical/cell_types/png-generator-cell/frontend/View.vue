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

      <!-- Preview Section -->
      <div v-if="localGeneratedPng" class="preview-section">
        <div class="flex items-center justify-between mb-2">
          <h4 class="text-sm font-medium text-text-secondary dark:text-text-secondary-dark">
            {{ $t('pngGeneratorCell.preview') }}
          </h4>
          <div class="flex gap-2">
            <button
              @click="handleCleanBackground"
              :disabled="isProcessingBackground"
              class="px-3 py-1 text-sm bg-primary dark:bg-primary-hover text-white rounded hover:bg-primary-light dark:hover:bg-primary transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
              :title="$t('pngGeneratorCell.cleanBackground')"
            >
              <svg
                v-if="isProcessingBackground"
                class="animate-spin h-4 w-4"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span>{{ isProcessingBackground ? $t('pngGeneratorCell.processing') : $t('pngGeneratorCell.cleanBackground') }}</span>
            </button>
          </div>
        </div>
        <div class="preview-container bg-white dark:bg-gray-800 border border-border dark:border-border-dark rounded p-4 flex items-center justify-center min-h-[300px]">
          <img
            :src="localGeneratedPng"
            alt="Generated PNG"
            class="max-w-full max-h-[500px] object-contain"
          />
        </div>
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
  (e: 'update:generatedPng', value: string | null): void
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
const localGeneratedPng = ref(props.generatedPng || initialData.value.generatedPng || null)
const localRelativeUrl = ref<string | null>(null)
const localContentId = ref<string | null>(null)
const localIsGenerating = ref(props.isGenerating || initialData.value.isGenerating || false)
const localError = ref(props.error || initialData.value.error || null)
const localNegativePrompt = ref(props.negativePrompt || initialData.value.negativePrompt || '')
const localAsset3dMode = ref(props.asset3dMode || initialData.value.asset3dMode || false)
const localParams = ref({
  ...DEFAULT_GENERATION_PARAMS,
  ...(initialData.value.generationParams || {}),
  ...props.generationParams
})

// Background removal state
const isProcessingBackground = ref(false)

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

// Inject CellFactory for creating child cells (image-content-cell)
const cellFactory = inject<CellFactory>(CELL_FACTORY_KEY)

// Watch for prop changes
watch(() => props.prompt, (newVal) => { if (newVal !== undefined) localPrompt.value = newVal })
watch(() => props.generatedPng, (newVal) => { if (newVal !== undefined) localGeneratedPng.value = newVal })
watch(() => props.isGenerating, (newVal) => { if (newVal !== undefined) localIsGenerating.value = newVal })
watch(() => props.error, (newVal) => { if (newVal !== undefined) localError.value = newVal })
watch(() => props.negativePrompt, (newVal) => { if (newVal !== undefined) localNegativePrompt.value = newVal })
watch(() => props.asset3dMode, (newVal) => { if (newVal !== undefined) localAsset3dMode.value = newVal })
watch(() => props.generationParams, (newVal) => { if (newVal) localParams.value = { ...newVal } }, { deep: true })

// Watch for initial_data changes from cell object
watch(() => props.cell?.initial_data, (newVal) => {
  if (newVal) {
    if (newVal.prompt !== undefined) localPrompt.value = newVal.prompt
    if (newVal.generatedPng !== undefined) localGeneratedPng.value = newVal.generatedPng
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
watch([localPrompt, localGeneratedPng, localIsGenerating, localError, localNegativePrompt, localAsset3dMode, localParams], () => {
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
          generatedPng: localGeneratedPng.value,
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
    emit('update:generatedPng', localGeneratedPng.value)
    emit('update:isGenerating', localIsGenerating.value)
    emit('update:error', localError.value)
    emit('update:negativePrompt', localNegativePrompt.value)
    emit('update:asset3dMode', localAsset3dMode.value)
    emit('update:generationParams', localParams.value)
  }, 100) // 100ms debounce
}, { deep: true })

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
            logger.info('Job completed, processing result', { job })
            localIsGenerating.value = false

            // If result has content reference, create viewer
            if (job.relative_url) {
              localRelativeUrl.value = job.relative_url
              const origin = window.location.origin.replace(/\/+$/, '')
              localGeneratedPng.value = `${origin}/artifacts${job.relative_url}`

              // AUTO-VIEWER: Create Image Content Cell
              if (cellFactory && job.content_id) {
                try {
                  await cellFactory.addChildCell('image-content-cell', {
                    content_id: job.content_id,
                    relative_url: job.relative_url,
                  })
                  logger.info('Image Content Cell auto-created after async job')
                } catch (autoViewError: any) {
                  logger.warn('Auto-viewer creation failed:', { error: autoViewError.message })
                }
              }
            } else if (job.mesh_data) {
              localGeneratedPng.value = job.mesh_data
            }
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
        localGeneratedPng.value = output.generatedPng
      } else {
        throw new Error('No image data in response')
      }

      // Redis Magro: store content reference for auto-viewer
      if (output.relative_url) {
        localRelativeUrl.value = output.relative_url
      }
      if (output.content_id) {
        localContentId.value = output.content_id
      }

      localError.value = null

      // AUTO-VIEWER: Create Image Content Cell automatically after successful generation
      if (cellFactory && (localContentId.value || localRelativeUrl.value)) {
        try {
          await cellFactory.addChildCell('image-content-cell', {
            content_id: localContentId.value,
            relative_url: localRelativeUrl.value,
          })
          logger.info('Image Content Cell auto-created successfully')
        } catch (autoViewError: any) {
          logger.warn('Auto-viewer creation failed (non-blocking):', { error: autoViewError.message })
        }
      } else if (!cellFactory) {
        logger.debug('Auto-viewer: CellFactory not available, skipping')
      }
    } else {
      throw new Error(result.error || 'Generation failed')
    }
  } catch (error: any) {
    logger.error('PNG generation failed', { error: error.message })
    localError.value = error.message || 'Failed to generate image'
    localGeneratedPng.value = null
    localRelativeUrl.value = null
    localContentId.value = null
  } finally {
    // Only reset isGenerating if not in async polling flow
    if (!localJobId.value) {
      localIsGenerating.value = false
    }
  }
}

const handleCleanBackground = async () => {
  if (!localGeneratedPng.value || isProcessingBackground.value) {
    return
  }

  logger.info('Cleaning background from PNG', {
    cellId: effectiveCellId.value
  })

  isProcessingBackground.value = true
  localError.value = null

  try {
    // Validate input using cell's validate method
    const input: PngGeneratorInput = {
      action: 'removeBackground',
      generatedPng: localGeneratedPng.value,
      alpha_matting: true
    }

    const validationErrors = cellInstance.validate(input)

    if (validationErrors.length > 0) {
      const errorMessages = validationErrors.map(e => `${e.field}: ${e.message}`).join(', ')
      throw new Error(`Validation failed: ${errorMessages}`)
    }

    // Execute using cell instance
    const result = await cellInstance.execute(input)

    logger.info('Background removal completed', {
      success: result.success,
      executionTime: result.execution_time
    })

    if (result.success && result.output) {
      const output = result.output as any

      // Extract transparent PNG from result
      if (output.generatedPng) {
        localGeneratedPng.value = output.generatedPng
        localError.value = null
        logger.info('PNG updated with transparent background')
      } else {
        throw new Error('No image data in background removal response')
      }
    } else {
      throw new Error(result.error || 'Background removal failed')
    }
  } catch (error: any) {
    logger.error('Background removal failed', { error: error.message })
    localError.value = error.message || 'Failed to remove background'
  } finally {
    isProcessingBackground.value = false
  }
}

// Check cell health on mount
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
})
</script>

<style scoped>
.png-generator-cell {
  /* Additional component-specific styles if needed */
}
</style>
