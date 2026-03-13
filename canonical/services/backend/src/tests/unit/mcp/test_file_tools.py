"""
Unit Tests for MCP File Tools

Tests for file system operations tools.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.mcp.tools import file_tools


@pytest.mark.asyncio
class TestFileTools:
    """Test cases for file system tools."""
    
    async def test_list_directory_basic(self, tmp_path):
        """Test basic directory listing."""
        # Create test files
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.py").write_text("content2")
        (tmp_path / "subdir").mkdir()
        
        # Mock BASE_DIR
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.list_directory({"path": "."})
        
        assert "items" in result
        assert result["count"] == 3
        
        # Check that files and dirs are listed
        names = [item["name"] for item in result["items"]]
        assert "file1.txt" in names
        assert "file2.py" in names
        assert "subdir" in names
    
    async def test_list_directory_hidden_files(self, tmp_path):
        """Test directory listing with hidden files."""
        # Create test files
        (tmp_path / "visible.txt").write_text("visible")
        (tmp_path / ".hidden").write_text("hidden")
        
        # Mock BASE_DIR
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            # Without hidden files
            result1 = await file_tools.list_directory({
                "path": ".",
                "include_hidden": False
            })
            
            # With hidden files
            result2 = await file_tools.list_directory({
                "path": ".",
                "include_hidden": True
            })
        
        names1 = [item["name"] for item in result1["items"]]
        names2 = [item["name"] for item in result2["items"]]
        
        assert ".hidden" not in names1
        assert ".hidden" in names2
    
    async def test_list_directory_security(self, tmp_path):
        """Test that listing outside project directory is blocked."""
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            with pytest.raises(ValueError, match="Access denied"):
                await file_tools.list_directory({"path": "../.."})
    
    async def test_read_file_basic(self, tmp_path):
        """Test basic file reading."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_content = "Hello, world!\nLine 2"
        test_file.write_text(test_content)
        
        # Mock BASE_DIR
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.read_file({"path": "test.txt"})
        
        assert result["content"] == test_content
        assert result["lines"] == 2
        assert "size" in result
    
    async def test_read_file_not_found(self, tmp_path):
        """Test reading non-existent file."""
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            with pytest.raises(FileNotFoundError):
                await file_tools.read_file({"path": "nonexistent.txt"})
    
    async def test_read_file_security(self, tmp_path):
        """Test that reading outside project directory is blocked."""
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            with pytest.raises(ValueError, match="Access denied"):
                await file_tools.read_file({"path": "../../etc/passwd"})
    
    async def test_write_file_basic(self, tmp_path):
        """Test basic file writing."""
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.write_file({
                "path": "new_file.txt",
                "content": "New content",
                "create_dirs": True
            })
        
        assert result["lines"] == 1
        assert (tmp_path / "new_file.txt").exists()
        assert (tmp_path / "new_file.txt").read_text() == "New content"
    
    async def test_write_file_create_dirs(self, tmp_path):
        """Test writing file with directory creation."""
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.write_file({
                "path": "subdir/nested/file.txt",
                "content": "Nested content",
                "create_dirs": True
            })
        
        assert (tmp_path / "subdir" / "nested" / "file.txt").exists()
    
    async def test_write_file_security(self, tmp_path):
        """Test that writing outside project directory is blocked."""
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            with pytest.raises(ValueError, match="Access denied"):
                await file_tools.write_file({
                    "path": "../../tmp/malicious.txt",
                    "content": "bad"
                })
    
    async def test_create_directory_basic(self, tmp_path):
        """Test basic directory creation."""
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.create_directory({
                "path": "new_dir",
                "parents": True
            })
        
        assert result["created"] is True
        assert (tmp_path / "new_dir").exists()
        assert (tmp_path / "new_dir").is_dir()
    
    async def test_create_directory_with_parents(self, tmp_path):
        """Test directory creation with parent directories."""
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.create_directory({
                "path": "parent/child/grandchild",
                "parents": True
            })
        
        assert (tmp_path / "parent" / "child" / "grandchild").exists()
    
    async def test_create_directory_already_exists(self, tmp_path):
        """Test creating directory that already exists."""
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()
        
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            with pytest.raises(ValueError, match="already exists"):
                await file_tools.create_directory({
                    "path": "existing",
                    "parents": True
                })
    
    async def test_search_files_basic(self, tmp_path):
        """Test basic file search."""
        # Create test files
        (tmp_path / "test1.py").write_text("python")
        (tmp_path / "test2.py").write_text("python")
        (tmp_path / "test.txt").write_text("text")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "test3.py").write_text("python")
        
        # Mock BASE_DIR
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.search_files({
                "pattern": "*.py",
                "path": ".",
                "recursive": True
            })
        
        assert result["count"] == 3
        assert len(result["matches"]) == 3
        
        # Check all matches are .py files
        for match in result["matches"]:
            assert match["name"].endswith(".py")
    
    async def test_search_files_non_recursive(self, tmp_path):
        """Test non-recursive file search."""
        # Create test files
        (tmp_path / "root.py").write_text("python")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.py").write_text("python")
        
        # Mock BASE_DIR
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.search_files({
                "pattern": "*.py",
                "path": ".",
                "recursive": False
            })
        
        assert result["count"] == 1
        assert result["matches"][0]["name"] == "root.py"


