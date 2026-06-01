/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-05-13",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<!--
  App.vue — DynamicWorkspace v2
  Phase 4: AddCellModal → artifacts-explorer-cell migration
  Fix: gridKey remount on layout load

  Orchestrates:
  1. Cockpit ↔ Runner handshake (Phase 1, preserved)
  2. Cell instantiation via useCellViewProvider
  3. Grid state via useGridLayout
  4. Layout persistence via usePersistenceManager (Phase 3)
  5. Auto-save via useAutoSave (Phase 3)
  6. All UI components (Toolbar, GridContainer, FooterWindowManager, …)
  7. artifacts-explorer-cell integration via useArtifactsExplorerStore (Phase 4)

  Flow: Handshake → Ready → User clicks ➕ → artifacts-explorer-cell rendered →
        User selects cell type → explorerStore.selectedCellType watcher fires →
        handleCellTypeSelected(cellType) → BaseCell instantiated → Grid renders cell
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
      <h1 class="text-2xl font-bold text-sky-400">{{ t('layout.dynamicWorkspace.title') }}</h1>

      <p v-if="store.status === 'pending'" class="text-slate-400 text-center">
        {{ t('layout.dynamicWorkspace.waitingHandshake') }}
      </p>
      <p v-else class="text-red-400 text-center">
        {{ store.errorMessage || t('layout.dynamicWorkspace.unknownHandshakeError') }}
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
          :key="gridKey"
          :cells="cells"
          @remove-cell="handleRemoveCell"
          @minimize-cell="toggleMinimize"
          @maximize-cell="toggleMaximize"
          @save-cell="handleSaveCellState"
          @load-cell="openLoadModal($event)"
          @delete-persisted-cell="e => handleDeletePersistedCell(e.runtimeId, e.cellId)"
        />
      </main>

      <!-- Footer -->
      <FooterWindowManager
        :cell-count="cells.length"
        :max-cells="MAX_CELLS"
        :cell-tabs="cellTabs"
        :saved-layouts="savedLayouts"
        :is-loading-layouts="isLoadingLayouts"
        @show-artifacts-explorer="handleShowArtifactsExplorer"
        @close-cell="handleRemoveCell"
        @load-layout="handleLoadLayout"
        @save-layout="showSaveLayoutModal = true"
        @show-load-modal="showLoadModal = true"
      />

      <!-- LoadCellModal (Phase 5: Persisted Cell Runtime UI) -->
      <LoadCellModal
        :visible="showLoadModal"
        :persisted-cells="loadableCells"
        :is-loading="isLoadingPersistedCells"
        :cell-types="explorerStore.availableCellTypes"
        :cell-type-id-filter="loadCellTypeFilter"
        @close="showLoadModal = false"
        @load-cell="handleLoadPersistedCell"
        @delete-cell="handleDeleteFromModal"
      />

      <!-- SaveLayout Modal -->
      <SaveLayoutBookModal
        :is-open="showSaveLayoutModal"
        :cells="[...cells]"
        @save-layout="handleSaveLayout"
        @cancel="showSaveLayoutModal = false"
      />

      <!-- Explorer Modal: artifacts-explorer-cell in picker mode -->
      <CellModal
        :is-open="isExplorerModalOpen"
        :cell="modalCell"
        @close="handleCloseExplorerModal"
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

      <!-- Dev debug overlay (disabled) -->
      <!-- <pre v-if="isDev" class="fixed top-2 right-2 text-xs bg-black/70 text-green-400 rounded p-2 max-w-xs overflow-auto z-[999]">{{ devInfo }}</pre> -->
    </template>
  </div>
</template>

<script setup lang="ts">
/**
 * Phase 4 orchestration:
 *  - All Phase 2 + Phase 3 functionality preserved
 *  - AddCellModal removed; replaced by artifacts-explorer-cell
 *  - useArtifactsExplorerStore bridges explorer cell selection → handleCellTypeSelected
 *  - loadCellTypes() delegated to the explorer store (lazy, on cell mount)
 */

// ── Tailwind CSS & Design System ──────────────────────────────────────────────
import '@/styles/index.css'
// See: VITE_SLOWNESS_ROOT_CAUSE.md

