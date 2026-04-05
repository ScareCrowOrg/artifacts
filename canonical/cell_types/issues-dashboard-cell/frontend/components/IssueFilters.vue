/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-02-22",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "dark_mode_support": "full",
 *   "theme_issues_found": 0,
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-02-22",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div
    class="flex justify-between items-center p-4 bg-surface dark:bg-gray-900 border-b border-border dark:border-gray-700 flex-wrap gap-4"
  >
    <!-- Filter Buttons -->
    <div class="flex gap-2">
      <button
        :class="[
          'px-4 py-2 text-sm rounded-md border transition-all',
          store.filterState === 'all'
            ? 'bg-primary border-primary text-white dark:text-white'
            : 'bg-surface dark:bg-gray-800 border-border dark:border-gray-700 text-text-primary dark:text-text-primary hover:bg-surface-hover dark:hover:bg-gray-700 hover:border-primary dark:hover:border-primary',
        ]"
        @click="store.setFilter('all')"
      >
        {{ $t('issues.filters.all') }}
      </button>
      <button
        :class="[
          'px-4 py-2 text-sm rounded-md border transition-all',
          store.filterState === 'pendente'
            ? 'bg-primary border-primary text-white dark:text-white'
            : 'bg-surface dark:bg-gray-800 border-border dark:border-gray-700 text-text-primary dark:text-text-primary hover:bg-surface-hover dark:hover:bg-gray-700 hover:border-primary dark:hover:border-primary',
        ]"
        @click="store.setFilter('pendente')"
      >
        {{ $t('issues.stats.pending') }}
      </button>
      <button
        :class="[
          'px-4 py-2 text-sm rounded-md border transition-all',
          store.filterState === 'executando'
            ? 'bg-primary border-primary text-white dark:text-white'
            : 'bg-surface dark:bg-gray-800 border-border dark:border-gray-700 text-text-primary dark:text-text-primary hover:bg-surface-hover dark:hover:bg-gray-700 hover:border-primary dark:hover:border-primary',
        ]"
        @click="store.setFilter('executando')"
      >
        {{ $t('issues.stats.running') }}
      </button>
      <button
        :class="[
          'px-4 py-2 text-sm rounded-md border transition-all',
          store.filterState === 'finalizado'
            ? 'bg-primary border-primary text-white dark:text-white'
            : 'bg-surface dark:bg-gray-800 border-border dark:border-gray-700 text-text-primary dark:text-text-primary hover:bg-surface-hover dark:hover:bg-gray-700 hover:border-primary dark:hover:border-primary',
        ]"
        @click="store.setFilter('finalizado')"
      >
        {{ $t('issues.stats.completed') }}
      </button>
      <button
        :class="[
          'px-4 py-2 text-sm rounded-md border transition-all',
          store.filterState === 'erro'
            ? 'bg-primary border-primary text-white dark:text-white'
            : 'bg-surface dark:bg-gray-800 border-border dark:border-gray-700 text-text-primary dark:text-text-primary hover:bg-surface-hover dark:hover:bg-gray-700 hover:border-primary dark:hover:border-primary',
        ]"
        @click="store.setFilter('erro')"
      >
        {{ $t('issues.stats.errors') }}
      </button>
    </div>

    <!-- Action Buttons -->
    <div class="flex gap-2">
      <button
        class="px-4 py-2 text-sm rounded-md bg-surface dark:bg-gray-800 border border-border dark:border-gray-700 text-text-primary dark:text-text-primary hover:bg-surface-hover dark:hover:bg-gray-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="store.isLoading"
        @click="store.loadIssues()"
      >
        {{ $t('issues.filters.refresh') }}
      </button>

      <!-- Monitoring Control (Write permission required) -->
      <template v-if="hasWritePermission">
        <button
          v-if="!store.monitoringStatus.active"
          class="px-4 py-2 text-sm rounded-md bg-success dark:bg-success border border-success dark:border-success text-white dark:text-white hover:bg-success/80 dark:hover:bg-success-dark transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="store.isMonitoringLoading"
          :title="$t('issues.filters.startMonitoringTitle')"
          @click="handleStartMonitoring"
        >
          {{
            store.isMonitoringLoading
              ? $t('issues.filters.startingMonitoring')
              : $t('issues.filters.startMonitoring')
          }}
        </button>
        <button
          v-else
          class="px-4 py-2 text-sm rounded-md bg-error dark:bg-error border border-error dark:border-error text-white dark:text-white hover:bg-error/80 dark:hover:bg-error-dark transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="store.isMonitoringLoading"
          :title="$t('issues.filters.stopMonitoringTitle')"
          @click="handleStopMonitoring"
        >
          {{
            store.isMonitoringLoading ? $t('issues.filters.stoppingMonitoring') : $t('issues.filters.stopMonitoring')
          }}
        </button>

        <!-- Manual Processing (Write permission required) -->
        <button
          class="px-4 py-2 text-sm rounded-md bg-info dark:bg-info border border-info dark:border-info text-white dark:text-white hover:bg-info/80 dark:hover:bg-info transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="store.isProcessing"
          :title="$t('issues.filters.processNowTitle')"
          @click="handleTriggerProcessing"
        >
          {{ store.isProcessing ? $t('issues.filters.processing') : $t('issues.filters.processNow') }}
        </button>

        <!-- Processing Control (Pause/Resume) (Write permission required) -->
        <button
          v-if="!store.processingStatus.paused"
          class="px-4 py-2 text-sm rounded-md bg-warning dark:bg-warning border border-warning dark:border-warning text-white dark:text-white hover:bg-warning/80 dark:hover:bg-warning transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="store.isProcessingLoading"
          :title="$t('issues.filters.pauseQueueTitle')"
          @click="handlePauseProcessing"
        >
          {{ store.isProcessingLoading ? $t('issues.filters.pausing') : $t('issues.filters.pauseQueue') }}
        </button>
        <button
          v-else
          class="px-4 py-2 text-sm rounded-md bg-success dark:bg-success border border-success dark:border-success text-white dark:text-white hover:bg-success/80 dark:hover:bg-success-dark transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="store.isProcessingLoading"
          :title="$t('issues.filters.resumeQueueTitle')"
          @click="handleResumeProcessing"
        >
          {{ store.isProcessingLoading ? $t('issues.filters.resuming') : $t('issues.filters.resumeQueue') }}
        </button>

        <!-- Ingest and Create Cell buttons (Write permission required) -->
        <button
          class="px-4 py-2 text-sm rounded-md bg-surface dark:bg-gray-800 border border-border dark:border-gray-700 text-text-primary dark:text-text-primary hover:bg-surface-hover dark:hover:bg-gray-700 transition-all"
          @click="emit('toggle-ingest')"
        >
          {{ $t('issues.filters.ingestDocs') }}
        </button>

        <button
          class="px-4 py-2 text-sm rounded-md bg-surface dark:bg-gray-800 border border-border dark:border-gray-700 text-text-primary dark:text-text-primary hover:bg-surface-hover dark:hover:bg-gray-700 transition-all"
          @click="emit('toggle-create-cell')"
        >
          {{ $t('issues.filters.newCell') }}
        </button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * IssueFilters Component
 *
 * Provides filtering and action controls for the issues dashboard.
 * Uses Pinia store directly for state management.
 * All styling uses Tailwind CSS classes.
 * 
 * RBAC: Write operations (monitoring, processing, ingest, create) are
 * only visible if user has issues:write permission.
 */
