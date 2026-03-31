# Canonical Permissions

Canonical RBAC permission definitions for the ScareVerseLab platform.
Each JSON file is named after its UUID and describes a single granular permission
that can be assigned to roles.

## Purpose

Provides an auditable, version-controlled set of permission records that are
seeded into the backend on first run and referenced by roles to enforce
access control across all platform services.

## Content Index

The directory contains **22 JSON files**, each named by UUID (e.g.
`a1b2c3d4-…​.json`).  Each file follows the canonical permission schema:

```json
{
  "id": "<uuid>",
  "name": "<permission_name>",
  "description": "<human-readable description>",
  "resource": "<api_resource>",
  "action": "<crud_action>"
}
```

All 22 files are loaded automatically by the seeding scripts; individual file
names correspond to the `id` field inside each document.

## Related Documentation

- [Canonical Roles](../roles/) — roles that bundle these permissions
- [Canonical Artifacts](../README.md) — parent canonical directory
- [Backend RBAC](../../../../backend/docs/) — backend RBAC implementation details
