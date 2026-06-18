<template>
  <div class="mesh-prototyping-container bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark p-6 rounded-lg border border-border dark:border-border-dark">
    <h2 class="text-2xl font-bold mb-4">{{ $t('artifacts.meshPrototypingCell.title') }}</h2>
    <p class="text-text-secondary dark:text-text-secondary-dark mb-6">
      {{ $t('artifacts.meshPrototypingCell.description') }}
    </p>

    <!-- Error Display -->
    <div v-if="error" class="bg-error/10 dark:bg-error/20 border border-error text-error dark:text-error-light px-4 py-3 rounded mb-4">
      <strong>{{ $t('artifacts.meshPrototypingCell.errorLabel') }}</strong> {{ error }}
    </div>

    <!-- Generation Mode Switcher -->
    <GenerationModeSwitcher
      v-model="generationMode"
      :disabled="isGenerating"
      class="mb-6"
    />

    <!-- Job Status -->
    <JobStatusIndicator
      v-if="generationMode !== 'manual-upload'"
      :is-generating="isGenerating"
      :job-status="jobStatus"
      :job-id="jobId"
      :blender-optimized="blenderOptimized"
      :blender-error="blenderError"
      :message="statusMessage"
    />

    <!-- Manual Upload Section -->
    <GLBFileUploader
      v-if="generationMode === 'manual-upload'"
      :disabled="isGenerating"
      @upload="handleGLBUpload"
      @error="handleGLBUploadError"
      class="mb-6"
    />

    <!-- Image Upload Section (Card Container) -->
    <div v-if="generationMode !== 'manual-upload'" class="p-6 bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg mb-6">
      <!-- Header with Icon -->
      <div class="flex items-center gap-2 mb-4">
        <span class="text-2xl">📤</span>
        <h3 class="text-lg font-semibold text-text-primary dark:text-text-primary-dark">
          {{ $t('artifacts.meshPrototypingCell.inputImageSection.title') }}
        </h3>
      </div>

      <!-- Description -->
      <p class="text-sm text-text-secondary dark:text-text-secondary-dark mb-1">
        {{ $t('artifacts.meshPrototypingCell.inputImageSection.description') }}
      </p>
      <p class="text-xs text-text-secondary dark:text-text-secondary-dark mb-4">
        {{ $t('artifacts.meshPrototypingCell.inputImageSection.supportedFormats') }}
      </p>

      <!-- Input Source Mode Tabs: Upload New | Select Existing -->
      <div class="flex gap-2 mb-4">
        <button
          @click="inputSourceMode = 'upload-new'"
          :class="inputSourceMode === 'upload-new'
            ? 'bg-primary text-white'
            : 'bg-surface text-text-secondary hover:bg-surface-hover'"
          class="px-4 py-2 rounded text-sm font-medium transition"
        >
          {{ $t('artifacts.meshPrototypingCell.inputImageSection.uploadNew') }}
        </button>
        <button
          @click="inputSourceMode = 'select-existing'"
          :class="inputSourceMode === 'select-existing'
            ? 'bg-primary text-white'
            : 'bg-surface text-text-secondary hover:bg-surface-hover'"
          class="px-4 py-2 rounded text-sm font-medium transition"
        >
          {{ $t('artifacts.meshPrototypingCell.inputImageSection.selectExisting') }}
        </button>
      </div>

      <!-- Tab: Upload New -->
      <div v-if="inputSourceMode === 'upload-new'">
        <input
          ref="fileInput"
          type="file"
          accept="image/*"
          @change="handleFileUpload"
          class="block w-full text-sm text-text-secondary dark:text-text-secondary-dark p-3 border border-dashed border-border dark:border-border-dark rounded mb-4 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-primary dark:file:bg-primary-light file:text-white hover:file:bg-primary-hover dark:hover:file:bg-primary"
          :disabled="isGenerating"
        />
      </div>

      <!-- Tab: Select Existing -->
      <div v-if="inputSourceMode === 'select-existing'">
        <button
          @click="openContentSelector"
          :disabled="isGenerating"
          class="bg-primary hover:bg-primary-hover text-white px-4 py-2 rounded text-sm transition"
        >
          {{ $t('artifacts.meshPrototypingCell.inputImageSection.browseLibrary') }}
        </button>
        <p v-if="selectedContentName" class="text-sm text-success mt-2">
          {{ $t('artifacts.meshPrototypingCell.inputImageSection.selected', { name: selectedContentName }) }}
        </p>
      </div>

      <!-- Content Selection Modal Component -->
      <ContentSelectorModal
        ref="contentSelectorRef"
        @select="handleContentSelected"
      />

      <!-- Solidify Silhouette Option -->
      <label v-if="selectedModel === 'instantmesh'" class="flex items-start gap-3 p-3 bg-surface-light dark:bg-surface-dark-light rounded border border-border dark:border-border-dark cursor-pointer">
        <input
          v-model="localSolidifySilhouette"
          type="checkbox"
          :disabled="isGenerating"
          class="w-5 h-5 rounded border-border dark:border-border-dark text-primary focus:ring-2 focus:ring-primary mt-0.5"
        />
        <div class="flex-1">
          <div class="text-sm font-medium text-text-primary dark:text-text-primary-dark">
            {{ $t('artifacts.meshPrototypingCell.inputImageSection.solidifySilhouette') }}
            <span class="text-xs text-text-secondary dark:text-text-secondary-dark font-normal">{{ $t('artifacts.meshPrototypingCell.inputImageSection.onlyForInstantMesh') }}</span>
          </div>
          <div class="text-xs text-text-secondary dark:text-text-secondary-dark mt-1">
            <span v-if="localSolidifySilhouette">
              {{ $t('artifacts.meshPrototypingCell.inputImageSection.solidifyEnabled') }}
            </span>
            <span v-else>
              {{ $t('artifacts.meshPrototypingCell.inputImageSection.solidifyDisabled') }}
            </span>
          </div>
        </div>
      </label>
    </div>

    <!-- Image Preview Container -->
    <div class="mb-6 p-4 bg-surface-light dark:bg-surface-dark-light rounded border border-border dark:border-border-dark">
      <label class="block text-sm font-medium mb-4 text-text-primary dark:text-text-primary-dark">
        {{ $t('artifacts.meshPrototypingCell.inputImagePreview.title') }}
      </label>
      <div class="preview-container border-2 border-dashed border-border dark:border-border-dark p-4 rounded">
        <img
          v-if="displayImage"
          :src="displayImage"
          :alt="$t('artifacts.meshPrototypingCell.inputImagePreview.altText')"
          class="w-full h-auto rounded"
          style="max-height: 400px;"
        />
        <p v-else class="text-sm text-text-secondary dark:text-text-secondary-dark text-center py-8">
          {{ $t('artifacts.meshPrototypingCell.inputImagePreview.noImage') }}
        </p>
      </div>
    </div>

    <!-- Generate Button (only for generation modes) -->
    <button
      v-if="generationMode !== 'manual-upload'"
      @click="generate3DMesh"
      :disabled="!hasInputImage || isGenerating"
      class="bg-success dark:bg-success-light hover:bg-success-dark dark:hover:bg-success disabled:bg-surface-disabled dark:disabled:bg-surface-disabled disabled:cursor-not-allowed text-white font-semibold py-2 px-6 rounded mb-6 transition"
    >
      <span v-if="isGenerating">{{ jobStatus === 'processing' ? $t('artifacts.meshPrototypingCell.generating.processing') : $t('artifacts.meshPrototypingCell.generating.queueing') }}</span>
      <span v-else>
        {{ $t('artifacts.meshPrototypingCell.generating.generate') }}
        <span v-if="generationMode === 'cloud-api'">{{ $t('artifacts.meshPrototypingCell.generating.cloudApiSuffix') }}</span>
      </span>
    </button>

    <!-- Job History Section (substitui preview inline do Babylon) -->
    <div class="job-history-section mt-6 border-t border-border dark:border-border-dark pt-4">
      <h4 class="text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-2">
        {{ $t('artifacts.meshPrototypingCell.recentJobs') }}
      </h4>

      <!-- Loading -->
      <div v-if="localJobsLoading" class="text-center py-4">
        <svg class="animate-spin h-5 w-5 text-primary mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      </div>

      <!-- Empty state -->
      <div v-else-if="localRecentJobs.length === 0" class="text-center py-6 text-text-secondary dark:text-text-secondary-dark text-sm">
        {{ $t('artifacts.meshPrototypingCell.noRecentJobs') }}
      </div>

      <!-- Job list -->
      <div v-else class="space-y-1">
        <div v-for="job in localRecentJobs" :key="job.id || job.job_id"
             class="flex items-center gap-2 py-1.5 px-2 rounded text-xs hover:bg-surface-light dark:hover:bg-surface-dark-light">
          <!-- Status indicator -->
          <span v-if="job.status === 'processing' || job.status === 'queued'"
                class="w-2 h-2 rounded-full bg-blue-500 animate-pulse inline-block"></span>
          <span v-else-if="job.status === 'success' || job.status === 'completed'"
                class="w-2 h-2 rounded-full bg-green-500 inline-block"></span>
          <span v-else-if="job.status === 'failed'"
                class="w-2 h-2 rounded-full bg-red-500 inline-block"></span>
          <span v-else class="w-2 h-2 rounded-full bg-gray-400 inline-block"></span>

          <!-- Status text -->
          <span class="text-text-secondary min-w-[60px]">{{ job.status }}</span>

          <!-- Date -->
          <span class="text-text-secondary font-mono">{{ formatJobDate(job.enqueued_at) }}</span>

          <!-- Completed job → Open in GLB Viewer -->
          <span v-if="(job.status === 'success' || job.status === 'completed') && (job.relative_url || job.content_id)"
                class="ml-auto text-primary hover:underline cursor-pointer" @click="openGLBViewer(job)">
            {{ $t('artifacts.meshPrototypingCell.viewResult') }}
          </span>
        </div>
      </div>

      <!-- Open full Job Manager -->
      <button v-if="cellFactory && localRecentJobs.length > 0"
              @click="openJobManager"
              class="mt-3 text-xs text-primary hover:underline">
        {{ $t('artifacts.meshPrototypingCell.viewAllJobs') }}
      </button>
    </div>

    <!-- Toast notification -->
    <div
      v-if="toastMessage"
      class="fixed bottom-4 right-4 z-50 px-4 py-2 rounded shadow-lg text-sm text-white transition-opacity duration-300"
      :class="toastType === 'success' ? 'bg-green-600' : 'bg-red-600'"
    >
      {{ toastMessage }}
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 3D Mesh Prototyping Cell - Main View Component
 *
 * Refactored to follow PNG Generator Cell pattern:
 * - No inline Babylon.js viewer (3D models open in glb-content-viewer cell)
 * - Job history list with "Open in GLB Viewer" button for completed jobs
 * - Job Manager Cell integration for full job history
 * - Image upload for 3D reconstruction
 * - Job queueing with shared useJobPolling composable (MongoDB SSOT)
 *
 * @component
 * @i18n-full-conversion 2026-06-09
 */

