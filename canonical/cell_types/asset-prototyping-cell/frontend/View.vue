/**
 * @metadata {
 *   "theme_validated": false,
 *   "theme_validated_date": null,
 *   "i18n_validated": false,
 *   "i18n_validated_date": null
 * }
 */
<template>
  <div class="asset-prototyping-cell bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg p-4 shadow-sm">
    <div class="cell-header mb-4">
      <h3 class="text-lg font-semibold text-primary dark:text-primary-light">
        Asset Prototyping Cell
      </h3>
      <p class="text-sm text-text-secondary dark:text-text-secondary-dark mt-1">
        Complete pipeline: AI Generation → Vectorization → 3D Prototyping
      </p>
    </div>

    <!-- Stepper Progress -->
    <div class="stepper-progress mb-6">
      <div class="flex items-center justify-between">
        <div
          v-for="step in steps"
          :key="step.number"
          class="flex flex-col items-center flex-1"
        >
          <div
            class="step-indicator w-10 h-10 rounded-full flex items-center justify-center border-2 transition"
            :class="getStepClass(step.number)"
          >
            <span v-if="currentStep > step.number" class="text-white">✓</span>
            <span v-else>{{ step.number }}</span>
          </div>
          <span class="text-xs mt-2 text-center">{{ step.label }}</span>
        </div>
      </div>
    </div>

    <!-- Step Content -->
    <div class="cell-content space-y-4">
      <!-- Step 1: PNG Generation -->
      <div v-if="currentStep === 1" class="step-content">
        <h4 class="font-medium mb-3">Step 1: Generate PNG Image</h4>
        
        <div class="prompt-section mb-3">
          <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-2">
            Describe your asset
          </label>
          <textarea
            v-model="prompt"
            :disabled="isGenerating"
            placeholder="e.g., 'a sword with ornate handle', 'a potion bottle', 'a shield emblem'"
            class="w-full px-3 py-2 border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark rounded focus:outline-none focus:ring-2 focus:ring-primary resize-none"
            rows="3"
          />
        </div>

        <button
          :disabled="!prompt.trim() || isGenerating"
          class="px-4 py-2 bg-primary dark:bg-primary-hover text-white rounded hover:bg-primary-hover dark:hover:bg-primary-light transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          @click="handleGeneratePNG"
        >
          <svg
            v-if="isGenerating"
            class="animate-spin h-5 w-5"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          {{ isGenerating ? 'Generating...' : 'Generate PNG' }}
        </button>

        <div v-if="generatedPng" class="mt-4">
          <p class="text-sm mb-2">Generated Image:</p>
          <img
            :src="`data:image/png;base64,${generatedPng}`"
            alt="Generated PNG"
            class="max-w-md border rounded"
          />
          <button
            class="mt-3 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition"
            @click="handleApprovePNG"
          >
            Approve & Continue to Vectorization
          </button>
        </div>
      </div>

      <!-- Step 2: SVG Vectorization -->
      <div v-if="currentStep === 2" class="step-content">
        <h4 class="font-medium mb-3">Step 2: Vectorize to SVG</h4>
        
        <div v-if="selectedPng" class="mb-4">
          <p class="text-sm mb-2">Selected Image:</p>
          <img
            :src="`data:image/png;base64,${selectedPng}`"
            alt="Selected PNG"
            class="max-w-xs border rounded"
          />
        </div>

        <button
          :disabled="isVectorizing"
          class="px-4 py-2 bg-primary dark:bg-primary-hover text-white rounded hover:bg-primary-hover dark:hover:bg-primary-light transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          @click="handleVectorize"
        >
          <svg
            v-if="isVectorizing"
            class="animate-spin h-5 w-5"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          {{ isVectorizing ? 'Vectorizing...' : 'Vectorize to SVG' }}
        </button>

        <div v-if="generatedSvg" class="mt-4">
          <p class="text-sm mb-2">Vectorized SVG:</p>
          <div class="border rounded p-2 bg-white" v-html="generatedSvg" />
          <button
            class="mt-3 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition"
            @click="handleContinueTo3D"
          >
            Continue to 3D Prototyping
          </button>
        </div>
      </div>

      <!-- Step 3: 3D Prototyping -->
      <div v-if="currentStep === 3" class="step-content">
        <h4 class="font-medium mb-3">Step 3: 3D Prototyping</h4>
        
        <div class="grid grid-cols-2 gap-4">
          <!-- Controls Panel -->
          <div class="controls-panel space-y-3">
            <div>
              <label class="block text-sm mb-1">Depth</label>
              <input
                v-model.number="mesh3dConfig.depth"
                type="range"
                min="1"
                max="50"
                class="w-full"
                @input="handleConfigChange"
              />
              <span class="text-xs">{{ mesh3dConfig.depth }}</span>
            </div>

            <div>
              <label class="block text-sm mb-1">
                <input
                  v-model="mesh3dConfig.bevelEnabled"
                  type="checkbox"
                  @change="handleConfigChange"
                />
                Enable Bevel
              </label>
            </div>

            <div v-if="mesh3dConfig.bevelEnabled">
              <label class="block text-sm mb-1">Bevel Thickness</label>
              <input
                v-model.number="mesh3dConfig.bevelThickness"
                type="range"
                min="0"
                max="10"
                step="0.5"
                class="w-full"
                @input="handleConfigChange"
              />
              <span class="text-xs">{{ mesh3dConfig.bevelThickness }}</span>
            </div>

            <div v-if="mesh3dConfig.bevelEnabled">
              <label class="block text-sm mb-1">Bevel Size</label>
              <input
                v-model.number="mesh3dConfig.bevelSize"
                type="range"
                min="0"
                max="5"
                step="0.5"
                class="w-full"
                @input="handleConfigChange"
              />
              <span class="text-xs">{{ mesh3dConfig.bevelSize }}</span>
            </div>

            <div v-if="mesh3dConfig.bevelEnabled">
              <label class="block text-sm mb-1">Bevel Segments</label>
              <input
                v-model.number="mesh3dConfig.bevelSegments"
                type="range"
                min="1"
                max="10"
                class="w-full"
                @input="handleConfigChange"
              />
              <span class="text-xs">{{ mesh3dConfig.bevelSegments }}</span>
            </div>
          </div>

          <!-- 3D Viewport -->
          <div class="viewport-container">
            <div
              ref="viewportRef"
              class="w-full h-96 border rounded bg-gray-100 dark:bg-gray-800"
            />
          </div>
        </div>

        <div class="mt-4">
          <button
            class="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition"
            @click="handleExport"
          >
            Export Asset
          </button>
          <button
            class="ml-2 px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 transition"
            @click="handleReset"
          >
            Start Over
          </button>
        </div>
      </div>

      <!-- Error Display -->
      <div v-if="error" class="error-message p-3 bg-red-100 border border-red-400 text-red-700 rounded">
        {{ error }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onMounted, onBeforeUnmount, type Ref } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { SVGLoader } from 'three/examples/jsm/loaders/SVGLoader.js'

