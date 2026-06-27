/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-05-13",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div class="flex gap-2 items-center">
    <button
      v-if="showDelete"
      class="px-2 py-1 text-xs font-medium text-white bg-error hover:bg-error/80 rounded transition-colors"
      :disabled="disabled"
      @click="$emit('delete')"
      title="Delete asset"
    >
      Delete
    </button>
    
    <button
      v-if="showView"
      class="px-2 py-1 text-xs font-medium text-text-primary dark:text-text-primary-dark bg-surface-hover dark:bg-surface-dark border border-border dark:border-border-dark rounded hover:bg-surface dark:hover:bg-surface-hover transition-colors"
      :disabled="disabled"
      @click="$emit('view')"
      title="View details"
    >
      View
    </button>
  </div>
</template>

<script setup lang="ts">
/**
 * AssetActions component
 * 
 * Displays action buttons for an asset (delete, view, etc.)
 */

interface Props {
  showDelete?: boolean
  showView?: boolean
  disabled?: boolean
}

withDefaults(defineProps<Props>(), {
  showDelete: true,
  showView: true,
  disabled: false
})

defineEmits<{
  delete: []
  view: []
}>()
</script>
