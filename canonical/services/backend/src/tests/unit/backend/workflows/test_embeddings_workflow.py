#!/usr/bin/env python3
"""
Unit Tests for Embedding Generation and Storage Workflows

Tests for:
- app/workflows/generate_embeddings_and_store.py
- app/workflows/generate_code_embeddings_and_store.py

Covers:
- Chunk loading from JSON
- Embedding model initialization
- Chunk ID generation
- Vector store operations
- Collection name determination
- Error handling and edge cases

Target: 90%+ test coverage
"""

import json
import hashlib
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call

from app.workflows.generate_embeddings_and_store import (
    get_collection_name_from_file_type,
    load_chunks_from_json,
    initialize_embedding_model,
    generate_chunk_id,
    store_chunks_in_chromadb
)

from app.workflows.generate_code_embeddings_and_store import (
    load_code_chunks_from_json,
    initialize_deepseek_embeddings,
    generate_chunk_id as generate_code_chunk_id,
    store_code_chunks_in_chromadb
)


class TestGetCollectionName:
    """Tests for collection name determination."""
    
    def test_markdown_to_docs_collection(self):
        """Test markdown files go to scareverse_docs."""
        assert get_collection_name_from_file_type('markdown') == 'scareverse_docs'
        assert get_collection_name_from_file_type('md') == 'scareverse_docs'
    
    def test_text_files_to_docs_collection(self):
        """Test text files go to scareverse_docs."""
        assert get_collection_name_from_file_type('text') == 'scareverse_docs'
        assert get_collection_name_from_file_type('txt') == 'scareverse_docs'
        assert get_collection_name_from_file_type('rst') == 'scareverse_docs'
        assert get_collection_name_from_file_type('pdf') == 'scareverse_docs'
    
    def test_python_to_code_collection(self):
        """Test Python files go to scareverse_code."""
        assert get_collection_name_from_file_type('python') == 'scareverse_code'
        assert get_collection_name_from_file_type('py') == 'scareverse_code'
    
    def test_javascript_to_code_collection(self):
        """Test JavaScript/TypeScript files go to scareverse_code."""
        assert get_collection_name_from_file_type('javascript') == 'scareverse_code'
        assert get_collection_name_from_file_type('js') == 'scareverse_code'
        assert get_collection_name_from_file_type('typescript') == 'scareverse_code'
        assert get_collection_name_from_file_type('ts') == 'scareverse_code'
    
    def test_other_code_languages_to_code_collection(self):
        """Test other code languages go to scareverse_code."""
        assert get_collection_name_from_file_type('java') == 'scareverse_code'
        assert get_collection_name_from_file_type('go') == 'scareverse_code'
        assert get_collection_name_from_file_type('rust') == 'scareverse_code'
        assert get_collection_name_from_file_type('cpp') == 'scareverse_code'
    
    def test_config_files_to_config_collection(self):
        """Test configuration files go to scareverse_config (fallback logic).
        
        Note: Actual chunks may override this via metadata.target_collection
        set by chunking strategies. This function provides fallback behavior
        when collection_name is not in chunk metadata.
        """
        assert get_collection_name_from_file_type('json') == 'scareverse_config'
        assert get_collection_name_from_file_type('yaml') == 'scareverse_config'
        assert get_collection_name_from_file_type('yml') == 'scareverse_config'
        assert get_collection_name_from_file_type('toml') == 'scareverse_config'
    
    def test_unknown_type_defaults_to_docs(self):
        """Test unknown file types default to scareverse_docs."""
        assert get_collection_name_from_file_type('unknown') == 'scareverse_docs'
        assert get_collection_name_from_file_type('xyz') == 'scareverse_docs'
    
    def test_case_insensitive(self):
        """Test file type matching is case insensitive."""
        assert get_collection_name_from_file_type('PYTHON') == 'scareverse_code'
        assert get_collection_name_from_file_type('Markdown') == 'scareverse_docs'
        assert get_collection_name_from_file_type('JSON') == 'scareverse_config'


