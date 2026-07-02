/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-05-13",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div class="flex flex-col h-full bg-surface dark:bg-surface-dark overflow-hidden">
    <!-- Header -->
    <div class="flex justify-between items-start p-6 pb-4 border-b-2 border-gray-200 dark:border-gray-700">
      <div class="flex flex-col gap-1">
        <h2 class="m-0 text-2xl text-text-primary dark:text-text-primary-dark font-semibold">
          Content Explorer
        </h2>
        <div class="flex items-center gap-1 text-sm text-text-secondary dark:text-text-secondary-dark">
          <span class="font-semibold">Browse Assets by Type</span>
        </div>
      </div>
      
      <div class="flex gap-2">
        <!-- View mode toggle -->
        <div class="flex gap-1 p-1 bg-surface-hover dark:bg-surface rounded-md border border-border dark:border-border-dark">
          <button
            class="px-2 py-1 text-xs rounded transition-colors"
            :class="viewMode === 'grid' ? 'bg-primary text-white' : 'text-text-secondary dark:text-text-secondary-dark hover:bg-surface dark:hover:bg-surface-hover'"
            @click="viewMode = 'grid'"
            title="Grid view"
          >
            Grid
          </button>
          <button
            class="px-2 py-1 text-xs rounded transition-colors"
            :class="viewMode === 'list' ? 'bg-primary text-white' : 'text-text-secondary dark:text-text-secondary-dark hover:bg-surface dark:hover:bg-surface-hover'"
            @click="viewMode = 'list'"
            title="List view"
          >
            List
          </button>
        </div>
        
        <button
          class="px-3 py-2 text-sm font-medium text-white dark:text-text-primary-dark bg-primary dark:bg-primary-dark rounded-md hover:bg-primary-hover dark:hover:bg-primary focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 transition-colors"
          :disabled="isLoading"
          @click="handleRefresh"
        >
          {{ isLoading ? 'Loading...' : 'Refresh' }}
        </button>
      </div>
    </div>
    
    <!-- Messages -->
    <div v-if="errorMessage" class="mx-6 mt-4 p-3 bg-error/10 border border-error/30 rounded text-error text-sm">
      {{ errorMessage }}
    </div>
    <div v-if="successMessage" class="mx-6 mt-4 p-3 bg-success/10 border border-success/30 rounded text-success text-sm">
      {{ successMessage }}
    </div>
    
    <!-- Main content -->
    <div class="flex flex-1 gap-4 p-6 overflow-hidden">
      <!-- Left sidebar: Type selector -->
      <div class="w-64 flex-shrink-0 bg-surface-hover dark:bg-surface border border-border dark:border-border-dark rounded-md overflow-hidden">
        <TypeSelector
          :types="types"
          :selected-type-id="selectedTypeId"
          :disabled="isLoading"
          @select-type="handleSelectType"
        />
      </div>
      
      <!-- Right content: Asset grid -->
      <div class="flex-1 flex flex-col gap-4 overflow-hidden">
        <!-- Filters (only show when type is selected) -->
        <div
          v-if="selectedTypeId"
          class="flex flex-wrap gap-3 p-4 bg-surface-hover dark:bg-surface border border-border dark:border-border-dark rounded-md"
        >
          <div class="flex-1 min-w-[150px]">
            <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-1">
              Latest Only
            </label>
            <select
              v-model="filters.is_latest"
              class="w-full px-3 py-2 text-sm border border-border dark:border-border-dark rounded-md bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark focus:outline-none focus:ring-2 focus:ring-primary"
              :disabled="isLoading"
              @change="handleFilterChange"
            >
              <option :value="null">{{ $t('artifacts.contentExplorer.allVersions') }}</option>
              <option :value="true">{{ $t('artifacts.contentExplorer.latestOnly') }}</option>
              <option :value="false">{{ $t('artifacts.contentExplorer.olderVersions') }}</option>
            </select>
          </div>
          
          <div class="flex items-end">
            <button
              class="px-3 py-2 text-sm font-medium text-text-secondary dark:text-text-secondary-dark bg-surface dark:bg-surface-dark rounded-md hover:bg-surface-hover dark:hover:bg-surface border border-border dark:border-border-dark focus:outline-none focus:ring-2 focus:ring-border transition-colors"
              :disabled="isLoading"
              @click="handleClearFilters"
            >
              Clear
            </button>
          </div>
        </div>
        
        <!-- Asset grid -->
        <div class="flex-1 overflow-y-auto">
          <div v-if="isLoading && assets.length === 0" class="flex items-center justify-center h-64">
            <div class="text-text-secondary dark:text-text-secondary-dark">Loading...</div>
          </div>
          
          <div v-else-if="!selectedTypeId" class="flex flex-col items-center justify-center h-full text-text-secondary dark:text-text-secondary-dark">
            <div class="text-6xl mb-4">👈</div>
            <div class="text-lg font-medium mb-2">Select a content type</div>
            <div class="text-sm">Choose a type from the sidebar to view assets</div>
          </div>
          
          <AssetGrid
            v-else
            :assets="assets"
            :view-mode="viewMode"
            :disabled="isLoading"
            @delete-asset="handleDeleteAsset"
            @view-asset="handleViewAsset"
          />
        </div>
        
        <!-- Pagination -->
        <div
          v-if="selectedTypeId && totalAssets > 0"
          class="flex justify-between items-center p-4 bg-surface-hover dark:bg-surface border border-border dark:border-border-dark rounded-md"
        >
          <div class="text-sm text-text-secondary dark:text-text-secondary-dark">
            Showing {{ Math.min(pagination.offset + 1, totalAssets) }}-{{ Math.min(pagination.offset + pagination.limit, totalAssets) }} of {{ totalAssets }}
          </div>
          
          <div class="flex gap-2">
            <button
              class="px-3 py-1 text-sm font-medium text-text-primary dark:text-text-primary-dark bg-surface dark:bg-surface-dark rounded-md hover:bg-surface-hover dark:hover:bg-surface border border-border dark:border-border-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              :disabled="!hasPreviousPage || isLoading"
              @click="handlePreviousPage"
            >
              Previous
            </button>
            
            <div class="flex items-center px-3 text-sm text-text-primary dark:text-text-primary-dark">
              Page {{ currentPage }} of {{ totalPages }}
            </div>
            
            <button
              class="px-3 py-1 text-sm font-medium text-text-primary dark:text-text-primary-dark bg-surface dark:bg-surface-dark rounded-md hover:bg-surface-hover dark:hover:bg-surface border border-border dark:border-border-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              :disabled="!hasNextPage || isLoading"
              @click="handleNextPage"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete Confirm Modal -->
    <ConfirmModal
      :visible="showDeleteConfirmModal"
      title="Delete Asset"
      message="Are you sure you want to delete this asset? This action cannot be undone."
      confirm-text="Delete"
      cancel-text="Cancel"
      :danger="true"
      :loading="deleteLoading"
      :error="deleteError"
      @confirm="onConfirmDelete"
      @cancel="onCancelDelete"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * Content Explorer Cell View
 * 
 * Main UI component for browsing and managing assets by type.
 * Composes TypeSelector, AssetGrid, and asset management functionality.
 */

