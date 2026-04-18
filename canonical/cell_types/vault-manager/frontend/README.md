# Vault Manager Cell – Frontend

## Purpose

Vue 3 frontend for the **Vault Manager Cell** — tabbed interface for listing, creating, rotating, and deleting encrypted secrets, with an audit trail view.

## Content Index

| File | Description |
|------|-------------|
| [`View.vue`](./View.vue) | Main component — tabbed UI (`list`, `create`, `rotate`, `audit`); all secret values masked; full i18n and dark mode support |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`tests/`](./tests/) | `View.spec.ts` — component tests |
| [`translations/`](./translations/) | `en.json` — i18n strings |

## Related

- [`../`](../) — Vault Manager Cell root
