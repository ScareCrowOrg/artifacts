<template>
  <div class="artifacts-manager-view flex flex-col h-full bg-white dark:bg-gray-900 p-4">
    <!-- Empty State -->
    <div v-if="!localArtifactId" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <span class="text-4xl mb-2 block">{{ $t('artifactsManager.noData') }}</span>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          {{ $t('artifactsManager.noDataDescription') }}
        </p>
      </div>
    </div>

    <template v-else>
      <!-- Header -->
      <div class="flex items-center gap-3 mb-4">
        <span class="text-3xl">{{ artifactIcon }}</span>
        <div>
          <h2 class="text-lg font-bold text-gray-900 dark:text-white">{{ artifactName }}</h2>
          <p class="text-xs text-gray-500 dark:text-gray-400">
            {{ $t('artifactsManager.version') }}: v{{ artifactVersion }}
          </p>
        </div>
      </div>

      <!-- Description -->
      <div v-if="artifactDescription" class="mb-4">
        <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">
          {{ $t('artifactsManager.description') }}
        </h3>
        <p class="text-sm text-gray-600 dark:text-gray-400">{{ artifactDescription }}</p>
      </div>

      <!-- Metadata JSON -->
      <div class="mb-4">
        <h3
          class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1 cursor-pointer flex items-center gap-1"
          @click="metadataExpanded = !metadataExpanded"
        >
          <span>{{ metadataExpanded ? '▼' : '▶' }}</span>
          {{ $t('artifactsManager.metadata') }}
          <span class="text-xs text-gray-400 font-normal">({{ $t('artifactsManager.clickToToggle') }})</span>
        </h3>
        <pre
          v-if="metadataExpanded"
          class="bg-gray-100 dark:bg-gray-800 p-3 rounded-lg text-xs overflow-auto max-h-64 border border-gray-200 dark:border-gray-700"
        >{{ formattedMetadata }}</pre>
      </div>

      <!-- Allow Button -->
      <div class="mt-auto pt-4 border-t border-gray-200 dark:border-gray-700">
        <button
          class="inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          :disabled="isAllowing"
          @click="handleAllow"
        >
          <span v-if="isAllowing">⏳ {{ $t('artifactsManager.saving') }}</span>
          <span v-else>{{ $t('artifactsManager.allow') }}</span>
        </button>

        <!-- Feedback -->
        <p
          v-if="feedback"
          class="mt-2 text-xs font-medium"
          :class="{
            'text-emerald-600 dark:text-emerald-400': feedbackType === 'success',
            'text-red-600 dark:text-red-400': feedbackType === 'error',
            'text-gray-500 dark:text-gray-400': feedbackType === 'info',
          }"
        >
          {{ feedback }}
        </p>
      </div>
    </template>
  </div>

  <!-- UserSelectionCell overlay (Teleport to body for modal) -->
  <UserSelectionView />
</template>

<script setup lang="ts">
/**
 * @file View.vue
 * @description artifacts-manager-cell — displays artifact metadata and provides Allow action.
 *
 * Buffer Local Pattern (REACTIVITY_ISOLATION.md):
 * All reactive state is initialized from props at mount time (hydration phase)
 * and stored in local refs. No cascading computed chain on dynamic props.
 *
 * Props:
 *  - cellInstance: ArtifactsManagerCell instance (from resolveViewSpec)
 *  - cell: { cellTypeName, cellType, initialData } (from resolveViewSpec)
 */

