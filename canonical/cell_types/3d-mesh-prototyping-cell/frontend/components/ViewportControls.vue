<script setup lang="ts">
/**
 * Viewport Controls Component
 * 
 * Provides control buttons for 3D viewport settings (auto-rotate, wireframe, grid)
 * and mesh download functionality.
 * 
 * @component
 */
const props = defineProps<{
  autoRotate: boolean
  wireframeMode: boolean
  showGrid: boolean
  hasMesh: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle-auto-rotate'): void
  (e: 'toggle-wireframe'): void
  (e: 'toggle-grid'): void
  (e: 'download-mesh'): void
}>()
</script>

<template>
  <div v-if="hasMesh" class="mb-4 flex gap-4 flex-wrap">
    <button
      @click="emit('toggle-auto-rotate')"
      :class="['px-4 py-2 rounded transition', autoRotate ? 'bg-blue-600 hover:bg-blue-700' : 'bg-gray-700 hover:bg-gray-600']"
    >
      Auto-Rotate: {{ autoRotate ? 'ON' : 'OFF' }}
    </button>
    <button
      @click="emit('toggle-wireframe')"
      :class="['px-4 py-2 rounded transition', wireframeMode ? 'bg-blue-600 hover:bg-blue-700' : 'bg-gray-700 hover:bg-gray-600']"
    >
      Wireframe: {{ wireframeMode ? 'ON' : 'OFF' }}
    </button>
    <button
      @click="emit('toggle-grid')"
      :class="['px-4 py-2 rounded transition', showGrid ? 'bg-blue-600 hover:bg-blue-700' : 'bg-gray-700 hover:bg-gray-600']"
    >
      Grid: {{ showGrid ? 'ON' : 'OFF' }}
    </button>
    <button
      @click="emit('download-mesh')"
      class="px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded transition"
    >
      Download GLB
    </button>
  </div>
</template>
