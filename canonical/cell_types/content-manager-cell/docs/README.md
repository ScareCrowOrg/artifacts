---
processed: true
processed_date: 2026-03-06
generated_docs:
  - docs/official/backend/testing/test-remediation-2026-q1.md
themes:
  - cells
  - frontend
  - testing
modules:
  - frontend
code_verified: true
dead_docs_found: false
---
# Content Manager Cell

Persistent content management with Cloudflare R2 storage. Provides list, load, and persist operations for typed content assets (images, vectors, 3D models).

**✅ Implements BaseCell Interface** - Can be imported and used as an ephemeral utility by other cells.

## Overview

The Content Manager Cell is a **modular, reusable cell** that acts as a proxy for content persistence and retrieval. It integrates with the ContentManager service and supports both Cloudflare R2 cloud storage and local filesystem storage.

**New in v1.0**: Implements the BaseCell interface, enabling programmatic usage as an ephemeral utility cell.

### Key Features

- **List Contents**: Query contents with filters (by type, assignee, tags) and pagination
- **Load Binary**: Stream downloads from R2 via presigned URLs or direct download
- **Persist Content**: Upload to R2 + MongoDB with schema validation
- **Conditional UI**: Optional persistence form for interactive uploads
- **Storage Modes**: Cloudflare R2 (production) or Local filesystem (development)
- **BaseCell Interface**: Can be imported and used by other cells (png-generator, svg-generator, etc.)
- **Ephemeral Execution**: No persistent cell instance required

## Architecture

```
content-manager-cell/
├── type.json                      # Symlink to canonical definition (ephemeral)
├── backend/
│   ├── scripts/
│   │   ├── main.py               # execute_cell(action, params)
│   │   ├── storage.py            # CloudflareR2Storage + LocalStorage
│   │   └── utils.py              # Helper functions
│   └── tests/
│       └── test_main.py          # Comprehensive tests
├── frontend/
│   ├── ContentManagerCell.ts     # ✅ BaseCell implementation (NEW)
│   ├── View.vue                  # Content list + persistence form
│   ├── composables.ts            # useContentManager hook
│   ├── types.ts                  # TypeScript interfaces
│   └── tests/
│       ├── ContentManagerCell.test.ts  # BaseCell tests (NEW)
│       └── View.spec.ts          # Component tests
└── docs/
    └── README.md                 # This file
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

There are two ways to use the Content Manager Cell:

1. **As a BaseCell** - Import and use programmatically in other cells (recommended for cell-to-cell composition)
2. **Via Backend API** - Direct HTTP calls to the execute-ephemeral endpoint

### Option 1: Using as BaseCell (TypeScript)

**Import and use in other cells:**

```typescript
// In png-generator-cell or any other cell:
import { ContentManagerCell } from '@/cells/content-manager-cell/frontend/ContentManagerCell'
import type { BaseCell, CellResult } from '@/types/BaseCell'

export class PngGeneratorCell implements BaseCell {
  private contentManager = new ContentManagerCell()

  async execute(input: Record<string, any>): Promise<CellResult> {
    // 1. Generate your PNG
    const pngData = await this.generatePNG(input.prompt)
    
    // 2. Persist using ContentManagerCell
    const persistResult = await this.contentManager.execute({
      action: 'persist',
      content_type_id: 'image-png',
      filename: `${input.prompt.substring(0, 20)}.png`,
      binary: pngData,  // Base64 or ArrayBuffer
      fragments: { 
        prompt: input.prompt,
        generated_at: new Date().toISOString()
      },
      tags: ['generated', 'png', 'ai'],
      origin_cell_id: this.cell_instance?.id
    })
    
    if (!persistResult.success) {
      return {
        success: false,
        output: {},
        execution_time: 0,
        error: `Failed to persist: ${persistResult.error}`
      }
    }
    
    // 3. Return result with content ID
    return {
      success: true,
      output: {
        content_id: persistResult.output.id,
        data_ref: persistResult.output.data_ref,
        png_url: `/api/content/${persistResult.output.id}`
      },
      execution_time: 100
    }
  }
  
  async describe() {
    return {
      id: 'png-generator-cell',
      name: 'PNG Generator',
      version: '1.0.0',
      description: 'Generates PNG images and persists them using ContentManagerCell',
      inputs: { prompt: { type: 'string', required: true } },
      outputs: { content_id: { type: 'string' } },
      tags: ['image', 'generator']
    }
  }
  
  validate(input: Record<string, any>) {
    return []
  }
}
```

**List existing contents:**

```typescript
const contentManager = new ContentManagerCell()

// List all PNG images
const listResult = await contentManager.execute({
  action: 'list',
  filters: {
    content_type_id: 'image-png',
    is_latest: true
  },
  limit: 20,
  offset: 0
})

if (listResult.success) {
  const contents = listResult.output.contents
  console.log(`Found ${contents.length} PNG images`)
}
```

**Load a specific content:**

```typescript
const loadResult = await contentManager.execute({
  action: 'load',
  content_id: 'content-uuid-here',
  direct_download: false  // Get presigned URL (faster)
})

if (loadResult.success) {
  const url = loadResult.output.presigned_url
  // Use the URL to display/download the content
}
```

### Option 2: Backend API Usage

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

The Content Manager Cell implements atomic persistence with comprehensive error handling. For detailed error codes, recovery procedures, and monitoring guidelines, see **[ERROR_CODES.md](./ERROR_CODES.md)**.

### Quick Reference

All actions return standardized error responses with detailed context:

```json
{
    "success": false,
    "action": "persist",
    "error": "User-friendly error message",
    "error_code": "MACHINE_READABLE_CODE",
    "details": {
        "context": "...",
        "cleanup_status": "...",
        "action_needed": "..."
    }
}
```

### Error Codes Summary

- **R2_UPLOAD_FAILED**: R2 upload failure (no files created)
- **MONGODB_INSERT_FAILED**: MongoDB failure after R2 success (cleanup succeeded)
- **ORPHANED_FILE_CLEANUP_FAILED**: Critical - orphaned file in R2 (manual intervention required)
- **VALIDATION_ERROR**: Input validation failure (missing/invalid parameters)

Common validation errors:
- `"Missing 'action' parameter"` - No action specified
- `"ContentType not found: ..."` - Invalid content type ID
- `"File too large. Max size: ..."` - File exceeds ContentType limit
- `"Missing required fragment '...' for ContentType"` - Fragment validation failed
- `"Content not found: ..."` - Invalid content ID

**See [ERROR_CODES.md](./ERROR_CODES.md) for complete error documentation.**

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
