# Content Type Manager Cell

## Overview

The **Content Type Manager Cell** is a headless-first, ephemeral utility cell that provides content type discovery functionality. It enables applications to list available content types with their metadata, supporting the development of type-aware asset browsers and filtering interfaces.

### Key Features

- **Content Type Discovery**: List all available content types in the system
- **Headless-First Design**: No UI component - designed for composition
- **Ephemeral Execution**: No persistent cell instance required
- **BaseCell Compliance**: Fully implements the BaseCell interface
- **Type-Safe**: Complete TypeScript implementation with type definitions
- **Fast**: No database queries - pure filesystem-based metadata

### Use Cases

- Building type selectors for content explorers
- Filtering content by type in asset browsers
- Discovering available content types for upload forms
- Validating content type IDs in other cells
- Generating content type documentation

---

## Architecture

### Cell Type

**Category**: `ephemeral`  
**Version**: `1.0.0`  
**Implements**: `BaseCell` interface

### Directory Structure

```
content-type-manager-cell/
├── type.json                           # Symlink to canonical definition
├── backend/
│   ├── scripts/
│   │   └── main.py                     # Main execution script
│   └── tests/
│       └── test_main.py                # Backend tests (90%+ coverage)
├── frontend/
│   ├── ContentTypeManagerCell.ts       # BaseCell implementation
│   └── tests/
│       └── ContentTypeManagerCell.test.ts  # Frontend tests (90%+ coverage)
└── docs/
    └── README.md                       # This file
```

### Execution Flow

1. **Frontend** → Calls `cell.execute({ action: 'list', ... })`
2. **BaseCell** → Validates input via `validate()`
3. **API Call** → POST to `/api/cells/execute-ephemeral`
4. **Backend** → `execute_cell()` routes to `handle_list()`
5. **ContentTypeLoader** → Loads types from filesystem (artifacts/canonical/content_types/)
6. **Response** → Returns array of ContentType metadata

---

## Usage

### TypeScript

```typescript
import { ContentTypeManagerCell } from '@/cells/content-type-manager-cell/ContentTypeManagerCell'

// Create cell instance
const cell = new ContentTypeManagerCell()

// List all content types
const result = await cell.execute({
  action: 'list'
})

if (result.success) {
  console.log('Available content types:', result.output.types)
  console.log('Total types:', result.output.total)
} else {
  console.error('Error:', result.output.error)
}
```

### With Limit Parameter

```typescript
// List only first 10 types
const result = await cell.execute({
  action: 'list',
  limit: 10
})
```

### Validation Before Execution

```typescript
const cell = new ContentTypeManagerCell()
const input = { action: 'list', limit: 50 }

// Validate input
const errors = await cell.validate(input)
if (errors.length > 0) {
  console.error('Validation errors:', errors)
} else {
  // Execute
  const result = await cell.execute(input)
}
```

### Cell Metadata

```typescript
const cell = new ContentTypeManagerCell()
const metadata = cell.describe()

console.log('Cell ID:', metadata.id)
console.log('Cell Name:', metadata.name)
console.log('Version:', metadata.version)
console.log('Inputs:', metadata.inputs)
console.log('Outputs:', metadata.outputs)
```

---

## API Reference

### Actions

#### `list` - List Available Content Types

Lists all content types defined in the system with their metadata.

**Request**:
```typescript
{
  action: 'list',
  limit?: number  // Optional, default: 100, range: 1-100
}
```

**Response** (Success):
```typescript
{
  success: true,
  output: {
    types: [
      {
        id: string,           // e.g., "image-png"
        name: string,         // e.g., "PNG Image Asset"
        description: string,  // e.g., "PNG raster images"
        mime_type: string,    // e.g., "image/png"
        version: string,      // e.g., "1.0.0"
        max_size_bytes: number,      // e.g., 52428800
        allowed_extensions: string[], // e.g., [".png"]
        render_hints?: object         // Optional frontend hints
      },
      // ... more types
    ],
    total: number  // Total number of types available
  },
  execution_time: number  // Milliseconds
}
```

**Response** (Error):
```typescript
{
  success: false,
  output: {
    error: string,
    validation_errors?: ValidationError[]
  },
  execution_time: number
}
```

---

## Integration Examples

### Example 1: ContentExplorerCell Integration

```typescript
import { ContentTypeManagerCell } from '@/cells/content-type-manager-cell/ContentTypeManagerCell'
import { ContentManagerCell } from '@/cells/content-manager-cell/ContentManagerCell'

// Component for browsing content by type
export class ContentExplorerCell {
  private typeManager = new ContentTypeManagerCell()
  private contentManager = new ContentManagerCell()
  
  async loadTypesAndContent() {
    // 1. Get available types
    const typesResult = await this.typeManager.execute({ action: 'list' })
    
    if (!typesResult.success) {
      throw new Error('Failed to load content types')
    }
    
    const types = typesResult.output.types
    
    // 2. For each type, get content count
    const typesWithCounts = await Promise.all(
      types.map(async (type) => {
        const contentResult = await this.contentManager.execute({
          action: 'list',
          filters: { content_type_id: type.id },
          limit: 0  // Just get count
        })
        
        return {
          ...type,
          count: contentResult.success ? contentResult.output.total : 0
        }
      })
    )
    
    return typesWithCounts
  }
}
```

### Example 2: Type Selector Component

