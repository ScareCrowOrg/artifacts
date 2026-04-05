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
# Base Cell Components

This directory contains reusable base components and composables for the Plug-and-Play cell architecture in ScareVerse Cockpit.

## Purpose

Provide common functionality and UI components that all cell types can leverage, reducing code duplication and ensuring consistency across cell implementations.

## Directory Structure

```
base_cell_components/
├── frontend/
│   ├── composables/          # Reusable composition functions
│   │   └── useBaseCellFeatures.ts
│   └── views/                # Reusable view components
│       └── BaseFragmentsManager.vue
└── README.md                 # This file
```

## Components

### Frontend Components

#### Composables

- **`useBaseCellFeatures.ts`**: Base cell API implementation providing common functionality for all cell types (save, close, fragment management, messaging)

#### Views

- **`BaseFragmentsManager.vue`**: Universal fragments manager component that can be used as a dynamic subview for any cell type

## Integration

### Using Base Cell Features

Cell-specific composables can leverage `useBaseCellFeatures` to get common functionality:

```typescript
import { useBaseCellFeatures } from '@/../artifacts/canonical/base_cell_components/frontend/composables/useBaseCellFeatures'

const baseCellApi = useBaseCellFeatures(
  computed(() => cellId.value),
  computed(() => 'my-cell-type')
)

// Use base features
await baseCellApi.saveCell()
baseCellApi.showCellFragmentsManager()
```

### Using Fragments Manager

Cell types can reference the BaseFragmentsManager in their `notebook_item_types/*.json` file:

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

## Architecture

This follows the **Plug-and-Play** cell architecture pattern where:

1. **Base Components** provide common functionality
2. **Cell-Specific Components** extend and customize base functionality
3. **Type Definitions** (`notebook_item_types/*.json`) configure which components to use
4. **Symlinks** allow dynamic resolution of component paths

## Related Documentation

- [BaseCellAPI Interface](../../../cockpit-vue/src/types/baseCell.ts)
- [Unclassified Cell Example](../cell_types/unclassified-cell/)
- [Epic #1108 - Phase 2.1.2 Extension](../../../docs/issues/1108/)

## Version

- **Created**: 2025-12-09
- **Epic**: #1108 (Phase 2.1.2 Extension)
- **Status**: Active