class TestFileToolsRegistration:
    """Test file tools registration."""
    
    def test_register_all_tools(self):
        """Test that all file tools are registered."""
        from app.mcp import MCPServer
        
        server = MCPServer()
        file_tools.register(server)
        
        # Check that all expected tools are registered
        expected_tools = [
            "list_directory",
            "read_file",
            "write_file",
            "create_directory",
            "search_files"
        ]
        
        for tool_name in expected_tools:
            assert tool_name in server.tools
            assert server.tools[tool_name].name == tool_name
        
        # Check category
        assert "filesystem" in server.tool_categories
        assert len(server.tool_categories["filesystem"]) == 5


@pytest.mark.asyncio
class TestFileToolsEnhancements:
    """Test cases for enhanced file tools (Issue #1383)."""
    
    async def test_read_file_with_line_numbers(self, tmp_path):
        """Test reading file with line numbers."""
        # Create test file
        test_file = tmp_path / "test.py"
        test_content = "import os\nfrom pathlib import Path\n\ndef main():\n    pass"
        test_file.write_text(test_content)
        
        # Mock BASE_DIR
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.read_file({
                "path": "test.py",
                "line_numbers": True
            })
        
        # Check that content has line numbers
        expected_lines = [
            "1: import os",
            "2: from pathlib import Path",
            "3: ",
            "4: def main():",
            "5:     pass"
        ]
        assert result["content"] == "\n".join(expected_lines)
        assert result["line_numbers"] is True
    
    async def test_read_file_multiple_files(self, tmp_path):
        """Test reading multiple files at once."""
        # Create test files
        (tmp_path / "file1.txt").write_text("Content 1")
        (tmp_path / "file2.txt").write_text("Content 2")
        (tmp_path / "file3.txt").write_text("Content 3")
        
        # Mock BASE_DIR
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.read_file({
                "paths": "file1.txt,file2.txt,file3.txt"
            })
        
        # Check multi-file response format
        assert "files" in result
        assert "count" in result
        assert result["count"] == 3
        
        # Check each file
        paths = [f["path"] for f in result["files"]]
        assert "file1.txt" in paths
        assert "file2.txt" in paths
        assert "file3.txt" in paths
        
        # Check contents
        for file_data in result["files"]:
            if file_data["path"] == "file1.txt":
                assert file_data["content"] == "Content 1"
            elif file_data["path"] == "file2.txt":
                assert file_data["content"] == "Content 2"
            elif file_data["path"] == "file3.txt":
                assert file_data["content"] == "Content 3"
    
    async def test_read_file_multiple_files_with_line_numbers(self, tmp_path):
        """Test reading multiple files with line numbers."""
        # Create test files
        (tmp_path / "file1.py").write_text("import os\nimport sys")
        (tmp_path / "file2.py").write_text("def test():\n    pass")
        
        # Mock BASE_DIR
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.read_file({
                "paths": "file1.py,file2.py",
                "line_numbers": True
            })
        
        assert result["count"] == 2
        
        # Check line numbers in content
        for file_data in result["files"]:
            assert file_data["line_numbers"] is True
            # Content should have line numbers
            assert file_data["content"].startswith("1: ")
    
    async def test_read_file_multiple_files_limit(self, tmp_path):
        """Test that reading too many files is rejected."""
        # Create 15 test files
        for i in range(15):
            (tmp_path / f"file{i}.txt").write_text(f"Content {i}")
        
        # Mock BASE_DIR
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            paths = ",".join([f"file{i}.txt" for i in range(15)])
            with pytest.raises(ValueError, match="Too many files"):
                await file_tools.read_file({"paths": paths})
    
    async def test_read_file_snippet_basic(self, tmp_path):
        """Test reading a snippet from a file."""
        # Create test file with multiple lines
        test_file = tmp_path / "config.py"
        lines = [
            "# Configuration",
            "DEBUG = False",
            "LOG_LEVEL = 'INFO'",
            "DATABASE_URL = 'sqlite:///db.sqlite3'",
            "SECRET_KEY = 'secret'",
            "# End of config"
        ]
        test_file.write_text("\n".join(lines))
        
        # Mock BASE_DIR
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.read_file_snippet({
                "path": "config.py",
                "start_line": 2,
                "end_line": 3
            })
        
        # Check snippet content
        expected_content = "DEBUG = False\nLOG_LEVEL = 'INFO'"
        assert result["content"] == expected_content
        assert result["start_line"] == 2
        assert result["end_line"] == 3
        assert result["lines"] == 2
        assert result["total_file_lines"] == 6
    
    async def test_read_file_snippet_with_context(self, tmp_path):
        """Test reading a snippet with context lines."""
        # Create test file
        test_file = tmp_path / "code.py"
        lines = [
            "line 1",
            "line 2",
            "line 3",  # Target
            "line 4",  # Target
            "line 5",
            "line 6"
        ]
        test_file.write_text("\n".join(lines))
        
        # Mock BASE_DIR
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.read_file_snippet({
                "path": "code.py",
                "start_line": 3,
                "end_line": 4,
                "context_lines": 1
            })
        
        # Should include 1 line before and 1 line after
        expected_content = "line 2\nline 3\nline 4\nline 5"
        assert result["content"] == expected_content
        assert result["actual_start"] == 2
        assert result["actual_end"] == 5
        assert result["lines"] == 4
    
    async def test_read_file_snippet_invalid_range(self, tmp_path):
        """Test reading snippet with invalid line range."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("line 1\nline 2\nline 3")
        
        # Mock BASE_DIR
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            # start_line > end_line
            with pytest.raises(ValueError, match="start_line must be <= end_line"):
                await file_tools.read_file_snippet({
                    "path": "test.txt",
                    "start_line": 5,
                    "end_line": 2
                })
            
            # start_line exceeds file length
            with pytest.raises(ValueError, match="exceeds file length"):
                await file_tools.read_file_snippet({
                    "path": "test.txt",
                    "start_line": 10,
                    "end_line": 11
                })
    
    async def test_read_file_snippet_security(self, tmp_path):
        """Test that snippet reading respects security boundaries."""
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            with pytest.raises(ValueError, match="Access denied"):
                await file_tools.read_file_snippet({
                    "path": "../../etc/passwd",
                    "start_line": 1,
                    "end_line": 5
                })
    
    async def test_read_file_backward_compatibility(self, tmp_path):
        """Test that single file reading still works (backward compatibility)."""
        # Create test file
        test_file = tmp_path / "legacy.txt"
        test_file.write_text("Legacy content")
        
        # Mock BASE_DIR
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            # Old API: single path parameter
            result = await file_tools.read_file({"path": "legacy.txt"})
        
        # Should return single file format (not array)
        assert "content" in result
        assert "files" not in result
        assert result["content"] == "Legacy content"
    
    async def test_read_file_snippet_append_mode(self, tmp_path):
        """Test reading snippet in append mode (start_line = total_lines + 1)."""
        # Create test file with 3 lines
        test_file = tmp_path / "append_test.txt"
        lines = ["line 1", "line 2", "line 3"]
        test_file.write_text("\n".join(lines))
        
        # Mock BASE_DIR
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            # Request line 4 (after end of file) - should return empty content
            result = await file_tools.read_file_snippet({
                "path": "append_test.txt",
                "start_line": 4,
                "end_line": 4
            })
        
        # Check append mode response
        assert result["content"] == ""
        assert result["lines"] == 0
        assert result["total_file_lines"] == 3
        assert result["start_line"] == 4
        assert result["end_line"] == 4
        assert result["append_mode"] is True
    
    async def test_read_file_snippet_append_mode_multiple_lines(self, tmp_path):
        """Test append mode with multiple new lines."""
        # Create test file with 2 lines
        test_file = tmp_path / "append_multi.txt"
        test_file.write_text("line 1\nline 2")
        
        # Mock BASE_DIR
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            # Request lines 3-5 (all after end of file)
            result = await file_tools.read_file_snippet({
                "path": "append_multi.txt",
                "start_line": 3,
                "end_line": 5
            })
        
        # Check append mode response
        assert result["content"] == ""
        assert result["lines"] == 0
        assert result["total_file_lines"] == 2
        assert result["append_mode"] is True
    
    async def test_read_file_snippet_reject_beyond_append(self, tmp_path):
        """Test that line numbers beyond append position are still rejected."""
        # Create test file with 2 lines
        test_file = tmp_path / "beyond_test.txt"
        test_file.write_text("line 1\nline 2")
        
        # Mock BASE_DIR
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            # Request line 4 (skipping line 3) - should fail
            with pytest.raises(ValueError, match="exceeds file length"):
                await file_tools.read_file_snippet({
                    "path": "beyond_test.txt",
                    "start_line": 4,
                    "end_line": 4
                })
    
    async def test_read_file_snippet_empty_file_append(self, tmp_path):
        """Test append mode on an empty file."""
        # Create empty file
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")
        
        # Mock BASE_DIR
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            # Request line 1 on empty file (0 lines)
            result = await file_tools.read_file_snippet({
                "path": "empty.txt",
                "start_line": 1,
                "end_line": 1
            })
        
        # Check append mode response
        assert result["content"] == ""
        assert result["lines"] == 0
        assert result["total_file_lines"] == 0
        assert result["append_mode"] is True

