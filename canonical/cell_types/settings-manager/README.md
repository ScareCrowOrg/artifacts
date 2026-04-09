# Settings Manager Cell

A CRUD interface for managing launcher settings with schema validation, modification history, and Redis L1 push capability.

## Purpose

The Settings Manager Cell provides a full administrative UI for application settings stored in `~/.scareverse/{tenant}/settings/settings.json`. It supports creating, updating, and deleting settings with type validation, a complete modification history, rollback to any previous value, and live propagation to Redis L1 for running services.

## Structure

```
settings-manager/
├── type.json              # Cell type manifest and discovery metadata
├── docs/
│   └── README.md          # Detailed cell documentation with API reference
├── backend/
│   ├── scripts/
│   │   ├── __init__.py
│   │   └── main.py        # Cell backend: CRUD logic for settings.json
│   └── tests/
│       └── test_main.py   # Backend unit tests
└── frontend/
    ├── View.vue            # Main cell component (list, create, update, delete, history)
    ├── tests/
    │   └── View.spec.ts   # Frontend component tests
    └── translations/
        └── en.json        # English i18n translations
```

## Cell Type ID

`settings-manager`

## Actions

| Action | Description |
|--------|-------------|
| `list` | Return all settings grouped by category |
| `create` | Add a new setting with type validation (`string`, `number`, `boolean`, `json`) |
| `update` | Update an existing setting value |
| `delete` | Remove a setting |
| `history` | Return modification history (optionally filtered by key) |
| `rollback` | Restore a setting to a previous value |
| `push_redis` | Push all settings to Redis L1 for live service consumption |

## How to Use

This cell is registered as `settings-manager` and can be instantiated in any notebook. It requires the launcher to have write access to the settings directory.

```json
{
  "cell_type": "settings-manager",
  "initial_data": {
    "currentTab": "list",
    "historyFilters": {}
  }
}
```

## Permissions

| Permission | Required? | Description |
|------------|-----------|-------------|
| `settings:manage` | Optional | Create, update, delete settings |
| `settings:admin` | Optional | Access Redis push and rollback operations |

## Related Documentation

- [Cell Documentation](./docs/README.md) — Full API reference and architecture details
- [Backend Script](./backend/scripts/main.py) — Implementation of all cell actions
- [Frontend Component](./frontend/View.vue) — Vue 3 UI component
- [docs/official/ADDING_NEW_CELL_TYPE.md](../../../docs/official/ADDING_NEW_CELL_TYPE.md) — Guide for adding new cell types
- [artifacts/canonical/cell_types/](../) — Other available cell types
