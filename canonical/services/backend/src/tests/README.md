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
# Backend Tests

## Overview

This directory contains all automated tests for the ScareVerse backend (Python/FastAPI). Tests are organized by type and follow the architecture defined in [docs/arquitetura_testes](../../docs/arquitetura_testes/README.md).

## Directory Structure

```
backend/tests/
├── conftest.py              # Shared test fixtures and configuration
├── unit/                    # Unit tests (fast, isolated)
│   └── backend/            # Backend-specific unit tests
├── integration/             # Integration tests (multiple components)
│   └── backend/            # Backend integration tests
├── persistence/             # Database layer tests (with mongomock)
│   └── backend/            # Backend persistence tests
├── contracts/               # Contract tests (API validation)
│   ├── consumer/           # Frontend expectations
│   └── provider/           # Backend implementation validation
├── observability/           # Logging, metrics, tracing tests
├── endpoints/               # API endpoint tests
└── security/                # Security tests (SAST baseline)
```

## Test Types

### Unit Tests
**Location**: `unit/backend/`
**Purpose**: Test individual functions, methods, classes in isolation
**Execution Time**: < 2 minutes
**Coverage Target**: ≥ 90%

```bash
cd backend
pytest tests/unit/ -v
```

### Integration Tests
**Location**: `integration/backend/`
**Purpose**: Test interaction between multiple components
**Execution Time**: < 3 minutes

```bash
pytest tests/integration/ -v
```

### Persistence Tests
**Location**: `persistence/backend/`
**Purpose**: Test database operations with mongomock
**Mocking**: Always uses `mongomock` (never real MongoDB)

```bash
pytest tests/persistence/ -v
```

### Contract Tests
**Location**: `contracts/provider/`
**Purpose**: Validate that backend implements contracts expected by frontend
**Framework**: Pact

```bash
pytest tests/contracts/provider/ -v
```

### Observability Tests
**Location**: `observability/`
**Purpose**: Verify logging, metrics, and tracing instrumentation

```bash
pytest tests/observability/ -v
```

## Running Tests

### All Tests
```bash
cd backend
pytest tests/ -v
```

### With Coverage
```bash
pytest tests/ --cov=app --cov-report=html --cov-report=term
```

### Specific Test File
```bash
pytest tests/unit/backend/services/test_cell_service.py -v
```

### Failed Tests Only
```bash
pytest --lf  # Last failed
```

### Parallel Execution
```bash
pytest -n auto  # Use all available CPUs
```

## Configuration

### pytest.ini
Main pytest configuration file in `backend/pytest.ini`:
- Test discovery patterns
- Coverage settings
- Markers for test categorization

### conftest.py
Shared fixtures available to all tests:
- `mock_db`: MongoDB mock instance
- `sample_user`: Sample user data
- `sample_cell`: Sample cell data
- And more...

## Writing Tests

### Quick Start

1. **Identify test type** (unit, integration, persistence, etc.)
2. **Create test file** in appropriate directory
3. **Follow naming convention**: `test_<module_name>.py`
4. **Use AAA pattern**: Arrange, Act, Assert

### Example Unit Test

```python
# tests/unit/backend/services/test_cell_service.py
import pytest
from app.services.cell_service import CellService

def test_create_cell_with_valid_data():
    """Should create cell successfully with valid data."""
    # Arrange
    service = CellService()
    cell_data = {
        'tipo': 'text',
        'conteudo': 'Test content'
    }
    
    # Act
    result = service.create_cell(cell_data)
    
    # Assert
    assert result['id'] is not None
    assert result['tipo'] == 'text'
```

### Example Persistence Test

```python
# tests/persistence/backend/test_cell_repository.py
import pytest
from mongomock import MongoClient
from app.repositories.cell_repository import CellRepository

@pytest.fixture
def mock_db():
    client = MongoClient()
    db = client.test_db
    yield db
    client.close()

def test_create_cell_in_database(mock_db):
    """Should store cell in database."""
    # Arrange
    repo = CellRepository(mock_db)
    
    # Act
    cell = repo.create({'tipo': 'text', 'conteudo': 'Test'})
    
    # Assert
    assert cell['_id'] is not None
    found = repo.find_by_id(cell['_id'])
    assert found is not None
```

## Guidelines

### Do's ✅

- Write descriptive test names
- Use fixtures for common setup
- Mock external dependencies
- Keep tests fast (< 100ms per unit test)
- Aim for ≥ 90% coverage
- Use AAA pattern (Arrange, Act, Assert)

### Don'ts ❌

- Don't use real database in tests
- Don't make external API calls
- Don't use `time.sleep()` (use mocks instead)
- Don't write tests that depend on execution order
- Don't commit tests with debug statements

## Metrics

Current test metrics:

- **Total Tests**: ~284 tests
- **Execution Time**: ~4.2 minutes
- **Coverage**: 92.3%
- **Pass Rate**: 100%

Target metrics:

- **Execution Time**: < 5 minutes
- **Coverage**: ≥ 90%
- **Pass Rate**: 100%

## Resources

- [Testing Best Practices](../BEST_PRACTICES.md)
- [Contributing Guide](../CONTRIBUTING.md)
- [Test Architecture](../../docs/arquitetura_testes/README.md)
- [Pytest Documentation](https://docs.pytest.org/)

## Support

- Open issue with `testing-question` label
- Check [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- Review existing tests for examples

---

**Last Updated**: November 2024  
**Maintainer**: Test Automator Agent
