# Content Manager Cell – Backend Tests

## Purpose

Unit tests for the Content Manager Cell backend.

## Content Index

| File | Description |
|------|-------------|
| [`test_main.py`](./test_main.py) | Tests for `execute_cell()` — list, upload, delete, metadata actions with mocked S3/R2 storage |

## How to Run

```bash
cd backend
pytest artifacts/canonical/cell_types/content-manager-cell/backend/tests/ -v
```

## Related

- [`../scripts/`](../scripts/) — The modules being tested
