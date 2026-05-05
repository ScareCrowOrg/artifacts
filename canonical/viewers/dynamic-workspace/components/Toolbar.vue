/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-03-05",
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-03-05"
 * }
 */
<template>
  <div
    class="workspace-toolbar flex items-center gap-3 px-4 py-2 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700"
  >
    <!-- Save Layout button -->
    <button
      class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
      :disabled="isSaving"
      :title="t('layout.toolbar.saveLayoutTooltip')"
      :aria-label="t('layout.toolbar.saveLayoutTooltip')"
      @click="$emit('save-layout')"
    >
      <span aria-hidden="true">💾</span>
      <span class="hidden sm:inline">{{ t('layout.toolbar.saveLayout') }}</span>
    </button>

    <!-- Unsaved changes indicator -->
    <span
      v-if="hasUnsaved"
      class="flex items-center gap-1 text-xs text-amber-500 dark:text-amber-400"
      :title="t('layout.toolbar.unsavedChangesTooltip')"
    >
      <span>●</span>
      <span class="hidden sm:inline">{{ t('layout.toolbar.unsavedChanges') }}</span>
    </span>

    <!-- Spacer -->
    <span class="flex-1" />

    <!-- Saving indicator -->
    <span
      v-if="isSaving"
      class="text-xs text-gray-400 dark:text-gray-500 animate-pulse"
    >
      {{ t('layout.toolbar.saving') }}
    </span>
  </div>
</template>

<script setup lang="ts">
/**
 * @file Toolbar.vue
 * @description Workspace toolbar for DynamicWorkspace v2 — Phase 3.
 *
 * Provides Save Layout button and an unsaved-changes indicator.
 * The LayoutBookSelector (load) is integrated into the FooterWindowManager.
 */

import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  /** Whether there are unsaved grid changes */
  hasUnsaved: boolean
  /** Whether a save operation is in progress */
  isSaving?: boolean
}>()

defineEmits<{
  'save-layout': []
}>()
</script>

<style scoped>
.workspace-toolbar {
  min-height: 44px;
}
</style>
