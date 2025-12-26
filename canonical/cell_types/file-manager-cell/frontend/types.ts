/**
 * FileManagerCell Type Definitions
 * 
 * Defines TypeScript interfaces and types for the File Manager cell.
 */

import type { Ref } from 'vue'

/**
 * File tree node structure
 */
export interface FileTreeNode {
  /** File or directory name */
  name: string
  /** Relative path from root */
  path: string
  /** Whether this is a directory */
  isDirectory: boolean
  /** Child nodes (for directories) */
  children?: FileTreeNode[]
  /** Whether children have been loaded */
  loaded?: boolean
  /** File size in bytes (for files) */
  size?: number
  /** Last modified timestamp */
  modified?: string
}

/**
 * File manager cell initial data
 */
export interface FileManagerInitialData {
  /** Current search query */
  searchQuery?: string
  /** Array of selected file paths */
  selectedFiles?: string[]
  /** Array of expanded directory paths */
  expandedPaths?: string[]
  /** Cell category (always "ephemeral") */
  category: 'ephemeral'
  /** Cell icon */
  icon: string
}

/**
 * File manager cell instance
 */
export interface FileManagerCell {
  /** Unique cell identifier */
  id: string
  /** Cell type identifier */
  type: 'file-manager-cell'
  /** Initial cell data */
  initial_data: FileManagerInitialData
  /** Creation timestamp */
  created_at?: string
  /** Last update timestamp */
  updated_at?: string
}

/**
 * File operation result
 */
export interface FileOperationResult {
  /** Whether operation succeeded */
  success: boolean
  /** Success or error message */
  message: string
  /** Additional result data */
  data?: any
}

/**
 * File manager composable return type
 */
export interface UseFileManagerReturn {
  // State
  /** File tree data */
  tree: Ref<FileTreeNode[]>
  /** Filtered tree based on search */
  displayTree: Ref<FileTreeNode[]>
  /** Currently selected file paths */
  selectedFiles: Ref<string[]>
  /** Expanded directory paths */
  expandedPaths: Ref<Set<string>>
  /** Search query string */
  searchQuery: Ref<string>
  /** Loading state */
  isLoading: Ref<boolean>
  /** Error message */
  errorMessage: Ref<string>
  /** Success message */
  successMessage: Ref<string>
  
  // Computed
  /** Number of selected files */
  selectedCount: Ref<number>
  /** Whether search has no matches */
  hasNoMatches: Ref<boolean>
  
  // Actions
  /** Load or refresh the file tree */
  refreshTree: () => Promise<void>
  /** Toggle file selection */
  toggleSelection: (path: string) => void
  /** Clear all selections */
  clearSelection: () => void
  /** Toggle directory expansion */
  toggleExpanded: (path: string) => void
  /** Collapse all directories */
  collapseAll: () => void
  /** Update search query */
  updateSearchQuery: (query: string) => void
  /** Open selected files in FileEditorCell */
  openSelectedFiles: () => Promise<void>
  /** Create new file */
  createNewFile: (fileName: string, folder?: string) => Promise<void>
  /** Create new file editor directly with editable filename/path */
  createNewFileEditor: () => Promise<void>
  /** Move file or directory */
  moveItem: (sourcePath: string, destPath: string) => Promise<void>
  /** Delete file or directory */
  deleteItem: (path: string) => Promise<void>
  /** Send selected files to chat as attachments - ITERATION 2 */
  sendSelectedToChat: () => Promise<void>
}
