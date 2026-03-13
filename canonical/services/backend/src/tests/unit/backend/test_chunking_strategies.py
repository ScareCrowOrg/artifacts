#!/usr/bin/env python3
"""
Unit Tests for Intelligent Chunking Strategies

Tests for markdown, Python AST-based, and configuration file chunking strategies.
"""

import pytest
from pathlib import Path
from app.workflows.chunking_strategies import (
    chunk_markdown,
    chunk_python_code,
    chunk_configuration_file,
    _clean_markdown_content
)


class TestMarkdownChunking:
    """
    Unit tests for markdown-based semantic chunking strategy.
    
    This test suite covers:
        - Header splitting: Ensures markdown is split into chunks based on header levels (#, ##, ###).
        - Content cleaning: Verifies that excessive whitespace, image syntax, and other markdown artifacts are removed or normalized.
        - Empty content handling: Confirms that the chunking strategy gracefully handles empty markdown files, producing at least one chunk.
    
    Expected behavior:
        - Each chunk should contain cleaned content and associated metadata (document_id, file_type, embedding_model_id, target_collection).
        - The chunking strategy should robustly handle complex markdown structures and edge cases.
    """
    
    def test_chunk_markdown_with_headers(self):
        """Test markdown chunking splits on headers correctly."""
        content = """# Main Title

This is the introduction paragraph.

## Section 1

Content for section 1.

### Subsection 1.1

Details for subsection 1.1.

## Section 2

Content for section 2.
"""
        file_path = Path("/test/document.md")
        document_id = "test_doc_001"
        
        chunks = chunk_markdown(content, file_path, document_id)
        
        # Should produce multiple chunks based on headers
        assert len(chunks) > 0
        
        # Each chunk should have text and metadata
        for chunk in chunks:
            assert "text" in chunk
            assert "metadata" in chunk
            assert chunk["metadata"]["document_id"] == document_id
            assert chunk["metadata"]["file_type"] == "markdown"
            assert chunk["metadata"]["embedding_model_id"] == "mistral"
            assert chunk["metadata"]["target_collection"] == "scareverse_docs"
    
    def test_chunk_markdown_empty_content(self):
        """Test markdown chunking with empty content."""
        content = ""
        file_path = Path("/test/empty.md")
        document_id = "test_doc_002"
        
        chunks = chunk_markdown(content, file_path, document_id)
        
        # Should produce at least one chunk (even if empty)
        assert isinstance(chunks, list)
    
    def test_clean_markdown_content(self):
        """Test markdown content cleaning."""
        dirty_content = """# Title


With   excessive    whitespace


![Image](image.png)

And more content.
"""
        clean = _clean_markdown_content(dirty_content)
        
        # Should remove excessive newlines
        assert "\n\n\n" not in clean
        # Should clean up excessive spaces
        assert "   " not in clean
        # Should remove image syntax but keep alt text
        assert "[Image]" not in clean or "image.png" not in clean


