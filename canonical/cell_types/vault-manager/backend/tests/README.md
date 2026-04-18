# Vault Manager Cell – Backend Tests

## Purpose

Unit tests for the Vault Manager Cell backend.

## Content Index

| File | Description |
|------|-------------|
| [`test_main.py`](./test_main.py) | Tests for all vault actions — list (masked), create, rotate, delete, audit; encryption/decryption mocking |

## How to Run

```bash
cd backend
pytest artifacts/canonical/cell_types/vault-manager/backend/tests/ -v
```

## Related

- [`../scripts/main.py`](../scripts/main.py) — The module being tested
