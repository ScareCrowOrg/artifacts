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
# Backend Unit Tests - Services

## Overview

Unit tests for service layer modules that contain business logic.

## Files Tested

Services in `app/services/`:
- `cell_service.py` - Cell management logic
- `rag_service.py` - RAG (Retrieval-Augmented Generation) logic
- `rag_postprocessor.py` - RAG response post-processing
- `openai_assistant_service.py` - OpenAI assistant integration
- `query_expander_service.py` - Query expansion logic
- And more...

## Running Tests

```bash
cd backend
pytest tests/unit/backend/services/ -v
```

## Test Coverage

- Business logic validation
- Service method behavior
- Error handling
- Edge cases
- Input validation

## Mocking Strategy

All tests use mocks for:
- Database operations
- External API calls (OpenAI, etc.)
- File system operations

---

For more details, see [Backend Tests README](../../README.md)
