# Vault Manager Cell

Secure CRUD interface for managing encrypted secrets in the launcher vault.

## Overview

The **Vault Manager Cell** provides a UI to create, rotate, delete and audit secrets stored in `~/.scareverse/{tenant}/settings/vault.json`.  It is part of the **Phase 3** implementation of the Launcher Centralized Secrets & Settings Manager epic.

## Features

- **List** all secrets (names visible, values masked)
- **Create** new secrets (with category and description)
- **Rotate** existing secrets (replaces the stored value)
- **Delete** secrets (with confirmation dialog)
- **Audit Trail** – every write operation is logged

## Cell Type ID

`vault-manager`

## Actions (Backend)

| Action   | Payload Fields                                    | Description               |
|----------|---------------------------------------------------|---------------------------|
| `list`   | —                                                 | Returns masked secret list |
| `create` | `secret_key`, `value`, `category`, `description`  | Creates a new secret       |
| `rotate` | `secret_key`, `new_value`                         | Rotates an existing secret |
| `delete` | `secret_key`                                      | Removes a secret           |
| `audit`  | `secret_key` (optional filter)                    | Returns audit log entries  |

## Architecture

```
vault-manager/
├── frontend/
│   ├── View.vue                    # Main UI (TypeScript + Tailwind)
│   ├── translations/en.json        # i18n strings
│   └── tests/View.spec.ts          # Vitest frontend tests
├── backend/
│   ├── scripts/main.py             # CRUD logic
│   └── tests/test_main.py          # Pytest backend tests
├── docs/README.md                  # This file
└── type.json → notebook_item_types/vault-manager.json
```

## BaseCell Compliance

This cell follows the **ADDING_NEW_CELL_TYPE.md** mandatory requirements:

- ✅ Emits `execute` events consumed by the cell runner
- ✅ Emits `update:cell` to persist state in `initial_data`
- ✅ TypeScript frontend with i18n
- ✅ Tests for both frontend and backend

## Related

- **Phase 0–2**: TOTP + Redis infrastructure
- **Settings Manager Cell**: Companion cell for non-sensitive settings
