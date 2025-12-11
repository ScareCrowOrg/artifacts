# File Manager Cell

## Overview

The **FileManagerCell** is an ephemeral cell type that provides a comprehensive file management interface for the ScareVerse Cockpit. It allows users to browse, search, and manage files in the project directory with a tree view interface.

## Key Features

### Core Functionality
- **File Tree Visualization**: Hierarchical tree view of all project files and directories
- **Search**: Real-time search filtering by file name
- **File Selection**: Multiple file selection with visual feedback
- **Cache Invalidation**: Refresh button invalidates backend Redis cache for up-to-date listings
- **Bidirectional Integration**: Opens files directly in FileEditorCell instances

### Action Buttons

| Button | Icon | Description | Functionality |
|--------|------|-------------|---------------|
| **Atualizar** | 🔄 | Refresh tree and invalidate cache | Calls `/api/tree-refresh` to clear backend cache, then reloads tree |
| **Recolher Tudo** | 📁 | Collapse all directories | Collapses all expanded directories in the tree view |
| **+ Novo** | + | Create new file | Prompts for filename and folder, creates new FileEditorCell |
| **Abrir** | 📄 | Open selected files | Opens each selected file in a new FileEditorCell instance |
| **Limpar** | 🗑️ | Clear selection | Deselects all selected files |

### Removed Buttons
- **📝 Notebook**: Discontinued (legacy functionality)
- **🌐 Share**: Not yet available (chat integration pending)

## Cell Properties

### Type Definition

```json
{
  "id": "file-manager-cell",
  "name": "File Manager",
  "description": "Ephemeral file management interface with tree view, search, and file operations",
  "version": "1.0.0",
  "category": "file-management",
  "can_render_dynamically": true
}
```

### Initial Data

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `searchQuery` | string | `""` | Current search filter query |
| `selectedFiles` | string[] | `[]` | Array of selected file paths |
| `expandedPaths` | string[] | `[]` | Array of expanded directory paths |
| `category` | string | `"efemera"` | Cell category (always ephemeral) |
| `icon` | string | `"📁"` | Cell icon emoji |

## Architecture

### TypeScript Implementation

Following **RULESET.md Rule 4.5**, this cell is implemented entirely in TypeScript:

```
file-manager-cell/
├── type.json                           # Cell type definition
├── frontend/
│   ├── View.vue                        # Main component (TypeScript)
│   ├── types.ts                        # TypeScript type definitions
│   └── composables/
│       └── useFileManager.ts           # Business logic composable
└── docs/
    └── README.md                       # This file
```

### Key Components

#### View.vue
- Main Vue component with `<script setup lang="ts">`
- Renders file tree, search bar, and action buttons
- Delegates logic to `useFileManager` composable
- Uses `FileTreeNode` component from cockpit-vue

#### useFileManager.ts
- Core business logic as a Vue 3 composable
- Manages file tree state, selection, and search
- Handles API calls with proper error handling
- Implements cache invalidation on refresh

#### types.ts
- Complete TypeScript type definitions
- Interfaces for cell data, tree nodes, and composable return
- Ensures type safety throughout the component

## Backend Integration

### API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/tree-refresh` | POST | Invalidate TreeBuilder cache |
| `/api/tree?format=flat&include_hidden=true` | GET | Load file tree data |
| `/api/cells/create` | POST | Create new FileEditorCell instances |

### Cache Invalidation Flow

1. User clicks "🔄 Atualizar" button
2. Frontend calls `POST /api/tree-refresh`
3. Backend calls `tree_builder.refresh_cache()` to clear in-memory cache
4. Frontend calls `GET /api/tree` to fetch fresh data
5. Tree view updates with latest filesystem state

**Note**: The TreeBuilder uses an in-memory cache with TTL. The refresh endpoint ensures the cache is immediately invalidated, not just after TTL expiry.

## Usage

### Adding FileManagerCell to Workspace

```typescript
import { useCellsStore } from '@/stores/cells'

const cellsStore = useCellsStore()

await cellsStore.addCell({
  type: 'file-manager-cell',
  initial_data: {
    searchQuery: '',
    selectedFiles: [],
    expandedPaths: [],
    category: 'efemera',
    icon: '📁'
  }
})
```

### Interacting with the Cell

#### Search Files
1. Type search query in the search bar
2. Tree filters in real-time to show matching files/folders
3. Search is case-insensitive and matches file names

#### Open Files in Editor
1. Click on files in the tree to select them (multiple selection supported)
2. Click "📄 Abrir" button
3. Each selected file opens in a new FileEditorCell

#### Refresh File List
1. Click "🔄 Atualizar" button
2. Backend cache is invalidated
3. Fresh file tree is loaded
4. Success message confirms update

#### Create New File
1. Click "+ Novo" button
2. Enter filename (with extension) in prompt
3. Enter folder path (defaults to "docs")
4. New FileEditorCell opens for the file

## Integration with FileEditorCell

### Bidirectional Flow

```
FileManagerCell → FileEditorCell
├─ User selects file in manager
├─ Clicks "📄 Abrir"
└─ FileEditorCell opens with file loaded

FileEditorCell → FileManagerCell
├─ User saves file in editor
├─ FileManagerCell can refresh tree
└─ Updated file appears in tree view
```

### Opening Files

When the "Abrir" button is clicked:
1. FileManagerCell iterates through selected files
2. For each file, extracts filename and directory path
3. Calls `cellsStore.addCell()` with `type: 'file-editor-v2'`
4. Passes file metadata as `initial_data`
5. FileEditorCell loads and displays the file

## State Management

### Local State (useFileManager)
- File tree data
- Selected files array
- Expanded directories set
- Search query string
- Loading and message states

### Persisted State (cells store)
- Cell ID and type
- Initial data (search query, selections)
- Cell metadata (created_at, updated_at)

### Ephemeral Nature
- Cell instance is not saved to backend database
- Only exists in frontend stores and localStorage
- Destroyed when workspace is closed or reset

## Testing

### Unit Tests
```bash
cd cockpit-vue
npm test -- artifacts/canonical/cell_types/file-manager-cell/frontend/composables/useFileManager.spec.ts
```

### Component Tests
```bash
npm test -- artifacts/canonical/cell_types/file-manager-cell/frontend/View.spec.ts
```

### Integration Tests
- Test file tree loading
- Test cache invalidation
- Test file opening in FileEditorCell
- Test search filtering

## Future Enhancements

### Planned Features
- [ ] Move file/folder functionality
- [ ] Delete file/folder functionality
- [ ] Drag-and-drop file organization
- [ ] Context menu (right-click) actions
- [ ] File type icons and metadata display
- [ ] Keyboard shortcuts for navigation

### Future Integration
- [ ] **Share Button**: Enable when chat integration is ready
- [ ] File upload from local machine
- [ ] Bulk file operations

## References

- [RULESET.md](../../../../docs/official/RULESET.md) - Rule 4.5 (TypeScript Adoption)
- [ADDING_NEW_CELL_TYPE.md](../../../../docs/official/ADDING_NEW_CELL_TYPE.md)
- [Epic #949 Unified Action Plan](../../../../docs/issues/949/unified-action-plan.md)
- [Issue #1108 Analysis](../../../../docs/issues/1108/ANALISE_E_PLANO_DE_ACAO.md)

---

**Version**: 1.0.0  
**Last Updated**: 2025-12-11  
**Status**: Complete - Ready for Integration Testing