// Define props interface
interface Props {
  cell: {
    initial_data?: {
      currentStep?: number
      prompt?: string
      generatedPng?: string | null
      selectedPng?: string | null
      generatedSvg?: string | null
      mesh3dConfig?: {
        depth: number
        bevelEnabled: boolean
        bevelThickness: number
        bevelSize: number
        bevelSegments: number
      }
      isGenerating?: boolean
      isVectorizing?: boolean
      error?: string | null
      selectedModel?: string
    }
  }
}

const props = defineProps<Props>()

// Typed emits
const emit = defineEmits<{
  'update:cell': [cell: Props['cell']]
}>()

// State
const currentStep: Ref<number> = ref(props.cell.initial_data?.currentStep || 1)
const prompt: Ref<string> = ref(props.cell.initial_data?.prompt || '')
const generatedPng: Ref<string | null> = ref(props.cell.initial_data?.generatedPng || null)
const selectedPng: Ref<string | null> = ref(props.cell.initial_data?.selectedPng || null)
const generatedSvg: Ref<string | null> = ref(props.cell.initial_data?.generatedSvg || null)
const isGenerating: Ref<boolean> = ref(props.cell.initial_data?.isGenerating || false)
const isVectorizing: Ref<boolean> = ref(props.cell.initial_data?.isVectorizing || false)
const error: Ref<string | null> = ref(props.cell.initial_data?.error || null)

