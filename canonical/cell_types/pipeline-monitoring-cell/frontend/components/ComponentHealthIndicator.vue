<template>
  <div 
    class="health-indicator"
    :class="getHealthClass(component.status)"
    :title="getTooltipText()"
  >
    <div class="flex flex-col items-center justify-center h-full p-3">
      <div 
        class="health-icon mb-2"
        :class="getIconClass(component.status)"
      >
        <component :is="getIcon(component.status)" class="w-5 h-5" />
      </div>
      
      <span class="text-xs font-medium text-center mb-1">
        {{ component.component }}
      </span>
      
      <div class="flex items-center gap-1">
        <span 
          class="status-dot"
          :class="getDotClass(component.status)"
        />
        <span class="text-xs text-muted-foreground">
          {{ component.latency_ms }}ms
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, type PropType } from 'vue'
import type { ComponentHealth } from '../composables/useMonitoring'

// Simple SVG icon components (no external dependencies)
const CheckCircleIcon = { template: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>' }
const ExclamationTriangleIcon = { template: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>' }
const XCircleIcon = { template: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>' }
const QuestionMarkCircleIcon = { template: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" /></svg>' }

const props = defineProps({
  component: {
    type: Object as PropType<ComponentHealth>,
    required: true
  }
})

function getHealthClass(status: string): string {
  const classes: Record<string, string> = {
    healthy: 'border-success/40 bg-success/10 hover:bg-success/20',
    degraded: 'border-warning/40 bg-warning/10 hover:bg-warning/20',
    unhealthy: 'border-error/40 bg-error/10 hover:bg-error/20',
    unknown: 'border-border bg-background hover:bg-muted/20'
  }
  return classes[status] || classes.unknown
}

function getIconClass(status: string): string {
  const classes: Record<string, string> = {
    healthy: 'text-success',
    degraded: 'text-warning',
    unhealthy: 'text-error',
    unknown: 'text-muted-foreground'
  }
  return classes[status] || classes.unknown
}

function getDotClass(status: string): string {
  const classes: Record<string, string> = {
    healthy: 'bg-success',
    degraded: 'bg-warning',
    unhealthy: 'bg-error',
    unknown: 'bg-muted-foreground'
  }
  return classes[status] || classes.unknown
}

function getIcon(status: string) {
  const icons: Record<string, any> = {
    healthy: CheckCircleIcon,
    degraded: ExclamationTriangleIcon,
    unhealthy: XCircleIcon,
    unknown: QuestionMarkCircleIcon
  }
  return icons[status] || QuestionMarkCircleIcon
}

function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    healthy: 'Healthy',
    degraded: 'Degraded',
    unhealthy: 'Unhealthy',
    unknown: 'Unknown'
  }
  return labels[status] || 'Unknown'
}

function getTooltipText(): string {
  return `${props.component.component}: ${getStatusLabel(props.component.status)} (${props.component.latency_ms}ms latency)`
}
</script>

<style scoped>
.health-indicator {
  @apply border-2 rounded-lg transition-all cursor-pointer;
  min-height: 100px;
}

.health-indicator:hover {
  @apply shadow-lg transform scale-105;
}

.health-icon {
  @apply flex items-center justify-center;
}

.status-dot {
  @apply w-1.5 h-1.5 rounded-full;
}
</style>
