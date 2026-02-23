/**
 * UserSettings - Personal user preferences component
 * Accessible to all users (no RBAC required)
 */
<template>
  <div class="user-settings">
    <h2 class="text-xl font-bold text-text-primary dark:text-text-primary-dark mb-6">
      User Settings
    </h2>
    
    <p class="text-sm text-text-secondary dark:text-text-secondary-dark mb-6">
      Configure your personal preferences. These settings apply only to your account.
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
