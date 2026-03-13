#!/usr/bin/env python3
"""
Unit Tests for Preprocess and Chunk Workflow

Tests for app/workflows/preprocess_and_chunk.py covering:
- File loading (markdown, Python, PDF, text)
- Text preprocessing
- Intelligent chunking strategies
- JSON output generation
- Error handling and edge cases

Target: 90%+ test coverage
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, mock_open

from app.workflows.preprocess_and_chunk import (
    generate_document_id,
    load_file_content,
    preprocess_text,
    chunk_text_intelligent,
    save_chunks_to_separate_json_files
)
from app.workflows.preprocess_and_chunk.chunker import _is_frontend_js_file


class TestGenerateDocumentID:
    """Tests for document ID generation."""
    
    def test_generate_document_id_returns_string(self):
        """Test that document ID is a string."""
        doc_id = generate_document_id()
        assert isinstance(doc_id, str)
    
    def test_generate_document_id_unique(self):
        """Test that generated IDs are unique."""
        id1 = generate_document_id()
        id2 = generate_document_id()
        assert id1 != id2
    
    def test_generate_document_id_format(self):
        """Test that document ID follows UUID format."""
        doc_id = generate_document_id()
        # UUID format: 8-4-4-4-12 hexadecimal characters
        parts = doc_id.split('-')
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12


class TestLoadFileContent:
    """Tests for file loading functionality."""
    
    def test_load_markdown_file(self, temp_test_file):
        """Test loading markdown file."""
        file_path = temp_test_file['markdown']
        content = load_file_content(file_path, 'markdown')
        
        assert isinstance(content, str)
        assert '# Test Document' in content
        assert 'Section 1' in content
    
    def test_load_python_file(self, temp_test_file):
        """Test loading Python file."""
        file_path = temp_test_file['python']
        content = load_file_content(file_path, 'python')
        
        assert isinstance(content, str)
        assert 'def test_function' in content
        assert 'class TestClass' in content
    
    def test_load_json_file(self, temp_test_file):
        """Test loading JSON file."""
        file_path = temp_test_file['json']
        content = load_file_content(file_path, 'json')
        
        assert isinstance(content, str)
        assert 'key1' in content
    
    def test_load_file_not_found(self):
        """Test error handling when file doesn't exist."""
        file_path = Path('/nonexistent/file.md')
        
        with pytest.raises(FileNotFoundError) as exc_info:
            load_file_content(file_path, 'markdown')
        
        assert 'File not found' in str(exc_info.value)
    
    def test_load_pdf_file_with_pypdf(self, tmp_path, mock_pdf_reader):
        """Test loading PDF file with pypdf."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b'dummy pdf content')
        
        # Mock pypdf module at import time using sys.modules
        mock_pypdf = MagicMock()
        mock_pypdf.PdfReader = MagicMock(return_value=mock_pdf_reader)
        
        with patch.dict('sys.modules', {'pypdf': mock_pypdf}):
            content = load_file_content(pdf_path, 'pdf')
            
            assert isinstance(content, str)
            assert 'PDF page content' in content
    
    def test_load_pdf_file_without_pypdf(self, tmp_path):
        """Test loading PDF falls back to text read if pypdf not available."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_text("Text content")
        
        # Mock the import to raise ImportError
        import sys
        with patch.dict(sys.modules, {'pypdf': None}):
            content = load_file_content(pdf_path, 'pdf')
            assert 'Text content' in content
    
    def test_load_file_unicode_decode_error(self, tmp_path):
        """Test handling of non-UTF8 files."""
        file_path = tmp_path / "binary.dat"
        file_path.write_bytes(b'\x80\x81\x82\x83')  # Invalid UTF-8
        
        with pytest.raises(ValueError) as exc_info:
            load_file_content(file_path, 'text')
        
        assert 'not UTF-8 encoded' in str(exc_info.value)


class TestPreprocessText:
    """Tests for text preprocessing."""
    
    def test_preprocess_normalizes_line_endings(self):
        """Test that line endings are normalized."""
        content = "Line 1\r\nLine 2\rLine 3"
        result = preprocess_text(content)
        
        assert '\r\n' not in result
        assert '\r' not in result
        assert 'Line 1' in result
        assert 'Line 2' in result
        assert 'Line 3' in result
    
    def test_preprocess_removes_excessive_blank_lines(self):
        """Test that excessive blank lines are removed."""
        content = "Line 1\n\n\n\n\nLine 2"
        result = preprocess_text(content)
        
        # Should keep max 2 consecutive blank lines
        assert '\n\n\n\n' not in result
        assert 'Line 1' in result
        assert 'Line 2' in result
    
    def test_preprocess_removes_trailing_whitespace(self):
        """Test that trailing whitespace is removed from lines."""
        content = "Line 1   \nLine 2\t\t\n"
        result = preprocess_text(content)
        
        assert 'Line 1   ' not in result
        assert 'Line 2\t\t' not in result
        lines = result.split('\n')
        assert all(line == line.rstrip() for line in lines)
    
    def test_preprocess_empty_string(self):
        """Test preprocessing empty string."""
        content = ""
        result = preprocess_text(content)
        assert result == ""
    
    def test_preprocess_preserves_content(self):
        """Test that actual content is preserved."""
        content = "Important content\nWith multiple lines\nShould be kept"
        result = preprocess_text(content)
        
        assert 'Important content' in result
        assert 'With multiple lines' in result
        assert 'Should be kept' in result


