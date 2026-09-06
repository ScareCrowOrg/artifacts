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

      <!-- Promotion feedback (kept OUTSIDE the stage condition so it survives the
           sandbox → runtime reactive transition and is not unmounted mid-flush) -->
      <p
        v-if="promotionFeedback"
        class="mb-3 text-xs font-medium"
        :class="{
          'text-emerald-600 dark:text-emerald-400': promotionFeedbackType === 'success',
          'text-red-600 dark:text-red-400': promotionFeedbackType === 'error',
          'text-gray-500 dark:text-gray-400': promotionFeedbackType === 'info',
        }"
      >
        {{ promotionFeedback }}
      </p>

      <!-- Dependencies (sandbox: declared graph + dry-run preview; runtime: read-only) -->
      <div class="mb-4">
        <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
          {{ $t('artifactsManager.dependencies') }}
        </h3>

        <p v-if="declaredDependencyCount === 0" class="text-sm text-gray-500 dark:text-gray-400">
          {{ $t('artifactsManager.noDependencies') }}
        </p>
        <ul v-else class="space-y-0.5 text-xs text-gray-600 dark:text-gray-400">
          <li v-for="(deps, key) in runtimeDependencies" :key="key">
            <span class="font-mono">{{ key }}:</span> {{ deps.join(', ') }}
          </li>
        </ul>
      </div>

      <!-- Promote section (owner-only, sandbox → runtime/user/{owner}) -->
      <div v-if="currentStage === 'sandbox'" class="mb-4">
        <!-- Preview resolved deps via /bundle dry_run -->
        <div class="mb-3">
          <label class="inline-flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
            <input
              type="checkbox"
              :checked="isPreviewOn"
              @change="togglePreview"
              class="h-3 w-3 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
            />
            {{ $t('artifactsManager.dependencyPreview') }}
          </label>
          <div v-if="isLoadingPreview" class="mt-1 text-xs text-gray-500 dark:text-gray-400">
            {{ $t('artifactsManager.previewLoading') }}
          </div>
          <ul v-else-if="previewDependencies.length" class="mt-1 space-y-0.5 text-xs text-gray-600 dark:text-gray-400">
            <li v-for="(dep, i) in previewDependencies" :key="i" class="font-mono">
              {{ dep.artifact_type }}:{{ dep.slug }}
            </li>
          </ul>
          <p v-else-if="previewError" class="mt-1 text-xs text-red-500 dark:text-red-400">{{ previewError }}</p>
        </div>

        <button
          class="inline-flex items-center gap-1.5 px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          :disabled="isPromoting"
          @click="handlePromote"
        >
          <span v-if="isPromoting">⏳ {{ $t('artifactsManager.promoting') }}</span>
          <span v-else>🚀 {{ $t('artifactsManager.promote') }}</span>
        </button>
      </div>

      <!-- Allowance section (runtime only — available only after promotion) -->
      <template v-else-if="currentStage === 'runtime'">
        <!-- Allowed Users -->
        <div class="mb-4">
          <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
            {{ $t('artifactsManager.allowedUsers') }}
          </h3>

          <!-- Loading -->
          <div v-if="isLoadingAllowances" class="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
            <span>⏳</span>
            <span>{{ $t('artifactsManager.loading') }}</span>
          </div>

          <!-- Error -->
          <div v-else-if="allowanceError" class="text-sm text-red-500 dark:text-red-400">
            {{ allowanceError }}
          </div>

          <!-- Empty -->
          <div v-else-if="allowanceUsers.length === 0" class="text-sm text-gray-500 dark:text-gray-400">
            {{ $t('artifactsManager.noAllowedUsers') }}
          </div>

          <!-- List -->
          <ul v-else class="space-y-1">
            <li
              v-for="entry in allowanceUsers"
              :key="entry.user_id"
              class="flex items-center justify-between py-1.5 px-2 bg-gray-50 dark:bg-gray-800 rounded"
            >
              <div class="flex items-center gap-2 min-w-0">
                <span v-if="entry.avatar_url" class="w-5 h-5 rounded-full flex-shrink-0 bg-cover" :style="{ backgroundImage: `url(${entry.avatar_url})` }"></span>
                <span v-else class="w-5 h-5 rounded-full flex-shrink-0 bg-emerald-100 dark:bg-emerald-900 flex items-center justify-center text-xs font-medium text-emerald-700 dark:text-emerald-300">
                  {{ (entry.name || entry.user_id).charAt(0).toUpperCase() }}
                </span>
                <span class="text-sm text-gray-700 dark:text-gray-300 truncate">{{ entry.name || entry.user_id }}</span>
              </div>
              <button
                class="flex-shrink-0 w-6 h-6 flex items-center justify-center text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/30 rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                :disabled="removingUsers.has(entry.user_id)"
                :title="$t('artifactsManager.removeAllowance')"
                @click="handleRemoveAllowance(entry.user_id)"
              >−</button>
            </li>
          </ul>
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

      <!-- Canonical: read-only (no promote, no allow) -->
      <div v-else class="text-sm text-gray-500 dark:text-gray-400">
        {{ $t('artifactsManager.canonicalReadOnly') }}
      </div>
    </template>
  </div>

  <!-- UserSelectionCell overlay (Teleport to body for modal) -->
  <UserSelectionView />

  <!-- Confirmation dialog for removing allowance -->
  <Teleport to="body">
    <div
      v-if="showRemoveConfirm"
      class="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
    >
      <!-- Backdrop -->
      <div class="absolute inset-0 bg-black/60" @click="cancelRemoveAllowance" />
      <!-- Modal -->
      <div class="relative z-10 w-full max-w-sm mx-4 bg-white dark:bg-gray-800 rounded-xl shadow-2xl p-6">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-2">
          {{ $t('artifactsManager.confirmRemoveTitle') }}
        </h3>
        <p class="text-sm text-gray-600 dark:text-gray-400 mb-6">
          {{ $t('artifactsManager.confirmRemoveMessage', { name: pendingRemoveUserName }) }}
        </p>
        <div class="flex justify-end gap-3">
          <button
            class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
            @click="cancelRemoveAllowance"
          >
            {{ $t('artifactsManager.cancel') }}
          </button>
          <button
            class="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            :disabled="removingUsers.has(pendingRemoveUserId)"
            @click="confirmRemoveAllowance"
          >
            <span v-if="removingUsers.has(pendingRemoveUserId)">⏳ {{ $t('artifactsManager.saving') }}</span>
            <span v-else>{{ $t('artifactsManager.confirmRemoveConfirm') }}</span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
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

