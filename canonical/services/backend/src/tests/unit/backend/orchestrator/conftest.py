"""
Shared fixtures for orchestrator tests.

Provides mocked dependencies for testing orchestrator modules:
- Mocked RAG service
- Mocked database (mongomock)
- Mocked LLM services (OpenAI, Gemini, Ollama)
- Mocked intention classifier
- Sample state objects
"""

import pytest
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import mongomock

from app.orchestrator.langgraph.langgraph_state import OrchestratorState
from app.intention_classifier import IntentionType


@pytest.fixture
def sample_state() -> OrchestratorState:
    """Provide a basic orchestrator state for testing."""
    return {
        "mensagem": "Hello, how can you help me?",
        "historico": [],
        "intencao": None,
        "responsavel_id": "user123",
        "model": "ollama",
        "acao_realizada": False,
        "resultado_acao": None,
        "resposta_final": "",
        "celula_criada": None,
        "document_paths": None,
        "enable_function_calling": False,
        "attached_files": None,
        "attached_files_metadata": None,
        "rag_context": None,
        "use_rag": False,
        "session_id": "session123",
        "use_memory": False,
        "target_llm": "ollama",
        "current_chat_summary": None,
        "recent_chat_history": [],
        "turns_since_last_summary": 0,
        "summary_threshold_turns": 10,
        "summary_threshold_tokens": 3000,
        "enable_tracing": False,
        "conversation_id": None,
        "trace_cell_id": None,
    }


@pytest.fixture
def state_with_rag(sample_state) -> OrchestratorState:
    """Provide state with RAG enabled and context."""
    # Create mock documents with page_content attribute
    mock_doc1 = Mock()
    mock_doc1.page_content = "RAG document content 1"
    mock_doc1.metadata = {"source": "doc1.pdf", "page": 1}
    
    mock_doc2 = Mock()
    mock_doc2.page_content = "RAG document content 2"
    mock_doc2.metadata = {"source": "doc2.pdf", "page": 2}
    
    state = sample_state.copy()
    state["use_rag"] = True
    state["rag_context"] = [mock_doc1, mock_doc2]
    return state


@pytest.fixture
def state_with_files(sample_state) -> OrchestratorState:
    """Provide state with attached files."""
    state = sample_state.copy()
    state["attached_files"] = [
        {
            "path": "/tmp/test_file1.txt",
            "type": "text/plain",
            "size": 1024
        },
        {
            "path": "/tmp/test_file2.pdf",
            "type": "application/pdf",
            "size": 2048
        }
    ]
    state["target_llm"] = "openai"
    return state


@pytest.fixture
def state_with_history(sample_state) -> OrchestratorState:
    """Provide state with conversation history."""
    state = sample_state.copy()
    state["historico"] = [
        {"role": "user", "content": "What is LangGraph?"},
        {"role": "assistant", "content": "LangGraph is a framework for building stateful AI agents."},
        {"role": "user", "content": "How does it work?"},
        {"role": "assistant", "content": "It uses state machines and graph-based orchestration."}
    ]
    state["recent_chat_history"] = state["historico"].copy()
    state["turns_since_last_summary"] = 2
    state["use_memory"] = True
    return state


@pytest.fixture
def mock_rag_service():
    """Provide a mocked RAG service."""
    # Create a mock document with page_content attribute
    mock_doc = Mock()
    mock_doc.page_content = "Mocked RAG content"
    mock_doc.metadata = {"source": "mock.pdf", "page": 1}
    
    mock_service = Mock()
    mock_service.retrieve_context = Mock(return_value=[
        {
            "content": "Mocked RAG content",
            "metadata": {"source": "mock.pdf", "page": 1}
        }
    ])
    mock_service.get_context = Mock(return_value=(
        [],  # prioritized_docs
        [mock_doc],  # general_docs - use mock documents with page_content
        []   # all_docs
    ))
    mock_service.debug_vectorstore = Mock()
    return mock_service


@pytest.fixture
def mock_intention_classifier():
    """Provide a mocked intention classifier."""
    mock_classifier = Mock()
    mock_classifier.classify = Mock(return_value=IntentionType.CONVERSAR)
    mock_classifier.get_explanation = Mock(return_value="User wants to have a conversation")
    return mock_classifier


@pytest.fixture
def mock_ollama_service():
    """Provide a mocked Ollama service."""
    mock_service = AsyncMock()
    mock_service.return_value = "Mocked Ollama response"
    return mock_service


@pytest.fixture
def mock_openai_service():
    """Provide a mocked OpenAI service."""
    mock_service = AsyncMock()
    mock_service.return_value = "Mocked OpenAI response"
    return mock_service


@pytest.fixture
def mock_gemini_service():
    """Provide a mocked Gemini service."""
    mock_service = AsyncMock()
    mock_service.return_value = "Mocked Gemini response"
    return mock_service


@pytest.fixture
def mock_cell_tools():
    """Provide a mocked CellTools class."""
    with patch('app.orchestrator.langgraph.action_executor.CellTools') as mock:
        mock.criar_celula_impl = Mock(return_value={
            "success": True,
            "celula_id": "cell123",
            "tipo_celula_id": "type456",
            "estado": "pendente"
        })
        yield mock


@pytest.fixture
def mock_db():
    """Provide a mocked MongoDB database using mongomock."""
    client = mongomock.MongoClient()
    db = client.scareverse_test
    yield db
    client.close()


@pytest.fixture
def mock_file_upload():
    """Provide mocked file upload functions for different LLM providers."""
    with patch('app.orchestrator.langgraph.file_processor.upload_file_to_openai_api') as openai_mock, \
         patch('app.orchestrator.langgraph.file_processor._upload_to_gemini') as gemini_mock:
        
        openai_mock.return_value = AsyncMock(return_value="file-abc123")
        gemini_mock.return_value = AsyncMock(return_value="gemini-file-uri-xyz")
        
        yield {
            'openai': openai_mock,
            'gemini': gemini_mock
        }


@pytest.fixture
def mock_conversation_memory():
    """Provide mocked conversation memory utilities."""
    with patch('app.orchestrator.langgraph.history_manager.update_history') as update_mock, \
         patch('app.orchestrator.langgraph.history_manager.should_summarize') as should_mock, \
         patch('app.orchestrator.langgraph.history_manager.build_summarization_prompt') as build_mock, \
         patch('app.orchestrator.langgraph.history_manager.reset_after_summarization') as reset_mock:
        
        # Configure mocks with sensible defaults
        update_mock.side_effect = lambda state, **kwargs: state
        should_mock.return_value = False
        build_mock.return_value = "Summarize this conversation: ..."
        reset_mock.side_effect = lambda state: state
        
        yield {
            'update_history': update_mock,
            'should_summarize': should_mock,
            'build_summarization_prompt': build_mock,
            'reset_after_summarization': reset_mock
        }


@pytest.fixture
def mock_tracing_service():
    """Provide mocked conversation tracing service."""
    with patch('app.orchestrator.langgraph.instruction_receiver._initialize_conversation_tracing') as init_mock, \
         patch('app.orchestrator.langgraph.response_generator._record_context_assembled_fragment') as record_mock:
        
        init_mock.return_value = AsyncMock()
        record_mock.return_value = AsyncMock()
        
        yield {
            'initialize_tracing': init_mock,
            'record_context': record_mock
        }
