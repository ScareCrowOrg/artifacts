---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - testing
  - langgraph
  - fixtures
  - debugging
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# LangGraph Orchestrator - Advanced Testing Patterns

This document covers advanced testing techniques, debugging strategies, and best practices for the LangGraph orchestrator.

## Test Fixtures

### Common Fixtures

```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.fixture
def sample_state():
    """Basic orchestrator state"""
    return {
        "mensagem": "Test message",
        "responsavel_id": "user123",
        "modelo": "mistral",
        "historico": [],
        "intencao": None,
        "acao_realizada": False,
        "rag_context": [],
        "use_rag": False,
        "use_memory": False,
        "session_id": "session_123",
        "target_llm": "ollama",
    }

@pytest.fixture
def mock_llm_services():
    """Mock all LLM services"""
    with patch('app.ollama_service.chat') as mock_ollama, \
         patch('app.openai_service.chat') as mock_openai, \
         patch('app.gemini_service.chat') as mock_gemini:
        
        mock_ollama.return_value = "Ollama response"
        mock_openai.return_value = AsyncMock(return_value="OpenAI response")
        mock_gemini.return_value = AsyncMock(return_value="Gemini response")
        
        yield {
            "ollama": mock_ollama,
            "openai": mock_openai,
            "gemini": mock_gemini
        }

@pytest.fixture
def temp_file():
    """Temporary file for testing"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("Test file content")
        temp_path = f.name
    
    yield temp_path
    
    Path(temp_path).unlink()  # Cleanup
```

## Running Tests

### Run All Tests
```bash
pytest tests/
```

### Run Specific Test Categories
```bash
# Unit tests only
pytest tests/unit/backend/orchestrator/

# Integration tests only
pytest tests/integration/backend/test_orchestrator*.py

# E2E tests only
pytest tests/e2e/backend/

# Specific file
pytest tests/unit/backend/orchestrator/test_action_executor.py

# Specific test
pytest tests/unit/backend/orchestrator/test_action_executor.py::test_executa_acao_criar
```

### With Coverage
```bash
# Coverage for orchestrator module
pytest tests/unit/backend/orchestrator/ \
  --cov=backend/app/orchestrator/langgraph \
  --cov-report=html \
  --cov-report=term-missing

# Minimum coverage threshold (90%)
pytest tests/ --cov=backend/app/orchestrator/langgraph --cov-fail-under=90
```

### Verbose Output
```bash
pytest tests/ -v  # Verbose
pytest tests/ -vv  # Extra verbose
pytest tests/ -s   # Show print statements
```

## Test Coverage Goals

### Per Module
- **instruction_receiver.py**: 95%+ (critical entry point)
- **response_generator.py**: 95%+ (critical user-facing logic)
- **action_executor.py**: 90%+
- **intention_classifier_node.py**: 90%+
- **history_manager.py**: 85%+
- **file_processor.py**: 90%+
- **function_calling.py**: 85%+

### Overall Target
- **Orchestrator module**: 90%+ coverage
- **Critical paths**: 100% coverage (CRIAR, CONVERSAR flows)

## Debugging Tests

### Print State for Debugging
```python
def test_debug_state():
    state = {"mensagem": "test"}
    result = executa_acao(state)
    
    import pprint
    pprint.pprint(result)  # Pretty-print state
    
    assert result["acao_realizada"]
```

### Use pytest Debugger
```bash
# Drop into debugger on failure
pytest tests/ --pdb

# Drop into debugger at start of test
pytest tests/ --pdb --trace
```

### Capture Logs
```python
import logging

def test_with_logs(caplog):
    caplog.set_level(logging.DEBUG)
    
    result = executa_acao(state)
    
    # Check logs
    assert "Executando acao" in caplog.text
```

## Best Practices

### 1. Test Independence
- Each test should be independent
- Use fixtures for setup/teardown
- Don't rely on test execution order

### 2. Mock External Services
- Always mock LLMs, databases, APIs in unit tests
- Use real services only in integration/E2E tests
- Provide mock fixtures for common services

### 3. Test Both Success and Failure
```python
def test_success_case():
    # Test happy path
    pass

def test_error_handling():
    # Test error conditions
    pass

def test_edge_cases():
    # Test boundary conditions
    pass
```

### 4. Descriptive Test Names
```python
# Good
def test_executa_acao_criar_with_valid_params():
    pass

def test_executa_acao_raises_error_when_missing_responsavel_id():
    pass

# Bad
def test_1():
    pass

def test_action():
    pass
```

### 5. Use Parameterized Tests
```python
@pytest.mark.parametrize("intencao,expected_action", [
    ("CRIAR", True),
    ("EXECUTAR", True),
    ("CONVERSAR", False),
    ("REFLETIR", False),
])
def test_acao_realizada_by_intencao(intencao, expected_action):
    state = {"intencao": intencao, "mensagem": "test"}
    result = executa_acao(state)
    assert result["acao_realizada"] == expected_action
```

## References

- [Testing Guide](./testing-guide.md) - Core testing strategies
- [Main README](../README.md) - Orchestrator overview
- [Node Documentation](./node-documentation.md) - Node details
- [pytest Documentation](https://docs.pytest.org/)
- [Testing Best Practices](https://docs.python-guide.org/writing/tests/)

---

**Last Updated**: 2025-11-15  
**Coverage Target**: 90%+
