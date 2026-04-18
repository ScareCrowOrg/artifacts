# Roles Management Cell – Frontend

## Purpose

Vue 3 frontend for the **Roles Management Cell** — admin interface for managing RBAC roles, permissions, and role assignments.

## Content Index

| File | Description |
|------|-------------|
| [`RolesManagementCell.ts`](./RolesManagementCell.ts) | BaseCell implementation — `list-roles`, `create-role`, `update-role`, `delete-role`, `assign-role`, `list-permissions` actions |
| [`View.vue`](./View.vue) | Main component — roles list, editor panel, permissions matrix, role assignment UI |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`components/`](./components/) | `AssignRoleModal`, `PermissionsPanel`, `RoleCard`, `RoleEditor`, `RolesList` |
| [`composables/`](./composables/) | `useRolesManagement.ts`, `usePermissionsData.ts` — role/permission state management |
| [`tests/`](./tests/) | `RolesManagementCell.test.ts` — unit tests |

## Related

- [`../`](../) — Roles Management Cell root
