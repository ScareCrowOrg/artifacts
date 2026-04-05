/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-01-22",
 *   "theme_compliance": 98,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full"
 * }
 */
<script setup lang="ts">
/**
 * Job Status Indicator Component
 * 
 * Displays real-time job processing status with visual feedback.
 * Now includes optimization status badge to inform users about Blender processing.
 * 
 * @component
 */
import { computed } from 'vue'

const props = defineProps<{
  isGenerating: boolean
  jobStatus: string
  jobId: string | null
  blenderOptimized?: boolean | null
  blenderError?: string | null
  message?: string | null
}>()

const statusColor = computed(() => {
  switch (props.jobStatus) {
    case 'queued':
      return 'bg-warning/10 dark:bg-warning/20 border-warning text-warning dark:text-warning-light'
    case 'processing':
      return 'bg-info/10 dark:bg-info/20 border-info text-info dark:text-info-light'
    case 'completed':
      return 'bg-success/10 dark:bg-success/20 border-success text-success dark:text-success-light'
    case 'failed':
      return 'bg-error/10 dark:bg-error/20 border-error text-error dark:text-error-light'
    default:
      return 'bg-surface dark:bg-surface-dark border-border dark:border-border-dark text-text-secondary dark:text-text-secondary-dark'
  }
})

const statusLabel = computed(() => {
  switch (props.jobStatus) {
    case 'queued':
      return 'Queued'
    case 'processing':
      return 'Processing...'
    case 'completed':
      return 'Completed'
    case 'failed':
      return 'Failed'
    default:
      return 'Idle'
  }
})

const optimizationBadge = computed(() => {
  if (props.jobStatus !== 'completed') return null
  
  if (props.blenderOptimized === true) {
    return {
      label: 'Optimized',
      color: 'bg-success dark:bg-success-light text-white',
      icon: '✓',
      tooltip: 'Mesh optimized with Blender (GLB with Draco compression)'
    }
  } else if (props.blenderOptimized === false) {
    return {
      label: 'Raw Mesh',
      color: 'bg-warning dark:bg-warning-light text-white',
      icon: '⚠',
      tooltip: 'Mesh delivered without Blender optimization (OBJ format)'
    }
  }
  
  return null
})
</script>

<template>
  <div
    v-if="isGenerating"
    :class="['px-4 py-3 rounded mb-4 border', statusColor]"
  >
    <div class="flex items-center gap-2">
      <div v-if="jobStatus === 'processing'" class="animate-spin h-4 w-4 border-2 border-current border-t-transparent rounded-full"></div>
      <strong>Status:</strong> {{ statusLabel }}
      
      <!-- Optimization Status Badge -->
      <span
        v-if="optimizationBadge"
        :class="['ml-2 px-2 py-1 rounded text-xs font-semibold', optimizationBadge.color]"
        :title="optimizationBadge.tooltip"
      >
        {{ optimizationBadge.icon }} {{ optimizationBadge.label }}
      </span>
    </div>
    
    <div v-if="jobId" class="text-xs mt-1 opacity-75">Job ID: {{ jobId }}</div>
    
    <!-- Warning message if Blender failed -->
    <div v-if="message && blenderOptimized === false" class="text-xs mt-2 opacity-90 flex items-start gap-1">
      <span class="text-warning dark:text-warning-light">⚠</span>
      <span>{{ message }}</span>
    </div>
    
    <!-- Blender error details (collapsible) -->
    <details v-if="blenderError && blenderOptimized === false" class="mt-2 text-xs">
      <summary class="cursor-pointer opacity-75 hover:opacity-100">View optimization error details</summary>
      <pre class="mt-1 p-2 bg-surface-dark/30 dark:bg-black/30 rounded text-xs overflow-x-auto">{{ blenderError }}</pre>
    </details>
  </div>
</template>