import { ref, computed, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { createLogger } from '@/utils/logger'
import UserSelectionView from '#canonical/cell_types/user-selection-cell/frontend/View.vue'
import type { ArtifactsManagerCell } from './ArtifactsManagerCell'

const log = createLogger('cell:artifacts-manager:view')
const { t } = useI18n()

// ── Props ──────────────────────────────────────────────────────────────────────
const props = defineProps<{
  cellInstance?: ArtifactsManagerCell
  cell?: {
    cellId?: string
    cellTypeName?: string
    cellType?: any
    initial_data?: {
      artifact_id?: string
      artifact_name?: string
      artifact_description?: string
      artifact_icon?: string
      artifact_type?: string
      metadata?: Record<string, any>
      stage?: string
      version?: string
      identity?: Record<string, any>
      runtime?: Record<string, any>
      execution_model?: Record<string, any>
    }
  }
}>()

// ── Buffer Local Pattern: Hydrate props into local refs ───────────────────────
// REACTIVITY_ISOLATION.md: all relevant props are captured once at mount time
// into local refs, preventing reactivity shadowing from dynamic prop changes.

const initialData = props.cell?.initial_data ?? {}

/** Local artifact ID — empty means no data (empty state). */
const localArtifactId = ref<string>(initialData.artifact_id || '')

/** Artifact display fields captured from initial_data. */
const artifactIcon = ref<string>(
  initialData.artifact_icon
  || (initialData.identity as any)?.icon
  || '⚙️',
)
const artifactName = ref<string>(
  initialData.artifact_name
  || (initialData.identity as any)?.name
  || 'Unknown Artifact',
)
const artifactVersion = ref<string>(
  initialData.version || (initialData as any).artifact_version || '0.0.0',
)
const artifactDescription = ref<string>(
  initialData.artifact_description
  || (initialData.identity as any)?.description
  || '',
)

/** Raw artifact data for JSON display. Captured from initial_data. */
const artifactData = ref<Record<string, any>>(
  initialData.metadata
  || (initialData as any).artifact_data?.metadata
  || {},
)

// ── UI State ───────────────────────────────────────────────────────────────────
const isAllowing = ref(false)
const feedback = ref<string | null>(null)
const feedbackType = ref<'success' | 'error' | 'info'>('info')
const metadataExpanded = ref(true)

let feedbackTimeout: ReturnType<typeof setTimeout> | null = null

// ── Computed ───────────────────────────────────────────────────────────────────
const formattedMetadata = computed(() => {
  const data = artifactData.value
  if (!data || Object.keys(data).length === 0) {
    return '{}'
  }
  return JSON.stringify(data, null, 2)
})

// ── Handlers ───────────────────────────────────────────────────────────────────

/**
 * Handle Allow button click.
 * Calls cellInstance.allowArtifact() if available.
 * Shows feedback on success/error/cancel.
 */
async function handleAllow(): Promise<void> {
  if (!localArtifactId.value) {
    log.warn('[ArtifactsManagerView] No artifact_id available for allowance')
    return
  }

  const cell = props.cellInstance
  if (!cell || typeof cell.allowArtifact !== 'function') {
    log.warn('[ArtifactsManagerView] cellInstance does not support allowArtifact()')
    feedback.value = t('artifactsManager.allowUnavailable')
    feedbackType.value = 'error'
    scheduleFeedbackClear()
    return
  }

  isAllowing.value = true
  try {
    const user = await cell.allowArtifact(localArtifactId.value)
    if (user) {
      feedback.value = t('artifactsManager.allowSuccess', { name: user.name })
      feedbackType.value = 'success'
      log.info('[ArtifactsManagerView] Allowance granted', {
        artifactId: localArtifactId.value,
        name: user.name,
      })
    } else {
      feedback.value = t('artifactsManager.allowCancelled')
      feedbackType.value = 'info'
      log.debug('[ArtifactsManagerView] Allowance cancelled', {
        artifactId: localArtifactId.value,
      })
    }
  } catch (error) {
    feedback.value = t('artifactsManager.allowFailed')
    feedbackType.value = 'error'
    log.error('[ArtifactsManagerView] Allowance error', {
      artifactId: localArtifactId.value,
      error: error instanceof Error ? error.message : String(error),
    })
  } finally {
    isAllowing.value = false
  }

  scheduleFeedbackClear()
}

function scheduleFeedbackClear(): void {
  if (feedbackTimeout !== null) {
    clearTimeout(feedbackTimeout)
  }
  feedbackTimeout = setTimeout(() => {
    feedback.value = null
    feedbackTimeout = null
  }, 3000)
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────
onBeforeUnmount(() => {
  if (feedbackTimeout !== null) {
    clearTimeout(feedbackTimeout)
    feedbackTimeout = null
  }
})
</script>

<style scoped>
pre {
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  line-height: 1.5;
}
</style>
