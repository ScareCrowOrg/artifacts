# Three.js Scene Generator Cell – Backend Tests

## Purpose

Unit tests for the Three.js Scene Generator Cell backend.

## Content Index

| File | Description |
|------|-------------|
| [`__init__.py`](./__init__.py) | Package marker |
| [`test_main.py`](./test_main.py) | Tests for `execute_cell()` — LLM call mocking, code extraction, syntax validation, error handling |

## How to Run

```bash
cd backend
pytest artifacts/canonical/cell_types/threejs-scene-generator-cell/backend/tests/ -v
```

## Related

- [`../scripts/main.py`](../scripts/main.py) — The module being tested
