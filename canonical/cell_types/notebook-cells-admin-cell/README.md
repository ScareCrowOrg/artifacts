---
processed: true
processed_date: 2026-03-06
generated_docs:
  - docs/official/backend/security/cell-types-security.md
themes:
  - cells
  - frontend
  - rbac
  - notebook
modules:
  - frontend
code_verified: true
dead_docs_found: false
---
# Notebook Cells Admin Cell

## Overview

The `notebook-cells-admin-cell` is an RBAC-protected administrative cell that provides complete CRUD operations for managing notebook cells within the ScareVerse Dynamic Workspace.

**Key Features:**
- ✅ RBAC protection with `notebook:admin` permission
- ✅ List cells with filtering (by assignee, cell type)
- ✅ View cell details
- ✅ Create new cells
- ✅ Update existing cells
- ✅ Delete cells
- ✅ List available cell types
- ✅ Replaces legacy NotebookCellsAdmin overlay

## Architecture

### Cell Structure

```
notebook-cells-admin-cell/
├── type.json                          # Cell metadata with RBAC config
├── frontend/
│   ├── NotebookCellsAdminCell.ts     # BaseCell implementation
│   ├── View.vue                       # Main Vue component
│   ├── components/                    # Child components
│   │   ├── NotebookCellList.vue
│   │   ├── NotebookCellDetails.vue
│   │   ├── NotebookCellFilters.vue
│   │   ├── JsonEditor.vue
│   │   └── JsonViewer.vue
│   └── tests/                         # Test files
├── backend/                           # Backend scripts (if needed)
├── docs/                              # Documentation
└── README.md                          # This file
```

### BaseCell Implementation

The `NotebookCellsAdminCell` extends `BaseCell` and implements all required methods:

- **execute()**: Performs CRUD operations with RBAC check
- **describe()**: Returns cell metadata
- **validate()**: Validates input before execution
- **setup()**: Optional setup (no-op for this cell)
- **teardown()**: Optional cleanup (no-op for this cell)
- **health_check()**: Verifies backend connectivity and permissions

### RBAC Protection

**Permission Required:** `notebook:admin`

The cell enforces RBAC at two levels:

1. **Execute Level**: The `execute()` method checks `notebook:admin` permission before any operation
2. **UI Level**: The View.vue wraps content in `PermissionGuard` component to show access denied UI

## Usage

### Programmatic Usage

```typescript
import { NotebookCellsAdminCell } from './NotebookCellsAdminCell'

const adminCell = new NotebookCellsAdminCell()

// List all cells
const listResult = await adminCell.execute({
  action: 'list',
  filters: { assignee: 'user123' }
})

// Get cell details
const getResult = await adminCell.execute({
  action: 'get',
  cellId: 'cell-uuid'
})

// Create new cell
const createResult = await adminCell.execute({
  action: 'create',
  data: { type: 'png-generator', assignee_id: 'user123' }
})

// Update cell
const updateResult = await adminCell.execute({
  action: 'update',
  cellId: 'cell-uuid',
  data: { status: 'archived' }
})

// Delete cell
const deleteResult = await adminCell.execute({
  action: 'delete',
  cellId: 'cell-uuid'
})

// List cell types
const typesResult = await adminCell.execute({
  action: 'list-types'
})
```

### UI Usage

The cell is automatically discovered and can be launched from the Dynamic Workspace. Users with `notebook:admin` permission can:

1. Open from AppHeader admin menu
2. Browse and filter cells
3. View cell details
4. Perform CRUD operations
5. Manage cell types

Users without `notebook:admin` permission will see an access denied screen.

## Actions

### list

List cells with optional filters.

**Input:**
```typescript
{
  action: 'list',
  filters?: {
    assignee?: string,
    cellType?: string
  }
}
```

**Output:**
```typescript
{
  success: true,
  output: {
    action: 'list',
    data: Cell[]
  }
}
```

### get

Get details of a specific cell.

**Input:**
```typescript
{
  action: 'get',
  cellId: string
}
```