import { useIssuesStore } from '../stores/issuesStore'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:IssuesDashboard:IssueFilters')
const store = useIssuesStore()

// Props
defineProps<{
  hasWritePermission: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle-ingest'): void
  (e: 'toggle-create-cell'): void
}>()

/**
 * Handle start monitoring with error handling
 */
async function handleStartMonitoring() {
  try {
    await store.startMonitoring()
  } catch (err) {
    log.error('Unexpected error starting monitoring', err)
  }
}

/**
 * Handle stop monitoring with error handling
 */
async function handleStopMonitoring() {
  try {
    await store.stopMonitoring()
  } catch (err) {
    log.error('Unexpected error stopping monitoring', err)
  }
}

/**
 * Handle pause processing with error handling
 */
async function handlePauseProcessing() {
  try {
    await store.pauseProcessing()
  } catch (err) {
    log.error('Unexpected error pausing processing', err)
  }
}

/**
 * Handle resume processing with error handling
 */
async function handleResumeProcessing() {
  try {
    await store.resumeProcessing()
  } catch (err) {
    log.error('Unexpected error resuming processing', err)
  }
}

/**
 * Handle trigger processing with error handling
 */
async function handleTriggerProcessing() {
  try {
    await store.triggerProcessing()
  } catch (err) {
    log.error('Unexpected error triggering processing', err)
  }
}
</script>
