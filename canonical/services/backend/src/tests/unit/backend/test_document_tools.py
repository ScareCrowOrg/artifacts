"""
Unit tests for app/document_tools.py

Tests document reading tools for OpenAI Function Calling,
including security validations and error handling.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch


class TestReadLocalDocument:
    """Test read_local_document function."""
    
    @patch('app.document_tools.BASE_DIR')
    def test_read_valid_document(self, mock_base_dir):
        """Test reading a valid document within allowed directories."""
        from app.document_tools import read_local_document
        
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_base_dir.__truediv__ = lambda self, other: Path(tmpdir) / other
            mock_base_dir.resolve.return_value = Path(tmpdir)
            
            # Create test file
            test_file = os.path.join(tmpdir, "docs", "README.md")
            os.makedirs(os.path.dirname(test_file), exist_ok=True)
            with open(test_file, 'w') as f:
                f.write("Test content")
            
            # Mock BASE_DIR properly
            with patch('app.document_tools.BASE_DIR', Path(tmpdir)):
                content = read_local_document("docs/README.md")
                
                assert content == "Test content"
    
    @patch('app.document_tools.BASE_DIR')
    def test_path_traversal_attack(self, mock_base_dir):
        """Test detection of path traversal attack."""
        from app.document_tools import read_local_document
        
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('app.document_tools.BASE_DIR', Path(tmpdir)):
                with pytest.raises(ValueError, match="path traversal"):
                    read_local_document("../../../etc/passwd")
    
    @patch('app.document_tools.BASE_DIR')
    def test_file_outside_allowed_dirs(self, mock_base_dir):
        """Test rejection of file outside allowed directories."""
        from app.document_tools import read_local_document
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file outside allowed dirs
            test_file = os.path.join(tmpdir, "forbidden", "file.txt")
            os.makedirs(os.path.dirname(test_file), exist_ok=True)
            with open(test_file, 'w') as f:
                f.write("Secret")
            
            with patch('app.document_tools.BASE_DIR', Path(tmpdir)):
                with pytest.raises(ValueError, match="not in allowed directories"):
                    read_local_document("forbidden/file.txt")
    
    @patch('app.document_tools.BASE_DIR')
    def test_file_not_found(self, mock_base_dir):
        """Test handling of non-existent file."""
        from app.document_tools import read_local_document
        
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('app.document_tools.BASE_DIR', Path(tmpdir)):
                with pytest.raises(FileNotFoundError):
                    read_local_document("docs/nonexistent.md")
    
    @patch('app.document_tools.BASE_DIR')
    def test_directory_instead_of_file(self, mock_base_dir):
        """Test rejection when path is a directory."""
        from app.document_tools import read_local_document
        
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = os.path.join(tmpdir, "docs")
            os.makedirs(dir_path)
            
            with patch('app.document_tools.BASE_DIR', Path(tmpdir)):
                with pytest.raises(ValueError, match="not a file"):
                    read_local_document("docs")
    
    @patch('app.document_tools.BASE_DIR')
    @patch('app.document_tools.MAX_FILE_SIZE_BYTES', 100)
    def test_file_too_large(self, mock_base_dir):
        """Test rejection of file exceeding size limit."""
        from app.document_tools import read_local_document
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "docs", "large.txt")
            os.makedirs(os.path.dirname(test_file), exist_ok=True)
            with open(test_file, 'w') as f:
                f.write("x" * 200)  # Exceeds 100 byte limit
            
            with patch('app.document_tools.BASE_DIR', Path(tmpdir)):
                with pytest.raises(ValueError, match="too large"):
                    read_local_document("docs/large.txt")
    
    @patch('app.document_tools.BASE_DIR')
    def test_read_utf8_file(self, mock_base_dir):
        """Test reading UTF-8 encoded file."""
        from app.document_tools import read_local_document
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "docs", "utf8.txt")
            os.makedirs(os.path.dirname(test_file), exist_ok=True)
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write("Hello 世界")
            
            with patch('app.document_tools.BASE_DIR', Path(tmpdir)):
                content = read_local_document("docs/utf8.txt")
                
                assert "世界" in content
    
    @patch('app.document_tools.BASE_DIR')
    def test_read_latin1_fallback(self, mock_base_dir):
        """Test fallback to latin-1 encoding."""
        from app.document_tools import read_local_document
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "docs", "latin1.txt")
            os.makedirs(os.path.dirname(test_file), exist_ok=True)
            # Write latin-1 content
            with open(test_file, 'wb') as f:
                f.write(b'\xe9\xe0')  # Latin-1 accented chars
            
            with patch('app.document_tools.BASE_DIR', Path(tmpdir)):
                content = read_local_document("docs/latin1.txt")
                
                # Should read successfully with fallback
                assert isinstance(content, str)


class TestGetReadDocumentToolDefinition:
    """Test get_read_document_tool_definition function."""
    
    def test_tool_definition_structure(self):
        """Test that tool definition has correct structure."""
        from app.document_tools import get_read_document_tool_definition
        
        tool_def = get_read_document_tool_definition()
        
        assert tool_def["type"] == "function"
        assert "function" in tool_def
        assert tool_def["function"]["name"] == "read_local_document"
        assert "description" in tool_def["function"]
        assert "parameters" in tool_def["function"]
    
    def test_tool_parameters(self):
        """Test tool parameters definition."""
        from app.document_tools import get_read_document_tool_definition
        
        tool_def = get_read_document_tool_definition()
        params = tool_def["function"]["parameters"]
        
        assert params["type"] == "object"
        assert "file_path" in params["properties"]
        assert "file_path" in params["required"]
    
    def test_tool_description_informative(self):
        """Test that tool description is informative."""
        from app.document_tools import get_read_document_tool_definition
        
        tool_def = get_read_document_tool_definition()
        description = tool_def["function"]["description"]
        
        assert len(description) > 50  # Should be detailed
        assert "read" in description.lower()
        assert "document" in description.lower()


class TestExecuteToolCall:
    """Test execute_tool_call function."""
    
    @patch('app.document_tools.read_local_document')
    def test_execute_read_document(self, mock_read):
        """Test executing read_local_document tool."""
        from app.document_tools import execute_tool_call
        
        mock_read.return_value = "Document content"
        
        result = execute_tool_call("read_local_document", {"file_path": "docs/README.md"})
        
        assert result == "Document content"
        mock_read.assert_called_once_with("docs/README.md")
    
    def test_execute_missing_argument(self):
        """Test execution with missing required argument."""
        from app.document_tools import execute_tool_call
        
        with pytest.raises(ValueError, match="Missing required argument"):
            execute_tool_call("read_local_document", {})
    
    def test_execute_unknown_tool(self):
        """Test execution of unknown tool."""
        from app.document_tools import execute_tool_call
        
        with pytest.raises(ValueError, match="Unknown tool"):
            execute_tool_call("unknown_tool", {})
    
    @patch('app.document_tools.read_local_document')
    def test_execute_tool_error_handling(self, mock_read):
        """Test error handling during tool execution."""
        from app.document_tools import execute_tool_call
        
        mock_read.side_effect = FileNotFoundError("File not found")
        
        result = execute_tool_call("read_local_document", {"file_path": "missing.txt"})
        
        # Should return error message as string
        assert "Error reading document" in result
        assert "File not found" in result


class TestAllowedDirectories:
    """Test ALLOWED_DOCUMENT_DIRS configuration."""
    
    def test_allowed_dirs_defined(self):
        """Test that allowed directories are defined."""
        from app.document_tools import ALLOWED_DOCUMENT_DIRS
        
        assert isinstance(ALLOWED_DOCUMENT_DIRS, list)
        assert len(ALLOWED_DOCUMENT_DIRS) > 0
    
    def test_allowed_dirs_include_common(self):
        """Test that common directories are included."""
        from app.document_tools import ALLOWED_DOCUMENT_DIRS
        
        # Should include common doc/code directories
        dirs_str = str(ALLOWED_DOCUMENT_DIRS).lower()
        assert any(d in dirs_str for d in ['docs', 'backend', 'app'])


class TestMaxFileSize:
    """Test MAX_FILE_SIZE_BYTES configuration."""
    
    def test_max_file_size_defined(self):
        """Test that max file size is defined."""
        from app.document_tools import MAX_FILE_SIZE_BYTES
        
        assert isinstance(MAX_FILE_SIZE_BYTES, int)
        assert MAX_FILE_SIZE_BYTES > 0
    
    def test_max_file_size_reasonable(self):
        """Test that max file size is reasonable."""
        from app.document_tools import MAX_FILE_SIZE_BYTES
        
        # Should be at least 1MB, at most 100MB
        assert 1024 * 1024 <= MAX_FILE_SIZE_BYTES <= 100 * 1024 * 1024
