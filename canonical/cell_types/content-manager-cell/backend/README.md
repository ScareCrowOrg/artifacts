# Content Manager Cell — Backend

Python backend for the Content Manager Cell, providing content listing, loading, and persistence operations against platform storage.

## Purpose

This package implements the execution logic for the Content Manager Cell's three core operations: listing content with filters, loading content (via presigned URL or direct download), and persisting uploaded content to storage with validation.

## Index

### Files

| File | Description |
|------|-------------|
| `__init__.py` (implied) | Python package marker |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| `scripts/` | Execution scripts: `main.py` (entry point, operation router), `storage.py` (storage backend abstraction), `utils.py` (validation and helper functions) |
| `tests/` | Unit tests for the backend scripts |

## Operations

The backend supports three operations, specified via `cell_data.operation`:

| Operation | Description |
|-----------|-------------|
| `list` | Query and list content items with optional filters (type, tags, date range) |
| `load` | Retrieve content — returns a presigned URL for large files or binary data for small files |
| `persist` | Upload and validate content to the platform storage backend |

## Architecture

```
execute-ephemeral endpoint
         ↓
  execute_cell(cell_data)  ← main.py
         ↓
  Operation routing
  ┌──────┬──────┬─────────┐
  │      │      │         │
 list   load  persist
  │      │      │
  └──────┴──────┴─────────┘
         ↓
  storage.py (S3/R2/local abstraction)
```

## Running Tests

```bash
pytest artifacts/canonical/cell_types/content-manager-cell/backend/tests/ -v
```

## Related Documentation

- [Content Manager Cell Root](../) - Full cell overview
- [Content Manager Frontend](../frontend/) - Vue frontend
- [Shared Services](../../../../shared/services/) - Shared HTTP and API services
