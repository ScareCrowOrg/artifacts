"""
Unit Tests for Enhanced Search Files (Find) - Issue #1433

Tests path wildcard support in search_files() function.
"""

import pytest
from pathlib import Path
from unittest.mock import patch
from app.mcp.tools import file_tools


@pytest.mark.asyncio
class TestSearchFilesWildcards:
    """Test path wildcard support in search_files()."""
    
    async def test_expand_search_path_wildcards_simple(self, tmp_path):
        """Test simple path without wildcards."""
        (tmp_path / "backend").mkdir()
        
        result = file_tools._expand_search_path_wildcards("backend", tmp_path)
        
        assert len(result) == 1
        assert result[0].name == "backend"
    
    async def test_expand_search_path_wildcards_star(self, tmp_path):
        """Test path with * wildcard."""
        # Create directory structure
        (tmp_path / "backend").mkdir()
        (tmp_path / "frontend").mkdir()
        (tmp_path / "docs").mkdir()
        (tmp_path / "file.txt").write_text("not a dir")  # File (should be excluded)
        
        result = file_tools._expand_search_path_wildcards("*/", tmp_path)
        
        # Should match only directories
        assert len(result) >= 3
        names = [p.name for p in result]
        assert "backend" in names
        assert "frontend" in names
        assert "docs" in names
        assert all(p.is_dir() for p in result)
    
    async def test_expand_search_path_wildcards_nested(self, tmp_path):
        """Test path with nested wildcards."""
        # Create directory structure
        (tmp_path / "src" / "components").mkdir(parents=True)
        (tmp_path / "src" / "utils").mkdir(parents=True)
        (tmp_path / "tests" / "unit").mkdir(parents=True)
        
        result = file_tools._expand_search_path_wildcards("src/*", tmp_path)
        
        # Should match src/components and src/utils
        assert len(result) == 2
        names = [p.name for p in result]
        assert "components" in names
        assert "utils" in names
    
    async def test_expand_search_path_wildcards_doublestar(self, tmp_path):
        """Test path with ** (recursive wildcard)."""
        # Create nested structure
        (tmp_path / "a" / "tests").mkdir(parents=True)
        (tmp_path / "b" / "c" / "tests").mkdir(parents=True)
        (tmp_path / "d" / "tests").mkdir(parents=True)
        
        result = file_tools._expand_search_path_wildcards("**/tests", tmp_path)
        
        # Should find all 'tests' directories
        assert len(result) >= 3
        assert all(p.name == "tests" for p in result)
    
    async def test_expand_search_path_wildcards_security(self, tmp_path):
        """Test that path traversal with wildcards is blocked."""
        with pytest.raises(ValueError, match="Access denied"):
            file_tools._expand_search_path_wildcards("../../*", tmp_path)
    
    async def test_expand_search_path_wildcards_no_matches(self, tmp_path):
        """Test wildcard pattern with no matches."""
        result = file_tools._expand_search_path_wildcards("nonexistent_*", tmp_path)
        
        # Should return empty list (not an error)
        assert result == []
    
    async def test_search_files_with_path_wildcards(self, tmp_path):
        """Test search_files with path wildcards."""
        # Create directory structure
        (tmp_path / "backend" / "app").mkdir(parents=True)
        (tmp_path / "backend" / "tests").mkdir(parents=True)
        (tmp_path / "frontend" / "src").mkdir(parents=True)
        
        # Create Python files
        (tmp_path / "backend" / "app" / "main.py").write_text("content")
        (tmp_path / "backend" / "app" / "utils.py").write_text("content")
        (tmp_path / "backend" / "tests" / "test_main.py").write_text("content")
        (tmp_path / "frontend" / "src" / "app.js").write_text("content")
        
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.search_files({
                "pattern": "*.py",
                "path": "backend/*"  # Wildcard path
            })
        
        # Should find all .py files in backend/app and backend/tests
        assert result["count"] == 3
        matched_files = [m["name"] for m in result["matches"]]
        assert "main.py" in matched_files
        assert "utils.py" in matched_files
        assert "test_main.py" in matched_files
        assert "app.js" not in matched_files
    
    async def test_search_files_wildcards_recursive(self, tmp_path):
        """Test search_files with wildcards and recursive flag."""
        # Create nested structure
        (tmp_path / "src" / "components").mkdir(parents=True)
        (tmp_path / "src" / "utils").mkdir(parents=True)
        
        # Create test files at different levels
        (tmp_path / "src" / "index.js").write_text("content")
        (tmp_path / "src" / "components" / "Button.js").write_text("content")
        (tmp_path / "src" / "utils" / "helpers.js").write_text("content")
        
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            # Recursive search
            result = await file_tools.search_files({
                "pattern": "*.js",
                "path": "src/*",
                "recursive": True
            })
        
        # Should find all .js files recursively
        assert result["count"] >= 2  # At least Button.js and helpers.js
    
    async def test_search_files_wildcards_non_recursive(self, tmp_path):
        """Test search_files with wildcards and non-recursive flag."""
        # Create nested structure
        (tmp_path / "src" / "components" / "nested").mkdir(parents=True)
        
        # Create files
        (tmp_path / "src" / "components" / "top.js").write_text("content")
        (tmp_path / "src" / "components" / "nested" / "deep.js").write_text("content")
        
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            # Non-recursive search
            result = await file_tools.search_files({
                "pattern": "*.js",
                "path": "src/components",
                "recursive": False
            })
        
        # Should only find top-level files
        assert result["count"] == 1
        assert result["matches"][0]["name"] == "top.js"


