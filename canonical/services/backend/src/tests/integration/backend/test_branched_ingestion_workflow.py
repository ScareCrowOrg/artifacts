#!/usr/bin/env python3
"""
Integration Tests for Branched Ingestion Workflow

Tests for the end-to-end ingestion workflow with intelligent chunking
and branched embedding generation.
"""

import pytest
import json
import tempfile
from pathlib import Path
from app.workflows.preprocess_and_chunk import (
    chunk_text_intelligent,
    save_chunks_to_separate_json_files
)


class TestPreprocessAndChunkIntegration:
    """Integration tests for preprocessing and chunking."""
    
    def test_chunk_markdown_file_produces_doc_chunks(self):
        """Test that markdown files produce documentation chunks."""
        content = """# Test Document

This is a test markdown document.

## Section 1

Content for section 1.
"""
        file_path = Path("/test/document.md")
        document_id = "test_integration_001"
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            content, file_path, "md", document_id
        )
        
        # Markdown should produce doc chunks
        assert len(doc_chunks) > 0
        # Should not produce code chunks
        assert len(code_chunks) == 0
        
        # Verify doc chunks target correct collection
        for chunk in doc_chunks:
            assert chunk["metadata"]["target_collection"] == "scareverse_docs"
            assert chunk["metadata"]["embedding_model_id"] == "mistral"
    
    def test_chunk_python_file_produces_both_chunks(self):
        """Test that Python files produce both doc and code chunks."""
        content = '''"""Module docstring."""

def example_function():
    """Function docstring."""
    return "hello world"
'''
        file_path = Path("/test/module.py")
        document_id = "test_integration_002"
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            content, file_path, "py", document_id
        )
        
        # Python should produce both types
        assert len(doc_chunks) > 0  # From docstrings
        assert len(code_chunks) > 0  # From code
        
        # Verify doc chunks
        for chunk in doc_chunks:
            assert chunk["metadata"]["target_collection"] == "scareverse_docs"
            assert chunk["metadata"]["embedding_model_id"] == "mistral"
        
        # Verify code chunks
        for chunk in code_chunks:
            assert chunk["metadata"]["target_collection"] == "scareverse_code"
            assert chunk["metadata"]["embedding_model_id"] == "deepseek-coder"
    
    def test_chunk_config_file_produces_code_chunks(self):
        """Test that config files produce code chunks."""
        content = """database:
  host: localhost
  port: 5432

cache:
  enabled: true
"""
        file_path = Path("/test/config.yaml")
        document_id = "test_integration_003"
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            content, file_path, "yaml", document_id
        )
        
        # Config should produce code chunks
        assert len(code_chunks) > 0
        # Should not produce doc chunks
        assert len(doc_chunks) == 0
        
        # Verify code chunks target correct collection
        for chunk in code_chunks:
            assert chunk["metadata"]["target_collection"] == "scareverse_code"
            assert chunk["metadata"]["embedding_model_id"] == "deepseek-coder"
    
    def test_save_separate_json_files(self):
        """Test saving chunks to separate JSON files."""
        doc_chunks = [
            {
                "content": "Test doc content",
                "metadata": {"type": "doc"}
            }
        ]
        code_chunks = [
            {
                "content": "Test code content",
                "metadata": {"type": "code"}
            }
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            document_id = "test_integration_004"
            
            doc_path, code_path = save_chunks_to_separate_json_files(
                doc_chunks, code_chunks, output_dir, document_id
            )
            
            # Both files should be created
            assert doc_path is not None
            assert code_path is not None
            assert doc_path.exists()
            assert code_path.exists()
            
            # Verify content
            with open(doc_path) as f:
                loaded_doc_chunks = json.load(f)
            assert len(loaded_doc_chunks) == 1
            assert loaded_doc_chunks[0]["content"] == "Test doc content"
            
            with open(code_path) as f:
                loaded_code_chunks = json.load(f)
            assert len(loaded_code_chunks) == 1
            assert loaded_code_chunks[0]["content"] == "Test code content"
    
    def test_save_only_doc_chunks(self):
        """Test saving when only doc chunks exist."""
        doc_chunks = [{"content": "Doc", "metadata": {}}]
        code_chunks = []
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            document_id = "test_integration_005"
            
            doc_path, code_path = save_chunks_to_separate_json_files(
                doc_chunks, code_chunks, output_dir, document_id
            )
            
            assert doc_path is not None and doc_path.exists()
            assert code_path is None
    
    def test_save_only_code_chunks(self):
        """Test saving when only code chunks exist."""
        doc_chunks = []
        code_chunks = [{"content": "Code", "metadata": {}}]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            document_id = "test_integration_006"
            
            doc_path, code_path = save_chunks_to_separate_json_files(
                doc_chunks, code_chunks, output_dir, document_id
            )
            
            assert doc_path is None
            assert code_path is not None and code_path.exists()


class TestBranchedWorkflowIntegration:
    """Integration tests for the branched workflow execution."""
    
    @pytest.mark.skip(reason="Requires full Chroma/Ollama setup")
    def test_doc_embedding_workflow(self):
        """Test documentation embedding workflow (requires Chroma setup)."""
        pass
    
    @pytest.mark.skip(reason="Requires full Chroma/Ollama setup")
    def test_code_embedding_workflow(self):
        """Test code embedding workflow (requires Chroma setup)."""
        pass


class TestDocumentLifecycle:
    """Tests for document lifecycle management (create/update/delete)."""
    
    @pytest.mark.skip(reason="Requires full Chroma/Ollama setup")
    def test_delete_embeddings_from_both_collections(self):
        """Test deletion removes embeddings from both collections (requires Chroma setup)."""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
