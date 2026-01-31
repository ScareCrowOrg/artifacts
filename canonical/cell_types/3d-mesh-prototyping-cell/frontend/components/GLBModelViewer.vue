/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-01-22",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full"
 * }
 */
<script setup lang="ts">
/**
 * GLBModel Viewer Component - Imperative Three.js-based 3D model display
 * 
 * Migrated from TresJS to imperative Three.js to support shared scene context.
 * Uses inject() to access the shared scene from DynamicWorkspace.vue
 * 
 * @component
 */
import { watch, onUnmounted, ref, onMounted } from 'vue'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js'
import { createLogger } from '@/utils/logger'
import { use3DContext } from '@/composables/use3DContext'

const logger = createLogger('component:glb-model-viewer')

const props = defineProps<{
  url: string
  wireframe: boolean
}>()

// Inject shared Three.js context
let scene: THREE.Scene | null = null
let loadedModel: THREE.Group | null = null

try {
  const context = use3DContext()
  scene = context.scene
  logger.info('Successfully injected Three.js scene')
} catch (error) {
  logger.warn('Three.js context not available - model will not be displayed', error)
}

const isLoading = ref(false)
const loadError = ref<string | null>(null)

/**
 * Apply wireframe mode to all meshes in the model
 */
const applyWireframe = (model: THREE.Group, enabled: boolean) => {
  if (!model) return
  
  model.traverse((child: any) => {
    if (child.isMesh) {
      const mesh = child as THREE.Mesh
      if (Array.isArray(mesh.material)) {
        mesh.material.forEach((mat: THREE.Material) => {
          if ('wireframe' in mat) {
            (mat as THREE.MeshStandardMaterial).wireframe = enabled
          }
        })
      } else if (mesh.material && 'wireframe' in mesh.material) {
        (mesh.material as THREE.MeshStandardMaterial).wireframe = enabled
      }
    }
  })
  
  logger.debug(`Wireframe mode: ${enabled}`)
}

/**
 * Load GLB model from URL
 */
const loadModel = async (url: string) => {
  if (!scene) {
    loadError.value = 'Three.js scene not available'
    logger.error('Cannot load model without scene context')
    return
  }

  // Remove previous model if exists
  if (loadedModel) {
    scene.remove(loadedModel)
    
    // Dispose previous model resources
    loadedModel.traverse((child: any) => {
      if (child.isMesh) {
        const mesh = child as THREE.Mesh
        if (mesh.geometry) mesh.geometry.dispose()
        if (Array.isArray(mesh.material)) {
          mesh.material.forEach(mat => mat.dispose())
        } else if (mesh.material) {
          mesh.material.dispose()
        }
      }
    })
    
    logger.debug('Previous model removed and disposed')
  }

  isLoading.value = true
  loadError.value = null

  try {
    // Setup loaders
    const loader = new GLTFLoader()
    const dracoLoader = new DRACOLoader()
    dracoLoader.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/')
    loader.setDRACOLoader(dracoLoader)

    // Load model
    const gltf = await loader.loadAsync(url)
    const model = gltf.scene

    // Center and scale the model
    const bbox = new THREE.Box3().setFromObject(model)
    const center = bbox.getCenter(new THREE.Vector3())
    model.position.sub(center)
    
    const size = bbox.getSize(new THREE.Vector3())
    const maxDim = Math.max(size.x, size.y, size.z)
    const scale = maxDim > 0 ? 2 / maxDim : 1
    model.scale.multiplyScalar(scale)

    // Apply wireframe if needed
    applyWireframe(model, props.wireframe)

    // Add to scene
    scene.add(model)
    loadedModel = model

    logger.info('GLB model loaded successfully', { scale, maxDim })
    isLoading.value = false
  } catch (error: any) {
    logger.error('Error loading GLB model:', error)
    loadError.value = `Failed to load model: ${error.message}`
    isLoading.value = false
  }
}

/**
 * Watch for URL changes and reload model
 */
watch(() => props.url, (newUrl) => {
  if (newUrl) {
    loadModel(newUrl)
  }
}, { immediate: true })

/**
 * Watch for wireframe changes
 */
watch(() => props.wireframe, (newWireframe) => {
  if (loadedModel) {
    applyWireframe(loadedModel, newWireframe)
  }
})

/**
 * Cleanup on unmount
 */
onUnmounted(() => {
  if (scene && loadedModel) {
    scene.remove(loadedModel)
    
    loadedModel.traverse((child: any) => {
      if (child.isMesh) {
        const mesh = child as THREE.Mesh
        if (mesh.geometry) mesh.geometry.dispose()
        if (Array.isArray(mesh.material)) {
          mesh.material.forEach(mat => mat.dispose())
        } else if (mesh.material) {
          mesh.material.dispose()
        }
      }
    })
    
    logger.debug('GLB model cleaned up on unmount')
  }
})
</script>

<template>
  <div class="glb-model-status">
    <!-- Error State -->
    <div v-if="loadError" class="error-message p-4 rounded bg-error/10 border border-error">
      <p class="text-error">⚠️ {{ loadError }}</p>
    </div>

    <!-- Loading State -->
    <div v-else-if="isLoading" class="loading-message p-4 rounded bg-surface dark:bg-surface-dark">
      <p class="text-text-secondary dark:text-text-secondary-dark">⏳ Loading 3D model...</p>
    </div>

    <!-- Success State (model loaded into shared scene) -->
    <div v-else-if="!loadError && !isLoading" class="success-message p-4 rounded bg-success/10 border border-success">
      <p class="text-success">✓ Model loaded in 3D workspace</p>
    </div>
  </div>
</template>

<style scoped>
.glb-model-status {
  margin-bottom: 1rem;
}

.error-message,
.loading-message,
.success-message {
  padding: 1rem;
  text-align: center;
  border-radius: 0.5rem;
}

.error-message {
  color: var(--error, #ef4444);
  background: var(--error-bg, rgba(239, 68, 68, 0.1));
  border: 1px solid var(--error, #ef4444);
}

.loading-message,
.success-message {
  color: var(--text-secondary, #6b7280);
}
</style>
