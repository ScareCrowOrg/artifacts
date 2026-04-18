# File Editor v2 – Frontend

## Purpose

Vue 3 frontend for the **File Editor v2 Cell** — an improved file editing cell with markdown support, file configuration dialog, and i18n support. Full dark mode and theme compliance.

## Content Index

| File | Description |
|------|-------------|
| [`View.vue`](./View.vue) | Main Vue component — code/markdown editor interface with syntax highlighting, save/discard controls; full i18n and theme validated |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`components/`](./components/) | `FileConfigDialog.vue` (file settings modal), `MarkdownEditor.vue` (rich markdown editing) |
| [`composables/`](./composables/) | `useFileEditor.ts` — file load/save/state management |
| [`tests/`](./tests/) | `View.spec.ts` — component tests |
| [`translations/`](./translations/) | `en.json`, `pt-BR.json` — i18n strings |

## Related

- [`../`](../) — File Editor v2 Cell root
