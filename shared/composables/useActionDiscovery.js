/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-24",
 *   "console_calls_found": 0,
 *   "console_calls_migrated": 0,
 *   "migration_rate": 100,
 *   "logger_namespace": "action:discovery",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Action Discovery Composable
 * 
 * Provides integration with the backend action discovery API to automatically
 * discover and manage available AgenteLab actions without manual registration.
 * 
 * Features:
 * - Automatic discovery of actions from backend
 * - Label-based action organization
 * - Caching with refresh capability
 * - Reactive state management
 * 
 * API Integration:
 * - GET /api/actions/discovery - List all labels and actions
 * - GET /api/actions/discovery?label=<name> - Get actions by label
 * - GET /api/actions/discovery?label=<name>&action=<name> - Get action details
 * - POST /api/actions/discovery/refresh - Refresh cache
 * 
 * ⚠️ INTENTIONAL SINGLETON PATTERN (Issue #1400)
 * 
 * This composable intentionally uses module-level state for global action caching.
 * Actions are discovered once from the backend and shared across all components
 * for performance and consistency.
 * 
 * Pattern: Global cache shared across all cells/components
 * 
 * DO NOT migrate to Factory-per-ID pattern - actions are global by design.
 */

import { ref, computed } from 'vue'
import { createLogger } from '@/utils/logger'
import apiService from '@/services/apiService'

const log = createLogger('action:discovery')

// Shared state across all instances
const actionsCache = ref(null)
const labelsCache = ref(null)
const isLoading = ref(false)
const lastError = ref(null)
const lastRefresh = ref(null)

/**
 * Action Discovery Composable
 * 
 * @returns {Object} Discovery API interface
 */
export function useActionDiscovery() {
  /**
   * Discover all available labels and actions
   * 
   * @returns {Promise<Object>} Labels mapping with action names
   */
  async function discoverAll() {
    log.info('[DISCOVERY] Fetching all labels and actions')
    
    // DEBUG LOG: Request details
    console.log('[ACTION_DISCOVERY] [DEBUG] discoverAll() called')
    console.log('[ACTION_DISCOVERY] [DEBUG] Fetching from: /api/actions/discovery')
    
    try {
      isLoading.value = true
      lastError.value = null
      
      const response = await apiService.fetch('/api/actions/discovery')
      
      // DEBUG LOG: Response details
      console.log('[ACTION_DISCOVERY] [DEBUG] Response received:')
      console.log('[ACTION_DISCOVERY] [DEBUG]   - Status:', response.status)
      console.log('[ACTION_DISCOVERY] [DEBUG]   - OK:', response.ok)
      console.log('[ACTION_DISCOVERY] [DEBUG]   - StatusText:', response.statusText)
      
      if (!response.ok) {
        throw new Error(`Discovery API returned ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      
      // DEBUG LOG: Response data
      console.log('[ACTION_DISCOVERY] [DEBUG] Response data:')
      console.log('[ACTION_DISCOVERY] [DEBUG]   - Full data:', JSON.stringify(data, null, 2))
      console.log('[ACTION_DISCOVERY] [DEBUG]   - data.status:', data.status)
      console.log('[ACTION_DISCOVERY] [DEBUG]   - data.labels type:', typeof data.labels)
      console.log('[ACTION_DISCOVERY] [DEBUG]   - data.labels:', data.labels)
      console.log('[ACTION_DISCOVERY] [DEBUG]   - data.total_labels:', data.total_labels)
      console.log('[ACTION_DISCOVERY] [DEBUG]   - data.total_actions:', data.total_actions)
      if (data.warnings) {
        console.log('[ACTION_DISCOVERY] [DEBUG]   - warnings:', data.warnings)
      }
      
      if (data.status !== 'ok') {
        throw new Error('Discovery API returned error status')
      }
      
      // Cache the results
      labelsCache.value = data.labels
      lastRefresh.value = new Date()
      
      // DEBUG LOG: Cache state
      console.log('[ACTION_DISCOVERY] [DEBUG] After caching:')
      console.log('[ACTION_DISCOVERY] [DEBUG]   - labelsCache.value:', labelsCache.value)
      console.log('[ACTION_DISCOVERY] [DEBUG]   - Object.keys(labelsCache.value):', Object.keys(labelsCache.value))
      
      log.success('[DISCOVERY] Loaded', {
        labels: data.total_labels,
        actions: data.total_actions
      })
      
      return data.labels
    } catch (error) {
      console.error('[ACTION_DISCOVERY] [DEBUG] Error in discoverAll:', error)
      log.error('[DISCOVERY] Failed to fetch all actions', { error: error.message })
      lastError.value = error.message
      throw error
    } finally {
      isLoading.value = false
    }
  }
  
  /**
   * Discover actions by label with parameters
   * 
   * @param {string} label - Label to filter by (e.g., 'search', 'file-operations')
   * @returns {Promise<Array>} List of actions with parameters
   */
  async function discoverByLabel(label) {
    log.info('[DISCOVERY] Fetching actions for label', { label })
    
    try {
      isLoading.value = true
      lastError.value = null
      
      const response = await apiService.fetch(`/api/actions/discovery?label=${encodeURIComponent(label)}`)
      
      if (!response.ok) {
        if (response.status === 404) {
          log.warn('[DISCOVERY] Label not found', { label })
          return []
        }
        throw new Error(`Discovery API returned ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      
      if (data.status !== 'ok') {
        throw new Error('Discovery API returned error status')
      }
      
      log.success('[DISCOVERY] Loaded actions for label', {
        label,
        count: data.count
      })
      
      return data.actions
    } catch (error) {
      log.error('[DISCOVERY] Failed to fetch actions by label', {
        label,
        error: error.message
      })
      lastError.value = error.message
      throw error
    } finally {
      isLoading.value = false
    }
  }
  
  /**
   * Discover detailed information about a specific action
   * 
   * @param {string} label - Label the action belongs to
   * @param {string} actionName - Action name
   * @returns {Promise<Object>} Complete action definition
   */
  async function discoverAction(label, actionName) {
    log.info('[DISCOVERY] Fetching action details', { label, action: actionName })
    
    try {
      isLoading.value = true
      lastError.value = null
      
      const response = await apiService.fetch(
        `/api/actions/discovery?label=${encodeURIComponent(label)}&action=${encodeURIComponent(actionName)}`
      )
      
      if (!response.ok) {
        if (response.status === 404) {
          log.warn('[DISCOVERY] Action not found', { label, action: actionName })
          return null
        }
        throw new Error(`Discovery API returned ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      
      if (data.status !== 'ok') {
        throw new Error('Discovery API returned error status')
      }
      
      log.success('[DISCOVERY] Loaded action details', {
        action: actionName,
        labels: data.action.metadata.labels
      })
      
      return data.action
    } catch (error) {
      log.error('[DISCOVERY] Failed to fetch action details', {
        label,
        action: actionName,
        error: error.message
      })
      lastError.value = error.message
      throw error
    } finally {
      isLoading.value = false
    }
  }
  
  /**
   * Refresh the discovery cache on the backend
   * 
   * @returns {Promise<Object>} Refresh result with counts
   */
  async function refreshCache() {
    log.info('[DISCOVERY] Refreshing cache')
    
    try {
      isLoading.value = true
      lastError.value = null
      
      const response = await apiService.fetch('/api/actions/discovery/refresh', {
        method: 'POST'
      })
      
      if (!response.ok) {
        throw new Error(`Refresh API returned ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
      
      if (data.status !== 'ok') {
        throw new Error('Refresh API returned error status')
      }
      
      // Clear local cache to force re-fetch
      labelsCache.value = null
      actionsCache.value = null
      lastRefresh.value = new Date()
      
      log.success('[DISCOVERY] Cache refreshed', {
        labels: data.total_labels,
        actions: data.total_actions
      })
      
      return data
    } catch (error) {
      log.error('[DISCOVERY] Failed to refresh cache', { error: error.message })
      lastError.value = error.message
      throw error
    } finally {
      isLoading.value = false
    }
  }
  
  /**
   * Get all actions grouped by label (flattened and enriched format)
   * 
   * @returns {Promise<Array>} Array of actions with label information
   */
  async function getAllActionsFlattened() {
    // DEBUG LOG: Method entry
    console.log('[ACTION_DISCOVERY] [DEBUG] getAllActionsFlattened() called')
    
    const labels = await discoverAll()
    
    // DEBUG LOG: Labels received
    console.log('[ACTION_DISCOVERY] [DEBUG] discoverAll() returned labels:')
    console.log('[ACTION_DISCOVERY] [DEBUG]   - Type:', typeof labels)
    console.log('[ACTION_DISCOVERY] [DEBUG]   - Is object:', typeof labels === 'object')
    console.log('[ACTION_DISCOVERY] [DEBUG]   - Object.keys():', Object.keys(labels))
    console.log('[ACTION_DISCOVERY] [DEBUG]   - Object.entries().length:', Object.entries(labels).length)
    
    const allActions = []
    
    // DEBUG LOG: Loop iteration
    console.log('[ACTION_DISCOVERY] [DEBUG] Starting to iterate over labels...')
    let iterationCount = 0
    
    for (const [label, actionNames] of Object.entries(labels)) {
      iterationCount++
      console.log(`[ACTION_DISCOVERY] [DEBUG] Iteration ${iterationCount}:`)
      console.log(`[ACTION_DISCOVERY] [DEBUG]   - Label: ${label}`)
      console.log(`[ACTION_DISCOVERY] [DEBUG]   - Action names: ${actionNames}`)
      
      const actions = await discoverByLabel(label)
      console.log(`[ACTION_DISCOVERY] [DEBUG]   - discoverByLabel returned ${actions.length} actions`)
      
      actions.forEach(action => {
        allActions.push({
          ...action,
          primaryLabel: label,
          allLabels: action.labels || [label]
        })
      })
    }
    
    console.log(`[ACTION_DISCOVERY] [DEBUG] Loop complete. Total iterations: ${iterationCount}`)
    console.log(`[ACTION_DISCOVERY] [DEBUG] Total actions before deduplication: ${allActions.length}`)
    
    // Remove duplicates (actions can appear in multiple labels)
    const uniqueActions = []
    const seen = new Set()
    
    for (const action of allActions) {
      if (!seen.has(action.name)) {
        seen.add(action.name)
        uniqueActions.push(action)
      }
    }
    
    console.log(`[ACTION_DISCOVERY] [DEBUG] Flattened actions after deduplication: ${uniqueActions.length}`)
    if (uniqueActions.length > 0) {
      console.log(`[ACTION_DISCOVERY] [DEBUG] Action names: ${uniqueActions.map(a => a.name).join(', ')}`)
    }
    
    log.info('[DISCOVERY] Flattened actions', { count: uniqueActions.length })
    return uniqueActions
  }
  
  // Computed properties
  const hasCache = computed(() => labelsCache.value !== null)
  const availableLabels = computed(() => {
    if (!labelsCache.value) return []
    return Object.keys(labelsCache.value).sort()
  })
  
  return {
    // State
    isLoading,
    lastError,
    lastRefresh,
    hasCache,
    availableLabels,
    
    // Methods
    discoverAll,
    discoverByLabel,
    discoverAction,
    refreshCache,
    getAllActionsFlattened
  }
}
