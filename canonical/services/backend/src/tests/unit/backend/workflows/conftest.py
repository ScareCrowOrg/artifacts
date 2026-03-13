#!/usr/bin/env python3
"""
Pytest Fixtures for Workflow Unit Tests

Provides common mocks and test fixtures for workflow module testing.
All external dependencies (DB, Vector Store, LLM, File I/O) are mocked.
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, MagicMock, mock_open, patch


@pytest.fixture
def mock_file_content():
    """Provide sample file content for testing."""
    return {
        'markdown': """# Test Document

This is a test document.

## Section 1

Content for section 1.

## Section 2

Content for section 2.
""",
        'python': '''"""Test module docstring."""

def test_function():
    """Test function docstring."""
    return "result"

class TestClass:
    """Test class docstring."""
    
    def test_method(self):
        """Test method docstring."""
        pass
''',
        'json': '''{
    "key1": "value1",
    "key2": {
        "nested": "value2"
    }
}''',
        'yaml': '''key1: value1
key2:
  nested: value2
''',
        'empty': ''
    }


@pytest.fixture
def mock_chunks():
    """Provide sample chunks for testing."""
    return [
        {
            "text": "Test content 1",
            "metadata": {
                "document_id": "test_doc_001",
                "source": "/test/document.md",
                "file_type": "markdown",
                "chunk_type": "markdown_section",
                "embedding_model_id": "mistral",
                "target_collection": "scareverse_docs"
            }
        },
        {
            "text": "Test content 2",
            "metadata": {
                "document_id": "test_doc_001",
                "source": "/test/document.md",
                "file_type": "markdown",
                "chunk_type": "markdown_section",
                "embedding_model_id": "mistral",
                "target_collection": "scareverse_docs"
            }
        }
    ]


@pytest.fixture
def mock_chunks_with_text():
    """Provide sample chunks with 'text' field for generate_embeddings_and_store.py."""
    return [
        {
            "text": "Test content 1",
            "metadata": {
                "document_id": "test_doc_001",
                "source": "/test/document.md",
                "file_type": "markdown",
                "chunk_type": "markdown_section",
                "embedding_model_id": "mistral",
                "target_collection": "scareverse_docs",
                "chunk_id": "test_chunk_001",
                "chunk_index": 0
            }
        },
        {
            "text": "Test content 2",
            "metadata": {
                "document_id": "test_doc_001",
                "source": "/test/document.md",
                "file_type": "markdown",
                "chunk_type": "markdown_section",
                "embedding_model_id": "mistral",
                "target_collection": "scareverse_docs",
                "chunk_id": "test_chunk_002",
                "chunk_index": 1
            }
        }
    ]


@pytest.fixture
def mock_code_chunks():
    """Provide sample code chunks for testing."""
    return [
        {
            "text": "def test(): pass",  # Changed from "content" to "text"
            "metadata": {
                "document_id": "test_doc_002",
                "source": "/test/code.py",
                "file_type": "python",
                "chunk_type": "function",
                "embedding_model_id": "deepseek-coder",
                "target_collection": "scareverse_code",
                "chunk_id": "test_code_chunk_001",
                "chunk_index": 0
            }
        }
    ]


@pytest.fixture
def mock_ollama_embeddings():
    """Mock OllamaEmbeddings class."""
    mock_embeddings = MagicMock()
    mock_embeddings.embed_documents.return_value = [
        [0.1, 0.2, 0.3],  # Mock embedding vector
        [0.4, 0.5, 0.6]
    ]
    mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
    return mock_embeddings


@pytest.fixture
def mock_chroma_vectorstore():
    """Mock Chroma vector store."""
    mock_store = MagicMock()
    mock_store.add_documents.return_value = ["id1", "id2"]
    mock_store._collection = MagicMock()
    mock_store._collection.count.return_value = 10
    return mock_store


@pytest.fixture
def mock_path_exists(monkeypatch):
    """Mock Path.exists() to return True."""
    def mock_exists(self):
        return True
    monkeypatch.setattr(Path, "exists", mock_exists)


@pytest.fixture
def mock_path_not_exists(monkeypatch):
    """Mock Path.exists() to return False."""
    def mock_exists(self):
        return False
    monkeypatch.setattr(Path, "exists", mock_exists)


@pytest.fixture
def mock_uuid():
    """Mock UUID generation for consistent testing."""
    with patch('uuid.uuid4') as mock:
        mock.return_value = MagicMock()
        mock.return_value.__str__ = Mock(return_value='test-uuid-1234')
        yield mock


@pytest.fixture
def temp_chunks_file(tmp_path, mock_chunks_with_text):
    """Create a temporary chunks JSON file."""
    chunks_file = tmp_path / "chunks.json"
    with open(chunks_file, 'w') as f:
        json.dump(mock_chunks_with_text, f)
    return chunks_file


@pytest.fixture
def temp_code_chunks_file(tmp_path, mock_code_chunks):
    """Create a temporary code chunks JSON file."""
    chunks_file = tmp_path / "code_chunks.json"
    with open(chunks_file, 'w') as f:
        json.dump(mock_code_chunks, f)
    return chunks_file


@pytest.fixture
def temp_test_file(tmp_path, mock_file_content):
    """Create temporary test files."""
    files = {}
    for file_type, content in mock_file_content.items():
        if file_type == 'empty':
            continue
        file_path = tmp_path / f"test.{file_type}"
        if file_type == 'python':
            file_path = tmp_path / "test.py"
        elif file_type == 'markdown':
            file_path = tmp_path / "test.md"
        
        with open(file_path, 'w') as f:
            f.write(content)
        files[file_type] = file_path
    
    return files


@pytest.fixture
def mock_pdf_reader():
    """Mock PdfReader for PDF processing."""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "PDF page content"
    
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page, mock_page]
    
    return mock_reader


@pytest.fixture
def mock_langchain_document():
    """Mock LangChain Document class."""
    def create_doc(content, metadata=None):
        doc = MagicMock()
        doc.page_content = content
        doc.metadata = metadata or {}
        return doc
    return create_doc


@pytest.fixture
def mock_config_values(monkeypatch):
    """Mock configuration values."""
    monkeypatch.setenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    monkeypatch.setenv('VECTORSTORE_PATH', '/tmp/vectorstore')
