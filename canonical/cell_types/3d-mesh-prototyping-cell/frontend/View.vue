<script setup lang="ts">
/**
 * 3D Mesh Prototyping Cell - Main View Component (TresJS)
 * 
 * Migrated from imperative Three.js to declarative TresJS for simplified 3D rendering.
 * This component orchestrates the entire 3D mesh generation workflow with job queueing.
 * 
 * Features:
 * - Image upload for 3D reconstruction
 * - Job queueing with Redis-based status polling
 * - Declarative TresJS scene with automatic lifecycle management
 * - Async GLB loading with Suspense
 * - Reactive viewport controls
 * 
 * @component
 */

import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { TresCanvas } from '@tresjs/core'
import { OrbitControls, Grid } from '@tresjs/cientos'
import { createLogger } from '@/utils/logger'
import GLBModelViewer from './components/GLBModelViewer.vue'
import JobStatusIndicator from './components/JobStatusIndicator.vue'
import ViewportControls from './components/ViewportControls.vue'
import MeshMetadataDisplay from './components/MeshMetadataDisplay.vue'

const logger = createLogger('component:3d-mesh-prototyping-cell-tresjs')

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

// Component state - Safe reactive access with defensive defaults (ITERATION #4)
const inputImage = computed(() => {
  const imageUrl = props.cell?.initial_data?.inputImage || props.cell?.state?.inputImage || props.cell?.inputImage || ''
  console.log('[DEBUG_ITERATION_4] Computed inputImage:', imageUrl)
  return imageUrl
})

const generatedMesh = computed(() => {
  return props.cell?.initial_data?.generatedMesh || props.cell?.state?.generatedMesh || props.cell?.generatedMesh || ''
})

const meshMetadata = computed(() => {
  return props.cell?.initial_data?.meshMetadata || props.cell?.state?.meshMetadata || props.cell?.meshMetadata || null
})

const isGenerating = computed(() => {
  return props.cell?.initial_data?.isGenerating || props.cell?.state?.isGenerating || props.cell?.isGenerating || false
})

const error = computed(() => {
  return props.cell?.initial_data?.error || props.cell?.state?.error || props.cell?.error || null
})

const autoRotate = computed(() => {
  return props.cell?.initial_data?.viewportSettings?.autoRotate || 
         props.cell?.state?.viewportSettings?.autoRotate || 
         props.cell?.viewportSettings?.autoRotate || false
})

const wireframeMode = computed(() => {
  return props.cell?.initial_data?.viewportSettings?.wireframeMode || 
         props.cell?.state?.viewportSettings?.wireframeMode || 
         props.cell?.viewportSettings?.wireframeMode || false
})

const showGrid = computed(() => {
  return props.cell?.initial_data?.viewportSettings?.showGrid || 
         props.cell?.state?.viewportSettings?.showGrid || 
         props.cell?.viewportSettings?.showGrid || true
})

// Job polling
const jobId = ref<string | null>(null)
const jobStatus = ref<string>('idle')
const pollingInterval = ref<number | null>(null)
const isPolling = ref<boolean>(false) // Prevent concurrent polls

// File input
const fileInput = ref<HTMLInputElement | null>(null)

// Computed
const hasInputImage = computed(() => inputImage.value !== null && inputImage.value !== '')
const hasMesh = computed(() => generatedMesh.value !== null && generatedMesh.value !== '')
const cameraPosition = computed(() => {
  return props.cell?.initial_data?.viewportSettings?.cameraPosition || 
         props.cell?.state?.viewportSettings?.cameraPosition || 
         props.cell?.viewportSettings?.cameraPosition || [0, 0, 5]
})

/**
 * Convert base64 data URL to blob URL for GLTFLoader
 * Memoized to avoid recreating URL on every access
 */
const meshBlobUrl = computed(() => {
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
    error.value = 'Please upload a valid image file (PNG, JPG, etc.)'
    return
  }

  logger.info(`File selected: ${file.name} (${file.size} bytes)`)

  const reader = new FileReader()
  reader.onload = (e) => {
    const result = e.target?.result as string
    inputImage.value = result
    error.value = null
    logger.debug('Image loaded as base64 data URL')
  }
  reader.onerror = () => {
    error.value = 'Failed to read image file'
    logger.error('FileReader error')
  }
  reader.readAsDataURL(file)
}

/**
 * Poll job status from Redis via backend API
 * Prevents concurrent polls with isPolling flag
 */
const pollJobStatus = async (id: string) => {
  // Prevent concurrent polling
  if (isPolling.value) {
    logger.debug('Poll already in progress, skipping')
    return
  }
  
  isPolling.value = true
  
  try {
    const response = await fetch(`/api/cells/3d-job-status/${id}`, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    })

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }

    const status = await response.json()
    jobStatus.value = status.status

    logger.debug(`Job ${id} status: ${status.status}`)

    if (status.status === 'completed') {
      logger.info('Job completed, fetching result...')
      
      generatedMesh.value = status.mesh_data
      meshMetadata.value = status.metadata
      error.value = null
      
      if (pollingInterval.value) {
        clearInterval(pollingInterval.value)
        pollingInterval.value = null
      }
      
      isGenerating.value = false
      logger.info('3D mesh loaded successfully', meshMetadata.value)
      
    } else if (status.status === 'failed') {
      error.value = status.error || 'Job processing failed'
      logger.error('Job failed', error.value)
      
      if (pollingInterval.value) {
        clearInterval(pollingInterval.value)
        pollingInterval.value = null
      }
      
      isGenerating.value = false
    }
    
  } catch (err: any) {
    logger.error('Error polling job status', err)
  } finally {
    isPolling.value = false
  }
}

/**
 * Generate 3D mesh from input image (queue job to Redis)
 */
