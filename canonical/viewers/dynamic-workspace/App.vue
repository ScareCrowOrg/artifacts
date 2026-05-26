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
import { useAutoSave } from './composables/useAutoSave'
import { useAutoLoadCellI18n } from './composables/useAutoLoadCellI18n'
import { useThemeSync } from '#artifacts/shared/composables/useThemeSync'
import GridContainer from './components/GridContainer.vue'
import FooterWindowManager from './components/FooterWindowManager.vue'
import SaveLayoutBookModal from './components/SaveLayoutBookModal.vue'
import Toolbar from './components/Toolbar.vue'
import { createLogger } from '@/utils/logger'
import { CELL_FACTORY_KEY, type CellFactory } from '#canonical/shared/cellFactory'
import { useArtifactsExplorerStore } from '#canonical/cell_types/artifacts-explorer-cell/frontend/store'
import type { ExplorerArtifact } from '#canonical/cell_types/artifacts-explorer-cell/frontend/store'
import type { CellTypeDefinition, LayoutBook } from './types'

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
): Promise<void> {
  log.info('[App] handleCellTypeSelected', { cellTypeName: cellType.name })

  const cellId = addCell(cellType.name, cellType)

  try {
    const cellInstance = await instantiateCellByType(cellType.name, cellType)
    const viewSpec = await resolveViewSpec(cellInstance, cellType.name, cellType, initialData, cellId)
    updateCell(cellId, { cellInstance, viewSpec, isLoading: false })
    log.info('[App] Cell ready', { cellId, cellTypeName: cellType.name })
  } catch (err: any) {
    const errorMsg = err?.message || 'Failed to load cell'
    updateCell(cellId, { isLoading: false, error: errorMsg })
    log.error('[App] Cell loading failed', { cellId, error: errorMsg })
  }
}

/**
 * Show the artifacts-explorer-cell in picker mode.
 * Called when FooterWindowManager emits 'show-artifacts-explorer'.
 *
 * Guards against duplicate instances: if the explorer is already in the grid, does nothing.
 */
async function handleShowArtifactsExplorer(): Promise<void> {
  const existing = cells.value.find((c) => c.cellTypeName === EXPLORER_CELL_TYPE_NAME)
  if (existing) {
    log.info('[App] artifacts-explorer-cell already in grid, skipping', { cellId: existing.cellId })
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

  log.info('[App] Instantiating artifacts-explorer-cell in picker mode')
  await handleCellTypeSelected(explorerType)
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

// ── Explorer store watcher (Phase 4 → Phase 2 upgrade) ───────────────────────
// When the user clicks a frontend-orchestrated artifact in the explorer,
// explorerStore.selectedArtifact is set. This watcher reacts and adds it to the grid.
// Guard: only orchestrator === 'frontend' artifacts are instantiated as cells.
watch(
  () => explorerStore.selectedArtifact,
  async (artifact: ExplorerArtifact | null) => {
    if (!artifact) return
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
      const cellInstance = await instantiateCellByType(cellRef.type, cellType)
      const viewSpec = await resolveViewSpec(cellInstance, cellRef.type, cellType, undefined, tempId)

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

  // Force GridContainer remount so vue3-grid-layout-next picks up the saved positions
  gridKey.value++

  log.info('[App] Layout loaded', { layoutId, cellCount: cellRefs.length })
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
