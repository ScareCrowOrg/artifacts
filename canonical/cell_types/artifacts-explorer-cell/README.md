---
processed: true
processed_date: 2026-05-06
themes:
  - workspace
  - explorer
  - picker
  - cells
modules:
  - artifacts-explorer-cell
code_verified: true
dead_docs_found: false
---

# artifacts-explorer-cell

**Version**: 1.0.0
**Category**: workspace
**Icon**: 🔍

## Overview

`artifacts-explorer-cell` is a workspace utility cell that replaces the legacy `AddCellModal.vue`.
In **picker mode** (Phase 1), it renders a searchable grid of all available cell types, allowing the user to add them to the dynamic workspace by clicking.

## Architecture

```
artifacts-explorer-cell/
├── type.json                        # Cell type definition (can_render_dynamically: true)
├── frontend/
│   ├── ArtifactsExplorerCell.ts     # BaseCell implementation (MANDATORY)
│   ├── View.vue                     # UI: searchable picker grid (<script setup lang="ts">)
│   └── store.ts                     # Pinia store: useArtifactsExplorerStore
└── README.md                        # This file
```

## BaseCell Contract

| Method | Description |
|--------|-------------|
| `execute(input)` | Fetches renderable cell types from `GET /api/cells/types/list` |
| `describe()` | Returns `CellMetadata` (id, name, version, inputs, outputs, tags) |
| `validate(input)` | Validates `input.mode` is `'picker'` or `'view'` |
| `show(data, options)` | Returns `{ componentPath: 'frontend/View.vue' }` |

## Pinia Store (`useArtifactsExplorerStore`)

Store ID: `artifactsExplorer`

| State | Type | Description |
|-------|------|-------------|
| `availableCellTypes` | `ExplorerCellType[]` | Loaded from backend API |
| `isLoading` | `boolean` | Loading indicator |
| `error` | `string \| null` | Error message if load failed |
| `selectedCellType` | `ExplorerCellType \| null` | Set when user clicks a type; App.vue watches this |

| Action | Description |
|--------|-------------|
| `loadCellTypes()` | Calls `GET /api/cells/types/list`, filters renderable types |
| `selectCellType(cellType)` | Sets `selectedCellType` → triggers App.vue watcher |
| `clearSelection()` | Resets `selectedCellType` to null |

## Integration with App.vue

```
[User] Clicks ➕ in FooterWindowManager
    ↓ emit('show-artifacts-explorer')
    ↓ App.vue: handleShowArtifactsExplorer()
        → Guard: if 'artifacts-explorer-cell' already in grid → return
        → Otherwise → handleCellTypeSelected(explorerType)
    ↓ artifacts-explorer-cell renders in picker mode
    ↓ [User] clicks a cell type card → explorerStore.selectCellType(cellType)
    ↓ App.vue watcher fires → handleCellTypeSelected(cellType) + clearSelection()
    ✅ New cell added to grid
```

## Props (View.vue)

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `cellInstance` | `any` | — | BaseCell instance from resolveViewSpec |
| `cell` | `any` | — | `{ cellTypeName, cellType }` from resolveViewSpec |
| `mode` | `'view' \| 'picker'` | `'picker'` | Display mode (Phase 2: 'view' mode reserved) |

## Phases

- **Phase 1** (current): Picker mode — replaces `AddCellModal.vue`
- **Phase 2** (future): View mode — full explorer for Books, Workers, Services, with social filters
- **Phase 3** (future): Stage promotion (Experimental → Protected)

## References

- [ADDING_NEW_CELL_TYPE.md](../../../../docs/official/ADDING_NEW_CELL_TYPE.md)
- [RULESET.md](../../../../docs/official/RULESET.md)
- Issue: `docs/issues/add-cell-modal-to-artifacts-explorer-refactor/ISSUE.md`
