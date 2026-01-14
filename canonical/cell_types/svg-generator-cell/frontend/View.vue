/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-01-13",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-01-13",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div class="svg-generator-cell bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg p-4 shadow-sm">
    <div class="cell-header mb-4">
      <h3 class="text-lg font-semibold text-primary dark:text-primary-light">
        {{ $t('svgGeneratorCell.title') }}
      </h3>
      <p class="text-sm text-text-secondary dark:text-text-secondary-dark mt-1">
        {{ $t('svgGeneratorCell.description') }}
      </p>
    </div>

    <div class="cell-content space-y-4">
      <!-- Model Selection -->
      <div class="model-selection">
        <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-2">
          {{ $t('svgGeneratorCell.modelLabel', 'AI Model') }}
        </label>
        <select
          v-model="selectedModel"
          :disabled="isGenerating || isLoadingModels"
          class="w-full px-3 py-2 border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark rounded focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option v-if="isLoadingModels" disabled value="">
            {{ $t('svgGeneratorCell.loadingModels', 'Loading models...') }}
          </option>
          <optgroup
            v-if="!isLoadingModels && localModels.length > 0"
            :label="$t('svgGeneratorCell.localModelsGroup', 'Local Models')"
          >
            <option
              v-for="model in localModels"
              :key="model.value"
              :value="model.value"
            >
              {{ model.label }}
            </option>
          </optgroup>
          <optgroup
            v-if="!isLoadingModels && externalModels.length > 0"
            :label="$t('svgGeneratorCell.externalModelsGroup', 'External Models')"
          >
            <option
              v-for="model in externalModels"
              :key="model.value"
              :value="model.value"
            >
              {{ model.label }}
            </option>
          </optgroup>
          <option
            v-if="!isLoadingModels && availableModels.length === 0"
            disabled
            value=""
          >
            {{ $t('svgGeneratorCell.noModelsAvailable', 'No models available') }}
          </option>
        </select>
      </div>

      <!-- Prompt Input Section -->
      <div class="prompt-section">
        <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-2">
          {{ $t('svgGeneratorCell.promptLabel') }}
        </label>
        <textarea
          v-model="prompt"
          :disabled="isGenerating"
          :placeholder="$t('svgGeneratorCell.promptPlaceholder')"
          class="w-full px-3 py-2 border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark rounded focus:outline-none focus:ring-2 focus:ring-primary resize-none"
          rows="3"
          @keydown.ctrl.enter="handleGenerate"
          @keydown.meta.enter="handleGenerate"
        />
      </div>

      <!-- Generate Button -->
      <div class="action-section">
        <button
          :disabled="!prompt.trim() || isGenerating || !selectedModel"
          class="px-4 py-2 bg-primary dark:bg-primary-hover text-white rounded hover:bg-primary-hover dark:hover:bg-primary-light transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          @click="handleGenerate"
        >
          <svg
            v-if="isGenerating"
            class="animate-spin h-5 w-5"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span>{{ isGenerating ? $t('svgGeneratorCell.generating') : $t('svgGeneratorCell.generateButton') }}</span>
        </button>
      </div>

      <!-- Error Display -->
      <div v-if="error" class="error-section p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded">
        <p class="text-sm text-red-600 dark:text-red-400">
          {{ error }}
        </p>
      </div>

      <!-- SVG Preview Section -->
      <div v-if="generatedSvg" class="svg-preview-section">
        <div class="flex items-center justify-between mb-2">
          <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark">
            {{ $t('svgGeneratorCell.previewLabel') }}
          </label>
          <div class="flex gap-2">
            <button
              class="px-3 py-1 text-sm bg-secondary dark:bg-secondary-hover text-text-primary dark:text-text-primary-dark rounded hover:bg-secondary-hover dark:hover:bg-secondary-light transition"
              @click="handleCopySvg"
            >
              {{ copiedSvg ? $t('svgGeneratorCell.copied') : $t('svgGeneratorCell.copySvg') }}
            </button>
            <button
              class="px-3 py-1 text-sm bg-secondary dark:bg-secondary-hover text-text-primary dark:text-text-primary-dark rounded hover:bg-secondary-hover dark:hover:bg-secondary-light transition"
              @click="handleDownloadSvg"
            >
              {{ $t('svgGeneratorCell.downloadSvg') }}
            </button>
          </div>
        </div>
        
        <div class="svg-preview-container border border-border dark:border-border-dark rounded p-4 bg-white dark:bg-gray-800 flex items-center justify-center min-h-[200px]">
          <div v-html="generatedSvg" class="svg-content"></div>
        </div>

        <!-- SVG Code Display (collapsible) -->
        <div class="mt-2">
          <button
            class="text-sm text-primary dark:text-primary-light hover:underline"
            @click="showCode = !showCode"
          >
            {{ showCode ? $t('svgGeneratorCell.hideCode') : $t('svgGeneratorCell.showCode') }}
          </button>
          <pre
            v-if="showCode"
            class="mt-2 p-3 bg-gray-50 dark:bg-gray-900 border border-border dark:border-border-dark rounded text-xs overflow-x-auto"
          ><code class="text-text-primary dark:text-text-primary-dark">{{ generatedSvg }}</code></pre>
        </div>
      </div>

      <!-- Tips Section -->
      <div v-if="!generatedSvg" class="tips-section p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded">
        <p class="text-sm text-blue-700 dark:text-blue-300 font-medium mb-2">
          {{ $t('svgGeneratorCell.tipsTitle') }}
        </p>
        <ul class="text-xs text-blue-600 dark:text-blue-400 space-y-1 list-disc list-inside">
          <li>{{ $t('svgGeneratorCell.tip1') }}</li>
          <li>{{ $t('svgGeneratorCell.tip2') }}</li>
          <li>{{ $t('svgGeneratorCell.tip3') }}</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted, type Ref, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { processMessage, fetchAvailableModels } from '@/services/aiChatService.js'

