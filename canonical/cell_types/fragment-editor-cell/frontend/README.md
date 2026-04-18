# Fragment Editor Cell – Frontend

## Purpose

Vue 3 frontend for the **Fragment Editor Cell** — a BaseCell that allows users to create, edit, and load markdown fragments for cells within the Dynamic Workspace.

Part of the **Classic Workspace Deprecation** epic.

## Content Index

| File | Description |
|------|-------------|
| [`FragmentEditorCell.ts`](./FragmentEditorCell.ts) | BaseCell implementation — `create`, `edit`, `load` actions for fragment management |
| [`View.vue`](./View.vue) | Main Vue component — markdown editor, fragment list, save/load UI |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`composables/`](./composables/) | `useFragmentEditor.ts` — reactive fragment editing state and API calls |
| [`tests/`](./tests/) | `FragmentEditorCell.test.ts` — unit tests (README already present) |
| [`translations/`](./translations/) | `en.json`, `pt-BR.json` — i18n strings |

## Related

- [`../`](../) — Fragment Editor Cell root
- [Dynamic Workspace](../../../../book_types/) — The workspace that uses this cell
