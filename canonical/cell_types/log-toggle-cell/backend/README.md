# Log Toggle Cell — Backend

Python backend for the Log Toggle Cell, enabling runtime control of log namespaces for debugging sessions.

## Purpose

This package provides the execution logic for temporarily enabling or disabling log namespaces within a ScareVerse session. Changes are applied at runtime and do not persist beyond the current session — this makes the cell useful for debugging without requiring a service restart.

## Index

### Files

| File | Description |
|------|-------------|
| `__init__.py` | Python package marker |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| `scripts/` | `main.py` — `execute_cell()` function that processes namespace enable/disable requests |
| `tests/` | `test_main.py` — unit tests for `execute_cell()` |

## Key Function

### `execute_cell(cell_data)` in `scripts/main.py`

Accepts a `cell_data` payload specifying which log namespaces to enable or disable:

```python
cell_data = {
    "enable": ["cockpit.auth", "cockpit.cells"],
    "disable": ["cockpit.render"],
}
result = execute_cell(cell_data)
# → { "status": "ok", "applied": { "enabled": [...], "disabled": [...] } }
```

The function:
1. Validates the namespace lists
2. Applies enable/disable flags to the runtime logging registry
3. Returns a summary of applied changes

## Usage

Invoked automatically by the platform `execute-ephemeral` endpoint when the Log Toggle Cell is executed. To run tests:

```bash
pytest artifacts/canonical/cell_types/log-toggle-cell/backend/tests/ -v
```

## Related Documentation

- [Log Toggle Cell Root](../) - Full cell overview
- [Log Toggle Frontend](../frontend/) - Vue frontend for this cell
- [Shared Utils / Logger](../../../../shared/utils/) - The logging system controlled by this cell