import { ref, computed, watch, onMounted, onUnmounted, provide } from 'vue'
import { useI18n } from 'vue-i18n'
import { useBaseViewer } from '@/composables/useBaseViewer'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useGridLayout } from './composables/useGridLayout'
import { useCellViewProvider } from './composables/useCellViewProvider'
import { usePersistenceManager } from './composables/usePersistenceManager'
import { useCellRuntime } from './composables/useCellRuntime'
import type { PersistedCell } from './composables/useCellRuntime'
import { useAutoSave } from './composables/useAutoSave'
import { useAutoLoadCellI18n } from './composables/useAutoLoadCellI18n'
import { useThemeSync } from '#artifacts/shared/composables/useThemeSync'
import GridContainer from './components/GridContainer.vue'
import FooterWindowManager from './components/FooterWindowManager.vue'
import SaveLayoutBookModal from './components/SaveLayoutBookModal.vue'
import Toolbar from './components/Toolbar.vue'
import CellModal from './components/CellModal.vue'
import LoadCellModal from './components/LoadCellModal.vue'
import { createLogger } from '@/utils/logger'
import { CELL_FACTORY_KEY, CELL_STATE_BRIDGE_KEY, type CellFactory, type CellStateBridge } from '#canonical/shared/cellFactory'
import { useArtifactsExplorerStore } from '#canonical/cell_types/artifacts-explorer-cell/frontend/store'
import type { ExplorerArtifact } from '#canonical/cell_types/artifacts-explorer-cell/frontend/store'
import type { CellTypeDefinition, GridCell, LayoutBook } from './types'

const log = createLogger('workspace:app')
const { t } = useI18n()

// ── Handshake (Phase 1) — managed by useBaseViewer ──────────────────────────
useBaseViewer({ validationMode: 'validated' })
const store = useWorkspaceStore()

// ── Grid Layout ───────────────────────────────────────────────────────────────
const { cells, addCell, removeCell, updateCell, toggleMinimize, toggleMaximize, clearCells } = useGridLayout()

// ⚡ CENTRALIZED i18n: Discovery-based auto-loading (Opção C)
// Monitors cells array and workspaceStore.locale changes.
// Automatically loads and merges cell translations under namespace: cells.{cellTypeName}
useAutoLoadCellI18n(cells)

// ⚡ CENTRALIZED Theme Sync: Apply Cockpit-Vue theme to DOM
// Monitors workspaceStore.theme changes and applies 'dark' class to document.documentElement
// Enables Tailwind CSS dark mode (dark:bg-gray-950, etc.)
useThemeSync()

// ── Cell View Provider ────────────────────────────────────────────────────────
const { instantiateCellByType, resolveViewSpec } = useCellViewProvider()

// ── Artifacts Explorer Store (Phase 4) ────────────────────────────────────────
// Bridge between artifacts-explorer-cell picker UI and handleCellTypeSelected.
const explorerStore = useArtifactsExplorerStore()

// ── Persistence (Phase 3) ─────────────────────────────────────────────────────
const persistence = usePersistenceManager()
const cellRuntime = useCellRuntime()
const autoSave = useAutoSave()

// ── Constants ─────────────────────────────────────────────────────────────────
const MAX_CELLS = 10
const EXPLORER_CELL_TYPE_NAME = 'artifacts-explorer-cell'

/** Toast visibility duration (ms) */
const TOAST_DURATION_MS = 3_000

// ── UI State ──────────────────────────────────────────────────────────────────
const showSaveLayoutModal = ref(false)
const gridKey = ref(0)
const savedLayouts = ref<LayoutBook[]>([])
const isLoadingLayouts = ref(false)
const isSavingLayout = ref(false)
const loadError = ref<string | null>(null)
const saveSuccess = ref<string | null>(null)
let loadErrorTimer: ReturnType<typeof setTimeout> | null = null
let saveSuccessTimer: typeof loadErrorTimer = null

// ── Load Cell Modal State (Phase 5) ───────────────────────────────────────────
const showLoadModal = ref(false)
const loadableCells = ref<PersistedCell[]>([])
const isLoadingPersistedCells = ref(false)
/** When triggered from CellItem toolbar, filter modal by cell type */
const loadCellTypeFilter = ref<string | null>(null)

/** Watch modal open → load persisted cells from MongoDB */
watch(showLoadModal, async (visible) => {
  if (visible) {
    isLoadingPersistedCells.value = true
    try {
      loadableCells.value = await cellRuntime.listCellRuntimes() || []
    } catch (err: any) {
      log.warn('[App] Failed to load persisted cells for modal', { error: err?.message })
    } finally {
      isLoadingPersistedCells.value = false
    }
  } else {
    // Reset filter when modal closes
    loadCellTypeFilter.value = null
  }
})

