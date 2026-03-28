---
processed: true
processed_date: 2026-03-28
themes:
  - cell-types
  - settings
modules:
  - frontend
  - runner
code_verified: true
dead_docs_found: false
---
# Settings Manager Cell

UI for managing launcher settings with type validation, modification history, and Redis L1 push.

## Overview

The **Settings Manager Cell** provides a full CRUD interface for application settings stored in `~/.scareverse/{tenant}/settings/settings.json`.  It is the companion cell to **Vault Manager** in the Phase 3 implementation.

## Features

- **List** all settings grouped by category (with type and current value)
- **Create** new settings with type: `string`, `number`, `boolean`, `json`
- **Update** existing settings (type-coercion validated)
- **Delete** settings (with confirmation dialog)
- **Modification History** – every write is logged to `settings_history.json`
- **Rollback** – restore a setting to any previous value
- **Push to Redis** – publish all settings to Redis L1 for live services

## Cell Type ID

`settings-manager`

## Actions (Backend)

| Action       | Payload Fields                                         | Description                    |
|--------------|--------------------------------------------------------|--------------------------------|
| `list`       | —                                                      | Returns all settings            |
| `create`     | `setting_key`, `value`, `type`, `category`             | Creates a new setting           |
| `update`     | `setting_key`, `value`                                 | Updates a setting value         |
| `delete`     | `setting_key`                                          | Removes a setting               |
| `history`    | `setting_key` (optional filter)                        | Returns modification history    |
| `rollback`   | `setting_key`, `value`                                 | Restores to a previous value    |
| `push_redis` | —                                                      | Pushes all settings to Redis L1 |

## Architecture

```
settings-manager/
├── frontend/
│   ├── View.vue                     # Main UI (TypeScript + Tailwind)
│   ├── translations/en.json         # i18n strings
│   └── tests/View.spec.ts           # Vitest frontend tests
├── backend/
│   ├── scripts/main.py              # CRUD logic + type coercion
│   └── tests/test_main.py           # Pytest backend tests
├── docs/README.md                   # This file
└── type.json → notebook_item_types/settings-manager.json
```

## BaseCell Compliance

This cell follows the **ADDING_NEW_CELL_TYPE.md** mandatory requirements:

- ✅ Emits `execute` events consumed by the cell runner
- ✅ Emits `update:cell` to persist state in `initial_data`
- ✅ TypeScript frontend with i18n
- ✅ Tests for both frontend and backend

## Related

- **Phase 0–2**: TOTP + Redis infrastructure
- **Vault Manager Cell**: Companion cell for encrypted secrets