class TestIsFrontendJSFile:
    """Tests for frontend JS file detection."""
    
    def test_identifies_composable_file(self):
        """Test identification of composable files."""
        path = Path('/project/cockpit-vue/src/composables/useAuth.js')
        assert _is_frontend_js_file(path, 'js') is True
    
    def test_identifies_store_file(self):
        """Test identification of store files."""
        path = Path('/project/cockpit-vue/src/stores/chat.js')
        assert _is_frontend_js_file(path, 'js') is True
    
    def test_identifies_component_file(self):
        """Test identification of component script files."""
        path = Path('/project/cockpit-vue/src/components/Header.js')
        assert _is_frontend_js_file(path, 'js') is True
    
    def test_identifies_cockpit_composable(self):
        """Test identification of cockpit (non-vue) composable files."""
        path = Path('/project/cockpit/src/composables/useUtils.js')
        assert _is_frontend_js_file(path, 'js') is True
    
    def test_non_frontend_file(self):
        """Test that non-frontend files are not identified."""
        path = Path('/project/backend/utils/helpers.js')
        assert _is_frontend_js_file(path, 'js') is False
    
    def test_non_js_file(self):
        """Test that non-JS files return False."""
        path = Path('/project/cockpit-vue/src/composables/useAuth.py')
        assert _is_frontend_js_file(path, 'py') is False


class TestChunkTextIntelligent:
    """Tests for intelligent text chunking."""
    
    def test_chunk_markdown_file(self, tmp_path, mock_file_content):
        """Test chunking markdown files."""
        file_path = tmp_path / "test.md"
        file_path.write_text(mock_file_content['markdown'])
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            mock_file_content['markdown'],
            file_path,
            'markdown',
            'test_doc_001'
        )
        
        assert len(doc_chunks) > 0
        assert len(code_chunks) == 0
        
        # Check chunk structure
        for chunk in doc_chunks:
            assert 'text' in chunk
            assert 'metadata' in chunk
            assert chunk['metadata']['file_type'] == 'markdown'
            assert chunk['metadata']['target_collection'] == 'scareverse_docs'
            assert chunk['metadata']['embedding_model_id'] == 'mistral'
    
    def test_chunk_python_file(self, tmp_path, mock_file_content):
        """Test chunking Python files."""
        file_path = tmp_path / "test.py"
        file_path.write_text(mock_file_content['python'])
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            mock_file_content['python'],
            file_path,
            'python',
            'test_doc_002'
        )
        
        assert len(code_chunks) > 0
        
        # Check code chunks target correct collection
        for chunk in code_chunks:
            assert chunk['metadata']['file_type'] == 'python'
            assert chunk['metadata']['target_collection'] == 'scareverse_code'
            assert chunk['metadata']['embedding_model_id'] == 'deepseek-coder'
    
    def test_chunk_json_file(self, tmp_path, mock_file_content):
        """Test chunking JSON configuration files."""
        file_path = tmp_path / "config.json"
        file_path.write_text(mock_file_content['json'])
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            mock_file_content['json'],
            file_path,
            'json',
            'test_doc_003'
        )
        
        assert len(code_chunks) > 0
        
        # JSON goes to code collection
        for chunk in code_chunks:
            assert chunk['metadata']['file_type'] == 'json'
            assert chunk['metadata']['target_collection'] == 'scareverse_code'
    
    def test_chunk_yaml_file(self, tmp_path, mock_file_content):
        """Test chunking YAML configuration files."""
        file_path = tmp_path / "config.yaml"
        file_path.write_text(mock_file_content['yaml'])
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            mock_file_content['yaml'],
            file_path,
            'yaml',
            'test_doc_004'
        )
        
        assert len(code_chunks) > 0
        
        # YAML is treated as code by chunking_strategies
        # (even though generate_embeddings has it as config)
        for chunk in code_chunks:
            assert chunk['metadata']['file_type'] == 'yaml'
            # The chunking strategy sets it to scareverse_code
            assert chunk['metadata']['target_collection'] == 'scareverse_code'
    
    def test_chunk_vue_file(self, tmp_path):
        """Test chunking Vue SFC files."""
        vue_content = '''<template>
  <div>Test</div>
</template>

<script>
export default {
  name: 'Test'
}
</script>
'''
        file_path = tmp_path / "Test.vue"
        file_path.write_text(vue_content)
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            vue_content,
            file_path,
            'vue',
            'test_doc_005'
        )
        
        assert len(code_chunks) > 0
    
    def test_chunk_generic_code_file(self, tmp_path):
        """Test chunking generic code files (e.g., JS not in frontend)."""
        js_content = '''function test() {
    return "result";
}
'''
        file_path = tmp_path / "utils.js"
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            js_content,
            file_path,
            'js',
            'test_doc_006'
        )
        
        assert len(code_chunks) > 0
        assert code_chunks[0]['metadata']['target_collection'] == 'scareverse_code'
    
    def test_chunk_text_file(self, tmp_path):
        """Test chunking plain text files."""
        text_content = "This is a plain text document.\n" * 50
        file_path = tmp_path / "readme.txt"
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            text_content,
            file_path,
            'txt',
            'test_doc_007'
        )
        
        assert len(doc_chunks) > 0
        assert len(code_chunks) == 0
        assert doc_chunks[0]['metadata']['target_collection'] == 'scareverse_docs'
    
    def test_chunk_unknown_file_type(self, tmp_path):
        """Test chunking unknown file types defaults to docs."""
        content = "Unknown file type content"
        file_path = tmp_path / "file.xyz"
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            content,
            file_path,
            'xyz',
            'test_doc_008'
        )
        
        assert len(doc_chunks) > 0
        assert doc_chunks[0]['metadata']['target_collection'] == 'scareverse_docs'