/**
 * Open the load modal with an optional cell type filter.
 * When triggered from a cell toolbar, only show persisted cells of that type.
 */
function openLoadModal(payload: { cellId: string; cellTypeId: string }): void {
  loadCellTypeFilter.value = payload.cellTypeId || null
  showLoadModal.value = true
}

// ── Explorer Modal State ────────────────────────────────────────────────────────
const isExplorerModalOpen = ref(false)
const modalCell = ref<GridCell | null>(null)

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
    explorerArtifacts: explorerStore.availableArtifacts.length,
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
 * Handle cell type selected — either from the explorer cell or any future source.
 *
 * Flow (ONE orchestration path):
 * 1. addCell() → creates GridCell with isLoading = true
 * 2. instantiateCellByType() → dynamic import + new CellClass()
 * 3. resolveViewSpec() → cellInstance.show() → {component, props}
 * 4. updateCell() → sets cellInstance, viewSpec, isLoading = false
 */
async function handleCellTypeSelected(
  cellType: CellTypeDefinition,
  initialData?: Record<string, any>,
  runtimeOpts?: { runtimeId?: string; isPersisted?: boolean },
): Promise<string | undefined> {
  log.info('[App] handleCellTypeSelected', { cellTypeName: cellType.name })

  const cellId = addCell(cellType.name, cellType)

  try {
    const cellInstance = await instantiateCellByType(cellType.name, cellType)
    const viewSpec = await resolveViewSpec(cellInstance, cellType.name, cellType, initialData, cellId)
    updateCell(cellId, {
      cellInstance,
      viewSpec,
      isLoading: false,
      ...(runtimeOpts ? { runtimeId: runtimeOpts.runtimeId, isPersisted: runtimeOpts.isPersisted ?? false } : {}),
    })
    log.info('[App] Cell ready', { cellId, cellTypeName: cellType.name })
    return cellId
  } catch (err: any) {
    const errorMsg = err?.message || 'Failed to load cell'
    updateCell(cellId, { isLoading: false, error: errorMsg })
    log.error('[App] Cell loading failed', { cellId, error: errorMsg })
    return undefined
  }
}

/**
 * Open the artifacts-explorer-cell in a modal overlay.
 * Called when FooterWindowManager emits 'show-artifacts-explorer'.
 *
 * Instantiates the explorer cell in memory (not in the grid), creates a temporary
 * GridCell, and shows it inside CellModal. When the user selects an artifact,
 * the explorerStore.selectedArtifact watcher adds it to the grid and closes the modal.
 */
async function handleShowArtifactsExplorer(): Promise<void> {
  if (isExplorerModalOpen.value) {
    log.debug('[App] Explorer modal already open, skipping')
    return
  }

  const explorerType: CellTypeDefinition = {
    name: EXPLORER_CELL_TYPE_NAME,
    id: EXPLORER_CELL_TYPE_NAME,
    description: 'Artifacts Explorer — browse and add cell types to the workspace.',
    version: '1.0.0',
    can_render_dynamically: true,
    default_refs: {
      basecell: ['frontend/ArtifactsExplorerCell.ts'],
      view: ['frontend/View.vue'],
    },
  }

  log.info('[App] Opening artifacts-explorer-cell in modal')

  // Create a temporary GridCell in loading state for the modal
  const tempCell: GridCell = {
    cellId: 'explorer-modal',
    cellTypeName: EXPLORER_CELL_TYPE_NAME,
    cellType: explorerType,
    cellInstance: null,
    viewSpec: null,
    isLoading: true,
    error: null,
    isMinimized: false,
    isMaximized: false,
    position: { x: 0, y: 0, w: 6, h: 12 },
  }

  modalCell.value = tempCell
  isExplorerModalOpen.value = true

  try {
    const cellInstance = await instantiateCellByType(EXPLORER_CELL_TYPE_NAME, explorerType)
    const viewSpec = await resolveViewSpec(cellInstance, EXPLORER_CELL_TYPE_NAME, explorerType, undefined, 'explorer-modal')

    modalCell.value = {
      ...tempCell,
      cellInstance,
      viewSpec,
      isLoading: false,
    }
  } catch (err: any) {
    const errorMsg = err?.message || 'Failed to load artifacts explorer'
    log.error('[App] Explorer cell instantiation failed', { error: errorMsg })
    modalCell.value = {
      ...tempCell,
      isLoading: false,
      error: errorMsg,
    }
  }
}

