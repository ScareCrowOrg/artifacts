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
# Test Troubleshooting Guide

This guide documents common test failures and their solutions, established during the PR #1 test fix initiative (Nov 2025).

## Quick Reference

### Test Execution
```bash
# Run all tests
cd backend
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=term --cov-report=html

# Run specific test file
pytest tests/unit/backend/test_backend_utils.py -v

# Run with short traceback
pytest tests/ -v --tb=short
```

### Current Status
- **Total Tests**: 273
- **Passing**: 261 (95.6%)
- **Failing**: 9 (3.3%) - RAG collection selection tests (outdated)
- **Skipped**: 3 (1.1%) - Require full Chroma/Ollama setup
- **Execution Time**: < 2 minutes ⚡

## Common Issues and Solutions

### 1. ModuleNotFoundError: No module named 'backend'

**Symptom:**
```python
ModuleNotFoundError: No module named 'backend'
```

**Cause:** Tests using absolute imports with `from backend.` prefix.

**Solution:** Change imports to use `from app.` or relative imports:

```python
# ❌ Wrong
from backend.utils import sanitize_filename
from backend.app.workflows import chunk_markdown

# ✅ Correct
from utils import sanitize_filename
from app.workflows import chunk_markdown
```

**Files Fixed:**
- `tests/unit/backend/test_backend_utils.py`
- `tests/unit/backend/test_chunking_strategies.py`
- `tests/unit/backend/test_vue_chunking_strategies.py`
- `tests/integration/backend/test_branched_ingestion_workflow.py`
- `tests/integration/backend/test_vue_preprocessing_integration.py`

---

### 2. AttributeError: Module does not have attribute (Mock Patch Issues)

**Symptom:**
```python
AttributeError: <module 'app.routers.chat_router'> does not have the attribute 'LLMProviderFactory'
AttributeError: <module 'app.services.providers.ollama_provider'> does not have the attribute 'chamar_ollama'
```

**Cause:** Patching imports that occur inside functions/methods instead of at module level.

**Solution:** Patch at the **source** where the function is defined, not where it's imported:

```python
# ❌ Wrong - Patching where it's imported (inside a function)
@patch('app.routers.chat_router.LLMProviderFactory')
@patch('app.services.providers.ollama_provider.chamar_ollama')

# ✅ Correct - Patching at the source
@patch('app.services.llm_provider_factory.LLMProviderFactory')
@patch('app.ollama_service.chamar_ollama')
```

**Files Fixed:**
- `tests/integration/backend/test_chat_endpoint_rag.py`
- `tests/integration/backend/test_llm_providers.py`

---

### 3. 404 Not Found on API Endpoints

**Symptom:**
```python
assert response.status_code == 200
AssertionError: assert 404 == 200
```

**Cause:** Incorrect API endpoint paths in tests.

**Solution:** Verify the correct API prefix. The default is `/api/`, not `/api/v1/`:

```python
# ❌ Wrong
response = client.get("/api/v1/traces/conversation/abc123")

# ✅ Correct
response = client.get("/api/traces/conversation/abc123")
```

**How to check actual routes:**
```python
from app.main import app
routes = [r for r in app.routes if hasattr(r, 'path')]
for route in routes:
    if 'trace' in route.path.lower():
        print(route.path)
```

**Files Fixed:**
- `tests/integration/backend/test_traces_router.py` (13 occurrences)

---

### 4. 401 Unauthorized (Auth Dependency Not Mocked)

**Symptom:**
```python
assert response.status_code == 200
AssertionError: assert 401 == 200
```

**Cause:** FastAPI auth dependency (`get_current_user_required`) not properly overridden.

**Solution:** Use `app.dependency_overrides` instead of `@patch` decorators:

```python
# ❌ Wrong - Patching doesn't work with FastAPI dependencies
@patch('app.routers.traces_router.get_current_user_required')
def test_endpoint(self, mock_auth, client):
    mock_auth.return_value = mock_user
    response = client.get("/api/endpoint")

# ✅ Correct - Use dependency_overrides
from app.auth import get_current_user_required

@pytest.fixture
def client(mock_user):
    """Create a test client with authentication override."""
    def override_get_current_user():
        return mock_user
    
    app.dependency_overrides[get_current_user_required] = override_get_current_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()  # Clean up!

def test_endpoint(self, client):
    response = client.get("/api/endpoint")  # Now authenticated!
```

**Important:** Always clear `app.dependency_overrides` after tests to avoid interference.

**Files Fixed:**
- `tests/integration/backend/test_traces_router.py`

---

### 5. AttributeError: RAGService object has no attribute '_get_ensemble_retriever'

