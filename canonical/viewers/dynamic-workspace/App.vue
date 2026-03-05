<!--
  App.vue — DynamicWorkspace v2
  Phase 2: Cell Rendering with HybridDatabase Integration

  Orchestrates:
  1. Cockpit ↔ Runner handshake (Phase 1, preserved)
  2. Cell type loading via useCellViewProvider
  3. Grid state via useGridLayout
  4. All UI components (AddCellModal, GridContainer, FooterWindowManager, …)

  Flow: Handshake → Ready → User adds cell → BaseCell instantiated →
        show() called → ViewSpec resolved → Grid renders cell
-->
<template>
  <div
    class="dynamic-workspace-v2 flex flex-col h-screen bg-gray-100 dark:bg-gray-950 overflow-hidden"
  >
    <!-- ── Handshake pending / error overlay ────────────────────────────── -->
    <div
      v-if="store.status !== 'ready'"
      class="flex-1 flex flex-col items-center justify-center gap-4 p-8 bg-gray-950 text-slate-100"
    >
      <div class="status-badge" :class="statusClass">{{ statusLabel }}</div>
      <h1 class="text-2xl font-bold text-sky-400">Dynamic Workspace v2</h1>

      <p v-if="store.status === 'pending'" class="text-slate-400 text-center">
        Waiting for handshake from Cockpit…
      </p>
      <p v-else class="text-red-400 text-center">
        {{ store.errorMessage || 'Unknown error during handshake.' }}
      </p>

      <pre v-if="isDev" class="text-xs text-slate-500 bg-slate-800 rounded p-4 max-w-sm w-full">{{ debugInfo }}</pre>
    </div>

    <!-- ── Main workspace (only shown when handshake ready) ─────────────── -->
    <template v-else>
      <!-- Grid Area -->
      <main class="flex-1 overflow-hidden pb-16">
        <GridContainer
          :cells="cells"
          @remove-cell="handleRemoveCell"
          @minimize-cell="toggleMinimize"
          @maximize-cell="toggleMaximize"
        />
      </main>

      <!-- Footer -->
      <FooterWindowManager
        :cell-count="cells.length"
        :max-cells="MAX_CELLS"
        :cell-tabs="cellTabs"
        @show-add-modal="showAddModal = true"
        @close-cell="handleRemoveCell"
      />

      <!-- AddCell Modal -->
      <AddCellModal
        :is-open="showAddModal"
        :cell-types="availableCellTypes"
        :is-loading="isLoadingCellTypes"
        :error="cellTypesError"
        @close="showAddModal = false"
        @cell-type-selected="handleCellTypeSelected"
        @retry="loadCellTypes"
      />

      <!-- SaveLayout Modal -->
      <SaveLayoutBookModal
        :is-open="showSaveLayoutModal"
        :cells="[...cells]"
        @save-layout="handleSaveLayout"
        @cancel="showSaveLayoutModal = false"
      />

      <!-- Dev debug overlay -->
      <pre v-if="isDev" class="fixed top-2 right-2 text-xs bg-black/70 text-green-400 rounded p-2 max-w-xs overflow-auto z-[999]">{{ devInfo }}</pre>
    </template>
  </div>
</template>

<script setup lang="ts">
/**
 * Phase 2 orchestration:
 *  - Handshake (Phase 1, preserved)
 *  - Cell type loading from HybridDatabase
 *  - BaseCell instantiation + show() → ViewSpec resolution
 *  - Reactive grid management
 */

import { ref, computed, onMounted } from 'vue'
import { useWorkspaceHandshake } from './composables/useWorkspaceHandshake'
import { useGridLayout } from './composables/useGridLayout'
import { useCellViewProvider } from './composables/useCellViewProvider'
import GridContainer from './components/GridContainer.vue'
import FooterWindowManager from './components/FooterWindowManager.vue'
import AddCellModal from './components/AddCellModal.vue'
import SaveLayoutBookModal from './components/SaveLayoutBookModal.vue'
import { createLogger } from '@/utils/logger'
import type { CellTypeDefinition } from './types'

const log = createLogger('workspace:app')

// ── Handshake (Phase 1) ───────────────────────────────────────────────────────
const { store } = useWorkspaceHandshake()

// ── Grid Layout ───────────────────────────────────────────────────────────────
const { cells, addCell, removeCell, updateCell, toggleMinimize, toggleMaximize } = useGridLayout()

