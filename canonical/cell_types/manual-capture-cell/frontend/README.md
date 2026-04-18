# Manual Capture Cell – Frontend

## Purpose

Vue 3 frontend for the **Manual Capture Cell** — allows users to manually capture and save content (screenshots, snippets, data) from the current notebook context.

## Content Index

| File | Description |
|------|-------------|
| [`View.vue`](./View.vue) | Main Vue component — capture area, preview, metadata form, save button |
| [`types.ts`](./types.ts) | TypeScript type definitions for capture data structures |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`composables/`](./composables/) | `useManualCapture.ts` — capture logic, preview state, upload handling |
| [`translations/`](./translations/) | `en.json`, `pt-BR.json` — i18n strings |

## Related

- [`../`](../) — Manual Capture Cell root
