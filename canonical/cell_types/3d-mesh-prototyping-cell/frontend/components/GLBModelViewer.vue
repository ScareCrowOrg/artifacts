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
 * Uses useGLTF composable for loading and displaying GLB models.
 * Handles automatic centering, scaling, and wireframe modes.
 * 
 * FIXED: Removed top-level await to prevent TresContext error.
 * The async loading is handled by useGLTF internally.
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
// NOTE: useGLTF handles async loading internally, we don't await it at top level
// The 'scene' ref will be null until the model loads
const { scene } = useGLTF(props.url, {
  draco: true,
  decoderPath: 'https://www.gstatic.com/draco/versioned/decoders/1.5.6/'
})

/**
 * Apply wireframe mode to all meshes in the scene
 */
const applyWireframe = (enabled: boolean) => {
  if (!scene.value) return
  
  scene.value.traverse((child: any) => {
    if (child.isMesh) {
      const mesh = child as THREE.Mesh
      if (Array.isArray(mesh.material)) {
        mesh.material.forEach((mat: THREE.Material) => {
          // Type guard: wireframe only exists on certain material types
          if ('wireframe' in mat) {
            (mat as THREE.MeshStandardMaterial).wireframe = enabled
          }
        })
      } else if (mesh.material && 'wireframe' in mesh.material) {
        // Type guard: wireframe only exists on certain material types
        (mesh.material as THREE.MeshStandardMaterial).wireframe = enabled
      }
    }
  })
  
  logger.debug(`Wireframe mode: ${enabled}`)
}

// Watch for changes in both scene loading and wireframe prop
watch([scene, () => props.wireframe], ([sceneValue, wireframeValue]) => {
  if (sceneValue) {
    // Center and scale the model once loaded
    const bbox = new THREE.Box3().setFromObject(sceneValue)
    const center = bbox.getCenter(new THREE.Vector3())
    sceneValue.position.sub(center)
    
    const size = bbox.getSize(new THREE.Vector3())
    const maxDim = Math.max(size.x, size.y, size.z)
    const scale = 2 / maxDim
    sceneValue.scale.multiplyScalar(scale)
    
    logger.debug('Model centered and scaled', { scale, maxDim })
    logger.info('GLB model loaded successfully')
    
    // Apply wireframe mode
    applyWireframe(wireframeValue)
  }
})

// Cleanup on unmount
onUnmounted(() => {
  if (scene.value) {
    scene.value.traverse((child: any) => {
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
  }
  logger.debug('GLB model cleaned up')
})
</script>

<template>
  <primitive v-if="scene" :object="scene" />
</template>
