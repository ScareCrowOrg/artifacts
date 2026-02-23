/**
 * AdminSettings - Global/admin settings component
 * Requires settings:admin permission
 */
<template>
  <div class="admin-settings">
    <h2 class="text-xl font-bold text-text-primary dark:text-text-primary-dark mb-6">
      {{ $t('settings.adminSettings.title') }}
    </h2>
    
    <p class="text-sm text-text-secondary dark:text-text-secondary-dark mb-6">
      {{ $t('settings.adminSettings.description') }}
    </p>
    
    <!-- OAuth Configuration -->
    <div class="mb-8">
      <h3 class="mb-4 text-lg font-semibold text-text-primary dark:text-text-primary-dark">
        {{ $t('settings.oauth.title') }}
      </h3>
      <p class="text-sm text-text-secondary dark:text-text-secondary-dark mb-4">
        {{ $t('settings.oauth.description') }}
      </p>

      <div class="mb-4">
        <label
          for="clientId"
          class="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1"
        >
          {{ $t('settings.oauth.clientIdLabel') }}
        </label>
        <input
          id="clientId"
          v-model="store.oauthConfig.googleClientId"
          type="text"
          :placeholder="$t('settings.oauth.clientIdPlaceholder')"
          class="w-full px-3 py-2 bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark border border-border dark:border-border-dark rounded-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
        />
      </div>

      <div class="mb-4">
        <label
          for="clientSecret"
          class="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1"
        >
          {{ $t('settings.oauth.clientSecretLabel') }}
        </label>
        <input
          id="clientSecret"
          v-model="store.oauthConfig.googleClientSecret"
          type="password"
          :placeholder="$t('settings.oauth.clientSecretPlaceholder')"
          class="w-full px-3 py-2 bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark border border-border dark:border-border-dark rounded-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
        />
        <small class="block mt-1 text-xs text-text-tertiary dark:text-text-tertiary-dark">
          {{ $t('settings.oauth.securityNote') }}
        </small>
      </div>

      <div class="mb-6">
        <div class="flex items-center gap-2">
          <span class="text-sm text-text-primary dark:text-text-primary-dark">
            {{ $t('settings.oauth.authStatusLabel') }}
          </span>
          <span
            :class="[
              'px-2 py-0.5 text-xs font-medium rounded',
              store.authStatus.authEnabled
                ? 'bg-success/20 dark:bg-success/30 text-success dark:text-success'
                : 'bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark',
            ]"
          >
            {{
              store.authStatus.authEnabled
                ? $t('settings.oauth.authEnabled')
                : $t('settings.oauth.authDisabled')
            }}
          </span>
        </div>
        <small
          v-if="store.authStatus.authEnabled"
          class="block mt-2 p-3 rounded-md bg-info/10 dark:bg-info/20 text-info dark:text-info border border-info/20 dark:border-info/30 text-sm"
        >
          {{ $t('settings.oauth.authRequiredInfo') }}
        </small>
      </div>

      <div class="flex gap-2">
        <button
          :disabled="store.isSavingOAuth || !store.isOAuthConfigChanged"
          class="btn btn-primary"
          @click="store.saveOAuthConfig()"
        >
          {{
            store.isSavingOAuth 
              ? $t('settings.oauth.saving') 
              : $t('settings.oauth.saveButton')
          }}
        </button>
      </div>

      <div
        v-if="store.oauthSaveMessage"
        :class="[
          'mt-4 p-3 rounded-md text-sm',
          store.oauthSaveMessageType === 'success'
            ? 'bg-success/10 dark:bg-success/20 text-success dark:text-success border border-success/20 dark:border-success/30'
            : 'bg-error/10 dark:bg-error/20 text-error dark:text-error border border-error/20 dark:border-error/30',
        ]"
      >
        {{ store.oauthSaveMessage }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useSettingsPanelStore } from '../stores/settingsStore'

const store = useSettingsPanelStore()

onMounted(async () => {
  // Load OAuth status when admin settings are opened
  await store.loadOAuthStatus()
})
</script>

<style scoped>
.admin-settings {
  /* Component-specific styles if needed */
}
</style>
