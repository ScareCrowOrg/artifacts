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
 * Babylon.js Model Viewer Component - Shared Reusable Component
 * 
 * Generic 3D model viewer with configurable scene rendering and dynamic resize handling.
 * Designed for reuse across multiple cells in the modular workspace.
 * 
 * Features:
 * - Native GLB/GLTF model loading with Babylon.js SceneLoader
 * - Per-canvas engine instance for input isolation
 * - Configurable scene appearance (background color, grid visibility)
 * - Dynamic resize handling via ResizeObserver (reacts to container changes)
 * - Bulletproof resource cleanup (disposes scene, engine, removes listeners)
 * - Wireframe mode toggle
 * - Auto-rotate camera option
 * - Orbit camera controls
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
  Color3
} from '@babylonjs/core'
import { GridMaterial } from '@babylonjs/materials/grid'
import '@babylonjs/loaders/glTF'
import { createLogger } from '@/utils/logger'

const logger = createLogger('component:babylon-model-viewer')

interface Props {
  url: string
  wireframe: boolean
  autoRotate: boolean
  showGrid: boolean
  backgroundColor?: string  // Hex color format (e.g., "#ffffff"), defaults to white
  gridVisible?: boolean     // Explicit grid control (overrides showGrid for backward compatibility)
}

const props = withDefaults(defineProps<Props>(), {
  backgroundColor: '#ffffff',
  gridVisible: undefined
})

// Template refs
const canvasRef = ref<HTMLCanvasElement | null>(null)

// Babylon.js instances
let engine: Engine | null = null
let scene: Scene | null = null
let camera: ArcRotateCamera | null = null
let loadedMesh: AbstractMesh | null = null
let gridMesh: AbstractMesh | null = null
let resizeObserver: ResizeObserver | null = null

// State
const isLoading = ref(false)
const loadError = ref<string | null>(null)

/**
 * Convert hex color string to Babylon.js Color3
 * @param hex - Hex color string (e.g., "#ffffff" or "ffffff")
 * @returns Color3 instance or white as fallback
 */
const hexToColor3 = (hex: string): Color3 => {
  // Remove # if present
  const cleanHex = hex.replace('#', '')
  const result = /^([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(cleanHex)
  
  if (!result) {
    logger.warn(`Invalid hex color: ${hex}, falling back to white`)
    return new Color3(1, 1, 1)  // fallback to white
  }
  
  return new Color3(
    parseInt(result[1], 16) / 255,
    parseInt(result[2], 16) / 255,
    parseInt(result[3], 16) / 255
  )
}

/**
 * Determine if grid should be visible
 * Priority: gridVisible prop > showGrid prop
 */
const shouldShowGrid = (): boolean => {
  return props.gridVisible !== undefined ? props.gridVisible : props.showGrid
}

/**
 * Initialize Babylon.js engine and scene with configurable rendering
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

    // Create scene with configurable background
    scene = new Scene(engine)
    const bgColor = hexToColor3(props.backgroundColor || '#ffffff')
    scene.clearColor = bgColor.toColor4()

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

    // Grid only if explicitly requested
    if (shouldShowGrid()) {
      createGrid()
    }

    // Start render loop
    engine.runRenderLoop(() => {
      if (scene) {
        scene.render()
      }
    })

    // Dynamic resize handling via ResizeObserver
    if (canvasRef.value.parentElement) {
      resizeObserver = new ResizeObserver(() => {
        if (engine) {
          engine.resize()
          logger.debug('Canvas resized via ResizeObserver')
        }
      })
      resizeObserver.observe(canvasRef.value.parentElement)
    }

    // Fallback window resize listener (for cases where container doesn't resize)
    window.addEventListener('resize', handleResize)

    logger.info('Babylon.js initialized successfully', {
      backgroundColor: props.backgroundColor,
      gridVisible: shouldShowGrid()
    })
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
  
  logger.debug('Grid created')
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
    // Detect if Blob URL and force extension
    const pluginExtension = props.url.startsWith('blob:') ? '.glb' : undefined

    // DIAG [3d-mesh-guest-403-render]: Log EXACT URL being loaded into SceneLoader
    logger.debug(
      '[DIAG-3d403] Babylon SceneLoader.ImportMeshAsync: url=%s pluginExtension=%s',
      props.url, pluginExtension,
    )

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
    // DIAG [3d-mesh-guest-403-render]: Detect HTTP 403 in Babylon.js error
    const errMsg = error instanceof Error ? error.message : String(error)
    const is403 = errMsg.includes('403') || errMsg.includes('Forbidden') || errMsg.includes('FORBIDDEN')
    if (is403) {
      logger.warn(
        '[DIAG-3d403] *** HTTP 403 FORBIDDEN detected *** loading url=%s — this is the auth-proxy RBAC bug',
        props.url,
      )
    } else {
      logger.error('[DIAG-3d403] Babylon SceneLoader error for url=%s: %s', props.url, errMsg)
    }
    loadError.value = `Failed to load model: ${errMsg}`
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
 * Handle window resize (fallback)
 */
const handleResize = () => {
  if (engine) {
    engine.resize()
  }
}

/**
 * Bulletproof cleanup - disposes all resources in correct order
 */
const cleanup = () => {
  logger.info('Cleaning up Babylon.js resources')

  // Remove resize observer
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
    logger.debug('ResizeObserver disconnected')
  }

  // Remove event listeners
  window.removeEventListener('resize', handleResize)

  // Dispose all meshes
  if (loadedMesh) {
    loadedMesh.dispose()
    loadedMesh = null
  }

  if (gridMesh) {
    gridMesh.dispose()
    gridMesh = null
  }

  // Dispose scene and engine (order matters: scene before engine)
  if (scene) {
    scene.dispose()
    scene = null
  }

  if (engine) {
    engine.dispose()
    engine = null
  }

  camera = null
  
  logger.info('All resources cleaned up successfully')
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
watch(() => [props.showGrid, props.gridVisible] as const, () => {
  if (shouldShowGrid()) {
    createGrid()
  } else if (gridMesh) {
    gridMesh.dispose()
    gridMesh = null
  }
})

// Watch for background color changes
watch(() => props.backgroundColor, (newColor) => {
  if (scene && newColor) {
    const bgColor = hexToColor3(newColor)
    scene.clearColor = bgColor.toColor4()
    logger.debug(`Background color updated: ${newColor}`)
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
