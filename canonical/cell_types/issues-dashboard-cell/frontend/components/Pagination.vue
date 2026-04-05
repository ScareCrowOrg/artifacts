<!-- eslint-disable vue/multi-word-component-names -->
/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-12",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "dark_mode_support": "full",
 *   "theme_issues_found": 0,
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-13",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
/**
 * Pagination - Helper component for pagination controls
 * Single-word name acceptable for utility components
 */
<template>
  <div
    class="flex items-center justify-between px-6 py-4 bg-surface dark:bg-gray-900 border-t border-border dark:border-gray-700"
  >
    <!-- Page info -->
    <div class="text-sm text-text-secondary dark:text-text-secondary">
      {{ $t('issues.pagination.showing') }} <span class="font-semibold text-text-primary dark:text-text-primary">{{ startItem }}</span> {{ $t('issues.pagination.to') }}
      <span class="font-semibold text-text-primary dark:text-text-primary">{{ endItem }}</span> {{ $t('issues.pagination.of') }}
      <span class="font-semibold text-text-primary dark:text-text-primary">{{ store.totalItems }}</span> {{ $t('issues.pagination.items') }}
    </div>

    <!-- Pagination controls -->
    <div class="flex items-center gap-2">
      <!-- Previous button -->
      <button
        class="px-3 py-2 border border-border dark:border-gray-700 rounded text-sm bg-surface dark:bg-gray-800 hover:bg-surface-hover dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-text-primary dark:text-text-primary"
        :disabled="store.currentPage <= 1"
        :aria-label="$t('issues.pagination.previousPage')"
        @click="store.previousPage()"
      >
        ← {{ $t('issues.pagination.previous') }}
      </button>

      <!-- Page numbers -->
      <div class="flex gap-1">
        <button
          v-for="page in visiblePages"
          :key="page"
          class="min-w-[2.5rem] px-3 py-2 border rounded text-sm transition-colors"
          :class="
            page === store.currentPage
              ? 'bg-primary text-white dark:text-white border-primary font-semibold'
              : 'bg-surface dark:bg-gray-800 border-border dark:border-gray-700 hover:bg-surface-hover dark:hover:bg-gray-700 text-text-primary dark:text-text-primary'
          "
          :aria-label="$t('issues.pagination.goToPage', { page })"
          :aria-current="page === store.currentPage ? 'page' : undefined"
          @click="store.goToPage(page)"
        >
          {{ page }}
        </button>
      </div>

      <!-- Next button -->
      <button
        class="px-3 py-2 border border-border dark:border-gray-700 rounded text-sm bg-surface dark:bg-gray-800 hover:bg-surface-hover dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-text-primary dark:text-text-primary"
        :disabled="store.currentPage >= store.totalPages"
        :aria-label="$t('issues.pagination.nextPage')"
        @click="store.nextPage()"
      >
        {{ $t('issues.pagination.next') }} →
      </button>
    </div>
  </div>
</template>

<script setup>
/**
 * Pagination Component
 *
 * Displays pagination controls for navigating through paginated data.
 * Uses Pinia store directly for state management.
 * Shows current page, total pages, and provides navigation buttons.
 */
import { computed } from 'vue'
import { useIssuesStore } from '../stores/issuesStore'

const store = useIssuesStore()

/**
 * Calculate start item number for current page
 */
const startItem = computed(() => {
  if (store.totalItems === 0) return 0
  return (store.currentPage - 1) * store.itemsPerPage + 1
})

/**
 * Calculate end item number for current page
 */
const endItem = computed(() => {
  const end = store.currentPage * store.itemsPerPage
  return Math.min(end, store.totalItems)
})

/**
 * Calculate which page numbers to show
 * Shows up to 5 pages at a time with current page in the middle when possible
 */
const visiblePages = computed(() => {
  const pages = []
  const maxVisible = 5

  if (store.totalPages <= maxVisible) {
    // Show all pages if total is less than max
    for (let i = 1; i <= store.totalPages; i++) {
      pages.push(i)
    }
  } else {
    // Show subset of pages with current in middle
    let start = Math.max(1, store.currentPage - Math.floor(maxVisible / 2))
    let end = Math.min(store.totalPages, start + maxVisible - 1)

    // Adjust start if we're near the end
    if (end === store.totalPages) {
      start = Math.max(1, end - maxVisible + 1)
    }

    for (let i = start; i <= end; i++) {
      pages.push(i)
    }
  }

  return pages
})
</script>
