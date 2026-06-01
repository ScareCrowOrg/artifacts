<template>
  <div
    v-if="visible"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 dark:bg-black/70"
    @click.self="emit('close')"
  >
    <div
      class="bg-white dark:bg-gray-900 shadow-xl rounded-lg w-full max-w-2xl mx-4 overflow-hidden"
      @click.stop
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h2 class="text-xl font-semibold text-gray-900 dark:text-white">
          {{ t('layout.loadCellModal.title') }}
        </h2>
        <button
          class="text-2xl text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
          :title="t('common.close')"
          @click="emit('close')"
        >✕</button>
      </div>

      <!-- Body: Loading -->
      <div v-if="isLoading" class="flex flex-col items-center justify-center py-16 gap-3">
        <div class="spinner"></div>
        <p class="text-sm text-gray-500 dark:text-gray-400">{{ t('layout.loadCellModal.loading') }}</p>
      </div>

      <!-- Body: Empty -->
      <div v-else-if="filteredCells.length === 0" class="flex flex-col items-center justify-center py-16 gap-3">
        <span class="text-4xl">📂</span>
        <p class="text-sm text-gray-500 dark:text-gray-400">{{ t('layout.loadCellModal.empty') }}</p>
        <p v-if="cellTypeIdFilter" class="text-xs text-gray-400 dark:text-gray-500">
          {{ filterTypeName }}
        </p>
      </div>

      <!-- Body: Cell List -->
      <div v-else class="overflow-y-auto max-h-[60vh] p-4 space-y-2">
        <div
          v-for="cell in filteredCells"
          :key="cell._id"
          class="flex items-center justify-between p-3 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:shadow-sm transition-shadow"
        >
          <div class="flex items-center gap-3 min-w-0 flex-1">
            <span class="text-xl flex-shrink-0">{{ cellIcon(cell) }}</span>
            <div class="min-w-0">
              <p class="text-sm font-medium text-gray-900 dark:text-white truncate">
                {{ cell.title || cellTypeName(cell) || 'Untitled' }}
              </p>
              <p class="text-xs text-gray-500 dark:text-gray-400 truncate">
                {{ cellTypeName(cell) }}
                <span v-if="cell.created_at" class="ml-2">• {{ formatDate(cell.created_at) }}</span>
              </p>
            </div>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0 ml-2">
            <button
              class="px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors text-xs font-medium"
              @click="emit('load-cell', cell)"
            >{{ t('layout.loadCellModal.load') }}</button>
            <button
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
              :class="deleteConfirmId === cell._id
                ? 'bg-red-600 text-white animate-pulse'
                : 'border border-red-300 dark:border-red-700 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20'"
              :title="t('common.delete')"
              @click="handleDelete(cell._id)"
            >{{ deleteConfirmId === cell._id ? t('layout.loadCellModal.confirmDelete') : t('layout.loadCellModal.delete') }}</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * @file LoadCellModal.vue
 * @description Modal for listing and loading persisted cell states from MongoDB.
 *
 * Buffer Local Pattern (REACTIVITY_ISOLATION.md):
 * - Uses local refs for UI state, never props deeply nested
 * - Props are read-only; all mutations use local refs
 */

import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { PersistedCell } from '../composables/useCellRuntime'
import type { CellTypeDefinition } from '../types'

const { t } = useI18n()

const props = defineProps<{
  visible: boolean
  persistedCells: PersistedCell[]
  isLoading: boolean
  cellTypes: CellTypeDefinition[]
  cellTypeIdFilter: string | null
}>()

const emit = defineEmits<{
  close: []
  'load-cell': [cell: PersistedCell]
  'delete-cell': [runtimeId: string]
}>()

/** Filter displayed cells when triggered from a specific cell toolbar */
const filteredCells = computed(() => {
  if (!props.cellTypeIdFilter) return props.persistedCells
  return props.persistedCells.filter(c => c.notebook_item_type_id === props.cellTypeIdFilter)
})

/** Resolve the filter display name for the header */
const filterTypeName = computed(() => {
  if (!props.cellTypeIdFilter) return ''
  const t = props.cellTypes.find(x => x.id === props.cellTypeIdFilter)
  return t?.name || t?.id || ''
})

// Local state (Buffer Local Pattern)
const deleteConfirmId = ref<string | null>(null)

watch(() => props, () => { deleteConfirmId.value = null }, { deep: false })

function handleDelete(runtimeId: string): void {
  if (deleteConfirmId.value === runtimeId) {
    emit('delete-cell', runtimeId)
    deleteConfirmId.value = null
  } else {
    deleteConfirmId.value = runtimeId
    setTimeout(() => {
      if (deleteConfirmId.value === runtimeId) deleteConfirmId.value = null
    }, 3000)
  }
}

function cellTypeName(cell: PersistedCell): string {
  const t = props.cellTypes.find(x => x.id === cell.notebook_item_type_id)
  return t?.name || cell.notebook_item_type_id
}

function cellIcon(cell: PersistedCell): string {
  const t = props.cellTypes.find(x => x.id === cell.notebook_item_type_id)
  return t?.icon || '📦'
}

function formatDate(s: string): string {
  try { return new Date(s).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) }
  catch { return s }
}
</script>

<style scoped>
.spinner {
  width: 32px; height: 32px;
  border: 3px solid rgba(0, 0, 0, 0.1);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