class TestSaveChunksToSeparateJSONFiles:
    """Tests for saving chunks to JSON files."""
    
    def test_save_both_doc_and_code_chunks(self, tmp_path, mock_chunks, mock_code_chunks):
        """Test saving both doc and code chunks."""
        doc_path, code_path = save_chunks_to_separate_json_files(
            mock_chunks,
            mock_code_chunks,
            tmp_path,
            'test_doc_001'
        )
        
        assert doc_path is not None
        assert code_path is not None
        assert doc_path.exists()
        assert code_path.exists()
        
        # Verify content
        with open(doc_path, 'r') as f:
            saved_doc_chunks = json.load(f)
        assert len(saved_doc_chunks) == len(mock_chunks)
        
        with open(code_path, 'r') as f:
            saved_code_chunks = json.load(f)
        assert len(saved_code_chunks) == len(mock_code_chunks)
    
    def test_save_only_doc_chunks(self, tmp_path, mock_chunks):
        """Test saving only doc chunks."""
        doc_path, code_path = save_chunks_to_separate_json_files(
            mock_chunks,
            [],
            tmp_path,
            'test_doc_002'
        )
        
        assert doc_path is not None
        assert code_path is None
        assert doc_path.exists()
    
    def test_save_only_code_chunks(self, tmp_path, mock_code_chunks):
        """Test saving only code chunks."""
        doc_path, code_path = save_chunks_to_separate_json_files(
            [],
            mock_code_chunks,
            tmp_path,
            'test_doc_003'
        )
        
        assert doc_path is None
        assert code_path is not None
        assert code_path.exists()
    
    def test_save_no_chunks(self, tmp_path):
        """Test saving when no chunks are provided."""
        doc_path, code_path = save_chunks_to_separate_json_files(
            [],
            [],
            tmp_path,
            'test_doc_004'
        )
        
        assert doc_path is None
        assert code_path is None
    
    def test_creates_output_directory(self, tmp_path, mock_chunks):
        """Test that output directory is created if it doesn't exist."""
        output_dir = tmp_path / "new_dir" / "nested"
        
        doc_path, code_path = save_chunks_to_separate_json_files(
            mock_chunks,
            [],
            output_dir,
            'test_doc_005'
        )
        
        assert output_dir.exists()
        assert doc_path is not None
        assert doc_path.exists()
    
    def test_json_format_valid(self, tmp_path, mock_chunks):
        """Test that saved JSON is valid and formatted correctly."""
        doc_path, _ = save_chunks_to_separate_json_files(
            mock_chunks,
            [],
            tmp_path,
            'test_doc_006'
        )
        
        # Should be able to load JSON
        with open(doc_path, 'r') as f:
            loaded_chunks = json.load(f)
        
        assert isinstance(loaded_chunks, list)
        assert len(loaded_chunks) == len(mock_chunks)
        
        # Check structure
        for chunk in loaded_chunks:
            assert 'text' in chunk
            assert 'metadata' in chunk