import { ref, computed, watch, onMounted, onUnmounted, defineOptions, inject } from 'vue'
import { useI18n } from 'vue-i18n'
import { createLogger } from '@/utils/logger'
import { MeshPrototypingCell } from './MeshPrototypingCell'
import type { MeshPrototypingInput } from './MeshPrototypingCell'
import { apiFetch } from '@/services/apiService'
import { CELL_STATE_BRIDGE_KEY, CELL_FACTORY_KEY } from '#canonical/shared/cellFactory'
import type { CellStateBridge, CellFactory } from '#canonical/shared/cellFactory'
import { useJobPolling } from '#shared/composables/useJobPolling'
import { useToast } from '#shared/composables/useToast'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import JobStatusIndicator from './components/JobStatusIndicator.vue'
import GenerationModeSwitcher from './components/GenerationModeSwitcher.vue'
import GLBFileUploader from './components/GLBFileUploader.vue'
import { ContentUploadCell } from '#canonical/cell_types/content-upload-cell/frontend/ContentUploadCell'
import ContentSelectorModal from './components/ContentSelectorModal.vue'

defineOptions({ name: 'MeshPrototypingCellView' })

const logger = createLogger('component:3d-mesh-prototyping-cell')
const { t } = useI18n()

const { toastMessage, toastType, showToast } = useToast()