import { ref, computed, onBeforeUnmount, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { createLogger } from '@/utils/logger'
import UserSelectionView from '#canonical/cell_types/user-selection-cell/frontend/View.vue'
import { useArtifactsExplorerStore } from '#canonical/cell_types/artifacts-explorer-cell/frontend/store'
import type {
  ArtifactsManagerCell,
  AllowanceEntry,
  DependencyPreview,
  PromoteError,
} from './ArtifactsManagerCell'

const log = createLogger('cell:artifacts-manager:view')
const { t } = useI18n()

// Explorer store — used to sync the artifact's stage to 'runtime' after a
// successful promotion (prevents a stale sandbox view → 409 on re-promote).
const explorerStore = useArtifactsExplorerStore()

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

// ── Artifact Promotion (sandbox → runtime/user/{owner}) ───────────────────────
const artifactType = ref<string>(initialData.artifact_type || (initialData as any).artifact_type || '')
const slug = ref<string>(initialData.artifact_id || (initialData as any).artifact_id || '')

/**
 * Local lifecycle stage buffer (Buffer Local Pattern). Hydrated from props at
 * mount; updated to 'runtime' reactively AFTER a successful promotion so the
 * Promote button disappears and the Allowance section appears without
 * closing/reopening the cell.
 */
const currentStage = ref<string>(initialData.stage || '')

/** Declared dependency graph from initial_data.runtime.dependencies. */
const runtimeDependencies = ref<Record<string, string[]>>(
  (initialData.runtime as any)?.dependencies || {},
)

/** Count of non-empty declared dependency groups. */
const declaredDependencyCount = computed<number>(
  () => Object.values(runtimeDependencies.value).filter(deps => Array.isArray(deps) && deps.length > 0).length,
)

/** Resolved (transitive) dependencies from /bundle dry_run preview. */
const previewDependencies = ref<DependencyPreview[]>([])
const isPreviewOn = ref(false)
const isLoadingPreview = ref(false)
const previewError = ref<string | null>(null)

const isPromoting = ref(false)
const promotionFeedback = ref<string | null>(null)
const promotionFeedbackType = ref<'success' | 'error' | 'info'>('info')

// ── UI State ───────────────────────────────────────────────────────────────────
const isAllowing = ref(false)
const feedback = ref<string | null>(null)
const feedbackType = ref<'success' | 'error' | 'info'>('info')
const metadataExpanded = ref(true)

// ── Allowance List State (Buffer Local Pattern) ──────────────────────────────
const allowanceUsers = ref<AllowanceEntry[]>([])
const isLoadingAllowances = ref(false)
const allowanceError = ref<string | null>(null)
const removingUsers = ref<Set<string>>(new Set())

// ── Confirmation Dialog State ────────────────────────────────────────────────
const showRemoveConfirm = ref(false)
const pendingRemoveUserId = ref<string>('')
const pendingRemoveUserName = ref<string>('')

let feedbackTimeout: ReturnType<typeof setTimeout> | null = null
let promotionFeedbackTimeout: ReturnType<typeof setTimeout> | null = null

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
      // Reload allowances list to include the newly granted user
      await loadAllowances()
    } else {
      feedback.value = t('artifactsManager.allowCancelled')
      feedbackType.value = 'info'
      log.debug('[ArtifactsManagerView] Allowance cancelled', {
        artifactId: localArtifactId.value,
      })
    }
  } catch (error) {
    const errMsg = error instanceof Error ? error.message : String(error)
    // F3: surface the real backend error (e.g. "Planet not found") instead of a
    // generic i18n string, so a failed grant is never presented as success.
    feedback.value = errMsg
      ? `${t('artifactsManager.allowFailed')} — ${errMsg}`
      : t('artifactsManager.allowFailed')
    feedbackType.value = 'error'
    log.error('[ArtifactsManagerView] Allowance error', {
      artifactId: localArtifactId.value,
      error: errMsg,
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

// ── Promotion Handlers ────────────────────────────────────────────────────────

/** Map a PromoteError code to a friendly i18n message (403/409/422/unsupported). */
function mapPromoteError(error: unknown): string {
  const err = error as PromoteError
  if (err?.code) {
    switch (err.code) {
      case 'promoteForbidden':
        return t('artifactsManager.promoteForbidden')
      case 'promoteConflict':
        return t('artifactsManager.promoteConflict')
      case 'promoteInvalid':
        return t('artifactsManager.promoteInvalid')
      case 'promoteUnsupportedType':
        return t('artifactsManager.promoteUnsupportedType')
      default:
        return t('artifactsManager.promoteFailed')
    }
  }
  return t('artifactsManager.promoteFailed')
}

function schedulePromotionFeedbackClear(): void {
  if (promotionFeedbackTimeout !== null) {
    clearTimeout(promotionFeedbackTimeout)
  }
  promotionFeedbackTimeout = setTimeout(() => {
    promotionFeedback.value = null
    promotionFeedbackTimeout = null
  }, 3000)
}

/**
 * Handle the "🚀 Promover" button. Bundles the artifact + transitive deps
 * from sandbox and promotes to the owner's runtime. On success, sets the local
 * stage to 'runtime' reactively (Promote hides, Allowance appears).
 */
async function handlePromote(): Promise<void> {
  if (!slug.value || !artifactType.value) {
    promotionFeedback.value = t('artifactsManager.promoteInvalid')
    promotionFeedbackType.value = 'error'
    schedulePromotionFeedbackClear()
    return
  }

  const cell = props.cellInstance
  if (!cell || typeof cell.promoteArtifact !== 'function') {
    log.warn('[ArtifactsManagerView] cellInstance does not support promoteArtifact()')
    promotionFeedback.value = t('artifactsManager.promoteFailed')
    promotionFeedbackType.value = 'error'
    schedulePromotionFeedbackClear()
    return
  }

  isPromoting.value = true
  promotionFeedback.value = null
  try {
    const summary = await cell.promoteArtifact(artifactType.value, slug.value)
    promotionFeedback.value = t('artifactsManager.promoteSuccess', { count: summary.promotedCount })
    promotionFeedbackType.value = 'success'
    // ⚡ Reactive transition: sandbox → runtime without reopening the cell.
    currentStage.value = 'runtime'
    if (typeof cell.setStage === 'function') {
      cell.setStage('runtime')
    }
    // Sync the artifact's stage in the explorer catalog so a reopen of the
    // manager cell shows the runtime Allowance section (not a stale sandbox
    // Promote that would 409 on a repeat promotion).
    explorerStore.markArtifactPromoted(slug.value)
    log.info('[ArtifactsManagerView] Promotion succeeded', {
      bundleId: summary.bundleId,
      count: summary.promotedCount,
    })
    await loadAllowances()
  } catch (error) {
    promotionFeedback.value = mapPromoteError(error)
    promotionFeedbackType.value = 'error'
    log.error('[ArtifactsManagerView] Promotion failed', {
      artifactId: slug.value,
      error: error instanceof Error ? error.message : String(error),
    })
  } finally {
    isPromoting.value = false
  }
  schedulePromotionFeedbackClear()
}

/** Toggle the dry-run dependency preview checkbox. */
async function togglePreview(): Promise<void> {
  isPreviewOn.value = !isPreviewOn.value
  if (isPreviewOn.value) {
    await loadDependenciesPreview()
  } else {
    // Clear the preview when the checkbox is turned off.
    previewDependencies.value = []
    previewError.value = null
  }
}

/** Load resolved (transitive) deps via /bundle dry_run:true. */
async function loadDependenciesPreview(): Promise<void> {
  if (!slug.value || !artifactType.value) return
  if (!isPreviewOn.value) return
  // In-flight guard: ignore a duplicate trigger while a dry-run is running.
  if (isLoadingPreview.value) return

  const cell = props.cellInstance
  if (!cell || typeof cell.previewDependencies !== 'function') {
    log.warn('[ArtifactsManagerView] cellInstance does not support previewDependencies()')
    previewError.value = t('artifactsManager.previewFailed')
    return
  }

  isLoadingPreview.value = true
  previewError.value = null
  try {
    previewDependencies.value = await cell.previewDependencies(artifactType.value, slug.value)
  } catch (error) {
    previewError.value = (error as PromoteError)?.code
      ? mapPromoteError(error as PromoteError)
      : t('artifactsManager.previewFailed')
  } finally {
    isLoadingPreview.value = false
  }
}

// ── Allowance Handlers ────────────────────────────────────────────────────────

/**
 * Load the list of users with allowance for the current artifact.
 * Called on mount and after successful allowance grants.
 */
async function loadAllowances(): Promise<void> {
  if (!localArtifactId.value) return

  const cell = props.cellInstance
  if (!cell || typeof cell.listAllowances !== 'function') {
    log.warn('[ArtifactsManagerView] cellInstance does not support listAllowances()')
    return
  }

  isLoadingAllowances.value = true
  allowanceError.value = null
  try {
    allowanceUsers.value = await cell.listAllowances(localArtifactId.value)
    log.info('[ArtifactsManagerView] Allowances loaded', {
      artifactId: localArtifactId.value,
      count: allowanceUsers.value.length,
    })
  } catch (error) {
    allowanceError.value = t('artifactsManager.allowanceLoadFailed')
    log.error('[ArtifactsManagerView] Failed to load allowances', {
      artifactId: localArtifactId.value,
      error: error instanceof Error ? error.message : String(error),
    })
  } finally {
    isLoadingAllowances.value = false
  }
}

/**
 * Handle remove (minus) button click.
 * Opens confirmation dialog before executing the removal.
 */
function handleRemoveAllowance(userId: string): void {
  if (!localArtifactId.value) return

  const cell = props.cellInstance
  if (!cell || typeof cell.removeAllowance !== 'function') {
    log.warn('[ArtifactsManagerView] cellInstance does not support removeAllowance()')
    return
  }

  // Find the user name for display in the confirmation dialog
  const entry = allowanceUsers.value.find(u => u.user_id === userId)
  pendingRemoveUserName.value = entry?.name || userId
  pendingRemoveUserId.value = userId
  showRemoveConfirm.value = true
}

/**
 * Cancel the remove operation — closes the confirmation dialog.
 */
function cancelRemoveAllowance(): void {
  showRemoveConfirm.value = false
  pendingRemoveUserId.value = ''
  pendingRemoveUserName.value = ''
}

/**
 * Confirmed remove — executes the allowance removal.
 */
async function confirmRemoveAllowance(): Promise<void> {
  if (!localArtifactId.value || !pendingRemoveUserId.value) return

  const cell = props.cellInstance
  if (!cell || typeof cell.removeAllowance !== 'function') {
    log.warn('[ArtifactsManagerView] cellInstance does not support removeAllowance()')
    return
  }

  const userId = pendingRemoveUserId.value
  showRemoveConfirm.value = false

  removingUsers.value = new Set([...removingUsers.value, userId])
  try {
    await cell.removeAllowance(localArtifactId.value, userId)
    // Remove from local list immediately on success
    allowanceUsers.value = allowanceUsers.value.filter(u => u.user_id !== userId)
    feedback.value = t('artifactsManager.allowanceRemoved')
    feedbackType.value = 'success'
    log.info('[ArtifactsManagerView] Allowance removed', {
      artifactId: localArtifactId.value,
      userId,
    })
  } catch (error) {
    feedback.value = t('artifactsManager.allowanceRemoveFailed')
    feedbackType.value = 'error'
    log.error('[ArtifactsManagerView] Failed to remove allowance', {
      artifactId: localArtifactId.value,
      userId,
      error: error instanceof Error ? error.message : String(error),
    })
  } finally {
    const next = new Set(removingUsers.value)
    next.delete(userId)
    removingUsers.value = next
  }

  scheduleFeedbackClear()
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────
onMounted(async () => {
  if (!localArtifactId.value) return

  // Sync the cell's defensive allowance gate with our hydrated stage.
  const cell = props.cellInstance
  if (cell && typeof cell.setStage === 'function') {
    cell.setStage(currentStage.value)
  }

  // Allowance only exists for promoted (runtime) artifacts.
  if (currentStage.value === 'runtime') {
    await loadAllowances()
  }
})
onBeforeUnmount(() => {
  if (feedbackTimeout !== null) {
    clearTimeout(feedbackTimeout)
    feedbackTimeout = null
  }
  if (promotionFeedbackTimeout !== null) {
    clearTimeout(promotionFeedbackTimeout)
    promotionFeedbackTimeout = null
  }
})
</script>

<style scoped>
pre {
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  line-height: 1.5;
}
</style>
