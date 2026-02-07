# Content Manager Cell

Persistent content management with Cloudflare R2 storage. Provides list, load, and persist operations for typed content assets (images, vectors, 3D models).

## Overview

The Content Manager Cell is a **modular, reusable cell** that acts as a proxy for content persistence and retrieval. It integrates with the ContentManager service and supports both Cloudflare R2 cloud storage and local filesystem storage.

### Key Features

- **List Contents**: Query contents with filters (by type, assignee, tags) and pagination
- **Load Binary**: Stream downloads from R2 via presigned URLs or direct download
- **Persist Content**: Upload to R2 + MongoDB with schema validation
- **Conditional UI**: Optional persistence form for interactive uploads
- **Storage Modes**: Cloudflare R2 (production) or Local filesystem (development)

## Architecture

```
content-manager-cell/
├── type.json                # Cell type definition
├── backend/
│   ├── scripts/
│   │   ├── main.py         # execute_cell(action, params)
│   │   ├── storage.py      # CloudflareR2Storage + LocalStorage
│   │   └── utils.py        # Helper functions
│   └── tests/
│       └── test_main.py    # Comprehensive tests
├── frontend/
│   ├── View.vue            # Content list + persistence form
│   ├── composables.ts      # useContentManager hook
│   ├── types.ts            # TypeScript interfaces
│   └── tests/
│       └── View.spec.ts    # Component tests
└── docs/
    └── README.md           # This file
```

## Configuration

### Environment Variables

Add to `.env`:

```bash
# Storage mode
STORAGE_MODE=local  # local | r2

# Local storage (when STORAGE_MODE=local)
STORAGE_LOCAL_PATH=/data/content

# Cloudflare R2 (when STORAGE_MODE=r2)
R2_ENABLED=true
R2_ACCOUNT_ID=your-account-id
R2_ACCESS_KEY_ID=your-access-key
R2_SECRET_ACCESS_KEY=your-secret-key
R2_BUCKET_NAME=scareverse-content
R2_PUBLIC_URL=https://content.scareverse.com
R2_PRESIGNED_URL_EXPIRY=3600
```

### Dependencies

Backend:
```bash
pip install boto3  # For R2 storage
```

Frontend: No additional dependencies required (uses existing Vue.js/TypeScript setup).

## Usage

### 1. List Contents

Query contents with filters and pagination:

```python
{
    "action": "list",
    "filters": {
        "content_type_id": "image-png",  # optional
        "assignee_id": "user-uuid",      # optional
        "tags": ["generated", "png"],    # optional
        "is_latest": true                # optional
    },
    "limit": 50,   # optional, default: 20
    "offset": 0    # optional, default: 0
}
```

**Response:**
```python
{
    "success": true,
    "action": "list",
    "data": {
        "contents": [...],
        "count": 42,
        "limit": 50,
        "offset": 0,
        "total": 420
    }
}
```

### 2. Load Content

Get presigned URL (recommended) or download binary:

```python
{
    "action": "load",
    "content_id": "uuid-of-content",
    "direct_download": false  # false = presigned URL (default)
}
```

**Response (Presigned URL):**
```python
{
    "success": true,
    "action": "load",
    "data": {
        "content_id": "uuid",
        "filename": "image.png",
        "presigned_url": "https://r2.scareverse.com/...",
        "presigned_expires_in": 3600,
        "size_bytes": 1024000,
        "mime_type": "image/png"
    }
}
```

**Response (Direct Download):**
```python
{
    "success": true,
    "action": "load",
    "data": {
        "content_id": "uuid",
        "filename": "image.png",
        "binary": "data:image/png;base64,...",  # Base64 encoded
        "size_bytes": 1024000,
        "mime_type": "image/png"
    }
}
```

### 3. Persist Content

Upload content with schema validation:

**Option A: Base64 in JSON (for files < 5 MB):**
```python
{
    "action": "persist",
    "content_type_id": "image-png",
    "filename": "generated_image.png",
    "binary": "data:image/png;base64,iVBORw0KGgoAAAANS...",
    "fragments": {
        "width": 512,
        "height": 512,
        "generation_method": "ai"
    },
    "tags": ["generated", "png"],
    "metadata": {"model": "sd-xl"},
    "origin_cell_id": "png-generator-cell"
}
```

**Option B: Multipart Form (for files 5-50 MB):**
```
POST /api/cells/{cell_id}/execute
Content-Type: multipart/form-data

Fields:
  action: "persist"
  content_type_id: "image-png"
  filename: "large_image.png"
  file: <binary bytes>
  fragments: '{"width": 1024, "height": 1024}'
  tags: '["large", "generated"]'
```

**Response:**
```python
{
    "success": true,
    "action": "persist",
    "data": {
        "id": "new-uuid",
        "content_type_id": "image-png",
        "filename": "generated_image.png",
        "size_bytes": 1024000,
        "data_ref": "r2://bucket/content/new-uuid/...",
        "version": 1,
        "created_at": "2026-02-07T..."
    }
}
```

## Integration Patterns

### From Other Cells

Use the content-manager-cell to persist generated content:

