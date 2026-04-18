# Unclassified Cell – Frontend

## Purpose

Vue 3 frontend for the **Unclassified Cell** — a general-purpose cell for displaying and editing content that does not fit a specific cell type. Supports both editable and read-only (fragment) views.

## Content Index

| File | Description |
|------|-------------|
| [`View.vue`](./View.vue) | Main component — conditional edit/view mode, content display, save/cancel controls |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`composables/`](./composables/) | `useUnclassifiedCell.ts` — cell data loading, content editing, fragment view, state management |
| [`tests/`](./tests/) | `View.spec.ts` — component tests |
| [`translations/`](./translations/) | `en.json`, `pt-BR.json` — i18n strings |

## Related

- [`../`](../) — Unclassified Cell root
