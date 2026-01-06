/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-01-02",
 *   "theme_compliance": 95,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full"
 * }
 */
<template>
  <div class="pipeline-monitoring-cell bg-surface rounded-lg p-6">
    <!-- Header -->
    <div class="flex justify-between items-center mb-6">
      <div>
        <h2 class="text-2xl font-bold text-foreground">Pipeline Monitoring</h2>
        <p class="text-sm text-muted-foreground">
          Last updated: {{ formatTimestamp(lastUpdate) }}
        </p>
      </div>
      
      <div class="flex gap-2">
        <button
          @click="refreshNow"
          class="btn btn-sm btn-secondary"
          :disabled="isRefreshing"
        >
          <ArrowPathIcon 
            class="w-4 h-4 mr-1"
            :class="{ 'animate-spin': isRefreshing }" 
          />
          Refresh
        </button>
        
        <button
          @click="toggleAutoRefresh"
          class="btn btn-sm"
          :class="autoRefreshEnabled ? 'btn-primary' : 'btn-secondary'"
        >
          {{ autoRefreshEnabled ? 'Auto-Refresh ON' : 'Auto-Refresh OFF' }}
        </button>
      </div>
    </div>
    
    <!-- Alert Banner -->
    <AlertBanner
      v-if="criticalAlerts.length > 0"
      :alerts="criticalAlerts"
      @dismiss="dismissAlert"
      @dismiss-all="dismissAllAlerts"
    />
    
    <!-- Error Banner for Backend Connection -->
    <div v-if="lastError" class="alert alert-error mb-6">
      <div class="flex items-start">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 flex-shrink-0 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <div class="flex-1">
          <h3 class="font-bold text-lg mb-1">⚠️ Monitoring Backend Unavailable</h3>
          <p class="text-sm mb-2">{{ lastError }}</p>
          <p class="text-sm opacity-90">
            <strong>This monitoring cell cannot function without backend connection.</strong>
            All displayed status information would be unreliable. Please check that the backend API is running and accessible.
          </p>
        </div>
      </div>
    </div>
    
    <!-- Overall Status Cards -->
    <div class="grid grid-cols-4 gap-4 mb-6">
      <div class="stat-card">
        <div class="stat-label">Prerequisites Status</div>
        <div class="stat-value">
          {{ healthyPrerequisites }}/{{ totalPrerequisites }}
        </div>
        <div class="stat-subtitle text-success">Healthy</div>
      </div>
      
      <div class="stat-card">
        <div class="stat-label">Generation Success Rate</div>
        <div class="stat-value">{{ successRate.toFixed(1) }}%</div>
        <div class="stat-subtitle">Last 24h</div>
      </div>
      
      <div class="stat-card">
        <div class="stat-label">Avg Generation Time</div>
        <div class="stat-value">{{ avgGenerationTime.toFixed(0) }}ms</div>
        <div class="stat-subtitle">p95</div>
      </div>
      
      <div class="stat-card">
        <div class="stat-label">Active Generations</div>
        <div class="stat-value">{{ activeGenerations }}</div>
        <div class="stat-subtitle">In progress</div>
      </div>
    </div>
    
    <!-- Component Health Indicators -->
    <div class="mb-6">
      <h3 class="text-lg font-semibold mb-3">Component Health</h3>
      <div class="grid grid-cols-7 gap-3">
        <ComponentHealthIndicator
          v-for="component in components"
          :key="component.component"
          :component="component"
        />
      </div>
    </div>
    
    <!-- Prerequisites by Category -->
    <div class="mb-6">
      <h3 class="text-lg font-semibold mb-3">Prerequisites by Category</h3>
      
      <div class="space-y-4">
        <div v-for="category in categories" :key="category.id" class="category-section">
          <div class="category-header flex justify-between items-center mb-2">
            <h4 class="font-medium">
              {{ category.name }}
              <span class="text-sm text-muted-foreground">({{ category.count }})</span>
            </h4>
            <div class="category-status">
              <span class="badge" :class="getCategoryStatusClass(category)">
                {{ getCategoryStatus(category) }}
              </span>
            </div>
          </div>
          
          <div class="grid grid-cols-2 gap-3">
            <PrerequisiteCard
              v-for="prereq in category.prerequisites"
              :key="prereq.id"
              :prerequisite="prereq"
              @fix="handleFix"
            />
          </div>
        </div>
      </div>
    </div>
    
    <!-- Metrics Charts -->
    <div class="mb-6">
      <h3 class="text-lg font-semibold mb-3">Metrics Overview</h3>
      
      <div class="grid grid-cols-2 gap-4">
        <MetricsChart
          title="Latency Trends"
          :data="latencyHistory"
          metric="extension_latency_p95_ms"
          unit="ms"
        />
        
        <MetricsChart
          title="OPFS Quota Usage"
          :data="quotaHistory"
          metric="opfs_quota_used_percent"
          unit="%"
        />
      </div>
    </div>
    
    <!-- Quick Actions -->
    <QuickActions
      :available-actions="availableActions"
      @action="handleQuickAction"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, type Ref } from 'vue'
