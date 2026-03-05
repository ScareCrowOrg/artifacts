/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-22",
 *   "console_calls_found": 36,
 *   "console_calls_migrated": 36,
 *   "migration_rate": 100,
 *   "logger_namespace": "issues:management",
 *   "validation_status": "excellent"
 * }
 */
/**
 * useIssues Composable
 *
 * Manages state and operations for issues dashboard with backend-driven
 * pagination, filtering, and summarization.
 *
 * Key Features:
 * - Paginated issue loading with configurable page size
 * - Server-side status filtering (pendente, executando, finalizado, erro)
 * - Real-time issue counts by status (independent of current filter/page)
 * - Server-Sent Events (SSE) for real-time updates
 * - Issue ingestion and processing triggers
 * - Monitoring and processing queue control
 *
 * The composable integrates with issuesService for API calls and ensures
 * that filtering and summarization are handled by the backend for consistency
 * and accurate counts across all data.
 */

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

const log = createLogger('issues:management')

export function useIssues() {
  // State
  const issues = ref([])
  const selectedIssue = ref(null)
  const isLoading = ref(false)
  const error = ref(null)
  const filterState = ref('all')
  const isIngestRunning = ref(false)
  const isProcessing = ref(false)
  const monitoringStatus = ref({
    active: false,
    polling_interval: 5,
    max_concurrent_cells: 2,
    task_running: false,
  })
  const isMonitoringLoading = ref(false)
  const processingStatus = ref({
    paused: false,
  })
  const isProcessingLoading = ref(false)
  const eventSource = ref(null)
  const cellFragmentEventSource = ref(null)
  const pipelineEventSource = ref(null)
  const pipelineActivityFeed = ref([])

  // New state for NotebookItemTypes and PipelineItems
  const notebookItemTypes = ref([])
  const pipelineItemsHistory = ref([])
  const isLoadingPipelineHistory = ref(false)

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

  // Computed

  // Note: filteredIssues now simply returns the issues from the backend
  // since filtering is handled server-side
  const filteredIssues = computed(() => {
    return issues.value
  })

  // Note: issuesByState now returns the counts from the backend
  // which reflect the total across all pages, not just the current page
  const issuesByState = computed(() => {
    return issueCounts.value
  })

  // Methods

  /**
   * Load issues with pagination and optional status filtering
   *
   * Fetches issues from the backend with pagination and filtering support.
   * Updates the local state with the paginated response including items,
   * total counts, page info, and issue counts by status.
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
      // Pass the current filter to the backend
      const status = filterState.value === 'all' ? null : filterState.value
      const response = await fetchIssues(page, limit, status)

      issues.value = response.items
      totalItems.value = response.total_items
      totalPages.value = response.total_pages
      currentPage.value = response.current_page
      itemsPerPage.value = response.items_per_page

      // Update issue counts from backend
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
   * Go to a specific page
   *
   * Navigates to the specified page number and loads the issues for that page.
   * Validates the page number is within valid bounds before navigating.
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
   * Load issue details
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
   * Start streaming fragments for a specific cell
   */
  function startFragmentStream(cellId) {
    if (!cellId) return

    stopFragmentStream() // Ensure any previous stream is closed

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
  function handleFragmentReceived(fragment) {
    log.debug('Fragment received via SSE:', fragment)

    if (!selectedIssue.value) return

    // Ensure fragments array exists
    if (!selectedIssue.value.fragments) {
      selectedIssue.value.fragments = []
    }

    // Add fragment
    selectedIssue.value.fragments.push(fragment)

    // Check if fragment indicates a status update
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
        // Legacy Portuguese
        'PENDENTE',
        'EXECUTANDO',
        'FINALIZADO',
        'ERRO',
        'PAUSADO',
        'CANCELADO',
      ]

      if (newStatus && validStatuses.includes(newStatus.toUpperCase())) {
        const statusValue = newStatus.toUpperCase()

        // Update selected issue status
        selectedIssue.value.status = statusValue
        selectedIssue.value.updated_at = new Date().toISOString()

        // Also update in the main issues list so IssueCard reacts
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
    // Optionally set an error state or show notification
  }

  /**
   * Load NotebookItemTypes
   *
   * Fetches all available notebook item types from the backend.
   * These types define the blueprint/schema for cells and books.
   *
   * @returns {Promise<void>}
   */
  async function loadNotebookItemTypes() {
    try {
      notebookItemTypes.value = await fetchNotebookItemTypes()
      log.debug(
        `Loaded ${notebookItemTypes.value.length} notebook item types`,
      )
    } catch (err) {
      log.error('Error loading notebook item types:', err)
      error.value = `Failed to load notebook item types: ${err.message}`
    }
  }

  /**
   * Load PipelineItems history for a specific notebook item (cell)
   *
   * Fetches all pipeline execution records associated with a notebook item.
   * Each PipelineItem represents an execution instance with its own fragments and status.
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
        `Loaded ${pipelineItemsHistory.value.length} pipeline items for ${notebookItemId}`,
      )
    } catch (err) {
      log.error('Error loading pipeline items history:', err)
      // For now, silently fail if the endpoint doesn't exist yet
      pipelineItemsHistory.value = []
    } finally {
      isLoadingPipelineHistory.value = false
    }
  }

  /**
   * Create a new cell
   *
   * Creates a new Celula (NotebookItem) with the specified type and initial data.
   *
   * @param {Object} cellData - Cell creation data
   * @param {string} cellData.notebook_item_type_id - ID of the NotebookItemType
   * @param {string} cellData.assignee_id - UUID of the user responsible
   * @param {Object} cellData.initial_data - Initial data for the cell
   * @param {Object} [cellData.refs] - Optional references to files
   * @returns {Promise<Object>} Created cell
   */
  async function createCell(cellData) {
    try {
      const newCell = await createCellService(cellData)
      log.debug('Cell created:', newCell)

      // Add to the beginning of the issues list
      issues.value.unshift(newCell)

      // Refresh the list to get accurate counts
      await loadIssues()

      return newCell
    } catch (err) {
      error.value = `Failed to create cell: ${err.message}`
      log.error('Error creating cell:', err)
      throw err
    }
  }

  /**
   * Select an issue
   */
  function selectIssue(issue) {
    stopFragmentStream() // Close any existing fragment stream
    selectedIssue.value = issue
    if (issue) {
      startFragmentStream(issue.id) // Start streaming fragments for the selected cell
      loadPipelineItemsHistory(issue.id) // Load pipeline execution history
    } else {
      pipelineItemsHistory.value = []
    }
  }

  /**
   * Clear selection
   */
  function clearSelection() {
    stopFragmentStream() // Close fragment stream when clearing selection
    selectedIssue.value = null
    pipelineItemsHistory.value = []
  }

  /**
   * Set filter
   *
   * Updates the filter state and resets pagination to page 1.
   * Automatically reloads the issues from the backend with the new filter applied.
   *
   * The filter is processed on the backend, ensuring accurate results across
   * all pages and consistent total counts.
   *
   * @param {string} state - Filter state ('all', 'pendente', 'executando', 'finalizado', 'erro')
   */
  function setFilter(state) {
    filterState.value = state
    // Reset to first page when filter changes
    currentPage.value = 1
    // Reload from backend with the new filter
    loadIssues(1)
  }

  /**
   * Start ingestion
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
      error.value = `Failed to trigger processing: ${err.message}`
      log.error('Error triggering processing:', err)
      throw err
    } finally {
      isProcessing.value = false
    }
  }

  /**
   * Load monitoring status
   */
  async function loadMonitoringStatus() {
    try {
      const status = await getMonitoringInfo()
      monitoringStatus.value = status
      return status
    } catch (err) {
      log.error('Error loading monitoring status:', err)
      return null
    }
  }

  /**
   * Start monitoring
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
      error.value = `Failed to start monitoring: ${err.message}`
      log.error('Error starting monitoring:', err)
      throw err
    } finally {
      isMonitoringLoading.value = false
    }
  }

  /**
   * Stop monitoring
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
      error.value = `Failed to stop monitoring: ${err.message}`
      log.error('Error stopping monitoring:', err)
      throw err
    } finally {
      isMonitoringLoading.value = false
    }
  }

  /**
   * Load processing status
   */
  async function loadProcessingStatus() {
    try {
      const status = await getProcessingInfo()
      processingStatus.value = status
      return status
    } catch (err) {
      log.error('Error loading processing status:', err)
      return null
    }
  }

  /**
   * Pause processing
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
      error.value = `Failed to pause processing: ${err.message}`
      log.error('Error pausing processing:', err)
      throw err
    } finally {
      isProcessingLoading.value = false
    }
  }

  /**
   * Resume processing
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
      error.value = `Failed to resume processing: ${err.message}`
      log.error('Error resuming processing:', err)
      throw err
    } finally {
      isProcessingLoading.value = false
    }
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

    // Update in issues list
    const issueIndex = issues.value.findIndex((i) => i.id === cell_id)
    if (issueIndex !== -1) {
      if (cell_data) {
        issues.value[issueIndex] = cell_data
      } else {
        issues.value[issueIndex].status = new_state
        issues.value[issueIndex].updated_at = new Date().toISOString()
      }
    }

    // Update selected issue if it's the one that changed
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

    // Update in issues list
    const issue = issues.value.find((i) => i.id === cell_id)
    if (issue) {
      if (!issue.fragments) {
        issue.fragments = []
      }
      issue.fragments.push(fragment)
      issue.updated_at = new Date().toISOString()
    }

    // Update selected issue if it's the one that changed
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
    error.value = 'Real-time updates disconnected. Refresh to reconnect.'
  }

  /**
   * Connect to SSE
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
    stopFragmentStream() // Also close fragment stream
    stopPipelineStream() // Also close pipeline stream
  }

  /**
   * Start streaming fragments from all active cells (pipeline view)
   */
  function startPipelineStream() {
    stopPipelineStream() // Ensure any previous stream is closed

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

    // Skip connection messages
    if (data.event_type === 'connected') {
      return
    }

    // Handle pipeline fragment events
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

      // Add to pipeline activity feed (newest first)
      pipelineActivityFeed.value.unshift(fragmentWithMeta)

      // Limit feed size to prevent memory issues (keep last 100 fragments)
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
    // Optionally set an error state or show notification
  }

  return {
    // State
    issues,
    selectedIssue,
    isLoading,
    error,
    filterState,
    isIngestRunning,
    isProcessing,
    monitoringStatus,
    isMonitoringLoading,
    processingStatus,
    isProcessingLoading,
    pipelineActivityFeed,

    // New state
    notebookItemTypes,
    pipelineItemsHistory,
    isLoadingPipelineHistory,

    // Pagination state
    currentPage,
    itemsPerPage,
    totalPages,
    totalItems,

    // Issue counts (from backend)
    issueCounts,

    // Computed
    filteredIssues,
    issuesByState,

    // Methods
    loadIssues,
    goToPage,
    loadIssueDetails,
    selectIssue,
    clearSelection,
    setFilter,
    triggerIngestion,
    triggerProcessing,
    loadMonitoringStatus,
    startMonitoring,
    stopMonitoring,
    loadProcessingStatus,
    pauseProcessing,
    resumeProcessing,
    connectSSE,
    disconnectSSE,
    startPipelineStream,
    stopPipelineStream,

    // New methods
    loadNotebookItemTypes,
    loadPipelineItemsHistory,
    createCell,
  }
}
