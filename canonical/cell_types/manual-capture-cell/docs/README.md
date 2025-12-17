# Manual Capture Cell

## Overview

The **Manual Capture Cell** is an **ephemeral cell** designed for quick content capture and wireframe generation. Unlike persistent cells, this cell exists only in browser memory and is not saved to the backend database.

**Key Characteristics**:
- ✅ **Ephemeral**: Disappears on page refresh (not persisted)
- ✅ **Utility Tool**: Provides temporary UI functionality
- ✅ **Content Creation**: Creates file-editor-v2 cells with captured/generated content
- ✅ **TypeScript Implementation**: Fully typed with comprehensive type safety

## Purpose

The Manual Capture Cell serves as a **content entry point** in the Dynamic Workspace. Instead of persisting its own state, it creates new **file-editor-v2 cells** containing:
1. **Captured text content** (markdown format)
2. **Generated ASCII wireframes** from HTML (plaintext format)

This design follows the ephemeral cell architecture pattern, making it a lightweight, transient tool.

## Features

### 1. Content Capture
- Accepts any text input via textarea
- Creates a new `file-editor-v2` cell with the captured content
- Automatically names the file with timestamp: `captured-content-YYYY-MM-DDTHH-MM-SS.md`
- Sets language to `markdown` for syntax highlighting
- Clears input after successful capture

### 2. Wireframe Generation
- Parses HTML content from textarea
- Generates ASCII art representation of DOM structure
- Groups repetitive elements for clarity
- Creates a new `file-editor-v2` cell with the wireframe
- Automatically names the file with timestamp: `wireframe-YYYY-MM-DDTHH-MM-SS.txt`
- Sets language to `plaintext`
- Clears input after successful generation

### 3. Ephemeral Behavior
- **No backend persistence**: Cell is not saved to MongoDB
- **Client-side only**: Exists in browser memory
- **Temporary ID**: Generated with pattern `ephemeral-manual-capture-cell-{timestamp}`
- **Disappears on refresh**: Lost when page is reloaded
- **Fast creation**: No network round-trip to backend

## Usage

### Adding the Cell

1. Click **➕ Add Cell** in the Dynamic Workspace footer
2. Select **Manual Capture** from the cell type modal
3. Cell is instantly added to the workspace (no backend call)

### Capturing Content

1. Type or paste text content into the textarea
2. Click **Capture Content** button
3. A new **file-editor-v2** cell appears with your content
4. Input is cleared, ready for next capture

### Generating Wireframe

1. Paste HTML content into the textarea
2. Click **Generate Wireframe** button
3. A new **file-editor-v2** cell appears with ASCII wireframe
4. Input is cleared, ready for next operation

### External Content Insertion

Components can programmatically insert content using the cell's exposed method:

```typescript
// Get reference to manual capture cell
const manualCaptureRef = ref<{ insertContent: (content: string) => void } | null>(null)

// Insert content from external source
manualCaptureRef.value?.insertContent("Content from chat response")
```

## Architecture

### Cell Type Definition

**Canonical Definition**: `artifacts/canonical/notebook_item_types/manual-capture-cell.json`

```json
{
  "id": "manual-capture-cell",
  "name": "Manual Capture",
  "category": "utility",
  "default_initial_data": {
    "category": "efemera"  // ← Marks as ephemeral
  }
}
```

### Directory Structure

```
manual-capture-cell/
├── type.json                          # Symlink → ../../notebook_item_types/manual-capture-cell.json
├── frontend/
│   ├── View.vue                       # Main component (TypeScript)
│   ├── types.ts                       # TypeScript type definitions
│   └── composables/
│       └── useManualCapture.ts        # Core composable logic
├── docs/
│   └── README.md                      # This file
└── tests/                             # Tests (future)
```

### TypeScript Implementation

All code is written in **TypeScript** per RULESET.md Rule 4.5:

**View.vue**:
```vue
<script setup lang="ts">
import type { CellProps, ManualCaptureCellData } from './types'

const props = defineProps<CellProps>()
// ... fully typed implementation
</script>
```

**useManualCapture.ts**:
```typescript
export interface UseManualCaptureReturn {
  inputContent: Ref<string>
  isProcessing: Ref<boolean>
  captureContent: (createCellFn: ...) => Promise<void>
  generateWireframe: (createCellFn: ...) => Promise<void>
  insertContent: (content: string) => void
}

export function useManualCapture(
  cellData: Ref<ManualCaptureCellData>
): UseManualCaptureReturn {
  // ... implementation
}
```

### Integration with Dynamic Layout

The cell uses `inject('dynamicLayout')` to access the layout's `addCell` method:

```typescript
const dynamicLayout = inject<{
  addCell: (params: {...}) => boolean
}>('dynamicLayout', null)

// Create file-editor-v2 cell
dynamicLayout.addCell({
  cellId: `ephemeral-file-editor-v2-${Date.now()}`,
  type: 'file-editor-v2',
  title: fileName,
  state: {
    cellInstance: { /* ... */ },
    cellType: { /* ... */ },
    initial_data: {
      content: capturedContent  // Pre-populate
    }
  }
})
```

