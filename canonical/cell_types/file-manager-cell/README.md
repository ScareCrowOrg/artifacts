# File Manager Cell

## Overview

The **FileManagerCell** is an ephemeral cell type that provides comprehensive file management functionality for the ScareVerse Cockpit. It displays a hierarchical file tree with search, selection, and file operations.

## Directory Structure

```
file-manager-cell/
├── README.md                           # This file
├── type.json                           # 🔗 Symlink to ../../notebook_item_types/file-manager-cell.json
├── frontend/                           # Frontend implementation
│   ├── README.md                       # Frontend components documentation
│   ├── View.vue                        # Main Vue component (TypeScript)
│   ├── types.ts                        # TypeScript type definitions
│   └── composables/                    # Vue composables
│       ├── README.md                   # Composables documentation
│       └── useFileManager.ts           # File manager business logic
└── docs/                               # Comprehensive documentation
    └── README.md                       # Complete usage guide and API reference
```

## Key Features

- **Ephemeral Architecture**: Non-persistent UI cell (category: "efemera")
- **File Tree Visualization**: Hierarchical display of project files
- **Real-time Search**: Filter files by name
- **Multiple Selection**: Select and open multiple files
- **Cache Invalidation**: Refresh button clears backend Redis cache
- **FileEditorCell Integration**: Opens files for editing

## Quick Start

### Adding to Workspace

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

### Using the Cell

1. **Search Files**: Type in the search bar to filter by filename
2. **Select Files**: Click on files to select them
3. **Open Files**: Click "📄 Abrir" to open selected files in FileEditorCell
4. **Refresh**: Click "🔄 Atualizar" to refresh tree and invalidate cache
5. **Create New**: Click "+ Novo" to create a new file

## Technical Details

- **TypeScript**: 100% TypeScript implementation (RULESET.md Rule 4.5)
- **File Size**: All files under 500 lines (RULESET.md Rule 1.1)
- **Composable Pattern**: Business logic separated from UI
- **Type Safety**: Complete TypeScript type system

## Documentation

For complete documentation, including:
- API reference
- Architecture details
- Usage examples
- Security analysis
- Integration guide

See: [docs/README.md](./docs/README.md)

## References

- [Cell Type Definition](../../notebook_item_types/file-manager-cell.json) (canonical)
- [Frontend Implementation](./frontend/README.md)
- [Composables](./frontend/composables/README.md)
- [Complete Documentation](./docs/README.md)

---

**Version**: 1.0.0  
**Category**: file-management  
**Status**: Production Ready  
**TypeScript**: 100%
