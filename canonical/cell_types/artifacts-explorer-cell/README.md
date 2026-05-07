---
processed: true
processed_date: 2026-05-07
themes:
  - workspace
  - explorer
  - picker
  - cells
  - artifacts
modules:
  - artifacts-explorer-cell
code_verified: true
dead_docs_found: false
---

# artifacts-explorer-cell

**Version**: 2.0.0
**Category**: workspace
**Icon**: 🔍

## Overview

`artifacts-explorer-cell` is the universal artifact discovery cell for the ScareVerse dynamic workspace.
It fetches all artifact types (Cells, Services, Workers) from `GET /api/v1/artifacts-map` and renders them in a filterable, searchable grid.

- **`filter_mode: "all"`** (default) — displays category tabs (All / Cells / Infrastructure / Intelligence).
- **`filter_mode: "cells_only"`** — displays only `cell-type` artifacts without tabs (server-side filter).

## Architecture

```
artifacts-explorer-cell/
├── type.json                        # Cell type definition (default_initial_data.filter_mode: "all")
├── frontend/
│   ├── ArtifactsExplorerCell.ts     # BaseCell implementation (MANDATORY)
│   ├── View.vue                     # UI: filterable explorer grid (<script setup lang="ts">)
│   └── store.ts                     # Pinia store: useArtifactsExplorerStore
└── README.md                        # This file
```

## BaseCell Contract

| Method | Description |
|--------|-------------|
| `execute(input)` | Fetches artifacts from `GET /api/v1/artifacts-map` (supports `input.filter_mode`) |
| `describe()` | Returns `CellMetadata` (id, name, version, inputs, outputs, tags) |
| `validate(input)` | Validates `input.filter_mode` is `'all'` or `'cells_only'` |
| `show(data, options)` | Returns `{ componentPath: 'frontend/View.vue' }` |

## Pinia Store (`useArtifactsExplorerStore`)

Store ID: `artifactsExplorer`

| State | Type | Description |
|-------|------|-------------|
| `availableArtifacts` | `ExplorerArtifact[]` | Loaded from `GET /api/v1/artifacts-map` |
| `isLoading` | `boolean` | Loading indicator |
| `error` | `string \| null` | Error message if load failed |
| `selectedArtifact` | `ExplorerArtifact \| null` | Set when user clicks a frontend-orchestrated artifact; App.vue watches this |

| Action | Description |
|--------|-------------|
| `loadArtifacts(filterMode)` | Calls `GET /api/v1/artifacts-map[?artifact_type=cell-type]` |
| `selectArtifact(artifact)` | Sets `selectedArtifact` → triggers App.vue watcher |
| `clearSelection()` | Resets `selectedArtifact` to null |

## ExplorerArtifact Interface

Mirrors `ArtifactRecord` from `backend/app/models/artifact.py`:

```typescript
interface ExplorerArtifact {
  artifact_id: string
  version: string
  artifact_type: 'cell-type' | 'service' | 'worker' | 'book' | 'job-type'
  stage: 'canonical' | 'sandbox' | 'runtime'
  identity: { name, description, icon, author }
  runtime: { entry_point, strategy, required_artifacts, env_vars }
  execution_model: { orchestrator: 'frontend' | 'launcher', heartbeat_channel, health_check }
  metadata: { tags }
}
```

## Integration with App.vue

```
[User] Clicks ➕ in FooterWindowManager
    ↓ emit('show-artifacts-explorer')
    ↓ App.vue: handleShowArtifactsExplorer()
        → Guard: if 'artifacts-explorer-cell' already in grid → return
        → Otherwise → handleCellTypeSelected(explorerType)
    ↓ artifacts-explorer-cell renders with category tabs
    ↓ [User] clicks "➕ Add to Workspace" on a frontend-orchestrated artifact
        → explorerStore.selectArtifact(artifact)
    ↓ App.vue watcher fires (guard: orchestrator === 'frontend' only)
        → handleCellTypeSelected(cellTypeDef) + clearSelection()
    ✅ New cell added to grid

    [User] views launcher-orchestrated artifact (service)
        → "🔄 Managed by Launcher" indicator shown
        → heartbeat_channel displayed if available
        → Clicking does NOT add anything to the grid
```

## Category Tabs (filter_mode: "all")

| Tab | Filters |
|-----|---------|
| 🗂️ All | All artifact types |
| 🧩 Cells | `artifact_type === 'cell-type'` |
| 🏗️ Infrastructure | `artifact_type === 'service'` |
| 🤖 Intelligence | `artifact_type === 'job-type'` |

## Stage Badges

| Stage | Visual |
|-------|--------|
| `canonical` | No badge (default, clean look) |
| `sandbox` | 🧪 sandbox (yellow badge) |

## Props (View.vue)

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `cellInstance` | `any` | — | BaseCell instance from resolveViewSpec |
| `cell` | `any` | — | `{ cellTypeName, cellType, initialData }` from resolveViewSpec |

`filter_mode` is read from `cell.cellType.default_initial_data.filter_mode`.

## Phases

- **Phase 1** (PR #2881): Picker mode — replaced `AddCellModal.vue`, cells only
- **Phase 2** (this PR): Universal explorer — all artifact types, category tabs, Strategy Interface
- **Phase 3** (future): Stage promotion (sandbox → canonical), social filters, heartbeat live status

## References

- [ADDING_NEW_CELL_TYPE.md](../../../../docs/official/ADDING_NEW_CELL_TYPE.md)
- [RULESET.md](../../../../docs/official/RULESET.md)
- Issue: `docs/issues/artifacts-explorer-cell-artifact-runtime-map-integration/ISSUE.md`
- PR #2885: `[FEAT] - Artifact Runtime Map: Virtual Catalog via ArtifactLoader + /api/v1/artifacts-map`
