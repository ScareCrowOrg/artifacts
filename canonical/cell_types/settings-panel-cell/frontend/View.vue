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
 * View.vue - Main settings panel view with tab navigation
 * Implements conditional RBAC for admin settings
 */
<template>
  <div class="settings-panel-cell p-6 bg-surface dark:bg-surface-dark rounded-lg shadow-xl max-w-4xl mx-auto">
    <!-- Header -->
    <div class="mb-6 pb-4 border-b border-border dark:border-border-dark">
      <h1 class="text-2xl font-bold text-text-primary dark:text-text-primary-dark">
        {{ $t('settings.title') }}
      </h1>
      <p class="text-sm text-text-secondary dark:text-text-secondary-dark mt-1">
        {{ $t('settings.description') }}
      </p>
    </div>
    
    <!-- Tab Navigation -->
    <div class="tabs mb-6">
      <button
        :class="[
          'px-4 py-2 font-medium rounded-t-lg transition-colors',
          activeTab === 'user'
            ? 'bg-primary text-white'
            : 'bg-surface-dark dark:bg-surface text-text-secondary dark:text-text-secondary-dark hover:bg-surface-hover dark:hover:bg-surface-hover-dark'
        ]"
        @click="activeTab = 'user'"
      >
        {{ $t('settings.userTab') }}
      </button>
      <button
        v-if="hasAdminPermission"
        :class="[
          'px-4 py-2 font-medium rounded-t-lg transition-colors ml-2',
          activeTab === 'admin'
            ? 'bg-primary text-white'
            : 'bg-surface-dark dark:bg-surface text-text-secondary dark:text-text-secondary-dark hover:bg-surface-hover dark:hover:bg-surface-hover-dark'
        ]"
        @click="activeTab = 'admin'"
      >
        {{ $t('settings.adminTab') }}
        <span class="ml-1 text-xs opacity-75">{{ $t('settings.requiresPermission') }}</span>
      </button>
    </div>
    
    <!-- Tab Content -->
    <div class="tab-content">
      <!-- User Settings Tab -->
      <Transition
        enter-active-class="transition-opacity duration-300"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition-opacity duration-300"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
        mode="out-in"
      >
        <UserSettings 
          v-if="activeTab === 'user'"
          key="user"
        />
      </Transition>
      
      <!-- Admin Settings Tab (RBAC protected) -->
      <Transition
        enter-active-class="transition-opacity duration-300"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition-opacity duration-300"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
        mode="out-in"
      >
        <AdminSettings 
          v-if="activeTab === 'admin' && hasAdminPermission"
          key="admin"
        />
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { SettingsPanelCell } from './SettingsPanelCell'
import UserSettings from './components/UserSettings.vue'
import AdminSettings from './components/AdminSettings.vue'
import { useAuthStore } from '@/stores/auth'
import { useSettingsPanelStore } from './stores/settingsStore'

interface Props {
  cellInstance: SettingsPanelCell
}

const props = defineProps<Props>()

const activeTab = ref<'user' | 'admin'>('user')
const hasAdminPermission = ref(false)

const store = useSettingsPanelStore()

onMounted(async () => {
  // Initialize settings store
  await store.initialize()
  
  // Check admin permission
  const authStore = useAuthStore()
  hasAdminPermission.value = await authStore.hasPermission('settings:admin')
})
</script>

<style scoped>
.settings-panel-cell {
  min-height: 400px;
}

.tabs {
  display: flex;
  border-bottom: 2px solid var(--color-border);
}

.tab-content {
  margin-top: 1rem;
}
</style>
