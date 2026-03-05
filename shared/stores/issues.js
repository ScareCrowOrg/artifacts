/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-22",
 *   "console_calls_found": 37,
 *   "console_calls_migrated": 37,
 *   "migration_rate": 100,
 *   "logger_namespace": "store:issues",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Issues Store
 *
 * Manages issues dashboard state, filters, actions, and selection.
 * Centralizes state management for the Issues Dashboard with pagination,
 * filtering, SSE updates, and processing control.
 *
 * @module stores/issues
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { createLogger } from '@/utils/logger'
import {
  fetchIssues,
  fetchIssueDetails,
  startIngestion,
  processPending,
  getMonitoringInfo,
  startMonitoringLoop,
  stopMonitoringLoop,
  getProcessingInfo,
  pauseProcessingQueue,
  resumeProcessingQueue,
  createIssuesEventSource,
  createCellFragmentStream,
  createPipelineFragmentStream,
  fetchNotebookItemTypes,
  fetchPipelineItems,
  createCell as createCellService,
} from '../services/issuesService.js'

const log = createLogger('store:issues')

export const useIssuesStore = defineStore('issues', () => {
  // ============================================================================
  // State
  // ============================================================================

  // Issues data
  const issues = ref([])
  const selectedIssue = ref(null)
  const isLoading = ref(false)
  const error = ref(null)

  // Filter state
  const filterState = ref('all') // 'all', 'pendente', 'executando', 'finalizado', 'erro'

  // Pagination state
  const currentPage = ref(1)
  const itemsPerPage = ref(20)
  const totalPages = ref(0)
  const totalItems = ref(0)

  // Issue counts by status (from backend)
  const issueCounts = ref({
    pendente: 0,
    executando: 0,
    finalizado: 0,
    erro: 0,
  })

  // Processing state
  const isIngestRunning = ref(false)
  const isProcessing = ref(false)

  // Monitoring state
  const monitoringStatus = ref({
    active: false,
    polling_interval: 5,
    max_concurrent_cells: 2,
    task_running: false,
  })
  const isMonitoringLoading = ref(false)

  // Processing queue state
  const processingStatus = ref({
    paused: false,
  })
  const isProcessingLoading = ref(false)

  // SSE connections
  const eventSource = ref(null)
  const cellFragmentEventSource = ref(null)
  const pipelineEventSource = ref(null)

  // Pipeline activity feed
  const pipelineActivityFeed = ref([])

  // Notebook item types and pipeline history
  const notebookItemTypes = ref([])
  const pipelineItemsHistory = ref([])
  const isLoadingPipelineHistory = ref(false)

  // ============================================================================
  // Getters (Computed)
  // ============================================================================

  /**
   * Filtered issues (server-side filtering)
   * Since filtering is handled on the backend, this simply returns the issues array
   */
  const filteredIssues = computed(() => {
    return issues.value
  })

  /**
   * Issues grouped by state with counts
   * Returns the backend-provided counts across all pages
   */
  const issuesByState = computed(() => {
    return issueCounts.value
  })

  /**
   * Check if there are more pages available
   */
  const hasNextPage = computed(() => {
    return currentPage.value < totalPages.value
  })

  /**
   * Check if we can go to previous page
   */
  const hasPreviousPage = computed(() => {
    return currentPage.value > 1
  })

  // ============================================================================
  // Actions
  // ============================================================================

  /**
   * Load issues with pagination and optional status filtering
   *
   * @param {number} page - Page number to load (defaults to current page)
   * @param {number} limit - Items per page (defaults to itemsPerPage)
   * @returns {Promise<void>}
   */
  async function loadIssues(
    page = currentPage.value,
    limit = itemsPerPage.value,
  ) {
    isLoading.value = true
    error.value = null

    try {
      const status = filterState.value === 'all' ? null : filterState.value
      const response = await fetchIssues(page, limit, status)

      issues.value = response.items
      totalItems.value = response.total_items
      totalPages.value = response.total_pages
      currentPage.value = response.current_page
      itemsPerPage.value = response.items_per_page

      if (response.issue_counts) {
        issueCounts.value = response.issue_counts
      }
    } catch (err) {
      error.value = `Failed to load issues: ${err.message}`
      log.error('Error loading issues:', err)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Navigate to a specific page
   *
   * @param {number} pageNumber - Page number to navigate to (1-indexed)
   * @returns {Promise<void>}
   */
  async function goToPage(pageNumber) {
    if (pageNumber < 1 || pageNumber > totalPages.value) {
      log.warn(`Invalid page number: ${pageNumber}`)
      return
    }

    currentPage.value = pageNumber
    await loadIssues(pageNumber)
  }

  /**
   * Navigate to next page
   *
   * @returns {Promise<void>}
   */
  async function nextPage() {
    if (hasNextPage.value) {
      await goToPage(currentPage.value + 1)
    }
  }

  /**
   * Navigate to previous page
   *
   * @returns {Promise<void>}
   */
  async function previousPage() {
    if (hasPreviousPage.value) {
      await goToPage(currentPage.value - 1)
    }
  }

  /**
   * Load issue details
   *
   * @param {string} issueId - Issue ID
   * @returns {Promise<void>}
   */
  async function loadIssueDetails(issueId) {
    try {
      selectedIssue.value = await fetchIssueDetails(issueId)
    } catch (err) {
      error.value = `Failed to load issue details: ${err.message}`
      log.error('Error loading issue details:', err)
    }
  }

  /**
   * Select an issue
   *
   * @param {Object|null} issue - Issue to select (null to clear)
   */
  function selectIssue(issue) {
    stopFragmentStream()
    selectedIssue.value = issue

    if (issue) {
      startFragmentStream(issue.id)
      loadPipelineItemsHistory(issue.id)
    } else {
      pipelineItemsHistory.value = []
    }
  }

  /**
   * Clear issue selection
   */
  function clearSelection() {
    stopFragmentStream()
    selectedIssue.value = null
    pipelineItemsHistory.value = []
  }

  /**
   * Set filter state and reload issues
   *
   * @param {string} state - Filter state ('all', 'pendente', 'executando', 'finalizado', 'erro')
   */
  async function setFilter(state) {
    filterState.value = state
    currentPage.value = 1
    await loadIssues(1)
  }

  /**
   * Trigger ingestion process
   *
   * @param {Object} options - Ingestion options
   * @returns {Promise<Object>} Ingestion result
   */
  async function triggerIngestion(options = {}) {
    isIngestRunning.value = true
    error.value = null

    try {
      const result = await startIngestion(options)
      log.debug('Ingestion triggered:', result)
      return result
    } catch (err) {
      error.value = `Failed to trigger ingestion: ${err.message}`
      log.error('Error triggering ingestion:', err)
      throw err
    } finally {
      isIngestRunning.value = false
    }
  }

  /**
   * Process pending issues
   *
   * @returns {Promise<Object|null>} Processing result or null on 503 error
   */
  async function triggerProcessing() {
    isProcessing.value = true
    error.value = null

    try {
      const result = await processPending()
      log.debug('Processing triggered:', result)

      // Refresh issues after delay
      setTimeout(() => {
        loadIssues()
      }, 1000)

      return result
    } catch (err) {
      // Handle 503 errors gracefully (orchestrator not initialized)
      if (err.message && err.message.includes('Service Unavailable')) {
        error.value = 'Orchestrator service is not available. Please wait for the service to start.'
        log.warn('Cannot trigger processing: Orchestrator not initialized')
        return null // Don't throw for 503 - it's an expected state
      } else {
        error.value = `Failed to trigger processing: ${err.message}`
        log.error('Error triggering processing:', err)
        throw err
      }
    } finally {
      isProcessing.value = false
    }
  }

  /**
   * Load monitoring status
   *
   * @returns {Promise<Object|null>} Monitoring status
   */
  async function loadMonitoringStatus() {
    try {
      const status = await getMonitoringInfo()
      monitoringStatus.value = status
      return status
    } catch (err) {
      // Handle 503 errors gracefully (orchestrator not initialized)
      if (err.message && err.message.includes('Service Unavailable')) {
        log.warn('Orchestrator not initialized yet, monitoring status unavailable')
        monitoringStatus.value = {
          active: false,
          polling_interval: 5,
          max_concurrent_cells: 2,
          task_running: false,
        }
      } else {
        log.error('Error loading monitoring status:', err)
      }
      return null
    }
  }

  /**
   * Start monitoring loop
   *
   * @returns {Promise<Object|null>} Monitoring result or null on 503 error
   */
  async function startMonitoring() {
    isMonitoringLoading.value = true
    error.value = null

    try {
      const result = await startMonitoringLoop()
      log.debug('Monitoring started:', result)
      await loadMonitoringStatus()
      return result
    } catch (err) {
      // Handle 503 errors gracefully (orchestrator not initialized)
      if (err.message && err.message.includes('Service Unavailable')) {
        error.value = 'Orchestrator service is not available. Please wait for the service to start.'
        log.warn('Cannot start monitoring: Orchestrator not initialized')
        return null // Don't throw for 503 - it's an expected state
      } else {
        error.value = `Failed to start monitoring: ${err.message}`
        log.error('Error starting monitoring:', err)
        throw err
      }
    } finally {
      isMonitoringLoading.value = false
    }
  }

  /**
   * Stop monitoring loop
   *
   * @returns {Promise<Object|null>} Monitoring result or null on 503 error
   */
  async function stopMonitoring() {
    isMonitoringLoading.value = true
    error.value = null

    try {
      const result = await stopMonitoringLoop()
      log.debug('Monitoring stopped:', result)
      await loadMonitoringStatus()
      return result
    } catch (err) {
      // Handle 503 errors gracefully (orchestrator not initialized)
      if (err.message && err.message.includes('Service Unavailable')) {
        error.value = 'Orchestrator service is not available.'
        log.warn('Cannot stop monitoring: Orchestrator not initialized')
        return null // Don't throw for 503 - it's an expected state
      } else {
        error.value = `Failed to stop monitoring: ${err.message}`
        log.error('Error stopping monitoring:', err)
        throw err
      }
    } finally {
      isMonitoringLoading.value = false
    }
  }

  /**
   * Load processing queue status
   *
   * @returns {Promise<Object|null>} Processing status
   */
  async function loadProcessingStatus() {
    try {
      const status = await getProcessingInfo()
      processingStatus.value = status
      return status
    } catch (err) {
      // Handle 503 errors gracefully (orchestrator not initialized)
      if (err.message && err.message.includes('Service Unavailable')) {
        log.warn('Orchestrator not initialized yet, processing status unavailable')
        processingStatus.value = {
          paused: false,
        }
      } else {
        log.error('Error loading processing status:', err)
      }
      return null
    }
  }

  /**
   * Pause processing queue
   *
   * @returns {Promise<Object|null>} Processing result or null on 503 error
   */
  async function pauseProcessing() {
    isProcessingLoading.value = true
    error.value = null

    try {
      const result = await pauseProcessingQueue()
      log.debug('Processing paused:', result)
      await loadProcessingStatus()
      return result
    } catch (err) {
      // Handle 503 errors gracefully (orchestrator not initialized)
      if (err.message && err.message.includes('Service Unavailable')) {
        error.value = 'Orchestrator service is not available.'
        log.warn('Cannot pause processing: Orchestrator not initialized')
        return null // Don't throw for 503 - it's an expected state
      } else {
        error.value = `Failed to pause processing: ${err.message}`
        log.error('Error pausing processing:', err)
        throw err
      }
    } finally {
      isProcessingLoading.value = false
    }
  }

  /**
   * Resume processing queue
   *
   * @returns {Promise<Object|null>} Processing result or null on 503 error
   */
  async function resumeProcessing() {
    isProcessingLoading.value = true
    error.value = null

    try {
      const result = await resumeProcessingQueue()
      log.debug('Processing resumed:', result)
      await loadProcessingStatus()
      return result
    } catch (err) {
      // Handle 503 errors gracefully (orchestrator not initialized)
      if (err.message && err.message.includes('Service Unavailable')) {
        error.value = 'Orchestrator service is not available.'
        log.warn('Cannot resume processing: Orchestrator not initialized')
        return null // Don't throw for 503 - it's an expected state
      } else {
        error.value = `Failed to resume processing: ${err.message}`
        log.error('Error resuming processing:', err)
        throw err
      }
    } finally {
      isProcessingLoading.value = false
    }
  }

  /**
   * Load notebook item types
   *
   * @returns {Promise<void>}
   */
  async function loadNotebookItemTypes() {
    try {
      notebookItemTypes.value = await fetchNotebookItemTypes()
      log.debug(
        `[IssuesStore] Loaded ${notebookItemTypes.value.length} notebook item types`,
      )
    } catch (err) {
      log.error('Error loading notebook item types:', err)
      error.value = `Failed to load notebook item types: ${err.message}`
    }
  }

  /**
   * Load pipeline items history for a specific notebook item
   *
   * @param {string} notebookItemId - UUID of the notebook item
   * @returns {Promise<void>}
   */
  async function loadPipelineItemsHistory(notebookItemId) {
    if (!notebookItemId) {
      pipelineItemsHistory.value = []
      return
    }

    isLoadingPipelineHistory.value = true

    try {
      pipelineItemsHistory.value = await fetchPipelineItems(notebookItemId)
      log.debug(
        `[IssuesStore] Loaded ${pipelineItemsHistory.value.length} pipeline items for ${notebookItemId}`,
      )
    } catch (err) {
      log.error('Error loading pipeline items history:', err)
      pipelineItemsHistory.value = []
    } finally {
      isLoadingPipelineHistory.value = false
    }
  }

  /**
   * Create a new cell
   *
   * @param {Object} cellData - Cell creation data
   * @returns {Promise<Object>} Created cell
   */
  async function createCell(cellData) {
    try {
      const newCell = await createCellService(cellData)
      log.debug('Cell created:', newCell)

      issues.value.unshift(newCell)
      await loadIssues()

      return newCell
    } catch (err) {
      error.value = `Failed to create cell: ${err.message}`
      log.error('Error creating cell:', err)
      throw err
    }
  }

  // ============================================================================
  // SSE and Real-time Updates
  // ============================================================================

  /**
   * Connect to SSE for real-time updates
   */
  function connectSSE() {
    if (eventSource.value) {
      eventSource.value.close()
    }

    eventSource.value = createIssuesEventSource(handleEvent, handleEventError)
  }

  /**
   * Disconnect from SSE
   */
  function disconnectSSE() {
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }
    stopFragmentStream()
    stopPipelineStream()
  }

  /**
   * Handle SSE events
   */
  function handleEvent(eventData) {
    log.debug('Received event:', eventData)

    switch (eventData.event_type) {
      case 'connected':
        log.debug('SSE connected:', eventData.message)
        break
      case 'cell_state_changed':
        handleCellStateChanged(eventData)
        break
      case 'fragment_added':
        handleFragmentAdded(eventData)
        break
      case 'cell_created':
        handleCellCreated(eventData)
        break
      default:
        log.debug('Unknown event type:', eventData.event_type)
    }
  }

  /**
   * Handle cell state change event
   */
  function handleCellStateChanged(eventData) {
    const { cell_id, new_state, cell_data } = eventData

    const issueIndex = issues.value.findIndex((i) => i.id === cell_id)
    if (issueIndex !== -1) {
      if (cell_data) {
        issues.value[issueIndex] = cell_data
      } else {
        issues.value[issueIndex].status = new_state
        issues.value[issueIndex].updated_at = new Date().toISOString()
      }
    }

    if (selectedIssue.value && selectedIssue.value.id === cell_id) {
      if (cell_data) {
        selectedIssue.value = cell_data
      } else {
        selectedIssue.value.status = new_state
        selectedIssue.value.updated_at = new Date().toISOString()
      }
    }
  }

  /**
   * Handle fragment added event
   */
  function handleFragmentAdded(eventData) {
    const { cell_id, fragment } = eventData

    const issue = issues.value.find((i) => i.id === cell_id)
    if (issue) {
      if (!issue.fragments) {
        issue.fragments = []
      }
      issue.fragments.push(fragment)
      issue.updated_at = new Date().toISOString()
    }

    if (selectedIssue.value && selectedIssue.value.id === cell_id) {
      if (!selectedIssue.value.fragments) {
        selectedIssue.value.fragments = []
      }
      selectedIssue.value.fragments.push(fragment)
      selectedIssue.value.updated_at = new Date().toISOString()
    }
  }

  /**
   * Handle cell created event
   */
  function handleCellCreated(eventData) {
    const { cell_data } = eventData

    if (cell_data) {
      issues.value.unshift(cell_data)
    }
  }

  /**
   * Handle SSE errors
   */
  function handleEventError(err) {
    log.error('SSE connection error:', err)
  }

  /**
   * Start streaming fragments for a specific cell
   */
  function startFragmentStream(cellId) {
    if (!cellId) return

    stopFragmentStream()

    cellFragmentEventSource.value = createCellFragmentStream(
      cellId,
      handleFragmentReceived,
      handleFragmentStreamError,
    )

    log.debug(`Fragment stream started for cell: ${cellId}`)
  }

  /**
   * Stop streaming fragments
   */
  function stopFragmentStream() {
    if (cellFragmentEventSource.value) {
      cellFragmentEventSource.value.close()
      cellFragmentEventSource.value = null
      log.debug('Fragment stream closed')
    }
  }

  /**
   * Handle fragment received via SSE
   */
  function handleFragmentReceived(data) {
    log.debug('Fragment received via SSE:', data)

    if (!selectedIssue.value) return

    // Handle connection messages
    if (data.event_type === 'connected') {
      log.debug('Cell fragment stream connected')
      return
    }

    // Extract fragment from event data
    const fragment = data.event_type === 'fragment' && data.fragment ? data.fragment : data

    if (!selectedIssue.value.fragments) {
      selectedIssue.value.fragments = []
    }

    selectedIssue.value.fragments.push(fragment)

    if (
      fragment.type === 'status_update' ||
      fragment.metadata?.is_status_update
    ) {
      const newStatus = fragment.content || fragment.result
      const validStatuses = [
        'PENDING',
        'RUNNING',
        'COMPLETED',
        'ERROR',
        'PAUSED',
        'CANCELED',
      ]

      if (newStatus && validStatuses.includes(newStatus.toUpperCase())) {
        const statusValue = newStatus.toUpperCase()

        selectedIssue.value.status = statusValue
        selectedIssue.value.updated_at = new Date().toISOString()

        const issueIndex = issues.value.findIndex(
          (c) => c.id === selectedIssue.value.id,
        )
        if (issueIndex !== -1) {
          issues.value[issueIndex].status = statusValue
          issues.value[issueIndex].updated_at = new Date().toISOString()
        }

        log.debug(`Cell status updated to: ${statusValue}`)
      }
    }
  }

  /**
   * Handle fragment stream error
   */
  function handleFragmentStreamError(err) {
    log.error('Fragment stream error:', err)
  }

  /**
   * Start streaming pipeline fragments
   */
  function startPipelineStream() {
    stopPipelineStream()

    pipelineEventSource.value = createPipelineFragmentStream(
      handlePipelineFragment,
      handlePipelineStreamError,
    )

    log.debug('Pipeline fragment stream started')
  }

  /**
   * Stop streaming pipeline fragments
   */
  function stopPipelineStream() {
    if (pipelineEventSource.value) {
      pipelineEventSource.value.close()
      pipelineEventSource.value = null
      log.debug('Pipeline fragment stream closed')
    }
  }

  /**
   * Handle pipeline fragment received via SSE
   */
  function handlePipelineFragment(data) {
    log.debug('Pipeline fragment received via SSE:', data)

    if (data.event_type === 'connected') {
      return
    }

    if (
      data.event_type === 'pipeline_fragment' &&
      data.fragment &&
      data.cell_id
    ) {
      const fragmentWithMeta = {
        ...data.fragment,
        cell_id: data.cell_id,
        received_at: new Date().toISOString(),
      }

      pipelineActivityFeed.value.unshift(fragmentWithMeta)

      if (pipelineActivityFeed.value.length > 100) {
        pipelineActivityFeed.value = pipelineActivityFeed.value.slice(0, 100)
      }
    }
  }

  /**
   * Handle pipeline stream error
   */
  function handlePipelineStreamError(err) {
    log.error('Pipeline fragment stream error:', err)
  }

  // ============================================================================
  // Return Store API
  // ============================================================================

  return {
    // State
    issues,
    selectedIssue,
    isLoading,
    error,
    filterState,
    currentPage,
    itemsPerPage,
    totalPages,
    totalItems,
    issueCounts,
    isIngestRunning,
    isProcessing,
    monitoringStatus,
    isMonitoringLoading,
    processingStatus,
    isProcessingLoading,
    pipelineActivityFeed,
    notebookItemTypes,
    pipelineItemsHistory,
    isLoadingPipelineHistory,

    // Getters
    filteredIssues,
    issuesByState,
    hasNextPage,
    hasPreviousPage,

    // Actions - Issues
    loadIssues,
    goToPage,
    nextPage,
    previousPage,
    loadIssueDetails,
    selectIssue,
    clearSelection,
    setFilter,
    createCell,

    // Actions - Processing
    triggerIngestion,
    triggerProcessing,
    loadMonitoringStatus,
    startMonitoring,
    stopMonitoring,
    loadProcessingStatus,
    pauseProcessing,
    resumeProcessing,

    // Actions - Data
    loadNotebookItemTypes,
    loadPipelineItemsHistory,

    // Actions - SSE
    connectSSE,
    disconnectSSE,
    startPipelineStream,
    stopPipelineStream,
  }
})
