/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-23",
 *   "console_calls_found": 20,
 *   "console_calls_migrated": 20,
 *   "migration_rate": 100,
 *   "logger_namespace": "dashboard:issues",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Issues Dashboard Composable
 *
 * Provides reactive state management and real-time updates for the issues dashboard.
 */

import { ref, computed, onMounted, onUnmounted } from 'vue'
import { createLogger } from '@/utils/logger'
import {
  fetchIssuesQueueCells,
  fetchCellDetails,
  triggerIngest,
  processPendingCells,
  getMonitoringStatus,
  startMonitoring,
  stopMonitoring,
  getProcessingStatus,
  pauseProcessing,
  resumeProcessing,
  createEventSource,
} from '../services/issuesDashboardService.js'

const log = createLogger('dashboard:issues')

export function useIssuesDashboard() {
  // State
  const cells = ref([])
  const selectedCell = ref(null)
  const isLoading = ref(false)
  const error = ref(null)
  const eventSource = ref(null)
  const filterState = ref('all') // 'all', 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED'
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

  // Computed
  const filteredCells = computed(() => {
    if (filterState.value === 'all') {
      return cells.value
    }
    return cells.value.filter((cell) => {
      const cellStatus = cell.status.toLowerCase()
      return cellStatus === filterState.value.toLowerCase()
    })
  })

  const cellsByState = computed(() => {
    const counts = {
      pendente: 0,
      executando: 0,
      finalizado: 0,
      erro: 0,
    }

    cells.value.forEach((cell) => {
      const state = cell.status.toLowerCase()
      if (Object.prototype.hasOwnProperty.call(counts, state)) {
        counts[state]++
      }
    })

    return counts
  })

  // Methods

  /**
   * Load all cells from the issues-queue
   */
  async function loadCells() {
    isLoading.value = true
    error.value = null

    try {
      cells.value = await fetchIssuesQueueCells()
    } catch (err) {
      error.value = `Failed to load cells: ${err.message}`
      log.error('Error loading cells', err)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Load details for a specific cell
   */
  async function loadCellDetails(cellId) {
    try {
      selectedCell.value = await fetchCellDetails(cellId)
    } catch (err) {
      error.value = `Failed to load cell details: ${err.message}`
      log.error('Error loading cell details', err)
    }
  }

  /**
   * Select a cell for detailed view
   */
  function selectCell(cell) {
    selectedCell.value = cell
  }

  /**
   * Clear selected cell
   */
  function clearSelection() {
    selectedCell.value = null
  }

  /**
   * Set filter state
   */
  function setFilter(state) {
    filterState.value = state
  }

  /**
   * Trigger ingestion process
   */
  async function startIngest(options = {}) {
    isIngestRunning.value = true
    error.value = null

    try {
      const result = await triggerIngest(options)
      log.info('Ingest triggered', result)
      return result
    } catch (err) {
      error.value = `Failed to trigger ingest: ${err.message}`
      log.error('Error triggering ingest', err)
      throw err
    } finally {
      isIngestRunning.value = false
    }
  }

  /**
   * Trigger immediate processing of pending cells
   */
  async function triggerProcessing() {
    isProcessing.value = true
    error.value = null

    try {
      const result = await processPendingCells()
      log.info('Processing triggered', result)

      // Refresh cells list after a short delay to show updates
      setTimeout(() => {
        loadCells()
      }, 1000)

      return result
    } catch (err) {
      error.value = `Failed to trigger processing: ${err.message}`
      log.error('Error triggering processing', err)
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
      const status = await getMonitoringStatus()
      monitoringStatus.value = status
      return status
    } catch (err) {
      log.error('Error loading monitoring status', err)
      // Don't set error here to avoid blocking UI
      return null
    }
  }

  /**
   * Start monitoring loop
   */
  async function startMonitoringLoop() {
    isMonitoringLoading.value = true
    error.value = null

    try {
      const result = await startMonitoring()
      log.info('Monitoring started', result)

      // Refresh status
      await loadMonitoringStatus()

      return result
    } catch (err) {
      error.value = `Failed to start monitoring: ${err.message}`
      log.error('Error starting monitoring', err)
      throw err
    } finally {
      isMonitoringLoading.value = false
    }
  }

  /**
   * Stop monitoring loop
   */
  async function stopMonitoringLoop() {
    isMonitoringLoading.value = true
    error.value = null

    try {
      const result = await stopMonitoring()
      log.info('Monitoring stopped', result)

      // Refresh status
      await loadMonitoringStatus()

      return result
    } catch (err) {
      error.value = `Failed to stop monitoring: ${err.message}`
      log.error('Error stopping monitoring', err)
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
      const status = await getProcessingStatus()
      processingStatus.value = status
      return status
    } catch (err) {
      log.error('Error loading processing status', err)
      // Don't set error here to avoid blocking UI
      return null
    }
  }

  /**
   * Pause processing
   */
  async function pauseProcessingQueue() {
    isProcessingLoading.value = true
    error.value = null

    try {
      const result = await pauseProcessing()
      log.info('Processing paused', result)

      // Refresh status
      await loadProcessingStatus()

      return result
    } catch (err) {
      error.value = `Failed to pause processing: ${err.message}`
      log.error('Error pausing processing', err)
      throw err
    } finally {
      isProcessingLoading.value = false
    }
  }

  /**
   * Resume processing
   */
  async function resumeProcessingQueue() {
    isProcessingLoading.value = true
    error.value = null

    try {
      const result = await resumeProcessing()
      log.info('Processing resumed', result)

      // Refresh status
      await loadProcessingStatus()

      return result
    } catch (err) {
      error.value = `Failed to resume processing: ${err.message}`
      log.error('Error resuming processing', err)
      throw err
    } finally {
      isProcessingLoading.value = false
    }
  }

  /**
   * Handle SSE events
   */
  function handleEvent(eventData) {
    log.debug('Received event', eventData)

    switch (eventData.event_type) {
      case 'connected':
        log.info('SSE connected', eventData.message)
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
        log.warn('Unknown event type', eventData.event_type)
    }
  }

  /**
   * Handle cell state change event
   */
  function handleCellStateChanged(eventData) {
    const { cell_id, new_state, cell_data } = eventData

    // Update in cells list
    const cellIndex = cells.value.findIndex((c) => c.id === cell_id)
    if (cellIndex !== -1) {
      if (cell_data) {
        cells.value[cellIndex] = cell_data
      } else {
        cells.value[cellIndex].status = new_state
        cells.value[cellIndex].updated_at = new Date().toISOString()
      }
    }

    // Update selected cell if it's the one that changed
    if (selectedCell.value && selectedCell.value.id === cell_id) {
      if (cell_data) {
        selectedCell.value = cell_data
      } else {
        selectedCell.value.status = new_state
        selectedCell.value.updated_at = new Date().toISOString()
      }
    }
  }

  /**
   * Handle fragment added event
   */
  function handleFragmentAdded(eventData) {
    const { cell_id, fragment } = eventData

    // Update in cells list
    const cell = cells.value.find((c) => c.id === cell_id)
    if (cell) {
      if (!cell.fragments) {
        cell.fragments = []
      }
      cell.fragments.push(fragment)
      cell.updated_at = new Date().toISOString()
    }

    // Update selected cell if it's the one that changed
    if (selectedCell.value && selectedCell.value.id === cell_id) {
      if (!selectedCell.value.fragments) {
        selectedCell.value.fragments = []
      }
      selectedCell.value.fragments.push(fragment)
      selectedCell.value.updated_at = new Date().toISOString()
    }
  }

  /**
   * Handle cell created event
   */
  function handleCellCreated(eventData) {
    const { cell_data } = eventData

    if (cell_data) {
      cells.value.unshift(cell_data)
    }
  }

  /**
   * Handle SSE errors
   */
  function handleEventError(err) {
    log.error('SSE connection error', err)
    error.value = 'Real-time updates disconnected. Refresh to reconnect.'
  }

  /**
   * Connect to SSE stream
   */
  function connectSSE() {
    if (eventSource.value) {
      eventSource.value.close()
    }

    eventSource.value = createEventSource(handleEvent, handleEventError)
  }

  /**
   * Disconnect from SSE stream
   */
  function disconnectSSE() {
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }
  }

  // Lifecycle
  onMounted(() => {
    loadCells()
    loadMonitoringStatus()
    loadProcessingStatus()
    connectSSE()
  })

  onUnmounted(() => {
    disconnectSSE()
  })

  return {
    // State
    cells,
    selectedCell,
    isLoading,
    error,
    filterState,
    isIngestRunning,
    isProcessing,
    monitoringStatus,
    isMonitoringLoading,
    processingStatus,
    isProcessingLoading,

    // Computed
    filteredCells,
    cellsByState,

    // Methods
    loadCells,
    loadCellDetails,
    selectCell,
    clearSelection,
    setFilter,
    startIngest,
    triggerProcessing,
    loadMonitoringStatus,
    startMonitoringLoop,
    stopMonitoringLoop,
    loadProcessingStatus,
    pauseProcessingQueue,
    resumeProcessingQueue,
    connectSSE,
    disconnectSSE,
  }
}
