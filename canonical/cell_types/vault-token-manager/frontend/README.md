# Vault Token Manager – Frontend

## Purpose

Vue 3 frontend for the **Vault Token Manager Cell** — provides a read/write interface for managing API tokens stored in the Launcher vault. Includes vault unlock flow, token listing, and token creation.

## Content Index

| File | Description |
|------|-------------|
| [`View.vue`](./View.vue) | Main component — vault lock/unlock state, token list, create token form; full dark mode and i18n validated |
| [`VaultTokenForm.vue`](./VaultTokenForm.vue) | Form for creating a new API token — name, expiry, scope selector |
| [`VaultTokenList.vue`](./VaultTokenList.vue) | Paginated list of stored tokens — masked values, copy button, revoke action |
| [`VaultUnlockModal.vue`](./VaultUnlockModal.vue) | Modal to unlock the vault — PIN/password entry with attempt limiting |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`translations/`](./translations/) | `en.json`, `pt-BR.json` — i18n strings |

## Related

- [`../`](../) — Vault Token Manager Cell root
- [`../../vault-manager/`](../../vault-manager/) — Admin complement for full secret CRUD
