/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-11",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-12",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div class="text-center p-8 welcome-message">
    <p class="mb-2">{{ $t('chat.welcome.greeting') }}</p>
    <p>
      {{ $t('chat.welcome.instructions') }}
    </p>
  </div>
</template>

<script setup>
// Simple presentational component with no logic
</script>

<style scoped>
.welcome-message {
  color: var(--color-text-secondary);
}
</style>
