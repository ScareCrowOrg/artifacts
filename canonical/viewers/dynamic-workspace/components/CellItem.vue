/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-03-05",
 *   "theme_compliance": 100,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-03-05",
 *   "i18n_coverage": 100,
 *   "logger_namespace": "layout:cell-wrapper",
 *   "source": "Adapted from cockpit-vue/src/components/layout/dynamic/CellWrapper.vue",
 *   "changes": "Props: GridCell; Events: @remove/@minimize/@maximize; removed store; renders viewSpec.component"
 * }
 */
<template>
  <div
    class="cell-item flex flex-col h-full bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg overflow-hidden"
    :class="{
      'cell-minimized': cell.isMinimized,
      'cell-maximized': cell.isMaximized,
    }"
  >
    <!-- Cell Toolbar (drag handle) -->
    <div
      class="cell-toolbar cell-drag-handle flex items-center justify-between px-3 py-2 bg-blue-50 dark:bg-blue-900/20 border-b border-gray-200 dark:border-gray-700"
    >
      <!-- Left: Icon + Title -->
      <div class="cell-header flex items-center gap-2 flex-1 min-w-0">
        <span class="text-lg flex-shrink-0" :title="cell.cellTypeName">
          {{ cellIcon }}
        </span>
        <h3
          class="text-sm font-semibold truncate text-gray-900 dark:text-white"
          :title="cell.cellTypeName"
        >
          {{ cell.cellType?.name || cell.cellTypeName }}
        </h3>
        <!-- Status badge -->
        <span
          v-if="!cell.isLoading"
          class="text-xs px-1.5 py-0.5 rounded-full"
          :class="cell.isPersisted
            ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
            : 'bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500'"
          :title="cell.isPersisted ? t('layout.cellWrapper.persisted') : t('layout.cellWrapper.ephemeral')"
        >
          {{ cell.isPersisted ? '🟢' : '⚪' }}
        </span>

        <!-- Loading indicator -->
        <span
          v-if="cell.isLoading"
          class="text-xs text-gray-400 dark:text-gray-500 animate-pulse"
        >⏳</span>
      </div>

      <!-- Right: Action Buttons -->
      <div class="cell-actions flex items-center gap-1">
        <!-- Save -->
        <button
          class="btn-icon hover:text-blue-500"
          :title="t('layout.cellWrapper.save')"
          @click.stop="$emit('save', cell.cellId)"
        >
          <span class="text-sm">💾</span>
        </button>

        <!-- Delete persisted (only if isPersisted) -->
        <button
          v-if="cell.isPersisted"
          class="btn-icon hover:bg-red-500 hover:text-white transition-colors"
          :title="t('layout.cellWrapper.deletePersisted')"
          @click.stop="confirmAndDelete"
        >
          <span class="text-sm">🗑️</span>
        </button>

        <!-- Minimize -->
        <button
          class="btn-icon"
          :title="t('layout.cellWrapper.minimize')"
          :aria-label="t('layout.cellWrapper.minimizeCell')"
          @click.stop="$emit('minimize', cell.cellId)"
        >
          <span class="text-sm">−</span>
        </button>

        <!-- Maximize / Restore -->
        <button
          class="btn-icon"
          :title="cell.isMaximized ? t('layout.cellWrapper.restore') : t('layout.cellWrapper.maximize')"
          :aria-label="cell.isMaximized ? t('layout.cellWrapper.restoreCell') : t('layout.cellWrapper.maximizeCell')"
          @click.stop="$emit('maximize', cell.cellId)"
        >
          <span class="text-sm">{{ cell.isMaximized ? '❐' : '□' }}</span>
        </button>

        <!-- Close -->
        <button
          class="btn-icon hover:bg-red-500 hover:text-white transition-colors"
          :title="t('layout.cellWrapper.close')"
          :aria-label="t('layout.cellWrapper.closeCell')"
          @click.stop="$emit('remove', cell.cellId)"
        >
          <span class="text-sm">✕</span>
        </button>
      </div>
    </div>

    <!-- Cell Content Area -->
    <div v-if="!cell.isMinimized" class="cell-content flex-1 overflow-auto">
      <!-- Loading State -->
      <div v-if="cell.isLoading" class="flex items-center justify-center h-full py-8">
        <div class="text-center">
          <div class="spinner mb-2"></div>
          <p class="text-sm text-gray-500 dark:text-gray-400">
            {{ t('layout.cellWrapper.loading', { title: cell.cellTypeName }) }}
          </p>
        </div>
      </div>

      <!-- Error State -->
      <div v-else-if="cell.error" class="flex items-center justify-center h-full py-8">
        <div class="text-center text-red-500">
          <span class="text-4xl mb-2 block">⚠️</span>
          <p class="font-semibold">{{ t('layout.cellWrapper.errorLoading') }}</p>
          <p class="text-sm mt-1 text-gray-500">{{ cell.error }}</p>
        </div>
      </div>

      <!-- Cell View: rendered via ViewSpec — component + props from cellInstance.show() -->
      <component
        v-else-if="cell.viewSpec"
        :is="cell.viewSpec.component"
        v-bind="cell.viewSpec.props"
      />
    </div>

    <!-- Minimized Placeholder -->
    <div
      v-else
      class="cell-minimized-placeholder flex items-center justify-center gap-2 py-1 text-gray-400 dark:text-gray-500 text-xs italic cursor-pointer hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
      :title="cell.cellTypeName"
      @click="$emit('minimize', cell.cellId)"
    >
      <span>{{ cellIcon }}</span>
      <span class="font-medium">{{ cell.cellType?.name || cell.cellTypeName }}</span>
      <span class="text-blue-500 dark:text-blue-400">
        {{ t('layout.cellWrapper.minimizedClickToRestore') }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * @file CellItem.vue
 * @description Cell wrapper component for DynamicWorkspace v2.
 *
 * Adapted from cockpit-vue v1 CellWrapper:
 * - Props: cell (GridCell) — single prop containing all cell state
 * - Events: @remove(cellId), @minimize(cellId), @maximize(cellId)
 * - Renders: toolbar + <component :is="viewSpec.component" v-bind="viewSpec.props" />
 * - Preserved: toolbar structure, dark mode, i18n, accessibility, loading/error states
 */

import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { createLogger } from '@/utils/logger'
import type { GridCell } from '../types'

const log = createLogger('layout:cell-wrapper')
const { t } = useI18n()

// ── Props ─────────────────────────────────────────────────────────────────────
const props = defineProps<{
  cell: GridCell
}>()

// ── Emits ─────────────────────────────────────────────────────────────────────
const emit = defineEmits<{
  remove: [cellId: string]
  minimize: [cellId: string]
  maximize: [cellId: string]
  save: [cellId: string]
  'delete-persisted': [{ runtimeId?: string; cellId: string }]
}>()

// ── Handlers ─────────────────────────────────────────────────────────────────
async function confirmAndDelete(): Promise<void> {
  if (window.confirm(t('layout.cellWrapper.confirmDelete'))) {
    emit('delete-persisted', { runtimeId: props.cell.runtimeId, cellId: props.cell.cellId })
  }
}

// ── Computed ──────────────────────────────────────────────────────────────────
const cellIcon = computed(() => {
  if (props.cell.cellType?.icon) return props.cell.cellType.icon

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
  return iconMap[props.cell.cellTypeName] || '📦'
})
</script>

<style scoped>
.cell-item {
  transition: box-shadow 0.2s ease;
}

.cell-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.cell-maximized {
  position: fixed;
  inset: 0;
  z-index: 100;
  border-radius: 0;
}

.cell-toolbar {
  user-select: none;
  -webkit-user-select: none;
}

.cell-drag-handle {
  cursor: grab;
}

.cell-drag-handle:active {
  cursor: grabbing;
}

.btn-icon {
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  background: transparent;
  border: none;
  cursor: pointer;
  color: inherit;
  transition: background-color 0.2s ease;
}

.btn-icon:hover {
  background-color: rgba(0, 0, 0, 0.1);
}

.btn-icon:active {
  transform: scale(0.95);
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
  to { transform: rotate(360deg); }
}
</style>