const generate3DMesh = async () => {
  if (!inputImage.value) {
    error.value = 'Please upload an image first'
    return
  }

  logger.info('Starting 3D mesh generation (queueing job)')
  isGenerating.value = true
  error.value = null
  jobStatus.value = 'queued'

  try {
    const response = await fetch('/api/cells/execute-ephemeral', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify({
        cell_type: '3d-mesh-prototyping-cell',
        input_data: {
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

    if (result.success && result.job_id) {
      jobId.value = result.job_id
      logger.info(`Job queued: ${jobId.value}`)
      
      jobStatus.value = 'processing'
      pollingInterval.value = window.setInterval(() => {
        if (jobId.value) {
          pollJobStatus(jobId.value)
        }
      }, 2000)
      
    } else {
      error.value = result.error || 'Failed to queue 3D generation job'
      logger.error('Job queueing failed', error.value)
      isGenerating.value = false
    }
  } catch (err: any) {
    logger.error('Error generating 3D mesh', err)
    error.value = `Generation error: ${err.message}`
    isGenerating.value = false
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
    error.value = 'Failed to download mesh file'
  }
}

// Toggle functions
const toggleAutoRotate = () => {
  autoRotate.value = !autoRotate.value
  logger.debug(`Auto-rotate: ${autoRotate.value}`)
}

const toggleWireframe = () => {
  wireframeMode.value = !wireframeMode.value
  logger.debug(`Wireframe mode: ${wireframeMode.value}`)
}

const toggleGrid = () => {
  showGrid.value = !showGrid.value
  logger.debug(`Grid: ${showGrid.value}`)
}

// Lifecycle
onMounted(() => {
  logger.info('3D Mesh Prototyping Cell (TresJS) mounted')
  
  // Debug check for inputImage availability (ITERATION #4)
  if (!inputImage.value) {
    console.warn('[DEBUG_ITERATION_4] inputImage is empty on mount. Cell may not have initial data yet.')
  } else {
    logger.info('inputImage available on mount:', inputImage.value)
  }
})

onUnmounted(() => {
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value)
  }
  
  // Cleanup blob URL on unmount
  if (previousBlobUrl) {
    URL.revokeObjectURL(previousBlobUrl)
    logger.debug('Revoked blob URL on unmount')
  }
  
  logger.info('3D Mesh Prototyping Cell (TresJS) unmounted')
})
</script>

<template>
  <div class="mesh-prototyping-container bg-gray-900 text-gray-100 p-6 rounded-lg">
    <h2 class="text-2xl font-bold mb-4">3D Mesh Prototyping Cell</h2>
    <p class="text-gray-400 mb-6">
      Generate volumetric 3D meshes with 360º volume from single images using AI-powered reconstruction
    </p>

    <!-- Error Display -->
    <div v-if="error" class="bg-red-900/50 border border-red-700 text-red-200 px-4 py-3 rounded mb-4">
      <strong>Error:</strong> {{ error }}
    </div>

    <!-- Job Status -->
    <JobStatusIndicator
      :is-generating="isGenerating"
      :job-status="jobStatus"
      :job-id="jobId"
    />

    <!-- Input Section -->
    <div class="mb-6">
      <label class="block text-sm font-medium mb-2">Upload Image for 3D Reconstruction</label>
      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        @change="handleFileUpload"
        class="block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-700"
        :disabled="isGenerating"
      />
      <p class="text-xs text-gray-500 mt-1">Supported formats: PNG, JPG, JPEG</p>
    </div>

    <!-- Image Preview -->
    <div v-if="hasInputImage" class="mb-6">
      <label class="block text-sm font-medium mb-2">Input Image Preview</label>
      <img
        :src="inputImage"
        alt="Input for reconstruction"
        class="max-w-xs max-h-64 rounded border border-gray-700"
      />
    </div>

    <!-- Generate Button -->
    <button
      @click="generate3DMesh"
      :disabled="!hasInputImage || isGenerating"
      class="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-semibold py-2 px-6 rounded mb-6 transition"
    >
      <span v-if="isGenerating">{{ jobStatus === 'processing' ? 'Processing...' : 'Queueing...' }}</span>
      <span v-else>Generate 3D Mesh</span>
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

    <!-- TresJS Viewport (Declarative) -->
    <TresCanvas
      v-if="hasMesh && meshBlobUrl"
      class="viewport-container bg-black rounded border border-gray-700"
      window-size
      :style="{ width: '100%', height: '500px' }"
    >
      <TresPerspectiveCamera
        :position="cameraPosition"
        :fov="50"
        :near="0.1"
        :far="1000"
      />

      <TresAmbientLight :intensity="0.6" />
      <TresDirectionalLight :position="[5, 10, 7.5]" :intensity="0.8" />

      <Grid v-if="showGrid" :size="10" :divisions="10" />

      <OrbitControls
        :auto-rotate="autoRotate"
        :auto-rotate-speed="2.0"
        :enable-damping="true"
        :damping-factor="0.05"
      />

      <Suspense>
        <template #default>
          <GLBModelViewer :url="meshBlobUrl" :wireframe="wireframeMode" />
        </template>
        <template #fallback>
          <TresMesh>
            <TresBoxGeometry :args="[0.1, 0.1, 0.1]" />
            <TresMeshBasicMaterial color="#666666" />
          </TresMesh>
        </template>
      </Suspense>
    </TresCanvas>

    <!-- Placeholder when no mesh -->
    <div
      v-else
      class="viewport-container bg-black rounded border border-gray-700 flex items-center justify-center"
      style="width: 100%; height: 500px;"
    >
      <p class="text-gray-500">Upload an image and generate a 3D mesh to view it here</p>
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
