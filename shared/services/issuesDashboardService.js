/**
 * @metadata {
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-17",
 *   "console_calls_found": 6,
 *   "console_calls_migrated": 6,
 *   "migration_rate": 100,
 *   "logger_namespace": "services:issues-dashboard",
 *   "validation_status": "excellent"
 * }
 */
/**
 * Issues Dashboard Service
 *
 * Provides API methods for interacting with the issues-queue dashboard.
 */

import { API_BASE_URL } from '../config/endpoints.js'
import apiService from './apiService.js'
import authService from './authService.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('services:issues-dashboard')

/**
 * Fetch paginated cells from the issues-queue.
 *
 * @param {number} page - Page number (starts at 1)
 * @param {number} limit - Items per page
 * @param {string} status - Optional status filter (pendente, executando, finalizado, erro, or 'all')
 * @returns {Promise<Object>} Paginated response with cells, metadata, and issue counts
 */
export async function fetchIssuesQueueCells(
  page = 1,
  limit = 20,
  status = null,
) {
  let url = `${API_BASE_URL}/api/issues-dashboard/cells?page=${page}&limit=${limit}`

  if (status && status !== 'all') {
    url += `&status=${encodeURIComponent(status)}`
  }

  const response = await apiService.fetch(url)

  if (!response.ok) {
    throw new Error(`Failed to fetch cells: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Fetch details of a specific cell.
 *
 * @param {string} cellId - UUID of the cell
 * @returns {Promise<Object>} Cell object with full details
 */
export async function fetchCellDetails(cellId) {
  const response = await apiService.fetch(
    `${API_BASE_URL}/api/issues-dashboard/cells/${cellId}`,
  )

  if (!response.ok) {
    throw new Error(`Failed to fetch cell details: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Trigger the ingest.py script.
 *
 * @param {Object} options - Ingest options
 * @param {string} [options.sourceDir] - Optional source directory
 * @param {boolean} [options.dryRun=false] - Whether to run in dry-run mode
 * @returns {Promise<Object>} Trigger response with status
 */
export async function triggerIngest({ sourceDir = null, dryRun = false } = {}) {
  const response = await apiService.fetch(
    `${API_BASE_URL}/api/issues-dashboard/ingest/trigger`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        source_dir: sourceDir,
        dry_run: dryRun,
      }),
    },
  )

  if (!response.ok) {
    throw new Error(`Failed to trigger ingest: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Trigger immediate processing of pending cells.
 *
 * Signals the orchestrator to bypass its regular polling interval
 * and immediately process any PENDING cells in the issues-queue.
 *
 * @returns {Promise<Object>} Processing trigger response with status
 */
export async function processPendingCells() {
  const response = await apiService.fetch(
    `${API_BASE_URL}/api/issues-dashboard/process-pending-cells`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    },
  )

  if (!response.ok) {
    throw new Error(`Failed to trigger processing: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Get current monitoring status.
 *
 * @returns {Promise<Object>} Monitoring status with active state and configuration
 */
export async function getMonitoringStatus() {
  const response = await apiService.fetch(
    `${API_BASE_URL}/api/issues-dashboard/monitoring/status`,
  )

  if (!response.ok) {
    throw new Error(`Failed to get monitoring status: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Start the orchestrator monitoring loop.
 *
 * Starts the background task that continuously monitors the issues-queue
 * for pending cells and processes them automatically.
 *
 * @returns {Promise<Object>} Control response with status
 */
export async function startMonitoring() {
  const response = await apiService.fetch(
    `${API_BASE_URL}/api/issues-dashboard/monitoring/start`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    },
  )

  if (!response.ok) {
    throw new Error(`Failed to start monitoring: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Stop the orchestrator monitoring loop.
 *
 * Stops the background task that monitors the issues-queue,
 * effectively pausing automatic processing of pending cells.
 *
 * @returns {Promise<Object>} Control response with status
 */
export async function stopMonitoring() {
  const response = await apiService.fetch(
    `${API_BASE_URL}/api/issues-dashboard/monitoring/stop`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    },
  )

  if (!response.ok) {
    throw new Error(`Failed to stop monitoring: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Get current processing status.
 *
 * @returns {Promise<Object>} Processing status with paused state
 */
export async function getProcessingStatus() {
  const response = await apiService.fetch(
    `${API_BASE_URL}/api/issues-dashboard/processing/status`,
  )

  if (!response.ok) {
    throw new Error(`Failed to get processing status: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Pause cell processing.
 *
 * Pauses processing of pending cells while keeping monitoring active.
 *
 * @returns {Promise<Object>} Control response with status
 */
export async function pauseProcessing() {
  const response = await apiService.fetch(
    `${API_BASE_URL}/api/issues-dashboard/processing/pause`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    },
  )

  if (!response.ok) {
    throw new Error(`Failed to pause processing: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Resume cell processing.
 *
 * Resumes processing of pending cells if it was previously paused.
 *
 * @returns {Promise<Object>} Control response with status
 */
export async function resumeProcessing() {
  const response = await apiService.fetch(
    `${API_BASE_URL}/api/issues-dashboard/processing/resume`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    },
  )

  if (!response.ok) {
    throw new Error(`Failed to resume processing: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Create SSE connection for real-time updates.
 *
 * @param {Function} onEvent - Callback for receiving events
 * @param {Function} onError - Callback for errors
 * @returns {EventSource} EventSource instance
 */
export function createEventSource(onEvent, onError) {
  // Get authentication token
  const token = authService.getToken()
  
  // Build URL with token as query parameter (EventSource doesn't support custom headers)
  const url = token
    ? `${API_BASE_URL}/api/issues-dashboard/events?token=${encodeURIComponent(token)}`
    : `${API_BASE_URL}/api/issues-dashboard/events`
  
  const eventSource = new EventSource(url, {
    withCredentials: true,
  })

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      onEvent(data)
    } catch (error) {
      log.error('Failed to parse SSE event', error)
    }
  }

  eventSource.onerror = (error) => {
    log.error('SSE error', error)
    if (onError) {
      onError(error)
    }
  }

  return eventSource
}

/**
 * Create SSE connection for streaming cell fragments in real-time.
 *
 * @param {string} cellId - UUID of the cell to stream fragments for
 * @param {Function} onFragment - Callback for receiving fragment events
 * @param {Function} onError - Callback for errors
 * @returns {EventSource} EventSource instance
 */
export function createCellFragmentEventSource(cellId, onFragment, onError) {
  const eventSource = new EventSource(
    `${API_BASE_URL}/api/issues-dashboard/cells/${cellId}/stream-fragments`,
    {
      withCredentials: true,
    },
  )

  eventSource.onmessage = (event) => {
    try {
      const fragment = JSON.parse(event.data)
      onFragment(fragment)
    } catch (error) {
      log.error('Failed to parse fragment SSE event', error)
    }
  }

  eventSource.onerror = (error) => {
    log.error('Fragment SSE error', error)
    if (onError) {
      onError(error)
    }
  }

  return eventSource
}

/**
 * Create SSE connection for streaming fragments from all active cells (pipeline view).
 *
 * Connects to the pattern-subscribed endpoint that provides a holistic view
 * of all fragment activity across the pipeline.
 *
 * @param {Function} onPipelineFragment - Callback for receiving pipeline fragment events
 * @param {Function} onError - Callback for errors
 * @returns {EventSource} EventSource instance
 */
export function createPipelineFragmentEventSource(onPipelineFragment, onError) {
  // Get authentication token
  const token = authService.getToken()
  
  // Build URL with token as query parameter (EventSource doesn't support custom headers)
  const url = token
    ? `${API_BASE_URL}/api/issues-dashboard/stream-all-active-fragments?token=${encodeURIComponent(token)}`
    : `${API_BASE_URL}/api/issues-dashboard/stream-all-active-fragments`
  
  const eventSource = new EventSource(url, {
    withCredentials: true,
  })

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      onPipelineFragment(data)
    } catch (error) {
      log.error('Failed to parse pipeline fragment SSE event', error)
    }
  }

  eventSource.onerror = (error) => {
    log.error('Pipeline fragment SSE error', error)
    if (onError) {
      onError(error)
    }
  }

  return eventSource
}

/**
 * Fetch all NotebookItemTypes.
 *
 * Gets the list of available notebook item types which define
 * the blueprint/schema for cells and books.
 *
 * @returns {Promise<Array>} Array of NotebookItemType objects
 */
export async function fetchNotebookItemTypes() {
  const response = await apiService.fetch(`${API_BASE_URL}/api/notebook-item-types`)

  if (!response.ok) {
    throw new Error(
      `Failed to fetch notebook item types: ${response.statusText}`,
    )
  }

  return response.json()
}

/**
 * Fetch pipeline items (execution history) for a specific notebook item.
 *
 * Gets all PipelineItem execution records associated with a given NotebookItem (usually a Celula).
 * PipelineItems represent individual execution instances with their own fragments and status.
 *
 * @param {string} notebookItemId - UUID of the notebook item (cell)
 * @returns {Promise<Array>} Array of PipelineItem objects with execution history
 */
export async function fetchPipelineItemsByNotebookItemId(notebookItemId) {
  const response = await apiService.fetch(
    `${API_BASE_URL}/api/pipeline-items?notebook_item_id=${encodeURIComponent(notebookItemId)}`,
  )

  if (!response.ok) {
    throw new Error(`Failed to fetch pipeline items: ${response.statusText}`)
  }

  return response.json()
}

/**
 * Create a new cell.
 *
 * Creates a new Celula (NotebookItem) with specified type and initial data.
 *
 * @param {Object} cellData - Cell creation data
 * @param {string} cellData.notebook_item_type_id - ID of the NotebookItemType
 * @param {string} cellData.assignee_id - UUID of the user responsible
 * @param {Object} cellData.initial_data - Initial data for the cell
 * @param {Object} [cellData.refs] - Optional references to files
 * @returns {Promise<Object>} Created Celula object
 */
export async function createCell(cellData) {
  const response = await apiService.fetch(`${API_BASE_URL}/api/cells/create`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      notebook_item_type_id: cellData.notebook_item_type_id,
      assignee_id: cellData.assignee_id,
      initial_data: cellData.initial_data || {},
      refs: cellData.refs || {},
    }),
  })

  if (!response.ok) {
    throw new Error(`Failed to create cell: ${response.statusText}`)
  }

  return response.json()
}
