/**
 * Issues Service
 *
 * Simplified wrapper service for issues-related API operations.
 * Delegates to issuesDashboardService for actual API calls.
 */

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
  createCellFragmentEventSource,
  createPipelineFragmentEventSource,
  fetchNotebookItemTypes as fetchTypes,
  fetchPipelineItemsByNotebookItemId,
  createCell as createCellFn,
} from './issuesDashboardService.js'

/**
 * Fetch paginated issues from the queue
 * @param {number} page - Page number (starts at 1)
 * @param {number} limit - Items per page
 * @param {string} status - Optional status filter (pendente, executando, finalizado, erro, or 'all')
 * @returns {Promise<Object>} Paginated response with issues, metadata, and issue counts
 */
export async function fetchIssues(page = 1, limit = 20, status = null) {
  return fetchIssuesQueueCells(page, limit, status)
}

/**
 * Fetch details for a specific issue
 * @param {string} issueId - The issue ID
 * @returns {Promise<Object>} Issue details
 */
export async function fetchIssueDetails(issueId) {
  return fetchCellDetails(issueId)
}

/**
 * Trigger document ingestion
 * @param {Object} options - Ingestion options
 * @returns {Promise<Object>} Trigger response
 */
export async function startIngestion(options = {}) {
  return triggerIngest(options)
}

/**
 * Process pending cells immediately
 * @returns {Promise<Object>} Processing response
 */
export async function processPending() {
  return processPendingCells()
}

/**
 * Get monitoring status
 * @returns {Promise<Object>} Monitoring status
 */
export async function getMonitoringInfo() {
  return getMonitoringStatus()
}

/**
 * Start monitoring loop
 * @returns {Promise<Object>} Start response
 */
export async function startMonitoringLoop() {
  return startMonitoring()
}

/**
 * Stop monitoring loop
 * @returns {Promise<Object>} Stop response
 */
export async function stopMonitoringLoop() {
  return stopMonitoring()
}

/**
 * Get processing queue status
 * @returns {Promise<Object>} Processing status
 */
export async function getProcessingInfo() {
  return getProcessingStatus()
}

/**
 * Pause processing queue
 * @returns {Promise<Object>} Pause response
 */
export async function pauseProcessingQueue() {
  return pauseProcessing()
}

/**
 * Resume processing queue
 * @returns {Promise<Object>} Resume response
 */
export async function resumeProcessingQueue() {
  return resumeProcessing()
}

/**
 * Create SSE connection for real-time updates
 * @param {Function} onEvent - Event handler
 * @param {Function} onError - Error handler
 * @returns {EventSource} EventSource instance
 */
export function createIssuesEventSource(onEvent, onError) {
  return createEventSource(onEvent, onError)
}

/**
 * Create SSE connection for streaming cell fragments
 * @param {string} cellId - Cell ID to stream fragments for
 * @param {Function} onFragment - Fragment handler
 * @param {Function} onError - Error handler
 * @returns {EventSource} EventSource instance
 */
export function createCellFragmentStream(cellId, onFragment, onError) {
  return createCellFragmentEventSource(cellId, onFragment, onError)
}

/**
 * Create SSE connection for streaming fragments from all active cells (pipeline view)
 * @param {Function} onPipelineFragment - Pipeline fragment handler
 * @param {Function} onError - Error handler
 * @returns {EventSource} EventSource instance
 */
export function createPipelineFragmentStream(onPipelineFragment, onError) {
  return createPipelineFragmentEventSource(onPipelineFragment, onError)
}

/**
 * Fetch all NotebookItemTypes
 * @returns {Promise<Array>} Array of NotebookItemType objects
 */
export async function fetchNotebookItemTypes() {
  return fetchTypes()
}

/**
 * Fetch pipeline items for a notebook item
 * @param {string} notebookItemId - Notebook item ID
 * @returns {Promise<Array>} Array of PipelineItem objects
 */
export async function fetchPipelineItems(notebookItemId) {
  return fetchPipelineItemsByNotebookItemId(notebookItemId)
}

/**
 * Create a new cell
 * @param {Object} cellData - Cell creation data
 * @returns {Promise<Object>} Created cell
 */
export async function createCell(cellData) {
  return createCellFn(cellData)
}
