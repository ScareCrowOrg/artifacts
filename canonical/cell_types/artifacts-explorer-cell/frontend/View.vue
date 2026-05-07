/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-05-07",
 *   "dark_mode_support": "full",
 *   "i18n_validated": false,
 *   "logger_namespace": "cell:artifacts-explorer:view",
 *   "validation_status": "phase2"
 * }
 */
<template>
  <div class="artifacts-explorer-view flex flex-col h-full bg-white dark:bg-gray-900">
    <!-- Header -->
    <div class="explorer-header px-4 py-3 border-b border-gray-200 dark:border-gray-700">
      <h2 class="text-lg font-bold text-gray-900 dark:text-white">
        🔍 Artifacts Explorer
      </h2>
      <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
        Browse and add artifacts to your workspace.
      </p>
    </div>

    <!-- Category Filter Tabs (only when filter_mode !== 'cells_only') -->
    <div
      v-if="filterMode !== 'cells_only'"
      class="flex gap-1 px-4 pt-3 pb-1 overflow-x-auto"
      role="tablist"
      aria-label="Filter artifacts by category"
    >
      <button
        v-for="tab in categoryTabs"
        :key="tab.key"
        role="tab"
        :aria-selected="activeCategory === tab.key"
        class="category-tab flex-shrink-0 px-3 py-1 rounded-full text-xs font-medium transition-colors"
        :class="
          activeCategory === tab.key
            ? 'bg-blue-600 text-white'
            : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
        "
        @click="activeCategory = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Search -->
    <div class="px-4 pt-2 pb-2">
      <input
        v-model="searchQuery"
        type="text"
        class="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm"
        placeholder="Search by name, description…"
        aria-label="Search artifacts"
      />
    </div>

    <!-- Loading State -->
    <div v-if="explorerStore.isLoading" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <div class="spinner mb-2"></div>
        <p class="text-sm text-gray-500 dark:text-gray-400">Loading artifacts…</p>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="explorerStore.error" class="flex-1 flex items-center justify-center px-4">
      <div class="text-center">
        <span class="text-4xl mb-2 block">⚠️</span>
        <p class="text-red-500 font-semibold mb-1">Failed to load artifacts</p>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">{{ explorerStore.error }}</p>
        <button
          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
          @click="loadArtifacts()"
        >
          Retry
        </button>
      </div>
    </div>

    <!-- Artifacts Grid -->
    <div v-else class="flex-1 overflow-auto px-4 pb-4">
      <!-- No results -->
      <div v-if="filteredArtifacts.length === 0" class="text-center py-8">
        <span class="text-3xl mb-2 block">🔍</span>
        <p class="text-gray-500 dark:text-gray-400 text-sm">
          No artifacts found<template v-if="searchQuery"> for "{{ searchQuery }}"</template>.
        </p>
      </div>

      <!-- Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
        <div
          v-for="artifact in filteredArtifacts"
          :key="artifact.artifact_id"
          class="artifact-card bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 transition-all"
          :class="
            artifact.execution_model.orchestrator === 'frontend'
              ? 'hover:shadow-md hover:border-blue-500 cursor-pointer'
              : 'opacity-80'
          "
        >
          <div class="flex items-start gap-3">
            <!-- Icon -->
            <span class="text-2xl flex-shrink-0">{{ getIcon(artifact) }}</span>

            <!-- Content -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-1.5 flex-wrap">
                <h3 class="font-semibold text-gray-900 dark:text-white text-sm truncate">
                  {{ artifact.identity.name }}
                </h3>
                <!-- Sandbox badge -->
                <span
                  v-if="artifact.stage === 'sandbox'"
                  class="text-xs px-1.5 py-0.5 bg-yellow-100 dark:bg-yellow-900 text-yellow-700 dark:text-yellow-300 rounded"
                >
                  🧪 sandbox
                </span>
              </div>
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
                {{ artifact.identity.description || 'No description available.' }}
              </p>
              <div class="flex items-center gap-1.5 mt-1.5 flex-wrap">
                <span
                  class="text-xs px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded"
                >
                  {{ artifactTypeLabel(artifact.artifact_type) }}
                </span>
                <span
                  v-if="artifact.version"
                  class="text-xs text-gray-400 dark:text-gray-500"
                >
                  v{{ artifact.version }}
                </span>
              </div>

              <!-- Strategy Interface -->
              <div class="mt-2">
                <!-- Frontend-orchestrated: add to workspace -->
                <button
                  v-if="artifact.execution_model.orchestrator === 'frontend'"
                  class="inline-flex items-center gap-1 px-2 py-1 bg-blue-600 text-white rounded text-xs font-medium hover:bg-blue-700 transition-colors"
                  :aria-label="`Add ${artifact.identity.name} to workspace`"
                  @click="handleSelectArtifact(artifact)"
                >
                  ➕ Add to Workspace
                </button>

                <!-- Launcher-orchestrated: managed externally -->
                <div
                  v-else
                  class="inline-flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400"
                >
                  <span>🔄 Managed by Launcher</span>
                  <span
                    v-if="artifact.execution_model.heartbeat_channel"
                    class="ml-1 px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 rounded font-mono"
                  >
                    {{ artifact.execution_model.heartbeat_channel }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * @file View.vue
 * @description artifacts-explorer-cell — Phase 2 universal artifact explorer.
 *
 * Renders a filterable, searchable grid of artifacts from GET /api/v1/artifacts-map.
 * Category tabs (All / Cells / Infrastructure / Intelligence) are shown when
 * filter_mode !== 'cells_only'.
 * Strategy Interface: frontend-orchestrated artifacts show "Add to Workspace";
 * launcher-orchestrated show "Managed by Launcher" with optional heartbeat_channel.
 *
 * Props:
 *  - cellInstance: BaseCell instance (from resolveViewSpec)
 *  - cell: { cellTypeName, cellType, initialData } (from resolveViewSpec)
 */

import { ref, computed, onMounted } from 'vue'
import { createLogger } from '@/utils/logger'
import { useArtifactsExplorerStore } from './store'
import type { ExplorerArtifact, FilterMode } from './store'

const log = createLogger('cell:artifacts-explorer:view')

// ── Props ──────────────────────────────────────────────────────────────────────
const props = defineProps<{
  cellInstance?: any
  cell?: any
}>()

// ── Store & Local State ────────────────────────────────────────────────────────
const explorerStore = useArtifactsExplorerStore()
const searchQuery = ref('')

/** Active category tab key. Defaults to 'all'. */
const activeCategory = ref<'all' | 'cell-type' | 'service' | 'job-type'>('all')

// ── Derived filter_mode from cell initialData / props ─────────────────────────
const filterMode = computed<FilterMode>(() => {
  const initial = props.cell?.cellType?.default_initial_data ?? {}
  const mode = initial.filter_mode
  // Explicitly validate against known values; anything else defaults to 'all'.
  return mode === 'cells_only' ? 'cells_only' : 'all'
})

// ── Category Tabs ──────────────────────────────────────────────────────────────
const categoryTabs = [
  { key: 'all' as const, label: '🗂️ All' },
  { key: 'cell-type' as const, label: '🧩 Cells' },
  { key: 'service' as const, label: '🏗️ Infrastructure' },
  { key: 'job-type' as const, label: '🤖 Intelligence' },
]

// ── Computed ───────────────────────────────────────────────────────────────────
const filteredArtifacts = computed<ExplorerArtifact[]>(() => {
  let list = explorerStore.availableArtifacts

  // When cells_only mode, only cell-type artifacts are shown.
  // The server already filters via ?artifact_type=cell-type, but we guard
  // client-side too for data integrity (e.g. stale cache from a previous 'all' load).
  if (filterMode.value === 'cells_only') {
    list = list.filter((a) => a.artifact_type === 'cell-type')
  } else if (activeCategory.value !== 'all') {
    list = list.filter((a) => a.artifact_type === activeCategory.value)
  }

  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return list
  return list.filter(
    (a) =>
      a.identity.name?.toLowerCase().includes(q) ||
      a.identity.description?.toLowerCase().includes(q) ||
      a.artifact_type?.toLowerCase().includes(q),
  )
})

// ── Helpers ────────────────────────────────────────────────────────────────────

function getIcon(artifact: ExplorerArtifact): string {
  if (artifact.identity.icon) return artifact.identity.icon
  const fallbacks: Record<string, string> = {
    'cell-type': '🧩',
    service: '🏗️',
    'job-type': '🤖',
    worker: '⚙️',
    book: '📚',
  }
  return fallbacks[artifact.artifact_type] ?? '📦'
}

function artifactTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    'cell-type': 'Cell',
    service: 'Service',
    'job-type': 'Job',
    worker: 'Worker',
    book: 'Book',
  }
  return labels[type] ?? type
}

// ── Handlers ───────────────────────────────────────────────────────────────────
function handleSelectArtifact(artifact: ExplorerArtifact): void {
  if (artifact.execution_model.orchestrator !== 'frontend') return
  log.info('[ArtifactsExplorerView] Artifact selected', { name: artifact.identity.name })
  explorerStore.selectArtifact(artifact)
}

function loadArtifacts(): void {
  explorerStore.loadArtifacts(filterMode.value)
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────
onMounted(async () => {
  if (explorerStore.availableArtifacts.length === 0) {
    log.debug('[ArtifactsExplorerView] Loading artifacts on mount', {
      filterMode: filterMode.value,
    })
    await explorerStore.loadArtifacts(filterMode.value)
  }
})
</script>

<style scoped>
.artifact-card {
  transition:
    box-shadow 0.15s ease,
    border-color 0.15s ease;
}

.category-tab:focus {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(0, 0, 0, 0.1);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
