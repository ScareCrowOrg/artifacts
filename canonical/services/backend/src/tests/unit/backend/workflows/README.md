---
processed: true
processed_date: 2025-12-09
themes:
  - testing
  - unit-tests
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Backend Unit Tests - Workflows

## Overview

Unit tests for workflow modules that orchestrate multi-step processes.

## Files Tested

Workflows in `app/workflows/`:
- `preprocess_and_chunk.py` - Document preprocessing and chunking
- `generate_embeddings_and_store.py` - Embedding generation
- `chunking_strategies.py` - Various chunking strategies
- `vue_chunking_strategies.py` - Vue component chunking
- And more...

## Running Tests

```bash
cd backend
pytest tests/unit/backend/workflows/ -v
```

## Test Coverage

- Workflow orchestration logic
- Step-by-step execution
- Error handling in pipelines
- Data transformation
- Strategy selection

## Mocking Strategy

All tests mock:
- Database operations
- File I/O
- External services (OpenAI embeddings, etc.)
- Long-running operations

---

For more details, see [Backend Tests README](../../README.md)
