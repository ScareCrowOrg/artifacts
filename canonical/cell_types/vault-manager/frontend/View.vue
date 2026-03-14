/**
 * @metadata {
 *   "theme_validated": true,
 *   "i18n_validated": true,
 *   "i18n_coverage": 100
 * }
 */
<template>
  <div class="vault-manager-cell p-4 bg-surface dark:bg-surface-dark rounded-lg shadow-sm">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4 pb-3 border-b border-border dark:border-border-dark">
      <div>
        <h2 class="text-xl font-bold text-text-primary dark:text-text-primary-dark">
          {{ $t('vaultManager.title') }}
        </h2>
        <p class="text-sm text-text-secondary dark:text-text-secondary-dark mt-0.5">
          {{ $t('vaultManager.description') }}
        </p>
      </div>
      <button
        class="px-3 py-1.5 text-sm bg-surface-dark dark:bg-surface rounded border border-border dark:border-border-dark text-text-secondary dark:text-text-secondary-dark hover:bg-surface-hover dark:hover:bg-surface-hover-dark transition-colors"
        :disabled="isLoading"
        @click="loadSecrets"
      >
        {{ $t('vaultManager.actions.refresh') }}
      </button>
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
      <span class="animate-pulse">{{ $t('vaultManager.loading') }}</span>
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
        {{ $t(`vaultManager.tabs.${tab}`) }}
      </button>
    </div>

    <!-- Tab: List Secrets -->
    <div v-if="currentTab === 'list'" class="tab-content">
      <div class="flex justify-end mb-3">
        <button
          class="px-3 py-1.5 text-sm bg-primary text-white rounded hover:bg-primary-hover transition-colors"
          @click="currentTab = 'create'"
        >
          + {{ $t('vaultManager.actions.createSecret') }}
        </button>
      </div>

      <div v-if="!secrets.length && !isLoading" class="py-8 text-center text-text-secondary dark:text-text-secondary-dark">
        {{ $t('vaultManager.emptyState') }}
      </div>

      <div v-else>
        <div
          v-for="(group, category) in secretsByCategory"
          :key="category"
          class="mb-4"
        >
          <h3 class="text-xs font-semibold uppercase tracking-wide text-text-secondary dark:text-text-secondary-dark mb-2">
            {{ category }}
          </h3>
          <table class="w-full text-sm border-collapse">
            <thead>
              <tr class="bg-surface-dark dark:bg-surface text-text-secondary dark:text-text-secondary-dark text-left">
                <th class="px-3 py-2 font-medium">{{ $t('vaultManager.cols.key') }}</th>
                <th class="px-3 py-2 font-medium">{{ $t('vaultManager.cols.description') }}</th>
                <th class="px-3 py-2 font-medium">{{ $t('vaultManager.cols.value') }}</th>
                <th class="px-3 py-2 font-medium">{{ $t('vaultManager.cols.lastUpdated') }}</th>
                <th class="px-3 py-2 font-medium">{{ $t('vaultManager.cols.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="secret in group"
                :key="secret.secret_key"
                class="border-t border-border dark:border-border-dark hover:bg-surface-hover dark:hover:bg-surface-hover-dark"
              >
                <td class="px-3 py-2 font-mono text-text-primary dark:text-text-primary-dark">{{ secret.secret_key }}</td>
                <td class="px-3 py-2 text-text-secondary dark:text-text-secondary-dark">{{ secret.description || '—' }}</td>
                <td class="px-3 py-2">
                  <code class="font-mono text-xs bg-surface-dark dark:bg-surface px-1 py-0.5 rounded">
                    {{ maskValue(secret.value) }}
                  </code>
                </td>
                <td class="px-3 py-2 text-text-secondary dark:text-text-secondary-dark text-xs">
                  {{ secret.last_updated ? new Date(secret.last_updated).toLocaleString() : '—' }}
                </td>
                <td class="px-3 py-2">
                  <div class="flex gap-1">
                    <button
                      class="px-2 py-1 text-xs bg-surface-dark dark:bg-surface border border-border dark:border-border-dark rounded hover:bg-surface-hover dark:hover:bg-surface-hover-dark transition-colors"
                      :title="$t('vaultManager.actions.rotate')"
                      @click="openRotateModal(secret.secret_key)"
                    >
                      🔄
                    </button>
                    <button
                      class="px-2 py-1 text-xs bg-error bg-opacity-10 text-error border border-error border-opacity-30 rounded hover:bg-opacity-20 transition-colors"
                      :title="$t('vaultManager.actions.delete')"
                      @click="handleDeleteSecret(secret.secret_key)"
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

    <!-- Tab: Create Secret -->
    <div v-if="currentTab === 'create'" class="tab-content max-w-lg">
      <form class="space-y-4" @submit.prevent="handleCreateSecret">
        <div>
          <label class="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">
            {{ $t('vaultManager.form.keyLabel') }} *
          </label>
          <input
            v-model="createForm.secret_key"
            type="text"
            :placeholder="$t('vaultManager.form.keyPlaceholder')"
            required
            class="w-full px-3 py-2 text-sm border border-border dark:border-border-dark bg-surface dark:bg-surface-dark rounded focus:outline-none focus:ring-2 focus:ring-primary text-text-primary dark:text-text-primary-dark"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">
            {{ $t('vaultManager.form.categoryLabel') }}
          </label>
          <select
            v-model="createForm.category"
            class="w-full px-3 py-2 text-sm border border-border dark:border-border-dark bg-surface dark:bg-surface-dark rounded focus:outline-none focus:ring-2 focus:ring-primary text-text-primary dark:text-text-primary-dark"
          >
            <option value="api">{{ $t('vaultManager.categories.api') }}</option>
            <option value="database">{{ $t('vaultManager.categories.database') }}</option>
            <option value="internal">{{ $t('vaultManager.categories.internal') }}</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">
            {{ $t('vaultManager.form.descriptionLabel') }}
          </label>
          <textarea
            v-model="createForm.description"
            :placeholder="$t('vaultManager.form.descriptionPlaceholder')"
            rows="2"
            class="w-full px-3 py-2 text-sm border border-border dark:border-border-dark bg-surface dark:bg-surface-dark rounded focus:outline-none focus:ring-2 focus:ring-primary text-text-primary dark:text-text-primary-dark resize-none"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">
            {{ $t('vaultManager.form.valueLabel') }} *
          </label>
          <input
            v-model="createForm.value"
            type="password"
            :placeholder="$t('vaultManager.form.valuePlaceholder')"
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
            {{ $t('vaultManager.form.createBtn') }}
          </button>
          <button
            type="button"
            class="px-4 py-2 text-sm bg-surface-dark dark:bg-surface border border-border dark:border-border-dark rounded hover:bg-surface-hover dark:hover:bg-surface-hover-dark transition-colors text-text-primary dark:text-text-primary-dark"
            @click="resetCreateForm"
          >
            {{ $t('vaultManager.form.cancelBtn') }}
          </button>
        </div>
      </form>
    </div>

    <!-- Tab: Audit Trail -->
    <div v-if="currentTab === 'audit'" class="tab-content">
      <div class="flex justify-end mb-3">
        <button
          class="px-3 py-1.5 text-sm bg-surface-dark dark:bg-surface border border-border dark:border-border-dark rounded hover:bg-surface-hover dark:hover:bg-surface-hover-dark transition-colors text-text-secondary dark:text-text-secondary-dark"
          :disabled="isLoading"
          @click="loadAuditTrail"
        >
          {{ $t('vaultManager.actions.refreshAudit') }}
        </button>
      </div>

      <div v-if="!auditTrail.length && !isLoading" class="py-8 text-center text-text-secondary dark:text-text-secondary-dark">
        {{ $t('vaultManager.auditEmptyState') }}
      </div>

      <table v-else class="w-full text-sm border-collapse">
        <thead>
          <tr class="bg-surface-dark dark:bg-surface text-text-secondary dark:text-text-secondary-dark text-left">
            <th class="px-3 py-2 font-medium">{{ $t('vaultManager.cols.timestamp') }}</th>
            <th class="px-3 py-2 font-medium">{{ $t('vaultManager.cols.action') }}</th>
            <th class="px-3 py-2 font-medium">{{ $t('vaultManager.cols.secretKey') }}</th>
            <th class="px-3 py-2 font-medium">{{ $t('vaultManager.cols.user') }}</th>
            <th class="px-3 py-2 font-medium">{{ $t('vaultManager.cols.reason') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(entry, idx) in auditTrail"
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
            <td class="px-3 py-2 font-mono text-xs text-text-primary dark:text-text-primary-dark">{{ entry.secret_key }}</td>
            <td class="px-3 py-2 text-text-secondary dark:text-text-secondary-dark text-xs">{{ entry.user || '—' }}</td>
            <td class="px-3 py-2 text-text-secondary dark:text-text-secondary-dark text-xs">{{ entry.reason || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Rotate Secret Modal -->
    <div
      v-if="showRotateModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50"
      @click.self="showRotateModal = false"
    >
      <div
        class="bg-surface dark:bg-surface-dark rounded-lg shadow-xl p-6 w-full max-w-sm mx-4"
        role="dialog"
        aria-modal="true"
      >
        <h3 class="text-base font-semibold text-text-primary dark:text-text-primary-dark mb-1">
          {{ $t('vaultManager.rotate.title') }}
        </h3>
        <p class="text-sm text-text-secondary dark:text-text-secondary-dark mb-4">
          {{ $t('vaultManager.rotate.subtitle', { key: rotateTargetKey }) }}
        </p>
        <form class="space-y-4" @submit.prevent="handleRotateSecret">
          <div>
            <label class="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">
              {{ $t('vaultManager.rotate.newValueLabel') }} *
            </label>
            <input
              v-model="rotateForm.new_value"
              type="password"
              :placeholder="$t('vaultManager.rotate.newValuePlaceholder')"
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
              {{ $t('vaultManager.rotate.confirmBtn') }}
            </button>
            <button
              type="button"
              class="px-4 py-2 text-sm bg-surface-dark dark:bg-surface border border-border dark:border-border-dark rounded hover:bg-surface-hover dark:hover:bg-surface-hover-dark transition-colors text-text-primary dark:text-text-primary-dark"
              @click="showRotateModal = false"
            >
              {{ $t('vaultManager.form.cancelBtn') }}
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

interface Secret {
  secret_key: string
  category: string
  description: string
  value: string
  last_updated?: string
}

interface AuditEntry {
  timestamp: string
  action: string
  secret_key: string
  user?: string
  reason?: string
}

type Tab = 'list' | 'create' | 'audit'

// ============================================================================
// State (Buffer Local Pattern)
// ============================================================================

const tabs: Tab[] = ['list', 'create', 'audit']
const currentTab = ref<Tab>((props.cell.initial_data?.currentTab as Tab) ?? 'list')
const secrets = ref<Secret[]>([])
const auditTrail = ref<AuditEntry[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)
const showRotateModal = ref(false)
const rotateTargetKey = ref<string>('')

const createForm = ref({
  secret_key: '',
  description: '',
  category: 'api',
  value: '',
})

const rotateForm = ref({
  new_value: '',
})

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
  if (tab === 'audit' && !auditTrail.value.length) {
    loadAuditTrail()
  }
}

// ============================================================================
// Data Loading
// ============================================================================

async function loadSecrets() {
  isLoading.value = true
  error.value = null
  try {
    emit('execute', {
      cell_type: 'vault-manager',
      action: 'list',
      service: 'launcher',
    })
  } catch (err: any) {
    error.value = err.message ?? $t('vaultManager.errors.loadFailed')
  } finally {
    isLoading.value = false
  }
}

async function loadAuditTrail() {
  isLoading.value = true
  error.value = null
  try {
    emit('execute', {
      cell_type: 'vault-manager',
      action: 'audit',
      service: 'launcher',
      filters: props.cell.initial_data?.auditFilters ?? {},
    })
  } catch (err: any) {
    error.value = err.message ?? $t('vaultManager.errors.auditFailed')
  } finally {
    isLoading.value = false
  }
}

// ============================================================================
// Actions
// ============================================================================

async function handleCreateSecret() {
  if (!createForm.value.secret_key || !createForm.value.value) {
    error.value = $t('vaultManager.errors.requiredFields')
    return
  }

  isLoading.value = true
  error.value = null
  try {
    emit('execute', {
      cell_type: 'vault-manager',
      action: 'create',
      service: 'launcher',
      payload: {
        secret_key: createForm.value.secret_key,
        description: createForm.value.description,
        category: createForm.value.category,
        value: createForm.value.value,
      },
    })
    resetCreateForm()
  } catch (err: any) {
    error.value = err.message ?? $t('vaultManager.errors.createFailed')
  } finally {
    isLoading.value = false
  }
}

function openRotateModal(secretKey: string) {
  rotateTargetKey.value = secretKey
  rotateForm.value = { new_value: '' }
  showRotateModal.value = true
}

async function handleRotateSecret() {
  if (!rotateTargetKey.value || !rotateForm.value.new_value) {
    error.value = $t('vaultManager.errors.requiredFields')
    return
  }

  isLoading.value = true
  error.value = null
  try {
    emit('execute', {
      cell_type: 'vault-manager',
      action: 'rotate',
      service: 'launcher',
      payload: {
        secret_key: rotateTargetKey.value,
        new_value: rotateForm.value.new_value,
      },
    })
    showRotateModal.value = false
    rotateForm.value = { new_value: '' }
  } catch (err: any) {
    error.value = err.message ?? $t('vaultManager.errors.rotateFailed')
  } finally {
    isLoading.value = false
  }
}

async function handleDeleteSecret(secretKey: string) {
  if (!confirm($t('vaultManager.deleteConfirm', { key: secretKey }))) {
    return
  }

  isLoading.value = true
  error.value = null
  try {
    emit('execute', {
      cell_type: 'vault-manager',
      action: 'delete',
      service: 'launcher',
      payload: { secret_key: secretKey },
    })
  } catch (err: any) {
    error.value = err.message ?? $t('vaultManager.errors.deleteFailed')
  } finally {
    isLoading.value = false
  }
}

function resetCreateForm() {
  createForm.value = { secret_key: '', description: '', category: 'api', value: '' }
  currentTab.value = 'list'
  persistState()
}

// ============================================================================
// Computed
// ============================================================================

const secretsByCategory = computed<Record<string, Secret[]>>(() => {
  const grouped: Record<string, Secret[]> = {}
  for (const secret of secrets.value) {
    const cat = secret.category || 'uncategorized'
    if (!grouped[cat]) grouped[cat] = []
    grouped[cat].push(secret)
  }
  return grouped
})

function maskValue(value: string, visibleChars: number = 3): string {
  if (!value) return '•••'
  if (value.length <= visibleChars) return '•'.repeat(value.length)
  return value.substring(0, visibleChars) + '•'.repeat(Math.min(value.length - visibleChars, 12))
}

// ============================================================================
// Lifecycle
// ============================================================================

onMounted(() => {
  loadSecrets()
})
</script>

<style scoped>
.vault-manager-cell {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.tab-content {
  min-height: 160px;
}
</style>
