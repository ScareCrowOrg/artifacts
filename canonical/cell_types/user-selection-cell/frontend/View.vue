/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-05-09",
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "logger_namespace": "cell:user-selection:view",
 *   "validation_status": "phase1",
 *   "i18n_validated_date": "2026-05-13",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <Teleport to="body">
    <div
      v-if="store.isOpen"
      class="user-selection-overlay fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      :aria-label="store.title"
    >
      <!-- Backdrop -->
      <div
        class="absolute inset-0 bg-black/60 dark:bg-black/75"
        @click="handleCancel"
      />

      <!-- Modal Panel -->
      <div
        class="relative z-10 w-full max-w-md mx-4 bg-white dark:bg-gray-900 rounded-xl shadow-2xl flex flex-col max-h-[80vh]"
      >
        <!-- Header -->
        <div class="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 class="text-base font-semibold text-gray-900 dark:text-white">
            👤 {{ store.title }}
          </h2>
          <button
            class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
            aria-label="Cancel selection"
            @click="handleCancel"
          >
            ✕
          </button>
        </div>

        <!-- Search Field -->
        <div class="px-5 py-3 border-b border-gray-200 dark:border-gray-700">
          <input
            v-model="store.searchQuery"
            type="text"
            :placeholder="$t('artifacts.userSelectionCell.searchPlaceholder')"
            class="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            aria-label="Search users"
            @input="handleSearch"
          />
        </div>

        <!-- Loading State -->
        <div
          v-if="store.isLoading"
          class="flex-1 flex items-center justify-center py-10"
        >
          <div class="text-center">
            <div class="spinner mb-2" />
            <p class="text-sm text-gray-500 dark:text-gray-400">{{ $t('artifacts.userSelectionCell.loadingUsers') }}</p>
          </div>
        </div>

        <!-- Error State -->
        <div
          v-else-if="store.error"
          class="flex-1 flex items-center justify-center px-5 py-10"
        >
          <div class="text-center">
            <span class="text-3xl mb-2 block">⚠️</span>
            <p class="text-red-500 dark:text-red-400 font-semibold mb-1 text-sm">
              {{ $t('artifacts.userSelectionCell.failedToLoad') }}
            </p>
            <p class="text-xs text-gray-500 dark:text-gray-400">
              {{ store.error }}
            </p>
          </div>
        </div>

        <!-- Empty State -->
        <div
          v-else-if="store.users.length === 0"
          class="flex-1 flex items-center justify-center py-10 px-5"
        >
          <div class="text-center">
            <span class="text-3xl mb-2 block">👤</span>
            <p class="text-sm text-gray-500 dark:text-gray-400">{{ $t('artifacts.userSelectionCell.noUsersFound') }}</p>
          </div>
        </div>

        <!-- User List -->
        <div
          v-else
          class="flex-1 overflow-y-auto divide-y divide-gray-100 dark:divide-gray-700"
        >
          <button
            v-for="user in store.users"
            :key="user.id"
            class="w-full flex items-center gap-3 px-5 py-3 text-left hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500"
            :aria-label="`Select user ${user.name}`"
            @click="handleSelectUser(user)"
          >
            <!-- Avatar: real image or initial fallback -->
            <div class="w-8 h-8 rounded-full flex-shrink-0 overflow-hidden">
              <img
                v-if="user.avatar_url"
                :src="user.avatar_url"
                :alt="user.name"
                class="w-full h-full object-cover"
              />
              <div
                v-else
                class="w-full h-8 bg-blue-100 dark:bg-blue-900 flex items-center justify-center text-blue-700 dark:text-blue-300 font-semibold text-sm"
              >
                {{ avatarInitial(user.name) }}
              </div>
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium text-gray-900 dark:text-white truncate">
                {{ user.name }}
              </p>
            </div>
          </button>
        </div>

        <!-- Footer -->
        <div class="px-5 py-3 border-t border-gray-200 dark:border-gray-700 flex justify-end">
          <button
            class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors"
            @click="handleCancel"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * @file View.vue
 * @description user-selection-cell — Modal overlay for selecting a ScareVerse user.
 *
 * This component is mounted via <Teleport to="body"> from the parent cell's View.
 * It communicates with UserSelectionCell via the userSelection Pinia store:
 * - store.open() → overlay opens, users load
 * - handleSelectUser(user) → store.selectUser(user) → Promise in UserSelectionCell resolves
 * - handleCancel() → store.cancel() → Promise resolves with null
 *
 * The component is self-contained: no props are needed.
 * It reads all state from the Pinia store.
 */

import { ref } from 'vue'
import { createLogger } from '@/utils/logger'
import { useUserSelectionStore } from './store'
import type { SelectableUser } from './store'

const log = createLogger('cell:user-selection:view')
const store = useUserSelectionStore()

// ── Helpers ──────────────────────────────────────────────────────────────────

function avatarInitial(name: string): string {
  return (name && name.trim()) ? name.trim().charAt(0).toUpperCase() : '?'
}

// ── Search debounce ───────────────────────────────────────────────────────────

const _searchTimer = ref<ReturnType<typeof setTimeout> | null>(null)

function handleSearch(): void {
  if (_searchTimer.value !== null) clearTimeout(_searchTimer.value)
  _searchTimer.value = setTimeout(() => {
    store.loadUsers(store.searchQuery || undefined)
  }, 300)
}

// ── Handlers ─────────────────────────────────────────────────────────────────

function handleSelectUser(user: SelectableUser): void {
  log.info('[UserSelectionView] User selected', { name: user.name, id: user.id })
  store.selectUser(user)
}

function handleCancel(): void {
  log.debug('[UserSelectionView] Selection cancelled by user')
  store.cancel()
}
</script>

<style scoped>
.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid rgba(0, 0, 0, 0.1);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
