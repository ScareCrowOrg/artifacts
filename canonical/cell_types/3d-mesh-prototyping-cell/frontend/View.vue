/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-01-22",
 *   "theme_compliance": 95,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full"
 * }
 */
<script setup lang="ts">
/**
 * 3D Mesh Prototyping Cell - Main View Component (Babylon.js)
 * 
 * Migrated from TresJS to Babylon.js for better physics integration and stability.
 * This component orchestrates the entire 3D mesh generation workflow with job queueing.
 * 
 * Features:
 * - Image upload for 3D reconstruction
 * - Job queueing with Redis-based status polling
 * - Babylon.js scene with per-cell engine architecture
 * - GLB loading with proper resource management
 * - Reactive viewport controls
 * 
 * @component
 */

import { ref, computed, watch, onMounted, onUnmounted, defineOptions } from 'vue'
import { createLogger } from '@/utils/logger'
import { apiFetch } from '@/services/apiService'
import authService from '@/services/authService'
import { useJobPolling } from './composables/useJobPolling'
import BabylonModelViewer from './components/BabylonModelViewer.vue'
import JobStatusIndicator from './components/JobStatusIndicator.vue'
import ViewportControls from './components/ViewportControls.vue'
import MeshMetadataDisplay from './components/MeshMetadataDisplay.vue'
import GenerationModeSwitcher from './components/GenerationModeSwitcher.vue'
import GLBFileUploader from './components/GLBFileUploader.vue'

// ITERATION #9: Define component name for proper Vue registration in dynamic loading context
defineOptions({ name: 'MeshPrototypingCellView' })

const logger = createLogger('component:3d-mesh-prototyping-cell-babylon')

interface Props {
  cell: any // Flexible to handle initial_data, state, or direct properties
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:cell', value: any): void
}>()

// Debug logs to inspect cell structure (ITERATION #4)
console.log('[DEBUG_ITERATION_4] props.cell:', JSON.parse(JSON.stringify(props.cell)))
if (props.cell && props.cell.initial_data) {
  console.log('[DEBUG_ITERATION_4] props.cell.initial_data:', JSON.parse(JSON.stringify(props.cell.initial_data)))
}
if (props.cell && props.cell.state) {
  console.log('[DEBUG_ITERATION_4] props.cell.state:', JSON.parse(JSON.stringify(props.cell.state)))
}

// Local component state (ITERATION #5 - writable refs for user interactions)
const uploadedImage = ref<string | null>(null) // User-uploaded image (writable)
const localError = ref<string | null>(null) // Local error state (writable)
const localGeneratedMesh = ref<string | null>(null) // Generated mesh data (writable)
const localIsGenerating = ref<boolean>(false) // Generation status (writable)
const localAutoRotate = ref<boolean>(false) // Viewport setting (writable)
const localWireframeMode = ref<boolean>(false) // Viewport setting (writable)
const localShowGrid = ref<boolean>(true) // Viewport setting (writable)

// Generation mode state
type GenerationMode = 'cloud-api' | 'local-gpu' | 'manual-upload'
const generationMode = ref<GenerationMode>(
  (props.cell?.initial_data?.generationMode || 
   props.cell?.state?.generationMode || 
   props.cell?.generationMode || 
   'local-gpu') as GenerationMode
)

// Manual upload state
const uploadedGLBFile = ref<File | null>(null)
const uploadedGLBUrl = ref<string | null>(null)

// Component state - Safe reactive access with defensive defaults (ITERATION #4)
// Now prioritizes local state over cell data (ITERATION #5)
const inputImage = computed(() => {
  // Prioritize uploaded image, then fall back to cell data
  const imageUrl = uploadedImage.value || 
                   props.cell?.initial_data?.inputImage || 
                   props.cell?.state?.inputImage || 
                   props.cell?.inputImage || ''
  console.log('[DEBUG_ITERATION_5] Computed inputImage:', imageUrl)
  return imageUrl
})

const generatedMesh = computed(() => {
  return localGeneratedMesh.value || 
         props.cell?.initial_data?.generatedMesh || 
         props.cell?.state?.generatedMesh || 
         props.cell?.generatedMesh || ''
})

const meshMetadata = computed(() => {
  return props.cell?.initial_data?.meshMetadata || props.cell?.state?.meshMetadata || props.cell?.meshMetadata || null
})

const isGenerating = computed(() => {
  return localIsGenerating.value || 
         props.cell?.initial_data?.isGenerating || 
         props.cell?.state?.isGenerating || 
         props.cell?.isGenerating || false
})

