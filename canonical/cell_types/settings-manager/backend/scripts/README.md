# Settings Manager Cell – Backend Scripts

Python entry-point module for the Settings Manager Cell backend.

## Purpose

Contains the `execute_cell()` function that the ScareVerse runner invokes to process all settings management actions. Handles reading/writing `settings.json` and `settings_history.json` for the specified service/tenant.

## Files

| File | Description |
|------|-------------|
| `__init__.py` | Package marker (empty) |
| `main.py` | `execute_cell()` dispatcher: `list`, `create`, `update`, `delete`, `history`, `rollback`, `push_redis` |

## Entry Point

```python
from backend.scripts.main import execute_cell

# Example: list all settings for the launcher service
body, status = execute_cell(action="list", service="launcher")
```

## Related Documentation

- [Backend README](../README.md) — Backend overview and action reference
- [Cell README](../../README.md) — Cell overview and permissions
