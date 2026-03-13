---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - testing
  - langgraph
  - unit-tests
  - integration-tests
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# LangGraph Orchestrator - Testing Guide

This guide provides comprehensive testing strategies and examples for the LangGraph orchestrator module.

## Testing Philosophy

The orchestrator uses a **layered testing approach**:
1. **Unit Tests**: Test individual nodes in isolation
2. **Integration Tests**: Test node interactions and data flow
3. **E2E Tests**: Test complete user workflows through API endpoints

## Test Structure

```
tests/
├── unit/backend/orchestrator/
│   ├── test_instruction_receiver.py
│   ├── test_intention_classifier_node.py
│   ├── test_action_executor.py
│   ├── test_response_generator.py
│   ├── test_history_manager.py
│   ├── test_file_processor.py
│   └── test_function_calling.py
├── integration/backend/
│   ├── test_orchestrator_rag.py
│   ├── test_orchestrator_rag_unification.py
│   └── test_orchestration_integration.py
└── e2e/backend/
    └── test_chat_orchestrator_e2e.py
```

## Unit Testing

### Testing Individual Nodes

Each node can be tested independently by mocking dependencies:

```python
import pytest
from unittest.mock import Mock, patch
from app.orchestrator.langgraph.action_executor import executa_acao

def test_executa_acao_criar():
    """Test CRIAR action execution"""
    state = {
        "mensagem": "Crie uma célula de texto",
        "intencao": "CRIAR",
        "responsavel_id": "user123",
        "modelo": "mistral",
    }
    
    with patch('app.langchain_tools.criar_celula') as mock_criar:
        mock_criar.return_value = {"id": "cell_123", "conteudo": "..."}
        
        result = executa_acao(state)
        
        assert result["acao_realizada"] is True
        assert result["celula_criada"]["id"] == "cell_123"
        mock_criar.assert_called_once()

def test_executa_acao_conversar_skip():
    """Test CONVERSAR skips action execution"""
    state = {
        "mensagem": "Olá",
        "intencao": "CONVERSAR",
        "responsavel_id": "user123",
    }
    
    result = executa_acao(state)
    
    assert result["acao_realizada"] is False
```

### Testing Async Nodes

For async nodes, use `pytest.mark.asyncio`:

```python
import pytest
from app.orchestrator.langgraph.response_generator import retorna_resposta

@pytest.mark.asyncio
async def test_retorna_resposta_conversa_with_rag():
    """Test response generation with RAG context"""
    state = {
        "mensagem": "Explain architecture",
        "intencao": "CONVERSAR",
        "rag_context": [
            Mock(page_content="ScareVerse uses LangGraph for orchestration"),
            Mock(page_content="RAG retrieves context from documents")
        ],
        "target_llm": "ollama",
        "modelo": "mistral",
    }
    
    with patch('app.ollama_service.chat') as mock_ollama:
        mock_ollama.return_value = "Based on the docs, ScareVerse uses..."
        
        result = await retorna_resposta(state)
        
        assert "resposta" in result
        assert "LangGraph" in result["resposta"]
        mock_ollama.assert_called_once()
```

### Mocking External Services

Always mock external services (LLMs, databases, APIs) in unit tests:

```python
from unittest.mock import Mock, patch, AsyncMock

@pytest.fixture
def mock_rag_service():
    """Mock RAG service"""
    with patch('app.services.rag_service.get_rag_service') as mock:
        rag_instance = Mock()
        rag_instance.get_context = AsyncMock(return_value=(
            "user message",
            [Mock(page_content="doc1"), Mock(page_content="doc2")],
            "formatted context"
        ))
        mock.return_value = rag_instance
        yield rag_instance

@pytest.mark.asyncio
async def test_recebe_instrucao_with_rag(mock_rag_service):
    """Test instruction receiver with RAG"""
    state = {
        "mensagem": "Explain something",
        "use_rag": True,
        "session_id": "session_123",
    }
    
    result = await recebe_instrucao(state)
    
    assert "rag_context" in result
    assert len(result["rag_context"]) == 2
    mock_rag_service.get_context.assert_called_once()
```

## Integration Testing

### Testing Node Interactions