class TestPythonChunking:
    """Tests for Python AST-based chunking."""
    
    def test_chunk_python_with_functions(self):
        """Test Python chunking extracts functions correctly."""
        content = '''"""Module docstring."""

def function1():
    """Function 1 docstring."""
    return "result1"

def function2():
    """Function 2 docstring."""
    return "result2"
'''
        file_path = Path("/test/module.py")
        document_id = "test_doc_003"
        
        code_chunks, doc_chunks = chunk_python_code(content, file_path, document_id)
        
        # Should extract functions as code chunks
        assert len(code_chunks) >= 2
        
        # Should extract docstrings as doc chunks
        assert len(doc_chunks) >= 2  # module docstring + function docstrings
        
        # Check code chunks
        for chunk in code_chunks:
            assert "text" in chunk
            assert "metadata" in chunk
            assert chunk["metadata"]["embedding_model_id"] == "deepseek-coder"
            assert chunk["metadata"]["target_collection"] == "scareverse_code"
        
        # Check doc chunks
        for chunk in doc_chunks:
            assert "text" in chunk
            assert "metadata" in chunk
            assert chunk["metadata"]["embedding_model_id"] == "mistral"
            assert chunk["metadata"]["target_collection"] == "scareverse_docs"
            assert "docstring" in chunk["metadata"]["file_type"]
    
    def test_chunk_python_with_class(self):
        """Test Python chunking extracts classes correctly."""
        content = '''class MyClass:
    """Class docstring."""
    
    def method1(self):
        """Method 1 docstring."""
        pass
    
    def method2(self):
        """Method 2 docstring."""
        pass
'''
        file_path = Path("/test/myclass.py")
        document_id = "test_doc_004"
        
        code_chunks, doc_chunks = chunk_python_code(content, file_path, document_id)
        
        # Should extract class and methods
        assert len(code_chunks) >= 1
        
        # Should extract docstrings
        assert len(doc_chunks) >= 1
    
    def test_chunk_python_invalid_syntax(self):
        """Test Python chunking handles invalid syntax gracefully."""
        content = '''def broken_function(:
    this is not valid python
'''
        file_path = Path("/test/broken.py")
        document_id = "test_doc_005"
        
        code_chunks, doc_chunks = chunk_python_code(content, file_path, document_id)
        
        # Should still produce at least one chunk with parse error metadata
        assert len(code_chunks) >= 1
        assert code_chunks[0]["metadata"]["chunk_type"] == "unparseable"
    
    def test_chunk_python_no_docstrings(self):
        """Test Python chunking with code but no docstrings."""
        content = '''def function_without_docstring():
    return 42

class ClassWithoutDocstring:
    def method(self):
        pass
'''
        file_path = Path("/test/no_docs.py")
        document_id = "test_doc_006"
        
        code_chunks, doc_chunks = chunk_python_code(content, file_path, document_id)
        
        # Should extract code chunks
        assert len(code_chunks) >= 1
        
        # No docstrings to extract
        # doc_chunks might be empty or contain only non-docstring chunks


class TestConfigurationChunking:
    """Tests for configuration file chunking."""
    
    def test_chunk_yaml_content(self):
        """Test YAML chunking splits by top-level keys."""
        content = """key1: value1
key2:
  nested1: value2
  nested2: value3
key3: value4
"""
        file_path = Path("/test/config.yaml")
        document_id = "test_doc_007"
        
        chunks = chunk_configuration_file(content, file_path, document_id, "yaml")
        
        # Should split by top-level keys
        assert len(chunks) >= 1
        
        for chunk in chunks:
            assert "text" in chunk
            assert "metadata" in chunk
            assert chunk["metadata"]["file_type"] == "yaml"
            assert chunk["metadata"]["embedding_model_id"] == "deepseek-coder"
            assert chunk["metadata"]["target_collection"] == "scareverse_code"
    
    def test_chunk_json_content(self):
        """Test JSON chunking splits by top-level keys."""
        content = '''{
    "key1": "value1",
    "key2": {
        "nested": "value2"
    },
    "key3": "value3"
}'''
        file_path = Path("/test/config.json")
        document_id = "test_doc_008"
        
        chunks = chunk_configuration_file(content, file_path, document_id, "json")
        
        # Should split by top-level keys
        assert len(chunks) >= 1
        
        for chunk in chunks:
            assert "text" in chunk
            assert "metadata" in chunk
            assert chunk["metadata"]["file_type"] == "json"
    
    def test_chunk_env_content(self):
        """Test .env file chunking groups related variables."""
        content = """# Database settings
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mydb

# API settings
API_KEY=secret
API_URL=https://api.example.com

# Cache settings
CACHE_ENABLED=true
"""
        file_path = Path("/test/.env")
        document_id = "test_doc_009"
        
        chunks = chunk_configuration_file(content, file_path, document_id, "env")
        
        # Should group by prefix
        assert len(chunks) >= 1
        
        for chunk in chunks:
            assert "text" in chunk
            assert "metadata" in chunk
            assert chunk["metadata"]["file_type"] == "env"
    
    def test_chunk_invalid_yaml(self):
        """Test YAML chunking handles invalid YAML gracefully."""
        content = """this is not
  valid: yaml:
    syntax
"""
        file_path = Path("/test/invalid.yaml")
        document_id = "test_doc_010"
        
        chunks = chunk_configuration_file(content, file_path, document_id, "yaml")
        
        # Should still produce at least one chunk
        assert len(chunks) >= 1
        assert chunks[0]["metadata"]["chunk_type"] == "unparseable"


