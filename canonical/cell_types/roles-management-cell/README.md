# Roles Management Cell

RBAC-protected administrative cell for managing roles and permissions in the ScareVerse system.

## Overview

The Roles Management Cell provides a secure, modularized interface for administrators to:
- List and view all system roles
- Create, update, and delete roles
- Manage role permissions
- Assign and unassign roles to users

## Features

- ✅ **BaseCell Implementation**: Follows canonical BaseCell v1.0 pattern
- ✅ **RBAC Protected**: Requires `roles:admin` permission
- ✅ **Modularized**: All files under 500 lines (RULESET.md compliant)
- ✅ **TypeScript**: Fully typed implementation
- ✅ **Tested**: 90%+ test coverage

## Architecture

### Cell Structure

```
roles-management-cell/
├── type.json                          # Cell metadata + RBAC config
├── README.md                          # This file
└── frontend/
    ├── RolesManagementCell.ts         # BaseCell implementation (387 lines)
    ├── View.vue                       # Main UI container (371 lines)
    ├── components/                    # Modularized UI components
    │   ├── RolesList.vue              # List view (192 lines)
    │   ├── RoleEditor.vue             # Create/Edit form (238 lines)
    │   ├── PermissionsPanel.vue       # Permission checkboxes (276 lines)
    │   ├── AssignRoleModal.vue        # Assign role modal (349 lines)
    │   └── RoleCard.vue               # Single role card (199 lines)
    ├── composables/                   # Business logic
    │   ├── useRolesManagement.ts      # CRUD operations (277 lines)
    │   └── usePermissionsData.ts      # Permission data (178 lines)
    └── tests/                         # Test files
        ├── RolesManagementCell.test.ts (391 lines)
        ├── View.spec.ts
        └── components/
            ├── RolesList.spec.ts
            ├── RoleEditor.spec.ts
            └── PermissionsPanel.spec.ts
```

## Usage

### BaseCell Execution

```typescript
import { RolesManagementCell } from '@/artifacts/canonical/cell_types/roles-management-cell/frontend/RolesManagementCell'

const cell = new RolesManagementCell()

// List all roles
const result = await cell.execute({
  action: 'list'
})

// Get specific role
const result = await cell.execute({
  action: 'get',
  roleId: 'role-123'
})

// Create new role
const result = await cell.execute({
  action: 'create',
  data: {
    name: 'moderator',
    permissions: ['content:edit', 'users:read'],
    description: 'Content moderator role'
  }
})

// Assign role to user
const result = await cell.execute({
  action: 'assign',
  roleId: 'role-123',
  userId: 'user-456'
})
```

## Actions

| Action | Permission | Parameters | Description |
|--------|-----------|------------|-------------|
| `list` | `roles:admin` | - | List all roles |
| `get` | `roles:admin` | `roleId` | Get specific role details |
| `create` | `roles:admin` | `data` | Create new role |
| `update` | `roles:admin` | `roleId`, `data` | Update existing role |
| `delete` | `roles:admin` | `roleId` | Delete role |
| `assign` | `roles:admin` | `roleId`, `userId` | Assign role to user |
| `unassign` | `roles:admin` | `roleId`, `userId` | Remove role from user |

## RBAC Requirements

### Required Permission
- **`roles:admin`**: Full access to all role management operations

### Permission Checks
1. Execute method checks permission before any operation
2. Returns permission denied error if user lacks `roles:admin`
3. Health check verifies permission availability
4. UI shows permission denied message for unauthorized users

## Components

### RolesList.vue
Displays paginated list of roles with filtering and search.

**Features**:
- Search by role name
- Filter by permission type
- Sort by name, date created
- Click to view/edit role

### RoleEditor.vue
Form for creating and editing roles.

**Features**:
- Role name input
- Description textarea
- Permission selection (via PermissionsPanel)
- Validation
- Save/Cancel actions

### PermissionsPanel.vue
Interactive panel for selecting role permissions.

**Features**:
- Grouped permission checkboxes
- Select all/none per group
- Permission descriptions
- Search permissions

