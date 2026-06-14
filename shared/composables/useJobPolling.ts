/**
 * Generic Job Polling Composable
 *
 * Extracted from 3D Mesh Prototyping Cell — works with ANY job type.
 * Polls GET /api/cells/job-status/{job_id} (MongoDB SSOT) instead of
 * Redis-only endpoint.
 *
 * ASYNC FLOW (v6.0):
 * 1. Cell creates JobDocument + LPUSH → returns { job_id, status: "queued" }
 * 2. This composable polls GET /api/cells/job-status/{job_id}
 * 3. On "completed": calls onComplete with the JobDocument result
 * 4. On "failed"/"error": calls onError with the error message
 *
 * @module useJobPolling
 */

import { ref, type Ref } from 'vue'
import { createLogger } from '@/utils/logger'

const logger = createLogger('composable:use-job-polling')

export interface JobPollingResult {
  /** Job status: queued, processing, success, failed, error, not_found */
  status: string
  /** Job ID for tracking */
  job_id?: string
  /** Job type identifier */
  job_type?: string
  /** Content ID (MongoDB _id) if auto-persisted */
  content_id?: string
  /** Relative URL for file reference (Redis Magro) */
  relative_url?: string
  /** Error message if failed */
  error_message?: string
  /** ISO timestamp when job completed */
  completed_at?: string
  /** Legacy: base64 mesh data (3D Cell only) */
  mesh_data?: string
  /** Legacy: mesh format (3D Cell only) */
  mesh_format?: string
  /** Generic error field */
  error?: string
}

export interface JobPollingOptions {
  /** Polling interval in milliseconds (default: 2000) */
  intervalMs?: number
  /** Callback when job completes successfully */
  onComplete?: (job: JobPollingResult) => void
  /** Callback when job fails */
  onError?: (err: string) => void
}

export interface UseJobPollingReturn {
  /** Current job ID being polled */
  jobId: Ref<string | null>
  /** Current job status string */
  jobStatus: Ref<string>
  /** Whether polling is active */
  isPolling: Ref<boolean>
  /** Last received result (cleared when polling resets) */
  lastResult: Ref<JobPollingResult | null>

  /** Start polling for a job */
  startPolling: (id: string, opts?: JobPollingOptions) => void
  /** Stop polling immediately */
  stopPolling: () => void
  /** Manually poll once */
  pollJobStatus: (id: string) => Promise<JobPollingResult | null>
}

/**
 * Generic composable for polling job status from GET /api/cells/job-status/{job_id}.
 *
 * @param apiFetch - Authenticated fetch function returning a raw Response
 * @returns Job polling state and methods
 */
export function useJobPolling(
  apiFetch: (path: string, options?: RequestInit) => Promise<Response>,
): UseJobPollingReturn {
  const jobId = ref<string | null>(null)
  const jobStatus = ref<string>('idle')
  const isPolling = ref<boolean>(false)
  const lastResult = ref<JobPollingResult | null>(null)
  let pollingInterval: number | null = null
  let currentOptions: JobPollingOptions = {}

  /**
   * Poll job status from the endpoint.
   * Reads from MongoDB SSOT via GET /api/cells/job-status/{id}.
   */
  const pollJobStatus = async (id: string): Promise<JobPollingResult | null> => {
    if (isPolling.value) {
      logger.debug('Poll already in progress, skipping')
      return null
    }

    isPolling.value = true

    try {
      const response = await apiFetch(`/api/cells/job-status/${id}`)

      if (!response.ok) {
        const text = await response.text().catch(() => 'No error details')
        throw new Error(`HTTP ${response.status}: ${text}`)
      }

      const status: JobPollingResult = await response.json()
      jobStatus.value = status.status
      lastResult.value = status

      logger.debug(`Job ${id} status: ${status.status}`)

      // Terminal states
      if (status.status === 'success' || status.status === 'completed') {
        stopPolling()
        if (currentOptions.onComplete) {
          currentOptions.onComplete(status)
        }
        return status
      }

      if (status.status === 'failed' || status.status === 'error') {
        stopPolling()
        const errorMsg = status.error_message || status.error || 'Job processing failed'
        if (currentOptions.onError) {
          currentOptions.onError(errorMsg)
        }
        return status
      }

      return status
    } catch (err: any) {
      logger.error('Error polling job status', err)
      return null
    } finally {
      isPolling.value = false
    }
  }

  /**
   * Start polling for job status at the configured interval.
   *
   * @param id - Job ID to poll
   * @param opts - Options including interval and callbacks
   */
  const startPolling = (id: string, opts?: JobPollingOptions) => {
    jobId.value = id
    jobStatus.value = 'processing'
    lastResult.value = null
    currentOptions = opts || {}

    const intervalMs = currentOptions.intervalMs ?? 2000

    // Clear existing interval
    if (pollingInterval !== null) {
      clearInterval(pollingInterval)
    }

    // Immediate first poll
    pollJobStatus(id)

    // Start interval
    pollingInterval = window.setInterval(() => {
      if (jobId.value) {
        pollJobStatus(jobId.value)
      }
    }, intervalMs)

    logger.info(`Started polling for job ${id} every ${intervalMs}ms`)
  }

  /**
   * Stop polling immediately.
   */
  const stopPolling = () => {
    if (pollingInterval !== null) {
      clearInterval(pollingInterval)
      pollingInterval = null
      logger.debug('Stopped polling')
    }
  }

  return {
    jobId,
    jobStatus,
    isPolling,
    lastResult,
    startPolling,
    stopPolling,
    pollJobStatus,
  }
}
