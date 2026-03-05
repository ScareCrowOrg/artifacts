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

import { ref, computed, watch, onMounted, onUnmounted, defineOptions, nextTick } from 'vue'
import { createLogger } from '@/utils/logger'
import { MeshPrototypingCell } from './MeshPrototypingCell'
import type { MeshPrototypingInput } from './MeshPrototypingCell'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { createApiFetch } from '@/services/apiService'
import { useJobPolling } from './composables/useJobPolling'
import BabylonModelViewer from '@/components/viewers/BabylonModelViewer.vue'
import JobStatusIndicator from './components/JobStatusIndicator.vue'
import ViewportControls from './components/ViewportControls.vue'
import MeshMetadataDisplay from './components/MeshMetadataDisplay.vue'
import GenerationModeSwitcher from './components/GenerationModeSwitcher.vue'
import GLBFileUploader from './components/GLBFileUploader.vue'

// ITERATION #9: Define component name for proper Vue registration in dynamic loading context
defineOptions({ name: 'MeshPrototypingCellView' })

const logger = createLogger('component:3d-mesh-prototyping-cell-babylon')

// Initialize MeshPrototypingCell instance
const cellInstance = new MeshPrototypingCell()

interface Props {
  cell: any // Flexible to handle initial_data, state, or direct properties
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:cell', value: any): void
}>()

// Local component state (ITERATION #5 - writable refs for user interactions)
// ARCHITECTURE: Separate UI State from Persistence State
// localPreview: ephemeral UI state (shows immediately on upload)
// localGeneratedMesh, etc: used to update persistent cell state
const localPreview = ref<string | null>(null) // UI preview from file input (ephemeral, not persisted)
const localError = ref<string | null>(null) // Local error state (writable)
const localGeneratedMesh = ref<string | null>(null) // Generated mesh data (writable)
const localIsGenerating = ref<boolean>(false) // Generation status (writable)
const localAutoRotate = ref<boolean>(false) // Viewport setting (writable)
const localWireframeMode = ref<boolean>(false) // Viewport setting (writable)
const localShowGrid = ref<boolean>(true) // Viewport setting (writable)
const localSolidifySilhouette = ref<boolean>(false) // Silhouette processing (writable)

// Generation mode state
type GenerationMode = 'cloud-api' | 'local-gpu' | 'manual-upload'
type MeshGenerationModel = 'sf3d' | 'instantmesh'

const generationMode = ref<GenerationMode>(
  (props.cell?.initial_data?.generationMode ||
   props.cell?.state?.generationMode ||
   props.cell?.generationMode ||
   'local-gpu') as GenerationMode
)

// Model selection state (defaults to instantmesh due to SF3D FP16 precision issues)
const selectedModel = ref<MeshGenerationModel>(
  (props.cell?.initial_data?.modelType ||
   props.cell?.state?.modelType ||
   props.cell?.modelType ||
   'instantmesh') as MeshGenerationModel
)

// Manual upload state
const uploadedGLBFile = ref<File | null>(null)
const uploadedGLBUrl = ref<string | null>(null)