function handleCloseExplorerModal(): void {
  isExplorerModalOpen.value = false
  modalCell.value = null
}

// ── Cell Factory (provide/inject) ─────────────────────────────────────────
// Permite que qualquer celula filha crie novas celulas na workspace
// Uso: const cellFactory = inject(CELL_FACTORY_KEY)
//       cellFactory?.addChildCell('file-editor-v2', { fileName, filePath, language })
// Veja: #canonical/shared/cellFactory.ts para a definicao da interface e chave

function findCellTypeByName(type: string): CellTypeDefinition | null {
  // 🚨 DEBUG: Log availableCellTypes state
  console.log('🔴 [workspace:app] findCellTypeByName CALLED', {
    type,
    availableCellTypesExists: 'availableCellTypes' in explorerStore,
    availableCellTypesValue: explorerStore.availableCellTypes,
    availableCellTypesType: typeof explorerStore.availableCellTypes,
    availableCellTypesIsArray: Array.isArray(explorerStore.availableCellTypes),
    availableCellTypesLength: Array.isArray(explorerStore.availableCellTypes) ? explorerStore.availableCellTypes.length : 'N/A',
    availableArtifactsLength: explorerStore.availableArtifacts?.length,
    availableArtifacts: explorerStore.availableArtifacts?.map(a => a.artifact_id),
    timestamp: Date.now(),
  })
  const known = explorerStore.availableCellTypes as CellTypeDefinition[]
  const result = known?.find(t => t.name === type) ?? null
  console.log('🔴 [workspace:app] findCellTypeByName RESULT:', {
    type,
    found: result !== null,
    resultName: result?.name,
    timestamp: Date.now(),
  })
  return result
}

const cellFactory: CellFactory = {
  async addChildCell(type: string, initialData?: Record<string, any>) {
    let cellTypeDef = findCellTypeByName(type)

    // Lazy-load cell types if not yet loaded
    if (!cellTypeDef) {
      log.info('[App] addChildCell: cell type not found, lazy-loading artifacts', { type })
      try {
        await explorerStore.loadCellTypes()
        cellTypeDef = findCellTypeByName(type)
      } catch (err) {
        log.error('[App] addChildCell: failed to lazy-load cell types', { type, error: err })
      }
    }

    if (!cellTypeDef) {
      log.error('[App] addChildCell: unknown cell type after load', { type })
      return undefined
    }
    return await handleCellTypeSelected(cellTypeDef, initialData)
  },
  async closeCell(cellId: string) {
    log.info('[App] closeCell: removing cell', { cellId })
    removeCell(cellId)
  },
}

provide(CELL_FACTORY_KEY, cellFactory)

// ── Cell State Bridge (View Bridge) ──────────────────────────────────────
// View.vue registers content_id providers so App.vue can capture them
// during save without needing direct access to View.vue's reactive state.
const stateProviders = new Map<string, () => Record<string, any>>()

function registerStateProvider(cellId: string, provider: () => Record<string, any>): void {
  stateProviders.set(cellId, provider)
}

function unregisterStateProvider(cellId: string): void {
  stateProviders.delete(cellId)
}

const cellStateBridge: CellStateBridge = { registerStateProvider, unregisterStateProvider }
provide(CELL_STATE_BRIDGE_KEY, cellStateBridge)

