/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-03-05",
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-03-05",
 *   "i18n_coverage": 100,
 *   "logger_namespace": "layout:footer-manager",
 *   "source": "Adapted from cockpit-vue/src/components/layout/dynamic/FooterWindowManager.vue",
 *   "changes": "Removed Pinia store injection; emits @show-add-modal; simplified to core Add Cell button"
 * }
 */
<template>
  <footer
    class="footer-window-manager fixed bottom-0 left-0 right-0 z-40 bg-white dark:bg-gray-900 shadow-lg border-t border-gray-200 dark:border-gray-700"
  >
    <div class="footer-content px-4 py-3">
      <div class="flex items-center justify-between gap-4">
        <!-- Left: Add Cell Button -->
        <div class="footer-left flex items-center gap-2">
          <button
            class="btn btn-primary flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors text-sm font-medium"
            :disabled="isMaxCellsReached"
            :title="isMaxCellsReached
              ? $t('layout.footerWindowManager.maxCellsReached', { max: maxCells })
              : $t('layout.footerWindowManager.addNewCell')"
            @click="handleAddCell"
          >
            <span class="text-base">➕</span>
            <span class="hidden sm:inline">{{ $t('layout.footerWindowManager.addCell') }}</span>
          </button>

          <!-- Cell count -->
          <span class="text-xs text-gray-400 dark:text-gray-500">
            {{ $t('layout.footerWindowManager.cellsCount', { count: cellCount, max: maxCells }) }}
          </span>
        </div>

        <!-- Center: Open cell tabs -->
        <div class="footer-center flex-1 flex items-center gap-2 overflow-x-auto">
          <div
            v-if="cellTabs.length === 0"
            class="text-sm text-gray-400 dark:text-gray-500 italic"
          >
            {{ $t('layout.footerWindowManager.noCellsOpen') }}
          </div>
          <div
            v-for="tab in cellTabs"
            :key="tab.cellId"
            class="cell-tab flex items-center gap-1.5 px-3 py-1 rounded-lg text-sm bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 whitespace-nowrap"
          >
            <span>{{ tab.icon }}</span>
            <span class="truncate max-w-[100px]">{{ tab.name }}</span>
            <button
              class="ml-1 text-xs opacity-60 hover:opacity-100 transition-opacity"
              :title="$t('layout.footerWindowManager.closeCell', { title: tab.name })"
              @click="$emit('close-cell', tab.cellId)"
            >✕</button>
          </div>
        </div>

        <!-- Right: Workspace status -->
        <div class="footer-right flex items-center gap-2 text-xs text-gray-400 dark:text-gray-500">
          <span class="hidden md:inline">DynamicWorkspace v2</span>
        </div>
      </div>
    </div>
  </footer>
</template>

<script setup lang="ts">
/**
 * @file FooterWindowManager.vue
 * @description Footer for DynamicWorkspace v2 — shows Add Cell button and open cell tabs.
 *
 * Adapted from cockpit-vue v1 FooterWindowManager:
 * - Props: cellCount, maxCells, cellTabs[]
 * - Events: @show-add-modal, @close-cell(cellId)
 * - Removed: store injections, layout book selector (Phase 3), admin menu
 * - Preserved: dark mode, i18n, Add Cell button, cell tabs
 */

import { useI18n } from 'vue-i18n'
import { createLogger } from '@/utils/logger'

const log = createLogger('layout:footer-manager')
const { t } = useI18n()

// ── Props ─────────────────────────────────────────────────────────────────────
const props = defineProps<{
  cellCount: number
  maxCells: number
  cellTabs: Array<{ cellId: string; name: string; icon: string }>
}>()

// ── Emits ─────────────────────────────────────────────────────────────────────
const emit = defineEmits<{
  'show-add-modal': []
  'close-cell': [cellId: string]
}>()

// ── Computed ──────────────────────────────────────────────────────────────────
const isMaxCellsReached = props.cellCount >= props.maxCells

// ── Handlers ──────────────────────────────────────────────────────────────────
function handleAddCell(): void {
  log.debug('[FooterWindowManager] Add Cell button clicked')
  emit('show-add-modal')
}
</script>

<style scoped>
.footer-window-manager {
  max-height: 80px;
}

.cell-tab {
  min-width: fit-content;
}

.footer-center::-webkit-scrollbar {
  height: 4px;
}

.footer-center::-webkit-scrollbar-thumb {
  background: #3b82f6;
  border-radius: 2px;
}
</style>