**Output:**
```typescript
{
  success: true,
  output: {
    action: 'get',
    data: Cell
  }
}
```

### create

Create a new cell.

**Input:**
```typescript
{
  action: 'create',
  data: {
    type: string,
    assignee_id: string,
    // ... other cell properties
  }
}
```

**Output:**
```typescript
{
  success: true,
  output: {
    action: 'create',
    data: Cell
  }
}
```

### update

Update an existing cell.

**Input:**
```typescript
{
  action: 'update',
  cellId: string,
  data: {
    // properties to update
  }
}
```

**Output:**
```typescript
{
  success: true,
  output: {
    action: 'update',
    data: Cell
  }
}
```

### delete

Delete a cell.

**Input:**
```typescript
{
  action: 'delete',
  cellId: string
}
```

**Output:**
```typescript
{
  success: true,
  output: {
    action: 'delete',
    data: { cellId: string }
  }
}
```

### list-types

List available cell types.

**Input:**
```typescript
{
  action: 'list-types'
}
```

**Output:**
```typescript
{
  success: true,
  output: {
    action: 'list-types',
    data: CellType[]
  }
}
```

## Components

### View.vue

Main component that orchestrates the admin interface. Features:
- PermissionGuard wrapper for RBAC
- Two-column layout (list + details)
- Filtering and pagination
- Error handling
- Responsive design

### NotebookCellList.vue

Displays the list of cells with:
- Cell metadata (ID, type, assignee)
- Selection state
- Pagination controls
- Empty state handling

### NotebookCellDetails.vue

Shows detailed cell information:
- Full cell metadata
- JSON viewer/editor
- Update functionality
- Close button

### NotebookCellFilters.vue

Provides filtering controls:
- Assignee filter
- Cell type filter
- Reset button

### JsonEditor.vue

Shared JSON editor component with syntax highlighting.

### JsonViewer.vue

Shared JSON viewer component for read-only display.

## Testing

### Unit Tests

Located in `frontend/tests/`:

- `NotebookCellsAdminCell.spec.ts`: Cell implementation tests
- `View.spec.ts`: Component tests

**Coverage Target:** 90%+

### RBAC Tests

Critical tests for permission enforcement:

```typescript
describe('RBAC Protection', () => {
  it('should deny execution without notebook:admin permission', async () => {
    // Test unauthorized access
  })

  it('should allow execution with notebook:admin permission', async () => {
    // Test authorized access
  })

  it('should show access denied UI without permission', async () => {
    // Test UI guard
  })
})
```

## Migration from NotebookCellsAdmin Overlay

This cell replaces the hardcoded `NotebookCellsAdmin.vue` overlay component:

**Before:**
- Hardcoded in App.vue
- Triggered by `uiStore.showNotebookCellsAdmin`
- No RBAC protection
- Not customizable per runner

**After:**
- Proper BaseCell implementation
- Auto-discovered cell type
- RBAC protected (`notebook:admin`)
- Customizable and composable
- Headless execution support

## Security

### Permission Requirements

- **Required:** `notebook:admin`
- **Enforced at:** Execute level + UI level
- **Failure mode:** Access denied with clear error message

### Best Practices

1. Always check permissions before API calls
2. Show access denied UI for unauthorized users
3. Log permission checks for audit trail
4. Never bypass RBAC checks

## Technical Debt Resolved

- ✅ Removes overlay from App.vue
- ✅ Adds RBAC protection
- ✅ Enables runner customization
- ✅ Follows BaseCell pattern
- ✅ Supports headless execution

## Version History

- **1.0.0** (2026-02-23): Initial implementation
  - BaseCell implementation with RBAC
  - Complete CRUD operations
  - Migrated from NotebookCellsAdmin overlay

## See Also

- [ADDING_NEW_CELL_TYPE.md](../../../docs/official/ADDING_NEW_CELL_TYPE.md)
- [BaseCell Interface](../../../cockpit-vue/src/types/BaseCell.ts)
- [RBAC Documentation](../../../docs/official/rbac/)