// ── Explorer store watcher (Phase 4 → Phase 2 upgrade) ───────────────────────
// When the user clicks a frontend-orchestrated artifact in the explorer,
// explorerStore.selectedArtifact is set. This watcher reacts and adds it to the grid.
// Guard: only orchestrator === 'frontend' artifacts are instantiated as cells.
watch(
  () => explorerStore.selectedArtifact,
  async (artifact: ExplorerArtifact | null) => {
    if (!artifact) return

    // Close the explorer modal since the user selected an artifact
    isExplorerModalOpen.value = false
    modalCell.value = null

    if (artifact.execution_model.orchestrator !== 'frontend') {
      log.info('[App] Ignoring non-frontend artifact selection', {
        name: artifact.identity.name,
        orchestrator: artifact.execution_model.orchestrator,
      })
      explorerStore.clearSelection()
      return
    }
    log.info('[App] Explorer selected artifact, adding to grid', {
      name: artifact.identity.name,
      stage: artifact.stage,
      default_refs: artifact.metadata.default_refs,
    })
    // Map ArtifactRecord → CellTypeDefinition shape expected by handleCellTypeSelected.
    // default_refs are populated from artifact.metadata.default_refs (preserved by ArtifactLoader
    // from type.json) so instantiateCellByType can locate the basecell entry point.
    const cellTypeDef: CellTypeDefinition = {
      name: artifact.artifact_id,
      id: artifact.artifact_id,
      description: artifact.identity.description,
      version: artifact.version,
      icon: artifact.identity.icon ?? undefined,
      can_render_dynamically: true,
      stage: artifact.stage,
      default_refs: artifact.metadata.default_refs,
    }
    try {
      await handleCellTypeSelected(cellTypeDef)
    } catch (err: any) {
      log.error('[App] Failed to add selected artifact from explorer', {
        name: artifact.identity.name,
        error: err?.message,
      })
    } finally {
      explorerStore.clearSelection()
    }
  },
)

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

// ── Persisted Cell Runtime (Phase 5) ──────────────────────────────────────────

/**
 * Delete a persisted cell from the modal list after deleting from MongoDB.
 * Called from LoadCellModal @delete-cell event.
 */
async function handleDeleteFromModal(runtimeId: string): Promise<void> {
  log.info('[App] handleDeleteFromModal', { runtimeId })
  // Reuse existing handler — it will delete from MongoDB and remove from grid
  await handleDeletePersistedCell(runtimeId, '')
  // Also remove from modal's local list so it disappears immediately
  loadableCells.value = loadableCells.value.filter(c => c._id !== runtimeId)
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
      // Ensure cell types are loaded in the explorer store for lookup
      let knownTypes = explorerStore.availableCellTypes
      if (knownTypes.length === 0) {
        await explorerStore.loadCellTypes()
        knownTypes = explorerStore.availableCellTypes
      }

      // Find the full CellTypeDefinition from the loaded list (or synthesize a minimal one)
      const knownType = knownTypes.find((t) => t.name === cellRef.type)
      const cellType: CellTypeDefinition = knownType
        ? (knownType as CellTypeDefinition)
        : {
            name: cellRef.type,
            id: cellRef.type,
            description: '',
            version: '1.0.0',
            can_render_dynamically: true,
          }
      // Pass initialization_data if the cell reference has persisted state
      const initialData = cellRef.initialization_data || undefined
      // Track runtimeId if the cell was previously persisted
      const runtimeId = cellRef.category === 'persistent' ? cellRef.cellId : undefined

      const cellInstance = await instantiateCellByType(cellRef.type, cellType)
      const viewSpec = await resolveViewSpec(cellInstance, cellRef.type, cellType, initialData, tempId)

      updateCell(tempId, {
        cellInstance,
        viewSpec,
        cellType,
        position: cellRef.position,
        isMinimized: cellRef.state?.isMinimized ?? false,
        isMaximized: cellRef.state?.isMaximized ?? false,
        isLoading: false,
        runtimeId,
        isPersisted: cellRef.category === 'persistent',
      })

      log.info('[App] Cell hydrated', { cellId: tempId, type: cellRef.type, isPersisted: cellRef.category === 'persistent' })
    } catch (err: any) {
      log.error('[App] Cell hydration failed', { type: cellRef.type, error: err?.message })
      updateCell(tempId, {
        isLoading: false,
        error: t('layout.persistence.hydrationError', { type: cellRef.type }),
      })
    }
  }

  // Force GridContainer remount so vue3-grid-layout-next picks up the saved positions
  gridKey.value++

  log.info('[App] Layout loaded', { layoutId, cellCount: cellRefs.length })
}

// ── Persisted Cell Runtime (Phase 5) ──────────────────────────────────────────

/**
 * Find a CellTypeDefinition by its UUID (id) from the explorer store.
 * This is used to resolve notebook_item_type_id from persisted cells back
 * to the CellTypeDefinition required by handleCellTypeSelected.
 */
