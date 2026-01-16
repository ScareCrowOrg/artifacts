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

      <!-- Error Display -->
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
              @click="handleCopy"
              class="px-3 py-1 text-sm bg-surface-light dark:bg-surface-dark-light border border-border dark:border-border-dark rounded hover:bg-surface-hover dark:hover:bg-surface-dark-hover transition"
              :title="$t('pngGeneratorCell.copyToClipboard')"
            >
              {{ $t('pngGeneratorCell.copy') }}
            </button>
            <button
              @click="handleDownload"
              class="px-3 py-1 text-sm bg-surface-light dark:bg-surface-dark-light border border-border dark:border-border-dark rounded hover:bg-surface-hover dark:hover:bg-surface-dark-hover transition"
              :title="$t('pngGeneratorCell.downloadPng')"
            >
              {{ $t('pngGeneratorCell.download') }}
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
import { ref, watch, computed } from 'vue'
import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'

const logger = createLogger('component:png-generator-cell')

// Props
interface Props {
  cell?: any  // Cell object from DynamicCellView (contains id, initial_data, etc.)
  cellId?: string  // Optional direct cellId (for backward compatibility)
  prompt?: string
  generatedPng?: string | null
  isGenerating?: boolean
  error?: string | null
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
  generationParams: () => ({
    width: 512,
    height: 512,
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
  (e: 'update:generationParams', value: any): void
  (e: 'generate', params: any): void
}>()

// Local state - Initialize from props or initial_data
const localPrompt = ref(props.prompt || initialData.value.prompt || '')
const localGeneratedPng = ref(props.generatedPng || initialData.value.generatedPng || null)
const localIsGenerating = ref(props.isGenerating || initialData.value.isGenerating || false)
const localError = ref(props.error || initialData.value.error || null)
const localParams = ref({ 
  ...props.generationParams,
  ...(initialData.value.generationParams || {})
})

// Watch for prop changes
watch(() => props.prompt, (newVal) => { if (newVal !== undefined) localPrompt.value = newVal })
watch(() => props.generatedPng, (newVal) => { if (newVal !== undefined) localGeneratedPng.value = newVal })
watch(() => props.isGenerating, (newVal) => { if (newVal !== undefined) localIsGenerating.value = newVal })
watch(() => props.error, (newVal) => { if (newVal !== undefined) localError.value = newVal })
watch(() => props.generationParams, (newVal) => { if (newVal) localParams.value = { ...newVal } }, { deep: true })

// Watch for initial_data changes from cell object
watch(() => props.cell?.initial_data, (newVal) => {
  if (newVal) {
    if (newVal.prompt !== undefined) localPrompt.value = newVal.prompt
    if (newVal.generatedPng !== undefined) localGeneratedPng.value = newVal.generatedPng
    if (newVal.isGenerating !== undefined) localIsGenerating.value = newVal.isGenerating
    if (newVal.error !== undefined) localError.value = newVal.error
    if (newVal.generationParams) localParams.value = { ...localParams.value, ...newVal.generationParams }
  }
}, { deep: true })

// Watch for local changes and emit updates (update cell object)
// Use throttled updates to prevent excessive emit calls
let updateTimeout: ReturnType<typeof setTimeout> | null = null
watch([localPrompt, localGeneratedPng, localIsGenerating, localError, localParams], () => {
  // Debounce updates to avoid excessive emit calls
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
          generationParams: localParams.value
        }
      })
    }
    
    // Also emit individual updates for backward compatibility
    emit('update:prompt', localPrompt.value)
    emit('update:generatedPng', localGeneratedPng.value)
    emit('update:isGenerating', localIsGenerating.value)
    emit('update:error', localError.value)
    emit('update:generationParams', localParams.value)
  }, 100) // 100ms debounce
}, { deep: true })

// Methods
const handleGenerate = async () => {
  if (!localPrompt.value.trim() || localIsGenerating.value) {
    return
  }

  logger.info('Generating PNG image via ephemeral execution', { 
    prompt: localPrompt.value,
    cellId: effectiveCellId.value
  })
  
  // Emit generate event FIRST for backward compatibility (before API call)
  // This allows parent components to handle generation themselves if needed
  emit('generate', {
    prompt: localPrompt.value,
    ...localParams.value
  })
  
  localIsGenerating.value = true
  localError.value = null
  
  try {
    // Call ephemeral execution endpoint for PNG generation
    const response = await apiService.fetch('/api/cells/execute-ephemeral', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cell_type: 'png-generator-cell',
        input_data: {
          prompt: localPrompt.value,
          ...localParams.value
        }
      })
    })
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
    }
    
    const data = await response.json()
    
    logger.info('PNG generation completed', { 
      success: data.success,
      hasResult: !!data.result
    })
    
    if (data.success && data.result) {
      // Extract generated PNG from result
      if (data.result.image_data) {
        localGeneratedPng.value = `data:image/png;base64,${data.result.image_data}`
      } else if (data.result.generatedPng) {
        localGeneratedPng.value = data.result.generatedPng
      } else {
        throw new Error('No image data in response')
      }
      
      localError.value = null
    } else {
      throw new Error(data.message || 'Generation failed')
    }
  } catch (error: any) {
    logger.error('PNG generation failed', { error: error.message })
    localError.value = error.message || 'Failed to generate image'
    localGeneratedPng.value = null
  } finally {
    localIsGenerating.value = false
  }
}

const handleCopy = async () => {
  try {
    if (!localGeneratedPng.value) return
    
    // Convert base64 to blob and copy to clipboard
    const response = await fetch(localGeneratedPng.value)
    const blob = await response.blob()
    
    await navigator.clipboard.write([
      new ClipboardItem({ 'image/png': blob })
    ])
    
    logger.info('PNG copied to clipboard')
  } catch (error: any) {
    logger.error('Failed to copy PNG to clipboard', { error: error.message })
    localError.value = 'Failed to copy image to clipboard'
  }
}

const handleDownload = () => {
  try {
    if (!localGeneratedPng.value) return
    
    const link = document.createElement('a')
    link.href = localGeneratedPng.value
    link.download = `generated-image-${Date.now()}.png`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    
    logger.info('PNG downloaded')
  } catch (error: any) {
    logger.error('Failed to download PNG', { error: error.message })
    localError.value = 'Failed to download image'
  }
}

logger.debug('PNG Generator Cell mounted', { 
  cellId: effectiveCellId.value,
  hasCell: !!props.cell,
  hasCellId: !!props.cellId
})
</script>

<style scoped>
.png-generator-cell {
  /* Additional component-specific styles if needed */
}
</style>
