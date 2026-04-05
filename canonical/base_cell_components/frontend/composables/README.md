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
# Base Cell Composables

Reusable Vue 3 composition functions for the base cell architecture.

## Available Composables

### `useBaseCellFeatures.ts`

**Purpose**: Provides common functionality for all cell types following the BaseCellAPI interface.

**Features**:
- ✅ Cell save operations
- ✅ Cell close functionality
- ✅ Fragment management (add, send to chat)
- ✅ Dynamic subview management (fragments manager)
- ✅ Success/error messaging with auto-clear
- ✅ Integration with Pinia stores (notebook, cells, chat, layout)

**Usage**:

```typescript
import { useBaseCellFeatures } from '@/../artifacts/canonical/base_cell_components/frontend/composables/useBaseCellFeatures'

// In your cell component
const baseCellApi = useBaseCellFeatures(
  computed(() => props.cell.id),
  computed(() => 'my-cell-type'),
  {
    autoSave: false,
    enableFragments: true
  }
)

// Save cell
await baseCellApi.saveCell()

// Show fragments manager
baseCellApi.showCellFragmentsManager()

// Add fragment
await baseCellApi.addFragment({
  type: 'memoria',
  conteudo: 'Fragment content...'
})

// Send fragment to chat
baseCellApi.sendFragmentToChat(fragment, 0)
```

**API Reference**: See [BaseCellAPI Interface](../../../../cockpit-vue/src/types/baseCell.ts)

**Returns**: `BaseCellAPI` implementation with reactive state and methods

## Integration Pattern

Cell-specific composables should use `useBaseCellFeatures` as a foundation:

```typescript
export function useMyCellType(cell: Ref<MyCellType>) {
  // Get base functionality
  const baseCellApi = useBaseCellFeatures(
    computed(() => cell.value.id),
    computed(() => 'my-cell-type')
  )

  // Add cell-specific logic
  const cellSpecificState = ref(...)
  
  function cellSpecificMethod() {
    // ...
  }

  // Return combined API
  return {
    ...baseCellApi,
    cellSpecificState,
    cellSpecificMethod
  }
}
```

## Architecture Notes

- **Reactive by Design**: All state is reactive using Vue 3's `ref` and `computed`
- **Store Integration**: Automatically integrates with Pinia stores for state management
- **Type-Safe**: Full TypeScript support with BaseCellAPI interface
- **Message Auto-Clear**: Success messages auto-clear after 3 seconds (configurable)
- **Error Handling**: Comprehensive try/catch with user-friendly error messages

## Related Files

- Interface: `cockpit-vue/src/types/baseCell.ts`
- Example Usage: `artifacts/canonical/cell_types/unclassified-cell/frontend/View.vue`
- Documentation: `../README.md`