import { ref, onMounted, inject } from 'vue'
import { useContentExplorer } from './composables'
import TypeSelector from './components/TypeSelector.vue'
import AssetGrid from './components/AssetGrid.vue'
import type { AssetItem } from './ContentExplorerCell'
import ConfirmModal from '#shared/components/ConfirmModal.vue'
import { CELL_FACTORY_KEY } from '#canonical/shared/cellFactory'
import type { CellFactory } from '#canonical/shared/cellFactory'
import { createLogger } from '@/utils/logger'

const logger = createLogger('component:content-explorer-cell')

// Props
interface Props {
  cellId?: string
  initialData?: Record<string, any>
}

const props = defineProps<Props>()

// Composable
const {
  isLoading,
  errorMessage,
  successMessage,
  types,
  selectedTypeId,
  assets,
  totalAssets,
  filters,
  pagination,
  hasNextPage,
  hasPreviousPage,
  currentPage,
  totalPages,
  loadData,
  selectType,
  updateFilters,
  clearFilters,
  nextPage,
  previousPage,
  deleteAsset,
  clearMessages
} = useContentExplorer()

// Local state
const viewMode = ref<'grid' | 'list'>('grid')

// Delete confirm modal state
const showDeleteConfirmModal = ref(false)
const pendingDeleteAssetId = ref<string | null>(null)
const deleteLoading = ref(false)
const deleteError = ref<string | null>(null)

// CellFactory injection for opening viewer cells
const cellFactory = inject<CellFactory>(CELL_FACTORY_KEY)

// Content type → viewer cell type mapping
const viewerTypeMap: Record<string, string> = {
  'image-png': 'image-content-cell',
  'image-jpg': 'image-content-cell',
  'vector-svg': 'image-content-cell',
  '3d-glb': 'glb-content-viewer',
  '3d-obj': 'glb-content-viewer',
}

// Handlers
async function handleRefresh() {
  clearMessages()
  await loadData()
}

async function handleSelectType(typeId: string) {
  clearMessages()
  await selectType(typeId)
}

async function handleFilterChange() {
  clearMessages()
  await updateFilters({})
}

async function handleClearFilters() {
  clearMessages()
  await clearFilters()
}

async function handlePreviousPage() {
  clearMessages()
  await previousPage()
}

async function handleNextPage() {
  clearMessages()
  await nextPage()
}

async function handleDeleteAsset(assetId: string) {
  pendingDeleteAssetId.value = assetId
  showDeleteConfirmModal.value = true
}

async function onConfirmDelete() {
  deleteLoading.value = true
  deleteError.value = null
  try {
    await deleteAsset(pendingDeleteAssetId.value!)
    showDeleteConfirmModal.value = false
    pendingDeleteAssetId.value = null
  } catch (error) {
    deleteError.value = error instanceof Error ? error.message : 'Failed to delete asset'
  } finally {
    deleteLoading.value = false
  }
}

function onCancelDelete() {
  showDeleteConfirmModal.value = false
  pendingDeleteAssetId.value = null
  deleteError.value = null
}

async function handleViewAsset(asset: AssetItem) {
  const viewerType = viewerTypeMap[asset.content_type_id]
  if (!viewerType || !cellFactory) {
    logger.warn('No viewer available for type=%s or cellFactory not injected', asset.content_type_id)
    return
  }

  logger.info('Opening asset in viewer: viewerType=%s, contentId=%s, data_ref=%s',
    viewerType, asset.id, asset.data_ref)

  try {
    await cellFactory.addChildCell(viewerType, {
      content_id: asset.id,
      relative_url: asset.data_ref || undefined,
    })
    logger.info('Viewer cell created: %s for asset %s', viewerType, asset.id)
  } catch (err: any) {
    logger.error('Failed to open viewer cell %s for asset %s: %s', viewerType, asset.id, err)
  }
}

// Initialize
onMounted(async () => {
  // Apply initial data if provided
  if (props.initialData) {
    if (props.initialData.selected_type_id) {
      selectedTypeId.value = props.initialData.selected_type_id
    }
    if (props.initialData.view_mode) {
      viewMode.value = props.initialData.view_mode
    }
    if (props.initialData.filters) {
      Object.assign(filters.value, props.initialData.filters)
    }
  }
  
  // Load initial data
  await loadData()
})
</script>
