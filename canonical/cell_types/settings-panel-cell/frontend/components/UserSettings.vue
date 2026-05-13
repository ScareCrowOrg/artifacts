/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-05-13",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
/**
 * UserSettings - Personal user preferences component
 * Accessible to all users (no RBAC required)
 */
<template>
  <div class="user-settings">
    <h2 class="text-xl font-bold text-text-primary dark:text-text-primary-dark mb-6">
      {{ $t('settings.userSettings.title') }}
    </h2>
    
    <p class="text-sm text-text-secondary dark:text-text-secondary-dark mb-6">
      {{ $t('settings.userSettings.description') }}
    </p>
    
    <!-- Theme Settings -->
    <ThemeSettings />
  </div>
</template>

<script setup lang="ts">
import ThemeSettings from './ThemeSettings.vue'
</script>

<style scoped>
.user-settings {
  /* Component-specific styles if needed */
}
</style>
