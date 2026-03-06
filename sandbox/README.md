---
processed: true
processed_date: 2026-03-06
generated_docs:
  - docs/official/frontend/architecture/dynamic-cell-loading-vite.md
themes:
  - cells
  - frontend
  - artifacts
modules:
  - frontend
code_verified: true
dead_docs_found: false
---
# Sandbox Artifacts - User Private Workspace

## Purpose

This directory contains **user-private draft artifacts** that are:
- ✅ Stored locally on ScareRunner
- ✅ Isolated per user (`sandbox/{user_id}/`)
- ✅ Never published to MongoDB or R2
- ✅ Never committed to Git (see `.gitignore`)
- ✅ Served only via local Vite server

## Structure

```
sandbox/
├── user-{id}/               # Per-user isolation
│   ├── artifact-{id}/
│   │   ├── metadata.json    # Artifact definition
│   │   ├── data.bin         # Binary data (if applicable)
│   │   └── ...
│   └── ...
└── ...
```

## Privacy Guarantees

**Sandbox artifacts are NEVER**:
- Published to MongoDB (CentralHub)
- Archived to R2 (cloud storage)
- Shared with other users
- Committed to Git repository

**Sandbox artifacts are ONLY**:
- Stored on local ScareRunner disk
- Accessible to the owning user
- Served via Vite dev server (local)
- Used for draft/experimentation

## Publishing Workflow

To share an artifact, users must **explicitly publish** it:

1. **Draft Phase** (sandbox):
   ```javascript
   POST /api/artifacts
   { scope: "sandbox", ...data }
   // Artifact stored in artifacts/sandbox/{user_id}/
   ```

2. **Publish Phase** (MongoDB):
   ```javascript
   POST /api/artifacts/{id}/publish
   // Artifact moved to MongoDB via CentralHub
   // Sandbox copy can be kept or deleted
   ```

## Lifecycle

- **Created**: On first insert with `scope="sandbox"`
- **Modified**: Updates remain in sandbox until published
- **Published**: Explicit action moves to MongoDB
- **Deleted**: Removed from local disk only

## Implementation

See `backend/app/database/hybrid/router.py` for implementation details.
- `HybridDatabase._find_in_sandbox()` - Read from sandbox
- `HybridDatabase._insert_to_sandbox()` - Write to sandbox
- `HybridDatabase._update_in_sandbox()` - Update in sandbox

## Configuration

Environment variables:
- `ARTIFACTS_SANDBOX_DIR` - Sandbox root directory (default: `artifacts/sandbox/`)
- `ARTIFACTS_CANONICAL_DIR` - Canonical types directory (default: `artifacts/canonical/`)

## Security

- User isolation enforced via `user_id` in path
- No cross-user access (enforced at HybridDatabase level)
- Cache keys include `user_id` to prevent leakage
- Sandbox data excluded from backups (local-only)

---

**Last Updated**: 2026-02-20
**Related**: Phase 1B - HybridDatabase Refactor
**Privacy Level**: User-Private (Never Published)