Integration tests verify that nodes work together correctly:

```python
import pytest
from app.orchestrator.langgraph import ChatOrchestrator

@pytest.mark.asyncio
async def test_full_graph_criar_flow():
    """Test complete CRIAR flow through graph"""
    orchestrator = ChatOrchestrator()
    
    with patch('app.langchain_tools.criar_celula') as mock_criar:
        mock_criar.return_value = {"id": "cell_123", "tipo": "text"}
        
        result = orchestrator.process(
            mensagem="Crie uma célula de texto",
            responsavel_id="user123",
            modelo="mistral"
        )
        
        # Verify flow through nodes
        assert result["intencao"] == "CRIAR"
        assert result["acao_realizada"] is True
        assert "celula_criada" in result
        assert "resposta" in result
        assert "sucesso" in result["resposta"].lower()

@pytest.mark.asyncio
async def test_full_graph_conversar_with_rag():
    """Test CONVERSAR flow with RAG context"""
    orchestrator = ChatOrchestrator()
    
    with patch('app.services.rag_service.get_rag_service') as mock_rag:
        rag_instance = Mock()
        rag_instance.get_context = AsyncMock(return_value=(
            "Explain architecture",
            [Mock(page_content="LangGraph orchestrates workflows...")],
            "context"
        ))
        mock_rag.return_value = rag_instance
        
        with patch('app.ollama_service.chat') as mock_ollama:
            mock_ollama.return_value = "ScareVerse uses LangGraph..."
            
            result = orchestrator.process(
                mensagem="Explain architecture",
                responsavel_id="user123",
                modelo="mistral",
                use_rag=True
            )
            
            assert result["intencao"] == "CONVERSAR"
            assert len(result["rag_context"]) > 0
            assert "LangGraph" in result["resposta"]
```

### Testing File Processing

Test file attachment handling with real file operations:

```python
import tempfile
from pathlib import Path

@pytest.mark.asyncio
async def test_file_processing_ollama():
    """Test Ollama file segmentation"""
    orchestrator = ChatOrchestrator()
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("This is test content for Ollama processing.\n" * 100)
        temp_path = f.name
    
    try:
        result = orchestrator.process(
            mensagem="Analyze this file",
            responsavel_id="user123",
            modelo="mistral",
            target_llm="ollama",
            attached_files=[
                {"path": temp_path, "type": "text/plain"}
            ]
        )
        
        assert "attached_files" in result
        assert len(result["attached_files"]) > 0
        assert "segments" in result["attached_files"][0]
    finally:
        Path(temp_path).unlink()
```

## E2E Testing

### Testing Through API Endpoints

E2E tests verify complete user workflows:

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_chat_endpoint_criar_celula():
    """Test cell creation through chat API"""
    response = client.post(
        "/api/chat/processar",
        headers={"Authorization": "Bearer test_token"},
        json={
            "mensagem": "Crie uma célula de texto",
            "assignee_id": "user123",
            "modelo": "mistral"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["intencao"] == "CRIAR"
    assert "celula" in data
    assert data["celula"]["tipo"] == "text"

def test_chat_endpoint_with_rag():
    """Test conversation with RAG through chat API"""
    response = client.post(
        "/api/chat/processar",
        headers={"Authorization": "Bearer test_token"},
        json={
            "mensagem": "Explain the architecture",
            "assignee_id": "user123",
            "modelo": "mistral",
            "useRag": True  # Enable RAG
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["intencao"] == "CONVERSAR"
    assert "ragContext" in data  # RAG context included
    assert len(data["ragContext"]) > 0
```

## Advanced Topics

For advanced testing patterns, debugging strategies, and detailed best practices, see:
- [Advanced Testing Guide](./advanced-testing.md) - Fixtures, debugging, coverage strategies

## References

- [Advanced Testing Guide](./advanced-testing.md) - Fixtures, debugging, best practices
- [Main README](../README.md) - Orchestrator overview
- [Node Documentation](./node-documentation.md) - Node details
- [pytest Documentation](https://docs.pytest.org/)

---

**Last Updated**: 2025-11-15  
**Test Count**: 50+ tests across unit/integration/E2E  
**Coverage Target**: 90%+