class TestSaveChunksToJSONFile:
    """Tests for save_chunks_to_json function."""
    
    def test_save_single_chunks_list(self, tmp_path, mock_chunks):
        """Test saving a single list of chunks to JSON."""
        from app.workflows.preprocess_and_chunk import save_chunks_to_json
        
        output_file = save_chunks_to_json(
            mock_chunks,
            tmp_path,
            'test_doc_001'
        )
        
        assert output_file is not None
        assert output_file.exists()
        
        # Verify content
        with open(output_file, 'r') as f:
            saved_chunks = json.load(f)
        assert len(saved_chunks) == len(mock_chunks)
    
    def test_save_chunks_creates_directory(self, tmp_path, mock_chunks):
        """Test that save function creates output directory."""
        from app.workflows.preprocess_and_chunk import save_chunks_to_json
        
        output_dir = tmp_path / "new_dir" / "nested"
        
        output_file = save_chunks_to_json(
            mock_chunks,
            output_dir,
            'test_doc_002'
        )
        
        assert output_dir.exists()
        assert output_file.exists()


class TestFrontendFilePatterns:
    """Additional tests for frontend file detection edge cases."""
    
    def test_frontend_file_with_uppercase_path(self):
        """Test frontend file detection with uppercase in path."""
        path = Path('/Project/COCKPIT-VUE/SRC/COMPOSABLES/useAuth.js')
        assert _is_frontend_js_file(path, 'js') is True
    
    def test_frontend_file_with_mixed_case(self):
        """Test frontend file detection with mixed case."""
        path = Path('/project/Cockpit-Vue/Src/Stores/chat.js')
        assert _is_frontend_js_file(path, 'js') is True
    
    def test_typescript_frontend_file(self):
        """Test TypeScript frontend files are detected."""
        path = Path('/app/cockpit-vue/src/composables/useData.ts')
        assert _is_frontend_js_file(path, 'ts') is True
    
    def test_backend_typescript_file(self):
        """Test backend TypeScript files are not detected as frontend."""
        path = Path('/app/backend/utils/helpers.ts')
        assert _is_frontend_js_file(path, 'ts') is False
    
    def test_non_composables_stores_components(self):
        """Test JS files in other directories are not frontend."""
        path1 = Path('/app/cockpit-vue/src/utils/helpers.js')
        path2 = Path('/app/cockpit-vue/src/lib/logger.js')
        assert _is_frontend_js_file(path1, 'js') is False
        assert _is_frontend_js_file(path2, 'js') is False


class TestChunkTextIntelligentEdgeCases:
    """Additional edge case tests for intelligent chunking."""
    
    def test_chunk_large_markdown_file(self, tmp_path):
        """Test chunking very large markdown file."""
        large_content = "# Header\n\n" + ("Lorem ipsum dolor sit amet. " * 1000)
        file_path = tmp_path / "large.md"
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            large_content,
            file_path,
            'markdown',
            'test_large_001'
        )
        
        # Should split large content into multiple chunks
        assert len(doc_chunks) > 1
        assert all(len(chunk['text']) <= 1500 for chunk in doc_chunks)
    
    def test_chunk_python_with_no_functions(self, tmp_path):
        """Test Python file with only module-level code."""
        py_content = '''"""Module docstring."""
import os
import sys

# Just configuration
DEBUG = True
CONFIG = {"key": "value"}
'''
        file_path = tmp_path / "config.py"
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            py_content,
            file_path,
            'python',
            'test_py_002'
        )
        
        # Should still create chunks
        assert len(code_chunks) >= 1 or len(doc_chunks) >= 1
    
    def test_chunk_empty_file(self, tmp_path):
        """Test chunking empty file."""
        file_path = tmp_path / "empty.md"
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            "",
            file_path,
            'markdown',
            'test_empty_001'
        )
        
        # Empty file should produce empty chunks or minimal chunks
        assert isinstance(doc_chunks, list)
        assert isinstance(code_chunks, list)
    
    def test_chunk_jsx_file(self, tmp_path):
        """Test chunking JSX files (treated as code)."""
        jsx_content = '''import React from 'react';

export function Component() {
    return <div>Hello</div>;
}
'''
        file_path = tmp_path / "Component.jsx"
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            jsx_content,
            file_path,
            'jsx',
            'test_jsx_001'
        )
        
        assert len(code_chunks) > 0
        assert code_chunks[0]['metadata']['target_collection'] == 'scareverse_code'
    
    def test_chunk_rst_file(self, tmp_path):
        """Test chunking reStructuredText files."""
        rst_content = '''
Documentation Title
===================

This is a section of documentation.

Another Section
---------------

More documentation here.
'''
        file_path = tmp_path / "docs.rst"
        
        doc_chunks, code_chunks = chunk_text_intelligent(
            rst_content,
            file_path,
            'rst',
            'test_rst_001'
        )
        
        assert len(doc_chunks) > 0
        assert doc_chunks[0]['metadata']['target_collection'] == 'scareverse_docs'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
