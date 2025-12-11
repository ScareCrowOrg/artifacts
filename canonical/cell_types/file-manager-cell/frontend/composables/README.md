---
processed: true
processed_date: 2025-12-11
themes:
  - composables
  - business-logic
  - typescript
  - vue3
modules:
  - cockpit-vue
generated_docs:
  - docs/official/cockpit-vue/cell-lifecycle/file-manager-cell.md
code_verified: true
dead_docs_found: false
---
# Composables

## Overview

This directory contains Vue 3 composables that encapsulate reusable business logic for the FileManagerCell.

## Files

### useFileManager.ts (471 lines)

The main composable that provides file management functionality.

**State Management**:
- `tree`: File tree data (hierarchical)
- `displayTree`: Filtered tree based on search
- `selectedFiles`: Array of selected file paths
- `expandedPaths`: Set of expanded directory paths
- `searchQuery`: Current search filter
- `isLoading`: Loading state
- `errorMessage`: Error feedback
- `successMessage`: Success feedback

**Computed Properties**:
- `selectedCount`: Number of selected files
- `hasNoMatches`: Whether search has no results

**Actions**:
- `refreshTree()`: Load/refresh tree with cache invalidation
- `toggleSelection(path)`: Toggle file selection
- `clearSelection()`: Clear all selections
- `toggleExpanded(path)`: Toggle directory expansion
- `collapseAll()`: Collapse all directories
- `updateSearchQuery(query)`: Update search filter
- `openSelectedFiles()`: Open files in FileEditorCell
- `createNewFile(fileName, folder)`: Create new file
- `moveItem(source, dest)`: Move file/directory (TODO)
- `deleteItem(path)`: Delete file/directory (TODO)

**API Integration**:
- `POST /api/tree-refresh`: Invalidate backend cache
- `GET /api/tree?format=flat`: Load file tree
- `POST /api/cells/create`: Create FileEditorCell instances

## Usage

```typescript
import { useFileManager } from './useFileManager'
import type { FileManagerCell } from '../types'

// In component setup
const cell = ref<FileManagerCell>(props.cell)

const {
  displayTree,
  selectedFiles,
  searchQuery,
  isLoading,
  refreshTree,
  openSelectedFiles
} = useFileManager(cell)

// In template
<template>
  <input v-model="searchQuery" />
  <button @click="refreshTree">Refresh</button>
  <button @click="openSelectedFiles">Open</button>
  <FileTree :nodes="displayTree" />
</template>
```

## Architecture

### Composable Pattern Benefits

1. **Separation of Concerns**: UI logic separated from business logic
2. **Reusability**: Logic can be used in multiple components
3. **Testability**: Easy to test without mounting Vue components
4. **Type Safety**: Full TypeScript support

### Cache Invalidation Flow

```typescript
async function refreshTree() {
  // 1. Invalidate backend cache
  await apiService.fetch(ENDPOINTS.treeRefresh, { method: 'POST' })
  
  // 2. Load fresh tree data
  const response = await apiService.fetch(ENDPOINTS.tree)
  
  // 3. Build hierarchy
  tree.value = buildTreeFromFlatList(data.items)
}
```

### File Opening Flow

```typescript
async function openSelectedFiles() {
  for (const filePath of selectedFiles.value) {
    // Create FileEditorCell for each file
    await cellsStore.addCell({
      type: 'file-editor-v2',
      initial_data: {
        fileName,
        filePath,
        language: getLanguageFromExtension(fileName),
        category: 'efemera'
      }
    })
  }
}
```

## Testing (Pending - Phase 2.1.4)

### Unit Tests

```typescript
import { describe, it, expect, vi } from 'vitest'
import { useFileManager } from './useFileManager'

describe('useFileManager', () => {
  it('should filter tree by search query', () => {
    // Test implementation
  })
  
  it('should invalidate cache on refresh', async () => {
    // Test implementation
  })
  
  it('should open selected files in FileEditorCell', async () => {
    // Test implementation
  })
})
```

### Coverage Target
- **Target**: 90% coverage (RULESET.md Rule 3.1)
- **Status**: Pending implementation

## Standards Compliance

- ✅ **RULESET.md Rule 1.1**: File < 500 lines (471 lines)
- ✅ **RULESET.md Rule 4.5**: 100% TypeScript
- ✅ **TypeScript Compilation**: Passes type checking

## References

- [useFileManager.ts](./useFileManager.ts) - Implementation
- [types.ts](../types.ts) - Type definitions
- [View.vue](../View.vue) - Usage example
- [Complete Documentation](../../docs/README.md)

---

**Version**: 1.0.0  
**TypeScript**: 100%  
**Lines**: 471  
**Test Coverage**: Pending
