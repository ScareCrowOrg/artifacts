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
# Backend Unit Tests - Orchestrator

## Overview

Unit tests for orchestrator modules that coordinate complex multi-step operations using LangGraph.

## Files Tested

Orchestrator modules in `app/orchestrator/`:
- `core.py` - Core orchestration logic
- `langgraph/` - LangGraph-based workflows
- And more...

## Running Tests

```bash
cd backend
pytest tests/unit/backend/orchestrator/ -v
```

## Test Coverage

- Orchestration flow logic
- State management
- Node transitions
- Error handling in workflows
- Conditional routing

---

For more details, see [Backend Tests README](../../README.md)