function findCellTypeById(typeId: string): CellTypeDefinition | null {
  const known = explorerStore.availableCellTypes as CellTypeDefinition[]
  const result = known?.find(t => t.id === typeId) ?? null
  if (!result) {
    log.warn('[App] findCellTypeById: type not found', { typeId })
  }
  return result
}

/**
 * Load persisted cells from MongoDB and hydrate them into the grid.
 *
 * Called during workspace initialization (onMounted). If no persisted cells
 * exist, the workspace remains empty (normal behavior). Errors are logged
 * as warnings and do NOT block the workspace from loading.
 */
async function loadPersistedCells(): Promise<void> {
  log.info('[App] Loading persisted cells')

  try {
    const persistedCells = await cellRuntime.listCellRuntimes()

    if (persistedCells.length === 0) {
      log.info('[App] No persisted cells to load')
      return
    }

    log.info('[App] Found persisted cells', { count: persistedCells.length })

    // Ensure cell types are loaded for resolution
    if (explorerStore.availableCellTypes.length === 0) {
      await explorerStore.loadCellTypes()
    }

    // Hydrate each persisted cell — one failure does NOT abort the rest
    for (const persistedCell of persistedCells) {
      try {
        const cellTypeDef = findCellTypeById(persistedCell.notebook_item_type_id)

        if (!cellTypeDef) {
          log.warn('[App] Skipping persisted cell: unknown cell type', {
            notebookItemTypeId: persistedCell.notebook_item_type_id,
          })
          continue
        }

        const cellId = await handleCellTypeSelected(
          cellTypeDef,
          persistedCell.initial_data,
          { runtimeId: persistedCell._id, isPersisted: true },
        )

        if (cellId) {
          log.info('[App] Persisted cell hydrated', {
            cellId,
            runtimeId: persistedCell._id,
            cellType: cellTypeDef.name,
          })
        }
      } catch (err: any) {
        log.warn('[App] Failed to hydrate persisted cell', {
          error: err?.message,
          persistedCellId: persistedCell._id,
        })
      }
    }

    log.info('[App] Persisted cells loaded', { hydrated: persistedCells.length })
  } catch (err: any) {
    log.warn('[App] Failed to load persisted cells — workspace continues', {
      error: err?.message,
    })
    // Graceful degradation: workspace loads normally without persisted cells
  }
}

/**
 * Save the current state of a cell to MongoDB.
 *
 * - If the cell already has a runtimeId → update existing record
 * - If the cell has no runtimeId → create new persisted cell record
 *
 * @param cellId  GridCell UUID
 */
async function handleSaveCellState(cellId: string): Promise<void> {
  const cell = cells.value.find(c => c.cellId === cellId)
  if (!cell) {
    log.warn('[App] handleSaveCellState: cell not found', { cellId })
    showLoadError('Cell not found')
    return
  }

  const initialData = extractCellStateForRuntime(cell)

  if (cell.runtimeId) {
    // Update existing persisted cell
    log.info('[App] Updating persisted cell state', { cellId, runtimeId: cell.runtimeId })
    const success = await cellRuntime.updateCellRuntime(cell.runtimeId, initialData)
    if (success) {
      showSaveSuccessToast('Cell state saved ✅')
    } else {
      showLoadError('Failed to save cell state')
    }
  } else {
    // Create new persisted cell
    log.info('[App] Saving cell state as new persisted cell', { cellId })

    const notebookItemTypeId = cell.cellType?.id || ''
    if (!notebookItemTypeId) {
      log.warn('[App] Cannot save cell: no cellType.id available', { cellId })
      showLoadError('Cannot save: cell type ID missing')
      return
    }

    const result = await cellRuntime.saveCellRuntime(
      notebookItemTypeId,
      initialData,
      cell.cellType?.name || cell.cellTypeName,
    )

    if (result && (result._id || result.id)) {
      const runtimeId = result._id || result.id!
      updateCell(cellId, { runtimeId, isPersisted: true })
      showSaveSuccessToast('Cell state saved ✅')
      log.info('[App] Cell state saved as persisted', { cellId, runtimeId })
    } else {
      showLoadError('Failed to save cell state')
    }
  }
}

/**
 * Load a specific persisted cell into the grid by its PersistedCell record.
 *
 * @param persistedCell  The PersistedCell to load from MongoDB
 */
