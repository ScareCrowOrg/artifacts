---
processed: true
processed_date: 2026-03-06
generated_docs:
  - docs/official/backend/security/cell-types-security.md
themes:
  - cells
  - frontend
  - rbac
  - issues
modules:
  - frontend
code_verified: true
dead_docs_found: false
---
# Issues Dashboard Cell

**Type**: Admin Cell  
**Version**: 1.0.0  
**Category**: admin  
**RBAC Protected**: ✅ Yes  
**Required Permissions**: `issues:read`  
**Optional Permissions**: `issues:write`

## Overview

The Issues Dashboard Cell provides comprehensive issue management capabilities within the ScareVerse Dynamic Workspace. It enables users to view, filter, and manage GitHub issues and project tasks with RBAC-based access control.

## Features

- **View Issues**: Browse and filter issues by status (pending, running, completed, error)
- **Issue Details**: View detailed information about individual issues including pipeline history
- **Real-time Updates**: SSE-based live updates for issue status changes
- **Pipeline Monitoring**: Monitor processing queue and pipeline activity
- **RBAC Protection**: Read-only mode for users without write permission

### Write-Permission Features

Users with `issues:write` permission can access additional features:
- Create new issues
- Update existing issues
- Delete issues
- Start/stop monitoring
- Pause/resume processing queue
- Trigger manual processing
- Ingest documentation

## Architecture

```
issues-dashboard-cell/
├── type.json                    # Cell metadata with RBAC configuration
├── frontend/
│   ├── IssuesDashboardCell.ts   # BaseCell implementation
│   ├── View.vue                 # Main Vue component
│   ├── components/              # Child components
│   │   ├── IssueStats.vue       # Statistics display
│   │   ├── IssueFilters.vue     # Filter and action controls
│   │   ├── IssueList.vue        # Issue list container
│   │   ├── IssueCard.vue        # Individual issue card
│   │   ├── IssueDetails.vue     # Detailed issue view
│   │   ├── Pagination.vue       # Pagination controls
│   │   ├── IngestForm.vue       # Document ingestion form
│   │   ├── CreateCellForm.vue   # Cell creation form
│   │   └── PipelineActivityFeed.vue  # Pipeline activity display
│   ├── stores/
│   │   └── issuesStore.ts       # Local Pinia store
│   └── tests/
│       ├── IssuesDashboardCell.spec.ts
│       ├── View.spec.ts
│       └── components/
└── README.md                    # This file
```

## BaseCell Interface

The cell implements the required BaseCell interface methods:

### `execute(input)`

Executes issue operations with RBAC checks:

**Actions**:
- `list`: List issues with optional filters
- `get`: Get detailed issue information
- `create`: Create new issue (requires `issues:write`)
- `update`: Update existing issue (requires `issues:write`)
- `delete`: Delete issue (requires `issues:write`)

**Input Schema**:
```typescript
{
  action: 'list' | 'get' | 'create' | 'update' | 'delete',
  issueId?: string,        // Required for get, update, delete
  filters?: {              // Optional for list
    status?: string,
    assignee?: string,
    labels?: string[]
  },
  data?: {                 // Required for create, optional for update
    title?: string,
    description?: string,
    assignee?: string,
    labels?: string[]
  }
}
```

**Output**:
```typescript
{
  success: boolean,
  output: {
    action: string,
    data: any
  },
  execution_time: number,
  error?: string
}
```

### `describe()`

Returns cell metadata including inputs, outputs, and RBAC requirements.

### `validate(input)`

Validates input before execution:
- Ensures action is present and valid
- Checks required fields for each action type
- Returns array of validation errors (empty if valid)

### `health_check()`

Checks if the cell can execute:
- Verifies user has `issues:read` permission
- Pings the issues API for availability
- Returns health status

## RBAC Implementation

The cell enforces permissions at multiple levels:

1. **Cell Level** (`IssuesDashboardCell.ts`):
   - `execute()` method checks `issues:read` for all operations
   - Write operations additionally check `issues:write`
   - Returns permission errors if unauthorized

2. **View Level** (`View.vue`):
   - Displays read-only warning banner if no write permission
   - Hides create/edit forms without write permission
   - Passes permission status to child components

3. **Component Level**:
   - `IssueFilters.vue`: Hides action buttons without write permission
   - `IssueDetails.vue`: Disables edit/delete buttons without write permission
   - All forms check permission before submission

## Usage

### As a Cell Instance

Users with `issues:read` permission can launch the Issues Dashboard from the admin menu in the Dynamic Workspace. The cell will automatically enforce RBAC based on the user's permissions.

### Programmatic Usage

```typescript
import { IssuesDashboardCell } from './IssuesDashboardCell'

const cell = new IssuesDashboardCell()

// List issues
const result = await cell.execute({
  action: 'list',
  filters: { status: 'pending' }
})

// Create issue (requires issues:write)
const result = await cell.execute({
  action: 'create',
  data: {
    title: 'New Issue',
    description: 'Description',
    labels: ['bug']
  }
})
```

## Dependencies

- **Stores**: `@/stores/permissions` - RBAC permission checking
- **Services**: `@/services/issuesService` - Issue API operations
- **Utils**: `@/utils/logger` - Structured logging
- **Services**: `@/services/apiService` - HTTP client with auth

## Testing

Run tests with:
```bash
npm test -- IssuesDashboardCell.spec.ts
```

Target coverage: 90%

## Migration Notes

This cell was migrated from the legacy `cockpit-vue/src/components/IssuesDashboard.vue` overlay component. Key changes:

1. **RBAC Protection**: Added permission checks at all levels
2. **BaseCell Interface**: Implemented required methods for headless execution
3. **TypeScript**: Converted all components to TypeScript
4. **Local Store**: Migrated store to cell-local directory
5. **Component Structure**: Organized components in cell structure

The original overlay integration in `App.vue` will be removed as part of the migration cleanup phase.

## Future Improvements

1. **Modularization**: Split large store file (899 lines) into smaller modules
2. **Composables**: Extract reusable logic into focused composables
3. **Backend Integration**: Implement backend handler for enhanced security
4. **Advanced Filters**: Add more filtering and search capabilities
5. **Export/Import**: Add issue export and bulk import features
