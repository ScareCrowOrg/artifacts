/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-01-22",
 *   "i18n_validated": false,
 *   "i18n_validated_date": null,
 *   "theme_compliance": 96,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full"
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

          <!-- 3D Viewport - Babylon.js Canvas -->
          <div class="viewport-container">
            <canvas
              ref="viewportRef"
              class="w-full h-96 border rounded bg-surface-elevated dark:bg-surface-dark"
              style="display: block;"
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
import {
  Engine,
  Scene,
  ArcRotateCamera,
  HemisphericLight,
  Vector3,
  StandardMaterial,
  Color3,
  Mesh,
  MeshBuilder
} from '@babylonjs/core'
import * as earcut from 'earcut'

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

// Babylon.js refs
const viewportRef: Ref<HTMLCanvasElement | null> = ref(null)
let engine: Engine | null = null
let scene: Scene | null = null
let camera: ArcRotateCamera | null = null
let currentMesh: Mesh | null = null

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

// Initialize Babylon.js when reaching step 3
watch(currentStep, (newStep) => {
  if (newStep === 3 && viewportRef.value && !scene) {
    initBabylonJS()
  }
})

onMounted(() => {
  if (currentStep.value === 3 && viewportRef.value) {
    initBabylonJS()
  }
})

onBeforeUnmount(() => {
  cleanupBabylonJS()
})

