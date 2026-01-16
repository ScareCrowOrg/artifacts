<script setup lang="ts">
/**
 * 3D Mesh Prototyping Cell - Frontend View Component
 * 
 * Provides an interactive interface for generating 3D meshes from single images
 * using AI-powered reconstruction, with real-time Three.js preview.
 * 
 * Features:
 * - Image upload for 3D reconstruction
 * - Three.js viewport with GLTFLoader + DRACOLoader
 * - Viewport controls (auto-rotate, wireframe, grid)
 * - Download GLB functionality
 * - Progress indicators and error handling
 * 
 * @component
 */

import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import { createLogger } from '@/utils/logger'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js'
import aiChatService from '@/services/aiChatService'

const logger = createLogger('component:3d-mesh-prototyping-cell')

interface Props {
  cellData: {
    inputImage: string | null
    generatedMesh: string | null
    meshMetadata: Record<string, any> | null
    isGenerating: boolean
    error: string | null
    reconstructionParams: {
      targetFaces: number
      enableDracoCompression: boolean
      compressionLevel: number
      targetFileSizeMB: number
    }
    viewportSettings: {
      autoRotate: boolean
      wireframeMode: boolean
      showGrid: boolean
      cameraPosition: number[]
    }
  }
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:cellData', value: any): void
}>()

// Component state
const inputImage = ref<string | null>(props.cellData.inputImage)
const generatedMesh = ref<string | null>(props.cellData.generatedMesh)
const meshMetadata = ref<Record<string, any> | null>(props.cellData.meshMetadata)
const isGenerating = ref<boolean>(props.cellData.isGenerating)
const error = ref<string | null>(props.cellData.error)
const autoRotate = ref<boolean>(props.cellData.viewportSettings.autoRotate)
const wireframeMode = ref<boolean>(props.cellData.viewportSettings.wireframeMode)
const showGrid = ref<boolean>(props.cellData.viewportSettings.showGrid)

// Three.js references
const viewportContainer = ref<HTMLDivElement | null>(null)
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let renderer: THREE.WebGLRenderer | null = null
let controls: OrbitControls | null = null
let currentMesh: THREE.Object3D | null = null
let gridHelper: THREE.GridHelper | null = null
let animationFrameId: number | null = null

// File input
const fileInput = ref<HTMLInputElement | null>(null)

// Computed
const hasInputImage = computed(() => inputImage.value !== null && inputImage.value !== '')
const hasMesh = computed(() => generatedMesh.value !== null && generatedMesh.value !== '')

/**
 * Initialize Three.js scene, camera, renderer, and controls
 */
const initThreeJS = () => {
  if (!viewportContainer.value) {
    logger.error('Viewport container not found')
    return
  }

  logger.info('Initializing Three.js viewport')

  // Scene
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x1a1a1a) // Dark background

  // Camera
  const width = viewportContainer.value.clientWidth
  const height = viewportContainer.value.clientHeight
  camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 1000)
  camera.position.set(
    props.cellData.viewportSettings.cameraPosition[0],
    props.cellData.viewportSettings.cameraPosition[1],
    props.cellData.viewportSettings.cameraPosition[2]
  )

  // Renderer
  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(width, height)
  renderer.setPixelRatio(window.devicePixelRatio)
  viewportContainer.value.appendChild(renderer.domElement)

  // Controls
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  controls.autoRotate = autoRotate.value
  controls.autoRotateSpeed = 2.0

  // Lighting
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6)
  scene.add(ambientLight)

  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8)
  directionalLight.position.set(5, 10, 7.5)
  scene.add(directionalLight)

  // Grid Helper
  gridHelper = new THREE.GridHelper(10, 10, 0x444444, 0x222222)
  if (showGrid.value) {
    scene.add(gridHelper)
  }

  // Start animation loop
  animate()

  logger.info('Three.js viewport initialized successfully')
}

/**
 * Animation loop
 */
const animate = () => {
  animationFrameId = requestAnimationFrame(animate)

  if (controls) {
    controls.update()
  }

  if (renderer && scene && camera) {
    renderer.render(scene, camera)
  }
}

/**
 * Load and display a GLB mesh in the scene
 */
