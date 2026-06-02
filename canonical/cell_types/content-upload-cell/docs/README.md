# Content Upload Cell

## Overview

The **Content Upload Cell** is a utility cell that provides a standardized file upload and persistence flow. It implements the `BaseCell` interface and delegates all backend persistence to the existing `ContentManagerCell` via the `POST /api/cells/execute-ephemeral` endpoint.

**Key Purpose**: Replace ad-hoc data URL handling in prototyping cells (3D Mesh, PNG Generator, etc.) with a clean, persistent Content reference approach.

## How It Works

1. **User selects a file** via drag-and-drop or file picker
2. **File is read as Base64** in the browser
3. **`ContentUploadCell.execute()`** is called with `{ filename, binary, assignee_id, ... }`
4. **Execute delegates** to `ContentManagerCell` via `POST /api/cells/execute-ephemeral`
5. **Backend persists** the file to storage (R2 or LocalStorage) and creates a MongoDB Content record
6. **Returns** `{ content_id, data_ref, filename, size_bytes }` — a lightweight reference (~36 bytes)

## Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `content_type_id` | `string \| null` | `null` | Content type for the upload. Auto-detected from MIME if null. |
| `allowMultiple` | `boolean` | `false` | Allow selecting multiple files (future use). |

## Usage

### Standalone (via Add Cell in Workspace)

1. Open the workspace
2. Click "Add Cell" and search for "Content Upload"
3. Drag and drop a file or click to select
4. Click "Upload & Persist"
5. The result displays `content_id`, `filename`, and `size_bytes`

### Programmatic (from other cells)

```typescript
import { ContentUploadCell } from '@/cells/content-upload-cell/frontend/ContentUploadCell'

const uploader = new ContentUploadCell()
const result = await uploader.execute({
  filename: 'my-file.png',
  binary: base64Data,        // Base64-encoded file content
  assignee_id: 'user-123',   // Runtime path routing
  content_type_id: 'image-png',
  origin_cell_id: 'cell-456' // For lineage tracking
})

if (result.success) {
  const { content_id, data_ref } = result.output
  // Use content_id as a lightweight reference (~36 bytes)
  // instead of the full data URL
}
```

### Using the `content_id` Reference

The `content_id` returned by this cell is a UUID that other cells can use as a lightweight reference:

- **Before**: Data URL 1MB+ in memory → inline in Redis → lost on save/load
- **After**: Upload → ContentUploadCell.execute() → Content in storage → `content_id` (~36 bytes)

## Dependencies

- **`ContentManagerCell`** — All persistence is delegated to this existing cell
- **`POST /api/cells/execute-ephemeral`** — Existing endpoint (no custom endpoints created)
- **`apiFetch`** — Automatic authentication (never plain `fetch()`)

## Architecture

```
User selects file
    │
    ▼
View.vue ─── reads as Base64 ───► ContentUploadCell.execute()
                                          │
                                          ▼
                              apiFetch('/api/cells/execute-ephemeral')
                              { cell_type: 'content-manager-cell',
                                input_data: { action: 'persist', ... } }
                                          │
                                          ▼
                              ContentManagerCell.handle_persist()
                              get_storage_backend(assignee_id)
                              → runtime/user/{assignee_id}/contents/
                                          │
                                          ▼
                              Returns { content_id, data_ref, filename, size_bytes }
```

## Output Schema

| Field | Type | Description |
|-------|------|-------------|
| `content_id` | `string` | UUID of the persisted Content record |
| `data_ref` | `string` | Storage reference path |
| `filename` | `string` | Original filename |
| `size_bytes` | `number` | File size in bytes |

## Error Handling

The cell handles three categories of errors:

1. **Validation Errors** — Missing required fields (filename, binary, assignee_id)
2. **Backend Errors** — Server returns error status (500, 503) or persist fails
3. **Network Errors** — Connection issues, fetch failures

## Files

| File | Purpose |
|------|---------|
| `frontend/ContentUploadCell.ts` | BaseCell implementation (execute, describe, validate, health_check) |
| `frontend/View.vue` | Vue component with upload UI |
| `frontend/tests/ContentUploadCell.spec.ts` | Unit tests (≥90% coverage) |
| `docs/README.md` | This file |

## Related

- [CELL_BINARY_PERSISTENCE_FLOW_WIREFRAME.md](../../../../docs/official/wireframe/artifacts/viewers/CELL_BINARY_PERSISTENCE_FLOW_WIREFRAME.md)
- [Content Upload Cell Issue](../../../../docs/issues/content-upload-cell/ISSUE.md)
