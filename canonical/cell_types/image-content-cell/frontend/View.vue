/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-06-12",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": false,
 *   "i18n_validated_date": "2026-06-12",
 *   "i18n_coverage": 0,
 *   "i18n_status": "pending",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div class="image-content-cell bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg p-4 shadow-sm">
    <div class="cell-header mb-4">
      <h3 class="text-lg font-semibold text-primary dark:text-primary-light">
        {{ $t('imageContentCell.title') || 'Image Viewer' }}
      </h3>
      <p class="text-sm text-text-secondary dark:text-text-secondary-dark mt-1">
        {{ $t('imageContentCell.description') || 'View and edit persisted image content' }}
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
          {{ $t('imageContentCell.loading') || 'Loading image content...' }}
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
            <p class="font-medium">{{ $t('imageContentCell.errorTitle') || 'Failed to load content' }}</p>
            <p class="text-sm mt-1">{{ localError }}</p>
          </div>
        </div>
      </div>

      <!-- EMPTY STATE -->
      <div
        v-if="displayIsEmpty && !localIsLoading && !localError"
        class="empty-state flex flex-col items-center justify-center py-12 text-text-secondary dark:text-text-secondary-dark"
      >
        <svg class="h-16 w-16 mb-4 opacity-40" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        <p class="text-lg font-medium mb-1">
          {{ $t('imageContentCell.noContent') || 'No image content' }}
        </p>
        <p class="text-sm">
          {{ $t('imageContentCell.noContentDescription') || 'Provide a content_id or relative_url to display an image.' }}
        </p>
      </div>

      <!-- IMAGE DISPLAY (when loaded) -->
      <div v-if="displayContentLoaded && !localIsLoading" class="image-display-section">
        <div class="preview-container bg-white dark:bg-gray-800 border border-border dark:border-border-dark rounded p-4 flex items-center justify-center min-h-[250px]">
          <img
            v-if="displayImageUrl"
            :src="displayImageUrl"
            :alt="displayContentName || 'Image content'"
            class="max-w-full max-h-[400px] object-contain rounded"
            @error="handleImageError"
          />
          <p v-else class="text-text-secondary dark:text-text-secondary-dark text-sm">
            {{ $t('imageContentCell.imageNotAvailable') || 'Image not available' }}
          </p>
        </div>
      </div>

      <!-- CONTENT INFO & METADATA EDITING (when loaded) -->
      <div v-if="displayContentLoaded && !localIsLoading" class="metadata-section space-y-3">
        <h4 class="text-sm font-medium text-text-secondary dark:text-text-secondary-dark border-t border-border dark:border-border-dark pt-3">
          {{ $t('imageContentCell.metadata') || 'Metadata' }}
        </h4>

        <!-- Name field -->
        <div>
          <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-1">
            {{ $t('imageContentCell.nameLabel') || 'Name' }}
          </label>
          <input
            v-model="localFormData.name"
            type="text"
            class="w-full px-3 py-2 border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark rounded focus:outline-none focus:ring-2 focus:ring-primary"
            :placeholder="$t('imageContentCell.namePlaceholder') || 'Content name'"
          />
        </div>

        <!-- Tags field -->
        <div>
          <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-1">
            {{ $t('imageContentCell.tagsLabel') || 'Tags' }}
          </label>
          <input
            v-model="localFormData.tagsInput"
            type="text"
            class="w-full px-3 py-2 border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark rounded focus:outline-none focus:ring-2 focus:ring-primary"
            :placeholder="$t('imageContentCell.tagsPlaceholder') || 'tag1, tag2, tag3'"
          />
          <p class="text-xs text-text-secondary dark:text-text-secondary-dark mt-1">
            {{ $t('imageContentCell.tagsHint') || 'Comma-separated tags' }}
          </p>
        </div>

        <!-- Description field -->
        <div>
          <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-1">
            {{ $t('imageContentCell.descriptionLabel') || 'Description' }}
          </label>
          <textarea
            v-model="localFormData.description"
            rows="2"
            class="w-full px-3 py-2 border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark rounded focus:outline-none focus:ring-2 focus:ring-primary resize-none"
            :placeholder="$t('imageContentCell.descriptionPlaceholder') || 'Content description'"
          />
        </div>

        <!-- Save button + feedback -->
        <div class="flex items-center gap-3">
          <button
            :disabled="localIsSaving"
            class="px-4 py-2 bg-primary dark:bg-primary-hover text-white rounded hover:bg-primary-hover dark:hover:bg-primary-light transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            @click="handleSaveMetadata"
          >
            <svg
              v-if="localIsSaving"
              class="animate-spin h-4 w-4"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <span>{{ localIsSaving ? ($t('imageContentCell.saving') || 'Saving...') : ($t('imageContentCell.save') || 'Save') }}</span>
          </button>

          <span
            v-if="localSaveSuccess"
            class="text-sm text-success dark:text-green-400"
          >
            {{ $t('imageContentCell.saveSuccess') || 'Metadata saved!' }}
          </span>
          <span
            v-if="localSaveError"
            class="text-sm text-error dark:text-red-400"
          >
            {{ localSaveError }}
          </span>
        </div>
      </div>

      <!-- ACTION BUTTONS (when loaded) -->
      <div v-if="displayContentLoaded && !localIsLoading" class="actions-section flex gap-2 pt-2 border-t border-border dark:border-border-dark">
        <button
          class="px-3 py-1.5 text-sm bg-surface-light dark:bg-surface-dark-light border border-border dark:border-border-dark rounded hover:bg-surface-hover dark:hover:bg-surface-dark-hover transition flex items-center gap-1.5"
          :title="$t('imageContentCell.download') || 'Download image'"
          @click="handleDownload"
        >
          <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span>{{ $t('imageContentCell.download') || 'Download' }}</span>
        </button>
        <button
          class="px-3 py-1.5 text-sm bg-surface-light dark:bg-surface-dark-light border border-border dark:border-border-dark rounded hover:bg-surface-hover dark:hover:bg-surface-dark-hover transition flex items-center gap-1.5"
          :title="$t('imageContentCell.copy') || 'Copy to clipboard'"
          @click="handleCopy"
        >
          <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          <span>{{ $t('imageContentCell.copy') || 'Copy' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * @file ImageContentView.vue
 * @description View component for Image Content Cell — displays image, allows metadata editing, download, copy.
 *
 * Buffer Local Pattern (REACTIVITY_ISOLATION.md):
 * - Layer 1 (Hydration): Read from props on mount/init
 * - Layer 2 (Buffer Local): local refs for UI state
 * - Layer 3 (Persistence): Sync via cell actions on explicit user action
 */
import { ref, computed, onMounted } from 'vue'
import { createLogger } from '@/utils/logger'
import { ImageContentCell } from './ImageContentCell'

const logger = createLogger('component:image-content-cell')

// ── Initialize ImageContentCell instance ──
const cellInstance = new ImageContentCell()

// ── Props ──
interface CellObject {
  id?: string
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

// ── Buffer Local (Layer 2): Local refs for UI state ──

// Loading states
const localIsLoading = ref(false)
const localIsSaving = ref(false)

// Error states
const localError = ref<string | null>(null)
const localSaveError = ref<string | null>(null)
const localSaveSuccess = ref(false)

// Content data (loaded from backend)
const localContent = ref<Record<string, any> | null>(null)
const localImageUrl = ref<string | null>(null)

// Form data (Buffer Local for user interaction)
const localFormData = ref({
  name: '',
  tagsInput: '',
  description: '',
})

// ── Hydration (Layer 1): Read from props on init ──
const initialContentId = computed(() => {
  return props.content_id || props.cell?.initial_data?.content_id || null
})

const initialRelativeUrl = computed(() => {
  return props.relative_url || props.cell?.initial_data?.relative_url || null
})

// ── Display Computeds (simple, direct) ──

/** Whether the cell has loaded content to display */
const displayContentLoaded = computed(() => {
  return localContent.value !== null || localImageUrl.value !== null
})

/** Whether the cell is in empty state (no content_id or relative_url) */
const displayIsEmpty = computed(() => {
  return !initialContentId.value && !initialRelativeUrl.value && !localIsLoading.value && !localError.value
})

/** The image URL to display */
const displayImageUrl = computed(() => {
  // Priority 1: URL from load action
  if (localImageUrl.value) return localImageUrl.value
  return null
})

/** The content name to display */
const displayContentName = computed(() => {
  if (localFormData.value.name) return localFormData.value.name
  return localContent.value?.fragments?.name || localContent.value?.filename || ''
})

// ── Methods ──

/** Load content on mount */
const loadContent = async () => {
  const contentId = initialContentId.value
  const relativeUrl = initialRelativeUrl.value

  if (!contentId && !relativeUrl) {
    logger.debug('No content_id or relative_url provided — empty state')
    return
  }

  localIsLoading.value = true
  localError.value = null

  try {
    logger.info('Loading content', { contentId, relativeUrl })

    const result = await cellInstance.execute({
      action: 'load',
      content_id: contentId,
      relative_url: relativeUrl,
    })

    if (result.success && result.output) {
      const output = result.output as any

      // Store image URL
      if (output.imageUrl) {
        localImageUrl.value = output.imageUrl
      }

      // Store content data
      if (output.content) {
        localContent.value = output.content

        // Hydrate form from loaded content
        const tags = output.content.tags || []
        const metadata = output.content.metadata || {}

        localFormData.value = {
          name: output.content.fragments?.name || output.content.filename || '',
          tagsInput: Array.isArray(tags) ? tags.join(', ') : '',
          description: metadata.description || '',
        }
      }

      localError.value = null
      logger.info('Content loaded successfully')
    } else {
      throw new Error(result.error || 'Failed to load content')
    }
  } catch (error: any) {
    logger.error('Failed to load content', { error: error.message })
    localError.value = error.message || 'Failed to load image content'
    localContent.value = null
    localImageUrl.value = null
  } finally {
    localIsLoading.value = false
  }
}

/** Handle image load error (broken URL) */
const handleImageError = () => {
  logger.warn('Image failed to load', { imageUrl: localImageUrl.value })
  localError.value = 'Failed to load image — the URL may be invalid or the file may have been deleted.'
  localImageUrl.value = null
}

/** Save metadata via PATCH /api/contents/{id} */
const handleSaveMetadata = async () => {
  const contentId = initialContentId.value
  if (!contentId) {
    logger.warn('Save attempted without content_id — aborting')
    localSaveError.value = 'No content ID available for saving'
    return
  }

  logger.debug(
    '[DIAG] handleSaveMetadata — contentId=%s (origin: props.content_id=%s, cell.initial_data.content_id=%s, relative_url=%s)',
    contentId,
    props.content_id,
    props.cell?.initial_data?.content_id,
    initialRelativeUrl.value,
  )
  localIsSaving.value = true
  localSaveError.value = null
  localSaveSuccess.value = false

  try {
    // Parse tags from comma-separated input
    const tags = localFormData.value.tagsInput
      .split(',')
      .map(t => t.trim())
      .filter(t => t.length > 0)

    // Build metadata from form fields
    const metadata: Record<string, any> = {}
    if (localFormData.value.description) {
      metadata.description = localFormData.value.description
    }

    const result = await cellInstance.execute({
      action: 'update-metadata',
      content_id: contentId,
      tags,
      metadata,
      name: localFormData.value.name || undefined,
    })

    if (result.success) {
      localSaveSuccess.value = true
      logger.info('Metadata saved successfully', { contentId })

      // Clear success message after 3 seconds
      setTimeout(() => {
        localSaveSuccess.value = false
      }, 3000)
    } else {
      throw new Error(result.error || 'Failed to save metadata')
    }
  } catch (error: any) {
    logger.error('Failed to save metadata', { error: error.message })
    localSaveError.value = error.message || 'Failed to save metadata'

    // Clear error after 5 seconds
    setTimeout(() => {
      localSaveError.value = null
    }, 5000)
  } finally {
    localIsSaving.value = false
  }
}

/** Download image via postMessage FILE_DOWNLOAD */
const handleDownload = async () => {
  if (!localImageUrl.value) return

  try {
    await cellInstance.execute({
      action: 'download',
      imageUrl: localImageUrl.value,
    })
  } catch (error: any) {
    logger.error('Download failed', { error: error.message })
    localError.value = error.message || 'Failed to download image'
  }
}

/** Copy image to clipboard */
const handleCopy = async () => {
  if (!localImageUrl.value) return

  try {
    await cellInstance.execute({
      action: 'copy',
      imageUrl: localImageUrl.value,
    })
  } catch (error: any) {
    logger.error('Copy to clipboard failed', { error: error.message })
    localError.value = error.message || 'Failed to copy image to clipboard'
  }
}

// ── Lifecycle ──
onMounted(() => {
  logger.debug('Image Content Cell mounted', {
    hasContentId: !!initialContentId.value,
    hasRelativeUrl: !!initialRelativeUrl.value,
  })

  loadContent()
})
</script>

<style scoped>
.image-content-cell {
  /* Component-specific styles if needed */
}
</style>
