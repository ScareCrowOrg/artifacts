---
processed: true
processed_date: 2026-03-06
generated_docs:
  - docs/official/frontend/architecture/dynamic-cell-loading-vite.md
themes:
  - cells
  - frontend
  - artifacts
modules:
  - frontend
code_verified: true
dead_docs_found: false
---
# DynamicWorkspace v2 — Viewer

> **Phase 2**: Cell Rendering with HybridDatabase Integration

## Overview

This viewer runs inside a Vite-served iframe at:

```
http://localhost:5052/viewers/dynamic-workspace
```

It is loaded by `ViewerShell.vue` (Cockpit) as an isolated micro-frontend context.

## Architecture

```
Cockpit-Vue (shell host)
  └── ViewerShell.vue
        └── <iframe src="http://localhost:5052/viewers/dynamic-workspace">
              └── App.vue  ← Phase 2 orchestration
                    ├── useWorkspaceHandshake  (Phase 1)
                    ├── useGridLayout          (Phase 2 — grid state)
                    ├── useCellViewProvider    (Phase 2 — BaseCell + ViewSpec)
                    ├── GridContainer          (Phase 2 — CSS grid)
                    ├── CellItem               (Phase 2 — cell wrapper + toolbar)
                    ├── FooterWindowManager    (Phase 2 — add cell button)
                    └── AddCellModal           (Phase 2 — cell type picker)
```

## Phase 2 Data Flow

```
User clicks "Add Cell"
  ↓
AddCellModal opens (dark mode + i18n, adapted from v1)
  ├── Shows available cell types (from HybridDatabase/canonical JSONs)
  └── User selects type

App.handleCellTypeSelected(cellType)
  ├── addCell() → GridCell in loading state
  ├── instantiateCellByType() → dynamic import + new CellClass()
  ├── resolveViewSpec() → cellInstance.show() → {component, props}
  └── updateCell() → GridCell with viewSpec ready

GridContainer renders
  ├── For each cell: CellItem (toolbar + content area)
  └── CellItem: <component :is="viewSpec.component" v-bind="viewSpec.props" />
        ├── Custom View.vue (if cell has one)
        └── GeneratedFormView (if no custom view)
```

## Files

| File | Purpose |
|------|---------|
| `App.vue` | Root orchestrator (handshake + grid + modals) |
| `main.ts` | Vue 3 + Pinia + vue-i18n setup |
| `composables/useWorkspaceHandshake.ts` | postMessage receiver + backend validation |
| `composables/useGridLayout.ts` | Reactive grid cell state (add/remove/update) |
| `composables/useCellViewProvider.ts` | Cell type loading + BaseCell instantiation + show() |
| `components/` | UI components (see `components/README.md`) |
| `types/index.ts` | GridCell, CellTypeDefinition, ViewSpec, etc. |
| `i18n/` | vue-i18n messages (layout.* keys from v1) |
| `stores/workspaceStore.ts` | Handshake state (Phase 1) |
| `tests/useGridLayout.test.ts` | Unit tests for grid layout composable |
| `DEPENDENCIES.md` | Dependency analysis and refactor notes |

## Handshake Protocol (Phase 1 — preserved)

### 1. Cockpit → Runner (`INIT_WORKSPACE`)

```typescript
{
  type: 'INIT_WORKSPACE',
  payload: {
    workspaceId: string,
    sessionToken: string,
    cockpitOrigin: string,
    userId: string,
  },
  timestamp: number
}
```

### 2. Runner → Cockpit (`RUNNER_READY`)

```typescript
{
  type: 'RUNNER_READY',
  payload: {
    workspaceId: string,
    runnerOrigin: string,
    version: 'v2.0.0-phase2',
    capabilities: ['cell-rendering', 'basecell-v2'],
    status: 'ready',
  },
  timestamp: number
}
```

## Phase 3 (Next)

- Layout persistence (save/load LayoutBook via HybridDatabase)
- drag/resize grid (vue3-grid-layout-next upgrade for GridContainer)
- Multi-workspace support

