/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-01-22",
 *   "theme_compliance": 95,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-05-13",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<script setup lang="ts">
/**
 * 3D Mesh Prototyping Cell - Main View Component (Babylon.js)
 * 
 * Migrated from TresJS to Babylon.js for better physics integration and stability.
 * This component orchestrates the entire 3D mesh generation workflow with job queueing.
 * 
 * Features:
 * - Image upload for 3D reconstruction
 * - Job queueing with Redis-based status polling
 * - Babylon.js scene with per-cell engine architecture
 * - GLB loading with proper resource management
 * - Reactive viewport controls
 * 
 * @component
 */

import { ref, computed, watch, onMounted, onUnmounted, defineOptions, inject } from 'vue'
import { createLogger } from '@/utils/logger'
import { MeshPrototypingCell } from './MeshPrototypingCell'
import type { MeshPrototypingInput } from './MeshPrototypingCell'
import { apiFetch } from '@/services/apiService'
import { CELL_STATE_BRIDGE_KEY } from '#canonical/shared/cellFactory'
import type { CellStateBridge } from '#canonical/shared/cellFactory'
import { useJobPolling } from './composables/useJobPolling'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import BabylonModelViewer from '@/components/viewers/BabylonModelViewer.vue'
import JobStatusIndicator from './components/JobStatusIndicator.vue'
import ViewportControls from './components/ViewportControls.vue'
import MeshMetadataDisplay from './components/MeshMetadataDisplay.vue'
import GenerationModeSwitcher from './components/GenerationModeSwitcher.vue'
import GLBFileUploader from './components/GLBFileUploader.vue'
import { ContentUploadCell } from '#canonical/cell_types/content-upload-cell/frontend/ContentUploadCell'
import ContentSelectorModal from './components/ContentSelectorModal.vue'

// ITERATION #9: Define component name for proper Vue registration in dynamic loading context
defineOptions({ name: 'MeshPrototypingCellView' })

const logger = createLogger('component:3d-mesh-prototyping-cell-babylon')

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
// MeshPrototypingCell creates its own instance locally (for validation),
// but content_ids from displays (e.g. relative_url) must flow to the save mechanism.
const cellStateBridge = inject<CellStateBridge>(CELL_STATE_BRIDGE_KEY) ?? null

// Local component state (ITERATION #5 - writable refs for user interactions)
// ARCHITECTURE: Separate UI State from Persistence State
// localPreview: ephemeral UI state (shows immediately on upload)
// localGeneratedMesh, etc: used to update persistent cell state
const localPreview = ref<string | null>(null) // UI preview from file input (ephemeral, not persisted)
const localError = ref<string | null>(null) // Local error state (writable)
const localGeneratedMesh = ref<string | null>(null) // Generated mesh data (writable)
const localIsGenerating = ref<boolean>(false) // Generation status (writable)
const localAutoRotate = ref<boolean>(false) // Viewport setting (writable)
const localWireframeMode = ref<boolean>(false) // Viewport setting (writable)
const localShowGrid = ref<boolean>(true) // Viewport setting (writable)
const localSolidifySilhouette = ref<boolean>(false) // Silhouette processing (writable)

// Input source mode: Upload New | Select Existing
type InputSourceMode = 'upload-new' | 'select-existing'
const inputSourceMode = ref<InputSourceMode>('upload-new')

// Content selection state (G5)
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

// Model selection state (defaults to instantmesh due to SF3D FP16 precision issues)
const selectedModel = ref<MeshGenerationModel>(
  (props.cell?.initial_data?.modelType ||
   props.cell?.state?.modelType ||
   props.cell?.modelType ||
   'instantmesh') as MeshGenerationModel
)

// Manual upload state
const uploadedGLBFile = ref<File | null>(null)
const uploadedGLBUrl = ref<string | null>(null)

// Component state - Simple separation: UI state vs Persistence state
// UI Display: Priority is local preview (what user just uploaded), then fallback to persisted data
const displayImage = computed(() => {
  // ONLY use localPreview - NO fallback to props
  // Props fallback can cause re-renders when parent updates
  return localPreview.value || ''
})

