/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-01-14",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-01-14",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div class="threejs-scene-generator-cell bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg p-4 shadow-sm">
    <div class="cell-header mb-4">
      <h3 class="text-lg font-semibold text-primary dark:text-primary-light">
        {{ $t('threejsSceneGeneratorCell.title') }}
      </h3>
      <p class="text-sm text-text-secondary dark:text-text-secondary-dark mt-1">
        {{ $t('threejsSceneGeneratorCell.description') }}
      </p>
    </div>

    <div class="cell-content space-y-4">
      <!-- Model Selection -->
      <div class="model-selection">
        <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-2">
          {{ $t('threejsSceneGeneratorCell.modelLabel', 'AI Model') }}
        </label>
        <select
          v-model="selectedModel"
          :disabled="isGenerating || isLoadingModels"
          class="w-full px-3 py-2 border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark rounded focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option v-if="isLoadingModels" disabled value="">
            {{ $t('threejsSceneGeneratorCell.loadingModels', 'Loading models...') }}
          </option>
          <optgroup
            v-if="!isLoadingModels && localModels.length > 0"
            :label="$t('threejsSceneGeneratorCell.localModelsGroup', 'Local Models')"
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
            :label="$t('threejsSceneGeneratorCell.externalModelsGroup', 'External Models')"
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
            {{ $t('threejsSceneGeneratorCell.noModelsAvailable', 'No models available') }}
          </option>
        </select>
      </div>

      <!-- Prompt Input Section -->
      <div class="prompt-section">
        <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-2">
          {{ $t('threejsSceneGeneratorCell.promptLabel') }}
        </label>
        <textarea
          v-model="prompt"
          :disabled="isGenerating"
          :placeholder="$t('threejsSceneGeneratorCell.promptPlaceholder')"
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
          <span>{{ isGenerating ? $t('threejsSceneGeneratorCell.generating') : $t('threejsSceneGeneratorCell.generateButton') }}</span>
        </button>
      </div>

      <!-- Error Display -->
      <div v-if="error" class="error-section p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded">
        <p class="text-sm text-red-600 dark:text-red-400">
          {{ error }}
        </p>
      </div>

      <!-- 3D Scene Preview Section -->
      <div v-if="generatedScript" class="scene-preview-section">
        <div class="flex items-center justify-between mb-2">
          <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark">
            {{ $t('threejsSceneGeneratorCell.previewLabel') }}
          </label>
          <div class="flex gap-2">
            <button
              class="px-3 py-1 text-sm bg-secondary dark:bg-secondary-hover text-text-primary dark:text-text-primary-dark rounded hover:bg-secondary-hover dark:hover:bg-secondary-light transition"
              @click="handleCopyScript"
            >
              {{ copiedScript ? $t('threejsSceneGeneratorCell.copied') : $t('threejsSceneGeneratorCell.copyScript') }}
            </button>
            <button
              class="px-3 py-1 text-sm bg-secondary dark:bg-secondary-hover text-text-primary dark:text-text-primary-dark rounded hover:bg-secondary-hover dark:hover:bg-secondary-light transition"
              @click="handleDownloadScript"
            >
              {{ $t('threejsSceneGeneratorCell.downloadScript') }}
            </button>
          </div>
        </div>
        
        <!-- Three.js Canvas Container -->
        <div 
          ref="canvasContainer" 
          class="scene-container border border-border dark:border-border-dark rounded bg-gray-900 flex items-center justify-center"
          style="min-height: 400px; position: relative;"
        >
          <div v-if="!sceneInitialized" class="text-white text-center p-4">
            <p>{{ $t('threejsSceneGeneratorCell.initializingScene') }}</p>
          </div>
          <div v-if="sceneError" class="text-red-400 text-center p-4">
            <p>{{ $t('threejsSceneGeneratorCell.sceneError') }}</p>
            <p class="text-sm mt-2">{{ sceneError }}</p>
          </div>
        </div>

        <!-- Script Code Display (collapsible) -->
        <div class="mt-2">
          <button
            class="text-sm text-primary dark:text-primary-light hover:underline"
            @click="showCode = !showCode"
          >
            {{ showCode ? $t('threejsSceneGeneratorCell.hideCode') : $t('threejsSceneGeneratorCell.showCode') }}
          </button>
          <pre
            v-if="showCode"
            class="mt-2 p-3 bg-gray-50 dark:bg-gray-900 border border-border dark:border-border-dark rounded text-xs overflow-x-auto max-h-96 overflow-y-auto"
          ><code class="text-text-primary dark:text-text-primary-dark">{{ generatedScript }}</code></pre>
        </div>
      </div>

      <!-- Tips Section -->
      <div v-if="!generatedScript" class="tips-section p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded">
        <p class="text-sm text-blue-700 dark:text-blue-300 font-medium mb-2">
          {{ $t('threejsSceneGeneratorCell.tipsTitle') }}
        </p>
        <ul class="text-xs text-blue-600 dark:text-blue-400 space-y-1 list-disc list-inside">
          <li>{{ $t('threejsSceneGeneratorCell.tip1') }}</li>
          <li>{{ $t('threejsSceneGeneratorCell.tip2') }}</li>
          <li>{{ $t('threejsSceneGeneratorCell.tip3') }}</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted, nextTick, type Ref, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { processMessage, fetchAvailableModels } from '@/services/aiChatService.js'
