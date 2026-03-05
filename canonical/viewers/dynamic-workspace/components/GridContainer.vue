/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-03-05",
 *   "dark_mode_support": "full",
 *   "source": "UPGRADED — vue3-grid-layout-next interactive grid (drag-drop + resize)"
 * }
 */
<template>
  <div class="grid-container relative w-full h-full overflow-auto">
    <!-- Empty state -->
    <div
      v-if="cells.length === 0"
      class="empty-state flex items-center justify-center h-full min-h-[300px]"
    >
      <div class="text-center p-8 bg-gray-50 dark:bg-gray-800 rounded-xl shadow max-w-lg">
        <h2 class="text-2xl font-bold text-gray-800 dark:text-white mb-4">
          🚀 {{ $t('layout.dynamicWorkspace.title') }}
        </h2>
        <p class="text-gray-500 dark:text-gray-400 mb-2">
          {{ $t('layout.dynamicWorkspace.welcomeMessage') }}
        </p>
        <p class="text-sm text-gray-400 dark:text-gray-500">
          {{ $t('layout.dynamicWorkspace.clickAddCell', { button: '➕' }) }}
        </p>
      </div>
    </div>

    <!-- Interactive Grid layout (vue3-grid-layout-next) -->
    <GridLayout
      v-else
      :layout="gridLayout"
      :col-num="GRID_COLS"
      :row-height="ROW_HEIGHT_PX"
      :is-draggable="true"
      :is-resizable="true"
      :vertical-compact="false"
      :use-css-transforms="true"
      :prevent-collision="false"
      :margin="[8, 8]"
      class="p-4"
      @layout-updated="handleLayoutUpdated"
    >
      <GridItem
        v-for="item in gridLayout"
        :key="item.i"
        :x="item.x"
        :y="item.y"
        :w="item.w"
        :h="item.h"
        :i="item.i"
        :min-w="2"
        :min-h="2"
        :is-draggable="!item.static"
        :is-resizable="!item.static"
        drag-allow-from=".cell-drag-handle"
      >
        <CellItem
          v-if="getCellById(item.i)"
          :cell="getCellById(item.i)!"
          @remove="$emit('remove-cell', $event)"
          @minimize="$emit('minimize-cell', $event)"
          @maximize="$emit('maximize-cell', $event)"
        />
      </GridItem>
    </GridLayout>
  </div>
</template>

<script setup lang="ts">
/**
 * @file GridContainer.vue
 * @description Interactive grid wrapper for DynamicWorkspace v2.
 *
 * Upgraded from CSS Grid to vue3-grid-layout-next for drag-drop and resize support.
 * Drag is restricted to the cell header via drag-allow-from=".cell-drag-handle".
 * Layout updates call syncLayoutPositions() to persist positions in useGridLayout state.
 *
 * Props: cells — readonly GridCell[]
 * Events: @remove-cell(cellId), @minimize-cell(cellId), @maximize-cell(cellId)
 */

import { computed } from 'vue'
import { GridLayout, GridItem } from 'vue3-grid-layout-next'
import CellItem from './CellItem.vue'
import { useGridLayout } from '../composables/useGridLayout'
import type { GridCell, GridPosition } from '../types'

// ── Props ─────────────────────────────────────────────────────────────────────
const props = defineProps<{
  cells: readonly GridCell[]
}>()

// ── Emits ─────────────────────────────────────────────────────────────────────
defineEmits<{
  'remove-cell': [cellId: string]
  'minimize-cell': [cellId: string]
  'maximize-cell': [cellId: string]
}>()

// ── Grid Configuration ────────────────────────────────────────────────────────

const GRID_COLS = 12
const ROW_HEIGHT_PX = 50 // px per row unit
/** Height (in rows) for a minimized cell */
const MINIMIZED_HEIGHT = 1

// ── Types ─────────────────────────────────────────────────────────────────────

/** Layout item shape required by vue3-grid-layout-next */
interface GridLayoutItem {
  i: string
  x: number
  y: number
  w: number
  h: number
  static?: boolean
}

// ── Composable ────────────────────────────────────────────────────────────────