// Component state - Simple separation: UI state vs Persistence state
// UI Display: Priority is local preview (what user just uploaded), then fallback to persisted data
const displayImage = computed(() => {
  // ONLY use localPreview - NO fallback to props
  // Props fallback can cause re-renders when parent updates
  const result = localPreview.value || ''
  console.log('[COMPUTED] displayImage:', { length: result.length, hasData: result.length > 0 })
  return result
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
// Create authenticated fetch function for API calls
// Token comes from workspaceStore.sessionToken (populated by handshake), not authService
const workspaceStore = useWorkspaceStore()
const apiFetch = createApiFetch(() => {
  const token = workspaceStore.sessionToken
  if (!token) {
    throw new Error('[MeshPrototyping] No session token — workspace not ready')
  }
  return token
})

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
  apiFetch,
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
const hasInputImage = computed(() => displayImage.value !== '')
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

// DEBUG: Watch localPreview changes - DETAILED LOGGING TO DETECT RESETS
watch(localPreview, (newVal, oldVal) => {
  const timestamp = new Date().toLocaleTimeString('pt-BR', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 })
  const newLength = newVal?.length || 0
  const oldLength = oldVal?.length || 0

  console.log(`%c[${timestamp}] [WATCH] localPreview CHANGED`, 'background: #ff6b6b; color: white; font-weight: bold;', {
    'Old Length': oldLength > 0 ? `${oldLength} bytes` : 'EMPTY',
    'New Length': newLength > 0 ? `${newLength} bytes` : 'EMPTY',
    'Direction': oldLength === 0 && newLength > 0 ? '📤 UPLOAD (empty → data)' : oldLength > 0 && newLength === 0 ? '❌ RESET (data → empty)' : '🔄 UPDATED',
    'New Start': newVal?.substring(0, 50) || 'null'
  })

  // CRITICAL: If resetting to empty, log stack trace
  if (oldLength > 0 && newLength === 0) {
    console.error('%c🚨 CRITICAL: localPreview WAS RESET TO EMPTY!', 'background: #ff0000; color: white; font-weight: bold;')
    console.trace('[STACK TRACE] Who reset localPreview?')
  }
})

// DEBUG: Watch displayImage changes
watch(displayImage, (newVal, oldVal) => {
  console.log('[WATCH] displayImage (computed) changed', {
    newValLength: newVal?.length || 0,
    oldValLength: oldVal?.length || 0
  })
})

// DEBUG: Watch hasInputImage changes
watch(hasInputImage, (newVal, oldVal) => {
  console.log('[WATCH] hasInputImage (computed) changed', { newVal, oldVal })
})

/**
 * Handle image file upload
 * ARCHITECTURE: Updates only localPreview (UI state), not persistent state
 */
let uploadCallCount = 0
const handleFileUpload = (event: Event) => {
  uploadCallCount++
  const callNum = uploadCallCount
  const timestamp = new Date().toLocaleTimeString('pt-BR', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 })

  console.log(`%c[${timestamp}] handleFileUpload CALLED (#${callNum})`, 'background: #4ecdc4; color: white; font-weight: bold;')

  const target = event.target as HTMLInputElement
  const file = target.files?.[0]

  if (!file) {
    console.warn(`[${timestamp}] No file selected (call #${callNum})`)
    return
  }

  console.log(`[${timestamp}] File selected: ${file.name} (${file.size} bytes) [call #${callNum}]`)

  if (!file.type.startsWith('image/')) {
    localError.value = 'Please upload a valid image file (PNG, JPG, etc.)'
    console.warn(`[${timestamp}] Invalid file type: ${file.type} [call #${callNum}]`)
    return
  }

  logger.info(`File selected: ${file.name} (${file.size} bytes)`)

  const reader = new FileReader()

  reader.onload = (e) => {
    try {
      const result = e.target?.result as string

      console.log(`%c[${timestamp}] reader.onload TRIGGERED - setting localPreview to ${result.length} bytes [call #${callNum}]`, 'background: #95e1d3; color: #222;')

      // IMMEDIATE UI UPDATE: localPreview updates synchronously
      // No cascading computeds, no prop dependencies, just show what user picked
      localPreview.value = result
      localError.value = null

      console.log(`%c[${timestamp}] ✅ localPreview.value SET SUCCESSFULLY [call #${callNum}]`, 'background: #38ada9; color: white; font-weight: bold;')

      logger.debug('Image loaded as base64', {
        previewLength: localPreview.value?.length || 0
      })
    } catch (err: any) {
      localError.value = `Image load failed: ${err.message}`
      console.error(`[${timestamp}] Error in onload: ${err.message} [call #${callNum}]`)
      logger.error('Image load error', err)
    }
  }

  reader.onerror = () => {
    localError.value = 'Failed to read image file'
    console.error(`[${timestamp}] FileReader error [call #${callNum}]`)
    logger.error('FileReader error')
  }

  console.log(`[${timestamp}] Calling reader.readAsDataURL [call #${callNum}]`)
  reader.readAsDataURL(file)
  console.log(`[${timestamp}] readAsDataURL call completed [call #${callNum}]`)
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
  if (!displayImage.value && generationMode.value !== 'manual-upload') {
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
    // Prepare input for cell execution
    const reconstructionParams = props.cell?.initial_data?.reconstructionParams ||
                                props.cell?.state?.reconstructionParams ||
                                props.cell?.reconstructionParams || {
                                  targetFaces: 10000,
                                  enableDracoCompression: true,
                                  compressionLevel: 7,
                                  targetFileSizeMB: 10
                                }

    const input: MeshPrototypingInput = {
      inputImage: displayImage.value || '',
      generationMode: generationMode.value,
      modelType: selectedModel.value,
      reconstructionParams,
      solidifySilhouette: localSolidifySilhouette.value  // User-controlled option
    }
    
    // Validate input using cell's validate method
    const validationErrors = cellInstance.validate(input)
    
    if (validationErrors.length > 0) {
      const errorMessages = validationErrors.map(e => `${e.field}: ${e.message}`).join(', ')
      throw new Error(`Validation failed: ${errorMessages}`)
    }
    
    logger.info(`Executing cell with mode: ${generationMode.value}`)

    // Execute using cell instance
    const result = await cellInstance.execute(input)
    
    logger.debug('Cell execution result:', { 
      success: result.success,
      executionTime: result.execution_time 
    })

    if (!result.success) {
      // Backend returned explicit failure
      const errorMsg = result.error || 'Unknown error'
      logger.error(`Generation failed: ${errorMsg}`)
      localError.value = errorMsg
      localIsGenerating.value = false

    } else if (result.output) {
      const output = result.output as any
      
      if (output.job_id) {
        // Async job (local-gpu mode) - start polling
        logger.info(`Job queued: ${output.job_id}`)
        startPolling(output.job_id, 2000)

      } else if (output.glb_url || output.mesh_data) {
        // Synchronous response (cloud-api mode) - load mesh directly
        logger.info('Mesh generated successfully (cloud-api)')
        localGeneratedMesh.value = output.glb_url || output.mesh_data
        localError.value = null
        localIsGenerating.value = false
        if (output.metadata) {
          logger.debug('Mesh metadata:', output.metadata)
        }
      } else {
        // Success but neither job_id nor glb_url - unexpected
        const unexpectedMsg = 'Unexpected response: no job ID or GLB URL received'
        logger.error(unexpectedMsg)
        localError.value = unexpectedMsg
        localIsGenerating.value = false
      }
    } else {
      const unexpectedMsg = 'Unexpected response: no output data'
      logger.error(unexpectedMsg)
      localError.value = unexpectedMsg
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
  if (!meshBlobUrl.value && !uploadedGLBFile.value) return

  logger.info('Downloading GLB mesh')

  try {
    const link = document.createElement('a')

    // Use blob URL for generated meshes, or file blob for uploaded files
    if (uploadedGLBFile.value) {
      // Manual upload mode - use file blob
      const blob = uploadedGLBFile.value
      link.href = URL.createObjectURL(blob)
      link.download = uploadedGLBFile.value.name || `mesh_${Date.now()}.glb`
    } else {
      // Generated mesh mode - use blob URL
      link.href = meshBlobUrl.value!
      link.download = `mesh_${Date.now()}.glb`
    }

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

// Lifecycle - HYDRATION PHASE: Initialize from props ONLY on mount
onMounted(async () => {
  logger.info('3D Mesh Prototyping Cell (Babylon.js) mounted')

  // HYDRATION: Read from props ONLY on mount, never again
  // This follows Buffer Local Pattern from REACTIVITY_ISOLATION.md
  if (!localPreview.value && props.cell?.initial_data?.inputImage) {
    localPreview.value = props.cell.initial_data.inputImage
    logger.info('Hydrated localPreview from props.cell.initial_data')
  }

  // Debug check
  if (!displayImage.value) {
    logger.warn('No image available on mount.')
  } else {
    logger.info('Image available on mount')
  }
  
  // Perform health check
  try {
    const health = await cellInstance.health_check()
    if (health.status !== 'healthy') {
      logger.warn('Cell health check warning', {
        status: health.status,
        reason: health.reason
      })
      // Optionally show a UI warning if service is degraded
      if (!health.can_execute) {
        localError.value = `Service unavailable: ${health.reason}`
      }
    } else {
      logger.debug('Cell health check passed')
    }
  } catch (error: any) {
    logger.error('Cell health check failed', { error: error.message })
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

    <!-- Image Upload Section (Card Container) -->
    <div v-if="generationMode !== 'manual-upload'" class="p-6 bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg mb-6">
      <!-- Header with Icon -->
      <div class="flex items-center gap-2 mb-4">
        <span class="text-2xl">📤</span>
        <h3 class="text-lg font-semibold text-text-primary dark:text-text-primary-dark">
          Upload Image for 3D Reconstruction
        </h3>
      </div>

      <!-- Description -->
      <p class="text-sm text-text-secondary dark:text-text-secondary-dark mb-1">
        Generate volumetric 3D meshes from 2D images
      </p>
      <p class="text-xs text-text-secondary dark:text-text-secondary-dark mb-4">
        Supported formats: PNG, JPG, JPEG
      </p>

      <!-- File Input -->
      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        @change="handleFileUpload"
        class="block w-full text-sm text-text-secondary dark:text-text-secondary-dark p-3 border border-dashed border-border dark:border-border-dark rounded mb-4 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-primary dark:file:bg-primary-light file:text-white hover:file:bg-primary-hover dark:hover:file:bg-primary"
        :disabled="isGenerating"
      />

      <!-- Solidify Silhouette Option (moved inside card) -->
      <label v-if="selectedModel === 'instantmesh'" class="flex items-start gap-3 p-3 bg-surface-light dark:bg-surface-dark-light rounded border border-border dark:border-border-dark cursor-pointer">
        <input
          v-model="localSolidifySilhouette"
          type="checkbox"
          :disabled="isGenerating"
          class="w-5 h-5 rounded border-border dark:border-border-dark text-primary focus:ring-2 focus:ring-primary mt-0.5"
        />
        <div class="flex-1">
          <div class="text-sm font-medium text-text-primary dark:text-text-primary-dark">
            Solidify Silhouette
            <span class="text-xs text-text-secondary dark:text-text-secondary-dark font-normal">(Only for InstantMesh)</span>
          </div>
          <div class="text-xs text-text-secondary dark:text-text-secondary-dark mt-1">
            <span v-if="localSolidifySilhouette">
              🔧 Enabled: Fixes incomplete geometry (good for objects with fine details like fur, whiskers)
            </span>
            <span v-else>
              ⚡ Disabled: Fast mode (good for clean silhouettes like boxes, simple shapes)
            </span>
          </div>
        </div>
      </label>
    </div>

    <!-- Image Preview Container -->
    <div class="mb-6 p-4 bg-surface-light dark:bg-surface-dark-light rounded border border-border dark:border-border-dark">
      <label class="block text-sm font-medium mb-4 text-text-primary dark:text-text-primary-dark">
        📤 Input Image Preview
      </label>
      <!-- Clean, simple preview using displayImage -->
      <div class="preview-container border-4 border-dashed border-blue-400 p-4 bg-blue-50 dark:bg-blue-950 rounded">
        <!-- DEBUG: Show actual values - ALWAYS VISIBLE -->
        <div class="text-xl font-bold text-red-600 bg-yellow-200 p-4 border-4 border-red-600 mb-4">
          🔴 TEMPLATE RENDER TEST 🔴
        </div>

        <p class="text-xs text-gray-500 mb-4 p-2 bg-gray-100 rounded">
          DEBUG: displayImage.length={{ displayImage.length }}, localPreview.length={{ localPreview?.length || 0 }}, hasInputImage={{ hasInputImage }}
        </p>

        <!-- REMOVED V-IF: Always show status -->
        <p v-if="displayImage.length === 0" class="text-xs text-blue-700 dark:text-blue-300 p-2 bg-blue-100 rounded mb-4">
          ⏳ Aguardando imagem... (displayImage ainda está vazio)
        </p>

        <!-- ALWAYS SHOW - Image container -->
        <div class="border-2 border-purple-500 p-4 bg-purple-50 rounded mb-4">
          <p class="text-purple-700 font-bold mb-2">
            📊 STATE: displayImage.length={{ displayImage.length }}
          </p>

          <p v-if="displayImage.length > 0" class="text-xs text-green-700 dark:text-green-300 mb-2">
            ✅ Imagem carregada ({{ displayImage.length }} chars)
          </p>

          <!-- ALWAYS RENDER IMG - regardless of v-if -->
          <img
            :src="displayImage"
            :key="`img-${displayImage.substring(0, 30)}`"
            alt="Input for reconstruction"
            class="w-full h-auto block rounded border-2 border-green-500"
            style="min-height: 200px; background: #333; display: block;"
            @load="console.log('[IMG] ✅ Imagem renderizada com sucesso!')"
            @error="console.error('[IMG] ❌ Erro ao renderizar imagem')"
          />
        </div>
      </div>
    </div>

    <!-- Generate Button (only for generation modes) -->
    <button
      v-if="generationMode !== 'manual-upload'"
      @click="generate3DMesh"
      :disabled="!hasInputImage || isGenerating"
      class="bg-success dark:bg-success-light hover:bg-success-dark dark:hover:bg-success disabled:bg-surface-disabled dark:disabled:bg-surface-disabled disabled:cursor-not-allowed text-white font-semibold py-2 px-6 rounded mb-6 transition"
    >
      <span v-if="isGenerating">{{ jobStatus === 'processing' ? 'Processing...' : 'Queueing...' }}</span>
      <span v-else>
        Generate 3D Mesh
        <span v-if="generationMode === 'cloud-api'"> (Cloud API)</span>
      </span>
    </button>

    <!-- Babylon.js Viewer Controls -->
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

    <!-- Babylon.js 3D Mesh Viewer (only shows generated mesh) -->
    <div
      v-if="generationMode !== 'manual-upload' || hasMesh"
      class="babylon-viewer-container bg-surface-dark dark:bg-black rounded border border-border dark:border-border-dark"
      :style="{ width: '100%', height: '500px' }"
    >
      <!-- Show 3D mesh if generated -->
      <BabylonModelViewer
        v-if="hasMesh && meshBlobUrl"
        :url="meshBlobUrl"
        :wireframe="wireframeMode"
        :auto-rotate="autoRotate"
        :show-grid="showGrid"
        background-color="#ffffff"
        :grid-visible="false"
      />

      <!-- Show waiting message when generating -->
      <div v-else class="flex items-center justify-center h-full">
        <p class="text-text-secondary dark:text-text-secondary-dark">
          {{ isGenerating ? 'Generating 3D mesh...' : 'Generate a 3D mesh to view it here' }}
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
</style>
