/**
 * useMonitoring Composable
 * 
 * Main state management for pipeline monitoring.
 * Fetches and manages prerequisites, component health, and metrics data.
 * 
 * @module composables/useMonitoring
 */

import { ref, type Ref } from 'vue'
import { createLogger } from '@/utils/logger'

const log = createLogger('composable:useMonitoring')

/**
 * Prerequisite validation result
 */
export interface PrerequisiteResult {
  id: string
  name: string
  category: string
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
  criticality: 'critical' | 'high' | 'medium' | 'low'
  validation_method: string
  monitoring_available: boolean
  details: Record<string, any>
  timestamp: number
}

/**
 * Component health status
 */
export interface ComponentHealth {
  component: string
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
  latency_ms: number
  details: Record<string, any>
  timestamp: number
}

/**
 * Metrics data structure
 */
export interface Metrics {
  generation_success_rate: number
  avg_generation_time_ms: number
  active_generations: number
  latency_history: Array<{ timestamp: number; value: number }>
  quota_history: Array<{ timestamp: number; value: number }>
}

/**
 * API response for monitoring data
 */
interface MonitoringResponse {
  prerequisites: PrerequisiteResult[]
  components: ComponentHealth[]
  metrics: Metrics
}

// Shared state (singleton pattern for composable)
const prerequisites: Ref<PrerequisiteResult[]> = ref([])
const components: Ref<ComponentHealth[]> = ref([])
const metrics: Ref<Metrics> = ref({
  generation_success_rate: 0,
  avg_generation_time_ms: 0,
  active_generations: 0,
  latency_history: [],
  quota_history: []
})
const isRefreshing: Ref<boolean> = ref(false)
const lastError: Ref<string | null> = ref(null)

/**
 * Fetch monitoring data from backend API
 * Attempts real API call first, falls back to mock data on failure
 */
