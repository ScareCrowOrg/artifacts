/**
 * @file JobManagerCell.ts
 * @description JobManagerCell — BaseCell implementation for async job status display.
 *
 * Two modes:
 * - Embedded: Polls a single job_id, shows progress bar + status.
 *             Intended to be embedded inside other cells (e.g. PngGeneratorCell).
 * - Standalone: Lists jobs for current user with filters (status, job_type).
 *               Used as a standalone cell in the Workspace.
 *
 * Uses existing endpoints (NO new endpoints):
 * - GET /api/cells/job-status/{job_id} — Single job status
 * - GET /api/cells/jobs — List jobs with filters
 */

import { BaseCell, createHealthyResult } from '@/types/BaseCell'
import type { CellResult, CellMetadata, ValidationError, EnvironmentConfig, HealthCheckResult } from '@/types/BaseCell'
import apiService from '@/services/apiService.js'
import { ENDPOINTS } from '@/config/endpoints.js'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:JobManager')

export interface JobRecord {
  id?: string
  job_id?: string
  type?: string
  status: string
  user_id?: string
  cell_type?: string
  content_id?: string
  relative_url?: string
  error_message?: string
  enqueued_at?: string
  completed_at?: string
}

export interface JobManagerInput {
  /** Embedded mode: poll single job */
  job_id?: string
  /** Standalone mode: filter by status */
  status?: string
  /** Standalone mode: filter by job type */
  job_type?: string
  /** Standalone mode: max items */
  max_items?: number
  /** Embedded mode: polling interval */
  poll_interval_ms?: number
}

export class JobManagerCell extends BaseCell {
  private _isSetup = false
  private _pollTimer: ReturnType<typeof setInterval> | null = null

  /**
   * Execute JobManagerCell logic.
   *
   * Embedded mode (job_id provided):
   *   - Returns job status from GET /api/cells/job-status/{job_id}
   *   - Stops polling when terminal status reached
   *
   * Standalone mode (no job_id):
   *   - Returns list of jobs from GET /api/cells/jobs
   */
  async execute(input: Record<string, any>): Promise<CellResult> {
    const startTime = performance.now()

    try {
      const errors = this.validate(input)
      if (errors.length > 0) {
        return {
          success: false,
          output: { success: false, errors, error: 'Validation failed' },
          execution_time: performance.now() - startTime,
          error: 'Validation failed',
        }
      }

      const jobId = input.job_id

      if (jobId) {
        // ── Embedded mode: poll single job ──
        const response = await apiService.fetch(
          `/api/cells/job-status/${jobId}`,
        ) as Response

        if (!response.ok) {
          throw new Error(`Job status check failed: ${response.statusText}`)
        }

        const status: JobRecord = await response.json()

        log.info('Job status fetched', { jobId, status: status.status })

        return {
          success: true,
          output: status,
          execution_time: performance.now() - startTime,
          execution_steps: ['fetch-job-status'],
          quality_score: 1.0,
        }
      }

      // ── Standalone mode: list jobs ──
      const queryParams = new URLSearchParams()
      if (input.status) queryParams.set('status', input.status)
      if (input.job_type) queryParams.set('job_type', input.job_type)
      if (input.max_items) queryParams.set('limit', String(input.max_items))

      const response = await apiService.fetch(
        `/api/cells/jobs?${queryParams.toString()}`,
      ) as Response

      if (!response.ok) {
        throw new Error(`Job list failed: ${response.statusText}`)
      }

      const jobsData: { jobs: JobRecord[]; total: number } = await response.json()

      log.info('Jobs listed', { total: jobsData.total, jobs: jobsData.jobs.length })

      return {
        success: true,
        output: jobsData,
        execution_time: performance.now() - startTime,
        execution_steps: ['list-jobs'],
        quality_score: 1.0,
      }
    } catch (error: any) {
      log.error('JobManagerCell execution failed', error)
      return {
        success: false,
        output: { success: false, error: error.message || 'Unknown error' },
        execution_time: performance.now() - startTime,
        error: error.message || 'Execution failed',
      }
    }
  }