```vue
<template>
  <div class="type-selector">
    <label>Content Type:</label>
    <select v-model="selectedType">
      <option value="">All Types</option>
      <option 
        v-for="type in contentTypes" 
        :key="type.id" 
        :value="type.id"
      >
        {{ type.name }} ({{ type.allowed_extensions.join(', ') }})
      </option>
    </select>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ContentTypeManagerCell } from '@/cells/content-type-manager-cell/ContentTypeManagerCell'

const contentTypes = ref([])
const selectedType = ref('')

onMounted(async () => {
  const cell = new ContentTypeManagerCell()
  const result = await cell.execute({ action: 'list' })
  
  if (result.success) {
    contentTypes.value = result.output.types
  }
})
</script>
```

### Example 3: Upload Form with Type Validation

```typescript
import { ContentTypeManagerCell } from '@/cells/content-type-manager-cell/ContentTypeManagerCell'

export async function validateFileForType(file: File, contentTypeId: string) {
  const cell = new ContentTypeManagerCell()
  const result = await cell.execute({ action: 'list' })
  
  if (!result.success) {
    throw new Error('Failed to load content types')
  }
  
  // Find the content type
  const contentType = result.output.types.find(t => t.id === contentTypeId)
  
  if (!contentType) {
    throw new Error(`Unknown content type: ${contentTypeId}`)
  }
  
  // Check file extension
  const fileExt = '.' + file.name.split('.').pop()?.toLowerCase()
  if (!contentType.allowed_extensions.includes(fileExt)) {
    throw new Error(
      `Invalid file extension. Expected: ${contentType.allowed_extensions.join(', ')}`
    )
  }
  
  // Check file size
  if (file.size > contentType.max_size_bytes) {
    throw new Error(
      `File too large. Max size: ${contentType.max_size_bytes} bytes`
    )
  }
  
  return true
}
```

---

## Testing

### Backend Tests

Run backend tests:
```bash
cd artifacts/canonical/cell_types/content-type-manager-cell/backend
python -m pytest tests/test_main.py -v --cov=scripts --cov-report=term
```

Expected coverage: **90%+**

### Frontend Tests

Run frontend tests:
```bash
cd cockpit-vue
npm run test -- artifacts/canonical/cell_types/content-type-manager-cell/frontend/tests/ContentTypeManagerCell.test.ts
```

Expected coverage: **90%+**

### Type Checking

```bash
cd cockpit-vue
npm run type-check
```

---

## Data Sources

### ContentType Definitions

Content types are loaded from:
```
artifacts/canonical/content_types/
├── image-png.json
├── vector-svg.json
├── 3d-glb.json
└── ... (more types)
```

Each JSON file defines:
- `id`: Unique identifier
- `name`: Human-readable name
- `description`: Purpose description
- `mime_type`: MIME type
- `version`: Version number
- `max_size_bytes`: Maximum file size
- `allowed_extensions`: Array of allowed file extensions
- `render_hints`: (Optional) Frontend rendering configuration

---

## Performance

### Benchmarks

- **List 3 types**: ~5-10ms (filesystem read, no DB)
- **List 50 types**: ~20-30ms (filesystem read, no DB)
- **Caching**: ContentTypeLoader caches loaded types

### Optimization Tips

1. **Use limit parameter**: When you only need a subset of types
2. **Cache results**: Types rarely change - cache in frontend state
3. **Parallel loading**: Combine with content queries in parallel

---

## Design Decisions

### Why Headless?

The Content Type Manager Cell is **headless-first** because:

1. **Reusability**: Can be composed into many different UIs
2. **Separation of Concerns**: Data provider vs. UI renderer
3. **Flexibility**: Multiple cells can use the same type discovery logic
4. **Performance**: No UI overhead for headless use cases

### Why Ephemeral?

Content type discovery is:

- **Stateless**: No need to persist cell instances
- **Read-only**: Types are defined in Git, not created by users
- **Utility**: Acts as a service, not a persistent entity

### Why No Database?

Content types are **system metadata**, not user data:

- Defined in Git (artifacts/canonical/content_types/)
- Version-controlled with code
- Rarely change
- Fast filesystem reads with caching

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Missing 'action' parameter` | No action provided | Include `action: 'list'` |
| `Invalid action 'xyz'` | Wrong action name | Use `action: 'list'` |
| `Invalid limit` | Limit out of range | Use 1-100 |
| `API request failed` | Backend unavailable | Check backend service |
| `Failed to list content types` | ContentTypeLoader error | Check filesystem permissions |

### Error Response Format

```typescript
{
  success: false,
  output: {
    error: string,  // Human-readable error message
    validation_errors?: ValidationError[]  // If validation failed
  },
  execution_time: number
}
```

---

## Future Enhancements

### Phase 2 (Optional)
- [ ] `get` action - Get single content type by ID
- [ ] Caching strategies (types rarely change)
- [ ] Asset count per type (from ContentManager)

### Phase 3 (Future)
- [ ] `create` action - Add new content type (admin only)
- [ ] `update` action - Update type definition
- [ ] `delete` action - Remove type (with constraints)
- [ ] Audit logging for type modifications

---

## Related Documentation

- [BaseCell Interface](../../../../../docs/official/ADDING_NEW_CELL_TYPE.md)
- [ContentManager Cell](../content-manager-cell/docs/README.md)
- [Content Types Documentation](../../../../content_types/README.md)
- [RULESET.md](../../../../../docs/official/RULESET.md)

---

**Version**: 1.0.0  
**Last Updated**: 2026-02-08  
**Status**: Production Ready
