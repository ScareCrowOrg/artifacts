<!--
  App.vue — DynamicWorkspace v2
  Phase 3: Layout Persistence with HybridDatabase Integration

  Orchestrates:
  1. Cockpit ↔ Runner handshake (Phase 1, preserved)
  2. Cell type loading via useCellViewProvider
  3. Grid state via useGridLayout
  4. Layout persistence via usePersistenceManager (Phase 3)
  5. Auto-save via useAutoSave (Phase 3)
  6. All UI components (Toolbar, AddCellModal, GridContainer, FooterWindowManager, …)

  Flow: Handshake → Ready → User adds cell → BaseCell instantiated →
        show() called → ViewSpec resolved → Grid renders cell
        User saves layout → usePersistenceManager.saveLayout() → HybridDatabase
        User loads layout → usePersistenceManager.fetchLayout() → hydrate cells
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
      <!-- Toolbar (Phase 3) -->
      <Toolbar
        :has-unsaved="hasUnsavedChanges"
        :is-saving="isSavingLayout"
        @save-layout="showSaveLayoutModal = true"
      />

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
        :saved-layouts="savedLayouts"
        :is-loading-layouts="isLoadingLayouts"
        @show-add-modal="showAddModal = true"
        @close-cell="handleRemoveCell"
        @load-layout="handleLoadLayout"
        @save-layout="showSaveLayoutModal = true"
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

      <!-- Load error toast -->
      <div
        v-if="loadError"
        class="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-red-600 text-white px-4 py-2 rounded-lg shadow-lg text-sm"
        @click="loadError = null"
      >
        {{ loadError }}
      </div>

      <!-- Save success toast -->
      <div
        v-if="saveSuccess"
        class="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-green-600 text-white px-4 py-2 rounded-lg shadow-lg text-sm"
      >
        {{ saveSuccess }}
      </div>

      <!-- Dev debug overlay -->
      <pre v-if="isDev" class="fixed top-2 right-2 text-xs bg-black/70 text-green-400 rounded p-2 max-w-xs overflow-auto z-[999]">{{ devInfo }}</pre>
    </template>
  </div>
</template>

<script setup lang="ts">
/**
 * Phase 3 orchestration:
 *  - All Phase 2 functionality preserved
 *  - Layout persistence via usePersistenceManager
 *  - Background auto-save via useAutoSave
 *  - Toolbar with Save button and unsaved-changes indicator
 *  - LayoutBookSelector in footer for loading saved layouts
 *  - Asynchronous cell hydration when loading a layout
 */

// ── Tailwind CSS & Design System ──────────────────────────────────────────────
import '@/styles/index.css'

import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useWorkspaceHandshake } from './composables/useWorkspaceHandshake'
import { useGridLayout } from './composables/useGridLayout'
import { useCellViewProvider } from './composables/useCellViewProvider'
import { usePersistenceManager } from './composables/usePersistenceManager'
import { useAutoSave } from './composables/useAutoSave'
import GridContainer from './components/GridContainer.vue'
import FooterWindowManager from './components/FooterWindowManager.vue'
import AddCellModal from './components/AddCellModal.vue'
import SaveLayoutBookModal from './components/SaveLayoutBookModal.vue'
import Toolbar from './components/Toolbar.vue'
import { createLogger } from '@/utils/logger'
import type { CellTypeDefinition, LayoutBook } from './types'

const log = createLogger('workspace:app')
const { t } = useI18n()

// ── Handshake (Phase 1) ───────────────────────────────────────────────────────
const { store } = useWorkspaceHandshake()

// ── Grid Layout ───────────────────────────────────────────────────────────────
const { cells, addCell, removeCell, updateCell, toggleMinimize, toggleMaximize, clearCells } = useGridLayout()

// ── Cell View Provider ────────────────────────────────────────────────────────
const { getCellTypes, instantiateCellByType, resolveViewSpec } = useCellViewProvider()

// ── Persistence (Phase 3) ─────────────────────────────────────────────────────
const persistence = usePersistenceManager()
const autoSave = useAutoSave()

// ── Constants ─────────────────────────────────────────────────────────────────
const MAX_CELLS = 10

/** Toast visibility duration (ms) */
const TOAST_DURATION_MS = 3_000

// ── UI State ──────────────────────────────────────────────────────────────────
const showAddModal = ref(false)
const showSaveLayoutModal = ref(false)
const availableCellTypes = ref<CellTypeDefinition[]>([])
const isLoadingCellTypes = ref(false)
const cellTypesError = ref<string | null>(null)
const savedLayouts = ref<LayoutBook[]>([])
const isLoadingLayouts = ref(false)
const isSavingLayout = ref(false)
const loadError = ref<string | null>(null)
const saveSuccess = ref<string | null>(null)
let loadErrorTimer: ReturnType<typeof setTimeout> | null = null
let saveSuccessTimer: ReturnType<typeof setTimeout> | null = null

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
  JSON.stringify({
    cells: cells.value.length,
    types: availableCellTypes.value.length,
    status: store.status,
    unsaved: autoSave.hasUnsavedChanges.value,
    layouts: savedLayouts.value.length,
  }, null, 2),
)

const hasUnsavedChanges = computed(() => autoSave.hasUnsavedChanges.value)

/** Tabs for FooterWindowManager */
const cellTabs = computed(() =>
  cells.value.map(cell => ({
    cellId: cell.cellId,
    name: cell.cellType?.name || cell.cellTypeName,
    icon: cell.cellType?.icon || '📦',
  })),
)

