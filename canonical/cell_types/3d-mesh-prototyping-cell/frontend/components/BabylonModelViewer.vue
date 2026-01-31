/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-01-31",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full"
 * }
 */
<script setup lang="ts">
/**
 * Babylon.js Model Viewer Component
 * 
 * Migrated from TresJS to Babylon.js for better physics integration and rendering.
 * Uses per-cell engine architecture as recommended by Babylon.js best practices.
 * 
 * Features:
 * - Native GLB/GLTF model loading with Babylon.js SceneLoader
 * - Per-canvas engine instance for input isolation
 * - Proper WebGL context management and cleanup
 * - Wireframe mode toggle
 * - Orbit camera controls
 * - Grid helper
 * 
 * @component
 */
import { ref, onMounted, onUnmounted, watch } from 'vue'
import {
  Engine,
  Scene,
  ArcRotateCamera,
  HemisphericLight,
  Vector3,
  SceneLoader,
  MeshBuilder,
  AbstractMesh,
  StandardMaterial,
  Color3
} from '@babylonjs/core'
import { GridMaterial } from '@babylonjs/materials/grid'
import '@babylonjs/loaders/glTF'
import { createLogger } from '@/utils/logger'

const logger = createLogger('component:babylon-model-viewer')

const props = defineProps<{
  url: string
  wireframe: boolean
  autoRotate: boolean
  showGrid: boolean
}>()

// Template refs
const canvasRef = ref<HTMLCanvasElement | null>(null)

// Babylon.js instances
let engine: Engine | null = null
let scene: Scene | null = null
let camera: ArcRotateCamera | null = null
let loadedMesh: AbstractMesh | null = null
let gridMesh: AbstractMesh | null = null

// State
const isLoading = ref(false)
const loadError = ref<string | null>(null)

/**
 * Initialize Babylon.js engine and scene
 */
