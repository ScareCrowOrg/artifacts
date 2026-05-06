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
# components/

DynamicWorkspace v2 — UI components.

All components are adapted from `cockpit-vue/src/components/layout/dynamic/` (v1).

## Component Inventory

| Component | Source | Changes |
|-----------|--------|---------|
| `CellItem.vue` | v1 CellWrapper | Props: `cell (GridCell)`; Events: `@remove/@minimize/@maximize`; renders `viewSpec.component` |
| `GridContainer.vue` | NEW | CSS-Grid wrapper; emits layout events; uses CellItem |
| `FooterWindowManager.vue` | v1 FooterWindowManager | Events: `@show-artifacts-explorer`, `@close-cell`; simplified |
| `GeneratedFormView.vue` | NEW | Fallback form renderer from `properties_schema`; calls `cellInstance.execute()` |
| `CellModal.vue` | v1 CellModal | Props: `cell (GridCell)`; no DynamicCellView dependency |
| `SaveLayoutBookModal.vue` | v1 SaveLayoutBookModal | Props: `cells[]`; Events: `@save-layout(name, desc)`, `@cancel` |
| `LayoutBookSelector.vue` | v1 LayoutBookSelector | Props: `layouts[]`; Events: `@load-layout(id)`, `@save-new` |

> **Note (Phase 4)**: `AddCellModal.vue` was removed and replaced by `artifacts-explorer-cell` — a dedicated cell type that renders a searchable picker grid. See `../../cell_types/artifacts-explorer-cell/README.md`.

## Preserved from v1

- ✅ Dark mode (`dark:` Tailwind classes throughout)
- ✅ i18n (`$t('layout.*')` keys preserved)
- ✅ Logger (`createLogger('layout:*')` namespaced)
- ✅ Accessibility (aria-labels, keyboard navigation)
- ✅ Loading and error states
- ✅ Animations (modal open/close transitions)

## v2 Architecture Changes

- Removed Pinia store injections (no `useDynamicLayout`, `useLayoutStore`, etc.)
- All data via explicit props, all mutations via emits
- `CellItem` renders `<component :is="viewSpec.component" v-bind="viewSpec.props" />`
- `GridContainer` uses CSS Grid (12-column layout, 50px row height)
- `GeneratedFormView` replaces `DynamicFormGenerator` — self-contained form from schema