// ── Cell View Provider ────────────────────────────────────────────────────────
const { getCellTypes, instantiateCellByType, resolveViewSpec } = useCellViewProvider()

// ── Constants ─────────────────────────────────────────────────────────────────
const MAX_CELLS = 10

// ── UI State ──────────────────────────────────────────────────────────────────
const showAddModal = ref(false)
const showSaveLayoutModal = ref(false)
const availableCellTypes = ref<CellTypeDefinition[]>([])
const isLoadingCellTypes = ref(false)
const cellTypesError = ref<string | null>(null)

const isDev = import.meta.env.DEV

// ── Computed ──────────────────────────────────────────────────────────────────
const statusClass = computed(() => ({
  'status-pending': store.status === 'pending',
  'status-ready': store.status === 'ready',
  'status-error': store.status === 'error',
}))

const statusLabel = computed(() => {
  switch (store.status) {
    case 'ready': return '🟢 Ready'
    case 'error': return '🔴 Error'
    default: return '🟡 Pending'
  }
})

const debugInfo = computed(() =>
  JSON.stringify({ workspaceId: store.workspaceId, status: store.status, errorCode: store.errorCode }, null, 2),
)

const devInfo = computed(() =>
  JSON.stringify({ cells: cells.value.length, types: availableCellTypes.value.length, status: store.status }, null, 2),
)

/** Tabs for FooterWindowManager */
const cellTabs = computed(() =>
  cells.value.map(cell => ({
    cellId: cell.cellId,
    name: cell.cellType?.name || cell.cellTypeName,
    icon: cell.cellType?.icon || '📦',
  })),
)

// ── Cell Type Loading ─────────────────────────────────────────────────────────

async function loadCellTypes(): Promise<void> {
  isLoadingCellTypes.value = true
  cellTypesError.value = null
  try {
    availableCellTypes.value = await getCellTypes()
    log.info('[App] Cell types loaded', { count: availableCellTypes.value.length })
  } catch (err: any) {
    cellTypesError.value = err?.message || 'Failed to load cell types'
    log.error('[App] Failed to load cell types', err)
  } finally {
    isLoadingCellTypes.value = false
  }
}

// ── Cell CRUD ─────────────────────────────────────────────────────────────────

/**
 * Handle cell type selected in AddCellModal.
 *
 * Flow (Requirement 2 — ONE orchestration path):
 * 1. addCell() → creates GridCell with isLoading = true
 * 2. instantiateCellByType() → dynamic import + new CellClass()
 * 3. resolveViewSpec() → cellInstance.show() → {component, props}
 * 4. updateCell() → sets cellInstance, viewSpec, isLoading = false
 */
async function handleCellTypeSelected(cellType: CellTypeDefinition): Promise<void> {
  log.info('[App] handleCellTypeSelected', { cellTypeName: cellType.name })

  // 1. Add to grid (loading state)
  const cellId = addCell(cellType.name, cellType)

  try {
    // 2. Instantiate BaseCell — uses cellType.name (semantic, never UUID)
    const cellInstance = await instantiateCellByType(cellType.name, cellType)

    // 3. Resolve ViewSpec — cellInstance.show() is source of truth
    const viewSpec = await resolveViewSpec(cellInstance, cellType.name, cellType)

    // 4. Update cell with resolved data
    updateCell(cellId, { cellInstance, viewSpec, isLoading: false })
    log.info('[App] Cell ready', { cellId, cellTypeName: cellType.name })
  } catch (err: any) {
    const errorMsg = err?.message || 'Failed to load cell'
    updateCell(cellId, { isLoading: false, error: errorMsg })
    log.error('[App] Cell loading failed', { cellId, error: errorMsg })
  }
}

function handleRemoveCell(cellId: string): void {
  removeCell(cellId)
  log.info('[App] Cell removed', { cellId })
}

// ── Layout Persistence (Phase 3 stub) ─────────────────────────────────────────

function handleSaveLayout(name: string, description: string): void {
  log.info('[App] Save layout requested (Phase 3)', { name, description })
  showSaveLayoutModal.value = false
  // Phase 3 will persist via HybridDatabase
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(() => {
  // Pre-load cell types so AddCellModal opens instantly
  loadCellTypes()
})
</script>

<style scoped>
.status-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.875rem;
  font-weight: 600;
}

.status-pending { background: #78350f; color: #fde68a; }
.status-ready   { background: #14532d; color: #86efac; }
.status-error   { background: #7f1d1d; color: #fca5a5; }
</style>
