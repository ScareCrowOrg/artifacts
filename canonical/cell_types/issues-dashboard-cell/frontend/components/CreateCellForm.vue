/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-12",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0,
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-12",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "dark_mode_support": "full",
 *   "theme_issues_found": 0
 * }
 */
<template>
  <div class="p-4 bg-surface dark:bg-gray-900 border-b border-border dark:border-gray-700">
    <h3 class="m-0 mb-4 text-base text-text-primary dark:text-text-primary">{{ $t('issues.createCellForm.title') }}</h3>

    <div class="mb-4">
      <label for="cellType" class="block mb-2 text-sm text-text-primary dark:text-text-primary">{{ $t('issues.createCellForm.cellTypeLabel') }}</label>
      <select
        id="cellType"
        v-model="formData.notebook_item_type_id"
        class="w-full px-2 py-2 bg-surface dark:bg-gray-800 border border-border dark:border-gray-700 text-text-primary dark:text-text-primary rounded text-sm focus:border-primary focus:ring-2 focus:ring-primary/50 focus:outline-none"
      >
        <option value="">{{ $t('issues.createCellForm.selectTypePlaceholder') }}</option>
        <option
          v-for="itemType in notebookItemTypes"
          :key="itemType.id"
          :value="itemType.id"
        >
          {{ itemType.name }}
        </option>
      </select>
    </div>

    <div class="mb-4">
      <label for="initialData" class="block mb-2 text-sm text-text-primary dark:text-text-primary">
        {{ $t('issues.createCellForm.initialDataLabel') }}
        <span class="text-text-secondary dark:text-text-secondary text-xs ml-1">{{ $t('issues.createCellForm.optional') }}</span>
      </label>
      <textarea
        id="initialData"
        v-model="formData.initial_data"
        rows="4"
        :placeholder="$t('issues.createCellForm.initialDataPlaceholder')"
        class="w-full px-2 py-2 bg-surface dark:bg-gray-800 border border-border dark:border-gray-700 text-text-primary dark:text-text-primary rounded text-sm font-mono focus:border-primary focus:ring-2 focus:ring-primary/50 focus:outline-none"
      ></textarea>
    </div>

    <div class="mb-4">
      <label for="refs" class="block mb-2 text-sm text-text-primary dark:text-text-primary">
        {{ $t('issues.createCellForm.referencesLabel') }}
        <span class="text-text-secondary dark:text-text-secondary text-xs ml-1">{{ $t('issues.createCellForm.optional') }}</span>
      </label>
      <textarea
        id="refs"
        v-model="formData.refs"
        rows="3"
        :placeholder="$t('issues.createCellForm.referencesPlaceholder')"
        class="w-full px-2 py-2 bg-surface dark:bg-gray-800 border border-border dark:border-gray-700 text-text-primary dark:text-text-primary rounded text-sm font-mono focus:border-primary focus:ring-2 focus:ring-primary/50 focus:outline-none"
      ></textarea>
    </div>

    <div class="flex gap-2">
      <button
        class="px-4 py-2 border-none rounded cursor-pointer text-sm bg-success dark:bg-success text-white dark:text-white hover:bg-success/80 dark:hover:bg-success-dark transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="isCreating || !formData.notebook_item_type_id"
        @click="handleSubmit"
      >
        {{ isCreating ? $t('issues.createCellForm.creatingButton') : $t('issues.createCellForm.createButton') }}
      </button>
      <button
        class="px-4 py-2 border-none rounded cursor-pointer text-sm bg-surface-hover dark:bg-gray-800 text-text-primary dark:text-text-primary hover:bg-border dark:hover:bg-gray-700 transition-all"
        @click="handleCancel"
      >
        {{ $t('issues.createCellForm.cancelButton') }}
      </button>
    </div>
  </div>
</template>

<script setup>
/**
 * CreateCellForm Component
 *
 * Form for creating new cells. Extracted from IssuesDashboard
 * to maintain component size under 500 lines.
 */
import { ref, computed } from 'vue'
import { useIssuesStore } from '../stores/issuesStore'
import { useI18n } from 'vue-i18n'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:IssuesDashboard:CreateCellForm')
const { t } = useI18n()

const emit = defineEmits(['close', 'submit'])

// Store
const store = useIssuesStore()

// Local state
const formData = ref({
  notebook_item_type_id: '',
  initial_data: '',
  refs: '',
})

const isCreating = ref(false)

// Computed
const notebookItemTypes = computed(() => store.notebookItemTypes)

// Methods
async function handleSubmit() {
  isCreating.value = true

  try {
    // Parse JSON fields
    let initialData = {}
    let refs = {}

    if (formData.value.initial_data) {
      try {
        initialData = JSON.parse(formData.value.initial_data)
      } catch {
        throw new Error(t('issues.createCellForm.invalidInitialData'))
      }
    }

    if (formData.value.refs) {
      try {
        refs = JSON.parse(formData.value.refs)
      } catch {
        throw new Error(t('issues.createCellForm.invalidRefs'))
      }
    }

    // Get current user ID (for now, use a placeholder)
    // TODO: Get from auth context
    const assigneeId = 'current-user-id'

    const cellData = {
      notebook_item_type_id: formData.value.notebook_item_type_id,
      assignee_id: assigneeId,
      initial_data: initialData,
      refs: refs,
    }

    await store.createCell(cellData)

    // Reset form
    formData.value = {
      notebook_item_type_id: '',
      initial_data: '',
      refs: '',
    }

    // Emit events
    emit('submit', cellData)
    emit('close')
  } catch (err: any) {
    log.error('Failed to create cell', { error: err.message })
    store.error = err.message
  } finally {
    isCreating.value = false
  }
}

function handleCancel() {
  // Reset form
  formData.value = {
    notebook_item_type_id: '',
    initial_data: '',
    refs: '',
  }

  emit('close')
}
</script>