const generatedMesh = computed(() => {
  // Priority chain:
  //   1. localGeneratedMesh (job completion or manual upload)
  //   2. mesh_relative_url from props (Redis Magro — content reference, set by App.vue on load)
  //   3. generatedMesh legacy base64 from props (backward compat)
  return localGeneratedMesh.value ||
         props.cell?.initial_data?.mesh_relative_url ||
         props.cell?.state?.mesh_relative_url ||
         props.cell?.initial_data?.generatedMesh ||
         props.cell?.state?.generatedMesh ||
         props.cell?.generatedMesh || ''
})

const meshMetadata = computed(() => {
  return props.cell?.initial_data?.meshMetadata || props.cell?.state?.meshMetadata || props.cell?.meshMetadata || null
})

const isGenerating = computed(() => {
  return localIsGenerating.value || 
         props.cell?.initial_data?.isGenerating || 
         props.cell?.state?.isGenerating || 
         props.cell?.isGenerating || false
})

// Error computed with local error priority (ITERATION #5)
const error = computed(() => {
  return localError.value || 
         props.cell?.initial_data?.error || 
         props.cell?.state?.error || 
         props.cell?.error || null
})

// Viewport settings with local toggle refs priority (ITERATION #5)
const autoRotate = computed(() => {
  return localAutoRotate.value || 
         props.cell?.initial_data?.viewportSettings?.autoRotate || 
         props.cell?.state?.viewportSettings?.autoRotate || 
         props.cell?.viewportSettings?.autoRotate || false
})

const wireframeMode = computed(() => {
  return localWireframeMode.value || 
         props.cell?.initial_data?.viewportSettings?.wireframeMode || 
         props.cell?.state?.viewportSettings?.wireframeMode || 
         props.cell?.viewportSettings?.wireframeMode || false
})

const showGrid = computed(() => {
  // Use logical OR but showGrid defaults to true
  return localShowGrid.value !== false && (
         props.cell?.initial_data?.viewportSettings?.showGrid !== false || 
         props.cell?.state?.viewportSettings?.showGrid !== false || 
         props.cell?.viewportSettings?.showGrid !== false)
})

// Job polling using composable
// Create authenticated fetch function for API calls
// Token comes from workspaceStore.sessionToken (populated by handshake), handled centrally by apiFetch

const {
  jobId,
  jobStatus,
  isPolling,
  blenderOptimized,
  blenderError,
  statusMessage,
  sf3dCompleted,
  startPolling,
  stopPolling
} = useJobPolling(
  apiFetch,
  // onComplete callback
  (meshData, metadata) => {
    localGeneratedMesh.value = meshData
    localError.value = null
    localIsGenerating.value = false
    logger.info('3D mesh loaded successfully', metadata)
  },
  // onError callback
  (error) => {
    localError.value = error
    localIsGenerating.value = false
    logger.error('Job failed', error)
  }
)

// File input
const fileInput = ref<HTMLInputElement | null>(null)

// Computed
const hasInputImage = computed(() => displayImage.value !== '')
const hasMesh = computed(() => {
  // Has mesh if either generated or manually uploaded
  return (generatedMesh.value !== null && generatedMesh.value !== '') || uploadedGLBUrl.value !== null
})
const cameraPosition = computed(() => {
  return props.cell?.initial_data?.viewportSettings?.cameraPosition || 
         props.cell?.state?.viewportSettings?.cameraPosition || 
         props.cell?.viewportSettings?.cameraPosition || [0, 0, 5]
})

/**
 * Convert base64 data URL to blob URL for GLTFLoader
 * Handles both generated meshes (base64) and manually uploaded files (blob URL)
 * Memoized to avoid recreating URL on every access
 */