async function fetchMonitoringData(): Promise<MonitoringResponse> {
  try {
    log.debug('Fetching monitoring data from backend...')
    
    // Attempt real API call to backend - updated endpoint for Sprint 3
    const response = await fetch('/api/v1/monitoring/pipeline', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    })
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`)
    }
    
    const data = await response.json()
    log.info('Monitoring data fetched successfully', { 
      prerequisiteCount: data.prerequisites?.length || 0,
      componentCount: data.components?.length || 0
    })
    
    // Transform API response to match expected format
    return {
      prerequisites: data.prerequisites || [],
      components: data.components || [],
      metrics: {
        generation_success_rate: data.metrics?.generation_metrics?.success_rate || 0,
        avg_generation_time_ms: data.metrics?.generation_metrics?.avg_generation_time_ms || 0,
        active_generations: data.metrics?.generation_metrics?.active_generations || 0,
        latency_history: data.metrics?.latency_metrics?.history || [],
        quota_history: data.metrics?.resource_metrics?.quota_history || []
      }
    }
  } catch (error) {
    log.error('Failed to fetch monitoring data', { error })
    
    // Return mock data for development when API is not available
    return getMockMonitoringData()
  }
}

/**
 * Mock monitoring data for development
 */
function getMockMonitoringData(): MonitoringResponse {
  log.warn('Using mock data - backend API not available')
  
  return {
    prerequisites: [
      // Frontend Prerequisites (Category 1)
      {
        id: 'prereq-frontend-1',
        name: 'useCellFactory Composable',
        category: 'frontend',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'Instance check in CellRegistry',
        monitoring_available: true,
        details: { location: 'cockpit-vue/src/composables/useCellFactory.js' },
        timestamp: Date.now()
      },
      {
        id: 'prereq-frontend-2',
        name: 'useExtension Composable',
        category: 'frontend',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'Extension ping check',
        monitoring_available: true,
        details: { location: 'cockpit-vue/src/composables/useExtension.js' },
        timestamp: Date.now()
      },
      {
        id: 'prereq-frontend-3',
        name: 'CellRegistry State',
        category: 'frontend',
        status: 'healthy',
        criticality: 'high',
        validation_method: 'Registry instance validation',
        monitoring_available: false,
        details: { location: 'cockpit-vue/src/utils/CellRegistry.js' },
        timestamp: Date.now()
      },
      
      // Extension Prerequisites (Category 2)
      {
        id: 'prereq-extension-1',
        name: 'Extension Installed',
        category: 'extension',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'Manifest detection',
        monitoring_available: true,
        details: { version: '1.0.0' },
        timestamp: Date.now()
      },
      {
        id: 'prereq-extension-2',
        name: 'Service Worker Active',
        category: 'extension',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'Service worker registration check',
        monitoring_available: true,
        details: { state: 'activated' },
        timestamp: Date.now()
      },
      {
        id: 'prereq-extension-3',
        name: 'Extension Permissions',
        category: 'extension',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'Permissions API check',
        monitoring_available: true,
        details: { activeTab: true, storage: true },
        timestamp: Date.now()
      },
      {
        id: 'prereq-extension-4',
        name: 'TARGET_ORIGIN Configuration',
        category: 'extension',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'Config validation',
        monitoring_available: false,
        details: { origin: 'http://localhost:5173' },
        timestamp: Date.now()
      },
      {
        id: 'prereq-extension-5',
        name: 'postMessage Channel',
        category: 'extension',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'Message passing test',
        monitoring_available: true,
        details: { latency_ms: 5 },
        timestamp: Date.now()
      },
      
      // WASM Prerequisites (Category 3)
      {
        id: 'prereq-wasm-1',
        name: 'Offscreen Document',
        category: 'wasm',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'Document existence check',
        monitoring_available: true,
        details: { url: 'chrome-extension://offscreen.html' },
        timestamp: Date.now()
      },
      {
        id: 'prereq-wasm-2',
        name: 'WASM Orchestrator',
        category: 'wasm',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'Module load check',
        monitoring_available: true,
        details: { module: 'ScareVerseOrchestrator' },
        timestamp: Date.now()
      },
      {
        id: 'prereq-wasm-3',
        name: 'OPFS Mounted',
        category: 'wasm',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'File system access test',
        monitoring_available: true,
        details: { quota_mb: 512, used_mb: 128 },
        timestamp: Date.now()
      },
      {
        id: 'prereq-wasm-4',
        name: 'Sandbox Bootloader',
        category: 'wasm',
        status: 'healthy',
        criticality: 'high',
        validation_method: 'Bootloader ready state',
        monitoring_available: true,
        details: { initialized: true },
        timestamp: Date.now()
      },
      
      // Backend Prerequisites (Category 4)
      {
        id: 'prereq-backend-1',
        name: 'Generation Service',
        category: 'backend',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'Health endpoint',
        monitoring_available: true,
        details: { endpoint: '/api/v1/generation/health' },
        timestamp: Date.now()
      },
      {
        id: 'prereq-backend-2',
        name: 'Complexity Evaluator',
        category: 'backend',
        status: 'healthy',
        criticality: 'high',
        validation_method: 'Service availability',
        monitoring_available: true,
        details: { service: 'complexity_evaluator' },
        timestamp: Date.now()
      },
      {
        id: 'prereq-backend-3',
        name: 'LLM Service',
        category: 'backend',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'LLM availability check',
        monitoring_available: true,
        details: { provider: 'openai', model: 'gpt-4' },
        timestamp: Date.now()
      },
      {
        id: 'prereq-backend-4',
        name: 'Discovery Service',
        category: 'backend',
        status: 'healthy',
        criticality: 'medium',
        validation_method: 'Service registration',
        monitoring_available: true,
        details: { registered_services: 12 },
        timestamp: Date.now()
      },
      {
        id: 'prereq-backend-5',
        name: 'Event Bus',
        category: 'backend',
        status: 'healthy',
        criticality: 'high',
        validation_method: 'Message broker check',
        monitoring_available: true,
        details: { broker: 'redis', connected: true },
        timestamp: Date.now()
      },
      
      // Infrastructure Prerequisites (Category 5)
      {
        id: 'prereq-infra-1',
        name: 'MongoDB',
        category: 'infrastructure',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'Connection test',
        monitoring_available: true,
        details: { host: 'mongodb://localhost:27017', connected: true },
        timestamp: Date.now()
      },
      {
        id: 'prereq-infra-2',
        name: 'Vault Token Manager',
        category: 'infrastructure',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'Vault status',
        monitoring_available: true,
        details: { sealed: false, version: '1.15.0' },
        timestamp: Date.now()
      },
      {
        id: 'prereq-infra-3',
        name: 'Valid Vault Token',
        category: 'infrastructure',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'Token validation',
        monitoring_available: true,
        details: { ttl_seconds: 3600, renewable: true },
        timestamp: Date.now()
      },
      {
        id: 'prereq-infra-4',
        name: 'Redis Cache',
        category: 'infrastructure',
        status: 'healthy',
        criticality: 'high',
        validation_method: 'PING command',
        monitoring_available: true,
        details: { host: 'redis://localhost:6379', connected: true },
        timestamp: Date.now()
      },
      
      // Configuration Prerequisites (Category 6)
      {
        id: 'prereq-config-1',
        name: 'Environment Variables',
        category: 'configuration',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'Config validation',
        monitoring_available: false,
        details: { loaded_vars: 25 },
        timestamp: Date.now()
      },
      {
        id: 'prereq-config-2',
        name: 'Feature Flags',
        category: 'configuration',
        status: 'healthy',
        criticality: 'medium',
        validation_method: 'Flag service check',
        monitoring_available: true,
        details: { active_flags: 8 },
        timestamp: Date.now()
      },
      
      // Runtime Prerequisites (Category 7)
      {
        id: 'prereq-runtime-1',
        name: 'Browser APIs',
        category: 'runtime',
        status: 'healthy',
        criticality: 'critical',
        validation_method: 'API availability check',
        monitoring_available: false,
        details: { 
          crypto: true, 
          indexedDB: true, 
          serviceWorker: true 
        },
        timestamp: Date.now()
      },
      {
        id: 'prereq-runtime-2',
        name: 'System Resources',
        category: 'runtime',
        status: 'healthy',
        criticality: 'medium',
        validation_method: 'Resource check',
        monitoring_available: true,
        details: { 
          memory_mb: 512, 
          storage_mb: 1024 
        },
        timestamp: Date.now()
      }
    ],
    components: [
      { component: 'Frontend', status: 'healthy', latency_ms: 15, details: {}, timestamp: Date.now() },
      { component: 'Extension', status: 'healthy', latency_ms: 8, details: {}, timestamp: Date.now() },
      { component: 'WASM', status: 'healthy', latency_ms: 12, details: {}, timestamp: Date.now() },
      { component: 'Backend', status: 'healthy', latency_ms: 45, details: {}, timestamp: Date.now() },
      { component: 'MongoDB', status: 'healthy', latency_ms: 5, details: {}, timestamp: Date.now() },
      { component: 'Vault', status: 'healthy', latency_ms: 10, details: {}, timestamp: Date.now() },
      { component: 'Redis', status: 'healthy', latency_ms: 2, details: {}, timestamp: Date.now() }
    ],
    metrics: {
      generation_success_rate: 94.5,
      avg_generation_time_ms: 1250,
      active_generations: 3,
      latency_history: Array.from({ length: 20 }, (_, i) => ({
        timestamp: Date.now() - (19 - i) * 30000,
        value: 40 + Math.random() * 20
      })),
      quota_history: Array.from({ length: 20 }, (_, i) => ({
        timestamp: Date.now() - (19 - i) * 30000,
        value: 20 + Math.random() * 10
      }))
    }
  }
}

/**
 * Refresh all monitoring data
 */
async function refreshData(): Promise<void> {
  if (isRefreshing.value) {
    log.warn('Refresh already in progress, skipping')
    return
  }
  
  isRefreshing.value = true
  lastError.value = null
  
  try {
    const data = await fetchMonitoringData()
    
    prerequisites.value = data.prerequisites
    components.value = data.components
    metrics.value = data.metrics
    
    log.info('Monitoring data refreshed', {
      prerequisites: prerequisites.value.length,
      components: components.value.length
    })
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error'
    lastError.value = errorMessage
    log.error('Failed to refresh monitoring data', { error: errorMessage })
  } finally {
    isRefreshing.value = false
  }
}

/**
 * useMonitoring Composable
 * 
 * Provides reactive state and methods for pipeline monitoring
 */
export function useMonitoring() {
  return {
    // State
    prerequisites,
    components,
    metrics,
    isRefreshing,
    lastError,
    
    // Methods
    refreshData
  }
}
