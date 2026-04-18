# Vault Manager Cell

## Purpose

**CRUD interface for managing encrypted secrets stored in the Launcher vault.** A security-category BaseCell that provides create, rotate, delete, and audit operations for AES-256-GCM encrypted secrets.

All secret values are **masked in the UI**. An audit trail tracks every access. Integrates with TOTP validation (Phase 2) and Redis L1 cache.

**Category**: Security
**Permissions**: `secrets:manage` (optional), `secrets:audit` (optional)

## Content Index

### Directories

| Directory | Description |
|-----------|-------------|
| [`backend/`](./backend/) | Python backend — `main.py` with `list`, `create`, `rotate`, `delete`, `audit` actions |
| [`frontend/`](./frontend/) | Vue 3 frontend — `View.vue`, tests, translations |
| [`docs/`](./docs/) | Cell-specific documentation |

### Key Files

| File | Description |
|------|-------------|
| [`type.json`](./type.json) | Cell type definition — inputs, outputs, permissions, discovery metadata |

## Actions

| Action | Description |
|--------|-------------|
| `list` | List all secrets (values masked) |
| `create` | Create a new encrypted secret |
| `rotate` | Generate a new value for an existing secret |
| `delete` | Permanently delete a secret |
| `audit` | View access/change audit trail |

## Related

- [`../vault-token-manager/`](../vault-token-manager/) — Read-only token access (non-admin complement)
- [Launcher TOTP Integration](../../../../../../docs/issues/launcher-totp-reintegration/) — TOTP validation for secret access
