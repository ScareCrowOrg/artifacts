/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-17",
 *   "console_calls_found": 4,
 *   "console_calls_migrated": 4,
 *   "migration_rate": 100,
 *   "logger_namespace": "composables:conversation-trace",
 *   "validation_status": "excellent"
 * }
 */
/**
 * useConversationTrace Composable
 * Manages conversation trace data fetching, caching, and state
 * 
 * Responsibilities:
 * - Fetch trace data from backend API
 * - Cache trace data to avoid redundant requests
 * - Manage loading and error states
 * - Format fragments for display
 * 
 * Technical naming: All functions and variables in English
 */

import { ref, computed } from 'vue'
import {
  fetchTraceByConversationId,
  formatTraceFragment,
} from '../services/tracesService'
import { createLogger } from '@/utils/logger'

const log = createLogger('composables:conversation-trace')

/**
 * Composable for managing conversation trace data
 * 
 * @returns Trace management interface
 */
export function useConversationTrace() {
  // State
  const traces = ref(new Map()) // conversationId -> trace data
  const loadingTraces = ref(new Set()) // conversationIds currently loading
  const errorTraces = ref(new Map()) // conversationId -> error message

  /**
   * Check if trace is currently loading
   * 
   * @param conversationId - Conversation identifier
   * @returns True if loading
   */
  const isTraceLoading = computed(() => (conversationId: string): boolean => {
    return loadingTraces.value.has(conversationId)
  })

  /**
   * Check if trace has an error
   * 
   * @param conversationId - Conversation identifier
   * @returns Error message or null
   */
  const getTraceError = computed(() => (conversationId: string): string | null => {
    return errorTraces.value.get(conversationId) || null
  })

  /**
   * Get trace data for a conversation
   * 
   * @param conversationId - Conversation identifier
   * @returns Trace data or null
   */
  const getTrace = computed(() => (conversationId: string): any => {
    return traces.value.get(conversationId) || null
  })

  /**
   * Fetch and cache trace data for a conversation
   * Automatically handles loading state and errors
   * 
   * @param conversationId - Conversation identifier
   * @param forceRefresh - Force refresh even if cached (default: false)
   * @returns Trace data
   */
  async function loadTrace(conversationId: string, forceRefresh = false): Promise<any> {
    // If already loading, skip
    if (loadingTraces.value.has(conversationId) && !forceRefresh) {
      log.debug('Trace already loading', { conversationId })
      return traces.value.get(conversationId)
    }

    // If cached and not forcing refresh, return cached
    if (traces.value.has(conversationId) && !forceRefresh) {
      log.debug('Returning cached trace', { conversationId })
      return traces.value.get(conversationId)
    }

    // Mark as loading
    loadingTraces.value.add(conversationId)
    errorTraces.value.delete(conversationId) // Clear previous error

    try {
      log.info('Fetching trace', { conversationId, forceRefresh })
      const traceData = await fetchTraceByConversationId(conversationId)

      // Format fragments
      if (traceData.fragments) {
        traceData.fragments = traceData.fragments.map((frag: any) => formatTraceFragment(frag))
      }

      // Cache the result
      traces.value.set(conversationId, traceData)
      log.info('Trace loaded successfully', { 
        conversationId, 
        fragmentCount: traceData.fragments?.length || 0 
      })

      return traceData
    } catch (error: any) {
      const errorMessage = error.message || 'Failed to fetch trace'
      log.error('Failed to load trace', { 
        conversationId, 
        error: errorMessage 
      })
      errorTraces.value.set(conversationId, errorMessage)
      throw error
    } finally {
      // Mark as no longer loading
      loadingTraces.value.delete(conversationId)
    }
  }

  /**
   * Clear cached trace for a conversation
   * 
   * @param conversationId - Conversation identifier
   */
  function clearTrace(conversationId: string): void {
    traces.value.delete(conversationId)
    errorTraces.value.delete(conversationId)
    log.debug('Trace cleared', { conversationId })
  }

  /**
   * Clear all cached traces
   */
  function clearAllTraces(): void {
    traces.value.clear()
    errorTraces.value.clear()
    loadingTraces.value.clear()
    log.debug('All traces cleared')
  }

  /**
   * Get formatted fragments for a conversation
   * 
   * @param conversationId - Conversation identifier
   * @returns Array of formatted fragments or empty array
   */
  const getFormattedFragments = computed(() => (conversationId: string): any[] => {
    const trace = traces.value.get(conversationId)
    return trace?.fragments || []
  })

  /**
   * Get trace metadata (excluding fragments)
   * 
   * @param conversationId - Conversation identifier
   * @returns Trace metadata or null
   */
  const getTraceMetadata = computed(() => (conversationId: string): any => {
    const trace = traces.value.get(conversationId)
    if (!trace) return null

    const { fragments, ...metadata } = trace
    return metadata
  })

  /**
   * Check if trace data exists (cached)
   * 
   * @param conversationId - Conversation identifier
   * @returns True if cached
   */
  const hasTrace = computed(() => (conversationId: string): boolean => {
    return traces.value.has(conversationId)
  })

  return {
    // State
    traces,
    loadingTraces,
    errorTraces,

    // Computed getters
    isTraceLoading,
    getTraceError,
    getTrace,
    getFormattedFragments,
    getTraceMetadata,
    hasTrace,

    // Actions
    loadTrace,
    clearTrace,
    clearAllTraces,
  }
}