const mesh3dConfig = reactive(
  props.cell.initial_data?.mesh3dConfig || {
    depth: 10,
    bevelEnabled: true,
    bevelThickness: 2,
    bevelSize: 1,
    bevelSegments: 3
  }
)

// Three.js refs
const viewportRef: Ref<HTMLDivElement | null> = ref(null)
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let renderer: THREE.WebGLRenderer | null = null
let controls: OrbitControls | null = null
let currentMesh: THREE.Mesh | null = null

// Steps definition
const steps = [
  { number: 1, label: 'PNG Generation' },
  { number: 2, label: 'SVG Vectorization' },
  { number: 3, label: '3D Prototyping' }
]

// Watch for prop changes
watch(() => props.cell.initial_data, (newData) => {
  if (newData) {
    currentStep.value = newData.currentStep || 1
    prompt.value = newData.prompt || ''
    generatedPng.value = newData.generatedPng || null
    selectedPng.value = newData.selectedPng || null
    generatedSvg.value = newData.generatedSvg || null
    isGenerating.value = newData.isGenerating || false
    isVectorizing.value = newData.isVectorizing || false
    error.value = newData.error || null
    if (newData.mesh3dConfig) {
      Object.assign(mesh3dConfig, newData.mesh3dConfig)
    }
  }
}, { deep: true })

// Initialize Three.js when reaching step 3
watch(currentStep, (newStep) => {
  if (newStep === 3 && viewportRef.value && !scene) {
    initThreeJS()
  }
})

onMounted(() => {
  if (currentStep.value === 3 && viewportRef.value) {
    initThreeJS()
  }
})

onBeforeUnmount(() => {
  cleanupThreeJS()
})

function getStepClass(stepNumber: number): string {
  if (currentStep.value > stepNumber) {
    return 'bg-green-600 border-green-600 text-white'
  } else if (currentStep.value === stepNumber) {
    return 'bg-primary border-primary text-white'
  } else {
    return 'bg-gray-200 border-gray-300 text-gray-600'
  }
}

async function handleGeneratePNG(): Promise<void> {
  isGenerating.value = true
  error.value = null

  try {
    const response = await fetch('/api/cells/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cell_type: 'asset-prototyping-cell',
        cell_data: {
          currentStep: 1,
          prompt: prompt.value
        }
      })
    })

    const result = await response.json()

    if (result.success && result.image_base64) {
      generatedPng.value = result.image_base64
      updateCell()
    } else {
      error.value = result.error || 'Failed to generate PNG'
    }
  } catch (err) {
    error.value = `Generation error: ${err}`
  } finally {
    isGenerating.value = false
  }
}

function handleApprovePNG(): void {
  selectedPng.value = generatedPng.value
  currentStep.value = 2
  updateCell()
}

async function handleVectorize(): Promise<void> {
  isVectorizing.value = true
  error.value = null

  try {
    const response = await fetch('/api/cells/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cell_type: 'asset-prototyping-cell',
        cell_data: {
          currentStep: 2,
          selectedPng: selectedPng.value
        }
      })
    })

    const result = await response.json()

    if (result.success && result.svg) {
      generatedSvg.value = result.svg
      updateCell()
    } else {
      error.value = result.error || 'Failed to vectorize'
    }
  } catch (err) {
    error.value = `Vectorization error: ${err}`
  } finally {
    isVectorizing.value = false
  }
}

