# Vault Manager Cell – Backend Scripts

## Purpose

Execution scripts for the **Vault Manager Cell** backend.

## Content Index

| File | Description |
|------|-------------|
| [`__init__.py`](./__init__.py) | Package marker |
| [`main.py`](./main.py) | Vault operations: `list` (masked values), `create` (AES-256-GCM), `rotate`, `delete`, `audit`; integrates with TOTP validation and Redis L1 |

## Related

- [`../`](../) — Vault Manager Cell backend root
