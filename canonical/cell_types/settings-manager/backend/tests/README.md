# Settings Manager Cell – Backend Tests

Unit tests for the Settings Manager Cell Python backend.

## Purpose

Validates all `execute_cell()` actions: `list`, `create`, `update`, `delete`, `history`, `rollback`, and `push_redis`. Tests use temporary directories to avoid touching real settings files.

## Files

| File | Description |
|------|-------------|
| `test_main.py` | Full test suite covering all CRUD actions, type validation, and history tracking |

## Running Tests

```bash
# From the cell root directory
cd artifacts/canonical/cell_types/settings-manager
pytest backend/tests/ -v

# Or from the repository root
pytest artifacts/canonical/cell_types/settings-manager/backend/tests/ -v
```

## Related Documentation

- [Backend README](../README.md) — Backend implementation details
- [Cell README](../../README.md) — Cell overview and actions
