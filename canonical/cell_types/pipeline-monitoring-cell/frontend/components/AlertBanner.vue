/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-01-02",
 *   "theme_compliance": 92,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full"
 * }
 */
<template>
  <Transition
    enter-active-class="transition-all duration-300"
    enter-from-class="opacity-0 -translate-y-4"
    enter-to-class="opacity-100 translate-y-0"
    leave-active-class="transition-all duration-300"
    leave-from-class="opacity-100 translate-y-0"
    leave-to-class="opacity-0 -translate-y-4"
  >
    <div 
      v-if="alerts.length > 0"
      class="alert-banner mb-6"
      :class="getBannerClass()"
    >
    <div class="flex items-start gap-3">
      <div class="alert-icon mt-0.5">
        <component :is="getIcon()" class="w-5 h-5" />
      </div>
      
      <div class="flex-1">
        <h4 class="font-semibold text-sm mb-1">
          {{ getBannerTitle() }}
        </h4>
        
        <div class="alert-list space-y-2">
          <div 
            v-for="alert in visibleAlerts"
            :key="alert.id"
            class="alert-item"
          >
            <div class="flex justify-between items-start gap-2">
              <div class="flex-1">
                <p class="text-sm font-medium">{{ alert.title }}</p>
                <p class="text-xs text-muted-foreground mt-0.5">
                  {{ alert.message }}
                </p>
                <div v-if="alert.component || alert.prerequisiteId" class="text-xs text-muted-foreground mt-1">
                  <span v-if="alert.component">Component: {{ alert.component }}</span>
                  <span v-if="alert.prerequisiteId" class="ml-2">ID: {{ alert.prerequisiteId }}</span>
                </div>
              </div>
              
              <button
                v-if="alert.dismissible"
                @click="handleDismiss(alert.id)"
                class="btn-dismiss"
                :aria-label="`Dismiss ${alert.title}`"
              >
                <XMarkIcon class="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
        
        <div v-if="alerts.length > maxVisible" class="mt-2">
          <button
            @click="toggleShowAll"
            class="text-xs font-medium underline hover:no-underline"
          >
            {{ showAll ? 'Show Less' : `Show ${alerts.length - maxVisible} More` }}
          </button>
        </div>
      </div>
      
      <button
        v-if="allowDismissAll"
        @click="handleDismissAll"
        class="btn btn-xs btn-secondary whitespace-nowrap"
      >
        Dismiss All
      </button>
    </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, type PropType } from 'vue'
import type { Alert } from '../composables/useAlerts'

// Simple SVG icon components (no external dependencies)
const ExclamationTriangleIcon = { template: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>' }
const InformationCircleIcon = { template: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" /></svg>' }
const XCircleIcon = { template: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>' }
const XMarkIcon = { template: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>' }

const props = defineProps({
  alerts: {
    type: Array as PropType<Alert[]>,
    required: true
  },
  maxVisible: {
    type: Number,
    default: 3
  },
  allowDismissAll: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits<{
  dismiss: [alertId: string]
  dismissAll: []
}>()

const showAll = ref(false)

const visibleAlerts = computed(() => {
  if (showAll.value || props.alerts.length <= props.maxVisible) {
    return props.alerts
  }
  return props.alerts.slice(0, props.maxVisible)
})

const highestSeverity = computed(() => {
  if (props.alerts.some(a => a.severity === 'critical')) return 'critical'
  if (props.alerts.some(a => a.severity === 'warning')) return 'warning'
  return 'info'
})

function getBannerClass(): string {
  const classes: Record<string, string> = {
    critical: 'bg-error/10 border-error/30 text-error',
    warning: 'bg-warning/10 border-warning/30 text-warning',
    info: 'bg-info/10 border-info/30 text-info'
  }
  return `${classes[highestSeverity.value]} border-2 rounded-lg p-4`
}

function getIcon() {
  const icons: Record<string, any> = {
    critical: XCircleIcon,
    warning: ExclamationTriangleIcon,
    info: InformationCircleIcon
  }
  return icons[highestSeverity.value] || InformationCircleIcon
}

function getBannerTitle(): string {
  const count = props.alerts.length
  const severity = highestSeverity.value
  
  if (count === 1) {
    return `${severity.charAt(0).toUpperCase() + severity.slice(1)} Alert`
  }
  
  return `${count} ${severity.charAt(0).toUpperCase() + severity.slice(1)} Alerts`
}

function handleDismiss(alertId: string): void {
  emit('dismiss', alertId)
}

function handleDismissAll(): void {
  emit('dismissAll')
}

function toggleShowAll(): void {
  showAll.value = !showAll.value
}
</script>

<style scoped>
.alert-icon {
  @apply flex-shrink-0;
}

.alert-item {
  @apply pb-2 last:pb-0 border-b last:border-b-0;
  border-color: rgba(currentColor, 0.2);
}

.btn-dismiss {
  @apply p-1 rounded transition-colors flex-shrink-0;
  background-color: transparent;
}

.btn-dismiss:hover {
  background-color: rgba(currentColor, 0.1);
}
</style>