const { syncLayoutPositions } = useGridLayout()

// ── Layout Computation ────────────────────────────────────────────────────────

/**
 * Maps GridCell[] to the vue3-grid-layout-next layout format.
 * Minimized cells are locked (static=true, h=MINIMIZED_HEIGHT) to prevent
 * accidental drag/resize while collapsed.
 */
const gridLayout = computed<GridLayoutItem[]>(() =>
  props.cells.map(cell => ({
    i: cell.cellId,
    x: cell.position.x,
    y: cell.position.y,
    w: cell.position.w,
    h: cell.isMinimized ? MINIMIZED_HEIGHT : cell.position.h,
    static: cell.isMinimized,
  })),
)

/**
 * Build an index Map from cellId → GridCell for O(1) lookups in the template.
 * Recomputed only when props.cells changes.
 */
const cellIndex = computed<Map<string, GridCell>>(() => {
  const map = new Map<string, GridCell>()
  for (const cell of props.cells) {
    map.set(cell.cellId, cell)
  }
  return map
})

/**
 * Lookup helper: find a GridCell by its cellId.
 * Always defined in v-for context (cellId comes from gridLayout which is derived from cells).
 * Returns null when called outside a valid v-for iteration (safe guard).
 */
function getCellById(cellId: string): GridCell | null {
  return cellIndex.value.get(cellId) ?? null
}

// ── Event Handlers ────────────────────────────────────────────────────────────

/**
 * Called by GridLayout after any drag or resize completes.
 * Translates the layout array back to a cellId → GridPosition map and
 * syncs into useGridLayout reactive state (triggering auto-save watcher).
 *
 * Height preservation for minimized cells:
 * - Minimized cells are rendered as h=MINIMIZED_HEIGHT in the layout.
 * - We must NOT persist that visual-only height to cell.position.h —
 *   the original height must survive the minimize/restore cycle.
 * - For minimized cells, we always use cell.position.h (the original height)
 *   so that restoring the cell renders at the correct size.
 */
function handleLayoutUpdated(layout: GridLayoutItem[]) {
  const updates: Record<string, GridPosition> = {}
  for (const item of layout) {
    const cell = cellIndex.value.get(item.i)
    if (!cell) continue
    updates[item.i] = {
      x: item.x,
      y: item.y,
      w: item.w,
      // For minimized cells: preserve original height (layout reports h=1, but that
      // is only a visual placeholder — the real height lives in cell.position.h)
      h: cell.isMinimized ? cell.position.h : item.h,
    }
  }
  syncLayoutPositions(updates)
}
</script>

<style scoped>
.grid-container {
  background: transparent;
}

/* Smooth transitions for grid items during drag/resize */
:deep(.vue-grid-item) {
  transition: all 0.2s ease;
  touch-action: none;
}

:deep(.vue-grid-item.vue-draggable-dragging) {
  transition: none;
  z-index: 100;
  opacity: 0.85;
  user-select: none;
  -webkit-user-select: none;
}

:deep(.vue-grid-item.resizing) {
  opacity: 0.9;
}

/* Resize handle styling — visible by default, prominent on hover.
   Note: .vue-resizable-handle is rendered by vue3-grid-layout-next.
   The nwse-resize cursor from the library serves as the primary accessibility
   affordance for resize capability. */
:deep(.vue-resizable-handle) {
  opacity: 0.6;
  border-radius: 2px;
  background: rgba(var(--color-primary-rgb) / 0.25);
  width: 16px !important;
  height: 16px !important;
}

:deep(.vue-resizable-handle::after) {
  content: "⋰";
  font-size: 10px;
  line-height: 16px;
  display: block;
  text-align: center;
  color: rgba(var(--color-primary-rgb) / 0.8);
  aria-hidden: true; /* decorative — resize affordance is provided by cursor:nwse-resize */
}

:deep(.vue-resizable-handle:hover) {
  opacity: 1;
  background: rgba(var(--color-primary-rgb) / 0.45);
}

/* Cell content area: allow normal text selection and interactions */
:deep(.cell-content) {
  cursor: auto;
  user-select: text;
  -webkit-user-select: text;
}
</style>
