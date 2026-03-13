---
processed: true
processed_date: 2025-12-09
themes:
  - testing
  - backend
  - frontend
  - quality-assurance
modules:
  - backend
  - frontend
  - testing
code_verified: true
dead_docs_found: false
---
# Backend Unit Tests

This directory contains unit tests for the ScareVerse backend application.

## Purpose

Unit tests validate individual components in isolation, including:
- Service classes and methods
- Utility functions
- Data models and validators
- Business logic

## Test Structure

Unit tests are organized by module:
- `test_*.py` - Test files following pytest conventions
- Each test file corresponds to a module in `app/`
- Tests use mocking to isolate units under test

## Running Tests

```bash
# Run all unit tests
cd backend
pytest tests/unit/backend/ -v

# Run specific test file
pytest tests/unit/backend/test_specific.py -v

# Run with coverage
pytest tests/unit/backend/ --cov=app --cov-report=html

# Run specific test
pytest tests/unit/backend/test_file.py::test_function_name -v
```

## Test Environment

Unit tests should:
- Mock external dependencies (database, APIs, file system)
- Run quickly (< 2 minutes for all unit tests)
- Be independent and isolated
- Use fixtures from `conftest.py` for common setup

## Coverage

Current coverage: See coverage reports in `/backend/coverage.json`

Target: **90%** minimum coverage for all backend modules

## Writing Tests

Follow these guidelines:
- Use descriptive test names: `test_should_do_something_when_condition()`
- One assertion concept per test
- Use pytest fixtures for setup/teardown
- Mock external dependencies
- Test edge cases and error conditions

## Related Documentation

- [Backend README](../../../README.md)
- [Test Architecture](../../../../docs/ARQUITETURA_TESTES.md)
- [Integration Tests](../../integration/backend/README.md)