const initBabylon = () => {
  if (!canvasRef.value) {
    logger.error('Canvas ref not available')
    return
  }

  try {
    // Create engine (per-cell instance)
    engine = new Engine(canvasRef.value, true, {
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
      5,
      Vector3.Zero(),
      scene
    )
    camera.attachControl(canvasRef.value, true)
    camera.lowerRadiusLimit = 2
    camera.upperRadiusLimit = 20
    camera.wheelPrecision = 50

    // Create lighting
    const light = new HemisphericLight('light', new Vector3(0, 1, 0), scene)
    light.intensity = 0.8

    // Create grid if enabled
    if (props.showGrid) {
      createGrid()
    }

    // Start render loop
    engine.runRenderLoop(() => {
      if (scene) {
        scene.render()
      }
    })

    // Handle window resize
    window.addEventListener('resize', handleResize)

    logger.info('Babylon.js initialized successfully')
  } catch (error) {
    logger.error('Error initializing Babylon.js:', error)
    loadError.value = 'Failed to initialize 3D engine'
  }
}

/**
 * Create grid helper
 */
const createGrid = () => {
  if (!scene) return

  // Remove existing grid if any
  if (gridMesh) {
    gridMesh.dispose()
    gridMesh = null
  }

  gridMesh = MeshBuilder.CreateGround('grid', { width: 10, height: 10 }, scene)
  const gridMaterial = new GridMaterial('gridMaterial', scene)
  gridMaterial.majorUnitFrequency = 1
  gridMaterial.minorUnitVisibility = 0.5
  gridMaterial.gridRatio = 1
  gridMaterial.backFaceCulling = false
  gridMaterial.mainColor = new Color3(1, 1, 1)
  gridMaterial.lineColor = new Color3(0.4, 0.4, 0.4)
  gridMaterial.opacity = 0.8
  gridMesh.material = gridMaterial
  gridMesh.position.y = -0.01 // Slightly below origin to avoid z-fighting
}

/**
 * Load GLB model
 */
const loadModel = async () => {
  if (!scene || !props.url) return

  // Remove existing mesh if any
  if (loadedMesh) {
    loadedMesh.dispose()
    loadedMesh = null
  }

  isLoading.value = true
  loadError.value = null

  try {
    // Detectar se é Blob URL e forçar extensão
    const pluginExtension = props.url.startsWith('blob:') ? '.glb' : undefined
    const result = await SceneLoader.ImportMeshAsync('', '', props.url, scene, undefined, pluginExtension)
    
    if (result.meshes.length === 0) {
      throw new Error('No meshes found in model')
    }

    // Get root mesh (usually first mesh or parent)
    loadedMesh = result.meshes[0]

    // Center and scale model
    const boundingInfo = loadedMesh.getHierarchyBoundingVectors(true)
    const size = boundingInfo.max.subtract(boundingInfo.min)
    const center = boundingInfo.min.add(size.scale(0.5))
    
    // Move to origin
    loadedMesh.position = center.negate()
    
    // Scale to fit in view
    const maxDim = Math.max(size.x, size.y, size.z)
    if (maxDim > 0) {
      const scale = 2 / maxDim
      loadedMesh.scaling = new Vector3(scale, scale, scale)
    }

    // Apply wireframe if enabled
    applyWireframe(props.wireframe)

    logger.info('Model loaded successfully', {
      meshCount: result.meshes.length,
      size: { x: size.x, y: size.y, z: size.z }
    })
  } catch (error) {
    logger.error('Error loading model:', error)
    loadError.value = `Failed to load model: ${error instanceof Error ? error.message : 'Unknown error'}`
  } finally {
    isLoading.value = false
  }
}

/**
 * Apply wireframe mode to all meshes
 */
const applyWireframe = (enabled: boolean) => {
  if (!loadedMesh) return

  loadedMesh.getChildMeshes().forEach((mesh) => {
    if (mesh.material) {
      mesh.material.wireframe = enabled
    }
  })

  if (loadedMesh.material) {
    loadedMesh.material.wireframe = enabled
  }

  logger.debug(`Wireframe mode: ${enabled}`)
}

/**
 * Handle window resize
 */
const handleResize = () => {
  if (engine) {
    engine.resize()
  }
}

/**
 * Cleanup Babylon.js resources
 */
const cleanup = () => {
  logger.info('Cleaning up Babylon.js resources')

  window.removeEventListener('resize', handleResize)

  if (loadedMesh) {
    loadedMesh.dispose()
    loadedMesh = null
  }

  if (gridMesh) {
    gridMesh.dispose()
    gridMesh = null
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

// Watch for URL changes to reload model
watch(() => props.url, (newUrl) => {
  if (newUrl) {
    loadModel()
  }
})

// Watch for wireframe toggle
watch(() => props.wireframe, (newValue) => {
  applyWireframe(newValue)
})

// Watch for auto-rotate toggle
watch(() => props.autoRotate, (newValue) => {
  if (camera) {
    if (newValue) {
      camera.useAutoRotationBehavior = true
      if (camera.autoRotationBehavior) {
        camera.autoRotationBehavior.idleRotationSpeed = 0.5
      }
    } else {
      camera.useAutoRotationBehavior = false
    }
  }
})

// Watch for grid toggle
watch(() => props.showGrid, (newValue) => {
  if (newValue) {
    createGrid()
  } else if (gridMesh) {
    gridMesh.dispose()
    gridMesh = null
  }
})

// Lifecycle
onMounted(() => {
  initBabylon()
  if (props.url) {
    loadModel()
  }
})

onUnmounted(() => {
  cleanup()
})
</script>

<template>
  <div class="babylon-viewer-container">
    <!-- Error State -->
    <div v-if="loadError" class="error-overlay">
      <p class="text-error dark:text-error-light">⚠️ {{ loadError }}</p>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="loading-overlay">
      <p class="text-text-secondary dark:text-text-secondary-dark">Loading 3D model...</p>
    </div>

    <!-- Canvas -->
    <canvas ref="canvasRef" class="babylon-canvas"></canvas>
  </div>
</template>

<style scoped>
.babylon-viewer-container {
  position: relative;
  width: 100%;
  height: 100%;
}

.babylon-canvas {
  width: 100%;
  height: 100%;
  display: block;
  outline: none;
}

.error-overlay,
.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.7);
  z-index: 10;
  pointer-events: none;
}

.error-overlay {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid var(--error, #ef4444);
}
</style>