// Error computed with local error priority (ITERATION #5)
const error = computed(() => {
  return localError.value || 
         props.cell?.initial_data?.error || 
         props.cell?.state?.error || 
         props.cell?.error || null
})

// Viewport settings with local toggle refs priority (ITERATION #5)
const autoRotate = computed(() => {
  return localAutoRotate.value || 
         props.cell?.initial_data?.viewportSettings?.autoRotate || 
         props.cell?.state?.viewportSettings?.autoRotate || 
         props.cell?.viewportSettings?.autoRotate || false
})

const wireframeMode = computed(() => {
  return localWireframeMode.value || 
         props.cell?.initial_data?.viewportSettings?.wireframeMode || 
         props.cell?.state?.viewportSettings?.wireframeMode || 
         props.cell?.viewportSettings?.wireframeMode || false
})

const showGrid = computed(() => {
  // Use logical OR but showGrid defaults to true
  return localShowGrid.value !== false && (
         props.cell?.initial_data?.viewportSettings?.showGrid !== false || 
         props.cell?.state?.viewportSettings?.showGrid !== false || 
         props.cell?.viewportSettings?.showGrid !== false)
})

// Job polling using composable
const {
  jobId,
  jobStatus,
  isPolling,
  blenderOptimized,
  blenderError,
  statusMessage,
  sf3dCompleted,
  startPolling,
  stopPolling
} = useJobPolling(
  // onComplete callback
  (meshData, metadata) => {
    localGeneratedMesh.value = meshData
    localError.value = null
    localIsGenerating.value = false
    logger.info('3D mesh loaded successfully', metadata)
  },
  // onError callback
  (error) => {
    localError.value = error
    localIsGenerating.value = false
    logger.error('Job failed', error)
  }
)

// File input
const fileInput = ref<HTMLInputElement | null>(null)

// Computed
const hasInputImage = computed(() => inputImage.value !== null && inputImage.value !== '')
const hasMesh = computed(() => {
  // Has mesh if either generated or manually uploaded
  return (generatedMesh.value !== null && generatedMesh.value !== '') || uploadedGLBUrl.value !== null
})
const cameraPosition = computed(() => {
  return props.cell?.initial_data?.viewportSettings?.cameraPosition || 
         props.cell?.state?.viewportSettings?.cameraPosition || 
         props.cell?.viewportSettings?.cameraPosition || [0, 0, 5]
})

/**
 * Convert base64 data URL to blob URL for GLTFLoader
 * Handles both generated meshes (base64) and manually uploaded files (blob URL)
 * Memoized to avoid recreating URL on every access
 */
const meshBlobUrl = computed(() => {
  // Priority: Manual upload > Generated mesh
  if (uploadedGLBUrl.value) {
    return uploadedGLBUrl.value
  }
  
  if (!generatedMesh.value) return null
  
  try {
    const base64Data = generatedMesh.value.split(',')[1]
    const binaryData = atob(base64Data)
    const bytes = new Uint8Array(binaryData.length)
    for (let i = 0; i < binaryData.length; i++) {
      bytes[i] = binaryData.charCodeAt(i)
    }
    const blob = new Blob([bytes], { type: 'model/gltf-binary' })
    return URL.createObjectURL(blob)
  } catch (err: any) {
    logger.error('Error creating blob URL', err)
    return null
  }
})

// Track previous blob URL for cleanup
let previousBlobUrl: string | null = null

// Watch for mesh changes and cleanup old blob URLs
watch(meshBlobUrl, (newUrl, oldUrl) => {
  if (previousBlobUrl && previousBlobUrl !== newUrl) {
    URL.revokeObjectURL(previousBlobUrl)
    logger.debug('Revoked previous blob URL')
  }
  previousBlobUrl = newUrl
})

/**
 * Handle image file upload
 */
const handleFileUpload = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]

  if (!file) return

  if (!file.type.startsWith('image/')) {
    localError.value = 'Please upload a valid image file (PNG, JPG, etc.)'
    return
  }

  logger.info(`File selected: ${file.name} (${file.size} bytes)`)

  const reader = new FileReader()
  reader.onload = (e) => {
    const result = e.target?.result as string
    uploadedImage.value = result // ITERATION #5 - Now using writable ref
    localError.value = null
    logger.debug('Image loaded as base64 data URL')
    console.log('[DEBUG_ITERATION_5] uploadedImage set:', result.substring(0, 50) + '...')
  }
  reader.onerror = () => {
    localError.value = 'Failed to read image file'
    logger.error('FileReader error')
  }
  reader.readAsDataURL(file)
}

/**
 * Handle GLB file upload (manual upload mode)
 */
