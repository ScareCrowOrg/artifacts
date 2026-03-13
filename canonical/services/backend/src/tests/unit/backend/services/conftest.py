"""
Shared fixtures for RAG and LLM service tests.

This module provides common mocks and fixtures for testing RAG, query expansion,
and post-processing services without requiring external dependencies.

Technical naming: All functions and variables in English.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any
from langchain_core.documents import Document


@pytest.fixture
def mock_ollama_response():
    """
    Mock response from Ollama API.
    
    Returns a standard Ollama API response structure that can be customized
    for different test scenarios.
    
    Returns:
        Dict with Ollama API response format
    """
    return {
        "response": "Mocked Ollama response",
        "model": "phi3:latest",
        "created_at": "2024-01-01T00:00:00Z",
        "done": True
    }


@pytest.fixture
def mock_chamar_ollama(mock_ollama_response):
    """
    Mock the chamar_ollama service function.
    
    Provides a mock that returns a standard Ollama response without
    making actual HTTP calls to the Ollama service.
    
    Usage:
        with mock_chamar_ollama as mock:
            result = await chamar_ollama(...)
            mock.assert_called_once()
    
    Returns:
        AsyncMock configured to return Ollama response
    """
    with patch('app.services.ollama_service.chamar_ollama', new_callable=AsyncMock) as mock:
        mock.return_value = mock_ollama_response
        yield mock


@pytest.fixture
def sample_documents() -> List[Document]:
    """
    Create sample LangChain Document objects for testing.
    
    Returns documents with varied content and metadata that simulate
    typical RAG retrieval results.
    
    Returns:
        List of Document objects with sample content
    """
    return [
        Document(
            page_content="ScareVerse is a horror game development platform.",
            metadata={"source": "docs/architecture.md", "type": "markdown"}
        ),
        Document(
            page_content="The backend uses FastAPI and MongoDB for persistence.",
            metadata={"source": "docs/backend.md", "type": "markdown"}
        ),
        Document(
            page_content="RAG retrieval uses ChromaDB for vector search.",
            metadata={"source": "docs/rag.md", "type": "markdown"}
        )
    ]


@pytest.fixture
def mock_format_context_for_prompt():
    """
    Mock the format_context_for_prompt utility function.
    
    Returns a simple formatted string from documents without requiring
    the actual utility implementation.
    
    Returns:
        Mock function that formats documents
    """
    def _format(docs: List[Document]) -> str:
        if not docs:
            return ""
        return "\n\n".join([f"[{i+1}] {doc.page_content}" for i, doc in enumerate(docs)])
    
    with patch('app.utils.input_processor.format_context_for_prompt', side_effect=_format) as mock:
        yield mock


@pytest.fixture
def mock_ensemble_retriever(sample_documents):
    """
    Mock CustomEnsembleRetriever for RAG testing.
    
    Simulates retrieval of relevant documents without requiring actual
    vector store access.
    
    Returns:
        Mock retriever that returns sample documents
    """
    mock = Mock()
    mock.get_relevant_documents = Mock(return_value=sample_documents)
    return mock


@pytest.fixture
def mock_retriever_manager(mock_ensemble_retriever):
    """
    Mock RetrieverManager for RAG service testing.
    
    Provides a mock manager that returns a mock ensemble retriever
    without requiring vector store initialization.
    
    Returns:
        Mock RetrieverManager
    """
    mock = Mock()
    mock.get_ensemble_retriever = Mock(return_value=mock_ensemble_retriever)
    mock.get_retriever_for_collection = Mock(return_value=mock_ensemble_retriever)
    return mock


@pytest.fixture
def mock_expanded_query():
    """
    Mock expanded query result from query expansion.
    
    Returns:
        Dict with expanded query data
    """
    return {
        "original": "Como criar uma célula?",
        "expanded": "célula, cell, criar, create, novo, new, item, notebook, estrutura, structure"
    }


@pytest.fixture
def mock_openai_client():
    """
    Mock OpenAI client for testing providers.
    
    Returns:
        Mock client configured for OpenAI API calls
    """
    with patch('openai.ChatCompletion.create') as mock:
        mock.return_value = {
            'choices': [{'message': {'content': 'Mocked OpenAI response'}}]
        }
        yield mock


@pytest.fixture
def mock_gemini_client():
    """
    Mock Gemini client for testing providers.
    
    Returns:
        Mock client configured for Gemini API calls
    """
    mock = MagicMock()
    mock.generate_content.return_value.text = "Mocked Gemini response"
    return mock


@pytest.fixture
async def async_mock_ollama():
    """
    Async fixture for mocking Ollama calls in async contexts.
    
    Returns:
        AsyncMock for Ollama service
    """
    mock = AsyncMock()
    mock.return_value = {
        "response": "Mocked async Ollama response",
        "model": "phi3:latest"
    }
    return mock


@pytest.fixture
def mock_config_values():
    """
    Mock configuration values for testing.
    
    Returns:
        Dict with common configuration values
    """
    return {
        "BASE_DIR": "/app",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_TIMEOUT": 30,
        "VECTORSTORE_PATH": "/app/chroma_db",
        "RAG_POSTPROCESS_LLM_ENABLED": True,
        "RAG_POSTPROCESS_LLM_MODEL": "phi3:latest",
        "DEFAULT_RAG_K": 5
    }


@pytest.fixture
def empty_documents() -> List[Document]:
    """
    Empty document list for testing edge cases.
    
    Returns:
        Empty list
    """
    return []


@pytest.fixture
def large_documents() -> List[Document]:
    """
    Large set of documents for testing performance.
    
    Returns:
        List of 20 documents
    """
    return [
        Document(
            page_content=f"Document {i} content with detailed information about topic {i}.",
            metadata={"source": f"docs/doc{i}.md", "index": i}
        )
        for i in range(20)
    ]
