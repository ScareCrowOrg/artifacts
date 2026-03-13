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
# Backend Integration Tests

This directory contains integration tests for the ScareVerse backend application.

## Purpose

Integration tests validate the interaction between multiple backend components, including:
- API endpoints with database
- Service layer integration
- External API interactions (mocked in test environment)
- Authentication and authorization flows

## Test Structure

Integration tests are organized by feature/module:
- API endpoint tests validate full request/response cycles
- Service integration tests verify cross-service communication
- Database integration tests ensure data persistence works correctly

## Running Tests

```bash
# Run all integration tests
cd backend
pytest tests/integration/backend/ -v

# Run specific test file
pytest tests/integration/backend/test_specific.py -v

# Run with coverage
pytest tests/integration/backend/ --cov=app --cov-report=html
```

## Test Environment

Integration tests run in an isolated test environment with:
- Test database (configured via `.env.test`)
- Mocked external services
- Test fixtures for common data setup

## Coverage

Current coverage: See coverage reports in `/backend/coverage.json`

Target: **90%** minimum for integration scenarios

## Related Documentation

- [Backend README](../../../README.md)
- [Test Architecture](../../../../docs/ARQUITETURA_TESTES.md)
- [Unit Tests](../unit/backend/README.md)
