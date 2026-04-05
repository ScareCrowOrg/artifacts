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
<template>
  <div class="flex gap-4 p-4 bg-surface dark:bg-gray-900 border-b border-border dark:border-gray-700">
    <div
      class="flex flex-col p-3 rounded-md bg-warning/20 dark:bg-warning/30 text-warning dark:text-warning min-w-[100px]"
    >
      <span class="text-sm opacity-80 mb-1">{{ $t('issues.stats.pending') }}</span>
      <span class="text-2xl font-bold">{{ stats.pendente }}</span>
    </div>
    <div
      class="flex flex-col p-3 rounded-md bg-info/20 dark:bg-info/30 text-info dark:text-info min-w-[100px]"
    >
      <span class="text-sm opacity-80 mb-1">{{ $t('issues.stats.running') }}</span>
      <span class="text-2xl font-bold">{{ stats.executando }}</span>
    </div>
    <div
      class="flex flex-col p-3 rounded-md bg-success/20 dark:bg-success/30 text-success dark:text-success min-w-[100px]"
    >
      <span class="text-sm opacity-80 mb-1">{{ $t('issues.stats.completed') }}</span>
      <span class="text-2xl font-bold">{{ stats.finalizado }}</span>
    </div>
    <div
      class="flex flex-col p-3 rounded-md bg-error/20 dark:bg-error/30 text-error dark:text-error min-w-[100px]"
    >
      <span class="text-sm opacity-80 mb-1">{{ $t('issues.stats.errors') }}</span>
      <span class="text-2xl font-bold">{{ stats.erro }}</span>
    </div>
  </div>
</template>

<script setup>
/**
 * IssueStats Component
 *
 * Displays statistics of issues by state (pending, running, completed, error).
 * Uses Tailwind CSS for styling with dark theme colors.
 */
defineProps({
  stats: {
    type: Object,
    required: true,
    validator: (value) => {
      return (
        typeof value.pendente === 'number' &&
        typeof value.executando === 'number' &&
        typeof value.finalizado === 'number' &&
        typeof value.erro === 'number'
      )
    },
  },
})
</script>
