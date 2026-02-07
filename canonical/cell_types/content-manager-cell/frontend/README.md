# ContentManagerCell - BaseCell Implementation

This directory contains the BaseCell implementation of ContentManagerCell, enabling programmatic usage as an ephemeral utility cell.

## Files

- **`ContentManagerCell.ts`** - Main BaseCell implementation
- **`example-usage.ts`** - Example demonstrating how other cells can use ContentManagerCell
- **`tests/ContentManagerCell.test.ts`** - Unit tests for BaseCell implementation
- **`View.vue`** - UI component for interactive usage (optional)
- **`composables.ts`** - Vue composables for UI integration
- **`types.ts`** - TypeScript type definitions

## Quick Start

### Import and Use in Another Cell

```typescript
import { ContentManagerCell } from '@/cells/content-manager-cell/frontend/ContentManagerCell'

// In your cell's execute method:
const contentManager = new ContentManagerCell()

// Persist content
const result = await contentManager.execute({
  action: 'persist',
  content_type_id: 'image-png',
  filename: 'my-image.png',
  binary: base64Data,
  tags: ['generated'],
  origin_cell_id: this.cell_instance?.id
})

if (result.success) {
  console.log('Content persisted:', result.output.id)
}
```

### Available Actions

#### 1. List Contents

```typescript
const result = await contentManager.execute({
  action: 'list',
  filters: {
    content_type_id: 'image-png',
    is_latest: true
  },
  limit: 20,
  offset: 0
})
```

#### 2. Load Content

```typescript
const result = await contentManager.execute({
  action: 'load',
  content_id: 'content-uuid',
  direct_download: false  // Use presigned URL
})
```

#### 3. Persist Content

```typescript
const result = await contentManager.execute({
  action: 'persist',
  content_type_id: 'image-png',
  filename: 'image.png',
  binary: base64Data,
  fragments: { /* metadata */ },
  tags: ['tag1', 'tag2']
})
```

## BaseCell Interface

ContentManagerCell implements all required BaseCell methods:

- **`execute(input)`** - Execute content management actions
- **`describe()`** - Get cell metadata and capabilities
- **`validate(input)`** - Validate input before execution
- **`setup(config)`** - Initialize (optional)
- **`teardown()`** - Cleanup (optional)
- **`health_check()`** - Check backend connectivity (optional)

## Testing

Run tests with:

```bash
cd cockpit-vue
npm test -- artifacts/canonical/cell_types/content-manager-cell/frontend/tests/ContentManagerCell.test.ts
```

## Example: Complete Cell Integration

See `example-usage.ts` for a complete example of a PNG generator cell that uses ContentManagerCell to persist its output.

## Type Safety

All inputs and outputs are fully typed. Import types as needed:

```typescript
import type { 
  ContentManagerInput,
  ListContentInput,
  LoadContentInput,
  PersistContentInput,
  ContentItem
} from './ContentManagerCell'
```

## Ephemeral Execution

ContentManagerCell is marked as ephemeral in its type definition, meaning:

- No persistent cell instance is created when used programmatically
- Designed for utility usage by other cells
- Executes via `/api/cells/execute-ephemeral` endpoint
- No database persistence of the cell itself (only the content it manages)

## Best Practices

1. **Reuse instances** - Create one ContentManagerCell instance per parent cell
2. **Handle errors** - Always check `result.success` before using output
3. **Set auth token** - Call `setAuthToken()` if authentication is required
4. **Pass cell_instance** - Include `origin_cell_id` when persisting to track provenance
5. **Use presigned URLs** - Set `direct_download: false` for better performance

## References

- [BaseCell Interface](../../../../cockpit-vue/src/types/BaseCell.ts)
- [ADDING_NEW_CELL_TYPE.md](../../../../docs/official/ADDING_NEW_CELL_TYPE.md)
- [Content Manager Documentation](../docs/README.md)