```python
# In png-generator-cell, svg-generator-cell, etc.

# 1. Generate content
png_binary = generate_image(prompt)

# 2. Prepare persistence action
content_data = {
    "action": "persist",
    "content_type_id": "image-png",
    "filename": f"generated_{timestamp}.png",
    "binary": png_binary,
    "fragments": {
        "width": 512,
        "height": 512,
        "generation_method": "ai"
    },
    "origin_cell_id": "png-generator-cell"
}

# 3. Execute via content-manager-cell
result = await cell.execute(content_data)

if result["success"]:
    content_id = result["data"]["id"]
    print(f"Content persisted: {content_id}")
```

### Frontend Usage

The composable provides reactive state management:

```vue
<script setup lang="ts">
import { useContentManager } from './composables'

const {
  contents,
  filters,
  isLoading,
  listContents,
  loadContent,
  persistContent
} = useContentManager('cell-id')

// List contents
await listContents()

// Load content
const result = await loadContent('content-id')
if (result && 'presigned_url' in result) {
  window.open(result.presigned_url, '_blank')
}

// Persist content
await persistContent({
  content_type_id: 'image-png',
  filename: 'test.png',
  binary: file,
  fragments: { width: 100, height: 100 }
})
</script>
```

## Content Types

Three canonical types are supported:

### 1. image-png
- **MIME**: `image/png`
- **Max Size**: 10 MB
- **Fragments**: `width`, `height`, `color_mode`, `has_transparency`, `generation_method`

### 2. vector-svg
- **MIME**: `image/svg+xml`
- **Max Size**: 5 MB
- **Fragments**: `width`, `height`, `viewbox`, `has_animations`

### 3. 3d-glb
- **MIME**: `model/gltf-binary`
- **Max Size**: 50 MB
- **Fragments**: `vertex_count`, `polygon_count`, `has_textures`, `has_animations`

## Storage Backends

### LocalStorage

- Stores files in local filesystem
- Directory structure: `{base_path}/{content_id}/{filename}`
- No presigned URL support (returns `null`)
- Suitable for development and testing

### CloudflareR2Storage

- S3-compatible cloud storage
- Supports presigned URLs (recommended)
- Configurable public URL for custom domains
- Production-ready with auto-fallback to local on error

## Error Handling

All actions return standardized error responses:

```python
{
    "success": false,
    "error": "Descriptive error message"
}
```

Common errors:
- `"Missing 'action' parameter"` - No action specified
- `"ContentType not found: ..."` - Invalid content type ID
- `"File too large. Max size: ..."` - File exceeds ContentType limit
- `"Missing required fragment '...' for ContentType"` - Fragment validation failed
- `"Content not found: ..."` - Invalid content ID

## Testing

### Backend Tests

Run with pytest:
```bash
pytest artifacts/canonical/cell_types/content-manager-cell/backend/tests/test_main.py -v
```

Coverage includes:
- Storage backends (local and R2)
- All three actions (list, load, persist)
- Error cases (invalid types, file too large, missing params)
- Pagination and filtering
- Fragment validation

### Frontend Tests

Run with Vitest:
```bash
npm run test -- content-manager-cell
```

Tests cover:
- Component rendering
- User interactions (filters, pagination, upload)
- API call mocking
- Error state handling

## Security Considerations

- **Presigned URLs**: Time-limited (default 1 hour), no auth required
- **File Size Limits**: Enforced at ContentType level
- **Fragment Validation**: Schema validation before persistence
- **Isolation**: Content filtered by `assignee_id` for multi-tenancy
- **MIME Type Validation**: Checked against ContentType definition

## Performance Tips

1. **Use presigned URLs** for downloads (avoids backend bandwidth)
2. **Paginate list results** (default limit: 20, max: 100)
3. **Filter by `is_latest`** to reduce query size
4. **Use multipart upload** for files > 5 MB
5. **Cache ContentType definitions** (loaded once per session)

## Troubleshooting

### R2 Connection Errors

If R2 storage fails, the system automatically falls back to local storage:

```
WARNING: R2 mode requested but R2_ENABLED=false. Falling back to local storage.
ERROR: R2 credentials not configured. Falling back to local storage.
ERROR: Failed to initialize R2 storage: ... Falling back to local storage.
```

### File Upload Issues

- **"File too large"**: Check ContentType `max_size_bytes`
- **"Invalid binary data format"**: Ensure Base64 encoding is correct
- **"Missing required fragment"**: Verify all required fragments are provided

### Presigned URL Not Working

- Check `R2_PUBLIC_URL` is configured correctly
- Verify R2 bucket has public access enabled
- Ensure `R2_PRESIGNED_URL_EXPIRY` is sufficient

## Roadmap

- [ ] Support for more content types (audio, video, documents)
- [ ] Batch upload/download operations
- [ ] Content versioning UI
- [ ] Storage analytics and usage metrics
- [ ] CDN integration for faster downloads
- [ ] Content preview in list view
- [ ] Advanced filtering (date range, file size, etc.)

## Contributing

When adding new content types:

1. Create JSON definition in `artifacts/canonical/content_types/`
2. Define `expected_fragments` schema
3. Set appropriate `max_size_bytes`
4. Update this README with new type details

## License

Part of the ScareVerseLab project.
