---
processed: true
processed_date: 2025-12-09
themes:
  - cells
  - plugin-system
  - file-editor
modules:
  - backend
  - frontend
code_verified: true
dead_docs_found: false
---
# File Editor Cell Type

**Type ID**: `file-editor`  
**Version**: 2.0.0  
**Category**: editor  
**Status**: ✅ Canonical Implementation (TypeScript)

## Overview

The File Editor cell type provides a complete file editing experience within the ScareVerse Cockpit, supporting file loading, editing, and saving with syntax highlighting.

## Features

- ✅ **File Loading**: Load existing files from the backend
- ✅ **File Editing**: Rich markdown editor with syntax highlighting
- ✅ **File Saving**: Save new files or update existing files
- ✅ **Toolbar Integration**: Full integration with CellToolbar for save/delete/send to chat
- ✅ **TypeScript**: Fully typed implementation with strict mode
- ✅ **Error Handling**: Comprehensive error handling and user feedback
- ✅ **Accessibility**: WCAG 2.1 compliant with ARIA labels

## Cell Data Schema

### Properties

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `fileName` | string | Yes | - | Name of the file being edited |
| `filePath` | string | No | "" | Path to the file (folder) |
| `language` | string | No | "text" | Programming language for syntax highlighting |
| `readOnly` | boolean | No | false | Whether the file is read-only |

### Example Cell Instance

```json
{
  "id": "cell-123",
  "type": "file-editor",
  "initial_data": {
    "fileName": "example.md",
    "filePath": "docs",
    "language": "markdown",
    "readOnly": false
  }
}
```

## Usage

### Creating a File Editor Cell

```typescript
import { useCellsStore } from '@/stores/cells'
import type { Cell, FileEditorCellData } from '@/types'

const cellsStore = useCellsStore()

const newCell: Cell = {
  id: 'file-editor-' + Date.now(),
  type: 'file-editor',
  initial_data: {
    fileName: 'new-file.md',
    filePath: 'documents',
    language: 'markdown',
    readOnly: false
  }
}

cellsStore.addCell(newCell)
```

### TypeScript Type Definitions

```typescript
// Using the built-in type from @/types
import type { FileEditorCell } from '@/types'

const cell: FileEditorCell = {
  id: 'file-editor-1',
  type: 'file-editor',
  initial_data: {
    fileName: 'example.ts',
    filePath: 'src/utils',
    language: 'typescript',
    readOnly: false
  }
}
```

## Implementation Details

### Architecture

The File Editor cell follows the canonical plug-and-play architecture:

```
file-editor/
├── type.json                     # Cell type definition
├── docs/
│   └── README.md                 # This file
├── frontend/
│   ├── View.vue                  # Main TypeScript component
│   ├── composables/
│   │   └── useFileEditor.ts      # Business logic composable
│   └── tests/
│       └── View.spec.ts          # Unit tests
└── backend/                      # (Future: backend handlers)
```

### Component: View.vue

**Tech Stack**:
- Vue 3.5 Composition API (`<script setup lang="ts">`)
- TypeScript strict mode
- MarkdownEditor component integration
- Pinia stores (cells, chat)

**Key Features**:
- File content loading on mount
- Real-time content synchronization
- Save functionality exposed via `defineExpose`
- Send to chat integration
- Error and success messaging

### Composable: useFileEditor.ts

**Purpose**: Extract file management logic from component

**Exports**:
```typescript
interface UseFileEditorReturn {
  fileContent: Ref<string>
  isLoading: Ref<boolean>
  isSaving: Ref<boolean>
  errorMessage: Ref<string | null>
  successMessage: Ref<string | null>
  loadFile: () => Promise<void>
  saveFile: () => Promise<void>
  deleteEphemeral: () => void
}
```

**Usage**:
```typescript
const {
  fileContent,
  isLoading,
  saveFile,
  loadFile
} = useFileEditor(props.cell)
```

## API Integration

### Load File Endpoint

**Endpoint**: `GET /api/files/load`  
**Query Params**:
- `folder`: string (file path)
- `filename`: string (file name)

**Response**:
```json
{
  "conteudo": "file content here..."
}
```

### Save File Endpoint

**Endpoint**: `POST /api/files/save`  
**Body**:
```json
{
  "folder": "path/to/folder",
  "filename": "example.md",
  "content": "file content..."
}
```

**Response**:
```json
{
  "status": "success",
  "message": "File saved successfully"
}
```

## Toolbar Integration

The File Editor integrates with `CellToolbar.vue` for common actions:

### Exposed Methods

```typescript
defineExpose({
  onSave: saveFile
})
```

### Toolbar Buttons

- **💾 Save**: Saves file content (calls exposed `onSave`)
- **💬 Send to Chat**: Sends file as chat attachment
- **📝 Add Fragment**: Adds code fragment to memory
- **🗑️ Delete**: Deletes ephemeral cell (not the file)

## Testing

### Unit Tests

**Location**: `frontend/tests/View.spec.ts`

**Coverage**:
- Component mounting and props
- File loading on mount
- File saving functionality
- Error handling
- Toolbar integration
- User feedback messages

**Target**: 90%+ coverage

### Running Tests

```bash
# Unit tests
npm run test:unit

# With coverage
npm run test:coverage

# Type check
npm run type-check
```

## Migration from Legacy

### From CellView_FileEditor.vue

The legacy `CellView_FileEditor.vue` (JavaScript) has been migrated to this TypeScript implementation with:

1. ✅ Full TypeScript type safety
2. ✅ Composable pattern for logic separation
3. ✅ Enhanced error handling
4. ✅ Toolbar integration improvements
5. ✅ Comprehensive testing
6. ✅ Better accessibility

### Breaking Changes

**None** - This implementation is backward compatible with existing cell instances.

## Best Practices

### Type Safety

Always use the typed interfaces:

```typescript
import type { FileEditorCell, FileEditorCellData } from '@/types'

// ✅ Good: Typed props
interface Props {
  cell: FileEditorCell
}

// ❌ Bad: Untyped props
interface Props {
  cell: any
}
```

### Error Handling

```typescript
try {
  await saveFile()
  successMessage.value = 'File saved successfully!'
} catch (error) {
  errorMessage.value = `Error: ${error.message}`
}
```

### Accessibility

```vue
<button
  :aria-label="'Save file ' + fileName"
  :disabled="isLoading"
  @click="saveFile"
>
  💾 Save
</button>
```

## References

**Project Documentation**:
- [RULESET.md Rule 4.5](../../../../docs/official/RULESET.md) - TypeScript requirement
- [TypeScript Migration Guide](../../../../cockpit-vue/docs/TYPESCRIPT_MIGRATION_GUIDE.md)
- [Type Definitions](../../../../cockpit-vue/src/types/README.md)

**Related Components**:
- [CellToolbar.vue](../../../../cockpit-vue/src/components/CellToolbar.vue)
- [MarkdownEditor.vue](../../../../cockpit-vue/src/components/MarkdownEditor.vue)
- [DynamicWorkspace.vue](../../../../cockpit-vue/src/components/DynamicWorkspace.vue)

**Epic Planning**:
- [Epic #1108 Analysis](../../../../docs/issues/1108/ANALISE_E_PLANO_DE_ACAO.md)
- [Phase 2.0 Summary](../../../../docs/issues/1108/PHASE_2.0_IMPLEMENTATION_SUMMARY.md)

---

**Last Updated**: 2025-12-08  
**Author**: GitHub Copilot Coding Agent  
**Status**: Canonical Implementation