  /**
   * Describe JobManagerCell capabilities.
   */
  async describe(): Promise<CellMetadata> {
    return {
      id: 'job-manager-cell',
      name: 'Job Manager Cell',
      version: '1.0.0',
      description: 'Displays async job status — embedded progress bar or standalone job history list. Works with any cell type that uses async job execution.',
      inputs: {
        job_id: {
          type: 'string',
          description: 'Job ID to poll (embedded mode). Omit for standalone list mode.',
          required: false,
        },
        status: {
          type: 'string',
          description: 'Filter by status (standalone mode): queued, processing, success, failed',
          required: false,
        },
        job_type: {
          type: 'string',
          description: 'Filter by job type (standalone mode)',
          required: false,
        },
        max_items: {
          type: 'number',
          description: 'Max items to display (standalone mode, default 10)',
          required: false,
        },
      },
      outputs: {
        status: { type: 'string', description: 'Job status or list count' },
        jobs: { type: 'array', description: 'List of job records (standalone mode)' },
        total: { type: 'number', description: 'Total job count (standalone mode)' },
      },
      tags: ['job-manager', 'async', 'polling', 'status'],
      required_resources: ['backend'],
      estimated_duration_seconds: 5,
    }
  }

  /**
   * Validate input.
   */
  validate(input: Record<string, any>): ValidationError[] {
    const errors: ValidationError[] = []

    if (input.poll_interval_ms !== undefined && (input.poll_interval_ms < 500 || input.poll_interval_ms > 30000)) {
      errors.push({ field: 'poll_interval_ms', message: 'Poll interval must be between 500ms and 30000ms' })
    }

    if (input.max_items !== undefined && (input.max_items < 1 || input.max_items > 100)) {
      errors.push({ field: 'max_items', message: 'Max items must be between 1 and 100' })
    }

    return errors
  }

  async setup(config: EnvironmentConfig): Promise<void> {
    log.debug('JobManagerCell setup', { config })
    this._isSetup = true
  }

  async teardown(): Promise<void> {
    this._stopPolling()
    this._isSetup = false
  }

  async health_check(): Promise<HealthCheckResult> {
    try {
      const response = await apiService.fetch('/api/health') as Response
      if (!response.ok) {
        return { status: 'degraded', can_execute: true, reason: 'Backend health check failed' }
      }
      return createHealthyResult()
    } catch {
      return { status: 'degraded', can_execute: true, reason: 'Backend unreachable' }
    }
  }

  /**
   * Cancel a queued or processing job.
   *
   * Calls POST /api/cells/jobs/{jobId}/cancel.
   * Only visible for jobs in ``queued`` or ``processing`` status.
   */
  async cancelJob(jobId: string): Promise<CellResult> {
    const startTime = performance.now()
    if (!jobId) {
      return { success: false, output: {}, execution_time: 0, error: 'jobId is required' }
    }
    try {
      const response = await apiService.fetch(
        `/api/cells/jobs/${jobId}/cancel`,
        { method: 'POST' },
      ) as Response
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || `Cancel failed: ${response.statusText}`)
      }
      return {
        success: true,
        output: await response.json(),
        execution_time: performance.now() - startTime,
      }
    } catch (error: any) {
      log.error('cancelJob failed', { jobId, error: error.message })
      return { success: false, output: {}, execution_time: performance.now() - startTime, error: error.message || 'Cancel failed' }
    }
  }

  /**
   * Retry a job — re-enqueues with original payload.
   *
   * Calls POST /api/cells/jobs/{jobId}/retry.
   * Accepts failed, cancelled, or stuck queued jobs.
   */
  async retryJob(jobId: string): Promise<CellResult> {
    const startTime = performance.now()
    if (!jobId) {
      return { success: false, output: {}, execution_time: 0, error: 'jobId is required' }
    }
    try {
      const response = await apiService.fetch(
        `/api/cells/jobs/${jobId}/retry`,
        { method: 'POST' },
      ) as Response
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || `Retry failed: ${response.statusText}`)
      }
      return {
        success: true,
        output: await response.json(),
        execution_time: performance.now() - startTime,
      }
    } catch (error: any) {
      log.error('retryJob failed', { jobId, error: error.message })
      return { success: false, output: {}, execution_time: performance.now() - startTime, error: error.message || 'Retry failed' }
    }
  }

  /** Start polling for a job (used by View.vue in embedded mode). */
  startPolling(jobId: string, intervalMs: number, onUpdate: (job: JobRecord) => void, onError: (err: string) => void): void {
    this._stopPolling()
    this._pollTimer = setInterval(async () => {
      try {
        const response = await apiService.fetch(`/api/cells/job-status/${jobId}`) as Response
        const job: JobRecord = await response.json()
        onUpdate(job)

        if (job.status === 'success' || job.status === 'failed' || job.status === 'completed' || job.status === 'error') {
          this._stopPolling()
        }
      } catch (err: any) {
        onError(err.message)
      }
    }, intervalMs)
  }

  private _stopPolling(): void {
    if (this._pollTimer) {
      clearInterval(this._pollTimer)
      this._pollTimer = null
    }
  }
}
