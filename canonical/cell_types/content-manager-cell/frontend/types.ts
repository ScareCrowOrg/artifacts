/**
 * Content Manager Cell Type Definitions
 * 
 * Defines TypeScript interfaces and types for the Content Manager cell.
 */

import type { Ref } from 'vue'

/**
 * Content metadata structure
 */
export interface Content {
  /** Unique content identifier */
  id: string
  /** ContentType identifier (e.g., "image-png", "vector-svg") */
  content_type_id: string
  /** Original filename */
  filename: string
  /** File size in bytes */
  size_bytes: number
  /** Creation timestamp */
  created_at: string | null
  /** Content-specific metadata */
  fragments: Record<string, any>
  /** Storage reference (r2://, file://) */
  data_ref: string
  /** Content tags */
  tags: string[]
  /** Version number */
  version: number
  /** Whether this is the latest version */
  is_latest: boolean
  /** Origin cell identifier for lineage tracking */
  origin_cell_id: string | null
}

/**
 * Content list response
 */
export interface ContentListResponse {
  /** List of contents */
  contents: Content[]
  /** Number of contents in current page */
  count: number
  /** Page limit */
  limit: number
  /** Page offset */
  offset: number
  /** Total number of contents */
  total: number
}

/**
 * Content load response (presigned URL)
 */
export interface ContentLoadResponsePresigned {
  /** Content identifier */
  content_id: string
  /** Filename */
  filename: string
  /** Presigned download URL */
  presigned_url: string
  /** URL expiration time in seconds */
  presigned_expires_in: number
  /** File size */
  size_bytes: number
  /** MIME type */
  mime_type: string
  /** Content fragments */
  fragments: Record<string, any>
}

/**
 * Content load response (direct download)
 */
export interface ContentLoadResponseDirect {
  /** Content identifier */
  content_id: string
  /** Filename */
  filename: string
  /** Base64-encoded binary data */
  binary: string
  /** File size */
  size_bytes: number
  /** MIME type */
  mime_type: string
  /** Content fragments */
  fragments: Record<string, any>
}

/**
 * Content persist request
 */
export interface ContentPersistRequest {
  /** ContentType identifier */
  content_type_id: string
  /** Filename */
  filename: string
  /** Base64-encoded binary or FormData (required if source_path not provided) */
  binary?: string | File
  /** Path to file already on disk (Redis Magro: avoids binary re-transmission). Alternative to binary. */
  source_path?: string
  /** Content-specific metadata */
  fragments: Record<string, any>
  /** Optional tags */
  tags?: string[]
  /** Optional metadata */
  metadata?: Record<string, any>
  /** Optional origin cell ID */
  origin_cell_id?: string
  /** Optional assignee ID */
  assignee_id?: string
}

/**
 * Content persist response
 */
export interface ContentPersistResponse {
  /** Created content ID */
  id: string
  /** ContentType ID */
  content_type_id: string
  /** Filename */
  filename: string
  /** File size */
  size_bytes: number
  /** Storage reference */
  data_ref: string
  /** Version number */
  version: number
  /** Creation timestamp */
  created_at: string | null
  /** Content fragments */
  fragments: Record<string, any>
  /** Tags */
  tags: string[]
  /** Origin cell ID */
  origin_cell_id: string | null
}

/**
 * Content query filters
 */
export interface ContentFilters {
  /** Filter by ContentType */
  content_type_id?: string | null
  /** Filter by assignee */
  assignee_id?: string | null
  /** Filter by tags */
  tags?: string[]
  /** Filter by latest version */
  is_latest?: boolean
}

/**
 * Pagination parameters
 */
export interface PaginationParams {
  /** Page limit (1-100) */
  limit: number
  /** Page offset (>=0) */
  offset: number
}

/**
 * Content manager cell initial data
 */
export interface ContentManagerInitialData {
  /** Whether to show persistence form */
  show_persistence_form: boolean
  /** Default ContentType ID for persistence form */
  default_content_type_id: string | null
  /** Default filters for listing */
  filters: ContentFilters
  /** Default pagination */
  pagination: PaginationParams
  /** Cell category */
  category: 'persistent'
  /** Cell icon */
  icon: string
}

/**
 * Content manager cell instance
 */
export interface ContentManagerCell {
  /** Unique cell identifier */
  id: string
  /** Cell type identifier */
  type: 'content-manager-cell'
  /** Initial cell data */
  initial_data: ContentManagerInitialData
  /** Creation timestamp */
  created_at?: string
  /** Last update timestamp */
  updated_at?: string
}

/**
 * ContentType definition
 */
export interface ContentType {
  /** Unique identifier */
  id: string
  /** Human-readable name */
  name: string
  /** Description */
  description?: string
  /** MIME type */
  mime_type: string
  /** Schema version */
  version: string
  /** Expected fragments schema */
  expected_fragments: Record<string, any>
  /** Storage policy */
  storage_policy: string
  /** Maximum file size in bytes */
  max_size_bytes: number
}

/**
 * API response wrapper
 */
export interface ApiResponse<T> {
  /** Success flag */
  success: boolean
  /** Action name */
  action?: string
  /** Response data */
  data?: T
  /** Error message */
  error?: string
}

/**
 * Content manager composable return type
 */
export interface UseContentManagerReturn {
  // State
  /** List of contents */
  contents: Ref<Content[]>
  /** Available ContentTypes */
  contentTypes: Ref<ContentType[]>
  /** Current filters */
  filters: Ref<ContentFilters>
  /** Pagination params */
  pagination: Ref<PaginationParams>
  /** Total number of contents */
  total: Ref<number>
  /** Loading state */
  isLoading: Ref<boolean>
  /** Error message */
  errorMessage: Ref<string>
  /** Success message */
  successMessage: Ref<string>
  
  // Computed
  /** Whether there are more pages */
  hasMore: Ref<boolean>
  /** Current page number */
  currentPage: Ref<number>
  /** Total pages */
  totalPages: Ref<number>
  
  // Actions
  /** List contents with current filters */
  listContents: () => Promise<void>
  /** Load content by ID */
  loadContent: (contentId: string, directDownload?: boolean) => Promise<ContentLoadResponsePresigned | ContentLoadResponseDirect | null>
  /** Persist new content */
  persistContent: (request: ContentPersistRequest) => Promise<ContentPersistResponse | null>
  /** Update filters */
  updateFilters: (newFilters: Partial<ContentFilters>) => void
  /** Go to next page */
  nextPage: () => Promise<void>
  /** Go to previous page */
  previousPage: () => Promise<void>
  /** Go to specific page */
  goToPage: (page: number) => Promise<void>
  /** Refresh content list */
  refresh: () => Promise<void>
  /** Clear all filters */
  clearFilters: () => void
}
