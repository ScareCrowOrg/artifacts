# Image Content Cell

**Ephemeral viewer cell** for displaying, editing metadata, downloading, and copying persisted image content.

## Overview

The `image-content-cell` provides a dedicated viewer for images that have already been persisted to storage (via the PNG Generator Cell + PersistModal). It removes the download/copy responsibilities from the PNG Generator Cell, following the separation of concerns principle.

## Usage

### Via CellFactory (from PNG Generator)

After generating and persisting an image, the PNG Generator creates an `image-content-cell` instance:

```typescript
cellFactory.addChildCell('image-content-cell', {
  content_id: 'uuid-here',
  relative_url: '/runtime/user/.../file.png'
})
```

### Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `content_id` | `string\|null` | `null` | UUID of the persisted content to display |
| `relative_url` | `string\|null` | `null` | Relative URL for direct file serving via Runtime File Server |

Either `content_id` or `relative_url` is required. When both are provided, `relative_url` takes precedence for image display (avoids an extra API call).

## Actions (ImageContentCell.execute())

### `load`

Loads content data and builds the image URL for display.

- If `relative_url` provided: builds full URL with `/artifacts` prefix (routes through RuntimeFileServer for CORS support)
- If `content_id` provided: fetches content metadata via `GET /api/contents/{id}`

### `update-metadata`

Updates content metadata **in-place** via `PATCH /api/contents/{content_id}`.

- Fields: `tags`, `metadata`, `name`
- Does NOT create a new version (unlike `POST .../versions`)
- Requires ownership of the content (403 if not owner)

### `download`

Requests a file download via `postMessage FILE_DOWNLOAD` (cross-origin iframe compatible).

### `copy`

Fetches the image blob and writes it to the clipboard via `navigator.clipboard.write()`.

## View.vue States

| State | Condition | Display |
|-------|-----------|---------|
| **Loading** | Content being fetched | Spinner + message |
| **Error** | Failed to load content | Error message with details |
| **Empty** | No `content_id` or `relative_url` provided | Placeholder illustration |
| **Loaded** | Content loaded successfully | Image + metadata form + action buttons |

## Integration

- **PNG Generator Cell**: Removed `handleDownload()` and `handleCopy()` — replaced by "Abrir no Viewer" button that creates this cell
- **CellFactory**: Standard `.addChildCell()` pattern
- **Backend**: Requires `PATCH /api/contents/{content_id}` endpoint (added to `content_router.py`)