// Initialize MeshPrototypingCell instance
const cellInstance = new MeshPrototypingCell()

interface Props {
  cell: any // Flexible to handle initial_data, state, or direct properties
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:cell', value: any): void
}>()

// View Bridge: register state providers so App.vue captures content_ids during save
const cellStateBridge = inject<CellStateBridge>(CELL_STATE_BRIDGE_KEY) ?? null

// CellFactory: inject for creating child cells (glb-content-viewer, job-manager-cell)
const cellFactory = inject<CellFactory>(CELL_FACTORY_KEY)

// Local component state
const localPreview = ref<string | null>(null) // UI preview from file input (ephemeral, not persisted)
const localError = ref<string | null>(null) // Local error state (writable)
const localIsGenerating = ref<boolean>(false) // Generation status (writable)
const localSolidifySilhouette = ref<boolean>(false) // Silhouette processing (writable)

// Input source mode: Upload New | Select Existing
type InputSourceMode = 'upload-new' | 'select-existing'
const inputSourceMode = ref<InputSourceMode>('upload-new')

// Content selection state
const selectedContentName = ref<string | null>(null)
const contentSelectorRef = ref<InstanceType<typeof ContentSelectorModal> | null>(null)

// Generation mode state
type GenerationMode = 'cloud-api' | 'local-gpu' | 'manual-upload'
type MeshGenerationModel = 'sf3d' | 'instantmesh'

