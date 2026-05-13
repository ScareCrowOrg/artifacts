/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-01-02",
 *   "theme_compliance": 92,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-05-13",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div 
    class="prerequisite-card"
    :class="getStatusClass(prerequisite.status)"
  >
    <div class="flex justify-between items-start mb-2">
      <div class="flex-1">
        <h5 class="font-medium text-sm text-foreground">
          {{ prerequisite.name }}
        </h5>
        <p class="text-xs text-muted-foreground mt-1">
          {{ prerequisite.validation_method }}
        </p>
      </div>
      
      <span 
        class="badge badge-sm ml-2"
        :class="getCriticalityClass(prerequisite.criticality)"
      >
        {{ prerequisite.criticality.toUpperCase() }}
      </span>
    </div>
    
    <div class="flex items-center justify-between mt-3">
      <div class="flex items-center gap-2">
        <span 
          class="status-indicator"
          :class="getIndicatorClass(prerequisite.status)"
        />
        <span class="text-xs font-medium">
          {{ getStatusLabel(prerequisite.status) }}
        </span>
      </div>
      
      <button
        v-if="prerequisite.status !== 'healthy'"
        @click="handleFix"
        class="btn btn-xs btn-primary"
        :disabled="!canFix"
      >
        Fix
      </button>
    </div>
    
    <!-- Details (collapsible) -->
    <Transition
      enter-active-class="transition-all duration-200"
      enter-from-class="opacity-0 max-h-0"
      enter-to-class="opacity-100 max-h-96"
      leave-active-class="transition-all duration-200"
      leave-from-class="opacity-100 max-h-96"
      leave-to-class="opacity-0 max-h-0"
    >
      <div v-if="showDetails && hasDetails" class="details-section mt-3 pt-3 border-t border-border overflow-hidden">
      <p class="text-xs text-muted-foreground mb-1">Details:</p>
      <div class="text-xs font-mono bg-background/50 rounded p-2">
        <div v-for="(value, key) in prerequisite.details" :key="key" class="detail-row">
          <span class="text-muted-foreground">{{ key }}:</span>
          <span class="ml-2">{{ formatValue(value) }}</span>
        </div>
      </div>
      </div>
    </Transition>
    
    <div class="flex justify-between items-center mt-2">
      <span class="text-xs text-muted-foreground">
        {{ formatTimestamp(prerequisite.timestamp) }}
      </span>
      
      <button
        v-if="hasDetails"
        @click="toggleDetails"
        class="text-xs text-primary hover:underline"
      >
        {{ showDetails ? 'Hide' : 'Show' }} Details
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, type PropType } from 'vue'
import type { PrerequisiteResult } from '../composables/useMonitoring'

const props = defineProps({
  prerequisite: {
    type: Object as PropType<PrerequisiteResult>,
    required: true
  }
})

const emit = defineEmits<{
  fix: [prerequisiteId: string]
}>()

const showDetails = ref(false)

const hasDetails = computed(() => 
  Object.keys(props.prerequisite.details).length > 0
)

const canFix = computed(() => 
  props.prerequisite.status === 'degraded' || props.prerequisite.status === 'unhealthy'
)

function getStatusClass(status: string): string {
  const classes: Record<string, string> = {
    healthy: 'border-success/30 bg-success/5',
    degraded: 'border-warning/30 bg-warning/5',
    unhealthy: 'border-error/30 bg-error/5',
    unknown: 'border-muted/50 bg-muted/10 opacity-75'  // More distinct for unknown
  }
  return classes[status] || classes.unknown
}

function getCriticalityClass(criticality: string): string {
  const classes: Record<string, string> = {
    critical: 'badge-error',
    high: 'badge-warning',
    medium: 'badge-info',
    low: 'badge-secondary'
  }
  return classes[criticality] || classes.medium
}

function getIndicatorClass(status: string): string {
  const classes: Record<string, string> = {
    healthy: 'bg-success',
    degraded: 'bg-warning',
    unhealthy: 'bg-error',
    unknown: 'bg-muted-foreground'
  }
  return classes[status] || classes.unknown
}

function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    healthy: 'Healthy',
    degraded: 'Degraded',
    unhealthy: 'Unhealthy',
    unknown: 'Not Validated'  // More descriptive
  }
  return labels[status] || 'Unknown'
}

function formatValue(value: any): string {
  if (typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value)
}

function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const seconds = Math.floor(diff / 1000)
  
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return date.toLocaleString()
}

function toggleDetails(): void {
  showDetails.value = !showDetails.value
}

function handleFix(): void {
  emit('fix', props.prerequisite.id)
}
</script>

<style scoped>
.prerequisite-card {
  @apply bg-surface border rounded-lg p-4 transition-all;
}

.prerequisite-card:hover {
  @apply shadow-md;
}

.badge {
  @apply px-2 py-0.5 rounded text-xs font-medium;
}

.badge-sm {
  @apply px-1.5 py-0.5 text-xs;
}

.badge-error {
  @apply bg-error/20 text-error;
}

.badge-warning {
  @apply bg-warning/20 text-warning;
}

.badge-info {
  @apply bg-info/20 text-info;
}

.badge-secondary {
  @apply bg-secondary/20 text-secondary;
}

.status-indicator {
  @apply w-2 h-2 rounded-full;
}

.detail-row {
  @apply mb-1 last:mb-0;
}
</style>
