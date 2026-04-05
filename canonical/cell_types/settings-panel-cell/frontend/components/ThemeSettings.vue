/**
 * ThemeSettings - Theme configuration component
 * Allows users to select theme preference (auto, light, dark)
 */
<template>
  <div class="theme-settings">
    <h3 class="mb-4 text-primary dark:text-primary text-lg font-semibold">
      {{ $t('settings.appearance.themeTitle') }}
    </h3>
    <p class="text-sm text-text-secondary dark:text-text-secondary-dark mb-4">
      {{ $t('settings.appearance.themeDescription') }}
    </p>

    <div class="mb-4">
      <label
        for="theme-select"
        class="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1"
      >
        {{ $t('settings.appearance.selectThemeLabel') }}
      </label>
      <select
        id="theme-select"
        v-model="localTheme"
        class="w-full px-3 py-2 bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark border border-border dark:border-border-dark rounded-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
        @change="handleThemeChange"
      >
        <option value="auto">{{ $t('settings.appearance.themeAuto') }}</option>
        <option value="light">{{ $t('settings.appearance.themeLight') }}</option>
        <option value="dark">{{ $t('settings.appearance.themeDark') }}</option>
      </select>
      <small class="block mt-1 text-xs text-text-tertiary dark:text-text-tertiary-dark">
        <strong>{{ $t('settings.appearance.themeAuto') }}:</strong> {{ $t('settings.appearance.themeAutoDesc') }}<br />
        <strong>{{ $t('settings.appearance.themeLight') }}:</strong> {{ $t('settings.appearance.themeLightDesc') }}<br />
        <strong>{{ $t('settings.appearance.themeDark') }}:</strong> {{ $t('settings.appearance.themeDarkDesc') }}
      </small>
    </div>

    <!-- Theme Preview -->
    <div class="mt-6 bg-surface dark:bg-surface-dark rounded-lg shadow-sm">
      <div class="px-4 py-3 border-b border-border dark:border-border-dark">
        <h4 class="text-base font-semibold text-text-primary dark:text-text-primary-dark m-0">
          {{ $t('settings.appearance.previewTitle', { theme: effectiveThemeDisplay }) }}
        </h4>
      </div>
      <div class="p-4">
        <div class="flex gap-2 mb-4">
          <button class="btn btn-sm btn-primary">
            {{ $t('settings.appearance.btnPrimary') }}
          </button>
          <button class="btn btn-sm btn-secondary">
            {{ $t('settings.appearance.btnSecondary') }}
          </button>
          <button class="btn btn-sm btn-ghost">
            {{ $t('settings.appearance.btnGhost') }}
          </button>
        </div>
        <p class="text-sm text-text-secondary dark:text-text-secondary-dark mb-4">
          {{ $t('settings.appearance.exampleContent') }}
        </p>
        <div class="p-3 rounded-md bg-info/10 dark:bg-info/20 text-info dark:text-info border border-info/20 dark:border-info/30 text-sm">
          {{ $t('settings.appearance.exampleInfo') }}
        </div>
      </div>
    </div>

    <!-- Design System Info -->
    <div class="mt-8">
      <h3 class="mb-4 text-primary dark:text-primary text-lg font-semibold">
        {{ $t('settings.appearance.designSystemTitle') }}
      </h3>
      <p class="text-sm text-text-secondary dark:text-text-secondary-dark mb-4">
        {{ $t('settings.appearance.designSystemDescription') }}
      </p>
      <ul class="list-none p-0">
        <li class="py-2 border-b border-border dark:border-border-dark last:border-b-0">
          <strong>{{ $t('settings.appearance.featureMinimalist') }}</strong>
        </li>
        <li class="py-2 border-b border-border dark:border-border-dark last:border-b-0">
          <strong>{{ $t('settings.appearance.featureThemes') }}</strong>
        </li>
        <li class="py-2 border-b border-border dark:border-border-dark last:border-b-0">
          <strong>{{ $t('settings.appearance.featureCSS') }}</strong>
        </li>
        <li class="py-2 border-b border-border dark:border-border-dark last:border-b-0">
          <strong>{{ $t('settings.appearance.featureResponsive') }}</strong>
        </li>
        <li class="py-2 border-b border-border dark:border-border-dark last:border-b-0">
          <strong>{{ $t('settings.appearance.featureAccessible') }}</strong>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useSettingsPanelStore } from '../stores/settingsStore'

const store = useSettingsPanelStore()

const localTheme = ref(store.selectedTheme)

const effectiveThemeDisplay = computed(() => store.effectiveThemeDisplay)

function handleThemeChange() {
  store.selectedTheme = localTheme.value
  store.changeTheme()
}

// Watch for external theme changes
watch(() => store.selectedTheme, (newTheme) => {
  localTheme.value = newTheme
})
</script>

<style scoped>
.theme-settings {
  /* Component-specific styles if needed */
}
</style>
