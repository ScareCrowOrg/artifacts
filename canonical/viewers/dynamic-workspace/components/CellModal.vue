/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-03-05",
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-03-05",
 *   "source": "Adapted from cockpit-vue/src/components/layout/dynamic/CellModal.vue",
 *   "changes": "Props: cell (GridCell); no store/DynamicCellView dependency; simplified"
 * }
 */
<template>
  <teleport to="body">
    <transition name="modal-fade">
      <div
        v-if="isOpen"
        class="cell-modal-overlay fixed inset-0 z-[1000] flex items-center justify-center bg-black/50 backdrop-blur-sm"
        @click.self="handleClose"
      >
        <div
          class="cell-modal-container bg-white dark:bg-gray-900 rounded-lg shadow-2xl flex flex-col max-w-6xl max-h-[90vh] w-[90vw]"
          @click.stop
        >
          <!-- Header -->
          <div class="flex items-center justify-between px-4 py-3 bg-blue-50 dark:bg-blue-900/20 border-b border-gray-200 dark:border-gray-700 rounded-t-lg">
            <h2 class="text-lg font-semibold text-gray-900 dark:text-white">
              {{ cell?.cellType?.name || cell?.cellTypeName || 'Cell' }}
            </h2>
            <button
              class="p-1 rounded hover:bg-red-500 hover:text-white transition-colors"
              :title="$t('common.close')"
              :aria-label="$t('common.close')"
              @click="handleClose"
            >
              <span class="text-xl">✕</span>
            </button>
          </div>

          <!-- Content: render cell viewSpec if available -->
          <div class="cell-modal-content flex-1 overflow-auto p-4">
            <div v-if="!cell" class="text-center text-gray-400 py-8">
              No cell selected
            </div>
            <div v-else-if="cell.isLoading" class="flex items-center justify-center py-8">
              <div class="text-center">
                <div class="spinner mb-2"></div>
                <p class="text-sm text-gray-400">Loading…</p>
              </div>
            </div>
            <div v-else-if="cell.error" class="text-red-500 text-center py-8">
              {{ cell.error }}
            </div>
            <component
              v-else-if="cell.viewSpec"
              :is="cell.viewSpec.component"
              v-bind="cell.viewSpec.props"
            />
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup lang="ts">
/**
 * @file CellModal.vue
 * @description Modal wrapper for displaying a cell in an isolated overlay.
 *
 * Adapted from cockpit-vue v1 CellModal:
 * - Props: isOpen (bool), cell (GridCell | null)
 * - Events: @close
 * - Removed: modalsStore, DynamicCellView dependency
 * - Preserved: modal overlay, transitions, keyboard close (Escape)
 */

import { onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { createLogger } from '@/utils/logger'
import type { GridCell } from '../types'

const log = createLogger('layout:cell-modal')
const { t } = useI18n()

// ── Props ─────────────────────────────────────────────────────────────────────
const props = defineProps<{
  isOpen: boolean
  cell: GridCell | null
}>()

// ── Emits ─────────────────────────────────────────────────────────────────────
const emit = defineEmits<{
  close: []
}>()

// ── Handlers ──────────────────────────────────────────────────────────────────
function handleClose(): void {
  log.debug('[CellModal] Close requested')
  emit('close')
}

function handleEscapeKey(event: KeyboardEvent): void {
  if (event.key === 'Escape' && props.isOpen) {
    handleClose()
  }
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(() => {
  document.addEventListener('keydown', handleEscapeKey)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleEscapeKey)
})
</script>

<style scoped>
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.3s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.cell-modal-content {
  scrollbar-width: thin;
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