const generationMode = ref<GenerationMode>(
  (props.cell?.initial_data?.generationMode ||
   props.cell?.state?.generationMode ||
   props.cell?.generationMode ||
   'local-gpu') as GenerationMode
)

const selectedModel = ref<MeshGenerationModel>(
  (props.cell?.initial_data?.modelType ||
   props.cell?.state?.modelType ||
   props.cell?.modelType ||
   'instantmesh') as MeshGenerationModel
)

// Job history state
const localRecentJobs = ref<any[]>([])
const localJobsLoading = ref(false)

// Computed
const displayImage = computed(() => {
  return localPreview.value || ''
})

const isGenerating = computed(() => {
  return localIsGenerating.value ||
         props.cell?.initial_data?.isGenerating ||
         props.cell?.state?.isGenerating ||
         props.cell?.isGenerating || false
})

const error = computed(() => {
  return localError.value ||
         props.cell?.initial_data?.error ||
         props.cell?.state?.error ||
         props.cell?.error || null
})

const hasInputImage = computed(() => displayImage.value !== '')

// Job polling using shared composable (MongoDB SSOT via GET /api/cells/job-status/{job_id})
const {
  jobId,
  jobStatus,
  isPolling,
  startPolling,
  stopPolling
} = useJobPolling(apiFetch)

// Optimization status refs (set from shared polling completion callback)
const blenderOptimized = ref<boolean | null>(null)
const blenderError = ref<string | null>(null)
const statusMessage = ref<string | null>(null)
const sf3dCompleted = ref<boolean | null>(null)

// File input
const fileInput = ref<HTMLInputElement | null>(null)

/**
 * Extract image dimensions from a data URL
 */
const getImageDimensions = (dataUrl: string): Promise<{ width: number; height: number }> => {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight })
    img.onerror = () => reject(new Error('Failed to decode image for dimension extraction'))
    img.src = dataUrl
  })
}

/**
 * Handle image file upload
 */
const getCurrentAssigneeId = (): string => {
  try {
    const store = useWorkspaceStore()
    return store.sessionUserId || store.userId || ''
  } catch {
    return ''
  }
}

