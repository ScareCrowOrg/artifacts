<script setup lang="ts">
/**
 * Job Status Indicator Component
 * 
 * Displays real-time job processing status with visual feedback.
 * 
 * @component
 */
import { computed } from 'vue'

const props = defineProps<{
  isGenerating: boolean
  jobStatus: string
  jobId: string | null
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
</script>

<template>
  <div
    v-if="isGenerating"
    :class="['px-4 py-3 rounded mb-4 border', statusColor]"
  >
    <div class="flex items-center gap-2">
      <div v-if="jobStatus === 'processing'" class="animate-spin h-4 w-4 border-2 border-current border-t-transparent rounded-full"></div>
      <strong>Status:</strong> {{ statusLabel }}
    </div>
    <div v-if="jobId" class="text-xs mt-1 opacity-75">Job ID: {{ jobId }}</div>
  </div>
</template>