**Symptom:**
```python
AttributeError: 'RAGService' object has no attribute '_get_ensemble_retriever'
```

**Status:** ⚠️ **Known Issue - Tests Outdated**

**Cause:** Tests written for old RAGService API before refactoring to use `RetrieverManager`.

**Current State:** 9 tests in `test_rag_collection_selection.py` fail due to this.

**Solution:** Tests need to be rewritten to match new architecture:
- Old API: `rag._get_ensemble_retriever(collections)`
- New API: Uses `RetrieverManager` internally, called via `rag.get_context()`

**Action Required:** Create follow-up issue to update tests for refactored RAG architecture.

**Files Affected:**
- `tests/unit/backend/test_rag_collection_selection.py` (9 tests)

---

## Test Environment Setup

### Dependencies
All test dependencies are in `requirements.txt`:
```bash
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
mongomock==4.1.2
bandit==1.7.7
```

### Environment Variables
Tests use `.env.test` file:
```bash
# Copy example file
cp .env.example .env.test

# Required for tests
export TESTING=true
export OLLAMA_BASE_URL=http://localhost:11434
export API_PREFIX=/api
```

### Mock Strategy
- **MongoDB**: Use `mongomock` for database tests
- **LLM Services**: Patch service functions (`chamar_ollama`, `chamar_gemini`, etc.)
- **Auth**: Use `app.dependency_overrides` for FastAPI dependencies
- **Vector Store**: Mock ChromaDB and LangChain when not testing RAG directly

---

## Performance Guidelines

### Target Execution Times
- **Unit tests**: < 2 minutes total
- **Contract tests**: < 3 minutes total
- **Main CI pipeline**: < 5 minutes total

### Current Performance
- **All tests**: ~1 second ⚡ (well under target!)

### Optimization Tips
1. Use `pytest -k "pattern"` to run subsets during development
2. Use `pytest-xdist` for parallel execution (not yet implemented)
3. Mock expensive operations (DB, API calls, embeddings)
4. Skip E2E tests requiring full infrastructure in unit test runs

---

## Running Tests in CI/CD

### GitHub Actions Workflow
```yaml
- name: Run Tests
  run: |
    cd backend
    pytest tests/ -v --cov=app --cov-report=json --cov-report=term
  env:
    TESTING: true
    OLLAMA_BASE_URL: http://mock-ollama:11434
```

### Coverage Requirements
- **Minimum**: 90% coverage for all modules (per RULESET.md)
- **Measurement**: Use `pytest-cov`
- **Reporting**: JSON, HTML, and terminal reports

### Failure Handling
- **Fail Fast**: CI should fail on first test failure
- **Artifacts**: Save test logs and coverage reports
- **Notifications**: Alert team on test failures

---

## Adding New Tests

### Test File Structure
```
tests/
├── unit/
│   └── backend/
│       ├── README.md
│       └── test_*.py        # Unit tests
├── integration/
│   └── backend/
│       ├── README.md
│       └── test_*.py        # Integration tests
└── TROUBLESHOOTING.md       # This file
```

### Test Naming Convention
- Files: `test_<module_name>.py`
- Classes: `Test<FeatureName>`
- Functions: `test_<what_it_tests>`

### Best Practices
1. **One test per behavior** - Don't test multiple things in one test
2. **Clear test names** - Describe what's being tested and expected outcome
3. **Arrange-Act-Assert** - Structure tests clearly
4. **Mock external dependencies** - Don't call real APIs or DBs in unit tests
5. **Clean up** - Clear mocks and overrides in teardown/fixtures

### Example Test Template
```python
import pytest
from unittest.mock import patch, AsyncMock

class TestMyFeature:
    """Test suite for My Feature."""
    
    @pytest.mark.asyncio
    @patch('app.services.my_service.external_call', new_callable=AsyncMock)
    async def test_feature_success_case(self, mock_call):
        """Test that feature works with valid input."""
        # Arrange
        mock_call.return_value = {"success": True}
        
        # Act
        result = await my_feature("valid_input")
        
        # Assert
        assert result["success"] is True
        mock_call.assert_called_once_with("valid_input")
```

---

## Contact

For questions or issues with tests:
1. Check this troubleshooting guide first
2. Check individual test README files
3. Open an issue with tag `tests` and `help-wanted`
4. Reference this document in your issue

## Version History

- **v1.0.0** (Nov 2025) - Initial troubleshooting guide created during PR #1 test fix initiative
  - Documented 5 import path fixes
  - Documented 2 mock path fixes  
  - Documented 13 traces router fixes
  - Identified 9 RAG tests needing update
  - Achieved 95.6% pass rate
