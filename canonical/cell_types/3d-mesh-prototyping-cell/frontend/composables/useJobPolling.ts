/**
 * Job Polling Composable for 3D Mesh Generation
 * 
 * Extracts job polling logic from View.vue for better modularity and reusability.
 * Handles Redis-based job status polling with configurable intervals.
 * 
 * @module useJobPolling
 */

import { ref, Ref } from 'vue'
import { apiFetch } from '@/services/apiService'
import { createLogger } from '#shared/logger'

const logger = createLogger('composable:use-job-polling')

export interface JobStatus {
  status: 'idle' | 'queued' | 'processing' | 'completed' | 'failed' | 'error'
  mesh_data?: string
  metadata?: Record<string, any>
  blender_optimized?: boolean
  blender_error?: string
  sf3d_completed?: boolean
  message?: string
  error?: string
}

export interface UseJobPollingReturn {
  // State
  jobId: Ref<string | null>
  jobStatus: Ref<string>
  isPolling: Ref<boolean>
  
  // Optimization status
  blenderOptimized: Ref<boolean | null>
  blenderError: Ref<string | null>
  statusMessage: Ref<string | null>
  sf3dCompleted: Ref<boolean | null>
  
  // Methods
  startPolling: (id: string, intervalMs?: number) => void
  stopPolling: () => void
  pollJobStatus: (id: string) => Promise<JobStatus | null>
}

/**
 * Composable for managing 3D mesh generation job polling
 * 
 * @param onComplete - Callback when job completes successfully
 * @param onError - Callback when job fails
 * @returns Job polling state and methods
 */
export function useJobPolling(
  onComplete?: (data: string, metadata?: Record<string, any>) => void,
  onError?: (error: string) => void
): UseJobPollingReturn {
  // Job state
  const jobId = ref<string | null>(null)
  const jobStatus = ref<string>('idle')
  const isPolling = ref<boolean>(false)
  const pollingInterval = ref<number | null>(null)
  
  // Optimization status tracking
  const blenderOptimized = ref<boolean | null>(null)
  const blenderError = ref<string | null>(null)
  const statusMessage = ref<string | null>(null)
  const sf3dCompleted = ref<boolean | null>(null)

  /**
   * Poll job status from Redis via backend API
   * Prevents concurrent polls with isPolling flag
   */
  const pollJobStatus = async (id: string): Promise<JobStatus | null> => {
    // Prevent concurrent polling
    if (isPolling.value) {
      logger.debug('Poll already in progress, skipping')
      return null
    }
    
    isPolling.value = true
    
    try {
      const response = await apiFetch(`/api/cells/3d-job-status/${id}`, {
        headers: {
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`)
      }

      const status: JobStatus = await response.json()
      jobStatus.value = status.status

      logger.debug(`Job ${id} status: ${status.status}`)

      if (status.status === 'completed') {
        logger.info('Job completed, processing result...')
        
        // Extract optimization status
        blenderOptimized.value = status.blender_optimized ?? status.metadata?.blenderOptimized ?? null
        blenderError.value = status.blender_error ?? status.metadata?.blenderError ?? null
        statusMessage.value = status.message ?? status.metadata?.message ?? null
        sf3dCompleted.value = status.sf3d_completed ?? status.metadata?.sf3dCompleted ?? null
        
        logger.info('Optimization status:', {
          blenderOptimized: blenderOptimized.value,
          sf3dCompleted: sf3dCompleted.value,
          hasError: !!blenderError.value
        })
        
        // Stop polling
        stopPolling()
        
        // Call completion callback
        if (onComplete && status.mesh_data) {
          onComplete(status.mesh_data, status.metadata)
        }
        
        return status
        
      } else if (status.status === 'failed' || status.status === 'error') {
        const errorMsg = status.error || 'Job processing failed'
        logger.error('Job failed', errorMsg)
        
        // Stop polling
        stopPolling()
        
        // Call error callback
        if (onError) {
          onError(errorMsg)
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
   * Start polling for job status
   * 
   * @param id - Job ID to poll
   * @param intervalMs - Polling interval in milliseconds (default: 2000)
   */
  const startPolling = (id: string, intervalMs: number = 2000) => {
    jobId.value = id
    jobStatus.value = 'processing'
    
    // Clear any existing interval
    if (pollingInterval.value) {
      clearInterval(pollingInterval.value)
    }
    
    // Start new polling interval
    pollingInterval.value = window.setInterval(() => {
      if (jobId.value) {
        pollJobStatus(jobId.value)
      }
    }, intervalMs)
    
    logger.info(`Started polling for job ${id} with interval ${intervalMs}ms`)
  }

  /**
   * Stop polling for job status
   */
  const stopPolling = () => {
    if (pollingInterval.value) {
      clearInterval(pollingInterval.value)
      pollingInterval.value = null
      logger.debug('Stopped polling')
    }
  }

  return {
    // State
    jobId,
    jobStatus,
    isPolling,
    
    // Optimization status
    blenderOptimized,
    blenderError,
    statusMessage,
    sf3dCompleted,
    
    // Methods
    startPolling,
    stopPolling,
    pollJobStatus
  }
}