// i18n
const { t: $t } = useI18n()

// AI Model interface
interface AIModel {
  value: string
  label: string
  type: 'local' | 'cloud' | 'byok'
  provider: string
}

// Define props interface
interface CellData {
  id?: string
  notebook_item_type_id?: string
  initial_data?: {
    prompt?: string
    generatedSvg?: string | null
    isGenerating?: boolean
    error?: string | null
    selectedModel?: string
  }
}

interface Props {
  cell: CellData
}

const props = defineProps<Props>()

// Typed emits
const emit = defineEmits<{
  'update:cell': [cell: CellData]
}>()

// Typed refs
const prompt: Ref<string> = ref(props.cell.initial_data?.prompt || '')
const generatedSvg: Ref<string | null> = ref(props.cell.initial_data?.generatedSvg || null)
const isGenerating: Ref<boolean> = ref(props.cell.initial_data?.isGenerating || false)
const error: Ref<string | null> = ref(props.cell.initial_data?.error || null)
const showCode: Ref<boolean> = ref(false)
const copiedSvg: Ref<boolean> = ref(false)

// Model selection state
const availableModels: Ref<AIModel[]> = ref([])
const selectedModel: Ref<string> = ref(props.cell.initial_data?.selectedModel || 'mistral')
const isLoadingModels: Ref<boolean> = ref(true)

// Computed properties for model groups
const localModels: ComputedRef<AIModel[]> = computed(() =>
  availableModels.value.filter((m) => m.type === 'local')
)

const externalModels: ComputedRef<AIModel[]> = computed(() =>
  availableModels.value.filter((m) => m.type === 'cloud' || m.type === 'byok')
)

// Watch for external cell changes
watch(() => props.cell.initial_data, (newData) => {
  if (newData) {
    prompt.value = newData.prompt || prompt.value
    generatedSvg.value = newData.generatedSvg || generatedSvg.value
    isGenerating.value = newData.isGenerating || false
    error.value = newData.error || null
    if (newData.selectedModel) {
      selectedModel.value = newData.selectedModel
    }
  }
}, { deep: true })

