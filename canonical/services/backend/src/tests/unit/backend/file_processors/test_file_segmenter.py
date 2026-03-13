"""
Unit tests for app/file_processors/file_segmenter.py

Tests file segmentation functions for Python and YAML files
to split large files into token-limited chunks while preserving structure.
"""

import pytest
from unittest.mock import Mock, patch


class TestSegmentPythonFile:
    """Test segment_python_file function."""
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_segment_simple_functions(self, mock_count):
        """Test segmenting Python file with simple functions."""
        from app.file_processors.file_segmenter import segment_python_file
        
        mock_count.side_effect = [50, 60]  # Tokens for each segment
        
        code = """
def func1():
    pass

def func2():
    pass
"""
        result = segment_python_file(code, max_tokens=100)
        
        assert len(result) == 2
        assert result[0]["type"] == "function"
        assert result[0]["name"] == "func1"
        assert result[1]["type"] == "function"
        assert result[1]["name"] == "func2"
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_segment_async_functions(self, mock_count):
        """Test segmenting Python file with async functions."""
        from app.file_processors.file_segmenter import segment_python_file
        
        mock_count.side_effect = [50, 60]
        
        code = """
async def async_func1():
    await something()

async def async_func2():
    await something_else()
"""
        result = segment_python_file(code, max_tokens=100)
        
        assert len(result) == 2
        assert result[0]["type"] == "async_function"
        assert result[0]["name"] == "async_func1"
        assert result[1]["type"] == "async_function"
        assert result[1]["name"] == "async_func2"
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_segment_statements(self, mock_count):
        """Test segmenting Python file with statements."""
        from app.file_processors.file_segmenter import segment_python_file
        
        mock_count.side_effect = [10, 20]
        
        code = """
x = 10
y = 20
"""
        result = segment_python_file(code, max_tokens=100)
        
        assert len(result) == 2
        assert result[0]["type"] == "statement"
        assert "line_" in result[0]["name"]
        assert result[1]["type"] == "statement"
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_segment_classes(self, mock_count):
        """Test segmenting Python file with classes."""
        from app.file_processors.file_segmenter import segment_python_file
        
        mock_count.return_value = 50
        
        code = """
class MyClass:
    def method(self):
        pass
"""
        result = segment_python_file(code, max_tokens=100)
        
        assert len(result) >= 1
        assert result[0]["type"] == "class"
        assert result[0]["name"] == "MyClass"
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_segment_warning_large_segment(self, mock_count):
        """Test warning when segment exceeds max tokens."""
        from app.file_processors.file_segmenter import segment_python_file
        
        mock_count.return_value = 500  # Exceeds limit
        
        code = """
def large_function():
    # Lots of code here
    pass
"""
        result = segment_python_file(code, max_tokens=100)
        
        # Should still return the segment with warning
        assert len(result) >= 1
        assert result[0]["tokens"] == 500
    
    def test_segment_syntax_error(self):
        """Test handling syntax errors in Python code."""
        from app.file_processors.file_segmenter import segment_python_file
        
        code = "def invalid syntax"
        result = segment_python_file(code, max_tokens=100)
        
        # Should return full code as unparseable segment
        assert len(result) == 1
        assert result[0]["type"] == "unparseable"
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_segment_empty_file(self, mock_count):
        """Test segmenting empty file."""
        from app.file_processors.file_segmenter import segment_python_file
        
        mock_count.return_value = 0
        
        code = ""
        result = segment_python_file(code, max_tokens=100)
        
        # Should return single module segment
        assert len(result) == 1
        assert result[0]["type"] == "module"


