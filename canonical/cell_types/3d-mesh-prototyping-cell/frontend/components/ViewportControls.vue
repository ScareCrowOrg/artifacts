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
      :class="['px-4 py-2 rounded transition', autoRotate ? 'bg-primary dark:bg-primary-light hover:bg-primary-hover dark:hover:bg-primary' : 'bg-surface-elevated dark:bg-surface-dark hover:bg-surface-hover dark:hover:bg-surface']"
    >
      Auto-Rotate: {{ autoRotate ? 'ON' : 'OFF' }}
    </button>
    <button
      @click="emit('toggle-wireframe')"
      :class="['px-4 py-2 rounded transition', wireframeMode ? 'bg-primary dark:bg-primary-light hover:bg-primary-hover dark:hover:bg-primary' : 'bg-surface-elevated dark:bg-surface-dark hover:bg-surface-hover dark:hover:bg-surface']"
    >
      Wireframe: {{ wireframeMode ? 'ON' : 'OFF' }}
    </button>
    <button
      @click="emit('toggle-grid')"
      :class="['px-4 py-2 rounded transition', showGrid ? 'bg-primary dark:bg-primary-light hover:bg-primary-hover dark:hover:bg-primary' : 'bg-surface-elevated dark:bg-surface-dark hover:bg-surface-hover dark:hover:bg-surface']"
    >
      Grid: {{ showGrid ? 'ON' : 'OFF' }}
    </button>
    <button
      @click="emit('download-mesh')"
      class="px-4 py-2 bg-accent dark:bg-accent-light hover:bg-accent-dark dark:hover:bg-accent rounded transition"
    >
      Download GLB
    </button>
  </div>
</template>
