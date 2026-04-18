# Content Explorer Cell – Frontend

## Purpose

Vue 3 frontend for the **Content Explorer Cell** — a composed BaseCell that provides a unified asset browsing experience by combining `ContentTypeManagerCell` and `ContentManagerCell`.

## Features

- Browse available content types (images, 3D meshes, SVGs, etc.)
- Filter assets by selected type
- View asset details and metadata
- Delete assets via ContentManagerCell composition
- Ephemeral execution (no persistent cell instance required)

## Content Index

| File | Description |
|------|-------------|
| [`ContentExplorerCell.ts`](./ContentExplorerCell.ts) | BaseCell implementation — action routing, composition of ContentTypeManager + ContentManager |
| [`View.vue`](./View.vue) | Main Vue component — type selector, asset grid, detail panel |
| [`composables.ts`](./composables.ts) | Composables for content type selection and asset loading |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`components/`](./components/) | Sub-components: `AssetActions.vue`, `AssetGrid.vue`, `TypeSelector.vue` |
| [`tests/`](./tests/) | Frontend unit and component tests |

## Related

- [`../`](../) — Content Explorer Cell root
- [`../../content-manager-cell/`](../../content-manager-cell/) — Provides asset CRUD operations
- [`../../content-type-manager-cell/`](../../content-type-manager-cell/) — Provides type discovery