function getStepClass(stepNumber: number): string {
  if (currentStep.value > stepNumber) {
    return 'bg-success dark:bg-success-light border-success dark:border-success-light text-white'
  } else if (currentStep.value === stepNumber) {
    return 'bg-primary dark:bg-primary-light border-primary dark:border-primary-light text-white'
  } else {
    return 'bg-surface-elevated dark:bg-surface-dark border-border dark:border-border-dark text-text-secondary dark:text-text-secondary-dark'
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

function initBabylonJS(): void {
  if (!viewportRef.value) return

  try {
    // Create engine
    engine = new Engine(viewportRef.value, true, {
      preserveDrawingBuffer: true,
      stencil: true,
    })

    // Create scene
    scene = new Scene(engine)
    scene.clearColor = new Color3(0.1, 0.1, 0.1).toColor4()

    // Create camera
    camera = new ArcRotateCamera(
      'camera',
      -Math.PI / 2,
      Math.PI / 2.5,
      100,
      Vector3.Zero(),
      scene
    )
    camera.attachControl(viewportRef.value, true)
    camera.lowerRadiusLimit = 20
    camera.upperRadiusLimit = 500
    camera.wheelPrecision = 50

    // Create lighting
    const light = new HemisphericLight('light', new Vector3(0, 1, 0), scene)
    light.intensity = 0.8

    // Add additional directional light for better depth perception
    const directionalLight = new HemisphericLight('dirLight', new Vector3(0, 1, 1), scene)
    directionalLight.intensity = 0.5

    // Start render loop
    engine.runRenderLoop(() => {
      if (scene) {
        scene.render()
      }
    })

    // Handle window resize
    window.addEventListener('resize', handleResize)

    // Load SVG and create mesh if available
    if (generatedSvg.value) {
      createMeshFromSVG(generatedSvg.value)
    }
  } catch (err) {
    console.error('Error initializing Babylon.js:', err)
    const errorMessage = err instanceof Error ? err.message : String(err)
    error.value = 'Failed to initialize 3D viewport'
  }
}

function handleResize(): void {
  if (engine) {
    engine.resize()
  }
}

function createMeshFromSVG(svgString: string): void {
  if (!scene) return

  // Remove existing mesh
  if (currentMesh) {
    currentMesh.dispose()
    currentMesh = null
  }

  try {
    // Parse SVG string to extract path data
    const parser = new DOMParser()
    const svgDoc = parser.parseFromString(svgString, 'image/svg+xml')
    const paths = svgDoc.querySelectorAll('path')

    if (paths.length === 0) {
      error.value = 'No paths found in SVG'
      return
    }

    // For simplicity, we'll create a basic extrusion from the first path
    // A more complete implementation would handle multiple paths
    const pathElement = paths[0]
    const pathData = pathElement.getAttribute('d')
    
    if (!pathData) {
      error.value = 'Invalid SVG path data'
      return
    }

    // Parse SVG path commands into polygon points
    const points = parseSVGPath(pathData)
    
    if (points.length < 3) {
      error.value = 'Insufficient points for mesh creation'
      return
    }

    // Create extruded mesh using Babylon.js ExtrudePolygon
    const polygon = MeshBuilder.ExtrudePolygon(
      'svgMesh',
      {
        shape: points,
        depth: mesh3dConfig.depth,
        sideOrientation: Mesh.DOUBLESIDE,
        // Note: Babylon.js doesn't have built-in bevel like Three.js
        // For production, would need custom bevel implementation
      },
      scene,
      earcut
    )

    // Apply material
    const material = new StandardMaterial('svgMaterial', scene)
    material.diffuseColor = new Color3(0, 1, 0) // Green color
    material.specularColor = new Color3(0.5, 0.5, 0.5)
    polygon.material = material

    // Center the mesh
    const boundingInfo = polygon.getBoundingInfo()
    const center = boundingInfo.boundingBox.centerWorld
    polygon.position = center.negate()

    currentMesh = polygon
  } catch (err) {
    console.error('Error creating mesh from SVG:', err)
    error.value = `Failed to create 3D mesh: ${err instanceof Error ? err.message : 'Unknown error'}`
  }
}

/**
 * Parse SVG path data string into Vector3 points for Babylon.js
 * This is a simplified parser - production would need a more robust implementation
 */
function parseSVGPath(pathData: string): Vector3[] {
  const points: Vector3[] = []
  const commands = pathData.match(/[MLHVCSQTAZmlhvcsqtaz][^MLHVCSQTAZmlhvcsqtaz]*/g) || []
  
  let currentX = 0
  let currentY = 0
  let startX = 0
  let startY = 0

  commands.forEach(cmd => {
    const type = cmd[0]
    const values = cmd.slice(1).trim().split(/[\s,]+/).map(parseFloat).filter(n => !isNaN(n))
    
    switch (type) {
      case 'M': // Move to absolute
        if (values.length >= 2) {
          currentX = values[0]
          currentY = values[1]
          startX = currentX
          startY = currentY
          points.push(new Vector3(currentX, currentY, 0))
        }
        break
      case 'm': // Move to relative
        if (values.length >= 2) {
          currentX += values[0]
          currentY += values[1]
          startX = currentX
          startY = currentY
          points.push(new Vector3(currentX, currentY, 0))
        }
        break
      case 'L': // Line to absolute
        for (let i = 0; i < values.length; i += 2) {
          if (i + 1 < values.length) {
            currentX = values[i]
            currentY = values[i + 1]
            points.push(new Vector3(currentX, currentY, 0))
          }
        }
        break
      case 'l': // Line to relative
        for (let i = 0; i < values.length; i += 2) {
          if (i + 1 < values.length) {
            currentX += values[i]
            currentY += values[i + 1]
            points.push(new Vector3(currentX, currentY, 0))
          }
        }
        break
      case 'H': // Horizontal line absolute
        values.forEach(x => {
          currentX = x
          points.push(new Vector3(currentX, currentY, 0))
        })
        break
      case 'h': // Horizontal line relative
        values.forEach(dx => {
          currentX += dx
          points.push(new Vector3(currentX, currentY, 0))
        })
        break
      case 'V': // Vertical line absolute
        values.forEach(y => {
          currentY = y
          points.push(new Vector3(currentX, currentY, 0))
        })
        break
      case 'v': // Vertical line relative
        values.forEach(dy => {
          currentY += dy
          points.push(new Vector3(currentX, currentY, 0))
        })
        break
      case 'Z':
      case 'z': // Close path
        if (currentX !== startX || currentY !== startY) {
          points.push(new Vector3(startX, startY, 0))
        }
        break
      // For curves (C, Q, etc.), we'd need to sample points along the curve
      // Simplified version treats them as line segments
      case 'C': // Cubic bezier absolute
        if (values.length >= 6) {
          // Just take the end point for simplicity
          currentX = values[4]
          currentY = values[5]
          points.push(new Vector3(currentX, currentY, 0))
        }
        break
      case 'c': // Cubic bezier relative
        if (values.length >= 6) {
          currentX += values[4]
          currentY += values[5]
          points.push(new Vector3(currentX, currentY, 0))
        }
        break
    }
  })

  // Normalize points to reasonable scale (SVG coordinates can be large)
  if (points.length > 0) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    points.forEach(p => {
      minX = Math.min(minX, p.x)
      minY = Math.min(minY, p.y)
      maxX = Math.max(maxX, p.x)
      maxY = Math.max(maxY, p.y)
    })
    
    const width = maxX - minX
    const height = maxY - minY
    const scale = 10 / Math.max(width, height) // Normalize to ~10 units
    const centerX = (minX + maxX) / 2
    const centerY = (minY + maxY) / 2
    
    return points.map(p => new Vector3(
      (p.x - centerX) * scale,
      (p.y - centerY) * scale,
      0
    ))
  }

  return points
}

function handleConfigChange(): void {
  if (generatedSvg.value) {
    createMeshFromSVG(generatedSvg.value)
  }
  updateCell()
}

function cleanupBabylonJS(): void {
  window.removeEventListener('resize', handleResize)
  
  if (currentMesh) {
    currentMesh.dispose()
    currentMesh = null
  }
  
  if (scene) {
    scene.dispose()
    scene = null
  }
  
  if (engine) {
    engine.dispose()
    engine = null
  }
  
  camera = null
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
