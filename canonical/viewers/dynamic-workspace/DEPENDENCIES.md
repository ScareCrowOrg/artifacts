# DEPENDENCIES.md

Dependencies for `DynamicWorkspace v2` viewer.

---

## Shared Infrastructure (`artifacts/shared/`)

These files were **copied** from `cockpit-vue/src/` to make `@/` imports work in the viewer context.

| Destination | Source | Notes |
|---|---|---|
| `shared/utils/logger.js` | `cockpit-vue/src/utils/logger.js` | Namespaced logging; import as `@/utils/logger` |
| `shared/utils/cellTypeLoaderUtil.ts` | `cockpit-vue/src/utils/cellTypeLoaderUtil.ts` | Loads `type.json` via fetch; import as `@/utils/cellTypeLoaderUtil` |
| `shared/types/BaseCell.ts` | `cockpit-vue/src/types/BaseCell.ts` | BaseCell abstract class; import as `@/types/BaseCell` |

### Path Changes
- `@/utils/logger` → `artifacts/shared/utils/logger.js` (via vite.config.ts alias `@/utils`)
- `@/types/BaseCell` → `artifacts/shared/types/BaseCell.ts` (via vite.config.ts alias `@/types`)

---

## Cell Type Loading (`useCellViewProvider.ts`)

| Import Type | URL Pattern | Notes |
|---|---|---|
| `type.json` | `http://localhost:5050/local/canonical/cell_types/{name}/type.json` | Fetched at runtime from ScareRunner backend |
| Cell class | `/canonical/cell_types/{name}/frontend/{BasecellFile}.ts` | Dynamic import via browser URL (Vite resolves) |
| View component | `/canonical/cell_types/{name}/frontend/View.vue` | Dynamic import via browser URL (Vite resolves) |

### Fallback Strategy
If the ScareRunner backend (port 5050) is not available:
1. `getCellTypes()` returns an empty list (modal shows "loading failed")
2. Cell instantiation fails gracefully (cell shows error state in grid)
3. No crash in App.vue — errors are caught and surfaced per-cell

---

## Runtime Dependencies (in `artifacts/package.json`)

| Package | Version | Purpose |
|---|---|---|
| `vue` | `^3.5.22` | Vue 3 reactivity + components |
| `pinia` | `^3.0.4` | Workspace state store |
| `vue-i18n` | `^9.14.5` | Translation system (layout.* keys) |
| `vue3-grid-layout-next` | `^1.0.7` | **ADDED** — drag/resize grid (Phase 2+; `GridContainer.vue` uses CSS grid as interim) |

### `vue3-grid-layout-next` Note
Added to `package.json` for future `GridContainer.vue` upgrade.
Currently, `GridContainer.vue` uses CSS Grid (12-column, 50px row height).
When `vue3-grid-layout-next` is available, `GridContainer.vue` can be upgraded to use it
by replacing the `<div class="grid-layout">` with `<GridLayout>` + `<GridItem>`.

---

## Phase 3 Refactor Opportunities

| Item | Current | Future (Phase 3) |
|---|---|---|
| Grid layout | CSS Grid (static) | vue3-grid-layout-next (drag/resize) |
| Cell types loading | fetch from backend + hardcoded fallback | HybridDatabase.listCellTypes() API |
| Layout persistence | stub (emit-based) | HybridDatabase.saveLayoutBook() |
| BaseCell in shared | Full copy from cockpit-vue | Extract to shared npm package |