// Watch for model changes to update cell data
watch(selectedModel, () => {
  updateCell()
})

// Fetch available models on mount
onMounted(async () => {
  try {
    availableModels.value = await fetchAvailableModels()
    
    // Validate selected model exists, otherwise use first available
    if (availableModels.value.length > 0) {
      const modelExists = availableModels.value.some(m => m.value === selectedModel.value)
      if (!modelExists) {
        selectedModel.value = availableModels.value[0].value
      }
    }
  } catch (err) {
    console.error('Failed to fetch models:', err)
    // Fallback to default
    availableModels.value = [
      { value: 'mistral', label: '🏠 Mistral (Ollama)', type: 'local', provider: 'ollama' }
    ]
  } finally {
    isLoadingModels.value = false
  }
})

// Handle SVG generation
async function handleGenerate(): Promise<void> {
  if (!prompt.value.trim() || isGenerating.value) {
    return
  }

  try {
    isGenerating.value = true
    error.value = null
    generatedSvg.value = null
    updateCell()

    // Create a specialized prompt for SVG generation
    const svgPrompt = `Generate a clean, valid SVG visualization based on this description: "${prompt.value}"

IMPORTANT: Return ONLY the SVG code, no explanations. Start with <svg> and end with </svg>.
Include proper viewBox and dimensions. Keep it simple and readable.`

    // Call the chat API with the prompt
    // Note: assignee_id is not required - backend uses authenticated user from JWT token
    // Use the selected model from the dropdown
    const response = await processMessage({
      intention: svgPrompt,
      history: [],
      model: selectedModel.value,
      classifyIntention: false,
      attachments: [],
    })

    // Extract SVG from response
    const content = response.message || response.response || ''
    
    // Try to extract SVG from the response
    let extractedSvg = content
    
    // If wrapped in code blocks, extract
    const svgMatch = content.match(/```(?:svg|xml)?\s*\n?([\s\S]*?)\n?```/) || 
                     content.match(/<svg[\s\S]*?<\/svg>/i)
    
    if (svgMatch) {
      extractedSvg = svgMatch[1] || svgMatch[0]
    }
    
    // Validate that we have SVG
    if (!extractedSvg.trim().startsWith('<svg')) {
      throw new Error('Generated content is not valid SVG')
    }

    generatedSvg.value = extractedSvg.trim()
    error.value = null

  } catch (err: unknown) {
    const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
    error.value = $t('svgGeneratorCell.errorGeneration', { error: errorMessage })
    console.error('SVG generation error:', err)
  } finally {
    isGenerating.value = false
    updateCell()
  }
}

// Copy SVG to clipboard
async function handleCopySvg(): Promise<void> {
  if (!generatedSvg.value) return

  try {
    await navigator.clipboard.writeText(generatedSvg.value)
    copiedSvg.value = true
    setTimeout(() => {
      copiedSvg.value = false
    }, 2000)
  } catch (err) {
    console.error('Failed to copy SVG:', err)
  }
}

// Download SVG as file
function handleDownloadSvg(): void {
  if (!generatedSvg.value) return

  const blob = new Blob([generatedSvg.value], { type: 'image/svg+xml' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'generated-svg.svg'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

// Update cell data
function updateCell(): void {
  const updatedCell: CellData = {
    ...props.cell,
    initial_data: {
      ...props.cell.initial_data,
      prompt: prompt.value,
      generatedSvg: generatedSvg.value,
      isGenerating: isGenerating.value,
      error: error.value,
      selectedModel: selectedModel.value
    }
  }
  emit('update:cell', updatedCell)
}
</script>

<style scoped>
.svg-generator-cell {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.svg-content {
  max-width: 100%;
  max-height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.svg-content :deep(svg) {
  max-width: 100%;
  max-height: 400px;
  height: auto;
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
