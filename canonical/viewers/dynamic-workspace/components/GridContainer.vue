/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-03-05",
 *   "dark_mode_support": "full",
 *   "source": "NEW — CSS Grid-based wrapper (vue3-grid-layout-next dependency added to package.json)"
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

    <!-- Grid layout -->
    <div
      v-else
      class="grid-layout p-4"
      :style="gridStyle"
    >
      <div
        v-for="cell in cells"
        :key="cell.cellId"
        class="grid-cell"
        :style="getCellStyle(cell)"
      >
        <CellItem
          :cell="cell"
          @remove="$emit('remove-cell', $event)"
          @minimize="$emit('minimize-cell', $event)"
          @maximize="$emit('maximize-cell', $event)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * @file GridContainer.vue
 * @description CSS-grid based wrapper for rendering cells in the dynamic workspace.
 *
 * Wraps a list of GridCell objects and renders each as a CellItem.
 * Uses CSS Grid for layout positioning (vue3-grid-layout-next added as future dependency).
 * Emits layout events for parent (App.vue) to react to.
 *
 * Props: cells — readonly GridCell[]
 * Events: @remove-cell(cellId), @minimize-cell(cellId), @maximize-cell(cellId)
 */

import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import CellItem from './CellItem.vue'
import type { GridCell } from '../types'

const { t } = useI18n()

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

// ── Grid Layout (12-column CSS Grid) ──────────────────────────────────────────

const GRID_COLS = 12
const ROW_HEIGHT_PX = 50 // px per row unit

const gridStyle = computed(() => ({
  display: 'grid',
  gridTemplateColumns: `repeat(${GRID_COLS}, 1fr)`,
  gridAutoRows: `${ROW_HEIGHT_PX}px`,
  gap: '8px',
  width: '100%',
}))

function getCellStyle(cell: GridCell) {
  const { x, y, w, h } = cell.position
  return {
    gridColumn: `${x + 1} / span ${w}`,
    gridRow: `${y + 1} / span ${h}`,
    minHeight: `${h * ROW_HEIGHT_PX}px`,
  }
}
</script>

<style scoped>
.grid-container {
  background: transparent;
}

.grid-cell {
  overflow: hidden;
}
</style>
