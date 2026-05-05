/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-03-05",
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-03-05",
 *   "source": "Adapted from cockpit-vue/src/components/layout/dynamic/SaveLayoutBookModal.vue",
 *   "changes": "Props: isOpen, cells[]; Events: @save-layout(name,desc), @cancel; no store"
 * }
 */
<template>
  <div
    v-if="isOpen"
    class="modal-overlay fixed inset-0 z-50 flex items-center justify-center bg-black/50 dark:bg-black/70"
    @click.self="handleClose"
  >
    <div
      class="modal-content bg-white dark:bg-gray-900 shadow-xl rounded-lg w-full max-w-lg mx-4 overflow-hidden"
      @click.stop
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <h2 class="text-xl font-semibold text-gray-900 dark:text-white">
          {{ t('layout.saveLayoutBookModal.title') }}
        </h2>
        <button
          class="text-2xl text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
          :title="t('layout.saveLayoutBookModal.close')"
          @click="handleClose"
        >✕</button>
      </div>

      <!-- Body -->
      <div class="px-6 py-4 space-y-4">
        <!-- Name -->
        <div>
          <label for="layout-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {{ t('layout.saveLayoutBookModal.nameLabel') }}
            <span class="text-red-500">*</span>
          </label>
          <input
            id="layout-name"
            v-model="formData.name"
            type="text"
            maxlength="100"
            class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            :class="{ 'border-red-500': nameError }"
            :placeholder="t('layout.saveLayoutBookModal.namePlaceholder')"
            @input="nameError = null"
          />
          <p v-if="nameError" class="text-sm text-red-500 mt-1">{{ nameError }}</p>
        </div>

        <!-- Description -->
        <div>
          <label for="layout-description" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {{ t('layout.saveLayoutBookModal.descriptionLabel') }}
          </label>
          <textarea
            id="layout-description"
            v-model="formData.description"
            rows="3"
            maxlength="500"
            class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            :placeholder="t('layout.saveLayoutBookModal.descriptionPlaceholder')"
          />
        </div>

        <!-- Cell summary -->
        <div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
          <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
            {{ t('layout.saveLayoutBookModal.cellPreviewTitle') }}
          </h3>
          <p class="text-sm text-gray-500 dark:text-gray-400">
            {{ t('layout.saveLayoutBookModal.totalCells') }}: <strong>{{ cells.length }}</strong>
          </p>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-6 py-4 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-2">
        <button
          class="px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors text-sm"
          :disabled="isSaving"
          @click="handleClose"
        >
          {{ t('layout.saveLayoutBookModal.cancel') }}
        </button>
        <button
          class="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
          :disabled="isSaving || !formData.name.trim()"
          @click="handleSave"
        >
          {{ isSaving ? t('layout.saveLayoutBookModal.saving') : t('layout.saveLayoutBookModal.save') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * @file SaveLayoutBookModal.vue
 * @description Modal for saving the current grid layout as a named "layout book".
 *
 * Adapted from cockpit-vue v1 SaveLayoutBookModal:
 * - Props: isOpen (bool), cells (GridCell[])
 * - Events: @save-layout(name, description), @cancel
 * - Removed: useLayoutStore dependency
 * - Preserved: form structure, validation, dark mode, i18n
 */

import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { createLogger } from '@/utils/logger'
import type { GridCell } from '../types'

const log = createLogger('layout:save-layout-modal')
const { t } = useI18n()

// ── Props ─────────────────────────────────────────────────────────────────────
const props = defineProps<{
  isOpen: boolean
  cells: GridCell[]
}>()

// ── Emits ─────────────────────────────────────────────────────────────────────
const emit = defineEmits<{
  'save-layout': [name: string, description: string]
  cancel: []
}>()

// ── State ─────────────────────────────────────────────────────────────────────
const formData = ref({ name: '', description: '' })
const nameError = ref<string | null>(null)
const isSaving = ref(false)

// ── Watchers ──────────────────────────────────────────────────────────────────
watch(() => props.isOpen, isOpen => {
  if (isOpen) {
    formData.value = { name: '', description: '' }
    nameError.value = null
    isSaving.value = false
  }
})

// ── Handlers ──────────────────────────────────────────────────────────────────
function handleClose(): void {
  if (!isSaving.value) {
    emit('cancel')
  }
}

async function handleSave(): Promise<void> {
  nameError.value = null
  if (!formData.value.name.trim()) {
    nameError.value = t('layout.saveLayoutBookModal.errorNameRequired')
    return
  }
  isSaving.value = true
  try {
    log.info('[SaveLayoutBookModal] Saving layout', { name: formData.value.name })
    emit('save-layout', formData.value.name.trim(), formData.value.description.trim())
  } finally {
    isSaving.value = false
  }
}
</script>

<style scoped>
.modal-overlay {
  animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.modal-content {
  animation: slideUp 0.3s ease-out;
}

@keyframes slideUp {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
</style>
