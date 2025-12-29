/**
 * useHealthChecks Composable
 * 
 * Periodic health check polling with configurable interval.
 * Automatically refreshes monitoring data at specified intervals.
 * 
 * @module composables/useHealthChecks
 */

import { ref, type Ref } from 'vue'
import { useMonitoring } from './useMonitoring'
import { createLogger } from '@/utils/logger'

const log = createLogger('composable:useHealthChecks')

// Shared state
let healthCheckInterval: ReturnType<typeof setInterval> | null = null
const isPolling: Ref<boolean> = ref(false)
const pollIntervalSeconds: Ref<number> = ref(30)

/**
 * Start periodic health checks
 * 
 * @param intervalSeconds - Interval between health checks in seconds (default: 30)
 */
export function useHealthChecks(intervalSeconds: number = 30) {
  const { refreshData } = useMonitoring()
  
  pollIntervalSeconds.value = intervalSeconds
  
  /**
   * Start health check polling
   */
  function startHealthChecks(): void {
    if (isPolling.value) {
      log.warn('Health checks already running')
      return
    }
    
    log.info('Starting health checks', { intervalSeconds: pollIntervalSeconds.value })
    
    isPolling.value = true
    
    // Clear any existing interval
    if (healthCheckInterval) {
      clearInterval(healthCheckInterval)
    }
    
    // Set up new interval
    healthCheckInterval = setInterval(async () => {
      log.debug('Running periodic health check')
      await refreshData()
    }, pollIntervalSeconds.value * 1000)
  }
  
  /**
   * Stop health check polling
   */
  function stopHealthChecks(): void {
    if (!isPolling.value) {
      log.warn('Health checks not running')
      return
    }
    
    log.info('Stopping health checks')
    
    if (healthCheckInterval) {
      clearInterval(healthCheckInterval)
      healthCheckInterval = null
    }
    
    isPolling.value = false
  }
  
  /**
   * Update polling interval
   * 
   * @param newIntervalSeconds - New interval in seconds
   */
  function updateInterval(newIntervalSeconds: number): void {
    log.info('Updating health check interval', { 
      oldInterval: pollIntervalSeconds.value,
      newInterval: newIntervalSeconds
    })
    
    pollIntervalSeconds.value = newIntervalSeconds
    
    // Restart polling with new interval if currently active
    if (isPolling.value) {
      stopHealthChecks()
      startHealthChecks()
    }
  }
  
  return {
    // State
    isPolling,
    pollIntervalSeconds,
    
    // Methods
    startHealthChecks,
    stopHealthChecks,
    updateInterval
  }
}
