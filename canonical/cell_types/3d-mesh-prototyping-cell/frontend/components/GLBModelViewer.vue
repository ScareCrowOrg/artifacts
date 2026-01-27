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
 * GLBModel Viewer Component - TresJS-based 3D model display
 * 
 * Uses async useGLTF composable for loading and displaying GLB models.
 * Handles automatic centering, scaling, and wireframe modes.
 * 
 * @component
 */
import { useGLTF } from '@tresjs/cientos'
import { watch, onUnmounted } from 'vue'
import * as THREE from 'three'
import { createLogger } from '@/utils/logger'

const logger = createLogger('component:glb-model-viewer')

const props = defineProps<{
  url: string
  wireframe: boolean
}>()

// Load GLB model using TresJS composable
// v5 API uses 'state' instead of 'scene' and 'execute' instead of 'load'
const { state: scene, execute: load } = useGLTF(props.url, {
  draco: true,
  decoderPath: 'https://www.gstatic.com/draco/versioned/decoders/1.5.6/'
})

// Load model asynchronously with error handling
let loadError = null
try {
  await load()
  logger.info('GLB model loaded successfully')
} catch (error) {
  logger.error('Failed to load GLB model', error)
  loadError = error
}

// Only proceed with setup if load succeeded
if (!loadError && scene.value && scene.value.scene) {
  const bbox = new THREE.Box3().setFromObject(scene.value.scene)
  const center = bbox.getCenter(new THREE.Vector3())
  scene.value.scene.position.sub(center)
  
  const size = bbox.getSize(new THREE.Vector3())
  const maxDim = Math.max(size.x, size.y, size.z)
  const scale = 2 / maxDim
  scene.value.scene.scale.multiplyScalar(scale)
  
  logger.debug('Model centered and scaled', { scale, maxDim })
}

/**
 * Apply wireframe mode to all meshes in the scene
 */
const applyWireframe = (enabled: boolean) => {
  if (!scene.value || !scene.value.scene) return
  
  scene.value.scene.traverse((child: any) => {
    if (child.isMesh) {
      const mesh = child as unknown as THREE.Mesh
      if (Array.isArray(mesh.material)) {
        mesh.material.forEach((mat: THREE.Material) => {
          // Type guard: wireframe only exists on certain material types
          if ('wireframe' in mat) {
            (mat as THREE.MeshStandardMaterial).wireframe = enabled
          }
        })
      } else if ('wireframe' in mesh.material) {
        // Type guard: wireframe only exists on certain material types
        (mesh.material as THREE.MeshStandardMaterial).wireframe = enabled
      }
    }
  })
  
  logger.debug(`Wireframe mode: ${enabled}`)
}

// Watch for wireframe prop changes
watch(() => props.wireframe, applyWireframe, { immediate: true })

// Cleanup on unmount
onUnmounted(() => {
  if (scene.value && scene.value.scene) {
    scene.value.scene.traverse((child: any) => {
      if (child.isMesh) {
        const mesh = child as unknown as THREE.Mesh
        if (mesh.geometry) mesh.geometry.dispose()
        if (Array.isArray(mesh.material)) {
          mesh.material.forEach(mat => mat.dispose())
        } else if (mesh.material) {
          mesh.material.dispose()
        }
      }
    })
  }
  logger.debug('GLB model cleaned up')
})
</script>

<template>
  <primitive v-if="scene" :object="scene" />
</template>
