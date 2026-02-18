/**
 * useAlerts Composable
 * 
 * Alert state management with add/dismiss functionality.
 * Manages critical, warning, and info alerts for the monitoring dashboard.
 * 
 * @module composables/useAlerts
 */

import { ref, computed, type Ref, type ComputedRef } from 'vue'
import { createLogger } from '#shared/logger'

const log = createLogger('composable:useAlerts')

/**
 * Alert severity levels
 */
export type AlertSeverity = 'critical' | 'warning' | 'info'

/**
 * Alert data structure
 */
export interface Alert {
  id: string
  severity: AlertSeverity
  title: string
  message: string
  timestamp: number
  dismissible: boolean
  component?: string
  prerequisiteId?: string
}

// Shared state
const alerts: Ref<Alert[]> = ref([])
const maxAlerts: Ref<number> = ref(10)

/**
 * Generate unique alert ID
 */
function generateAlertId(): string {
  return `alert-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

/**
 * Add new alert
 * 
 * @param severity - Alert severity level
 * @param title - Alert title
 * @param message - Alert message
 * @param options - Additional alert options
 */
function addAlert(
  severity: AlertSeverity,
  title: string,
  message: string,
  options: {
    dismissible?: boolean
    component?: string
    prerequisiteId?: string
  } = {}
): string {
  const alertId = generateAlertId()
  
  const newAlert: Alert = {
    id: alertId,
    severity,
    title,
    message,
    timestamp: Date.now(),
    dismissible: options.dismissible ?? true,
    component: options.component,
    prerequisiteId: options.prerequisiteId
  }
  
  log.info('Adding alert', { 
    id: alertId, 
    severity, 
    title,
    component: options.component,
    prerequisiteId: options.prerequisiteId
  })
  
  // Add to beginning of array (most recent first)
  alerts.value.unshift(newAlert)
  
  // Trim to max alerts
  if (alerts.value.length > maxAlerts.value) {
    const removed = alerts.value.splice(maxAlerts.value)
    log.debug('Trimmed old alerts', { count: removed.length })
  }
  
  return alertId
}

/**
 * Dismiss alert by ID
 * 
 * @param alertId - ID of alert to dismiss
 */
function dismissAlert(alertId: string): void {
  const index = alerts.value.findIndex(a => a.id === alertId)
  
  if (index === -1) {
    log.warn('Alert not found', { alertId })
    return
  }
  
  const alert = alerts.value[index]
  
  if (!alert.dismissible) {
    log.warn('Alert is not dismissible', { alertId })
    return
  }
  
  log.info('Dismissing alert', { alertId, title: alert.title })
  alerts.value.splice(index, 1)
}

/**
 * Dismiss all alerts of a specific severity
 * 
 * @param severity - Severity level to dismiss
 */
function dismissAllBySeverity(severity: AlertSeverity): void {
  const count = alerts.value.filter(a => a.severity === severity && a.dismissible).length
  alerts.value = alerts.value.filter(a => a.severity !== severity || !a.dismissible)
  log.info('Dismissed alerts by severity', { severity, count })
}

/**
 * Clear all dismissible alerts
 */
function clearAllAlerts(): void {
  const count = alerts.value.filter(a => a.dismissible).length
  alerts.value = alerts.value.filter(a => !a.dismissible)
  log.info('Cleared all dismissible alerts', { count })
}

/**
 * Check if alert exists for specific component
 * 
 * @param component - Component name to check
 */
function hasAlertForComponent(component: string): boolean {
  return alerts.value.some(a => a.component === component)
}

/**
 * Check if alert exists for specific prerequisite
 * 
 * @param prerequisiteId - Prerequisite ID to check
 */
function hasAlertForPrerequisite(prerequisiteId: string): boolean {
  return alerts.value.some(a => a.prerequisiteId === prerequisiteId)
}

/**
 * useAlerts Composable
 * 
 * Provides reactive state and methods for alert management
 */
export function useAlerts() {
  // Computed properties
  const criticalAlerts: ComputedRef<Alert[]> = computed(() =>
    alerts.value.filter(a => a.severity === 'critical')
  )
  
  const warningAlerts: ComputedRef<Alert[]> = computed(() =>
    alerts.value.filter(a => a.severity === 'warning')
  )
  
  const infoAlerts: ComputedRef<Alert[]> = computed(() =>
    alerts.value.filter(a => a.severity === 'info')
  )
  
  const alertCount: ComputedRef<number> = computed(() => alerts.value.length)
  
  const criticalCount: ComputedRef<number> = computed(() => criticalAlerts.value.length)
  
  const warningCount: ComputedRef<number> = computed(() => warningAlerts.value.length)
  
  return {
    // State
    alerts,
    criticalAlerts,
    warningAlerts,
    infoAlerts,
    alertCount,
    criticalCount,
    warningCount,
    
    // Methods
    addAlert,
    dismissAlert,
    dismissAllBySeverity,
    clearAllAlerts,
    hasAlertForComponent,
    hasAlertForPrerequisite
  }
}