import { useMonitoring } from './composables/useMonitoring'
import { useHealthChecks } from './composables/useHealthChecks'
import { useAlerts } from './composables/useAlerts'
import { useMonitoringWebSocket } from './composables/useMonitoringWebSocket'
import PrerequisiteCard from './components/PrerequisiteCard.vue'
import ComponentHealthIndicator from './components/ComponentHealthIndicator.vue'
import MetricsChart from './components/MetricsChart.vue'
import AlertBanner from './components/AlertBanner.vue'
import QuickActions from './components/QuickActions.vue'
import { createLogger } from '@/utils/logger'

// Simple SVG icon component
const ArrowPathIcon = { template: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" /></svg>' }

const log = createLogger('cell:pipeline-monitoring')

// Define props interface
interface Props {
  cell: {
    initial_data?: {
      refresh_interval_seconds?: number
      enable_auto_refresh?: boolean
      enable_alerts?: boolean
      history_retention_count?: number
    }
  }
}

const props = defineProps<Props>()

// Typed emits
const emit = defineEmits<{
  'update:cell': [cell: Props['cell']]
}>()

// Composables
const {
  prerequisites,
  components,
  metrics,
  refreshData,
  isRefreshing,
  lastError
} = useMonitoring()

const {
  startHealthChecks,
  stopHealthChecks
} = useHealthChecks(props.cell.initial_data?.refresh_interval_seconds || 30)

const {
  alerts,
  criticalAlerts,
  dismissAlert: dismissAlertInternal,
  clearAllAlerts
} = useAlerts()

// WebSocket for real-time updates (Sprint 3)
const {
  connectionState: wsConnectionState,
  lastError: wsError,
  connect: connectWebSocket,
  disconnect: disconnectWebSocket
} = useMonitoringWebSocket()

// State
const lastUpdate: Ref<number> = ref(Date.now())
const autoRefreshEnabled: Ref<boolean> = ref(
  props.cell.initial_data?.enable_auto_refresh ?? true
)

// Computed
const totalPrerequisites = computed<number>(() => prerequisites.value.length)
const healthyPrerequisites = computed<number>(
  () => prerequisites.value.filter(p => p.status === 'healthy').length
)

const successRate = computed<number>(() => metrics.value.generation_success_rate || 0)
const avgGenerationTime = computed<number>(() => metrics.value.avg_generation_time_ms || 0)
const activeGenerations = computed<number>(() => metrics.value.active_generations || 0)

const categories = computed(() => {
  const categoryMap = new Map<string, any>()
  
  prerequisites.value.forEach(prereq => {
    if (!categoryMap.has(prereq.category)) {
      categoryMap.set(prereq.category, {
        id: prereq.category,
        name: prereq.category.charAt(0).toUpperCase() + prereq.category.slice(1),
        count: 0,
        prerequisites: []
      })
    }
    
    const category = categoryMap.get(prereq.category)!
    category.count++
    category.prerequisites.push(prereq)
  })
  
  return Array.from(categoryMap.values())
})

const latencyHistory = computed(() => metrics.value.latency_history || [])
const quotaHistory = computed(() => metrics.value.quota_history || [])

const availableActions = computed(() => [
  { 
    id: 'clear-opfs', 
    label: 'Clear OPFS Cache', 
    icon: 'trash',
    requiresConfirmation: true
  },
  { 
    id: 'restart-health-checks', 
    label: 'Restart Health Checks', 
    icon: 'refresh',
    requiresConfirmation: true
  },
  { 
    id: 'export-metrics', 
    label: 'Export Metrics', 
    icon: 'download'
  }
])

// Methods
async function refreshNow(): Promise<void> {
  log.info('Manual refresh triggered')
  await refreshData()
  lastUpdate.value = Date.now()
}

function toggleAutoRefresh(): void {
  autoRefreshEnabled.value = !autoRefreshEnabled.value
  
  log.info('Auto-refresh toggled', { enabled: autoRefreshEnabled.value })
  
  if (autoRefreshEnabled.value) {
    startHealthChecks()
  } else {
    stopHealthChecks()
  }
  
  emit('update:cell', {
    ...props.cell,
    initial_data: {
      ...props.cell.initial_data,
      enable_auto_refresh: autoRefreshEnabled.value
    }
  })
}

function dismissAlert(alertId: string): void {
  log.debug('Dismissing alert', { alertId })
  dismissAlertInternal(alertId)
}

function dismissAllAlerts(): void {
  log.info('Dismissing all alerts')
  clearAllAlerts()
}

function getCategoryStatusClass(category: any): string {
  const unhealthyCount = category.prerequisites.filter(
    (p: any) => p.status !== 'healthy'
  ).length
  
  if (unhealthyCount === 0) return 'badge-success'
  if (unhealthyCount < 3) return 'badge-warning'
  return 'badge-error'
}

function getCategoryStatus(category: any): string {
  const unhealthyCount = category.prerequisites.filter(
    (p: any) => p.status !== 'healthy'
  ).length
  
  if (unhealthyCount === 0) return 'All Healthy'
  return `${unhealthyCount} Issue${unhealthyCount > 1 ? 's' : ''}`
}

function handleFix(prerequisiteId: string): void {
  log.info('Fix requested for prerequisite', { prerequisiteId })
  // TODO: Implement fix actions based on prerequisite type
  // This would integrate with backend APIs to remediate issues
}

function handleQuickAction(actionId: string): void {
  log.info('Quick action triggered', { actionId })
  
  switch (actionId) {
    case 'clear-opfs':
      // TODO: Implement OPFS cache clearing
      log.debug('Clearing OPFS cache...')
      break
    case 'restart-health-checks':
      stopHealthChecks()
      setTimeout(() => startHealthChecks(), 100)
      log.debug('Health checks restarted')
      break
    case 'export-metrics':
      exportMetrics()
      break
    default:
      log.warn('Unknown quick action', { actionId })
  }
}

function exportMetrics(): void {
  const data = {
    prerequisites: prerequisites.value,
    components: components.value,
    metrics: metrics.value,
    timestamp: Date.now()
  }
  
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `pipeline-metrics-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
  
  log.info('Metrics exported successfully')
}

function formatTimestamp(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString()
}

// Lifecycle
onMounted(async () => {
  log.info('Pipeline Monitoring Cell mounted', {
    autoRefresh: autoRefreshEnabled.value,
    interval: props.cell.initial_data?.refresh_interval_seconds || 30
  })
  
  await refreshNow()
  
  if (autoRefreshEnabled.value) {
    startHealthChecks()
  }
  
  // Initialize WebSocket connection for real-time updates (Sprint 3)
  try {
    connectWebSocket({
      onHealthUpdate: (payload) => {
        log.debug('Received health update via WebSocket', payload)
      },
      onMetricsUpdate: (payload) => {
        log.debug('Received metrics update via WebSocket', payload)
      },
      onPrerequisiteUpdate: (payload) => {
        log.debug('Received prerequisite update via WebSocket', payload)
      },
      onAlertTriggered: (payload) => {
        log.info('Alert triggered via WebSocket', payload)
        const { addAlert } = useAlerts()
        addAlert(
          payload.severity || 'warning',
          payload.title || 'Alert',
          payload.message || 'A monitoring alert was triggered',
          {
            dismissible: true,
            ...payload.details
          }
        )
      },
      onAlertResolved: (payload) => {
        log.info('Alert resolved via WebSocket', payload)
      }
    })
    log.info('WebSocket connection initiated')
  } catch (error) {
    log.error('Failed to initialize WebSocket', { error })
  }
})

onUnmounted(() => {
  log.info('Pipeline Monitoring Cell unmounted')
  stopHealthChecks()
  disconnectWebSocket()
})
</script>

<style scoped>
.pipeline-monitoring-cell {
  min-height: 600px;
}

.stat-card {
  @apply bg-background border border-border rounded-lg p-4;
}

.stat-label {
  @apply text-sm text-muted-foreground mb-1;
}

.stat-value {
  @apply text-3xl font-bold text-foreground;
}

.stat-subtitle {
  @apply text-xs text-muted-foreground mt-1;
}

.category-section {
  @apply bg-background border border-border rounded-lg p-4;
}

.badge {
  @apply px-2 py-1 rounded text-xs font-medium;
}

.badge-success {
  @apply bg-success/20 text-success;
}

.badge-warning {
  @apply bg-warning/20 text-warning;
}

.badge-error {
  @apply bg-error/20 text-error;
}
</style>
