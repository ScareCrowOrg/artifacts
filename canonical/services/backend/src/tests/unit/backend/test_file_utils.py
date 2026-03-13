"""
Unit tests for app/file_utils.py

Tests secure file operation utilities including path validation,
file encoding/decoding, atomic writes, and permission checks.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, mock_open


class TestValidateAndSanitizePath:
    """Test validate_and_sanitize_path function."""
    
    def test_valid_path_within_base(self):
        """Test valid path within base directory."""
        from app.file_utils import validate_and_sanitize_path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            is_valid, sanitized, error = validate_and_sanitize_path(tmpdir, "subdir/file.txt")
            
            assert is_valid is True
            assert error is None
            assert "subdir" in sanitized
    
    def test_path_traversal_attack(self):
        """Test detection of path traversal attack."""
        from app.file_utils import validate_and_sanitize_path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            is_valid, sanitized, error = validate_and_sanitize_path(tmpdir, "../../../etc/passwd")
            
            assert is_valid is False
            assert "Path traversal" in error
    
    def test_null_byte_in_path(self):
        """Test detection of null byte in path."""
        from app.file_utils import validate_and_sanitize_path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            is_valid, sanitized, error = validate_and_sanitize_path(tmpdir, "file\x00.txt")
            
            assert is_valid is False
            assert "null byte" in error.lower()
    
    def test_normalize_path_with_spaces(self):
        """Test path normalization with leading/trailing spaces."""
        from app.file_utils import validate_and_sanitize_path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            is_valid, sanitized, error = validate_and_sanitize_path(tmpdir, "  /file.txt  ")
            
            assert is_valid is True
            # Should strip spaces and leading slashes
    
    def test_exception_handling(self):
        """Test handling of exceptions during validation."""
        from app.file_utils import validate_and_sanitize_path
        
        # Invalid base path
        is_valid, sanitized, error = validate_and_sanitize_path(None, "file.txt")
        
        assert is_valid is False
        assert error is not None


class TestValidateFilenameExtension:
    """Test validate_filename_extension function."""
    
    def test_valid_filename(self):
        """Test valid filename."""
        from app.file_utils import validate_filename_extension
        
        is_valid, error = validate_filename_extension("test.py")
        
        assert is_valid is True
        assert error is None
    
    def test_path_traversal_in_filename(self):
        """Test detection of path traversal in filename."""
        from app.file_utils import validate_filename_extension
        
        is_valid, error = validate_filename_extension("../etc/passwd")
        
        assert is_valid is False
        assert "path traversal" in error.lower()
    
    def test_slash_in_filename(self):
        """Test detection of slashes in filename."""
        from app.file_utils import validate_filename_extension
        
        is_valid, error = validate_filename_extension("dir/file.txt")
        
        assert is_valid is False
    
    def test_empty_filename(self):
        """Test detection of empty filename."""
        from app.file_utils import validate_filename_extension
        
        is_valid, error = validate_filename_extension("")
        
        assert is_valid is False
        assert "empty" in error.lower()
    
    def test_whitespace_filename(self):
        """Test detection of whitespace-only filename."""
        from app.file_utils import validate_filename_extension
        
        is_valid, error = validate_filename_extension("   ")
        
        assert is_valid is False


class TestDecodeBase64Content:
    """Test decode_base64_content function."""
    
    def test_valid_base64(self):
        """Test decoding valid base64 content."""
        from app.file_utils import decode_base64_content
        import base64
        
        content = "Hello, world!"
        encoded = base64.b64encode(content.encode('utf-8')).decode('ascii')
        
        success, decoded, error = decode_base64_content(encoded)
        
        assert success is True
        assert decoded == content
        assert error is None
    
    def test_invalid_base64(self):
        """Test handling of invalid base64."""
        from app.file_utils import decode_base64_content
        
        success, decoded, error = decode_base64_content("not valid base64!!!")
        
        assert success is False
        assert "Invalid base64" in error
    
    def test_non_utf8_content(self):
        """Test handling of non-UTF-8 content."""
        from app.file_utils import decode_base64_content
        import base64
        
        # Binary content that's not valid UTF-8
        binary = b'\xff\xfe\xfd'
        encoded = base64.b64encode(binary).decode('ascii')
        
        success, decoded, error = decode_base64_content(encoded)
        
        assert success is False
        assert "UTF-8" in error
    
    @patch('app.file_utils.MAX_FILE_SIZE', 100)
    def test_file_size_limit(self):
        """Test file size limit enforcement."""
        from app.file_utils import decode_base64_content
        import base64
        
        # Create content larger than limit
        large_content = "a" * 200
        encoded = base64.b64encode(large_content.encode('utf-8')).decode('ascii')
        
        success, decoded, error = decode_base64_content(encoded)
        
        assert success is False
        assert "exceeds maximum" in error


class TestWriteFileAtomically:
    """Test write_file_atomically function."""
    
    def test_write_new_file(self):
        """Test writing new file atomically."""
        from app.file_utils import write_file_atomically
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.txt")
            content = "Test content"
            
            success, error = write_file_atomically(file_path, content)
            
            assert success is True
            assert error is None
            assert os.path.exists(file_path)
            with open(file_path, 'r') as f:
                assert f.read() == content
    
    def test_overwrite_existing_file(self):
        """Test overwriting existing file atomically."""
        from app.file_utils import write_file_atomically
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.txt")
            
            # Create initial file
            with open(file_path, 'w') as f:
                f.write("Initial content")
            
            # Overwrite atomically
            success, error = write_file_atomically(file_path, "New content")
            
            assert success is True
            with open(file_path, 'r') as f:
                assert f.read() == "New content"
    
    def test_create_parent_directories(self):
        """Test automatic creation of parent directories."""
        from app.file_utils import write_file_atomically
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "subdir", "nested", "file.txt")
            
            success, error = write_file_atomically(file_path, "Content")
            
            assert success is True
            assert os.path.exists(file_path)


class TestEnsureDirectoryExists:
    """Test ensure_directory_exists function."""
    
    def test_create_new_directory(self):
        """Test creating new directory."""
        from app.file_utils import ensure_directory_exists
        
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "newdir")
            
            success, error = ensure_directory_exists(new_dir)
            
            assert success is True
            assert os.path.isdir(new_dir)
    
    def test_existing_directory(self):
        """Test with existing directory."""
        from app.file_utils import ensure_directory_exists
        
        with tempfile.TemporaryDirectory() as tmpdir:
            success, error = ensure_directory_exists(tmpdir)
            
            assert success is True
    
    def test_create_nested_directories(self):
        """Test creating nested directories."""
        from app.file_utils import ensure_directory_exists
        
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "a", "b", "c")
            
            success, error = ensure_directory_exists(nested)
            
            assert success is True
            assert os.path.isdir(nested)


class TestCheckFilePermissions:
    """Test check_file_permissions function."""
    
    def test_check_read_permission(self):
        """Test checking read permissions on existing file."""
        from app.file_utils import check_file_permissions
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"content")
            tmp_path = tmp.name
        
        try:
            has_perm, error = check_file_permissions(tmp_path, check_write=False)
            assert has_perm is True
        finally:
            os.unlink(tmp_path)
    
    def test_check_write_permission_existing(self):
        """Test checking write permissions on existing file."""
        from app.file_utils import check_file_permissions
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            has_perm, error = check_file_permissions(tmp_path, check_write=True)
            assert has_perm is True
        finally:
            os.unlink(tmp_path)
    
    def test_check_non_existent_file_read(self):
        """Test checking read permission on non-existent file."""
        from app.file_utils import check_file_permissions
        
        has_perm, error = check_file_permissions("/tmp/nonexistent_file.txt", check_write=False)
        
        assert has_perm is False
        assert "does not exist" in error
    
    def test_check_non_existent_file_write(self):
        """Test checking write permission for new file."""
        from app.file_utils import check_file_permissions
        
        with tempfile.TemporaryDirectory() as tmpdir:
            new_file = os.path.join(tmpdir, "newfile.txt")
            
            has_perm, error = check_file_permissions(new_file, check_write=True)
            
            # Should check parent directory permission
            assert has_perm is True


class TestDeleteFileOrDirectory:
    """Test delete_file_or_directory function."""
    
    def test_delete_file(self):
        """Test deleting a file."""
        from app.file_utils import delete_file_or_directory
        
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        
        success, error = delete_file_or_directory(tmp_path)
        
        assert success is True
        assert not os.path.exists(tmp_path)
    
    def test_delete_directory(self):
        """Test deleting a directory."""
        from app.file_utils import delete_file_or_directory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "to_delete")
            os.makedirs(test_dir)
            
            success, error = delete_file_or_directory(test_dir)
            
            assert success is True
            assert not os.path.exists(test_dir)
    
    def test_delete_non_existent(self):
        """Test deleting non-existent path."""
        from app.file_utils import delete_file_or_directory
        
        success, error = delete_file_or_directory("/tmp/nonexistent_path")
        
        assert success is False
        assert "does not exist" in error
