# Log Toggle Cell – Backend Tests

## Purpose

Unit tests for the Log Toggle Cell backend.

## Content Index

| File | Description |
|------|-------------|
| [`__init__.py`](./__init__.py) | Package marker |
| [`test_main.py`](./test_main.py) | Tests for `execute_cell()` — enable/disable/list actions, error handling |

## How to Run

```bash
cd backend
pytest artifacts/canonical/cell_types/log-toggle-cell/backend/tests/ -v
```

## Related

- [`../scripts/main.py`](../scripts/main.py) — The module being tested
