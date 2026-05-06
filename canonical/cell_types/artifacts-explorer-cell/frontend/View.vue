/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-05-06",
 *   "dark_mode_support": "full",
 *   "i18n_validated": false,
 *   "logger_namespace": "cell:artifacts-explorer:view",
 *   "validation_status": "initial"
 * }
 */
<template>
  <div class="artifacts-explorer-view flex flex-col h-full bg-white dark:bg-gray-900">
    <!-- Header -->
    <div class="explorer-header px-4 py-3 border-b border-gray-200 dark:border-gray-700">
      <h2 class="text-lg font-bold text-gray-900 dark:text-white">
        🔍 Select Cell Type
      </h2>
      <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
        Click a cell type to add it to your workspace.
      </p>
    </div>

    <!-- Search -->
    <div class="px-4 pt-3 pb-2">
      <input
        v-model="searchQuery"
        type="text"
        class="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm"
        placeholder="Search by name, description or category…"
        aria-label="Search cell types"
      />
    </div>

    <!-- Loading State -->
    <div v-if="explorerStore.isLoading" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <div class="spinner mb-2"></div>
        <p class="text-sm text-gray-500 dark:text-gray-400">Loading cell types…</p>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="explorerStore.error" class="flex-1 flex items-center justify-center px-4">
      <div class="text-center">
        <span class="text-4xl mb-2 block">⚠️</span>
        <p class="text-red-500 font-semibold mb-1">Failed to load cell types</p>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">{{ explorerStore.error }}</p>
        <button
          class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
          @click="explorerStore.loadCellTypes()"
        >
          Retry
        </button>
      </div>
    </div>

    <!-- Cell Types Grid -->
    <div v-else class="flex-1 overflow-auto px-4 pb-4">
      <!-- No results -->
      <div v-if="filteredTypes.length === 0" class="text-center py-8">
        <span class="text-3xl mb-2 block">🔍</span>
        <p class="text-gray-500 dark:text-gray-400 text-sm">
          No cell types found<template v-if="searchQuery"> for "{{ searchQuery }}"</template>.
        </p>
      </div>

      <!-- Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <button
          v-for="cellType in filteredTypes"
          :key="cellType.name"
          class="cell-type-card text-left bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 hover:shadow-md hover:border-blue-500 transition-all"
          :aria-label="`Add ${cellType.name}`"
          @click="handleSelectType(cellType)"
        >
          <div class="flex items-start gap-3">
            <!-- Icon -->
            <span class="text-2xl flex-shrink-0">{{ getIcon(cellType) }}</span>

            <!-- Content -->
            <div class="flex-1 min-w-0">
              <h3 class="font-semibold text-gray-900 dark:text-white text-sm truncate">
                {{ cellType.name }}
              </h3>
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
                {{ cellType.description || 'No description available.' }}
              </p>
              <div class="flex items-center gap-1.5 mt-1.5">
                <span
                  v-if="cellType.category"
                  class="text-xs px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded"
                >
                  {{ cellType.category }}
                </span>
                <span
                  v-if="cellType.version"
                  class="text-xs text-gray-400 dark:text-gray-500"
                >
                  v{{ cellType.version }}
                </span>
              </div>
            </div>
          </div>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * @file View.vue
 * @description artifacts-explorer-cell — picker mode UI.
 *
 * Renders a searchable grid of available cell types.
 * When a type is clicked, explorerStore.selectCellType() is called.
 * App.vue watches selectedCellType and instantiates the chosen type via handleCellTypeSelected().
 *
 * Props:
 *  - cellInstance: BaseCell instance (from resolveViewSpec)
 *  - cell: { cellTypeName, cellType } (from resolveViewSpec)
 *  - mode: 'picker' | 'view' — defaults to 'picker' (Phase 2: 'view' mode reserved)
 */

import { ref, computed, onMounted } from 'vue'
import { createLogger } from '@/utils/logger'
import { useArtifactsExplorerStore } from './store'
import type { ExplorerCellType } from './store'

const log = createLogger('cell:artifacts-explorer:view')

// ── Props ──────────────────────────────────────────────────────────────────────
defineProps<{
  cellInstance?: any
  cell?: any
  mode?: 'view' | 'picker'
}>()

// ── Store & Local State ────────────────────────────────────────────────────────
const explorerStore = useArtifactsExplorerStore()
const searchQuery = ref('')

// ── Computed ───────────────────────────────────────────────────────────────────
const filteredTypes = computed<ExplorerCellType[]>(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return explorerStore.availableCellTypes
  return explorerStore.availableCellTypes.filter(
    (t) =>
      t.name?.toLowerCase().includes(q) ||
      t.description?.toLowerCase().includes(q) ||
      t.category?.toLowerCase().includes(q),
  )
})

// ── Helpers ────────────────────────────────────────────────────────────────────
const iconMap: Record<string, string> = {
  'calculator-cell': '🧮',
  '3d-mesh-prototyping-cell': '🔷',
  'chat-ia': '💬',
  'file-manager-cell': '📁',
  'fragment-editor-cell': '✏️',
  'issues-dashboard-cell': '📋',
  'log-toggle-cell': '📊',
  'content-manager-cell': '📦',
  'manual-capture-cell': '📸',
  'roles-management-cell': '👥',
}

function getIcon(cellType: ExplorerCellType): string {
  if (cellType.icon) return cellType.icon
  return iconMap[cellType.name] || '📦'
}

// ── Handlers ───────────────────────────────────────────────────────────────────
function handleSelectType(cellType: ExplorerCellType): void {
  log.info('[ArtifactsExplorerView] Cell type selected', { name: cellType.name })
  explorerStore.selectCellType(cellType)
}

// ── Lifecycle ──────────────────────────────────────────────────────────────────
onMounted(async () => {
  if (explorerStore.availableCellTypes.length === 0) {
    log.debug('[ArtifactsExplorerView] Loading cell types on mount')
    await explorerStore.loadCellTypes()
  }
})
</script>

<style scoped>
.cell-type-card {
  cursor: pointer;
}

.cell-type-card:focus {
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