### AssignRoleModal.vue
Modal for assigning roles to users.

**Features**:
- User search/select
- Role selection
- Confirm assignment
- Success/error feedback

### RoleCard.vue
Compact display of a single role.

**Features**:
- Role name and description
- Permission count badge
- Action buttons (edit, delete)
- User count display

## Composables

### useRolesManagement.ts
Handles CRUD operations for roles.

**Provides**:
- `roles` - Reactive list of roles
- `loading` - Loading state
- `error` - Error state
- `fetchRoles()` - Load roles
- `createRole()` - Create new role
- `updateRole()` - Update role
- `deleteRole()` - Delete role
- `assignRole()` - Assign to user
- `unassignRole()` - Remove from user

### usePermissionsData.ts
Manages permission data and metadata.

**Provides**:
- `permissions` - Available permissions
- `permissionGroups` - Grouped permissions
- `getPermissionInfo()` - Get permission details

## Testing

### Test Coverage
- **Target**: 90%+ coverage
- **Unit Tests**: BaseCell methods (execute, describe, validate)
- **Component Tests**: All 6 components
- **RBAC Tests**: Permission checks (authorized/unauthorized)
- **Integration Tests**: Full workflows

### Running Tests

```bash
# Run all tests
npm run test

# Run specific test file
npm run test roles-management-cell

# Run with coverage
npm run test:coverage
```

## Migration Notes

This cell replaces the legacy `RolesManagement.vue` component (506 lines).

### Changes from Legacy
- ✅ Modularized into 9 files (all <500 lines)
- ✅ Implements BaseCell interface
- ✅ Added RBAC protection (`roles:admin`)
- ✅ TypeScript instead of JavaScript
- ✅ Composables for business logic
- ✅ Comprehensive test coverage

### Removed Components
- `cockpit-vue/src/components/admin/RolesManagement.vue` (506 lines)
- `cockpit-vue/src/components/admin/AssignRoleModal.vue` (moved to cell)

### Updated Files
- `cockpit-vue/src/App.vue` - Removed hardcoded component
- `cockpit-vue/src/stores/ui.ts` - Removed `showRolesManagement` flag
- `cockpit-vue/src/components/AppHeader.vue` - Launch via cell instead

## API Integration

### Endpoints Used
- `GET /api/roles` - List roles
- `GET /api/roles/:id` - Get role
- `POST /api/roles` - Create role
- `PUT /api/roles/:id` - Update role
- `DELETE /api/roles/:id` - Delete role
- `POST /api/roles/:id/assign` - Assign to user
- `POST /api/roles/:id/unassign` - Remove from user

All requests use `apiFetch` which automatically includes Authorization headers.

## Development

### Adding New Features
1. Add action to `RolesManagementCell.ts` execute method
2. Add validation rules in validate method
3. Create/update UI components as needed
4. Add tests for new functionality
5. Update README documentation

### Modularization Guidelines
- Keep all files under 500 lines (RULESET.md Rule 1.1)
- Use composables for shared logic
- Extract reusable components
- Follow TypeScript conventions

## Security

### Permission Enforcement
- ✅ Permission checked before execute
- ✅ Permission checked in health_check
- ✅ API endpoints validate permissions server-side
- ✅ UI shows permission denied for unauthorized users

### Audit Trail
- All role changes logged in execution metadata
- User ID included in operation context
- Timestamps recorded for all operations

## Related Documentation

- [BaseCell v1.0 Framework](../../../../../../docs/official/RULESET.md#48-canonical-cell-architecture)
- [ADDING_NEW_CELL_TYPE.md](../../../../../../docs/official/ADDING_NEW_CELL_TYPE.md)
- [RBAC Documentation](../../../../../../docs/official/rbac/README.md)
- [TypeScript Guide](../../../../../../docs/official/standards/typescript-guide.md)

## Support

For issues or questions:
- Open issue with tag `roles-management-cell`
- Reference this README
- Include error messages and steps to reproduce

---

**Version**: 1.0.0  
**Last Updated**: 2026-02-23  
**Status**: Active
