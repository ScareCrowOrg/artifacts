/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-03-05",
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-03-05",
 *   "logger_namespace": "layout:book-selector",
 *   "source": "Adapted from cockpit-vue/src/components/layout/dynamic/LayoutBookSelector.vue",
 *   "changes": "Props: layouts (LayoutBook[]); Events: @load-layout(id), @save-new; no store"
 * }
 */
<template>
  <div ref="root" class="layout-book-selector relative">
    <!-- Trigger Button -->
    <button
      ref="triggerButton"
      class="btn btn-sm flex items-center gap-2 px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 text-sm transition-colors"
      :title="t('layout.layoutBookSelector.tooltip')"
      @click="toggleDropdown"
    >
      <span class="text-base">📚</span>
      <span class="hidden sm:inline">{{ t('layout.layoutBookSelector.selectBook') }}</span>
      <span class="text-xs">{{ isOpen ? '▲' : '▼' }}</span>
    </button>

    <!-- Dropdown -->
    <div
      v-if="isOpen"
      ref="dropdown"
      class="dropdown-menu absolute bottom-full left-0 mb-2 w-72 bg-white dark:bg-gray-900 shadow-xl rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden z-50"
    >
      <!-- Save New Button -->
      <div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <button
          class="w-full flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
          @click="handleSaveNew"
        >
          <span>💾</span>
          <span>{{ t('layout.layoutBookSelector.saveCurrentLayout') }}</span>
        </button>
      </div>

      <!-- Loading -->
      <div v-if="isLoading" class="p-4 text-center text-gray-400">
        <div class="text-2xl mb-2 animate-spin inline-block">⏳</div>
        <div class="text-sm">{{ t('layout.layoutBookSelector.loading') }}</div>
      </div>

      <!-- Content -->
      <div v-else>
        <!-- No layouts -->
        <div v-if="layouts.length === 0" class="p-4 text-center text-gray-400">
          <div class="text-2xl mb-2">📚</div>
          <div class="text-sm">{{ t('layout.layoutBookSelector.noBooksYet') }}</div>
        </div>

        <!-- Layout list -->
        <div v-else class="max-h-64 overflow-y-auto">
          <div
            v-for="layout in layouts"
            :key="layout.id"
            class="px-4 py-3 border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors group"
            @click="handleLoadLayout(layout.id)"
          >
            <div class="flex items-center justify-between gap-2">
              <div class="flex-1 min-w-0">
                <h4 class="font-semibold text-gray-800 dark:text-white text-sm truncate">
                  {{ layout.name }}
                </h4>
                <p v-if="layout.description" class="text-xs text-gray-400 dark:text-gray-500 truncate mt-0.5">
                  {{ layout.description }}
                </p>
                <p class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                  {{ layout.cells?.length ?? 0 }} {{ t('layout.layoutBookSelector.cells') }}
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="px-4 py-2 border-t border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800">
          <p class="text-xs text-gray-400 text-center">
            {{ t('layout.layoutBookSelector.totalBooks', { count: layouts.length }) }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * @file LayoutBookSelector.vue
 * @description Dropdown for loading a saved workspace layout book.
 *
 * Adapted from cockpit-vue v1 LayoutBookSelector:
 * - Props: layouts (LayoutBook[]), isLoading (bool)
 * - Events: @load-layout(layoutId), @save-new
 * - Removed: useLayoutStore, useDynamicLayout dependencies
 * - Preserved: dropdown UI, dark mode, i18n, click-outside close
 */

import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { createLogger } from '@/utils/logger'
import type { LayoutBook } from '../types'

const log = createLogger('layout:book-selector')
const { t } = useI18n()

// ── Props ─────────────────────────────────────────────────────────────────────
const props = defineProps<{
  layouts: LayoutBook[]
  isLoading: boolean
}>()

// ── Emits ─────────────────────────────────────────────────────────────────────
const emit = defineEmits<{
  'load-layout': [layoutId: string]
  'save-new': []
}>()

// ── State ─────────────────────────────────────────────────────────────────────
const isOpen = ref(false)
const triggerButton = ref<HTMLElement | null>(null)
const dropdown = ref<HTMLElement | null>(null)
const root = ref<HTMLElement | null>(null)

// ── Handlers ──────────────────────────────────────────────────────────────────
function toggleDropdown(): void {
  isOpen.value = !isOpen.value
  log.debug('[LayoutBookSelector] Dropdown toggled', { isOpen: isOpen.value })
}

function closeDropdown(): void {
  isOpen.value = false
}

function handleClickOutside(event: MouseEvent): void {
  if (root.value && !root.value.contains(event.target as Node)) {
    closeDropdown()
  }
}

function handleSaveNew(): void {
  closeDropdown()
  emit('save-new')
}

function handleLoadLayout(layoutId: string): void {
  log.info('[LayoutBookSelector] Loading layout', { layoutId })
  closeDropdown()
  emit('load-layout', layoutId)
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.layout-book-selector {
  position: relative;
}

.dropdown-menu {
  animation: slideUp 0.2s ease-out;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