import { useThreeJSScene } from './composables/useThreeJSScene'

// i18n
const { t: $t } = useI18n()

// Use Three.js scene composable
const {
  sceneInitialized,
  sceneError,
  canvasContainer,
  loadThreeJS,
  initializeThreeJSScene
} = useThreeJSScene()

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
    generatedScript?: string | null
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
const generatedScript: Ref<string | null> = ref(props.cell.initial_data?.generatedScript || null)
const isGenerating: Ref<boolean> = ref(props.cell.initial_data?.isGenerating || false)
const error: Ref<string | null> = ref(props.cell.initial_data?.error || null)
const showCode: Ref<boolean> = ref(false)
const copiedScript: Ref<boolean> = ref(false)

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
    const newScript = newData.generatedScript || generatedScript.value
    
    // Only reinitialize scene if script changed
    if (newScript !== generatedScript.value) {
      generatedScript.value = newScript
      if (newScript) {
        nextTick(() => {
          initializeThreeJSScene(newScript)
        })
      }
    }
    
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

  // Load Three.js from CDN
  loadThreeJS()
  
  // Initialize scene if script already exists
  if (generatedScript.value) {
    await nextTick()
    initializeThreeJSScene(generatedScript.value)
  }
})

// Handle scene generation
async function handleGenerate(): Promise<void> {
  if (!prompt.value.trim() || isGenerating.value) {
    return
  }

  try {
    isGenerating.value = true
    error.value = null
    generatedScript.value = null
    sceneInitialized.value = false
    sceneError.value = null
    updateCell()

    // Create a specialized prompt for Three.js generation
    const threejsPrompt = `Generate a complete, self-contained Three.js 3D scene based on this description: "${prompt.value}"

IMPORTANT: Return ONLY the JavaScript code, no explanations or markdown.

The code should:
1. Use the 'container' variable (passed as parameter) to append the renderer
2. Use THREE namespace (Three.js is loaded globally)
3. Create scene, camera, and renderer with proper setup
4. Add appropriate lighting
5. Create the described 3D objects
6. Include an animation loop
7. Handle window resize
8. Be production-ready and well-commented

Example structure:
// Scene setup
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(container.clientWidth, container.clientHeight);
container.appendChild(renderer.domElement);

// Your 3D scene code here...

// Animation
function animate() {
  requestAnimationFrame(animate);
  // Animation logic
  renderer.render(scene, camera);
}
animate();`

    // Call the chat API with the prompt
    const response = await processMessage({
      intention: threejsPrompt,
      history: [],
      model: selectedModel.value,
      classifyIntention: false,
      attachments: [],
    })

    // Extract code from response
    const content = response.message || response.response || ''
    
    // Try to extract code from response
    let extractedCode = content
    
    // If wrapped in code blocks, extract
    const codeMatch = content.match(/```(?:javascript|js)?\s*\n?([\s\S]*?)\n?```/)
    
    if (codeMatch) {
      extractedCode = codeMatch[1]
    }
    
    // Validate that we have Three.js code
    if (!extractedCode.includes('THREE')) {
      throw new Error('Generated content does not appear to be Three.js code')
    }

    generatedScript.value = extractedCode.trim()
    error.value = null

    // Initialize the scene
    await nextTick()
    initializeThreeJSScene(generatedScript.value)

  } catch (err: unknown) {
    const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
    error.value = $t('threejsSceneGeneratorCell.errorGeneration', { error: errorMessage })
    console.error('Three.js generation error:', err)
  } finally {
    isGenerating.value = false
    updateCell()
  }
}

// Copy script to clipboard
async function handleCopyScript(): Promise<void> {
  if (!generatedScript.value) return

  try {
    await navigator.clipboard.writeText(generatedScript.value)
    copiedScript.value = true
    setTimeout(() => {
      copiedScript.value = false
    }, 2000)
  } catch (err) {
    console.error('Failed to copy script:', err)
  }
}

// Download script as file
function handleDownloadScript(): void {
  if (!generatedScript.value) return

  const blob = new Blob([generatedScript.value], { type: 'text/javascript' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'threejs-scene.js'
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
      generatedScript: generatedScript.value,
      isGenerating: isGenerating.value,
      error: error.value,
      selectedModel: selectedModel.value
    }
  }
  emit('update:cell', updatedCell)
}
</script>

<style scoped>
.threejs-scene-generator-cell {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.scene-container {
  position: relative;
  overflow: hidden;
}

.scene-container canvas {
  display: block;
  width: 100% !important;
  height: 100% !important;
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