## Wireframe Algorithm

The wireframe generator uses a recursive DOM traversal algorithm:

1. **Parse HTML**: Use browser's DOMParser to create DOM tree
2. **Traverse Tree**: Recursively visit each element
3. **Group Siblings**: Group repetitive elements by tag+class signature
4. **Draw Boxes**: Create ASCII art boxes with indentation
5. **Show Repetitions**: Indicate repeated patterns (e.g., "... 5 more")

**Example Output**:
```
+--- <section.container> ---+
  +--- <div.header> "Welcome" ---+
  +--- <ul.list> ---+
    +--- <li.item> "First" ---+
    ... (4 repetidos)
  +--- <footer.footer> ---+
```

## Internationalization (i18n)

Fully internationalized with support for:
- 🇺🇸 **English** (`en-US`)
- 🇧🇷 **Portuguese** (`pt-BR`)

**Keys**:
- `manualCapture.title`: "Manual Capture"
- `manualCapture.placeholder`: Input placeholder text
- `manualCapture.captureButton`: "Capture Content"
- `manualCapture.wireframeButton`: "Generate Wireframe"
- `manualCapture.ephemeralLabel`: "ephemeral"
- `manualCapture.processing`: "Processing..."
- `manualCapture.captureError`: Error message for capture failure
- `manualCapture.wireframeError`: Error message for wireframe failure

## Theme Compliance

Fully compliant with ScareVerse design system:

- ✅ Dark mode support via Tailwind CSS design tokens
- ✅ Uses semantic color classes: `bg-surface`, `text-primary`, etc.
- ✅ Proper contrast ratios for accessibility
- ✅ Consistent spacing with design system
- ✅ Hover states and disabled states

## Properties Schema

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `category` | string | `"efemera"` | Marks cell as ephemeral (not persisted) |
| `icon` | string | `"✍️"` | Icon displayed in cell header |
| `placeholder` | string | `"Enter content..."` | Textarea placeholder text |

## Testing Guidance

### Manual Testing Checklist

- [ ] Add manual-capture-cell from AddCellModal
- [ ] Verify **no backend API call** in Network tab (ephemeral)
- [ ] Enter text and click "Capture Content"
- [ ] Verify file-editor-v2 cell created with content
- [ ] Paste HTML and click "Generate Wireframe"
- [ ] Verify file-editor-v2 cell created with wireframe
- [ ] Refresh page
- [ ] Verify manual-capture-cell disappeared (ephemeral)
- [ ] Verify created file-editor-v2 cells also disappeared (ephemeral)

### Automated Testing (Future)

```typescript
// Example E2E test
test('manual capture creates file editor cell', async () => {
  // Add manual-capture-cell
  await addCellToWorkspace('manual-capture-cell')
  
  // Enter content
  await fillTextarea('[data-testid="manual-capture-textarea"]', 'Test content')
  
  // Click capture
  await click('[data-testid="capture-content-button"]')
  
  // Verify file-editor-v2 cell created
  const cells = await getCellsInWorkspace()
  expect(cells).toContainEqual(
    expect.objectContaining({
      type: 'file-editor-v2',
      content: 'Test content'
    })
  )
})
```

## Migration from Legacy ManualCapture.vue

This cell replaces the legacy `ManualCapture.vue` component with:

**Improvements**:
1. ✅ **Plug-and-play architecture**: Discoverable via NotebookItemTypeRegistry
2. ✅ **Ephemeral design**: No unnecessary persistence
3. ✅ **File-editor-v2 creation**: Output goes to dedicated editor cells
4. ✅ **TypeScript**: Full type safety
5. ✅ **Dynamic workspace integration**: Works seamlessly in new layout
6. ✅ **No notebook coupling**: Independent of legacy notebook container

**Breaking Changes**:
- No longer uses `useGlobalEventsStore().setCopiedContent()`
- No longer uses `useUIStore().handleContentCaptured()`
- Creates file-editor-v2 cells instead of adding to legacy notebook

## Related Documentation

- **[Ephemeral Cell Architecture](../../../../docs/official/frontend/architecture/ephemeral-cell-architecture.md)** - Architectural pattern
- **[Adding New Cell Types](../../../../docs/official/ADDING_NEW_CELL_TYPE.md)** - Cell creation guide
- **[Cell Type Symlink Architecture](../../../../docs/official/backend/architecture/cell-type-symlink-architecture.md)** - Symlink pattern
- **[File Editor Cell](../../file-editor/docs/README.md)** - Target cell type for content

## Support

For issues or questions:
- Review **Ephemeral Cell Architecture** documentation
- Check **DynamicWorkspace** integration code
- Contact ScareVerse development team

---

**Last Updated**: 2025-12-16  
**Version**: 1.0.0  
**Status**: Production Ready  
**Cell Type**: Ephemeral Utility
