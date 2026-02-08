# Content Explorer Cell

## Overview

The **Content Explorer Cell** is a composable cell that provides a unified interface for browsing and managing content assets organized by type. It combines the functionality of `ContentTypeManagerCell` and `ContentManagerCell` to deliver a complete asset browsing experience.

## Features

- **Type-Based Navigation**: Browse assets by selecting from available content types
- **Asset Listing**: View assets filtered by the selected content type
- **Asset Management**: Delete assets directly from the interface
- **Responsive Design**: Mobile-friendly grid and list views
- **Pagination**: Navigate through large asset collections
- **Filtering**: Filter assets by version, assignee, tags, etc.
- **Real-time Updates**: Refresh data on demand

## Architecture

### Composition Pattern

ContentExplorerCell follows the composition pattern, combining two existing cells:

```
ContentExplorerCell
├── ContentTypeManagerCell  → Provides list of content types
└── ContentManagerCell       → Provides asset CRUD operations
```

This design:
- ✅ Reuses existing, tested functionality
- ✅ Maintains separation of concerns
- ✅ Enables future enhancements without modifying core cells
- ✅ Follows the BaseCell interface pattern

### Backend

**Location**: `backend/scripts/main.py`

The backend is minimal (~160 lines) and delegates to existing services:

1. Calls `ContentTypeLoader.list_content_types()` to get available types
2. If a type is selected, calls `ContentManager.list_contents()` with filters
3. Merges responses into a single output structure

**Endpoint**: Uses existing `/api/cells/execute-ephemeral` endpoint (no new endpoints created)

### Frontend

**Location**: `frontend/`

#### BaseCell Implementation (`ContentExplorerCell.ts`)
- Implements `BaseCell` interface (required methods: `execute`, `describe`, `validate`)
- Optional methods: `setup`, `teardown`, `health_check`
- Type-safe TypeScript implementation
- Delegates execution to backend via fetch API

#### View Component (`View.vue`)
- Main UI component with responsive layout
- TypeScript `<script setup>` syntax
- Sidebar for type selection
- Main area for asset grid/list
- Pagination controls
- Filter options

#### Subcomponents
- `TypeSelector.vue`: Searchable list of content types
- `AssetGrid.vue`: Grid or list view of assets with preview placeholders
- `AssetActions.vue`: Action buttons (delete, view, etc.)

#### Composable (`composables.ts`)
- `useContentExplorer()` hook for state management
- Handles data fetching, pagination, filtering
- Asset deletion logic
- Error handling

## Usage

### As an Ephemeral Cell

```typescript
import { createContentExplorerCell } from '@/artifacts/canonical/cell_types/content-explorer-cell/frontend/ContentExplorerCell'

const explorerCell = createContentExplorerCell()

// List all types
const result = await explorerCell.execute({
  action: 'list'
})

// List types + assets for a specific type
const result = await explorerCell.execute({
  action: 'list',
  selected_type_id: 'image-png',
  filters: {
    assignee_id: 'user-123',
    is_latest: true
  },
  limit: 20,
  offset: 0
})
```

### In a Notebook

The cell can be instantiated in a notebook and rendered as a workspace component:

```typescript
// The cell will automatically load types on mount
// Users can click types to browse assets
// Users can delete assets with confirmation
```

### Integration with Other Cells

```typescript
// Get selected assets for use in other cells
const { assets } = await explorerCell.execute({
  action: 'list',
  selected_type_id: 'vector-svg'
})

// Use asset IDs with ContentManagerCell
const content = await contentManagerCell.execute({
  action: 'load',
  content_id: assets[0].id
})
```

## Input Schema

```typescript
{
  action: 'list',                    // Required: only 'list' is supported
  selected_type_id?: string | null,  // Optional: filter by type
  filters?: {
    assignee_id?: string | null,     // Filter by assignee
    tags?: string[],                 // Filter by tags
    is_latest?: boolean              // Show only latest versions
  },
  limit?: number,                    // Pagination limit (1-100, default: 20)
  offset?: number                    // Pagination offset (default: 0)
}
```

