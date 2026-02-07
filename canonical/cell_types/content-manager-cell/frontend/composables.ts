/**
 * Content Manager Composable
 * 
 * Provides reactive state and actions for content management operations.
 */

import { ref, computed, type Ref } from 'vue'
import type {
  Content,
  ContentFilters,
  PaginationParams,
  ContentType,
  ContentPersistRequest,
  ContentPersistResponse,
  ContentLoadResponsePresigned,
  ContentLoadResponseDirect,
  ApiResponse,
  ContentListResponse,
  UseContentManagerReturn
} from '../types'

/**
 * Content Manager composable
 * 
 * @param cellId - Cell identifier for API calls
 * @param initialFilters - Initial filter values
 * @param initialPagination - Initial pagination values
 */
export function useContentManager(
  cellId: string,
  initialFilters: ContentFilters = {},
  initialPagination: PaginationParams = { limit: 20, offset: 0 }
): UseContentManagerReturn {
  // State
  const contents = ref<Content[]>([])
  const contentTypes = ref<ContentType[]>([])
  const filters = ref<ContentFilters>({ ...initialFilters })
  const pagination = ref<PaginationParams>({ ...initialPagination })
  const total = ref(0)
  const isLoading = ref(false)
  const errorMessage = ref('')
  const successMessage = ref('')
  
  // Computed
  const hasMore = computed(() => {
    return pagination.value.offset + pagination.value.limit < total.value
  })
  
  const currentPage = computed(() => {
    return Math.floor(pagination.value.offset / pagination.value.limit) + 1
  })
  
  const totalPages = computed(() => {
    return Math.ceil(total.value / pagination.value.limit)
  })
  
  /**
   * Execute cell action via API
   */
  async function executeAction<T>(action: string, params: Record<string, any>): Promise<ApiResponse<T>> {
    const response = await fetch(`/api/cells/${cellId}/execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        action,
        ...params
      })
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error ${response.status}: ${response.statusText}`)
    }
    
    return await response.json()
  }
  
  /**
   * List contents with current filters and pagination
   */
  async function listContents(): Promise<void> {
    isLoading.value = true
    errorMessage.value = ''
    successMessage.value = ''
    
    try {
      const response = await executeAction<ContentListResponse>('list', {
        filters: filters.value,
        limit: pagination.value.limit,
        offset: pagination.value.offset
      })
      
      if (response.success && response.data) {
        contents.value = response.data.contents
        total.value = response.data.total
        successMessage.value = `Loaded ${response.data.count} content(s)`
      } else {
        errorMessage.value = response.error || 'Failed to list contents'
      }
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : 'Failed to list contents'
      console.error('Error listing contents:', error)
    } finally {
      isLoading.value = false
    }
  }
  
  /**
   * Load content by ID
   */
  async function loadContent(
    contentId: string,
    directDownload: boolean = false
  ): Promise<ContentLoadResponsePresigned | ContentLoadResponseDirect | null> {
    isLoading.value = true
    errorMessage.value = ''
    
    try {
      const response = await executeAction<ContentLoadResponsePresigned | ContentLoadResponseDirect>('load', {
        content_id: contentId,
        direct_download: directDownload
      })
      
      if (response.success && response.data) {
        successMessage.value = `Loaded content: ${response.data.filename}`
        return response.data
      } else {
        errorMessage.value = response.error || 'Failed to load content'
        return null
      }
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : 'Failed to load content'
      console.error('Error loading content:', error)
      return null
    } finally {
      isLoading.value = false
    }
  }
  
  /**
   * Persist new content
   */
  async function persistContent(
    request: ContentPersistRequest
  ): Promise<ContentPersistResponse | null> {
    isLoading.value = true
    errorMessage.value = ''
    successMessage.value = ''
    
    try {
      let response: ApiResponse<ContentPersistResponse>
      
      // Check if binary is a File (multipart upload)
      if (request.binary instanceof File) {
        const formData = new FormData()
        formData.append('action', 'persist')
        formData.append('content_type_id', request.content_type_id)
        formData.append('filename', request.filename)
        formData.append('file', request.binary)
        formData.append('fragments', JSON.stringify(request.fragments))
        
        if (request.tags) {
          formData.append('tags', JSON.stringify(request.tags))
        }
        if (request.metadata) {
          formData.append('metadata', JSON.stringify(request.metadata))
        }
        if (request.origin_cell_id) {
          formData.append('origin_cell_id', request.origin_cell_id)
        }
        if (request.assignee_id) {
          formData.append('assignee_id', request.assignee_id)
        }
        
        const httpResponse = await fetch(`/api/cells/${cellId}/execute`, {
          method: 'POST',
          body: formData
        })
        
        if (!httpResponse.ok) {
          throw new Error(`HTTP error ${httpResponse.status}: ${httpResponse.statusText}`)
        }
        
        response = await httpResponse.json()
      } else {
        // JSON request with Base64 binary
        response = await executeAction<ContentPersistResponse>('persist', {
          content_type_id: request.content_type_id,
          filename: request.filename,
          binary: request.binary,
          fragments: request.fragments,
          tags: request.tags,
          metadata: request.metadata,
          origin_cell_id: request.origin_cell_id,
          assignee_id: request.assignee_id
        })
      }
      
      if (response.success && response.data) {
        successMessage.value = `Content persisted: ${response.data.filename}`
        // Refresh list to show new content
        await listContents()
        return response.data
      } else {
        errorMessage.value = response.error || 'Failed to persist content'
        return null
      }
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : 'Failed to persist content'
      console.error('Error persisting content:', error)
      return null
    } finally {
      isLoading.value = false
    }
  }
  
  /**
   * Update filters and refresh list
   */
  function updateFilters(newFilters: Partial<ContentFilters>): void {
    filters.value = { ...filters.value, ...newFilters }
    // Reset to first page when filters change
    pagination.value.offset = 0
  }
  
  /**
   * Go to next page
   */
  async function nextPage(): Promise<void> {
    if (hasMore.value) {
      pagination.value.offset += pagination.value.limit
      await listContents()
    }
  }
  
  /**
   * Go to previous page
   */
  async function previousPage(): Promise<void> {
    if (pagination.value.offset > 0) {
      pagination.value.offset = Math.max(0, pagination.value.offset - pagination.value.limit)
      await listContents()
    }
  }
  
  /**
   * Go to specific page
   */
  async function goToPage(page: number): Promise<void> {
    const newOffset = (page - 1) * pagination.value.limit
    if (newOffset >= 0 && newOffset < total.value) {
      pagination.value.offset = newOffset
      await listContents()
    }
  }
  
  /**
   * Refresh content list
   */
  async function refresh(): Promise<void> {
    await listContents()
  }
  
  /**
   * Clear all filters
   */
  function clearFilters(): void {
    filters.value = {}
    pagination.value.offset = 0
  }
  
  return {
    // State
    contents,
    contentTypes,
    filters,
    pagination,
    total,
    isLoading,
    errorMessage,
    successMessage,
    
    // Computed
    hasMore,
    currentPage,
    totalPages,
    
    // Actions
    listContents,
    loadContent,
    persistContent,
    updateFilters,
    nextPage,
    previousPage,
    goToPage,
    refresh,
    clearFilters
  }
}