class TestChunkMetadata:
    """Tests for chunk metadata generation."""
    
    def test_metadata_contains_required_fields(self):
        """Test that all chunks have required metadata fields."""
        content = "# Simple document\n\nWith some content."
        file_path = Path("/test/simple.md")
        document_id = "test_doc_011"
        
        chunks = chunk_markdown(content, file_path, document_id)
        
        required_fields = [
            "document_id",
            "source",
            "file_type",
            "embedding_model_id",
            "target_collection"
        ]
        
        for chunk in chunks:
            metadata = chunk["metadata"]
            for field in required_fields:
                assert field in metadata, f"Missing required field: {field}"
    
    def test_document_id_consistency(self):
        """Test that all chunks from same document share document_id."""
        content = '''def func1():
    """Docstring 1."""
    pass

def func2():
    """Docstring 2."""
    pass
'''
        file_path = Path("/test/functions.py")
        document_id = "test_doc_012"
        
        code_chunks, doc_chunks = chunk_python_code(content, file_path, document_id)
        
        all_chunks = code_chunks + doc_chunks
        
        for chunk in all_chunks:
            assert chunk["metadata"]["document_id"] == document_id


class TestChunkMetadata:
    """Tests for chunk metadata structure."""
    
    def test_metadata_contains_required_fields(self):
        """Test that chunk metadata contains all required fields."""
        content = "# Test\n\nContent"
        chunks = chunk_markdown(content, Path("/test.md"), "test_doc_001")
        
        assert len(chunks) > 0
        metadata = chunks[0]['metadata']
        
        # Required fields (markdown chunks use headers as metadata keys)
        assert 'document_id' in metadata
        assert 'source' in metadata
        assert 'file_type' in metadata
        assert 'embedding_model_id' in metadata
        assert 'target_collection' in metadata
    
    def test_document_id_consistency(self):
        """Test that document_id is consistent across chunks."""
        content = "# H1\n\nC1\n\n## H2\n\nC2"
        chunks = chunk_markdown(content, Path("/test.md"), "test_doc_002")
        
        doc_ids = [c['metadata']['document_id'] for c in chunks]
        assert all(did == "test_doc_002" for did in doc_ids)


class TestPythonChunkingEdgeCases:
    """Additional edge case tests for Python chunking."""
    
    def test_chunk_python_invalid_syntax(self):
        """Test Python chunking with syntax errors falls back gracefully."""
        invalid_python = '''
def broken_function(
    # Missing closing parenthesis
    return "oops"
'''
        file_path = Path("/test/broken.py")
        code_chunks, doc_chunks = chunk_python_code(invalid_python, file_path, "test_syntax_001")
        
        # Should fall back to simple chunking
        assert len(code_chunks) >= 1
        # Fallback creates a chunk without specific function structure
        assert code_chunks[0]['metadata']['file_type'] == 'python'
    
    def test_chunk_python_empty_file(self):
        """Test Python chunking with empty file."""
        empty_python = ""
        file_path = Path("/test/empty.py")
        code_chunks, doc_chunks = chunk_python_code(empty_python, file_path, "test_empty_001")
        
        # Should handle gracefully
        assert isinstance(code_chunks, list)
        assert isinstance(doc_chunks, list)
    
    def test_chunk_python_only_comments(self):
        """Test Python file with only comments and no code."""
        comments_only = '''# Just a comment file
# Another comment
# No actual code here
'''
        file_path = Path("/test/comments.py")
        code_chunks, doc_chunks = chunk_python_code(comments_only, file_path, "test_comments_001")
        
        # Should still create chunks
        assert isinstance(code_chunks, list)
        assert isinstance(doc_chunks, list)


