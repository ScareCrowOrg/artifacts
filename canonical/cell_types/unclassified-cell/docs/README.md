# Unclassified Cell - Canonical Cell Type

**Version:** 2.0.0  
**Category:** viewer  
**Status:** ✅ Ready for Dynamic Workspace  
**Migration Phase:** 2.1.2 (Epic #1108)

## Overview

The Unclassified Cell is a generic cell type designed for viewing unclassified content and memory fragments. It provides a simple interface for displaying title, content in Markdown format, and associated memory fragments with integrated fragment viewer functionality.

This cell type has been migrated to the canonical plug-and-play architecture with full TypeScript implementation, following the same patterns established by the File Editor cell (Phase 2.1.1).

## Features

- ✅ **TypeScript Implementation**: Full type safety with strict mode
- ✅ **Composable Pattern**: Business logic separated into `useUnclassifiedCell.ts`
- ✅ **Integrated Fragment Viewer**: Built-in memory fragment display
- ✅ **Toolbar Integration**: Exposes methods for toolbar actions
- ✅ **Diagnostic Logging**: Comprehensive console logging for debugging
- ✅ **Zero Breaking Changes**: Classic layout remains unaffected
- ✅ **Dynamic Workspace Compatible**: `can_render_dynamically: true`

## Directory Structure

```
artifacts/canonical/cell_types/unclassified-cell/
├── type.json                                    # Symlink → ../../notebook_item_types/unclassified-cell.json
├── frontend/
│   ├── View.vue                                 # Main TypeScript component
│   ├── composables/
│   │   └── useUnclassifiedCell.ts               # Business logic composable
│   └── tests/
│       └── View.spec.ts                         # Component tests
├── docs/
│   └── README.md                                # This file
└── backend/                                     # Reserved for future handlers
```

## Cell Type Definition

**Canonical Source:** `artifacts/canonical/notebook_item_types/unclassified-cell.json`

```json
{
  "id": "unclassified-cell",
  "name": "Unclassified Cell",
  "description": "A generic cell type for viewing unclassified content and memory fragments",
  "version": "2.0.0",
  "category": "viewer",
  "can_render_dynamically": true,
  "default_refs": {
    "view": ["frontend/View.vue"],
    "docs": ["docs/README.md"],
    "composables": ["frontend/composables/useUnclassifiedCell.ts"]
  },
  "default_initial_data": {
    "title": "Nova Célula Sem Título",
    "content": "",
    "category": "persistida",
    "icon": "mdi-text-box"
  },
  "allow_instance_override_refs": true
}
```

## Component Architecture

### View.vue (Main Component)

**Lines:** ~200  
**Language:** TypeScript (Vue 3 SFC)  
**Purpose:** Presentation layer for unclassified cell

**Key Features:**
- Title and content editing
- Integrated fragment viewer
- Toolbar integration via `defineExpose`
- Error/success message display
- Responsive layout

**Exposed Methods:**
```typescript
interface ExposedMethods {
  onSave: () => Promise<void>  // Save cell data
}
```

### useUnclassifiedCell.ts (Composable)

**Lines:** ~320  
**Purpose:** Business logic and state management

**Exported Interface:**
```typescript
interface UseUnclassifiedCellReturn {
  // State
  cellData: Ref<UnclassifiedCellData>
  isLoading: Ref<boolean>
  isSaving: Ref<boolean>
  errorMessage: Ref<string | null>
  successMessage: Ref<string | null>
  
  // Computed
  isNewCell: Ref<boolean>
  memoryFragments: Ref<Array<any>>
  fragmentCount: Ref<number>
  
  // Methods
  loadCellData: () => void
  saveCell: () => Promise<void>
  closeCell: () => void
  sendFragmentToChat: (fragment: any, index: number) => void
  formatDate: (dateString: string | undefined) => string
}
```

## Integration with DynamicWorkspace

### Registration in useCellViewLoader.js

The cell type is registered using the dual mapping strategy:

```javascript
const CELL_VIEW_PATHS = {
  // Legacy (Classic Layout)
  'unclassified': () => import('@/components/CellView_Unclassified.vue'),
  
  // New canonical implementation (DynamicWorkspace - TypeScript)
  'unclassified-cell': () => import('#artifacts/canonical/cell_types/unclassified-cell/frontend/View.vue'),
  
  // ... other mappings
}
```

### Filtering Mechanism

The cell type is automatically included in the DynamicWorkspace "Add Cell" modal due to `can_render_dynamically: true`.

**Backend API:** `/api/cells/types/list`  
**Frontend Filter:** `AddCellModal.vue` (line 199)

```javascript
const filteredCellTypes = computed(() => {
  return cellTypes.value.filter(type => {
    return type.can_render_dynamically === true
  })
})
```

## Fragment Viewer Integration

### Migration from DefaultCellView.vue

The fragment viewer functionality has been migrated directly into the Unclassified Cell View component, eliminating the dependency on a separate `DefaultCellView.vue` for this cell type.

**Key Differences:**
- **Before**: Fragment viewer was in `DefaultCellView.vue`, rendered separately
- **After**: Fragment viewer is integrated directly in the cell view
- **Benefit**: Simplified architecture, better encapsulation

### Fragment Display Logic

```typescript
// Filter only "memoria" type fragments
const memoryFragments = computed(() => {
  const cellFragments = cell.value?.fragments
  if (!cellFragments || !Array.isArray(cellFragments)) {
    return []
  }
  return cellFragments.filter((f: any) => f.type === 'memoria')
})
```

### Send to Chat Feature

Each fragment can be sent to the chat as an attachment:

```typescript
function sendFragmentToChat(fragment: any, index: number): void {
  chatStore.addAttachment({
    type: 'fragment',
    content: fragment.conteudo,
    metadata: {
      fragmentIndex: index,
      cellId: cell.value?.id,
      fragmentType: fragment.type,
    },
  })
}
```

## Diagnostic Logging

### Load Lifecycle Logs

The component implements comprehensive logging throughout its lifecycle:

```typescript
console.group('[UnclassifiedCellView] 🎨 Component mounted')
console.log('📦 Cell ID:', props.cell?.id || 'NEW')
console.log('📊 Initial data:', props.cell?.initial_data || props.cell?.data)
console.log('🧩 Fragments:', props.cell?.fragments?.length || 0)
console.groupEnd()
```

### Composable Logs

```typescript
console.group('[useUnclassifiedCell] 🏗️ Initializing composable')
console.log('📦 Cell:', cell.value?.id || 'NEW')
console.groupEnd()
```

### Action Logs

Every user action is logged:
- Save operations
- Close operations
- Fragment sending
- Data loading

## User Feedback

### Success Messages
- Cell saved successfully
- Fragment sent to chat

### Error Messages
- Error loading cell data
- Error saving cell
- Error sending fragment to chat

All messages are displayed inline in the component with appropriate styling.

## Usage Examples

### Creating a New Unclassified Cell

1. Open DynamicWorkspace
2. Click "➕ Add Cell" in footer
3. Select "Unclassified Cell" from modal
4. Enter title and content
5. (Optional) View associated fragments

### Viewing Fragments

Fragments are automatically displayed below the content editor when present:
- Only "memoria" type fragments are shown
- Each fragment shows type badge and index
- "Send to Chat" button for each fragment

### Toolbar Actions

The cell exposes the following toolbar actions:
- **Save**: Triggers `onSave()` method
- **Close**: Handled internally via close button

## Testing

### Unit Tests

**Location:** `frontend/tests/View.spec.ts`

**Coverage Target:** 90%+

**Test Categories:**
- Component mounting and data loading
- User interactions (editing, saving)
- Fragment display logic
- Send to chat functionality
- Error handling
- Toolbar integration

### E2E Tests

**Integration Point:** DynamicWorkspace cell loading flow

**Test Scenarios:**
- Cell type appears in Add Cell modal
- Cell renders correctly in grid
- Fragment viewer displays fragments
- Save and close operations work

## Migration Notes

### From Legacy `unclassified` to `unclassified-cell`

**Classic Layout (Unchanged):**
- Still uses `CellView_Unclassified.vue`
- Cell type ID: `unclassified`
- No changes required

**DynamicWorkspace (New):**
- Uses canonical TypeScript implementation
- Cell type ID: `unclassified-cell`
- Symlink architecture
- `can_render_dynamically: true`

### Dual Mapping Strategy

Both cell types coexist during the transition:
- `unclassified`: Legacy JavaScript (Classic Layout)
- `unclassified-cell`: New TypeScript (DynamicWorkspace)

## Troubleshooting

### Cell Not Appearing in Add Cell Modal

**Check:**
1. Verify `can_render_dynamically: true` in `unclassified-cell.json`
2. Check backend API response: `GET /api/cells/types/list`
3. Verify symlink is correctly pointing to canonical definition
4. Check browser console for filter logs

### Component Not Loading

**Check:**
1. Verify import path in `useCellViewLoader.js`
2. Check browser console for import errors
3. Verify `View.vue` exists at canonical path
4. Check TypeScript compilation errors

### Fragments Not Displaying

**Check:**
1. Verify cell has `fragments` array
2. Check fragment `type` field (must be "memoria")
3. Check browser console for fragment filter logs
4. Verify `MarkdownRenderer` is available

## Future Enhancements

- [ ] Add fragment search/filter capability
- [ ] Support additional fragment types beyond "memoria"
- [ ] Add fragment sorting options
- [ ] Implement fragment editing (if needed)
- [ ] Add export functionality for fragments

## Related Documentation

- **Epic #1108**: Replanejamento Estratégico da Epic #949
- **Phase 2.1.1**: File Editor Cell Migration (reference implementation)
- **SYMLINK_ARCHITECTURE.md**: Symlink pattern documentation
- **DUAL_MAPPING_IMPLEMENTATION.md**: Dual mapping strategy
- **RULESET.md**: Project rules and conventions

## Changelog

### v2.0.0 (2025-12-09)
- ✅ Migrated to TypeScript with strict mode
- ✅ Implemented composable pattern
- ✅ Integrated fragment viewer
- ✅ Added comprehensive logging
- ✅ Added user feedback messages
- ✅ Implemented toolbar integration
- ✅ Created complete documentation
- ✅ Set `can_render_dynamically: true`