const loadMesh = async (meshData: string) => {
  if (!scene) {
    logger.error('Scene not initialized')
    return
  }

  logger.info('Loading GLB mesh into scene')

  try {
    // Remove existing mesh
    if (currentMesh) {
      scene.remove(currentMesh)
      currentMesh = null
    }

    // Initialize GLTF loader with Draco decoder
    const loader = new GLTFLoader()
    const dracoLoader = new DRACOLoader()
    dracoLoader.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/')
    loader.setDRACOLoader(dracoLoader)

    // Convert base64 data URL to blob URL for loading
    const base64Data = meshData.split(',')[1]
    const binaryData = atob(base64Data)
    const bytes = new Uint8Array(binaryData.length)
    for (let i = 0; i < binaryData.length; i++) {
      bytes[i] = binaryData.charCodeAt(i)
    }
    const blob = new Blob([bytes], { type: 'model/gltf-binary' })
    const blobUrl = URL.createObjectURL(blob)

    // Load GLB
    loader.load(
      blobUrl,
      (gltf) => {
        currentMesh = gltf.scene

        // Center the mesh
        const box = new THREE.Box3().setFromObject(currentMesh)
        const center = box.getCenter(new THREE.Vector3())
        currentMesh.position.sub(center)

        // Scale to fit viewport
        const size = box.getSize(new THREE.Vector3())
        const maxDim = Math.max(size.x, size.y, size.z)
        const scale = 2 / maxDim
        currentMesh.scale.multiplyScalar(scale)

        // Apply wireframe mode if enabled
        if (wireframeMode.value) {
          applyWireframeMode(currentMesh, true)
        }

        scene!.add(currentMesh)
        logger.info('GLB mesh loaded and added to scene')

        // Clean up blob URL
        URL.revokeObjectURL(blobUrl)
      },
      undefined,
      (err) => {
        logger.error('Error loading GLB mesh', err)
        error.value = `Failed to load 3D mesh: ${err.message}`
      }
    )
  } catch (err: any) {
    logger.error('Error processing mesh data', err)
    error.value = `Failed to process mesh: ${err.message}`
  }
}

/**
 * Apply or remove wireframe mode to all materials in a mesh
 */
const applyWireframeMode = (object: THREE.Object3D, enable: boolean) => {
  object.traverse((child) => {
    if ((child as THREE.Mesh).isMesh) {
      const mesh = child as THREE.Mesh
      if (Array.isArray(mesh.material)) {
        mesh.material.forEach((mat) => {
          mat.wireframe = enable
        })
      } else {
        mesh.material.wireframe = enable
      }
    }
  })
}

/**
 * Handle image file upload
 */
const handleFileUpload = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]

  if (!file) {
    return
  }

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
 * Generate 3D mesh from input image
 */
