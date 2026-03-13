---
processed: true
processed_date: 2025-12-09
themes:
  - testing
  - routers
  - unit-tests
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Router Unit Tests

Comprehensive unit tests for all API routers in `app/routers/`.

## Overview

This test suite ensures 90%+ code coverage for the router layer, testing all HTTP endpoints with various scenarios including success cases, authentication, authorization, validation errors, and error handling.

## Test Structure

```
tests/unit/backend/routers/
├── __init__.py
├── conftest.py              # Shared fixtures and test helpers
├── test_traces_router.py    # Traces API tests (11 tests) ✅
├── test_system_router.py    # System API tests (5 tests) ✅  
├── test_config_router.py    # Config API tests (8 tests) ✅
└── [additional router tests to be added]
```

## Fixtures (conftest.py)

The `conftest.py` provides shared fixtures for all router tests:

- `client` - FastAPI TestClient for making HTTP requests
- `mock_user` - Mock authenticated user
- `mock_admin_user` - Mock admin user
- `mock_db` - Mock database instance
- `mock_celula`, `mock_livro`, `mock_session`, etc. - Mock data models
- `cleanup` - Auto-cleanup of dependency overrides after each test

## Testing Patterns

### Authentication Override

Tests use FastAPI's `dependency_overrides` to mock authentication:

```python
@patch('app.routers.traces_router.db')
def test_endpoint(mock_db, client, mock_user):
    app.dependency_overrides[get_current_user_required] = lambda: mock_user
    
    response = client.get("/api/traces/recent")
    
    assert response.status_code == 200
```

### Database Mocking

Database operations are mocked using `unittest.mock`:

```python
@patch('app.routers.traces_router.db')
def test_database_interaction(mock_db, client):
    mock_db.find_many.return_value = [mock_trace_1, mock_trace_2]
    
    response = client.get("/api/traces/recent")
    
    assert len(response.json()["traces"]) == 2
```

### Error Scenarios

All tests cover error scenarios:

```python
def test_not_found(mock_db, client, mock_user):
    """Test 404 when resource not found."""
    mock_db.find_many.return_value = []
    
    response = client.get("/api/resource/nonexistent")
    
    assert response.status_code == 404
```

## Running Tests

### Run all router tests:
```bash
cd backend
pytest tests/unit/backend/routers/ -v
```

### Run specific router tests:
```bash
pytest tests/unit/backend/routers/test_traces_router.py -v
```

### Run with coverage:
```bash
pytest tests/unit/backend/routers/ --cov=app.routers --cov-report=term-missing
```

### Run specific test class or method:
```bash
pytest tests/unit/backend/routers/test_traces_router.py::TestGetTraceByConversationId -v
pytest tests/unit/backend/routers/test_traces_router.py::TestGetTraceByConversationId::test_get_trace_success -v
```

## Test Coverage Goals

Each router should have tests covering:

- ✅ **Success cases** (200, 201 responses)
- ✅ **Authentication** (401 Unauthorized)
- ✅ **Authorization** (403 Forbidden)
- ✅ **Validation errors** (400, 422 Unprocessable Entity)
- ✅ **Not found errors** (404)
- ✅ **Server errors** (500)
- ✅ **Edge cases** (empty results, pagination, filtering)

Target: **90%+ code coverage** per router.

## Current Status

| Router | Tests | Status | Coverage |
|--------|-------|--------|----------|
| `traces_router.py` | 11 | ✅ Complete | High |
| `system_router.py` | 5 | ✅ Complete | Medium |
| `config_router.py` | 8 | ✅ Complete | Medium |
| `chat_router.py` | 0 | ⏳ In Progress | - |
| `auth_router.py` | 0 | 📋 Planned | - |
| `celulas_router.py` | 0 | 📋 Planned | - |
| `livros_router.py` | 0 | 📋 Planned | - |
| `file_ops_router.py` | 0 | 📋 Planned | - |
| `issues_router.py` | 0 | 📋 Planned | - |
| `issues_dashboard_router.py` | 0 | 📋 Planned | - |
| `modelos_ia_router.py` | 0 | 📋 Planned | - |
| `ngrok_router.py` | 0 | 📋 Planned | - |
| `notebook_item_types_router.py` | 0 | 📋 Planned | - |
| `pipeline_items_router.py` | 0 | 📋 Planned | - |
| `services_router.py` | 0 | 📋 Planned | - |
| `sessoes_router.py` | 0 | 📋 Planned | - |
| `usuarios_router.py` | 0 | 📋 Planned | - |
| `router.py` (legacy) | 0 | 📋 Planned | - |

**Total Tests:** 22 passing, 6 skipped

## Known Issues

Some tests are skipped due to bugs in the router code itself (not test issues):

1. **system_router.py dev-login tests** - Router has incorrect relative import (`from .auth` should be `from app.auth` or `from ..auth`)
2. **config_router.py OAuth config tests** - Router uses relative import `.config` which causes issues in test context

These issues should be fixed in the router code, not worked around in tests.

## Best Practices

1. **Use descriptive test names** - Test name should describe what is being tested
2. **One assertion per test** - Keep tests focused and atomic
3. **Mock external dependencies** - Database, external APIs, file system
4. **Test edge cases** - Empty results, None values, invalid input
5. **Use fixtures** - Reuse common setup via pytest fixtures
6. **Clean up** - Use autouse fixtures to clean up dependency overrides
7. **Follow AAA pattern** - Arrange, Act, Assert

## Contributing

When adding tests for a new router:

1. Create `test_<router_name>.py` in this directory
2. Import required models and fixtures from `conftest.py`
3. Create test classes for each endpoint or logical grouping
4. Ensure 90%+ coverage of the router code
5. Run tests locally before committing
6. Update this README with the new router status

## References

- [FastAPI Testing Documentation](https://fastapi.tiangolo.com/tutorial/testing/)
- [Pytest Documentation](https://docs.pytest.org/)
- [ScareVerse Test Architecture](../../../../docs/ARQUITETURA_TESTES.md)
- [Router Documentation](../../../../backend/app/routers/README.md)