class TestConfigurationChunkingEdgeCases:
    """Edge case tests for configuration file chunking."""
    
    def test_chunk_invalid_yaml(self):
        """Test chunking invalid YAML falls back gracefully."""
        invalid_yaml = '''
key1: value1
key2: [unclosed list
  - item1
  - item2
'''
        file_path = Path("/test/invalid.yaml")
        chunks = chunk_configuration_file(invalid_yaml, file_path, "test_invalid_yaml", "yaml")
        
        # Should fall back to full file content with 'unparseable' chunk type
        assert len(chunks) >= 1
        assert chunks[0]['metadata']['chunk_type'] == 'unparseable'
    
    def test_chunk_invalid_json(self):
        """Test chunking invalid JSON falls back gracefully."""
        invalid_json = '{"key": "value",}'  # Trailing comma
        file_path = Path("/test/invalid.json")
        chunks = chunk_configuration_file(invalid_json, file_path, "test_invalid_json", "json")
        
        # Should fall back to full file content
        assert len(chunks) >= 1
    
    def test_chunk_env_file(self):
        """Test chunking .env file."""
        env_content = '''DATABASE_URL=postgresql://localhost/db
API_KEY=secret123
DEBUG=true
PORT=3000
'''
        file_path = Path("/test/.env")
        chunks = chunk_configuration_file(env_content, file_path, "test_env_001", "env")
        
        # Should chunk .env file
        assert len(chunks) >= 1
        assert all(c['metadata']['file_type'] == 'env' for c in chunks)
    
    def test_chunk_empty_env_file(self):
        """Test chunking empty .env file."""
        env_content = ""
        file_path = Path("/test/.env")
        chunks = chunk_configuration_file(env_content, file_path, "test_empty_env", "env")
        
        # Should handle empty file
        assert isinstance(chunks, list)
    
    def test_chunk_yaml_with_complex_structure(self):
        """Test YAML with nested complex structures."""
        complex_yaml = '''
database:
  host: localhost
  port: 5432
  credentials:
    username: admin
    password: secret
  pools:
    - name: pool1
      size: 10
    - name: pool2
      size: 20
services:
  api:
    enabled: true
    endpoints:
      - /api
      - /api/v2
'''
        file_path = Path("/test/complex.yaml")
        chunks = chunk_configuration_file(complex_yaml, file_path, "test_complex_yaml", "yaml")
        
        # Should parse complex structure
        assert len(chunks) >= 1
        # Should chunk by top-level keys
        chunk_keys = [c['metadata'].get('yaml_key', '') for c in chunks]
        assert 'database' in chunk_keys or 'services' in chunk_keys
    
    def test_chunk_json_with_nested_objects(self):
        """Test JSON with deeply nested objects."""
        nested_json = '''{
    "config": {
        "app": {
            "name": "test",
            "version": "1.0"
        },
        "database": {
            "host": "localhost"
        }
    }
}'''
        file_path = Path("/test/nested.json")
        chunks = chunk_configuration_file(nested_json, file_path, "test_nested_json", "json")
        
        # Should parse nested structure
        assert len(chunks) >= 1
    
    def test_chunk_unknown_config_type(self):
        """Test unknown configuration type falls back."""
        content = "some content"
        file_path = Path("/test/unknown.xyz")
        chunks = chunk_configuration_file(content, file_path, "test_unknown", "xyz")
        
        # Should fall back to full file
        assert len(chunks) >= 1
        assert chunks[0]['metadata']['chunk_type'] == 'full_file'
    
    def test_chunk_yaml_list_content(self):
        """Test YAML with list at root level (not a dict)."""
        list_yaml = '''- item1
- item2
- item3
'''
        file_path = Path("/test/list.yaml")
        chunks = chunk_configuration_file(list_yaml, file_path, "test_yaml_list", "yaml")
        
        # Should fall back to full file when YAML is not a dict
        assert len(chunks) >= 1
        assert chunks[0]['metadata']['chunk_type'] == 'full_file'
    
    def test_chunk_json_array_content(self):
        """Test JSON with array at root level (not an object)."""
        array_json = '[{"id": 1}, {"id": 2}]'
        file_path = Path("/test/array.json")
        chunks = chunk_configuration_file(array_json, file_path, "test_json_array", "json")
        
        # Should fall back to full file when JSON is not a dict
        assert len(chunks) >= 1
        assert chunks[0]['metadata']['chunk_type'] == 'full_file'
    
    def test_chunk_env_empty_lines_only(self):
        """Test .env file with only empty lines and comments."""
        empty_env = '''
# Just comments
# No actual variables

'''
        file_path = Path("/test/empty_comments.env")
        chunks = chunk_configuration_file(empty_env, file_path, "test_env_comments", "env")
        
        # Should handle gracefully
        assert isinstance(chunks, list)
    
    def test_chunk_env_no_prefixes(self):
        """Test .env file with variables without underscores."""
        no_prefix_env = '''SIMPLEVAR=value1
ANOTHERVAR=value2
THIRDVAR=value3
'''
        file_path = Path("/test/no_prefix.env")
        chunks = chunk_configuration_file(no_prefix_env, file_path, "test_env_no_prefix", "env")
        
        # Should chunk with 'general' as group
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk['metadata']['env_group'] in ['general', 'SIMPLEVAR', 'ANOTHERVAR', 'THIRDVAR']