// ── Helpers ───────────────────────────────────────────────────────────────────

function showLoadError(message: string): void {
  loadError.value = message
  if (loadErrorTimer !== null) clearTimeout(loadErrorTimer)
  loadErrorTimer = setTimeout(() => { loadError.value = null }, TOAST_DURATION_MS)
}

function showSaveSuccessToast(message: string): void {
  saveSuccess.value = message
  if (saveSuccessTimer !== null) clearTimeout(saveSuccessTimer)
  saveSuccessTimer = setTimeout(() => { saveSuccess.value = null }, TOAST_DURATION_MS)
}

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

// ── Saved Layouts Loading ─────────────────────────────────────────────────────

async function loadSavedLayouts(): Promise<void> {
  if (!store.sessionToken) return
  isLoadingLayouts.value = true
  try {
    savedLayouts.value = await persistence.listLayouts()
    log.info('[App] Saved layouts loaded', { count: savedLayouts.value.length })
  } catch (err: any) {
    log.warn('[App] Failed to load saved layouts', { error: err?.message })
  } finally {
    isLoadingLayouts.value = false
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

  const cellId = addCell(cellType.name, cellType)

  try {
    const cellInstance = await instantiateCellByType(cellType.name, cellType)
    const viewSpec = await resolveViewSpec(cellInstance, cellType.name, cellType)
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

// ── Layout Persistence (Phase 3) ──────────────────────────────────────────────

/**
 * Save the current grid layout as a named layout book.
 * Called from SaveLayoutBookModal @save-layout event.
 */
async function handleSaveLayout(name: string, description: string): Promise<void> {
  isSavingLayout.value = true
  try {
    const book = await persistence.saveLayout(name, description)
    showSaveLayoutModal.value = false
    showSaveSuccessToast(t('layout.persistence.saveSuccess'))
    log.info('[App] Layout saved', { layoutId: book.id, name })
    // Refresh list so the new entry appears in LayoutBookSelector
    await loadSavedLayouts()
  } catch (err: any) {
    showLoadError(t('layout.persistence.saveError'))
    log.error('[App] Failed to save layout', { error: err?.message })
  } finally {
    isSavingLayout.value = false
  }
}

/**
 * Load a saved layout by ID with asynchronous cell hydration.
 *
 * Hydration flow per cell (ESSENTIAL — prevents "empty cell flash"):
 * 1. Add to grid in isLoading=true state
 * 2. instantiateCellByType()
 * 3. resolveViewSpec() — cellInstance.show()
 * 4. updateCell() with final data (isLoading=false)
 *
 * One cell failing does NOT abort the whole layout load.
 */
async function handleLoadLayout(layoutId: string): Promise<void> {
  log.info('[App] Loading layout', { layoutId })

  let book
  try {
    book = await persistence.fetchLayout(layoutId)
  } catch (err: any) {
    showLoadError(t('layout.persistence.loadError'))
    log.error('[App] Failed to fetch layout', { layoutId, error: err?.message })
    return
  }

  const cellRefs = book.initial_data?.cells ?? []

  // Step 1: Clear current grid
  clearCells()

  // Step 2: Hydrate each cell sequentially (respects BaseCell contract: show() before render)
  for (const cellRef of cellRefs) {
    const tempId = addCell(cellRef.type, null)
    updateCell(tempId, { isLoading: true })

    try {
      // Find the full CellTypeDefinition from the loaded list (or synthesize a minimal one)
      const knownType = availableCellTypes.value.find(t => t.name === cellRef.type)
      const cellType: CellTypeDefinition = knownType ?? {
        name: cellRef.type,
        id: cellRef.type,
        description: '',
        version: '1.0.0',
        can_render_dynamically: true,
      }

      const cellInstance = await instantiateCellByType(cellRef.type, cellType)
      const viewSpec = await resolveViewSpec(cellInstance, cellRef.type, cellType)

      updateCell(tempId, {
        cellInstance,
        viewSpec,
        cellType,
        position: cellRef.position,
        isMinimized: cellRef.state?.isMinimized ?? false,
        isMaximized: cellRef.state?.isMaximized ?? false,
        isLoading: false,
      })

      log.info('[App] Cell hydrated', { cellId: tempId, type: cellRef.type })
    } catch (err: any) {
      log.error('[App] Cell hydration failed', { type: cellRef.type, error: err?.message })
      updateCell(tempId, {
        isLoading: false,
        error: t('layout.persistence.hydrationError', { type: cellRef.type }),
      })
    }
  }

  log.info('[App] Layout loaded', { layoutId, cellCount: cellRefs.length })
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(() => {
  // Defer cell type loading and persistence init until workspace is ready (session token available).
  // Use a reactive watch so we cleanly respond to the handshake completing.
  if (store.status === 'ready') {
    loadCellTypes()
    initPersistence()
  } else {
    const stopWatch = watch(
      () => store.status,
      (status) => {
        if (status === 'ready') {
          stopWatch()
          loadCellTypes()
          initPersistence()
        }
      },
    )
  }
})

onUnmounted(() => {
  autoSave.disableAutoSave()
  if (loadErrorTimer !== null) clearTimeout(loadErrorTimer)
  if (saveSuccessTimer !== null) clearTimeout(saveSuccessTimer)
})

async function initPersistence(): Promise<void> {
  await loadSavedLayouts()
  autoSave.enableAutoSave()
  log.info('[App] Persistence initialized')
}
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