class TestSegmentYamlFile:
    """Test segment_yaml_file function."""
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_segment_yaml_sections(self, mock_count):
        """Test segmenting YAML by top-level keys."""
        from app.file_processors.file_segmenter import segment_yaml_file
        
        mock_count.side_effect = [30, 40]
        
        yaml = """
section1:
  key: value
section2:
  key: value
"""
        result = segment_yaml_file(yaml, max_tokens=100)
        
        assert len(result) >= 1
        assert all("key" in seg for seg in result)
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_segment_yaml_with_actual_parsing(self, mock_count):
        """Test YAML segmentation with actual PyYAML parsing."""
        from app.file_processors.file_segmenter import segment_yaml_file
        
        mock_count.side_effect = [30, 40, 50]
        
        # Valid YAML with clear top-level sections (no indentation)
        yaml = """section1:
  key1: value1
  key2: value2
section2:
  key3: value3
section3:
  key4: value4
"""
        result = segment_yaml_file(yaml, max_tokens=100)
        
        # Should create segments for each section
        assert len(result) >= 3
        # Verify sections are properly identified
        keys = [seg.get("key") for seg in result]
        assert "section1" in keys or "section2" in keys or "section3" in keys
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_segment_yaml_dict_complex(self, mock_count):
        """Test YAML segmentation with complex dictionary structure."""
        from app.file_processors.file_segmenter import segment_yaml_file
        
        # Set up token counts for multiple sections
        mock_count.side_effect = [100] * 10
        
        # YAML with multiple top-level keys
        yaml = """database:
  host: localhost
  port: 5432
server:
  host: 0.0.0.0
  port: 8080
logging:
  level: INFO
  file: app.log
"""
        result = segment_yaml_file(yaml, max_tokens=200)
        
        # Should segment by top-level keys
        assert len(result) >= 1
        # Check that we got section types
        assert any(seg.get("type") == "section" for seg in result)
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_segment_yaml_non_dict(self, mock_count):
        """Test YAML segmentation with non-dict content (list)."""
        from app.file_processors.file_segmenter import segment_yaml_file
        
        mock_count.return_value = 50
        
        # YAML that parses to a list, not a dict
        yaml = """- item1
- item2
- item3
"""
        result = segment_yaml_file(yaml, max_tokens=100)
        
        # Should return full content since it's not a dict
        assert len(result) == 1
        assert result[0]["type"] == "full"
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_segment_yaml_import_error(self, mock_count):
        """Test YAML segmentation when PyYAML is not available."""
        from app.file_processors.file_segmenter import segment_yaml_file
        
        mock_count.return_value = 50
        
        # Use import mocking to simulate PyYAML not available
        with patch.dict('sys.modules', {'yaml': None}):
            import importlib
            import app.file_processors.file_segmenter as segmenter_module
            
            yaml_content = "key: value"
            # This should trigger the ImportError handling
            result = segment_yaml_file(yaml_content, max_tokens=100)
            
            # Should return full file as single segment
            assert len(result) >= 1
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_segment_yaml_parse_error(self, mock_count):
        """Test YAML segmentation with parsing error."""
        from app.file_processors.file_segmenter import segment_yaml_file
        
        mock_count.return_value = 30
        
        # Invalid YAML that will cause parse error
        yaml = """
invalid yaml content
  this is not valid
    ~~~
"""
        result = segment_yaml_file(yaml, max_tokens=100)
        
        # Should return full content as single segment on error
        assert len(result) == 1
        assert result[0]["type"] == "full"
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_segment_yaml_empty(self, mock_count):
        """Test segmenting empty YAML."""
        from app.file_processors.file_segmenter import segment_yaml_file
        
        mock_count.return_value = 0
        
        yaml = ""
        result = segment_yaml_file(yaml, max_tokens=100)
        
        # Should return full file segment
        assert len(result) == 1
        assert result[0]["type"] == "full"


