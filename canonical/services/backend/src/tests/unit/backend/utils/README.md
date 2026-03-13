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
# Backend Unit Tests - Utils

## Overview

Unit tests for utility modules including helpers, validators, and common functions.

## Files Tested

Utils in `app/utils/`:
- `trace_export.py` - Trace export functionality
- `conversation_memory.py` - Conversation memory management
- And other utility modules

## Running Tests

```bash
cd backend
pytest tests/unit/backend/utils/ -v
```

## Test Coverage

- Utility function behavior
- Input validation
- Edge cases
- Error handling
- Data transformation

---

For more details, see [Backend Tests README](../../README.md)
