# Roles Management Cell – Frontend Components

## Purpose

Vue 3 components for the **Roles Management Cell** RBAC admin UI.

## Content Index

| File | Description |
|------|-------------|
| [`AssignRoleModal.vue`](./AssignRoleModal.vue) | Modal to assign a role to a user — user search, role selector, confirmation |
| [`PermissionsPanel.vue`](./PermissionsPanel.vue) | Permissions matrix panel — shows all permissions with checkbox toggles per role |
| [`RoleCard.vue`](./RoleCard.vue) | Compact card for a single role — shows name, description, permission count, quick actions |
| [`RoleEditor.vue`](./RoleEditor.vue) | Full role editor form — name, description, permissions multi-select, save/cancel |
| [`RolesList.vue`](./RolesList.vue) | Paginated/filterable list of all roles with create and delete actions |

## Related

- [`../`](../) — Roles Management Cell frontend root
- [`../composables/useRolesManagement.ts`](../composables/useRolesManagement.ts) — Data composable consumed by these components
