# Chat IA Cell – Backend Tests

## Purpose

Unit tests for the Chat IA Cell backend execution logic.

## Content Index

| File | Description |
|------|-------------|
| [`__init__.py`](./__init__.py) | Package marker |
| [`test_main.py`](./test_main.py) | Tests for `execute_cell()` — validates routing logic, intention classification, direct LLM path, and orchestrator path |

## How to Run

```bash
# From repository root
cd backend
pytest artifacts/canonical/cell_types/chat-ia/backend/tests/ -v
```

## Related

- [`../scripts/main.py`](../scripts/main.py) — The module being tested
- [`../`](../) — Chat IA Cell backend root
