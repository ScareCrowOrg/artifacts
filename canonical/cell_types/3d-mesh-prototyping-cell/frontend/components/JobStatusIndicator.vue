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
      return 'bg-yellow-900/50 border-yellow-700 text-yellow-200'
    case 'processing':
      return 'bg-blue-900/50 border-blue-700 text-blue-200'
    case 'completed':
      return 'bg-green-900/50 border-green-700 text-green-200'
    case 'failed':
      return 'bg-red-900/50 border-red-700 text-red-200'
    default:
      return 'bg-gray-900/50 border-gray-700 text-gray-200'
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
      color: 'bg-emerald-600 text-white',
      icon: '✓',
      tooltip: 'Mesh optimized with Blender (GLB with Draco compression)'
    }
  } else if (props.blenderOptimized === false) {
    return {
      label: 'Raw Mesh',
      color: 'bg-amber-600 text-white',
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
      <span class="text-amber-300">⚠</span>
      <span>{{ message }}</span>
    </div>
    
    <!-- Blender error details (collapsible) -->
    <details v-if="blenderError && blenderOptimized === false" class="mt-2 text-xs">
      <summary class="cursor-pointer opacity-75 hover:opacity-100">View optimization error details</summary>
      <pre class="mt-1 p-2 bg-black/30 rounded text-xs overflow-x-auto">{{ blenderError }}</pre>
    </details>
  </div>
</template>
