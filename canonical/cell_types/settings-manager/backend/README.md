# Settings Manager Cell – Backend

Python backend for the Settings Manager Cell. Implements all CRUD operations on the launcher `settings.json` file with type validation, modification history, rollback, and Redis L1 push.

## Purpose

This backend handles all cell actions dispatched by the runner. It reads and writes settings from `~/.scareverse/{tenant}/settings/settings.json` and maintains a parallel `settings_history.json` for change tracking.

## Structure

```
backend/
├── scripts/
│   ├── __init__.py        # Package marker
│   └── main.py            # Entry point: execute_cell() dispatcher
└── tests/
    └── test_main.py       # Unit tests for all CRUD actions
```

## Entry Point

```python
from backend.scripts.main import execute_cell

response_body, http_status = execute_cell(
    action="list",
    payload={},
    service="launcher"
)
```

## Actions

| Action | Payload Fields | Returns |
|--------|---------------|---------|
| `list` | _(none)_ | All settings grouped by category |
| `create` | `setting_key`, `value`, `type`, `category` | Created setting |
| `update` | `setting_key`, `value` | Updated setting |
| `delete` | `setting_key` | Confirmation |
| `history` | `setting_key` (optional) | Modification history entries |
| `rollback` | `setting_key`, `value` | Restored setting |
| `push_redis` | _(none)_ | Push confirmation (ready for Phase 1B wiring) |

## Valid Types

Settings values must use one of these types: `string`, `number`, `boolean`, `json`

## File Paths

The `service` parameter controls which tenant's settings are targeted:

```
~/.scareverse/{service}/settings/settings.json
~/.scareverse/{service}/settings/settings_history.json
```

## Running Tests

```bash
cd artifacts/canonical/cell_types/settings-manager
pytest backend/tests/test_main.py -v
```

## Related Documentation

- [Cell README](../README.md) — Cell overview and usage
- [Cell Docs](../docs/README.md) — Full API reference
- [Frontend](../frontend/) — Vue 3 UI component