const meshBlobUrl = computed(() => {
  // Priority: Manual upload > Generated mesh
  if (uploadedGLBUrl.value) {
    return uploadedGLBUrl.value
  }
  
  if (!generatedMesh.value) return null

  // NEW: Direct URL (relative_url from Redis Magro) — return as-is
  // Vite serves runtime/user/ assets directly, no blob conversion needed
  if (typeof generatedMesh.value === 'string' && generatedMesh.value.startsWith('/runtime/')) {
    return generatedMesh.value
  }

  try {
    const base64Data = generatedMesh.value.split(',')[1]
    const binaryData = atob(base64Data)
    const bytes = new Uint8Array(binaryData.length)
    for (let i = 0; i < binaryData.length; i++) {
      bytes[i] = binaryData.charCodeAt(i)
    }
    const blob = new Blob([bytes], { type: 'model/gltf-binary' })
    return URL.createObjectURL(blob)
  } catch (err: any) {
    logger.error('Error creating blob URL', err)
    return null
  }
})

// Track previous blob URL for cleanup
let previousBlobUrl: string | null = null

// Watch for mesh changes and cleanup old blob URLs
watch(meshBlobUrl, (newUrl, oldUrl) => {
  if (previousBlobUrl && previousBlobUrl !== newUrl) {
    URL.revokeObjectURL(previousBlobUrl)
    logger.debug('Revoked previous blob URL')
  }
  previousBlobUrl = newUrl
})

/**
 * Extract image dimensions (width, height) from a data URL.
 * Creates an off-screen Image element and resolves once loaded.
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
 * ARCHITECTURE: localPreview updated immediately for UI; async persist via ContentUploadCell
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

      logger.debug('Image loaded as base64', {
        previewLength: localPreview.value?.length || 0
      })

      // 2. Async persist via ContentUploadCell (non-blocking, generation still works without it)
      try {
        // 2a. Extract image dimensions for fragment metadata
        let fragments: Record<string, any> = {}
        try {
          const { width, height } = await getImageDimensions(result)
          fragments = { width, height }
          logger.debug(`Image dimensions: ${width}x${height}`)
        } catch (dimErr: any) {
          // Non-critical: persist still works without dimension metadata
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
          cellInstance.contentId = output.content_id
          cellInstance.contentDataRef = output.data_ref
          logger.info('Input image persisted via ContentUploadCell', {
            contentId: output.content_id,
            dataRef: output.data_ref,
            fragments,
          })
        } else {
          // Persist responded but with failure (e.g. validation error on backend)
          logger.warn('Image persist returned error (non-critical, generation still works)', {
            error: persistResult.error,
            errorCode: persistResult.error_code,
          })
        }
      } catch (persistErr: any) {
        // Non-critical: user can still generate without persistence
        logger.warn('Image persist failed (non-critical, generation still works)', persistErr)
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
  
  uploadedGLBFile.value = file
  uploadedGLBUrl.value = blobUrl
  localError.value = null
  
  // Clear any generated mesh to prioritize the uploaded one
  localGeneratedMesh.value = null
}

/**
 * Handle GLB upload error
 */
const handleGLBUploadError = (error: string) => {
  localError.value = error
  logger.error('GLB upload error', error)
}

/**
 * Open the content selector to browse persisted images (G5)
 */
const openContentSelector = () => {
  contentSelectorRef.value?.open()
}

/**
 * Handle user selection of a persisted content item (G5)
 */
