/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-02-22",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-02-22",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0,
 *   "rbac_protected": true,
 *   "required_permissions": ["issues:read"],
 *   "optional_permissions": ["issues:write"]
 * }
 */
<template>
  <div
    class="flex flex-col h-screen bg-background text-text-secondary dark:text-text-secondary-dark overflow-hidden"
  >
    <!-- Header -->
    <div
      class="flex justify-between items-center p-4 bg-surface border-b border-border dark:bg-surface-dark dark:border-border-dark"
    >
      <h1 class="m-0 text-2xl font-semibold">{{ $t('issues.dashboard.title') }}</h1>
      <button
        class="bg-transparent border-none text-text-secondary dark:text-text-secondary-dark text-2xl cursor-pointer px-2 py-1 hover:text-text-primary dark:hover:text-text-primary-dark transition-colors"
        :aria-label="$t('issues.dashboard.closeAriaLabel')"
        @click="$emit('close')"
      >
        ✕
      </button>
    </div>

    <!-- RBAC Permission Warning (Read-Only Mode) -->
    <div
      v-if="!hasWritePermission"
      class="flex items-center gap-2 px-6 py-3 bg-warning/20 border-b border-border dark:border-border-dark"
    >
      <span class="text-xl leading-none text-warning">🔒</span>
      <span class="text-sm text-text-secondary dark:text-text-secondary-dark">
        {{ $t('issues.dashboard.readOnlyMode') }} - {{ $t('issues.dashboard.needsWritePermission') }}
      </span>
    </div>

    <!-- Stats Bar -->
    <IssueStats :stats="store.issuesByState" />

    <!-- Filters and Actions -->
    <IssueFilters
      :has-write-permission="hasWritePermission"
      @toggle-ingest="showIngestForm = !showIngestForm"
      @toggle-create-cell="showCreateCellForm = !showCreateCellForm"
    />

    <!-- Monitoring Status Bar -->
    <div
      v-if="store.monitoringStatus.active"
      class="flex items-center gap-2 px-6 py-3 bg-success/20 border-b border-border dark:border-border-dark"
    >
      <span class="text-base leading-none text-success animate-pulse">●</span>
      <span class="text-sm text-text-secondary dark:text-text-secondary-dark">
        {{ $t('issues.dashboard.monitoringActive', { 
          interval: store.monitoringStatus.polling_interval, 
          maxCells: store.monitoringStatus.max_concurrent_cells 
        }) }}
      </span>
    </div>

    <!-- Processing Status Bar -->
    <div
      v-if="store.processingStatus.paused"
      class="flex items-center gap-2 px-6 py-3 bg-warning/20 border-b border-border dark:border-border-dark"
    >
      <span class="text-xl leading-none text-warning">⏸</span>
      <span class="text-sm text-text-secondary dark:text-text-secondary-dark">
        {{ $t('issues.dashboard.processingPaused') }}
      </span>
    </div>

    <!-- Ingest Form (Only if has write permission) -->
    <IngestForm 
      v-if="showIngestForm && hasWritePermission" 
      @close="showIngestForm = false" 
    />

    <!-- Create Cell Form (Only if has write permission) -->
    <CreateCellForm
      v-if="showCreateCellForm && hasWritePermission"
      @close="showCreateCellForm = false"
    />

    <!-- Error Display -->
    <div
      v-if="store.error"
      class="flex justify-between items-center px-6 py-4 bg-error/20 text-error border-b border-border dark:border-border-dark"
      role="alert"
    >
      ⚠️ {{ store.error }}
      <button
        class="bg-transparent border-none text-error text-xl cursor-pointer px-2"
        @click="store.error = null"
      >
        ✕
      </button>
    </div>

    <!-- Main Content -->
    <div class="flex flex-1 overflow-hidden">
      <!-- Issues List -->
      <div class="flex flex-col flex-1 border-r border-border dark:border-border-dark">
        <IssueList :has-write-permission="hasWritePermission" />

        <!-- Pagination -->
        <Pagination
          v-if="!store.isLoading && store.filteredIssues.length > 0"
        />
      </div>

      <!-- Pipeline Activity Feed (when no issue selected) -->
      <PipelineActivityFeed
        v-if="!store.selectedIssue"
        :activity-feed="store.pipelineActivityFeed"
      />

      <!-- Issue Details (when issue selected) -->
      <IssueDetails
        v-if="store.selectedIssue"
        :issue="store.selectedIssue"
        :pipeline-items-history="store.pipelineItemsHistory"
        :is-loading-pipeline-history="store.isLoadingPipelineHistory"
        :has-write-permission="hasWritePermission"
        @close="store.clearSelection()"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Issues Dashboard View Component
 *
 * Main container for the issues dashboard within the issues-dashboard-cell.
 * Orchestrates sub-components with RBAC-aware controls.
 * 
 * RBAC Features:
 * - Displays read-only warning if user lacks write permission
 * - Hides/disables write actions (create, edit, delete) without write permission
 * - All users with issues:read can view issues
 * - Only users with issues:write can modify issues
 * 
 * Uses Pinia store directly. All styling uses Tailwind CSS.
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import IssueStats from './components/IssueStats.vue'
import IssueFilters from './components/IssueFilters.vue'
import IssueList from './components/IssueList.vue'
import Pagination from './components/Pagination.vue'
import IngestForm from './components/IngestForm.vue'
import CreateCellForm from './components/CreateCellForm.vue'
import PipelineActivityFeed from './components/PipelineActivityFeed.vue'
import IssueDetails from './components/IssueDetails.vue'
import { useIssuesStore } from './stores/issuesStore'
import { usePermissionsStore } from '@/stores/permissions'
import { createLogger } from '@/utils/logger'

const log = createLogger('cells:IssuesDashboard:View')

// Props & Emits
defineEmits(['close'])

// Store
const store = useIssuesStore()
const permissionsStore = usePermissionsStore()

// RBAC: Check permissions
const hasWritePermission = computed(() => {
  return permissionsStore.hasPermission('issues:write')
})

// Log permission status
log.debug('Permission status', {
  hasWrite: hasWritePermission.value,
  userPermissions: permissionsStore.userPermissions
})

// Local state
const showIngestForm = ref(false)
const showCreateCellForm = ref(false)

// Lifecycle
onMounted(() => {
  log.debug('Issues Dashboard View mounted')
  store.loadIssues()
  store.loadMonitoringStatus()
  store.loadProcessingStatus()
  store.loadNotebookItemTypes()
  store.connectSSE()
  store.startPipelineStream()
})

onUnmounted(() => {
  log.debug('Issues Dashboard View unmounted')
  store.disconnectSSE()
  store.stopPipelineStream()
})
</script>