const handleFileUpload = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]

  if (!file) return

  if (!file.type.startsWith('image/')) {
    localError.value = 'Please upload a valid image file (PNG, JPG, etc.)'
    return
  }

  logger.info(`File selected: ${file.name} (${file.size} bytes)`)

  const reader = new FileReader()

  reader.onload = async (e) => {
    try {
      const result = e.target?.result as string

      // 1. IMMEDIATE UI UPDATE: Display the image right away
      localPreview.value = result
      localError.value = null

      // 2. Async persist via ContentUploadCell (non-blocking, generation still works without it)
      try {
        let fragments: Record<string, any> = {}
        try {
          const { width, height } = await getImageDimensions(result)
          fragments = { width, height }
        } catch (dimErr: any) {
          logger.warn('Could not extract image dimensions', dimErr)
        }

        const uploader = new ContentUploadCell()
        const assigneeId = getCurrentAssigneeId()
        const persistResult = await uploader.execute({
          filename: file.name,
          binary: result,
          assignee_id: assigneeId,
          content_type_id: 'image-png',
          fragments,
        })

        if (persistResult.success) {
          const output = persistResult.output as any
          const contentId = output.id || output.content_id
          cellInstance.contentId = contentId
          cellInstance.contentDataRef = output.data_ref
          logger.info('Input image persisted via ContentUploadCell', { contentId, dataRef: output.data_ref })
        } else {
          const persistMsg = persistResult.error || 'Unknown persist error'
          localError.value = `Image upload failed (generation still works): ${persistMsg}`
          logger.warn('Image persist returned error (non-critical, generation still works)', { error: persistMsg })
        }
      } catch (persistErr: any) {
        localError.value = `Image persist failed (generation still works): ${persistErr.message}`
        logger.warn('Image persist failed (non-critical, generation still works)', { error: persistErr.message })
      }
    } catch (err: any) {
      localError.value = `Image load failed: ${err.message}`
      logger.error('Image load error', err)
    }
  }

  reader.onerror = () => {
    localError.value = 'Failed to read image file'
    logger.error('FileReader error')
  }

  reader.readAsDataURL(file)
}

/**
 * Handle GLB file upload (manual upload mode)
 */
const handleGLBUpload = (file: File, blobUrl: string) => {
  logger.info(`GLB file uploaded: ${file.name} (${file.size} bytes)`)
  localError.value = null
}

/**
 * Handle GLB upload error
 */
const handleGLBUploadError = (error: string) => {
  localError.value = error
  logger.error('GLB upload error', error)
}

/**
 * Open the content selector to browse persisted images
 */
const openContentSelector = () => {
  contentSelectorRef.value?.open()
}

/**
 * Handle user selection of a persisted content item
 */
const handleContentSelected = (content: any) => {
  const resolvedId = content.id || content.content_id
  cellInstance.contentId = resolvedId
  cellInstance.contentDataRef = content.data_ref
  selectedContentName.value = content.filename

  if (content.data_ref && typeof content.data_ref === 'string') {
    if (content.data_ref.startsWith('file://')) {
      localPreview.value = content.data_ref.replace(/^file:\/\//, '/')
      localError.value = null
    } else if (
      content.data_ref.startsWith('data:') ||
      content.data_ref.startsWith('http://') ||
      content.data_ref.startsWith('https://')
    ) {
      localPreview.value = content.data_ref
      localError.value = null
    } else if (content.data_ref.startsWith('pending:')) {
      localError.value = 'This content is still being processed. Please try again later.'
      localPreview.value = null
    } else {
      localError.value = 'Selected content has no valid data reference'
      localPreview.value = null
    }
  } else {
    localError.value = 'Selected content has no data reference'
  }
}

/**
 * Resolve input image to base64 for generation
 */
const resolveInputImageForGeneration = async (): Promise<string> => {
  if (localPreview.value?.startsWith('data:')) {
    return localPreview.value
  }

  if (localPreview.value?.startsWith('http') || localPreview.value?.startsWith('/')) {
    try {
      const response = await fetch(localPreview.value)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const blob = await response.blob()
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result as string)
        reader.onerror = () => reject(new Error('Failed to convert blob to base64'))
        reader.readAsDataURL(blob)
      })
      localPreview.value = dataUrl
      return dataUrl
    } catch (err: any) {
      logger.error('Failed to resolve HTTP URL for generation', err)
      throw new Error('Cannot resolve input image: ' + err.message)
    }
  }

  throw new Error('No input image available for generation')
}