async function handleLoadPersistedCell(persistedCell: PersistedCell): Promise<void> {
  log.info('[App] Loading persisted cell', { persistedCellId: persistedCell._id })

  try {
    // Ensure cell types are loaded
    if (explorerStore.availableCellTypes.length === 0) {
      await explorerStore.loadCellTypes()
    }

    const cellTypeDef = findCellTypeById(persistedCell.notebook_item_type_id)
    if (!cellTypeDef) {
      showLoadError(`Cell type ${persistedCell.notebook_item_type_id} not found`)
      return
    }

    await handleCellTypeSelected(
      cellTypeDef,
      persistedCell.initial_data,
      { runtimeId: persistedCell._id, isPersisted: true },
    )

    showSaveSuccessToast('Persisted cell loaded ✅')
  } catch (err: any) {
    showLoadError(`Failed to load persisted cell: ${err?.message}`)
    log.error('[App] Failed to load persisted cell', {
      persistedCellId: persistedCell._id,
      error: err?.message,
    })
  }
}

/**
 * Delete a persisted cell from MongoDB and remove it from the grid.
 *
 * @param runtimeId    MongoDB _id of the persisted cell
 * @param cellId       GridCell UUID (to remove from grid)
 */
async function handleDeletePersistedCell(runtimeId: string, cellId: string): Promise<void> {
  log.info('[App] Deleting persisted cell', { runtimeId, cellId })

  const success = await cellRuntime.deleteCellRuntime(runtimeId)
  if (success) {
    removeCell(cellId)
    showSaveSuccessToast('Persisted cell deleted')
    log.info('[App] Persisted cell deleted', { runtimeId, cellId })
  } else {
    showLoadError('Failed to delete persisted cell')
  }
}

/**
 * Extract the serializable state from a GridCell for persistence.
 *
 * Priority order:
 * 1. BaseCell.getState() — standardized serialization (content_ids only, no binary)
 * 2. View Bridge providers — current reactive content_ids from View.vue
 * 3. GridCell-level fields (fallback)
 *
 * Binary/base64 data is NEVER persisted in MongoDB (Redis Magro architecture).
 * Only lightweight content references (~200 bytes) are stored.
 */
function extractCellStateForRuntime(cell: GridCell): Record<string, any> {
  const state: Record<string, any> = {}

  if (!cell.cellInstance) return state

  // Priority 1: Use BaseCell.getState() for standardized serialization
  if (typeof cell.cellInstance.getState === 'function') {
    const baseState = cell.cellInstance.getState()
    Object.assign(state, baseState)
  } else {
    // Legacy fallback: manual field extraction
    const stateFields = [
      'status', 'jobId', 'content_id', 'input_content_id',
      'error', 'progress', 'isGenerating', 'generatedMesh',
      'inputImage', 'outputData',
    ]
    for (const field of stateFields) {
      if (field in cell.cellInstance) {
        // Skip binary/base64 data
        if (typeof cell.cellInstance[field] === 'string') {
          const val = cell.cellInstance[field] as string
          if (val.startsWith('data:') || val.startsWith('blob:')) continue
        }
        state[field] = cell.cellInstance[field]
      }
    }
  }

  // Priority 2: Merge View Bridge content_ids from View.vue's reactive state
  if (cell.cellId && stateProviders.has(cell.cellId)) {
    const contentIds = stateProviders.get(cell.cellId)!()
    Object.assign(state, contentIds)
  }

  // Also include GridCell-level error
  if (cell.error) state._gridError = cell.error

  return state
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(() => {
  // Defer persistence init until workspace is ready (session token available).
  // Cell types are loaded lazily by the explorer store when the picker mounts.
  if (store.status === 'ready') {
    initPersistence()
    // 🚨 DEBUG: Pre-load cell-type artifacts so cellFactory lookups work
    explorerStore.loadCellTypes().catch((err: any) => {
      console.warn('[App] Could not pre-load cell-type artifacts:', err?.message)
    })
  } else {
    const stopWatch = watch(
      () => store.status,
      (status) => {
        if (status === 'ready') {
          stopWatch()
          initPersistence()
          // 🚨 DEBUG: Pre-load cell-type artifacts so cellFactory lookups work
          explorerStore.loadCellTypes().catch((err: any) => {
            console.warn('[App] Could not pre-load cell-type artifacts:', err?.message)
          })
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
  // Load persisted cells from MongoDB (graceful: warns if fails, never blocks)
  loadPersistedCells()
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
