"""
Unit Tests for Enhanced Search Code (Grep) - Issue #1433

Tests regex support and path wildcards in search_code() function.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.mcp.tools import repo_tools


@pytest.mark.asyncio
class TestSearchCodeRegex:
    """Test regex pattern support in search_code()."""
    
    async def test_is_regex_pattern_detection(self):
        """Test detection of regex metacharacters."""
        # Regex patterns
        assert repo_tools._is_regex_pattern("foo|bar") is True
        assert repo_tools._is_regex_pattern("^import") is True
        assert repo_tools._is_regex_pattern("test.*") is True
        assert repo_tools._is_regex_pattern("\\w+Error") is True
        assert repo_tools._is_regex_pattern("(group)") is True
        assert repo_tools._is_regex_pattern("[abc]") is True
        
        # Simple strings (not regex)
        assert repo_tools._is_regex_pattern("simple") is False
        assert repo_tools._is_regex_pattern("TODO") is False
        assert repo_tools._is_regex_pattern("hello world") is False
    
    async def test_validate_regex_pattern_valid(self):
        """Test validation of valid regex patterns."""
        # Should not raise
        repo_tools._validate_regex_pattern("foo|bar")
        repo_tools._validate_regex_pattern("^import")
        repo_tools._validate_regex_pattern("test.*")
        repo_tools._validate_regex_pattern("\\w+")
    
    async def test_validate_regex_pattern_invalid(self):
        """Test validation of invalid regex patterns."""
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            repo_tools._validate_regex_pattern("[invalid")
        
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            repo_tools._validate_regex_pattern("(unclosed")
        
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            repo_tools._validate_regex_pattern("*invalid")
    
    async def test_search_code_with_regex_or(self, tmp_path):
        """Test search with regex OR operator."""
        # Create test files
        (tmp_path / "file1.py").write_text("def foo():\n    pass")
        (tmp_path / "file2.py").write_text("def bar():\n    pass")
        (tmp_path / "file3.py").write_text("def baz():\n    pass")
        
        # Mock BASE_DIR
        with patch.object(repo_tools, 'BASE_DIR', tmp_path):
            result = await repo_tools.search_code({
                "query": "foo|bar",  # Regex OR
                "path": "."
            })
        
        # Should find matches in file1.py and file2.py
        assert result["count"] >= 2
        matched_files = [m["file"] for m in result["matches"]]
        assert any("file1.py" in f for f in matched_files)
        assert any("file2.py" in f for f in matched_files)
    
    async def test_search_code_with_regex_anchor(self, tmp_path):
        """Test search with regex anchor (^)."""
        # Create test file
        content = "import os\nimport sys\n  import re"
        (tmp_path / "test.py").write_text(content)
        
        with patch.object(repo_tools, 'BASE_DIR', tmp_path):
            result = await repo_tools.search_code({
                "query": "^import",  # Anchored to line start
                "path": "test.py"
            })
        
        # Should only match lines starting with "import" (not "  import")
        assert result["count"] == 2


@pytest.mark.asyncio
class TestSearchCodeWildcards:
    """Test path wildcard support in search_code()."""
    
    async def test_expand_path_wildcards_simple(self, tmp_path):
        """Test simple path without wildcards."""
        (tmp_path / "backend").mkdir()
        
        result = repo_tools._expand_path_wildcards("backend", tmp_path)
        
        assert len(result) == 1
        assert result[0].name == "backend"
    
    async def test_expand_path_wildcards_star(self, tmp_path):
        """Test path with * wildcard."""
        # Create directory structure
        (tmp_path / "backend").mkdir()
        (tmp_path / "frontend").mkdir()
        (tmp_path / "docs").mkdir()
        
        result = repo_tools._expand_path_wildcards("*/", tmp_path)
        
        # Should match all three directories
        assert len(result) >= 3
        names = [p.name for p in result]
        assert "backend" in names
        assert "frontend" in names
        assert "docs" in names
    
    async def test_expand_path_wildcards_nested(self, tmp_path):
        """Test path with nested wildcards."""
        # Create directory structure
        (tmp_path / "backend" / "app").mkdir(parents=True)
        (tmp_path / "backend" / "tests").mkdir(parents=True)
        (tmp_path / "frontend" / "src").mkdir(parents=True)
        
        result = repo_tools._expand_path_wildcards("backend/*", tmp_path)
        
        # Should match backend/app and backend/tests
        assert len(result) == 2
        names = [p.name for p in result]
        assert "app" in names
        assert "tests" in names
    
    async def test_expand_path_wildcards_doublestar(self, tmp_path):
        """Test path with ** (recursive wildcard)."""
        # Create nested structure
        (tmp_path / "a" / "b" / "c").mkdir(parents=True)
        (tmp_path / "x" / "y").mkdir(parents=True)
        
        result = repo_tools._expand_path_wildcards("**/c", tmp_path)
        
        # Should find deeply nested 'c'
        assert len(result) >= 1
        assert any(p.name == "c" for p in result)
    
    async def test_expand_path_wildcards_security(self, tmp_path):
        """Test that path traversal with wildcards is blocked."""
        # This should raise ValueError for security
        with pytest.raises(ValueError, match="Access denied"):
            repo_tools._expand_path_wildcards("../../*", tmp_path)
    
    async def test_expand_path_wildcards_no_matches(self, tmp_path):
        """Test wildcard pattern with no matches."""
        result = repo_tools._expand_path_wildcards("nonexistent_*", tmp_path)
        
        # Should return empty list (not an error)
        assert result == []
    
    async def test_search_code_with_path_wildcards(self, tmp_path):
        """Test search_code with path wildcards."""
        # Create directory structure
        (tmp_path / "backend" / "app").mkdir(parents=True)
        (tmp_path / "backend" / "tests").mkdir(parents=True)
        
        # Create files
        (tmp_path / "backend" / "app" / "main.py").write_text("import sys")
        (tmp_path / "backend" / "tests" / "test_main.py").write_text("import pytest")
        
        with patch.object(repo_tools, 'BASE_DIR', tmp_path):
            result = await repo_tools.search_code({
                "query": "import",
                "path": "backend/*"  # Wildcard path
            })
        
        # Should find matches in both directories
        assert result["count"] >= 2


@pytest.mark.asyncio
class TestSearchCodeCombined:
    """Test combined regex + wildcards functionality."""
    
    async def test_regex_and_wildcards_combined(self, tmp_path):
        """Test regex pattern with wildcard path."""
        # Create structure
        (tmp_path / "src" / "models").mkdir(parents=True)
        (tmp_path / "src" / "views").mkdir(parents=True)
        
        # Create files with class definitions
        (tmp_path / "src" / "models" / "user.py").write_text("class User:\n    pass")
        (tmp_path / "src" / "views" / "home.py").write_text("class HomeView:\n    pass")
        (tmp_path / "src" / "views" / "about.py").write_text("def about():\n    pass")
        
        with patch.object(repo_tools, 'BASE_DIR', tmp_path):
            result = await repo_tools.search_code({
                "query": "^class\\s+",  # Regex: lines starting with "class "
                "path": "src/*"  # Wildcard path
            })
        
        # Should find class definitions in both models and views
        assert result["count"] >= 2
        matched_files = [m["file"] for m in result["matches"]]
        assert any("user.py" in f for f in matched_files)
        assert any("home.py" in f for f in matched_files)
        assert not any("about.py" in f for f in matched_files)  # No class definition


@pytest.mark.asyncio
class TestSearchCodeEdgeCases:
    """Test edge cases and error handling."""
    
    async def test_search_code_empty_results(self, tmp_path):
        """Test search with no matches."""
        (tmp_path / "file.txt").write_text("hello world")
        
        with patch.object(repo_tools, 'BASE_DIR', tmp_path):
            result = await repo_tools.search_code({
                "query": "nonexistent_pattern_12345",
                "path": "."
            })
        
        assert result["count"] == 0
        assert result["matches"] == []
        assert result["truncated"] is False
    
    async def test_search_code_path_wildcard_no_matches(self, tmp_path):
        """Test wildcard path with no matching directories."""
        with patch.object(repo_tools, 'BASE_DIR', tmp_path):
            result = await repo_tools.search_code({
                "query": "test",
                "path": "nonexistent_*"
            })
        
        # Should return empty results (not error)
        assert result["count"] == 0
        assert result["matches"] == []
    
    async def test_search_code_max_results_with_wildcards(self, tmp_path):
        """Test max_results limit with wildcard paths."""
        # Create multiple directories with files
        for i in range(5):
            dir_path = tmp_path / f"dir{i}"
            dir_path.mkdir()
            (dir_path / "file.py").write_text("import os\nimport sys")
        
        with patch.object(repo_tools, 'BASE_DIR', tmp_path):
            result = await repo_tools.search_code({
                "query": "import",
                "path": "dir*",
                "max_results": 5
            })
        
        # Should respect max_results limit
        assert result["count"] <= 5
        if result["count"] == 5:
            assert result["truncated"] is True