class TestProcessFileForOpenai:
    """Test process_file_for_openai function."""
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    @patch('app.file_processors.file_segmenter.remove_python_comments_and_docstrings')
    def test_process_python_file_small(self, mock_minimize, mock_count):
        """Test processing small Python file."""
        from app.file_processors.file_segmenter import process_file_for_openai
        
        code = 'def hello():\n    print("hi")'
        mock_minimize.return_value = code
        mock_count.return_value = 50  # Under limit
        
        result = process_file_for_openai(code, "test.py", max_tokens=1000, minimize_docs=True)
        
        assert len(result) == 1
        assert result[0]["metadata"]["file_name"] == "test.py"
        assert result[0]["metadata"]["file_type"] == "py"
        assert result[0]["metadata"]["is_minimized"] is True
        assert result[0]["tokens"] == 50
    
    @patch('app.file_processors.file_segmenter.segment_python_file')
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_process_python_file_large(self, mock_count, mock_segment):
        """Test processing large Python file that needs segmentation."""
        from app.file_processors.file_segmenter import process_file_for_openai
        
        code = "a" * 10000
        mock_count.return_value = 5000  # Exceeds limit
        mock_segment.return_value = [
            {"content": "seg1", "type": "function", "name": "func1", "tokens": 2500},
            {"content": "seg2", "type": "function", "name": "func2", "tokens": 2500}
        ]
        
        result = process_file_for_openai(code, "test.py", max_tokens=3000)
        
        assert len(result) == 2
        assert result[0]["metadata"]["segment_index"] == 0
        assert result[1]["metadata"]["segment_index"] == 1
        assert result[0]["metadata"]["total_segments"] == 2
    
    def test_process_file_empty_content(self):
        """Test processing empty file content."""
        from app.file_processors.file_segmenter import process_file_for_openai
        
        with pytest.raises(ValueError, match="File content is empty"):
            process_file_for_openai("", "test.py")
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_process_file_without_minimization(self, mock_count):
        """Test processing without documentation minimization."""
        from app.file_processors.file_segmenter import process_file_for_openai
        
        code = '"""Docstring"""\ndef hello(): pass'
        mock_count.return_value = 50
        
        result = process_file_for_openai(code, "test.py", minimize_docs=False)
        
        assert result[0]["metadata"]["is_minimized"] is False
        # Should contain original content with docstring
        assert '"""Docstring"""' in result[0]["content"]
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    @patch('app.file_processors.file_segmenter.remove_yaml_comments')
    def test_process_yaml_file(self, mock_minimize, mock_count):
        """Test processing YAML file."""
        from app.file_processors.file_segmenter import process_file_for_openai
        
        yaml = "key: value"
        mock_minimize.return_value = yaml
        mock_count.return_value = 10
        
        result = process_file_for_openai(yaml, "config.yml", minimize_docs=True)
        
        assert len(result) == 1
        assert result[0]["metadata"]["file_type"] == "yml"
        mock_minimize.assert_called_once()
    
    @patch('app.file_processors.file_segmenter.segment_yaml_file')
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_process_yaml_file_large(self, mock_count, mock_segment):
        """Test processing large YAML file that needs segmentation."""
        from app.file_processors.file_segmenter import process_file_for_openai
        
        yaml = "key: value\n" * 100
        mock_count.return_value = 5000  # Exceeds limit
        mock_segment.return_value = [
            {"content": "section1", "key": "key1", "tokens": 2500, "type": "section"},
            {"content": "section2", "key": "key2", "tokens": 2500, "type": "section"}
        ]
        
        result = process_file_for_openai(yaml, "config.yaml", max_tokens=3000)
        
        assert len(result) == 2
        assert result[0]["metadata"]["file_type"] == "yaml"
        assert result[0]["metadata"]["segment_type"] == "section"
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_process_generic_file(self, mock_count):
        """Test processing generic file type."""
        from app.file_processors.file_segmenter import process_file_for_openai
        
        content = "generic content"
        mock_count.return_value = 10
        
        result = process_file_for_openai(content, "file.txt")
        
        assert len(result) == 1
        assert result[0]["metadata"]["file_type"] == "txt"
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_process_generic_file_large(self, mock_count):
        """Test processing large generic file that needs simple segmentation."""
        from app.file_processors.file_segmenter import process_file_for_openai
        
        # Create content that will trigger segmentation
        lines = ["Line " + str(i) for i in range(100)]
        content = "\n".join(lines)
        
        # Mock: first call for total, then calls for each line during segmentation
        token_values = [5000]  # Total exceeds limit
        token_values.extend([10] * 100)  # Each line is 10 tokens
        mock_count.side_effect = token_values
        
        result = process_file_for_openai(content, "file.txt", max_tokens=500)
        
        # Should create multiple segments
        assert len(result) > 1
        # Each segment should be a chunk
        assert all(seg["metadata"]["segment_type"] == "chunk" for seg in result)


class TestSimpleSegment:
    """Test _simple_segment helper function."""
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_simple_segment_basic(self, mock_count):
        """Test simple line-based segmentation."""
        from app.file_processors.file_segmenter import _simple_segment
        
        # Each line is 10 tokens
        mock_count.side_effect = [10] * 10
        
        content = "\n".join(["Line " + str(i) for i in range(10)])
        result = _simple_segment(content, max_tokens=30, model="gpt-3.5-turbo")
        
        # Should create multiple chunks to stay under limit
        assert len(result) > 1
        # Each segment should have chunk type
        assert all(seg["type"] == "chunk" for seg in result)
    
    @patch('app.file_processors.file_segmenter.count_tokens')
    def test_simple_segment_single_large_line(self, mock_count):
        """Test simple segmentation with line exceeding limit."""
        from app.file_processors.file_segmenter import _simple_segment
        
        # First line is too large, but should still be included
        mock_count.side_effect = [100, 10, 10]
        
        content = "Very long line\nShort line 1\nShort line 2"
        result = _simple_segment(content, max_tokens=50, model="gpt-3.5-turbo")
        
        # Large line should be in its own chunk
        assert len(result) >= 1
        assert result[0]["tokens"] == 100
