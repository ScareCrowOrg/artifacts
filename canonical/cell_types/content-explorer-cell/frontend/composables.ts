/**
 * @file composables.ts
 * @description Composables for Content Explorer Cell
 * 
 * Provides reactive state management and data fetching for the
 * content explorer interface.
 */

import { ref, computed, type Ref } from 'vue'
import { createContentExplorerCell, type ContentTypeMetadata } from './ContentExplorerCell'
import type { AssetItem, ExplorerFilters } from './ContentExplorerCell'

/**
 * Composable for content explorer functionality
 */
export function useContentExplorer() {
  // State
  const isLoading = ref(false)
  const errorMessage = ref<string | null>(null)
  const successMessage = ref<string | null>(null)
  
  const types = ref<ContentTypeMetadata[]>([])
  const selectedTypeId = ref<string | null>(null)
  const assets = ref<AssetItem[]>([])
  const totalAssets = ref(0)
  
  const filters = ref<ExplorerFilters>({
    assignee_id: null,
    tags: [],
    is_latest: true
  })
  
  const pagination = ref({
    limit: 20,
    offset: 0
  })
  
  // Create cell instance
  const cell = createContentExplorerCell()
  
  /**
   * Load content types and optionally assets
   */
  async function loadData() {
    isLoading.value = true
    errorMessage.value = null
    
    try {
      const result = await cell.execute({
        action: 'list',
        selected_type_id: selectedTypeId.value,
        filters: filters.value,
        limit: pagination.value.limit,
        offset: pagination.value.offset
      })
      
      if (result.success && result.output) {
        // Update types
        if (result.output.types) {
          types.value = result.output.types.types || []
        }
        
        // Update assets if present
        if (result.output.assets) {
          assets.value = result.output.assets.items || []
          totalAssets.value = result.output.assets.total || 0
        } else {
          assets.value = []
          totalAssets.value = 0
        }
      } else {
        throw new Error(result.output?.error || 'Failed to load data')
      }
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : 'Unknown error'
      types.value = []
      assets.value = []
    } finally {
      isLoading.value = false
    }
  }
  
  /**
   * Select a content type and load its assets
   */
  async function selectType(typeId: string | null) {
    selectedTypeId.value = typeId
    pagination.value.offset = 0 // Reset pagination
    await loadData()
  }
  
  /**
   * Update filters and reload
   */
  async function updateFilters(newFilters: Partial<ExplorerFilters>) {
    filters.value = { ...filters.value, ...newFilters }
    pagination.value.offset = 0 // Reset pagination
    await loadData()
  }
  
  /**
   * Clear all filters
   */
  async function clearFilters() {
    filters.value = {
      assignee_id: null,
      tags: [],
      is_latest: true
    }
    pagination.value.offset = 0
    await loadData()
  }
  
  /**
   * Go to next page
   */
  async function nextPage() {
    if (pagination.value.offset + pagination.value.limit < totalAssets.value) {
      pagination.value.offset += pagination.value.limit
      await loadData()
    }
  }
  
  /**
   * Go to previous page
   */
  async function previousPage() {
    if (pagination.value.offset > 0) {
      pagination.value.offset = Math.max(0, pagination.value.offset - pagination.value.limit)
      await loadData()
    }
  }
  
  /**
   * Delete an asset (via ContentManagerCell)
   */
  async function deleteAsset(assetId: string) {
    isLoading.value = true
    errorMessage.value = null
    successMessage.value = null
    
    try {
      // Call ContentManagerCell delete endpoint
      const response = await fetch('/api/cells/execute-ephemeral', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          cell_type: 'content-manager-cell',
          input_data: {
            action: 'delete',
            content_id: assetId
          }
        })
      })
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      
      const result = await response.json()
      
      if (result.success !== false) {
        successMessage.value = 'Asset deleted successfully'
        // Reload data to refresh list
        await loadData()
      } else {
        throw new Error(result.error || 'Failed to delete asset')
      }
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : 'Failed to delete asset'
    } finally {
      isLoading.value = false
    }
  }
  
  /**
   * Clear messages
   */
  function clearMessages() {
    errorMessage.value = null
    successMessage.value = null
  }
  
  // Computed
  const hasNextPage = computed(() => {
    return pagination.value.offset + pagination.value.limit < totalAssets.value
  })
  
  const hasPreviousPage = computed(() => {
    return pagination.value.offset > 0
  })
  
  const currentPage = computed(() => {
    return Math.floor(pagination.value.offset / pagination.value.limit) + 1
  })
  
  const totalPages = computed(() => {
    return Math.ceil(totalAssets.value / pagination.value.limit)
  })
  
  return {
    // State
    isLoading,
    errorMessage,
    successMessage,
    types,
    selectedTypeId,
    assets,
    totalAssets,
    filters,
    pagination,
    
    // Computed
    hasNextPage,
    hasPreviousPage,
    currentPage,
    totalPages,
    
    // Actions
    loadData,
    selectType,
    updateFilters,
    clearFilters,
    nextPage,
    previousPage,
    deleteAsset,
    clearMessages
  }
}
