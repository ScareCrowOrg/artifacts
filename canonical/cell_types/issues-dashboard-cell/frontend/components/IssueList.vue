/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-13",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-13",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div class="overflow-y-auto border-r border-gray-300 dark:border-gray-700 flex-1">
    <div v-if="store.isLoading" class="p-8 text-center text-gray-600 dark:text-gray-400">
      {{ $t('issues.list.loading') }}
    </div>

    <div
      v-else-if="store.filteredIssues.length === 0"
      class="p-8 text-center text-gray-600 dark:text-gray-400"
    >
      {{ $t('issues.list.noCellsFound') }}
    </div>

    <div v-else>
      <IssueCard
        v-for="cell in store.filteredIssues"
        :key="cell.id"
        :cell="cell"
        :is-selected="store.selectedIssue?.id === cell.id"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * IssueList Component
 *
 * Renders a scrollable list of issue cards.
 * Uses Pinia store directly for state management.
 * Handles loading states and empty states.
 */
import IssueCard from './IssueCard.vue'
import { useIssuesStore } from '../stores/issuesStore'

// Props
defineProps<{}>()

const store = useIssuesStore()
</script>

<style scoped>
/* Custom scrollbar styling for better UX */
div::-webkit-scrollbar {
  width: 8px;
}

div::-webkit-scrollbar-track {
  background-color: var(--color-surface-secondary);
}

div::-webkit-scrollbar-thumb {
  background-color: var(--color-border);
  border-radius: 0.5rem;
}

div::-webkit-scrollbar-thumb:hover {
  background-color: var(--color-border-light);
}
</style>
