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
    <h3 class="m-0 mb-4 text-base text-text-primary dark:text-text-primary">{{ $t('issues.ingestForm.title') }}</h3>

    <div class="mb-4">
      <label for="sourceDir" class="block mb-2 text-sm text-text-primary dark:text-text-primary">{{ $t('issues.ingestForm.sourceDirLabel') }}</label>
      <input
        id="sourceDir"
        v-model="localOptions.sourceDir"
        type="text"
        :placeholder="$t('issues.ingestForm.sourceDirPlaceholder')"
        class="w-full px-2 py-2 bg-surface dark:bg-gray-800 border border-border dark:border-gray-700 text-text-primary dark:text-text-primary rounded text-sm focus:border-primary focus:ring-2 focus:ring-primary/50 focus:outline-none"
      />
    </div>

    <div class="mb-4">
      <label class="flex items-center text-sm cursor-pointer text-text-primary dark:text-text-primary">
        <input v-model="localOptions.dryRun" type="checkbox" class="mr-2" />
        {{ $t('issues.ingestForm.dryRunLabel') }}
      </label>
    </div>

    <div class="flex gap-2">
      <button
        class="px-4 py-2 border-none rounded cursor-pointer text-sm bg-primary dark:bg-primary text-white dark:text-white hover:bg-primary-hover dark:hover:bg-primary-hover transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="isRunning"
        @click="handleSubmit"
      >
        {{ isRunning ? $t('issues.ingestForm.runningButton') : $t('issues.ingestForm.runButton') }}
      </button>
      <button
        class="px-4 py-2 border-none rounded cursor-pointer text-sm bg-surface-hover dark:bg-gray-800 text-text-primary dark:text-text-primary hover:bg-border dark:hover:bg-gray-700 transition-all"
        @click="handleCancel"
      >
        {{ $t('issues.ingestForm.cancelButton') }}
      </button>
    </div>
  </div>
</template>

<script setup>
/**
 * IngestForm Component
 *
 * Form for triggering ingestion process. Extracted from IssuesDashboard
 * to maintain component size under 500 lines.
 */
import { ref } from 'vue'
import { useIssuesStore } from '../stores/issuesStore'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:IssuesDashboard:IngestForm')
const emit = defineEmits(['close', 'submit'])

// Store
const store = useIssuesStore()

// Local state
const localOptions = ref({
  sourceDir: '',
  dryRun: false,
})

// Computed
const isRunning = ref(false)

// Methods
async function handleSubmit() {
  isRunning.value = true

  try {
    const options = {
      sourceDir: localOptions.value.sourceDir || null,
      dryRun: localOptions.value.dryRun,
    }

    await store.triggerIngestion(options)

    // Reset form
    localOptions.value = {
      sourceDir: '',
      dryRun: false,
    }

    // Emit close and notify parent
    emit('submit', options)
    emit('close')

    // Reload issues after delay
    setTimeout(() => {
      store.loadIssues()
    }, 2000)
  } catch (err) {
    log.error('Failed to trigger ingest', { error: err })
    isRunning.value = false
  }
}

function handleCancel() {
  // Reset form
  localOptions.value = {
    sourceDir: '',
    dryRun: false,
  }

  emit('close')
}
</script>