function handleContinueTo3D(): void {
  currentStep.value = 3
  updateCell()
}

function initThreeJS(): void {
  if (!viewportRef.value) return

  // Create scene
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0xf0f0f0)

  // Create camera
  const width = viewportRef.value.clientWidth
  const height = viewportRef.value.clientHeight
  camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000)
  camera.position.z = 100

  // Create renderer
  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(width, height)
  viewportRef.value.appendChild(renderer.domElement)

  // Add controls
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true

  // Add lights
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.5)
  scene.add(ambientLight)

  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5)
  directionalLight.position.set(0, 1, 1)
  scene.add(directionalLight)

  // Load SVG and create mesh
  if (generatedSvg.value) {
    createMeshFromSVG(generatedSvg.value)
  }

  // Start animation loop
  animate()
}

function createMeshFromSVG(svgString: string): void {
  if (!scene) return

  // Remove existing mesh
  if (currentMesh) {
    scene.remove(currentMesh)
    currentMesh.geometry.dispose()
    if (Array.isArray(currentMesh.material)) {
      currentMesh.material.forEach(m => m.dispose())
    } else {
      currentMesh.material.dispose()
    }
  }

  const loader = new SVGLoader()
  const svgData = loader.parse(svgString)

  const group = new THREE.Group()

  svgData.paths.forEach((path) => {
    const shapes = SVGLoader.createShapes(path)

    shapes.forEach((shape) => {
      const geometry = new THREE.ExtrudeGeometry(shape, {
        depth: mesh3dConfig.depth,
        bevelEnabled: mesh3dConfig.bevelEnabled,
        bevelThickness: mesh3dConfig.bevelThickness,
        bevelSize: mesh3dConfig.bevelSize,
        bevelSegments: mesh3dConfig.bevelSegments
      })

      const material = new THREE.MeshStandardMaterial({
        color: 0x00ff00,
        roughness: 0.5,
        metalness: 0.3
      })

      const mesh = new THREE.Mesh(geometry, material)
      group.add(mesh)
    })
  })

  // Center the group
  const box = new THREE.Box3().setFromObject(group)
  const center = box.getCenter(new THREE.Vector3())
  group.position.sub(center)

  scene.add(group)
  currentMesh = group as any
}

function handleConfigChange(): void {
  if (generatedSvg.value) {
    createMeshFromSVG(generatedSvg.value)
  }
  updateCell()
}

function animate(): void {
  if (!renderer || !scene || !camera || !controls) return

  requestAnimationFrame(animate)
  controls.update()
  renderer.render(scene, camera)
}

function cleanupThreeJS(): void {
  if (renderer && viewportRef.value) {
    viewportRef.value.removeChild(renderer.domElement)
    renderer.dispose()
  }
  scene = null
  camera = null
  renderer = null
  controls = null
  currentMesh = null
}

function handleExport(): void {
  error.value = 'Export functionality not yet implemented. This feature will export assets to Unity Addressables format.'
  // TODO: Implement export to Unity Addressables
}

function handleReset(): void {
  currentStep.value = 1
  prompt.value = ''
  generatedPng.value = null
  selectedPng.value = null
  generatedSvg.value = null
  error.value = null
  updateCell()
}

function updateCell(): void {
  emit('update:cell', {
    ...props.cell,
    initial_data: {
      ...props.cell.initial_data,
      currentStep: currentStep.value,
      prompt: prompt.value,
      generatedPng: generatedPng.value,
      selectedPng: selectedPng.value,
      generatedSvg: generatedSvg.value,
      mesh3dConfig: { ...mesh3dConfig },
      isGenerating: isGenerating.value,
      isVectorizing: isVectorizing.value,
      error: error.value
    }
  })
}
</script>

<style scoped>
.step-indicator {
  transition: all 0.3s ease;
}
</style>