class TestLoadChunksFromJSON:
    """Tests for loading chunks from JSON files."""
    
    def test_load_valid_chunks_file(self, temp_chunks_file):
        """Test loading valid chunks from JSON file."""
        chunks = load_chunks_from_json(str(temp_chunks_file))
        
        assert isinstance(chunks, list)
        assert len(chunks) == 2
        assert all('text' in chunk for chunk in chunks)
        assert all('metadata' in chunk for chunk in chunks)
    
    def test_load_file_not_found(self):
        """Test error handling when chunks file doesn't exist."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_chunks_from_json('/nonexistent/chunks.json')
        
        assert 'Chunks file not found' in str(exc_info.value)
    
    def test_load_invalid_json(self, tmp_path):
        """Test error handling for invalid JSON."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{ invalid json }")
        
        with pytest.raises(ValueError) as exc_info:
            load_chunks_from_json(str(invalid_file))
        
        assert 'Invalid JSON' in str(exc_info.value)
    
    def test_load_non_list_json(self, tmp_path):
        """Test error handling when JSON is not a list."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text('{"key": "value"}')
        
        with pytest.raises(ValueError) as exc_info:
            load_chunks_from_json(str(invalid_file))
        
        assert 'must be a list' in str(exc_info.value)
    
    def test_load_chunks_without_text_field(self, tmp_path):
        """Test chunks with 'content' field instead of 'text' (for compatibility)."""
        chunks_data = [
            {"content": "Test content", "metadata": {}}
        ]
        chunks_file = tmp_path / "chunks.json"
        with open(chunks_file, 'w') as f:
            json.dump(chunks_data, f)
        
        # The function expects 'text' but we have 'content'
        # This should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            load_chunks_from_json(str(chunks_file))
        
        # Error should mention text field is required
        assert "text: Field required" in str(exc_info.value) or "missing 'text' field" in str(exc_info.value)
    
    def test_load_chunks_adds_empty_metadata(self, tmp_path):
        """Test that chunks with missing metadata fields raise validation error."""
        chunks_data = [
            {"text": "Test content"}
        ]
        chunks_file = tmp_path / "chunks.json"
        with open(chunks_file, 'w') as f:
            json.dump(chunks_data, f)
        
        # Missing metadata field should raise ValidationError
        with pytest.raises(ValueError) as exc_info:
            load_chunks_from_json(str(chunks_file))
        
        # Should report missing required metadata
        error_str = str(exc_info.value)
        assert "metadata" in error_str.lower() or "Field required" in error_str


class TestLoadCodeChunksFromJSON:
    """Tests for loading code chunks from JSON (generate_code_embeddings_and_store.py)."""
    
    def test_load_valid_code_chunks_file(self, temp_code_chunks_file):
        """Test loading valid code chunks from JSON file."""
        chunks = load_code_chunks_from_json(str(temp_code_chunks_file))
        
        assert isinstance(chunks, list)
        assert len(chunks) == 1
    
    def test_load_code_chunks_file_not_found(self):
        """Test error handling when code chunks file doesn't exist."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_code_chunks_from_json('/nonexistent/chunks.json')
        
        assert 'Chunks file not found' in str(exc_info.value)
    
    def test_load_code_chunks_invalid_json(self, tmp_path):
        """Test error handling for invalid JSON."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{ invalid json }")
        
        with pytest.raises(ValueError) as exc_info:
            load_code_chunks_from_json(str(invalid_file))
        
        assert 'Invalid JSON' in str(exc_info.value)


class TestInitializeEmbeddingModel:
    """Tests for embedding model initialization."""
    
    @patch('app.workflows.generate_embeddings_and_store.embeddings_model_manager.OllamaEmbeddings')
    def test_initialize_mistral_model(self, mock_ollama_class):
        """Test initialization of Mistral embedding model."""
        mock_embeddings = MagicMock()
        mock_ollama_class.return_value = mock_embeddings
        
        result = initialize_embedding_model('mistral', 'http://localhost:11434')
        
        mock_ollama_class.assert_called_once_with(
            model='mistral',
            base_url='http://localhost:11434'
        )
        assert result == mock_embeddings
    
    @patch('app.workflows.generate_embeddings_and_store.embeddings_model_manager.OllamaEmbeddings')
    def test_initialize_different_models(self, mock_ollama_class):
        """Test initialization of different embedding models."""
        mock_embeddings = MagicMock()
        mock_ollama_class.return_value = mock_embeddings
        
        # Test deepseek-coder
        initialize_embedding_model('deepseek-coder')
        assert 'deepseek-coder' in str(mock_ollama_class.call_args)
        
        # Test phi
        initialize_embedding_model('phi')
        assert 'phi' in str(mock_ollama_class.call_args)


class TestInitializeDeepseekEmbeddings:
    """Tests for DeepSeek-Coder embedding initialization."""
    
    @patch('app.workflows.generate_code_embeddings_and_store.OllamaEmbeddings')
    def test_initialize_deepseek_embeddings(self, mock_ollama_class):
        """Test initialization of DeepSeek-Coder embeddings."""
        mock_embeddings = MagicMock()
        mock_ollama_class.return_value = mock_embeddings
        
        result = initialize_deepseek_embeddings('http://localhost:11434')
        
        mock_ollama_class.assert_called_once_with(
            model='deepseek-coder',
            base_url='http://localhost:11434'
        )
        assert result == mock_embeddings


class TestGenerateChunkID:
    """Tests for chunk ID generation."""
    
    def test_generate_chunk_id_deterministic(self):
        """Test that chunk ID is deterministic for same input."""
        chunk_id_1 = generate_chunk_id("test content", "/path/to/file.md")
        chunk_id_2 = generate_chunk_id("test content", "/path/to/file.md")
        
        assert chunk_id_1 == chunk_id_2
    
    def test_generate_chunk_id_different_content(self):
        """Test that different content produces different IDs."""
        chunk_id_1 = generate_chunk_id("content 1", "/path/to/file.md")
        chunk_id_2 = generate_chunk_id("content 2", "/path/to/file.md")
        
        assert chunk_id_1 != chunk_id_2
    
    def test_generate_chunk_id_different_source(self):
        """Test that different source produces different IDs."""
        chunk_id_1 = generate_chunk_id("test content", "/path/file1.md")
        chunk_id_2 = generate_chunk_id("test content", "/path/file2.md")
        
        assert chunk_id_1 != chunk_id_2
    
    def test_generate_chunk_id_format(self):
        """Test that chunk ID is a SHA256 hash."""
        chunk_id = generate_chunk_id("test", "source")
        
        # SHA256 hash is 64 hex characters
        assert len(chunk_id) == 64
        assert all(c in '0123456789abcdef' for c in chunk_id)
    
    def test_generate_chunk_id_matches_expected(self):
        """Test chunk ID matches expected hash."""
        content = "test content/path/to/file.md"
        expected_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        chunk_id = generate_chunk_id("test content", "/path/to/file.md")
        assert chunk_id == expected_hash


class TestGenerateCodeChunkID:
    """Tests for code chunk ID generation."""
    
    def test_generate_code_chunk_id_deterministic(self):
        """Test that code chunk ID is deterministic."""
        chunk_id_1 = generate_code_chunk_id("def test(): pass", "/code.py")
        chunk_id_2 = generate_code_chunk_id("def test(): pass", "/code.py")
        
        assert chunk_id_1 == chunk_id_2
    
    def test_generate_code_chunk_id_different_content(self):
        """Test that different code produces different IDs."""
        chunk_id_1 = generate_code_chunk_id("def func1(): pass", "/code.py")
        chunk_id_2 = generate_code_chunk_id("def func2(): pass", "/code.py")
        
        assert chunk_id_1 != chunk_id_2


class TestStoreChunksInChromaDB:
    """Tests for storing chunks in ChromaDB."""
    
    @patch('app.workflows.generate_embeddings_and_store.embeddings_chromadb_store.Chroma')
    def test_store_chunks_creates_vectorstore(self, mock_chroma_class, mock_ollama_embeddings, mock_chunks_with_text):
        """Test that chunks are stored in ChromaDB."""
        mock_vectorstore = MagicMock()
        mock_chroma_class.from_documents.return_value = mock_vectorstore
        mock_vectorstore._collection = MagicMock()
        mock_vectorstore._collection.count.return_value = 2
        
        result = store_chunks_in_chromadb(
            mock_chunks_with_text,
            mock_ollama_embeddings,
            'scareverse_docs',
            'test_doc_001',
            'markdown',
            '/tmp/vectorstore'
        )
        
        # Verify from_documents was called
        assert mock_chroma_class.from_documents.called
        
        # Verify result contains expected fields
        assert 'collection_name' in result
        assert result['collection_name'] == 'scareverse_docs'
        assert 'new_chunks_ingested' in result
    
    @patch('app.workflows.generate_embeddings_and_store.embeddings_chromadb_store.Chroma')
    def test_store_empty_chunks_list(self, mock_chroma_class, mock_ollama_embeddings):
        """Test handling of empty chunks list."""
        mock_vectorstore = MagicMock()
        mock_vectorstore._collection = MagicMock()
        mock_vectorstore._collection.count.return_value = 0
        mock_chroma_class.return_value = mock_vectorstore
        
        result = store_chunks_in_chromadb(
            [],
            mock_ollama_embeddings,
            'scareverse_docs',
            'test_doc_002',
            'markdown'
        )
        
        # Should still succeed with 0 chunks
        assert 'new_chunks_ingested' in result
        assert result['new_chunks_ingested'] == 0


class TestStoreCodeChunksInChromaDB:
    """Tests for storing code chunks in ChromaDB."""
    
    @patch('app.workflows.generate_code_embeddings_and_store.Chroma')
    def test_store_code_chunks_creates_vectorstore(self, mock_chroma_class, mock_ollama_embeddings, mock_code_chunks):
        """Test that code chunks are stored in ChromaDB."""
        mock_vectorstore = MagicMock()
        mock_chroma_class.from_documents.return_value = mock_vectorstore
        mock_vectorstore._collection = MagicMock()
        mock_vectorstore._collection.count.return_value = 1
        
        result = store_code_chunks_in_chromadb(
            mock_code_chunks,
            mock_ollama_embeddings,
            'test_doc_002',
            '/tmp/vectorstore'
        )
        
        # Verify from_documents was called
        assert mock_chroma_class.from_documents.called
        
        # Verify result
        assert 'collection_name' in result
        assert result['collection_name'] == 'scareverse_code'


class TestStoreCodeChunksInChromaDB:
    """Tests for storing code chunks in ChromaDB."""
    
    @patch('app.workflows.generate_code_embeddings_and_store.Chroma')
    def test_store_code_chunks_creates_vectorstore(self, mock_chroma_class, mock_ollama_embeddings, mock_code_chunks):
        """Test that code chunks are stored in ChromaDB."""
        mock_vectorstore = MagicMock()
        mock_chroma_class.from_documents.return_value = mock_vectorstore
        mock_vectorstore._collection = MagicMock()
        mock_vectorstore._collection.count.return_value = 1
        
        result = store_code_chunks_in_chromadb(
            mock_code_chunks,
            mock_ollama_embeddings,
            'test_doc_002',
            '/tmp/vectorstore'
        )
        
        # Verify from_documents was called
        assert mock_chroma_class.from_documents.called
        
        # Verify result
        assert 'collection_name' in result
        assert result['collection_name'] == 'scareverse_code'


class TestEdgeCasesAndErrorHandling:
    """Tests for edge cases and error handling in workflows."""
    
    def test_load_chunks_with_non_dict_chunk(self, tmp_path):
        """Test error when chunk is not a dictionary."""
        chunks_data = ["not a dict", {"text": "valid"}]
        chunks_file = tmp_path / "invalid_chunks.json"
        with open(chunks_file, 'w') as f:
            json.dump(chunks_data, f)
        
        with pytest.raises(ValueError) as exc_info:
            load_chunks_from_json(str(chunks_file))
        
        assert "must be a dictionary" in str(exc_info.value)
    
    def test_generate_chunk_id_with_unicode(self):
        """Test chunk ID generation with unicode content."""
        chunk_id = generate_chunk_id("Olá, mundo! 你好世界", "/path/file.md")
        
        # Should still generate valid hash
        assert len(chunk_id) == 64
        assert all(c in '0123456789abcdef' for c in chunk_id)
    
    def test_generate_chunk_id_with_empty_strings(self):
        """Test chunk ID generation with empty strings."""
        chunk_id1 = generate_chunk_id("", "")
        chunk_id2 = generate_chunk_id("", "")
        
        # Same empty input should produce same hash
        assert chunk_id1 == chunk_id2
    
    def test_generate_chunk_id_with_special_characters(self):
        """Test chunk ID generation with special characters."""
        special_content = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
        chunk_id = generate_chunk_id(special_content, "/file.txt")
        
        assert len(chunk_id) == 64
    
    @patch('app.workflows.generate_embeddings_and_store.embeddings_chromadb_store.Chroma')
    def test_store_chunks_with_large_batch(self, mock_chroma_class, mock_ollama_embeddings):
        """Test storing a large batch of chunks."""
        mock_vectorstore = MagicMock()
        mock_chroma_class.from_documents.return_value = mock_vectorstore
        mock_vectorstore._collection = MagicMock()
        mock_vectorstore._collection.count.return_value = 100
        
        # Create 100 chunks
        large_batch = [
            {
                "text": f"Content {i}",
                "metadata": {
                    "document_id": "test_large",
                    "source": "/test.md",
                    "file_type": "markdown",
                    "chunk_type": "section",
                    "embedding_model_id": "mistral",
                    "target_collection": "scareverse_docs"
                }
            }
            for i in range(100)
        ]
        
        result = store_chunks_in_chromadb(
            large_batch,
            mock_ollama_embeddings,
            'scareverse_docs',
            'test_large',
            'markdown'
        )
        
        assert result['new_chunks_ingested'] == 100
    
    def test_collection_name_edge_cases(self):
        """Test collection name determination with edge cases."""
        # Empty string defaults to docs
        assert get_collection_name_from_file_type('') == 'scareverse_docs'
        
        # Whitespace and case should be handled by lower()
        # But 'PYTHON ' with trailing space might not match
        assert get_collection_name_from_file_type('python') == 'scareverse_code'
        
        # File extensions with dots
        assert get_collection_name_from_file_type('md') == 'scareverse_docs'
        assert get_collection_name_from_file_type('py') == 'scareverse_code'


class TestCodeChunkIDGeneration:
    """Additional tests for code chunk ID generation."""
    
    def test_code_chunk_id_consistency(self):
        """Test that code chunk IDs are consistent."""
        code1 = "def hello(): print('world')"
        code2 = "def hello(): print('world')"
        
        id1 = generate_code_chunk_id(code1, "/app/main.py")
        id2 = generate_code_chunk_id(code2, "/app/main.py")
        
        assert id1 == id2
    
    def test_code_chunk_id_with_whitespace_differences(self):
        """Test that whitespace differences create different IDs."""
        code1 = "def hello():pass"
        code2 = "def hello(): pass"
        
        id1 = generate_code_chunk_id(code1, "/app/main.py")
        id2 = generate_code_chunk_id(code2, "/app/main.py")
        
        # Different whitespace should produce different IDs
        assert id1 != id2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
