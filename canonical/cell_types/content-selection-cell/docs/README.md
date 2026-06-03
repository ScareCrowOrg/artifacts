# Content Selection Cell

## Overview

The **Content Selection Cell** is a utility cell that provides a standardized interface for browsing and selecting persisted content. It implements the `BaseCell` interface and delegates all list/load operations to the existing `ContentManagerCell` via the `POST /api/cells/execute-ephemeral` endpoint.

**Key Purpose**: Enable users to select previously persisted content (uploaded via `content-upload-cell` or any other means) for reuse in other cells, replacing the need to re-upload or manually type `content_id`.

## How It Works

1. **User opens the cell** in the workspace
2. **Cell loads persisted content** via `ContentSelectionCell.execute({ action: 'list' })`, delegating to `ContentManagerCell`
3. **User filters** by content type (`image-png`, `vector-svg`, `3d-glb`) or searches by filename
4. **User navigates** through pages (previous/next)
5. **User clicks** on a content row → item is highlighted
6. **User clicks "Confirm Selection"** → cell returns `content_id` + metadata for use by other cells

## Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `content_type_id` | `string \| null` | `null` | Initial content type filter. Shows all types if null. |
| `allow_multiple` | `boolean` | `false` | Allow selecting multiple items (future use). |
| `view_mode` | `string` | `"list"` | Display mode: "list" (table) or "grid" (future). |

## Usage

### Standalone (via Add Cell in Workspace)

1. Open the workspace
2. Click "Add Cell" and search for "Content Selection"
3. The cell loads all persisted content automatically
4. Use the type filter dropdown to narrow by content type
5. Type in the search box to filter by filename
6. Click on a content row to select it
7. Click "Confirm Selection" to commit the selection

### Programmatic (from other cells)

```typescript
import { ContentSelectionCell } from '@/cells/content-selection-cell/frontend/ContentSelectionCell'

// List contents
const selector = new ContentSelectionCell()
const listResult = await selector.execute({
  action: 'list',
  content_type_id: 'image-png',  // optional filter
  limit: 20,
  offset: 0
})

if (listResult.success) {
  const { contents, total } = listResult.output
  // contents = [{ id, content_type_id, filename, size_bytes, ... }]
}

// Load specific content (for preview/download)
const loadResult = await selector.execute({
  action: 'load',
  content_id: '550e8400-e29b-...',
  direct_download: false  // → presigned URL (true returns binary)
})

if (loadResult.success) {
  const { presigned_url, filename, size_bytes, mime_type } = loadResult.output
}
```

## Dependencies

- **`ContentManagerCell`** — All list/load operations are delegated to this existing cell
- **`POST /api/cells/execute-ephemeral`** — Existing endpoint (no custom endpoints created)
- **`apiFetch`** — Automatic authentication (never plain `fetch()`)

## Architecture

```
User opens Content Selection Cell
    │
    ▼
View.vue ───► ContentSelectionCell.execute({ action: 'list' })
                      │
                      ▼
          apiFetch('/api/cells/execute-ephemeral')
          { cell_type: 'content-manager-cell',
            input_data: { action: 'list', filters, limit, offset } }
                      │
                      ▼
          ContentManagerCell.handle_list()
          → Content.query_contents(filters) → MongoDB
                      │
                      ▼
          Returns { contents: ContentItem[], count, limit, offset, total }
                      │
                      ▼
          View.vue renders: table → filters → pagination → click-to-select
                      │
                      ▼
          User confirms selection
          → Returns { selected_content_id, selected_filename,
                      selected_content_type_id, selected_size_bytes,
                      selected_data_ref }
```

## Output Schema

| Field | Type | Description |
|-------|------|-------------|
| `selected_content_id` | `string` | UUID of the selected Content record |
| `selected_filename` | `string` | Filename of the selected content |
| `selected_content_type_id` | `string` | Content type ID (e.g. image-png, vector-svg, 3d-glb) |
| `selected_size_bytes` | `number` | File size in bytes |
| `selected_data_ref` | `string` | Storage reference path |

## Selection Flow

```
❌ BEFORE: Upload → content-upload-cell → content_id → "how to reuse?" → re-upload
✅ AFTER:  Upload → content-upload-cell → content_id → content-selection-cell → selects → uses in other cells
```

## Error Handling

The cell handles three categories of errors:

1. **Validation Errors** — Invalid action, missing content_id for load, invalid limit
2. **Backend Errors** — Server returns error status or list/load operation fails
3. **Network Errors** — Connection issues, fetch failures

## States

| State | Description |
|-------|-------------|
| **Loading** | Content list is being fetched from the backend |
| **Empty** | No content found (with context-appropriate message) |
| **Error** | Error occurred (with retry button) |
| **Content List** | Contents displayed in a table with filters and pagination |
| **Selected** | A content item is selected (highlighted row) |
| **Confirmed** | Selection confirmed (confirmation message shown) |

## Files

| File | Purpose |
|------|---------|
| `frontend/ContentSelectionCell.ts` | BaseCell implementation (execute, describe, validate, health_check) |
| `frontend/View.vue` | Vue component with selection UI |
| `frontend/tests/ContentSelectionCell.spec.ts` | Unit tests (≥90% coverage) |
| `docs/README.md` | This file |

## Related

- [CELL_BINARY_PERSISTENCE_FLOW_WIREFRAME.md](../../../../docs/official/wireframe/artifacts/viewers/CELL_BINARY_PERSISTENCE_FLOW_WIREFRAME.md)
- [Content Selection Cell Issue](../../../../docs/issues/content-selection-cell/ISSUE.md)