/**
 * Fetch recent 3D jobs from backend
 */
const fetchRecentJobs = async () => {
  localJobsLoading.value = true
  try {
    const response = await apiFetch(
      '/api/cells/jobs?job_type=hunyuan3d_generate&limit=10'
    )
    const data = await response.json()
    localRecentJobs.value = (data.jobs || []).slice(0, 10)
  } catch (err: any) {
    logger.error('Failed to fetch recent jobs', { error: err.message })
    localRecentJobs.value = []
  } finally {
    localJobsLoading.value = false
  }
}

/**
 * Open GLB Content Viewer for a completed job
 */
const openGLBViewer = async (job: any) => {
  if (!cellFactory) {
    logger.warn('Cannot open GLB Viewer: cellFactory not available')
    return
  }
  try {
    const initialData: Record<string, any> = {}
    if (job.relative_url) {
      initialData.relative_url = job.relative_url
    } else if (job.content_id) {
      initialData.content_id = job.content_id
    }
    await cellFactory.addChildCell('glb-content-viewer', initialData)
    logger.info('GLB Content Viewer created from 3D Mesh Cell', { jobId: job.id || job.job_id })
  } catch (err: any) {
    logger.warn('Failed to open GLB Viewer', { error: err.message })
  }
}

/**
 * Open Job Manager Cell contextualized for 3D jobs
 */
const openJobManager = async () => {
  if (!cellFactory) return
  try {
    await cellFactory.addChildCell('job-manager-cell', {
      job_type_filter: 'hunyuan3d_generate',
    })
    logger.info('Job Manager Cell created from 3D Mesh Cell')
  } catch (err: any) {
    logger.warn('Failed to open Job Manager', { error: err.message })
  }
}

/**
 * Format date for compact display
 */
const formatJobDate = (dateStr?: string): string => {
  if (!dateStr) return '—'
  try {
    const d = new Date(dateStr)
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return dateStr.substring(0, 10)
  }
}

/**
 * Generate 3D mesh from input image with mode-aware routing
 */
const generate3DMesh = async () => {
  if (!displayImage.value && generationMode.value !== 'manual-upload') {
    localError.value = 'Please upload an image first'
    return
  }

  logger.info(`Starting 3D mesh generation with mode: ${generationMode.value}`)

  localIsGenerating.value = true
  localError.value = null

  try {
    let resolvedImage: string
    try {
      resolvedImage = await resolveInputImageForGeneration()
    } catch (err: any) {
      localError.value = err.message
      localIsGenerating.value = false
      return
    }

    const reconstructionParams = props.cell?.initial_data?.reconstructionParams ||
                                props.cell?.state?.reconstructionParams ||
                                props.cell?.reconstructionParams || {
                                  targetFaces: 10000,
                                  enableDracoCompression: true,
                                  compressionLevel: 7,
                                  targetFileSizeMB: 10
                                }

    const input: MeshPrototypingInput = {
      inputImage: resolvedImage,
      input_content_id: cellInstance.contentId || undefined,
      generationMode: generationMode.value,
      modelType: selectedModel.value,
      reconstructionParams,
      solidifySilhouette: localSolidifySilhouette.value
    }

    const validationErrors = cellInstance.validate(input)

    if (validationErrors.length > 0) {
      const errorMessages = validationErrors.map(e => `${e.field}: ${e.message}`).join(', ')
      throw new Error(`Validation failed: ${errorMessages}`)
    }

    const result = await cellInstance.execute(input)

    if (!result.success) {
      const errorMsg = result.error || 'Unknown error'
      logger.error(`Generation failed: ${errorMsg}`)
      localError.value = errorMsg
      localIsGenerating.value = false

    } else if (result.output) {
      const output = result.output as any

      if (output.job_id) {
        // Async job (local-gpu mode) - start polling
        // DESBLOQUEIA botão imediatamente — usuário pode enfileirar mais jobs
        localIsGenerating.value = false
        // Feedback: mensagem de confirmação
        showToast(t('meshPrototypingCell.jobEnqueued'), 'success')
        logger.info(`Job queued: ${output.job_id}`)
        startPolling(output.job_id, {
          intervalMs: 2000,
          onComplete: async (job: any) => {
            localError.value = null
            logger.info('3D mesh generation completed', { job })
            // Refresh the recent jobs list to show the completed job
            await fetchRecentJobs()
          },
          onError: (err: string) => {
            localError.value = err
            logger.error('Job failed', err)
          }
        })

      } else if (output.glb_url || output.mesh_data) {
        // Synchronous response (cloud-api mode)
        logger.info('Mesh generated successfully (cloud-api)')
        localError.value = null
        localIsGenerating.value = false
        await fetchRecentJobs()
      } else {
        const unexpectedMsg = 'Unexpected response: no job ID or GLB URL received'
        logger.error(unexpectedMsg)
        localError.value = unexpectedMsg
        localIsGenerating.value = false
      }
    } else {
      const unexpectedMsg = 'Unexpected response: no output data'
      logger.error(unexpectedMsg)
      localError.value = unexpectedMsg
      localIsGenerating.value = false
    }
  } catch (err: any) {
    logger.error('Error generating 3D mesh', err)
    localError.value = `Generation error: ${err.message}`
    localIsGenerating.value = false
  }
}