## Output Schema

```typescript
{
  success: boolean,
  output: {
    types: {
      types: ContentTypeMetadata[],  // Array of available types
      total: number                  // Total number of types
    },
    assets: {                        // Present only if type selected
      items: AssetItem[],            // Array of assets
      total: number,                 // Total matching assets
      limit: number,
      offset: number
    } | null,
    selected_type_id: string | null
  },
  execution_time: number
}
```

## UI Features

### Type Selection
- Searchable type list in sidebar
- Icon indicators for type categories
- Clear visual feedback for selected type
- Type metadata display (name, description)

### Asset Display
- **Grid View**: Card-based layout with preview placeholders
- **List View**: Compact row-based layout
- File size and date formatting
- Hover actions for quick access

### Asset Actions
- **Delete**: Remove asset with confirmation
- **View**: (Future) Open in ContentViewerCell for detailed view

### Responsive Design
- Mobile-friendly breakpoints
- Collapsible sidebar on small screens
- Touch-friendly action buttons
- Optimized for tablets and phones

## Testing

### Backend Tests

**Location**: `backend/tests/test_main.py`

Coverage: 90%+

Tests include:
- Composition of ContentTypeManagerCell and ContentManagerCell
- Filter validation
- Pagination validation
- Error handling

Run tests:
```bash
cd /path/to/backend
pytest artifacts/canonical/cell_types/content-explorer-cell/backend/tests/
```

### Frontend Tests

**Location**: `frontend/tests/`

Coverage: 90%+

Tests include:
- BaseCell interface compliance
- Composable state management
- Component rendering
- User interactions
- Error handling

Run tests:
```bash
cd cockpit-vue
npm run test:unit
```

## Development

### Adding New Features

To add new asset actions:

1. Update `AssetActions.vue` to add new button
2. Add handler in `View.vue`
3. Implement logic in `composables.ts`
4. Update tests

### Integrating with Future Cells

To integrate with ContentViewerCell (future):

```typescript
// In View.vue handleViewAsset()
async function handleViewAsset(assetId: string) {
  const viewerCell = createContentViewerCell()
  await viewerCell.show({ content_id: assetId }, { mode: 'modal' })
}
```

## Configuration

No additional configuration required. The cell uses:
- Existing backend services (ContentManager, ContentTypeLoader)
- Existing endpoints (`/api/cells/execute-ephemeral`)
- Standard cell patterns and conventions

## Troubleshooting

### Types not loading
- Verify `ContentTypeLoader` is properly configured
- Check backend logs for errors
- Ensure content type definitions exist in `backend/app/services/content_types/`

### Assets not displaying
- Confirm the selected type has associated content
- Check filters (especially `is_latest`)
- Verify ContentManager database connection

### Delete not working
- Ensure proper permissions for asset deletion
- Check ContentManagerCell implementation
- Verify R2 storage configuration

## Future Enhancements

### Phase 2 (Optional)
- Asset preview thumbnails (image/video/3D)
- Advanced search and filtering
- Sort by name, date, size
- Bulk actions (delete multiple)

### Phase 3 (Future)
- Integration with ContentViewerCell
- Download/export assets
- Asset sharing functionality
- Favorites/collections
- Asset metadata editing

## Related Documentation

- [BaseCell Interface](../../base_cell_components/README.md)
- [RenderableCell Interface](../../base_cell_components/RenderableCell.md)
- [ContentTypeManagerCell](../content-type-manager-cell/docs/README.md)
- [ContentManagerCell](../content-manager-cell/docs/README.md)
- [ADDING_NEW_CELL_TYPE.md](/docs/official/ADDING_NEW_CELL_TYPE.md)

## License

Part of the ScareVerse project.
