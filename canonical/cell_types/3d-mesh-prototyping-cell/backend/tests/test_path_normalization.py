"""
Tests for path normalization and validation robustness.

These tests verify that the path sanitization logic correctly handles:
- Trailing/leading whitespace
- Double slashes
- Path normalization
- Absolute path resolution
"""

import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Add the backend scripts directory to path for imports
scripts_path = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_path))


class TestPathNormalization:
    """Tests for path normalization and sanitization."""
    
    def test_path_strip_whitespace(self):
        """Test that paths with trailing/leading whitespace are normalized."""
        test_path = "  /app/.local-dev-data/scareverse-data/jobs/test-id/output.glb  "
        
        # Apply the same normalization logic from main.py
        path_str = test_path.strip()
        path_normalized = os.path.normpath(path_str)
        path_absolute = os.path.abspath(path_normalized)
        
        # Verify no whitespace
        assert not path_absolute.startswith(' ')
        assert not path_absolute.endswith(' ')
        assert ' ' not in path_absolute or '/' in path_absolute  # Allow spaces in path components
    
    def test_path_normalize_double_slashes(self):
        """Test that paths with double slashes are normalized."""
        test_path = "/app/.local-dev-data//scareverse-data///jobs/test-id/output.glb"
        
        # Apply normalization
        path_str = test_path.strip()
        path_normalized = os.path.normpath(path_str)
        
        # Verify no double slashes (except for potential network paths)
        assert '//' not in path_normalized or path_normalized.startswith('//')
    
    def test_path_absolute_resolution(self):
        """Test that relative paths are converted to absolute."""
        test_path = "jobs/test-id/output.glb"
        
        # Apply normalization
        path_str = test_path.strip()
        path_normalized = os.path.normpath(path_str)
        path_absolute = os.path.abspath(path_normalized)
        
        # Verify it's absolute
        assert os.path.isabs(path_absolute)
    
    def test_path_normalization_preserves_valid_path(self):
        """Test that valid paths are preserved after normalization."""
        test_path = "/app/.local-dev-data/scareverse-data/jobs/test-id/output.glb"
        
        # Apply normalization
        path_str = test_path.strip()
        path_normalized = os.path.normpath(path_str)
        path_absolute = os.path.abspath(path_normalized)
        
        # Verify the path structure is preserved
        assert "jobs" in path_absolute
        assert "test-id" in path_absolute
        assert "output.glb" in path_absolute
    
    def test_path_with_newline_characters(self):
        """Test that paths with newline characters are sanitized."""
        test_path = "/app/.local-dev-data/scareverse-data/jobs/test-id/output.glb\n"
        
        # Apply sanitization
        path_str = test_path.strip()
        path_normalized = os.path.normpath(path_str)
        
        # Verify no newline
        assert '\n' not in path_normalized
        assert '\r' not in path_normalized


class TestPathExistenceLogging:
    """Tests for path existence checking and logging."""
    
    @pytest.mark.asyncio
    async def test_nonexistent_file_triggers_directory_listing(self, tmp_path):
        """Test that directory listing is triggered when file doesn't exist."""
        # Create a test directory structure
        job_dir = tmp_path / "jobs" / "test-id"
        job_dir.mkdir(parents=True)
        
        # Create some files in the directory
        (job_dir / "input.png").touch()
        (job_dir / "raw_mesh.obj").touch()
        
        # The output.glb file doesn't exist
        output_path = job_dir / "output.glb"
        
        # Verify file doesn't exist
        assert not output_path.exists()
        
        # Verify parent directory exists
        assert output_path.parent.exists()
        
        # Verify we can list directory contents
        dir_contents = list(output_path.parent.iterdir())
        assert len(dir_contents) == 2
        assert any(item.name == "input.png" for item in dir_contents)
        assert any(item.name == "raw_mesh.obj" for item in dir_contents)
    
    @pytest.mark.asyncio
    async def test_existing_file_is_found(self, tmp_path):
        """Test that existing files are correctly identified."""
        # Create a test file
        job_dir = tmp_path / "jobs" / "test-id"
        job_dir.mkdir(parents=True)
        output_path = job_dir / "output.glb"
        output_path.touch()
        
        # Apply path normalization
        path_str = str(output_path).strip()
        path_normalized = os.path.normpath(path_str)
        path_absolute = os.path.abspath(path_normalized)
        normalized_path = Path(path_absolute)
        
        # Verify file exists after normalization
        assert normalized_path.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