const handleContentSelected = (content: any) => {
  // BUG #2 FIX: Backend returns "id", not "content_id"
  const resolvedId = content.id || content.content_id
  cellInstance.contentId = resolvedId
  cellInstance.contentDataRef = content.data_ref
  selectedContentName.value = content.filename

  // BUG #1 FIX: data_ref is "file://..." which browser cannot load as img src.
  // Convert file:// path to auth-proxy HTTP URL (/artifacts/runtime/...).
  // Auth-proxy (RuntimeFileServer) intercepts /artifacts/runtime/*,
  // validates session via cookie, and serves the file from disk.
  if (content.data_ref && typeof content.data_ref === 'string') {
    if (content.data_ref.startsWith('file://')) {
      // file://artifacts/runtime/user/... -> /artifacts/runtime/user/...
      localPreview.value = content.data_ref.replace(/^file:\/\//, '/')
      localError.value = null
    } else {
      // data URL (upload flow) or other browser-loadable format
      localPreview.value = content.data_ref
      localError.value = null
    }
  } else {
    localError.value = 'Selected content has no data reference'
    logger.warn('Content selected without data_ref', { content })
  }

  logger.info('Content selected', {
    contentId: resolvedId,
    dataRef: content.data_ref,
    filename: content.filename,
  })
}

/**
 * Resolve input image to base64 for generation.
 * If we have a base64 data URL (new upload), use directly.
 * If we have a data_ref URL (loaded from save), fetch and convert.
 */
const resolveInputImageForGeneration = async (): Promise<string> => {
  // Already have base64 in localPreview (new upload)
  if (localPreview.value?.startsWith('data:')) {
    return localPreview.value
  }

  // Have an HTTP URL (auth-proxy /artifacts/... or presigned R2) — fetch and convert to base64.
  // The auth-proxy handles session validation via cookie; no auth header needed.
  if (localPreview.value?.startsWith('http') || localPreview.value?.startsWith('/')) {
    try {
      const response = await apiFetch(localPreview.value)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const blob = await response.blob()
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result as string)
        reader.onerror = () => reject(new Error('Failed to convert blob to base64'))
        reader.readAsDataURL(blob)
      })
      // Cache in localPreview for future calls (save refetch on retry)
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
 * Generate 3D mesh from input image with mode-aware routing
 * Supports: cloud-api, local-gpu, manual-upload
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
    // Resolve image to base64 (handles both new uploads and loaded-from-save)
    let resolvedImage: string
    try {
      resolvedImage = await resolveInputImageForGeneration()
    } catch (err: any) {
      localError.value = err.message
      localIsGenerating.value = false
      return
    }

    // Prepare input for cell execution
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
      solidifySilhouette: localSolidifySilhouette.value  // User-controlled option
    }
    
    // Validate input using cell's validate method
    const validationErrors = cellInstance.validate(input)
    
    if (validationErrors.length > 0) {
      const errorMessages = validationErrors.map(e => `${e.field}: ${e.message}`).join(', ')
      throw new Error(`Validation failed: ${errorMessages}`)
    }
    
    logger.info(`Executing cell with mode: ${generationMode.value}`)

    // Execute using cell instance
    const result = await cellInstance.execute(input)
    
    logger.debug('Cell execution result:', { 
      success: result.success,
      executionTime: result.execution_time 
    })

    if (!result.success) {
      // Backend returned explicit failure
      const errorMsg = result.error || 'Unknown error'
      logger.error(`Generation failed: ${errorMsg}`)
      localError.value = errorMsg
      localIsGenerating.value = false

    } else if (result.output) {
      const output = result.output as any
      
      if (output.job_id) {
        // Async job (local-gpu mode) - start polling
        logger.info(`Job queued: ${output.job_id}`)
        startPolling(output.job_id, 2000)

      } else if (output.glb_url || output.mesh_data) {
        // Synchronous response (cloud-api mode) - load mesh directly
        logger.info('Mesh generated successfully (cloud-api)')
        localGeneratedMesh.value = output.glb_url || output.mesh_data
        localError.value = null
        localIsGenerating.value = false
        if (output.metadata) {
          logger.debug('Mesh metadata:', output.metadata)
        }
      } else {
        // Success but neither job_id nor glb_url - unexpected
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

/**
 * Download generated GLB mesh
 */
const downloadMesh = () => {
  if (!meshBlobUrl.value && !uploadedGLBFile.value) return

  logger.info('Downloading GLB mesh')

  try {
    if (uploadedGLBFile.value) {
      // Manual upload mode - use file blob
      const blob = uploadedGLBFile.value
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = uploadedGLBFile.value.name || `mesh_${Date.now()}.glb`
      link.click()
      URL.revokeObjectURL(link.href)
      logger.debug('GLB download initiated (manual upload)')

    } else if (meshBlobUrl.value && meshBlobUrl.value.startsWith('/runtime/')) {
      // NEW: Direct URL (Redis Magro) — fetch then download
      fetch(meshBlobUrl.value)
        .then(res => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`)
          return res.blob()
        })
        .then(blob => {
          const link = document.createElement('a')
          link.href = URL.createObjectURL(blob)
          link.download = `mesh_${Date.now()}.glb`
          link.click()
          URL.revokeObjectURL(link.href)
          logger.debug('GLB download initiated (Redis Magro URL)')
        })
        .catch(err => {
          logger.error('Error downloading mesh from URL', err)
          localError.value = 'Failed to download mesh file'
        })
    } else {
      // Generated mesh blob URL (legacy base64)
      const link = document.createElement('a')
      link.href = meshBlobUrl.value!
      link.download = `mesh_${Date.now()}.glb`
      link.click()
      logger.debug('GLB download initiated (blob URL)')
    }
  } catch (err) {
    logger.error('Error downloading mesh', err)
    localError.value = 'Failed to download mesh file'
  }
}

// Toggle functions (ITERATION #5 - using local refs declared above)
const toggleAutoRotate = () => {
  localAutoRotate.value = !localAutoRotate.value
  logger.debug(`Auto-rotate: ${localAutoRotate.value}`)
}

const toggleWireframe = () => {
  localWireframeMode.value = !localWireframeMode.value
  logger.debug(`Wireframe mode: ${localWireframeMode.value}`)
}

const toggleGrid = () => {
  localShowGrid.value = !localShowGrid.value
  logger.debug(`Grid: ${localShowGrid.value}`)
}

// Lifecycle - HYDRATION PHASE: Initialize from props ONLY on mount
onMounted(async () => {
  logger.info('3D Mesh Prototyping Cell (Babylon.js) mounted')

  // ── View Bridge Registration ────────────────────────────────────────────
  // Register state provider so App.vue captures content_ids during save.
  // The provider is called lazily by extractCellStateForRuntime() at save time.
  const cellId = props.cell?.cellId
  if (cellId && cellStateBridge) {
    cellStateBridge.registerStateProvider(cellId, () => {
      const ids: Record<string, any> = {}
      // mesh_relative_url: the current mesh reference (Redis Magro) or base64
      if (localGeneratedMesh.value) {
        ids.mesh_relative_url = localGeneratedMesh.value
      }
      // input_content_id: if we have a content reference for the input image
      if (cellInstance.contentId) {
        ids.input_content_id = cellInstance.contentId
        ids.input_data_ref = cellInstance.contentDataRef  // URL for direct display
      }
      // mesh_content_id: extracted from relative_url or set by cellInstance
      if (cellInstance.meshContentId) {
        ids.mesh_content_id = cellInstance.meshContentId
      }
      // Also extract content_id from relative_url if cellInstance doesn't have it yet
      if (!cellInstance.meshContentId && typeof localGeneratedMesh.value === 'string') {
        const url = localGeneratedMesh.value as string
        if (url.startsWith('/runtime/')) {
          const parts = url.split('/')
          const contentIdx = parts.indexOf('contents')
          if (contentIdx >= 0 && contentIdx + 1 < parts.length) {
            ids.mesh_content_id = parts[contentIdx + 1]
          }
        }
      }
      return ids
    })
    logger.info('[View] Registered state provider with View Bridge', { cellId })
  }

  // ── HYDRATION: Read from props ONLY on mount, never again ───────────────
  // This follows Buffer Local Pattern from REACTIVITY_ISOLATION.md

  // Hydrate input image: data_ref URL (new) → base64 (legacy fallback)
  if (!localPreview.value) {
    if (props.cell?.initial_data?.input_data_ref) {
      // BUG #3 FIX: data_ref is "file://artifacts/runtime/..." which browser cannot load as img src.
      // Convert file:// to auth-proxy HTTP URL (/artifacts/runtime/...) for browser rendering.
      const ref = props.cell.initial_data.input_data_ref
      if (ref.startsWith('file://')) {
        // file://artifacts/runtime/... -> /artifacts/runtime/... (auth-proxy serves this)
        localPreview.value = ref.replace(/^file:\/\//, '/')
        logger.info('Hydrated localPreview from input_data_ref (file:// to HTTP URL)', { ref })
      } else if (!ref.startsWith('r2://')) {
        // Directly usable (HTTP or data URL)
        localPreview.value = ref
        logger.info('Hydrated localPreview from input_data_ref URL')
      } else {
        logger.info('Skipped localPreview hydration (R2 ref, not directly loadable)', { ref })
      }
    } else if (props.cell?.initial_data?.inputImage) {
      // LEGACY: Base64 data URL fallback
      localPreview.value = props.cell.initial_data.inputImage
      logger.info('Hydrated localPreview from legacy inputImage')
    }
  }

  // Hydrate mesh from relative_url (Redis Magro — content reference)
  if (!localGeneratedMesh.value && props.cell?.initial_data?.mesh_relative_url) {
    localGeneratedMesh.value = props.cell.initial_data.mesh_relative_url
    logger.info('Hydrated mesh from mesh_relative_url', {
      url: localGeneratedMesh.value,
    })
  }

  // Hydrate mesh from legacy base64 (fallback)
  if (!localGeneratedMesh.value && props.cell?.initial_data?.generatedMesh) {
    localGeneratedMesh.value = props.cell.initial_data.generatedMesh
    logger.info('Hydrated mesh from legacy generatedMesh')
  }

  // Hydrate content_ids into cellInstance for future save operations
  if (props.cell?.initial_data?.input_content_id) {
    cellInstance.contentId = props.cell.initial_data.input_content_id
  }
  if (props.cell?.initial_data?.input_data_ref) {
    cellInstance.contentDataRef = props.cell.initial_data.input_data_ref
  }
  if (props.cell?.initial_data?.mesh_content_id) {
    cellInstance.meshContentId = props.cell.initial_data.mesh_content_id
  }

  // Debug check
  if (!displayImage.value) {
    logger.warn('No image available on mount.')
  } else {
    logger.info('Image available on mount')
  }

  // Perform health check
  try {
    const health = await cellInstance.health_check()
    if (health.status !== 'healthy') {
      logger.warn('Cell health check warning', {
        status: health.status,
        reason: health.reason
      })
      // Optionally show a UI warning if service is degraded
      if (!health.can_execute) {
        localError.value = `Service unavailable: ${health.reason}`
      }
    } else {
      logger.debug('Cell health check passed')
    }
  } catch (error: any) {
    logger.error('Cell health check failed', { error: error.message })
  }
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

  // Cleanup blob URL on unmount
  if (previousBlobUrl) {
    URL.revokeObjectURL(previousBlobUrl)
    logger.debug('Revoked blob URL on unmount')
  }

  // Cleanup uploaded GLB URL
  if (uploadedGLBUrl.value) {
    URL.revokeObjectURL(uploadedGLBUrl.value)
    logger.debug('Revoked uploaded GLB URL')
  }
  
  logger.info('3D Mesh Prototyping Cell (Babylon.js) unmounted')
})
</script>

<template>
  <div class="mesh-prototyping-container bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark p-6 rounded-lg border border-border dark:border-border-dark">
    <h2 class="text-2xl font-bold mb-4">3D Mesh Prototyping Cell</h2>
    <p class="text-text-secondary dark:text-text-secondary-dark mb-6">
      Generate volumetric 3D meshes with 360º volume from single images using AI-powered reconstruction
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
          Input Image for 3D Reconstruction
        </h3>
      </div>

      <!-- Description -->
      <p class="text-sm text-text-secondary dark:text-text-secondary-dark mb-1">
        Generate volumetric 3D meshes from 2D images
      </p>
      <p class="text-xs text-text-secondary dark:text-text-secondary-dark mb-4">
        Supported formats: PNG, JPG, JPEG
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
          📤 Upload New
        </button>
        <button
          @click="inputSourceMode = 'select-existing'"
          :class="inputSourceMode === 'select-existing'
            ? 'bg-primary text-white'
            : 'bg-surface text-text-secondary hover:bg-surface-hover'"
          class="px-4 py-2 rounded text-sm font-medium transition"
        >
          📂 Select Existing
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
          📂 Browse Library
        </button>
        <p v-if="selectedContentName" class="text-sm text-success mt-2">
          ✅ Selected: {{ selectedContentName }}
        </p>
      </div>

      <!-- Content Selection Modal Component -->
      <ContentSelectorModal
        ref="contentSelectorRef"
        @select="handleContentSelected"
      />

      <!-- Solidify Silhouette Option (moved inside card) -->
      <label v-if="selectedModel === 'instantmesh'" class="flex items-start gap-3 p-3 bg-surface-light dark:bg-surface-dark-light rounded border border-border dark:border-border-dark cursor-pointer">
        <input
          v-model="localSolidifySilhouette"
          type="checkbox"
          :disabled="isGenerating"
          class="w-5 h-5 rounded border-border dark:border-border-dark text-primary focus:ring-2 focus:ring-primary mt-0.5"
        />
        <div class="flex-1">
          <div class="text-sm font-medium text-text-primary dark:text-text-primary-dark">
            Solidify Silhouette
            <span class="text-xs text-text-secondary dark:text-text-secondary-dark font-normal">(Only for InstantMesh)</span>
          </div>
          <div class="text-xs text-text-secondary dark:text-text-secondary-dark mt-1">
            <span v-if="localSolidifySilhouette">
              🔧 Enabled: Fixes incomplete geometry (good for objects with fine details like fur, whiskers)
            </span>
            <span v-else>
              ⚡ Disabled: Fast mode (good for clean silhouettes like boxes, simple shapes)
            </span>
          </div>
        </div>
      </label>
    </div>

    <!-- Image Preview Container -->
    <div class="mb-6 p-4 bg-surface-light dark:bg-surface-dark-light rounded border border-border dark:border-border-dark">
      <label class="block text-sm font-medium mb-4 text-text-primary dark:text-text-primary-dark">
        📤 Input Image Preview
      </label>
      <!-- Image preview / placeholder -->
      <div class="preview-container border-2 border-dashed border-border dark:border-border-dark p-4 rounded">
        <img
          v-if="displayImage"
          :src="displayImage"
          alt="Input for reconstruction"
          class="w-full h-auto rounded"
          style="max-height: 400px;"
        />
        <p v-else class="text-sm text-text-secondary dark:text-text-secondary-dark text-center py-8">
          No image selected. Upload or select an image above.
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
      <span v-if="isGenerating">{{ jobStatus === 'processing' ? 'Processing...' : 'Queueing...' }}</span>
      <span v-else>
        Generate 3D Mesh
        <span v-if="generationMode === 'cloud-api'"> (Cloud API)</span>
      </span>
    </button>

    <!-- Babylon.js Viewer Controls -->
    <ViewportControls
      :auto-rotate="autoRotate"
      :wireframe-mode="wireframeMode"
      :show-grid="showGrid"
      :has-mesh="hasMesh"
      @toggle-auto-rotate="toggleAutoRotate"
      @toggle-wireframe="toggleWireframe"
      @toggle-grid="toggleGrid"
      @download-mesh="downloadMesh"
    />

    <!-- Babylon.js 3D Mesh Viewer (only shows generated mesh) -->
    <div
      v-if="generationMode !== 'manual-upload' || hasMesh"
      class="babylon-viewer-container bg-surface-dark dark:bg-black rounded border border-border dark:border-border-dark"
      :style="{ width: '100%', height: '500px' }"
    >
      <!-- Show 3D mesh if generated -->
      <BabylonModelViewer
        v-if="hasMesh && meshBlobUrl"
        :url="meshBlobUrl"
        :wireframe="wireframeMode"
        :auto-rotate="autoRotate"
        :show-grid="showGrid"
        background-color="#ffffff"
        :grid-visible="false"
      />

      <!-- Show waiting message when generating -->
      <div v-else class="flex items-center justify-center h-full">
        <p class="text-text-secondary dark:text-text-secondary-dark">
          {{ isGenerating ? 'Generating 3D mesh...' : 'Generate a 3D mesh to view it here' }}
        </p>
      </div>
    </div>

    <!-- Mesh Metadata -->
    <MeshMetadataDisplay :metadata="meshMetadata" />
  </div>
</template>

<style scoped>
.mesh-prototyping-container {
  font-family: 'Inter', sans-serif;
}
</style>
