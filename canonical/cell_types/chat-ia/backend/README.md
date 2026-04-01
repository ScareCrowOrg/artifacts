# Chat IA Cell — Backend

Python backend script for the Chat IA cell, implementing the `execute-ephemeral` pattern.

## Purpose

This package provides the server-side execution logic for the Chat IA cell. It accepts execution payloads from the `/api/cells/execute-ephemeral` endpoint, validates input, classifies user intention, and routes requests to either a direct LLM call or the AI orchestrator.

## Index

### Files

| File | Description |
|------|-------------|
| `__init__.py` | Python package marker with module docstring |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| `scripts/` | Execution entry point (`main.py`) — `execute_cell()` async function implementing the full chat pipeline |
| `tests/` | Unit tests for `scripts/main.py` with 90%+ coverage |

## Architecture

```
execute-ephemeral endpoint
         ↓
  execute_cell(cell_data, user_id)
         ↓
  Input validation & normalization
         ↓
  Intention classification
     /          \
Direct LLM    AI Orchestrator
  call         (multi-step)
     \          /
  Standardized response
```

## Key Responsibilities

- **Input validation**: Checks required fields (`prompt`, model configuration)
- **Intention classification**: Determines whether the request requires direct LLM response or orchestration
- **Routing**: Delegates to `chat_router.py` logic (reused, not duplicated)
- **Response normalization**: Returns a standard `{ output, metadata, status }` shape

## Usage

This backend is invoked automatically by the ScareVerse platform when the Chat IA cell is executed. It is not called directly by developers in normal usage.

To run tests:

```bash
pytest artifacts/canonical/cell_types/chat-ia/backend/tests/ -v
```

## Related Documentation

- [Chat IA Cell Root](../) - Full cell overview
- [Chat IA Frontend](../frontend/) - Vue frontend for this cell
- [Shared Services](../../../../shared/services/) - Shared backend service utilities
