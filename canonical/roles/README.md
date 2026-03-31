# Canonical Roles

Canonical RBAC role definitions for the ScareVerseLab platform.
Each JSON file is named after its UUID and declares a role together with the
set of permissions it grants.

## Purpose

Provides the authoritative role definitions seeded into the backend on
first-run.  Roles compose permissions from `../permissions/` and are assigned
to users to control access across notebooks, cells, and workers.

## Content Index

The directory contains **7 JSON files**, each named by UUID.
Each file follows the canonical role schema:

```json
{
  "id": "<uuid>",
  "name": "<role_name>",
  "description": "<human-readable description>",
  "permissions": ["<permission_uuid>", "…"]
}
```

Current roles cover the standard access tiers: viewer, contributor, editor,
reviewer, admin, service-account, and super-admin.

## Related Documentation

- [Canonical Permissions](../permissions/) — individual permissions bundled into these roles
- [Canonical Artifacts](../README.md) — parent canonical directory
- [Backend RBAC](../../../../backend/docs/) — runtime RBAC enforcement
