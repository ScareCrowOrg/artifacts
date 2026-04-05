---
processed: true
processed_date: 2025-12-09
themes:
  - cells
  - frontend
  - components
modules:
  - artifacts
  - frontend
code_verified: true
dead_docs_found: false
---
# Base Cell Views

Reusable Vue 3 components for the base cell architecture.

## Available Components

### `BaseFragmentsManager.vue`

**Purpose**: Universal fragments manager that displays and manages fragments for any cell type.

**Features**:
- ✅ Display all fragments for a given cell
- ✅ Add new fragments with type selection (memoria, code, note, reference)
- ✅ Send fragments to chat as attachments
- ✅ Markdown rendering for fragment content
- ✅ Empty state and loading states
- ✅ Success/error messaging
- ✅ Responsive and accessible UI

**Props**:

```typescript
interface Props {
  cellId: string  // Required: ID of the cell whose fragments to manage
}
```

**Usage**:

The component is typically opened as a dynamic subview through the BaseCellAPI:

```typescript
// From a cell component
baseCellApi.showCellFragmentsManager()
```

Or it can be used directly in a template:

```vue
<template>
  <BaseFragmentsManager :cellId="myCellId" />
</template>

<script setup lang="ts">
import BaseFragmentsManager from '@/../artifacts/canonical/base_cell_components/frontend/views/BaseFragmentsManager.vue'
</script>
```

**Styling**:
- Uses Tailwind CSS utility classes
- Consistent with ScareVerse design system
- Responsive layout with overflow handling
- Custom scrollbar styling

**Fragment Types**:
- 📝 **Memória**: Memory/recall fragments
- 💻 **Código**: Code snippets
- 📄 **Nota**: General notes
- 🔗 **Referência**: References and links

**Dependencies**:
- `useNotebookStore`: Access cell data and fragments
- `useBaseCellFeatures`: Fragment management operations
- `MarkdownRenderer`: Render fragment content

## Integration with Cell Types

### 1. Add to `notebook_item_types/*.json`

```json
{
  "dynamic_views": {
    "fragments-manager": {
      "label": "Gerenciador de Fragmentos",
      "default_refs": {
        "view": "base_cell_components/frontend/views/BaseFragmentsManager.vue"
      }
    }
  }
}
```

### 2. Open from Cell Component

```typescript
import { useBaseCellFeatures } from '@/../artifacts/canonical/base_cell_components/frontend/composables/useBaseCellFeatures'

const baseCellApi = useBaseCellFeatures(
  computed(() => props.cell.id),
  computed(() => 'my-cell-type')
)

function handleShowFragments() {
  baseCellApi.showCellFragmentsManager()
}
```

## UI/UX Features

- **Compact Display**: Shows fragment count and type badges
- **Inline Actions**: Send to chat directly from fragment card
- **Form Validation**: Add button disabled until content is provided
- **Auto-Clear Messages**: Success messages auto-clear after 3 seconds
- **Markdown Support**: Full markdown rendering in fragment content
- **Scrollable Content**: Fragment content limited to 400px height with custom scrollbar

## Architecture Notes

- **Standalone Component**: Can be used independently or as a dynamic subview
- **Store-Driven**: Reads fragments directly from `notebookStore.cells`
- **Reactive**: Automatically updates when fragments are added/modified
- **TypeScript**: Fully typed with proper interfaces

## Related Files

- Base API: `../composables/useBaseCellFeatures.ts`
- Type Definitions: `../../../../cockpit-vue/src/types/baseCell.ts`
- Example: `../../cell_types/unclassified-cell/frontend/View.vue`
