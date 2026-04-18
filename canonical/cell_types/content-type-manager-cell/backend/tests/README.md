# Content Type Manager Cell – Backend Tests

## Purpose

Unit tests for the Content Type Manager Cell backend.

## Content Index

| File | Description |
|------|-------------|
| [`test_main.py`](./test_main.py) | Tests for `execute_cell()` — type listing, schema retrieval, error handling |

## How to Run

```bash
cd backend
pytest artifacts/canonical/cell_types/content-type-manager-cell/backend/tests/ -v
```

## Related

- [`../scripts/main.py`](../scripts/main.py) — The module being tested