@pytest.mark.asyncio
class TestSearchFilesEdgeCases:
    """Test edge cases and error handling for search_files."""
    
    async def test_search_files_empty_results(self, tmp_path):
        """Test search with no matches."""
        (tmp_path / "dir").mkdir()
        (tmp_path / "dir" / "file.txt").write_text("content")
        
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.search_files({
                "pattern": "*.py",  # No .py files exist
                "path": "dir"
            })
        
        assert result["count"] == 0
        assert result["matches"] == []
    
    async def test_search_files_path_wildcard_no_matches(self, tmp_path):
        """Test wildcard path with no matching directories."""
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.search_files({
                "pattern": "*.py",
                "path": "nonexistent_*"
            })
        
        # Should return empty results (not error)
        assert result["count"] == 0
        assert result["matches"] == []
    
    async def test_search_files_duplicate_avoidance(self, tmp_path):
        """Test that duplicate files are not returned."""
        # Create overlapping directory structure
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        
        # Create same file in both directories
        (tmp_path / "a" / "shared.py").write_text("content")
        
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            # Search in both directories
            result = await file_tools.search_files({
                "pattern": "*.py",
                "path": "*"  # Matches both 'a' and 'b'
            })
        
        # Each unique file should appear only once
        file_paths = [m["path"] for m in result["matches"]]
        assert len(file_paths) == len(set(file_paths))  # No duplicates
    
    async def test_search_files_security_check_matches(self, tmp_path):
        """Test that matched files outside BASE_DIR are excluded."""
        # This is a defensive test - in normal operation this shouldn't happen,
        # but we want to ensure the security check is in place
        (tmp_path / "safe").mkdir()
        (tmp_path / "safe" / "file.py").write_text("content")
        
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.search_files({
                "pattern": "*.py",
                "path": "safe"
            })
        
        # All results should be within BASE_DIR
        for match in result["matches"]:
            full_path = tmp_path / match["path"]
            assert str(full_path.resolve()).startswith(str(tmp_path))


@pytest.mark.asyncio
class TestSearchFilesCombined:
    """Test combined pattern + path wildcards functionality."""
    
    async def test_pattern_and_path_wildcards(self, tmp_path):
        """Test filename pattern with wildcard path."""
        # Create structure
        (tmp_path / "backend" / "models").mkdir(parents=True)
        (tmp_path / "backend" / "views").mkdir(parents=True)
        (tmp_path / "frontend" / "components").mkdir(parents=True)
        
        # Create test files
        (tmp_path / "backend" / "models" / "test_user.py").write_text("content")
        (tmp_path / "backend" / "views" / "test_home.py").write_text("content")
        (tmp_path / "frontend" / "components" / "test_button.js").write_text("content")
        
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.search_files({
                "pattern": "test_*.py",  # Pattern for test Python files
                "path": "backend/*"  # Wildcard path
            })
        
        # Should find test files in backend/models and backend/views
        assert result["count"] == 2
        matched_names = [m["name"] for m in result["matches"]]
        assert "test_user.py" in matched_names
        assert "test_home.py" in matched_names
        assert "test_button.js" not in matched_names
    
    async def test_recursive_wildcard_pattern(self, tmp_path):
        """Test recursive wildcard in path with filename pattern."""
        # Create deeply nested structure
        (tmp_path / "a" / "b" / "tests").mkdir(parents=True)
        (tmp_path / "c" / "d" / "e" / "tests").mkdir(parents=True)
        
        # Create test files
        (tmp_path / "a" / "b" / "tests" / "test_one.py").write_text("content")
        (tmp_path / "c" / "d" / "e" / "tests" / "test_two.py").write_text("content")
        
        with patch.object(file_tools, 'BASE_DIR', tmp_path):
            result = await file_tools.search_files({
                "pattern": "test_*.py",
                "path": "**/tests"  # Recursive wildcard
            })
        
        # Should find all test files in any 'tests' directory
        assert result["count"] == 2
        matched_names = [m["name"] for m in result["matches"]]
        assert "test_one.py" in matched_names
        assert "test_two.py" in matched_names
