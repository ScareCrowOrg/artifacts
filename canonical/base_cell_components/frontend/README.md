# Base Cell Components — Frontend

Reusable base Vue components and composables shared by all canonical cell types in the ScareVerse Plug-and-Play architecture.

## Purpose

This directory provides the common frontend building blocks that every cell type can import to reduce duplication and ensure a consistent user experience across all cells. It is the frontend counterpart to the `BaseCell` TypeScript interface in `artifacts/shared/types/`.

## Index

### Subdirectories

| Directory | Description |
|-----------|-------------|
| `composables/` | Base composables: `useBaseCellFeatures.ts` — full implementation of the `RenderableCell` interface for all cell types |
| `views/` | Base Vue view components: `BaseFragmentsManager.vue` — standardized UI for managing cell fragments (sub-content) |

## Key Modules

### `composables/useBaseCellFeatures.ts`

The primary composable that all cell `View.vue` components should use as their foundation. Provides:

- Cell data loading and reactive state
- Fragment management hooks
- Cell lifecycle callbacks (`onMounted`, `onBeforeUnmount`)
- Standard emit events (`cell:updated`, `cell:executed`)
- Permission-aware action availability

```ts
import { useBaseCellFeatures } from '@artifacts/base_cell_components/composables/useBaseCellFeatures'

const { cellData, isLoading, fragments, execute } = useBaseCellFeatures(props.cellId)
```

### `views/BaseFragmentsManager.vue`

A standardized component for displaying and managing cell fragments (discrete content blocks within a cell). Import and compose this in your `View.vue` to get fragment CRUD UI out of the box.

```vue
<template>
  <BaseFragmentsManager :cell-id="cellId" :fragments="fragments" @fragment:updated="onFragmentUpdated" />
</template>
```

## Usage

These components are available to all canonical cell type frontends via relative import or the `@artifacts/base_cell_components` path alias.

## Related Documentation

- [Base Cell Components Root](../) - Parent directory overview
- [Shared Types](../../shared/types/) - `BaseCell` and `BaseBook` interfaces
- [Shared Composables](../../shared/composables/) - Platform-wide composable library
- [Adding New Cell Type](../../../docs/official/ADDING_NEW_CELL_TYPE.md) - Guide for implementing new cells