const generate3DMesh = async () => {
  if (!inputImage.value) {
    error.value = 'Please upload an image first'
    return
  }

  logger.info('Starting 3D mesh generation')
  isGenerating.value = true
  error.value = null

  try {
    // Call backend via execute-ephemeral endpoint
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
          reconstructionParams: props.cellData.reconstructionParams
        }
      })
    })

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`)
    }

    const result = await response.json()

    if (result.success && result.result) {
      generatedMesh.value = result.result.generatedMesh
      meshMetadata.value = result.result.meshMetadata
      error.value = null

      logger.info('3D mesh generated successfully', meshMetadata.value)

      // Load mesh into Three.js scene
      if (generatedMesh.value) {
        await loadMesh(generatedMesh.value)
      }
    } else {
      error.value = result.result?.error || 'Failed to generate 3D mesh'
      logger.error('Generation failed', error.value)
    }
  } catch (err: any) {
    logger.error('Error generating 3D mesh', err)
    error.value = `Generation error: ${err.message}`
  } finally {
    isGenerating.value = false
  }
}

/**
 * Download generated GLB mesh
 */
const downloadMesh = () => {
  if (!generatedMesh.value) {
    return
  }

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

/**
 * Toggle auto-rotate
 */
const toggleAutoRotate = () => {
  autoRotate.value = !autoRotate.value
  if (controls) {
    controls.autoRotate = autoRotate.value
  }
  logger.debug(`Auto-rotate: ${autoRotate.value}`)
}

/**
 * Toggle wireframe mode
 */
const toggleWireframe = () => {
  wireframeMode.value = !wireframeMode.value
  if (currentMesh) {
    applyWireframeMode(currentMesh, wireframeMode.value)
  }
  logger.debug(`Wireframe mode: ${wireframeMode.value}`)
}

/**
 * Toggle grid helper
 */
const toggleGrid = () => {
  showGrid.value = !showGrid.value
  if (scene && gridHelper) {
    if (showGrid.value) {
      scene.add(gridHelper)
    } else {
      scene.remove(gridHelper)
    }
  }
  logger.debug(`Grid: ${showGrid.value}`)
}

/**
 * Handle window resize
 */
const handleResize = () => {
  if (!viewportContainer.value || !camera || !renderer) {
    return
  }

  const width = viewportContainer.value.clientWidth
  const height = viewportContainer.value.clientHeight

  camera.aspect = width / height
  camera.updateProjectionMatrix()

  renderer.setSize(width, height)

  logger.debug(`Viewport resized: ${width}x${height}`)
}

// Lifecycle hooks
onMounted(() => {
  logger.info('3D Mesh Prototyping Cell mounted')
  initThreeJS()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  logger.info('3D Mesh Prototyping Cell unmounted')

  // Clean up Three.js
  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId)
  }

  if (renderer) {
    renderer.dispose()
  }

  window.removeEventListener('resize', handleResize)
})

// Watch for mesh changes
watch(() => generatedMesh.value, (newMesh) => {
  if (newMesh && scene) {
    loadMesh(newMesh)
  }
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
      <span v-if="isGenerating">Generating 3D Mesh...</span>
      <span v-else>Generate 3D Mesh</span>
    </button>

    <!-- Viewport Controls -->
    <div v-if="hasMesh" class="mb-4 flex gap-4">
      <button
        @click="toggleAutoRotate"
        :class="['px-4 py-2 rounded transition', autoRotate ? 'bg-blue-600 hover:bg-blue-700' : 'bg-gray-700 hover:bg-gray-600']"
      >
        Auto-Rotate: {{ autoRotate ? 'ON' : 'OFF' }}
      </button>
      <button
        @click="toggleWireframe"
        :class="['px-4 py-2 rounded transition', wireframeMode ? 'bg-blue-600 hover:bg-blue-700' : 'bg-gray-700 hover:bg-gray-600']"
      >
        Wireframe: {{ wireframeMode ? 'ON' : 'OFF' }}
      </button>
      <button
        @click="toggleGrid"
        :class="['px-4 py-2 rounded transition', showGrid ? 'bg-blue-600 hover:bg-blue-700' : 'bg-gray-700 hover:bg-gray-600']"
      >
        Grid: {{ showGrid ? 'ON' : 'OFF' }}
      </button>
      <button
        @click="downloadMesh"
        class="px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded transition"
      >
        Download GLB
      </button>
    </div>

    <!-- Three.js Viewport -->
    <div
      ref="viewportContainer"
      class="viewport-container bg-black rounded border border-gray-700"
      style="width: 100%; height: 500px;"
    ></div>

    <!-- Mesh Metadata -->
    <div v-if="meshMetadata" class="mt-6 bg-gray-800 p-4 rounded">
      <h3 class="text-lg font-semibold mb-2">Mesh Information</h3>
      <div class="grid grid-cols-2 gap-2 text-sm">
        <div><strong>Vertices:</strong> {{ meshMetadata.vertices?.toLocaleString() }}</div>
        <div><strong>Faces:</strong> {{ meshMetadata.faces?.toLocaleString() }}</div>
        <div><strong>File Size:</strong> {{ (meshMetadata.fileSizeBytes / 1024).toFixed(2) }} KB</div>
        <div><strong>Compression:</strong> {{ meshMetadata.compressionEnabled ? 'Enabled' : 'Disabled' }}</div>
        <div><strong>Generation Time:</strong> {{ meshMetadata.generationTimeSeconds?.toFixed(2) }}s</div>
        <div v-if="meshMetadata.note" class="col-span-2 text-yellow-400"><strong>Note:</strong> {{ meshMetadata.note }}</div>
      </div>
    </div>
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
