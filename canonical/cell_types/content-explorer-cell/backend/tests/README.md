# Content Explorer Cell – Backend Tests

## Purpose

Unit tests for the Content Explorer Cell backend.

## Content Index

| File | Description |
|------|-------------|
| [`test_main.py`](./test_main.py) | Tests for `execute_cell()` — action routing, type listing, asset filtering, delete flow |

## How to Run

```bash
cd backend
pytest artifacts/canonical/cell_types/content-explorer-cell/backend/tests/ -v
```

## Related

- [`../scripts/main.py`](../scripts/main.py) — The module being tested
