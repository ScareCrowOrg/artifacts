# DynamicWorkspace Composables

Vue 3 composables providing the core logic for the DynamicWorkspace v2 viewer — workspace handshake, cell management, grid layout, persistence, theme sync, and i18n auto-loading.

## Purpose

This directory contains all composables used by the DynamicWorkspace viewer. Each composable encapsulates a specific domain of the workspace lifecycle:
- **Handshake**: Validates `INIT_WORKSPACE` postMessage from Cockpit and establishes the session
- **Cell management**: Discovers, instantiates, and resolves Vue views for cell types
- **Grid layout**: Manages reactive grid state, positions, and CRUD operations
- **Auto-save**: Debounced and interval-based background save of grid state
- **Persistence**: Load and save workspace layouts via the CentralHub API
- **Theme sync**: Synchronizes Cockpit theme tokens with the viewer context
- **i18n auto-load**: Lazy-loads cell-specific i18n translation files

## Directory Structure

```
composables/
├── ~~useWorkspaceHandshake.ts~~  - **[REMOVED]** — Migrated to `shared/composables/useBaseViewer.ts`
├── useCellViewProvider.ts      - Cell type discovery, instantiation, and view resolution
├── useGridLayout.ts            - Reactive grid state management and CRUD
├── useAutoSave.ts              - Debounced + interval auto-save for grid changes
├── usePersistenceManager.ts    - Layout load/save via CentralHub API
├── useThemeSync.ts             - Theme token synchronization from Cockpit
└── useAutoLoadCellI18n.ts      - Lazy i18n file loading per cell type
```

## How to Use

```typescript
import { useBaseViewer } from '@/composables/useBaseViewer'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useGridLayout } from './composables/useGridLayout'
import { useAutoSave } from './composables/useAutoSave'

// In App.vue setup():
const { isAuthenticated } = useBaseViewer({ validationMode: 'validated' })
const store = useWorkspaceStore()
const { cells, addCell, removeCell } = useGridLayout()
useAutoSave(cells)
```

## Content Index

| File | Description |
|---|---|
| ~~`useWorkspaceHandshake.ts`~~ | **[REMOVED]** — Migrated to `@/composables/useBaseViewer` |
| `useCellViewProvider.ts` | Cell type discovery (HybridDatabase), instantiation, and view resolution |
| `useGridLayout.ts` | Reactive GridCell list with position management and CRUD |
| `useAutoSave.ts` | Debounced + interval auto-save background task |
| `usePersistenceManager.ts` | Load/save workspace layouts to/from CentralHub API |
| `useThemeSync.ts` | Theme CSS token sync from parent Cockpit frame |
| `useAutoLoadCellI18n.ts` | Lazy-load per-cell-type i18n translation files |