class TestMarkdownLargeChunks:
    """Tests for markdown with large sections that need splitting."""
    
    def test_chunk_markdown_large_section(self):
        """Test markdown chunking splits large sections."""
        # Create content larger than default chunk_size (1000 chars)
        large_content = "A" * 1200
        content = f"""# Large Section

{large_content}

## Another Section

Normal content.
"""
        file_path = Path("/test/large.md")
        document_id = "test_doc_large"
        
        chunks = chunk_markdown(content, file_path, document_id)
        
        # Should split large section into sub-chunks
        assert len(chunks) > 1
        
        # Check that sub-chunks have proper chunk_id format (e.g., "0_0", "0_1")
        chunk_ids = [c['metadata']['chunk_id'] for c in chunks]
        has_subchunk = any('_' in str(cid) for cid in chunk_ids)
        assert has_subchunk, "Large sections should be split into sub-chunks"


class TestPythonNoFunctionsClasses:
    """Tests for Python files without functions or classes."""
    
    def test_chunk_python_no_functions_or_classes(self):
        """Test Python file with no functions or classes (just module-level code)."""
        module_code = '''"""Module docstring."""

# Just some module-level code
x = 42
y = "hello"
result = x + len(y)
print(result)
'''
        file_path = Path("/test/module_level.py")
        document_id = "test_no_funcs"
        
        code_chunks, doc_chunks = chunk_python_code(module_code, file_path, document_id)
        
        # Should create single code chunk for full file
        assert len(code_chunks) == 1
        assert code_chunks[0]['metadata']['chunk_type'] == 'full_file'
        
        # Module docstring should still be extracted
        assert len(doc_chunks) >= 1
        module_docstrings = [c for c in doc_chunks if 'module_docstring' in c['metadata'].get('chunk_type', '')]
        assert len(module_docstrings) >= 1


class TestPythonExtractionErrors:
    """Tests for Python code extraction edge cases."""
    
    def test_chunk_python_extraction_exception(self):
        """Test Python chunking handles extraction errors gracefully."""
        # Python code that might cause extraction issues
        # This is valid Python but has complex AST structure
        complex_code = '''def outer():
    def inner():
        def deepest():
            pass
        return deepest
    return inner

async def async_function():
    async for item in async_generator():
        yield item
'''
        file_path = Path("/test/complex.py")
        document_id = "test_extraction"
        
        code_chunks, doc_chunks = chunk_python_code(complex_code, file_path, document_id)
        
        # Should still create chunks despite complexity
        assert len(code_chunks) >= 1
        assert isinstance(code_chunks, list)
        assert isinstance(doc_chunks, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