// Lifecycle
onMounted(async () => {
  logger.info('3D Mesh Prototyping Cell mounted')

  // ── View Bridge Registration ──
  const cellId = props.cell?.cellId
  if (cellId && cellStateBridge) {
    cellStateBridge.registerStateProvider(cellId, () => {
      const ids: Record<string, any> = {}
      if (cellInstance.contentId) {
        ids.input_content_id = cellInstance.contentId
        ids.input_data_ref = cellInstance.contentDataRef
      }
      return ids
    })
    logger.info('[View] Registered state provider with View Bridge', { cellId })
  }

  // ── HYDRATION: Read from props ONLY on mount ──
  if (!localPreview.value) {
    if (props.cell?.initial_data?.input_data_ref) {
      const ref = props.cell.initial_data.input_data_ref
      if (ref.startsWith('file://')) {
        localPreview.value = ref.replace(/^file:\/\//, '/')
      } else if (!ref.startsWith('r2://')) {
        localPreview.value = ref
      }
    } else if (props.cell?.initial_data?.inputImage) {
      localPreview.value = props.cell.initial_data.inputImage
    }
  }

  // Hydrate content_ids into cellInstance
  if (props.cell?.initial_data?.input_content_id) {
    cellInstance.contentId = props.cell.initial_data.input_content_id
  }
  if (props.cell?.initial_data?.input_data_ref) {
    cellInstance.contentDataRef = props.cell.initial_data.input_data_ref
  }

  // Perform health check
  try {
    const health = await cellInstance.health_check()
    if (health.status !== 'healthy') {
      logger.warn('Cell health check warning', { status: health.status, reason: health.reason })
      if (!health.can_execute) {
        localError.value = `Service unavailable: ${health.reason}`
      }
    }
  } catch (error: any) {
    logger.error('Cell health check failed', { error: error.message })
  }

  // Fetch recent 3D jobs
  await fetchRecentJobs()
})

onUnmounted(() => {
  // Unregister from View Bridge
  const cellId = props.cell?.cellId
  if (cellId && cellStateBridge) {
    cellStateBridge.unregisterStateProvider(cellId)
    logger.info('[View] Unregistered state provider from View Bridge', { cellId })
  }

  // Stop polling
  stopPolling()

  logger.info('3D Mesh Prototyping Cell unmounted')
})
</script>

<style scoped>
.mesh-prototyping-container {
  font-family: 'Inter', sans-serif;
}
</style>
