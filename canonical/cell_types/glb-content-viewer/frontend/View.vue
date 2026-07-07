<template>
  <div class="glb-content-viewer bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg p-4 shadow-sm">
    <div class="cell-header mb-4">
      <h3 class="text-lg font-semibold text-primary dark:text-primary-light">
        {{ $t('glbContentCell.title') }}
      </h3>
      <p class="text-sm text-text-secondary dark:text-text-secondary-dark mt-1">
        {{ $t('glbContentCell.description') }}
      </p>
    </div>

    <div class="cell-content space-y-4">
      <!-- LOADING STATE -->
      <div
        v-if="localIsLoading"
        class="loading-state flex flex-col items-center justify-center py-12"
      >
        <svg
          class="animate-spin h-10 w-10 text-primary mb-4"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        <p class="text-text-secondary dark:text-text-secondary-dark">
          {{ $t('glbContentCell.loading') }}
        </p>
      </div>

      <!-- ERROR STATE -->
      <div
        v-if="localError && !localIsLoading"
        class="error-state p-4 bg-error-light dark:bg-error-dark text-error-dark dark:text-error-light rounded border border-error"
      >
        <div class="flex items-start gap-3">
          <svg class="h-6 w-6 flex-shrink-0 mt-0.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <p class="font-medium">{{ $t('glbContentCell.errorTitle') }}</p>
            <p class="text-sm mt-1">{{ localError }}</p>
            <button
              v-if="localRetryAvailable"
              class="mt-2 px-3 py-1 text-sm bg-primary dark:bg-primary-hover text-white rounded hover:bg-primary-hover dark:hover:bg-primary-light transition"
              @click="loadContent"
            >
              {{ $t('glbContentCell.retry') }}
            </button>
          </div>
        </div>
      </div>

      <!-- EMPTY STATE -->
      <div
        v-if="displayIsEmpty && !localIsLoading && !localError"
        class="empty-state flex flex-col items-center justify-center py-12 text-text-secondary dark:text-text-secondary-dark"
      >
        <svg class="h-16 w-16 mb-4 opacity-40" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
        </svg>
        <p class="text-lg font-medium mb-1">
          {{ $t('glbContentCell.noContent') }}
        </p>
        <p class="text-sm">
          {{ $t('glbContentCell.noContentDescription') }}
        </p>
      </div>

      <!-- LOADED STATE: Babylon.js 3D Viewer -->
      <div v-if="displayContentLoaded && !localIsLoading" class="model-display-section">
        <div class="model-viewer-container bg-white dark:bg-gray-800 border border-border dark:border-border-dark rounded overflow-hidden" style="min-height: 300px; height: 400px;">
          <BabylonModelViewer
            v-if="displayModelUrl"
            :url="displayModelUrl"
            :wireframe="localWireframeMode"
            :auto-rotate="localAutoRotate"
            :show-grid="localShowGrid"
            background-color="#f8f9fa"
          />
          <div v-else class="flex items-center justify-center h-full text-text-secondary dark:text-text-secondary-dark text-sm">
            {{ $t('glbContentCell.modelNotAvailable') }}
          </div>
        </div>
      </div>

      <!-- ACTION BUTTONS (when loaded) -->
      <div v-if="displayContentLoaded && !localIsLoading" class="actions-section flex flex-wrap gap-2 pt-2 border-t border-border dark:border-border-dark">
        <!-- Viewport Controls -->
        <button
          class="px-3 py-1.5 text-sm bg-surface-light dark:bg-surface-dark-light border border-border dark:border-border-dark rounded hover:bg-surface-hover dark:hover:bg-surface-dark-hover transition flex items-center gap-1.5"
          :title="$t('glbContentCell.autoRotate')"
          @click="localAutoRotate = !localAutoRotate"
        >
          <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>{{ localAutoRotate ? $t('glbContentCell.autoRotateOn') : $t('glbContentCell.autoRotateOff') }}</span>
        </button>

        <button
          class="px-3 py-1.5 text-sm bg-surface-light dark:bg-surface-dark-light border border-border dark:border-border-dark rounded hover:bg-surface-hover dark:hover:bg-surface-dark-hover transition flex items-center gap-1.5"
          :title="$t('glbContentCell.wireframe')"
          @click="localWireframeMode = !localWireframeMode"
        >
          <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
          </svg>
          <span>{{ localWireframeMode ? $t('glbContentCell.wireframeOn') : $t('glbContentCell.wireframeOff') }}</span>
        </button>

        <button
          class="px-3 py-1.5 text-sm bg-surface-light dark:bg-surface-dark-light border border-border dark:border-border-dark rounded hover:bg-surface-hover dark:hover:bg-surface-dark-hover transition flex items-center gap-1.5"
          :title="$t('glbContentCell.grid')"
          @click="localShowGrid = !localShowGrid"
        >
          <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h12a2 2 0 012 2v12a2 2 0 01-2 2H6a2 2 0 01-2-2V6z" />
          </svg>
          <span>{{ localShowGrid ? $t('glbContentCell.gridOn') : $t('glbContentCell.gridOff') }}</span>
        </button>

        <!-- Download Button -->
        <button
          class="px-3 py-1.5 text-sm bg-surface-light dark:bg-surface-dark-light border border-border dark:border-border-dark rounded hover:bg-surface-hover dark:hover:bg-surface-dark-hover transition flex items-center gap-1.5"
          :title="$t('glbContentCell.download')"
          @click="handleDownload"
        >
          <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span>{{ $t('glbContentCell.download') }}</span>
        </button>
      </div>

      <!-- Metadata Section (when loaded) -->
      <div v-if="displayContentLoaded && !localIsLoading && localContent" class="metadata-section text-xs text-text-secondary dark:text-text-secondary-dark border-t border-border dark:border-border-dark pt-2">
        <div v-if="localContent.metadata?.vertexCount || localContent.metadata?.fileSize" class="flex gap-4">
          <span v-if="localContent.metadata.vertexCount">
            <strong>{{ $t('glbContentCell.vertices') }}:</strong> {{ localContent.metadata.vertexCount.toLocaleString() }}
          </span>
          <span v-if="localContent.metadata.fileSize">
            <strong>{{ $t('glbContentCell.fileSize') }}:</strong> {{ formatFileSize(localContent.metadata.fileSize) }}
          </span>
          <span v-if="localContent.metadata.format">
            <strong>{{ $t('glbContentCell.format') }}:</strong> {{ localContent.metadata.format.toUpperCase() }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * @file GlbContentView.vue
 * @description View component for GLB Content Cell — displays 3D model, allows download, viewport controls.
 *
 * 4 States: loading, error, empty, loaded
 *
 * Buffer Local Pattern (REACTIVITY_ISOLATION.md):
 * - Layer 1 (Hydration): Read from props on mount/init
 * - Layer 2 (Buffer Local): local refs for UI state
 * - Layer 3 (Persistence): Sync via cell actions on explicit user action
 */
import { ref, computed, onMounted, onUnmounted, inject } from 'vue'
import { createLogger } from '@/utils/logger'
import { GlbContentCell } from './GlbContentCell'
import BabylonModelViewer from '@/components/viewers/BabylonModelViewer.vue'
import { CELL_STATE_BRIDGE_KEY } from '#canonical/shared/cellFactory'
import type { CellStateBridge } from '#canonical/shared/cellFactory'

const logger = createLogger('component:glb-content-viewer')

// ── Initialize GlbContentCell instance ──
const cellInstance = new GlbContentCell()

// ── Props ──
interface CellObject {
  id?: string
  cellId?: string
  initial_data?: {
    content_id?: string | null
    relative_url?: string | null
    [key: string]: any
  }
  data?: any
}

interface Props {
  cell?: CellObject
  content_id?: string
  relative_url?: string
}

const props = withDefaults(defineProps<Props>(), {
  cell: undefined,
  content_id: undefined,
  relative_url: undefined,
})

// ── View Bridge ──
const cellStateBridge = inject<CellStateBridge>(CELL_STATE_BRIDGE_KEY) ?? null

// ── Buffer Local (Layer 2): Local refs for UI state ──

// Loading state
const localIsLoading = ref(false)

// Error state
const localError = ref<string | null>(null)
const localRetryAvailable = ref(false)

// Content data (loaded from backend)
const localContent = ref<Record<string, any> | null>(null)
const localModelUrl = ref<string | null>(null)

// Viewport state (local toggles)
const localAutoRotate = ref(true)
const localWireframeMode = ref(false)
const localShowGrid = ref(true)

// ── Hydration (Layer 1): Read from props on init ──
const initialContentId = computed(() => {
  return props.content_id || props.cell?.initial_data?.content_id || null
})

const initialRelativeUrl = computed(() => {
  return props.relative_url || props.cell?.initial_data?.relative_url || null
})

// ── Display Computeds ──

/** Whether the cell has loaded content to display */
const displayContentLoaded = computed(() => {
  return localContent.value !== null || localModelUrl.value !== null
})

/** Whether the cell is in empty state (no content_id or relative_url) */
const displayIsEmpty = computed(() => {
  return !initialContentId.value && !initialRelativeUrl.value && !localIsLoading.value && !localError.value
})

/** The model URL to display in Babylon.js */
const displayModelUrl = computed(() => {
  if (localModelUrl.value) return localModelUrl.value
  return null
})

// ── Methods ──

/** Format file size for display */
const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** Load 3D content on mount */
const loadContent = async () => {
  const contentId = initialContentId.value
  const relativeUrl = initialRelativeUrl.value

  if (!contentId && !relativeUrl) {
    logger.debug('No content_id or relative_url provided — empty state')
    return
  }

  localIsLoading.value = true
  localError.value = null
  localRetryAvailable.value = false

  try {
    logger.info('Loading 3D content', { contentId, relativeUrl })

    const result = await cellInstance.execute({
      action: 'load',
      content_id: contentId,
      relative_url: relativeUrl,
    })

    if (result.success && result.output) {
      const output = result.output as any

      // Store model URL
      if (output.modelUrl) {
        localModelUrl.value = output.modelUrl
      }

      // Store content data
      if (output.content) {
        localContent.value = output.content
      }

      localError.value = null
      logger.info('3D content loaded successfully')
    } else {
      throw new Error(result.error || 'Failed to load 3D content')
    }
  } catch (error: any) {
    logger.error('Failed to load 3D content', { error: error.message })
    localError.value = error.message || 'Failed to load 3D model content'
    localContent.value = null
    localModelUrl.value = null
    localRetryAvailable.value = true
  } finally {
    localIsLoading.value = false
  }
}

/** Download 3D model via postMessage FILE_DOWNLOAD */
const handleDownload = async () => {
  if (!localModelUrl.value) {
    logger.warn('[DIAG-DOWNLOAD] handleDownload: localModelUrl is null, aborting download')
    localError.value = 'Model not loaded yet. Please wait for the 3D model to finish loading.'
    localRetryAvailable.value = true
    return
  }

  try {
    // DIAG: Log the modelUrl before delegating to cellInstance.execute
    logger.debug('[View.vue-DIAG] handleDownload: initiating download', {
      modelUrl: localModelUrl.value,
      windowOrigin: window.location.origin,
    })

    const result = await cellInstance.execute({
      action: 'download',
      modelUrl: localModelUrl.value,
    })
    logger.debug('[DIAG-DOWNLOAD] handleDownload: cellInstance.execute result', {
      success: result?.success,
      message: result?.output?.message,
    })

    // CHECK result.success — was previously silently ignored
    if (!result?.success) {
      const errorMsg = result?.output?.error || result?.output?.message || 'Download failed to initialize'
      logger.error('[DIAG-DOWNLOAD] handleDownload: execute returned failure', { error: errorMsg })
      localError.value = errorMsg
    }
  } catch (error: any) {
    logger.error('Download failed', { error: error.message })
    localError.value = error.message || 'Failed to download 3D model'
  }
}

// ── Lifecycle ──
onMounted(() => {
  logger.debug('GLB Content Cell mounted', {
    hasContentId: !!initialContentId.value,
    hasRelativeUrl: !!initialRelativeUrl.value,
  })

  // Register state provider for save/load persistence
  const cellId = props.cell?.cellId
  if (cellId && cellStateBridge) {
    cellStateBridge.registerStateProvider(cellId, () => {
      const ids: Record<string, any> = {}
      if (localModelUrl.value) {
        ids.model_url = localModelUrl.value
      }
      if (initialContentId.value) {
        ids.content_id = initialContentId.value
      }
      if (initialRelativeUrl.value) {
        ids.relative_url = initialRelativeUrl.value
      }
      return ids
    })
    logger.info('[View] Registered state provider with View Bridge', { cellId })
  }

  loadContent()
})

onUnmounted(() => {
  // Unregister from View Bridge
  const cellId = props.cell?.cellId
  if (cellId && cellStateBridge) {
    cellStateBridge.unregisterStateProvider(cellId)
    logger.info('[View] Unregistered state provider from View Bridge', { cellId })
  }

  logger.info('GLB Content Cell unmounted')
})
</script>

<style scoped>
.glb-content-viewer {
  font-family: 'Inter', sans-serif;
}

.model-viewer-container :deep(.babylon-viewer-container) {
  width: 100%;
  height: 100%;
}

.model-viewer-container :deep(.babylon-canvas) {
  width: 100%;
  height: 100%;
}
</style>