const handleGLBUpload = (file: File, blobUrl: string) => {
  logger.info(`GLB file uploaded: ${file.name} (${file.size} bytes)`)
  
  uploadedGLBFile.value = file
  uploadedGLBUrl.value = blobUrl
  localError.value = null
  
  // Clear any generated mesh to prioritize the uploaded one
  localGeneratedMesh.value = null
}

/**
 * Handle GLB upload error
 */
const handleGLBUploadError = (error: string) => {
  localError.value = error
  logger.error('GLB upload error', error)
}

/**
 * Generate 3D mesh from input image with mode-aware routing
 * Supports: cloud-api, local-gpu, manual-upload
 */
const generate3DMesh = async () => {
  if (!inputImage.value && generationMode.value !== 'manual-upload') {
    localError.value = 'Please upload an image first'
    return
  }

  // ITERATION #6: Check if user is authenticated
  if (!authService.isAuthenticated()) {
    localError.value = 'You must be logged in to generate 3D meshes'
    logger.warn('User not authenticated, cannot generate mesh')
    return
  }

  logger.info(`Starting 3D mesh generation with mode: ${generationMode.value}`)
  
  localIsGenerating.value = true
  localError.value = null

  try {
    const response = await apiFetch('/api/cells/execute-ephemeral', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        cell_type: '3d-mesh-prototyping-cell',
        input_data: {
          generationMode: generationMode.value,
          inputImage: inputImage.value,
          reconstructionParams: props.cell?.initial_data?.reconstructionParams || 
                                props.cell?.state?.reconstructionParams || 
                                props.cell?.reconstructionParams || {
                                  targetFaces: 10000,
                                  enableDracoCompression: true,
                                  compressionLevel: 7,
                                  targetFileSizeMB: 10
                                }
        }
      })
    })

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`)
    }

    const result = await response.json()
    logger.debug('API response:', result)

    // Extract job_id from nested API response
    const jobIdValue = result.result?.job_id || result.job_id
    
    if (result.success && jobIdValue) {
      logger.info(`Job queued: ${jobIdValue}`)
      
      // Start polling using composable
      startPolling(jobIdValue, 2000)
      
    } else {
      const errorMsg = result.error || result.result?.error || 'Failed to queue 3D generation job'
      localError.value = errorMsg
      logger.error('Job queueing failed', errorMsg)
      localIsGenerating.value = false
    }
  } catch (err: any) {
    logger.error('Error generating 3D mesh', err)
    localError.value = `Generation error: ${err.message}`
    localIsGenerating.value = false
  }
}

/**
 * Download generated GLB mesh
 */
const downloadMesh = () => {
  if (!generatedMesh.value) return

  logger.info('Downloading GLB mesh')

  try {
    const link = document.createElement('a')
    link.href = generatedMesh.value
    link.download = `mesh_${Date.now()}.glb`
    link.click()

    logger.debug('GLB download initiated')
  } catch (err) {
    logger.error('Error downloading mesh', err)
    localError.value = 'Failed to download mesh file' // ITERATION #5 - Use local ref
  }
}

// Toggle functions (ITERATION #5 - using local refs declared above)
const toggleAutoRotate = () => {
  localAutoRotate.value = !localAutoRotate.value
  logger.debug(`Auto-rotate: ${localAutoRotate.value}`)
}

const toggleWireframe = () => {
  localWireframeMode.value = !localWireframeMode.value
  logger.debug(`Wireframe mode: ${localWireframeMode.value}`)
}

const toggleGrid = () => {
  localShowGrid.value = !localShowGrid.value
  logger.debug(`Grid: ${localShowGrid.value}`)
}

// Lifecycle
onMounted(() => {
  logger.info('3D Mesh Prototyping Cell (Babylon.js) mounted')
  
  // Debug check for inputImage availability (ITERATION #4)
  if (!inputImage.value) {
    console.warn('[DEBUG_ITERATION_4] inputImage is empty on mount. Cell may not have initial data yet.')
  } else {
    logger.info('inputImage available on mount:', inputImage.value)
  }
})

onUnmounted(() => {
  // Stop polling
  stopPolling()
  
  // Cleanup blob URL on unmount
  if (previousBlobUrl) {
    URL.revokeObjectURL(previousBlobUrl)
    logger.debug('Revoked blob URL on unmount')
  }
  
  // Cleanup uploaded GLB URL
  if (uploadedGLBUrl.value) {
    URL.revokeObjectURL(uploadedGLBUrl.value)
    logger.debug('Revoked uploaded GLB URL')
  }
  
  logger.info('3D Mesh Prototyping Cell (Babylon.js) unmounted')
})
</script>

<template>
  <div class="mesh-prototyping-container bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark p-6 rounded-lg border border-border dark:border-border-dark">
    <h2 class="text-2xl font-bold mb-4">3D Mesh Prototyping Cell</h2>
    <p class="text-text-secondary dark:text-text-secondary-dark mb-6">
      Generate volumetric 3D meshes with 360º volume from single images using AI-powered reconstruction
    </p>

    <!-- Error Display -->
    <div v-if="error" class="bg-error/10 dark:bg-error/20 border border-error text-error dark:text-error-light px-4 py-3 rounded mb-4">
      <strong>Error:</strong> {{ error }}
    </div>

    <!-- Generation Mode Switcher -->
    <GenerationModeSwitcher
      v-model="generationMode"
      :disabled="isGenerating"
      class="mb-6"
    />

    <!-- Job Status -->
    <JobStatusIndicator
      v-if="generationMode !== 'manual-upload'"
      :is-generating="isGenerating"
      :job-status="jobStatus"
      :job-id="jobId"
      :blender-optimized="blenderOptimized"
      :blender-error="blenderError"
      :message="statusMessage"
    />

    <!-- Manual Upload Section -->
    <GLBFileUploader
      v-if="generationMode === 'manual-upload'"
      :disabled="isGenerating"
      @upload="handleGLBUpload"
      @error="handleGLBUploadError"
      class="mb-6"
    />

    <!-- Image Upload Section (for generation modes) -->
    <div v-if="generationMode !== 'manual-upload'" class="mb-6">
      <label class="block text-sm font-medium mb-2 text-text-primary dark:text-text-primary-dark">Upload Image for 3D Reconstruction</label>
      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        @change="handleFileUpload"
        class="block w-full text-sm text-text-secondary dark:text-text-secondary-dark file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-primary dark:file:bg-primary-light file:text-white hover:file:bg-primary-hover dark:hover:file:bg-primary"
        :disabled="isGenerating"
      />
      <p class="text-xs text-text-secondary dark:text-text-secondary-dark mt-1">Supported formats: PNG, JPG, JPEG</p>
    </div>

    <!-- Image Preview (only for generation modes) -->
    <div v-if="hasInputImage && generationMode !== 'manual-upload'" class="mb-6">
      <label class="block text-sm font-medium mb-2 text-text-primary dark:text-text-primary-dark">Input Image Preview</label>
      <img
        :src="inputImage"
        alt="Input for reconstruction"
        class="max-w-xs max-h-64 rounded border border-border dark:border-border-dark"
      />
    </div>

    <!-- Generate Button (only for generation modes) -->
    <button
      v-if="generationMode !== 'manual-upload'"
      @click="generate3DMesh"
      :disabled="!hasInputImage || isGenerating"
      class="bg-success dark:bg-success-light hover:bg-success-dark dark:hover:bg-success disabled:bg-surface-disabled dark:disabled:bg-surface-disabled disabled:cursor-not-allowed text-white font-semibold py-2 px-6 rounded mb-6 transition"
    >
      <span v-if="isGenerating">{{ jobStatus === 'processing' ? 'Processing...' : 'Queueing...' }}</span>
      <span v-else>Generate 3D Mesh ({{ generationMode === 'cloud-api' ? 'Cloud' : 'Local GPU' }})</span>
    </button>

    <!-- Viewport Controls -->
    <ViewportControls
      :auto-rotate="autoRotate"
      :wireframe-mode="wireframeMode"
      :show-grid="showGrid"
      :has-mesh="hasMesh"
      @toggle-auto-rotate="toggleAutoRotate"
      @toggle-wireframe="toggleWireframe"
      @toggle-grid="toggleGrid"
      @download-mesh="downloadMesh"
    />

    <!-- Babylon.js Viewport - Per-cell engine instance -->
    <div 
      class="viewport-container bg-surface-dark dark:bg-black rounded border border-border dark:border-border-dark"
      :style="{ width: '100%', height: '500px' }"
    >
      <BabylonModelViewer
        v-if="hasMesh && meshBlobUrl"
        :url="meshBlobUrl"
        :wireframe="wireframeMode"
        :auto-rotate="autoRotate"
        :show-grid="showGrid"
      />
      <div v-else class="flex items-center justify-center h-full">
        <p class="text-text-secondary dark:text-text-secondary-dark">
          Upload an image and generate a 3D mesh to view it here
        </p>
      </div>
    </div>

    <!-- Mesh Metadata -->
    <MeshMetadataDisplay :metadata="meshMetadata" />
  </div>
</template>

<style scoped>
.mesh-prototyping-container {
  font-family: 'Inter', sans-serif;
}

.viewport-container {
  position: relative;
  overflow: hidden;
}
</style>
