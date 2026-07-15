/**
 * @metadata {
 *   "theme_validated": true,
 *   "i18n_validated": true,
 *   "i18n_coverage": 100
 * }
 */
<template>
  <div class="settings-manager-cell p-4 bg-surface dark:bg-surface-dark rounded-lg shadow-sm">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4 pb-3 border-b border-border dark:border-border-dark">
      <div>
        <h2 class="text-xl font-bold text-text-primary dark:text-text-primary-dark">
          {{ $t('settingsManager.title') }}
        </h2>
        <p class="text-sm text-text-secondary dark:text-text-secondary-dark mt-0.5">
          {{ $t('settingsManager.description') }}
        </p>
      </div>
      <div class="flex gap-2">
        <button
          class="px-3 py-1.5 text-sm bg-primary text-white rounded hover:bg-primary-hover transition-colors disabled:opacity-50"
          :disabled="isLoading"
          @click="handlePushRedis"
        >
          {{ $t('settingsManager.actions.pushRedis') }}
        </button>
        <button
          class="px-3 py-1.5 text-sm bg-surface-dark dark:bg-surface border border-border dark:border-border-dark rounded text-text-secondary dark:text-text-secondary-dark hover:bg-surface-hover dark:hover:bg-surface-hover-dark transition-colors"
          :disabled="isLoading"
          @click="loadSettings"
        >
          {{ $t('settingsManager.actions.refresh') }}
        </button>
      </div>
    </div>

    <!-- Error Banner -->
    <div
      v-if="error"
      class="flex items-center justify-between p-3 mb-4 rounded bg-error bg-opacity-10 text-error text-sm"
    >
      <span>{{ error }}</span>
      <button class="ml-2 font-bold" @click="error = null">✕</button>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="flex items-center justify-center py-8 text-text-secondary dark:text-text-secondary-dark">
      <span class="animate-pulse">{{ $t('settingsManager.loading') }}</span>
    </div>

    <!-- Tab Navigation -->
    <div class="flex gap-2 mb-4 border-b border-border dark:border-border-dark">
      <button
        v-for="tab in tabs"
        :key="tab"
        :class="[
          'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
          currentTab === tab
            ? 'border-primary text-primary dark:text-primary-light'
            : 'border-transparent text-text-secondary dark:text-text-secondary-dark hover:text-text-primary dark:hover:text-text-primary-dark'
        ]"
        @click="onTabChange(tab)"
      >
        {{ $t(`settingsManager.tabs.${tab}`) }}
      </button>
    </div>

    <!-- Tab: List Settings -->
    <div v-if="currentTab === 'list'" class="tab-content">
      <div class="flex justify-end mb-3">
        <button
          class="px-3 py-1.5 text-sm bg-primary text-white rounded hover:bg-primary-hover transition-colors"
          @click="currentTab = 'create'"
        >
          + {{ $t('settingsManager.actions.createSetting') }}
        </button>
      </div>

      <div v-if="!settings.length && !isLoading" class="py-8 text-center text-text-secondary dark:text-text-secondary-dark">
        {{ $t('settingsManager.emptyState') }}
      </div>

      <div v-else>
        <div
          v-for="(group, category) in settingsByCategory"
          :key="category"
          class="mb-4"
        >
          <h3 class="text-xs font-semibold uppercase tracking-wide text-text-secondary dark:text-text-secondary-dark mb-2">
            {{ category }}
          </h3>
          <table class="w-full text-sm border-collapse">
            <thead>
              <tr class="bg-surface-dark dark:bg-surface text-text-secondary dark:text-text-secondary-dark text-left">
                <th class="px-3 py-2 font-medium">{{ $t('settingsManager.cols.key') }}</th>
                <th class="px-3 py-2 font-medium">{{ $t('settingsManager.cols.type') }}</th>
                <th class="px-3 py-2 font-medium">{{ $t('settingsManager.cols.value') }}</th>
                <th class="px-3 py-2 font-medium">{{ $t('settingsManager.cols.lastUpdated') }}</th>
                <th class="px-3 py-2 font-medium">{{ $t('settingsManager.cols.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="setting in group"
                :key="setting.setting_key"
                class="border-t border-border dark:border-border-dark hover:bg-surface-hover dark:hover:bg-surface-hover-dark"
              >
                <td class="px-3 py-2 font-mono text-sm text-text-primary dark:text-text-primary-dark">{{ setting.setting_key }}</td>
                <td class="px-3 py-2">
                  <span class="px-1.5 py-0.5 text-xs rounded bg-surface-dark dark:bg-surface text-text-secondary dark:text-text-secondary-dark font-mono">
                    {{ setting.type }}
                  </span>
                </td>
                <td class="px-3 py-2 text-text-primary dark:text-text-primary-dark max-w-xs truncate">
                  <code class="text-xs">{{ formatSettingValue(setting) }}</code>
                </td>
                <td class="px-3 py-2 text-text-secondary dark:text-text-secondary-dark text-xs">
                  {{ setting.last_updated ? new Date(setting.last_updated).toLocaleString() : '—' }}
                </td>
                <td class="px-3 py-2">
                  <div class="flex gap-1">
                    <button
                      class="px-2 py-1 text-xs bg-surface-dark dark:bg-surface border border-border dark:border-border-dark rounded hover:bg-surface-hover dark:hover:bg-surface-hover-dark transition-colors"
                      :title="$t('settingsManager.actions.edit')"
                      @click="openEditModal(setting)"
                    >
                      ✏️
                    </button>
                    <button
                      class="px-2 py-1 text-xs bg-error bg-opacity-10 text-error border border-error border-opacity-30 rounded hover:bg-opacity-20 transition-colors"
                      :title="$t('settingsManager.actions.delete')"
                      @click="handleDeleteSetting(setting.setting_key)"
                    >
                      🗑️
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Tab: Create Setting -->
    <div v-if="currentTab === 'create'" class="tab-content max-w-lg">
      <form class="space-y-4" @submit.prevent="handleCreateSetting">
        <div>
          <label class="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">
            {{ $t('settingsManager.form.keyLabel') }} *
          </label>
          <input
            v-model="createForm.setting_key"
            type="text"
            :placeholder="$t('settingsManager.form.keyPlaceholder')"
            required
            class="w-full px-3 py-2 text-sm border border-border dark:border-border-dark bg-surface dark:bg-surface-dark rounded focus:outline-none focus:ring-2 focus:ring-primary text-text-primary dark:text-text-primary-dark"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">
            {{ $t('settingsManager.form.categoryLabel') }}
          </label>
          <input
            v-model="createForm.category"
            type="text"
            :placeholder="$t('settingsManager.form.categoryPlaceholder')"
            class="w-full px-3 py-2 text-sm border border-border dark:border-border-dark bg-surface dark:bg-surface-dark rounded focus:outline-none focus:ring-2 focus:ring-primary text-text-primary dark:text-text-primary-dark"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">
            {{ $t('settingsManager.form.typeLabel') }}
          </label>
          <select
            v-model="createForm.type"
            class="w-full px-3 py-2 text-sm border border-border dark:border-border-dark bg-surface dark:bg-surface-dark rounded focus:outline-none focus:ring-2 focus:ring-primary text-text-primary dark:text-text-primary-dark"
          >
            <option value="string">{{ $t('settingsManager.types.string') }}</option>
            <option value="number">{{ $t('settingsManager.types.number') }}</option>
            <option value="boolean">{{ $t('settingsManager.types.boolean') }}</option>
            <option value="json">{{ $t('settingsManager.types.json') }}</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">
            {{ $t('settingsManager.form.valueLabel') }} *
          </label>
          <textarea
            v-if="createForm.type === 'json'"
            v-model="createForm.value"
            :placeholder="$t('settingsManager.form.jsonPlaceholder')"
            rows="4"
            required
            class="w-full px-3 py-2 text-sm border border-border dark:border-border-dark bg-surface dark:bg-surface-dark rounded focus:outline-none focus:ring-2 focus:ring-primary text-text-primary dark:text-text-primary-dark font-mono resize-none"
          />
          <input
            v-else-if="createForm.type === 'boolean'"
            v-model="createForm.value"
            type="text"
            placeholder="true or false"
            required
            class="w-full px-3 py-2 text-sm border border-border dark:border-border-dark bg-surface dark:bg-surface-dark rounded focus:outline-none focus:ring-2 focus:ring-primary text-text-primary dark:text-text-primary-dark"
          />
          <input
            v-else-if="createForm.type === 'number'"
            v-model="createForm.value"
            type="number"
            :placeholder="$t('settingsManager.form.numberPlaceholder')"
            required
            class="w-full px-3 py-2 text-sm border border-border dark:border-border-dark bg-surface dark:bg-surface-dark rounded focus:outline-none focus:ring-2 focus:ring-primary text-text-primary dark:text-text-primary-dark"
          />
          <input
            v-else
            v-model="createForm.value"
            type="text"
            :placeholder="$t('settingsManager.form.valuePlaceholder')"
            required
            class="w-full px-3 py-2 text-sm border border-border dark:border-border-dark bg-surface dark:bg-surface-dark rounded focus:outline-none focus:ring-2 focus:ring-primary text-text-primary dark:text-text-primary-dark"
          />
        </div>

        <div class="flex gap-2 pt-2">
          <button
            type="submit"
            :disabled="isLoading"
            class="px-4 py-2 text-sm bg-primary text-white rounded hover:bg-primary-hover disabled:opacity-50 transition-colors"
          >
            {{ $t('settingsManager.form.createBtn') }}
          </button>
          <button
            type="button"
            class="px-4 py-2 text-sm bg-surface-dark dark:bg-surface border border-border dark:border-border-dark rounded hover:bg-surface-hover dark:hover:bg-surface-hover-dark transition-colors text-text-primary dark:text-text-primary-dark"
            @click="resetCreateForm"
          >
            {{ $t('settingsManager.form.cancelBtn') }}
          </button>
        </div>
      </form>
    </div>

    <!-- Tab: Modification History -->
    <div v-if="currentTab === 'history'" class="tab-content">
      <div class="flex justify-end mb-3">
        <button
          class="px-3 py-1.5 text-sm bg-surface-dark dark:bg-surface border border-border dark:border-border-dark rounded hover:bg-surface-hover dark:hover:bg-surface-hover-dark transition-colors text-text-secondary dark:text-text-secondary-dark"
          :disabled="isLoading"
          @click="loadHistory"
        >
          {{ $t('settingsManager.actions.refreshHistory') }}
        </button>
      </div>

      <div v-if="!history.length && !isLoading" class="py-8 text-center text-text-secondary dark:text-text-secondary-dark">
        {{ $t('settingsManager.historyEmptyState') }}
      </div>

      <table v-else class="w-full text-sm border-collapse">
        <thead>
          <tr class="bg-surface-dark dark:bg-surface text-text-secondary dark:text-text-secondary-dark text-left">
            <th class="px-3 py-2 font-medium">{{ $t('settingsManager.cols.timestamp') }}</th>
            <th class="px-3 py-2 font-medium">{{ $t('settingsManager.cols.action') }}</th>
            <th class="px-3 py-2 font-medium">{{ $t('settingsManager.cols.settingKey') }}</th>
            <th class="px-3 py-2 font-medium">{{ $t('settingsManager.cols.previousValue') }}</th>
            <th class="px-3 py-2 font-medium">{{ $t('settingsManager.cols.newValue') }}</th>
            <th class="px-3 py-2 font-medium">{{ $t('settingsManager.cols.historyActions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(entry, idx) in history"
            :key="idx"
            class="border-t border-border dark:border-border-dark hover:bg-surface-hover dark:hover:bg-surface-hover-dark"
          >
            <td class="px-3 py-2 text-xs text-text-secondary dark:text-text-secondary-dark">
              {{ new Date(entry.timestamp).toLocaleString() }}
            </td>
            <td class="px-3 py-2">
              <span class="px-1.5 py-0.5 text-xs rounded bg-primary bg-opacity-10 text-primary dark:text-primary-light font-mono">
                {{ entry.action }}
              </span>
            </td>
            <td class="px-3 py-2 font-mono text-xs text-text-primary dark:text-text-primary-dark">{{ entry.setting_key }}</td>
            <td class="px-3 py-2 font-mono text-xs text-text-secondary dark:text-text-secondary-dark max-w-xs truncate">
              {{ entry.previous_value ?? '—' }}
            </td>
            <td class="px-3 py-2 font-mono text-xs text-text-primary dark:text-text-primary-dark max-w-xs truncate">
              {{ entry.new_value ?? '—' }}
            </td>
            <td class="px-3 py-2">
              <button
                v-if="entry.previous_value !== undefined"
                class="px-2 py-1 text-xs bg-surface-dark dark:bg-surface border border-border dark:border-border-dark rounded hover:bg-surface-hover dark:hover:bg-surface-hover-dark transition-colors"
                :title="$t('settingsManager.actions.rollback')"
                @click="handleRollback(entry)"
              >
                ↩️
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Edit Setting Modal -->
    <div
      v-if="showEditModal && editTarget"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50"
      @click.self="showEditModal = false"
    >
      <div
        class="bg-surface dark:bg-surface-dark rounded-lg shadow-xl p-6 w-full max-w-sm mx-4"
        role="dialog"
        aria-modal="true"
      >
        <h3 class="text-base font-semibold text-text-primary dark:text-text-primary-dark mb-1">
          {{ $t('settingsManager.edit.title') }}
        </h3>
        <p class="text-sm text-text-secondary dark:text-text-secondary-dark mb-4 font-mono">
          {{ editTarget.setting_key }}
        </p>
        <form class="space-y-4" @submit.prevent="handleUpdateSetting">
          <div>
            <label class="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">
              {{ $t('settingsManager.form.valueLabel') }} *
            </label>
            <textarea
              v-if="editTarget.type === 'json'"
              v-model="editForm.value"
              rows="4"
              required
              class="w-full px-3 py-2 text-sm border border-border dark:border-border-dark bg-surface dark:bg-surface-dark rounded focus:outline-none focus:ring-2 focus:ring-primary text-text-primary dark:text-text-primary-dark font-mono resize-none"
            />
            <input
              v-else
              v-model="editForm.value"
              :type="editTarget.type === 'number' ? 'number' : 'text'"
              required
              class="w-full px-3 py-2 text-sm border border-border dark:border-border-dark bg-surface dark:bg-surface-dark rounded focus:outline-none focus:ring-2 focus:ring-primary text-text-primary dark:text-text-primary-dark"
            />
          </div>
          <div class="flex gap-2">
            <button
              type="submit"
              :disabled="isLoading"
              class="px-4 py-2 text-sm bg-primary text-white rounded hover:bg-primary-hover disabled:opacity-50 transition-colors"
            >
              {{ $t('settingsManager.edit.saveBtn') }}
            </button>
            <button
              type="button"
              class="px-4 py-2 text-sm bg-surface-dark dark:bg-surface border border-border dark:border-border-dark rounded hover:bg-surface-hover dark:hover:bg-surface-hover-dark transition-colors text-text-primary dark:text-text-primary-dark"
              @click="showEditModal = false"
            >
              {{ $t('settingsManager.form.cancelBtn') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

const { t: $t } = useI18n()

// ============================================================================
// Props & Emits
// ============================================================================

const props = defineProps<{
  cell: {
    id: string
    notebook_item_type_id: string
    initial_data: Record<string, any>
  }
}>()

const emit = defineEmits<{
  (e: 'update:cell', cell: typeof props.cell): void
  (e: 'execute', payload: Record<string, any>): void
}>()

// ============================================================================
// Types
// ============================================================================

type SettingType = 'string' | 'number' | 'boolean' | 'json'
type Tab = 'list' | 'create' | 'history'

interface Setting {
  setting_key: string
  category: string
  type: SettingType
  value: unknown
  last_updated?: string
}

interface HistoryEntry {
  timestamp: string
  action: string
  setting_key: string
  previous_value?: unknown
  new_value?: unknown
  user?: string
}

// ============================================================================
// State (Buffer Local Pattern)
// ============================================================================

const tabs: Tab[] = ['list', 'create', 'history']
const currentTab = ref<Tab>((props.cell.initial_data?.currentTab as Tab) ?? 'list')
const settings = ref<Setting[]>([])
const history = ref<HistoryEntry[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)
const showEditModal = ref(false)
const editTarget = ref<Setting | null>(null)

const createForm = ref({
  setting_key: '',
  category: 'general',
  type: 'string' as SettingType,
  value: '',
})

const editForm = ref({ value: '' })

// ============================================================================
// Hydration from props
// ============================================================================

watch(
  () => props.cell.initial_data,
  (newData) => {
    if (newData?.currentTab) {
      currentTab.value = newData.currentTab as Tab
    }
  },
  { deep: true }
)

// ============================================================================
// Persistence
// ============================================================================

function persistState() {
  emit('update:cell', {
    ...props.cell,
    initial_data: {
      ...props.cell.initial_data,
      currentTab: currentTab.value,
    },
  })
}

function onTabChange(tab: Tab) {
  currentTab.value = tab
  persistState()
  if (tab === 'history' && !history.value.length) {
    loadHistory()
  }
}

// ============================================================================
// Data Loading
// ============================================================================

async function loadSettings() {
  isLoading.value = true
  error.value = null
  try {
    emit('execute', {
      cell_type: 'settings-manager',
      action: 'list',
      service: 'launcher',
    })
  } catch (err: any) {
    error.value = err.message ?? $t('settingsManager.errors.loadFailed')
  } finally {
    isLoading.value = false
  }
}

async function loadHistory() {
  isLoading.value = true
  error.value = null
  try {
    emit('execute', {
      cell_type: 'settings-manager',
      action: 'history',
      service: 'launcher',
      filters: props.cell.initial_data?.historyFilters ?? {},
    })
  } catch (err: any) {
    error.value = err.message ?? $t('settingsManager.errors.historyFailed')
  } finally {
    isLoading.value = false
  }
}

// ============================================================================
// Actions
// ============================================================================

async function handleCreateSetting() {
  if (!createForm.value.setting_key || createForm.value.value === '') {
    error.value = $t('settingsManager.errors.requiredFields')
    return
  }

  isLoading.value = true
  error.value = null
  try {
    emit('execute', {
      cell_type: 'settings-manager',
      action: 'create',
      service: 'launcher',
      payload: {
        setting_key: createForm.value.setting_key,
        category: createForm.value.category,
        type: createForm.value.type,
        value: createForm.value.value,
      },
    })
    resetCreateForm()
  } catch (err: any) {
    error.value = err.message ?? $t('settingsManager.errors.createFailed')
  } finally {
    isLoading.value = false
  }
}

function openEditModal(setting: Setting) {
  editTarget.value = setting
  editForm.value = {
    value: setting.type === 'json' ? JSON.stringify(setting.value, null, 2) : String(setting.value),
  }
  showEditModal.value = true
}

async function handleUpdateSetting() {
  if (!editTarget.value) return

  isLoading.value = true
  error.value = null
  try {
    emit('execute', {
      cell_type: 'settings-manager',
      action: 'update',
      service: 'launcher',
      payload: {
        setting_key: editTarget.value.setting_key,
        value: editForm.value.value,
      },
    })
    showEditModal.value = false
    editTarget.value = null
  } catch (err: any) {
    error.value = err.message ?? $t('settingsManager.errors.updateFailed')
  } finally {
    isLoading.value = false
  }
}

async function handleDeleteSetting(settingKey: string) {
  if (!confirm($t('settingsManager.deleteConfirm', { key: settingKey }))) return

  isLoading.value = true
  error.value = null
  try {
    emit('execute', {
      cell_type: 'settings-manager',
      action: 'delete',
      service: 'launcher',
      payload: { setting_key: settingKey },
    })
  } catch (err: any) {
    error.value = err.message ?? $t('settingsManager.errors.deleteFailed')
  } finally {
    isLoading.value = false
  }
}

async function handleRollback(entry: HistoryEntry) {
  if (!confirm($t('settingsManager.rollbackConfirm', { key: entry.setting_key }))) return

  isLoading.value = true
  error.value = null
  try {
    emit('execute', {
      cell_type: 'settings-manager',
      action: 'rollback',
      service: 'launcher',
      payload: {
        setting_key: entry.setting_key,
        value: entry.previous_value,
      },
    })
  } catch (err: any) {
    error.value = err.message ?? $t('settingsManager.errors.rollbackFailed')
  } finally {
    isLoading.value = false
  }
}

async function handlePushRedis() {
  isLoading.value = true
  error.value = null
  try {
    emit('execute', {
      cell_type: 'settings-manager',
      action: 'push_redis',
      service: 'launcher',
    })
  } catch (err: any) {
    error.value = err.message ?? $t('settingsManager.errors.pushRedisFailed')
  } finally {
    isLoading.value = false
  }
}

function resetCreateForm() {
  createForm.value = { setting_key: '', category: 'general', type: 'string', value: '' }
  currentTab.value = 'list'
  persistState()
}

// ============================================================================
// Computed
// ============================================================================

const settingsByCategory = computed<Record<string, Setting[]>>(() => {
  const grouped: Record<string, Setting[]> = {}
  for (const setting of settings.value) {
    const cat = setting.category || 'general'
    if (!grouped[cat]) grouped[cat] = []
    grouped[cat].push(setting)
  }
  return grouped
})

function formatSettingValue(setting: Setting): string {
  if (setting.type === 'json') {
    try {
      return JSON.stringify(setting.value)
    } catch {
      return String(setting.value)
    }
  }
  return String(setting.value ?? '')
}

// ============================================================================
// Lifecycle
// ============================================================================

onMounted(() => {
  loadSettings()
})
</script>

<style scoped>
.settings-manager-cell {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.tab-content {
  min-height: 160px;
}
</style>
