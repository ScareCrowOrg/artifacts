# Content Type Manager Cell – Frontend

## Purpose

Vue 3 frontend for the **Content Type Manager Cell** — a headless-first BaseCell that provides content type discovery for other cells. Designed for ephemeral execution with no persistent state.

## Features

- List all available content types with metadata
- Ephemeral execution (no persistent cell instance required)
- **Headless-first** design (no `View.vue` — used programmatically by other cells)
- Type-safe inputs and outputs

## Content Index

| File | Description |
|------|-------------|
| [`ContentTypeManagerCell.ts`](./ContentTypeManagerCell.ts) | BaseCell implementation — `list-types` and `get-schema` actions, headless execution |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`tests/`](./tests/) | `ContentTypeManagerCell.test.ts` — unit tests |

## Usage

```typescript
import { ContentTypeManagerCell } from './ContentTypeManagerCell'

const cell = new ContentTypeManagerCell(cellUUID, notebook)
const result = await cell.run({ action: 'list-types' })
// result.data.types = ['png-image', '3d-mesh', 'svg-vector', ...]
```

## Related

- [`../`](../) — Content Type Manager Cell root
- [`../../content-explorer-cell/`](../../content-explorer-cell/) — Primary consumer of this cell
