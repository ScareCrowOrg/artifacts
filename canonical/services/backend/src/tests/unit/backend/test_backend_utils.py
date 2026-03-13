"""
Unit tests for backend utility modules.

This test file covers all modularized utility functions from backend/utils/
to ensure 90% test coverage as per RULESET.md Rule 3.1.
"""

import pytest
import os
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# Import all utility functions
from utils import (
    # File utilities
    ensure_directory_exists,
    get_file_size,
    get_file_extension,
    get_mime_type,
    is_text_file,
    read_file_content,
    write_file_content,
    list_files_in_directory,
    calculate_file_hash,
    safe_delete_file,
    # String utilities
    sanitize_filename,
    truncate_string,
    normalize_whitespace,
    camel_to_snake,
    snake_to_camel,
    extract_numbers,
    mask_sensitive_data,
    count_words,
    # Data utilities
    safe_json_loads,
    safe_json_dumps,
    merge_dicts,
    flatten_dict,
    chunk_list,
    remove_duplicates,
    filter_dict_by_keys,
    # Datetime utilities
    format_timestamp,
    parse_timestamp,
    get_time_delta,
    is_timestamp_expired,
    # Validation utilities
    is_valid_email,
    is_valid_url,
    is_valid_uuid,
    validate_required_fields,
)


class TestFileUtils:
    """Test file utility functions."""

    def test_ensure_directory_exists(self, tmp_path):
        """Test directory creation."""
        test_dir = tmp_path / "test_dir" / "nested"
        ensure_directory_exists(str(test_dir))
        assert test_dir.exists()
        
        # Test idempotency
        ensure_directory_exists(str(test_dir))
        assert test_dir.exists()

    def test_get_file_size(self, tmp_path):
        """Test file size retrieval."""
        test_file = tmp_path / "test.txt"
        content = "Hello, World!"
        test_file.write_text(content)
        
        size = get_file_size(str(test_file))
        assert size == len(content.encode('utf-8'))
        
        # Test non-existent file
        with pytest.raises(FileNotFoundError):
            get_file_size(str(tmp_path / "nonexistent.txt"))

    def test_get_file_extension(self):
        """Test file extension extraction."""
        assert get_file_extension("test.txt") == "txt"
        assert get_file_extension("archive.tar.gz") == "gz"
        assert get_file_extension("noextension") == ""
        assert get_file_extension(".hidden") == ""  # Hidden files have no extension

    def test_get_mime_type(self, tmp_path):
        """Test MIME type detection."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        mime = get_mime_type(str(test_file))
        assert mime == "text/plain"

    def test_is_text_file(self, tmp_path):
        """Test text file detection."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("content")
        assert is_text_file(str(txt_file)) is True
        
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value"}')
        assert is_text_file(str(json_file)) is True

    def test_read_write_file_content(self, tmp_path):
        """Test file reading and writing."""
        test_file = tmp_path / "test.txt"
        content = "Test content\nLine 2"
        
        write_file_content(str(test_file), content)
        assert test_file.exists()
        
        read_content = read_file_content(str(test_file))
        assert read_content == content

    def test_list_files_in_directory(self, tmp_path):
        """Test file listing."""
        # Create test files
        (tmp_path / "file1.txt").write_text("content")
        (tmp_path / "file2.py").write_text("content")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file3.txt").write_text("content")
        
        # List all files
        files = list_files_in_directory(str(tmp_path))
        assert len(files) == 2
        
        # List with pattern
        py_files = list_files_in_directory(str(tmp_path), pattern="*.py")
        assert len(py_files) == 1
        
        # List recursively
        all_files = list_files_in_directory(str(tmp_path), recursive=True)
        assert len(all_files) == 3

    def test_calculate_file_hash(self, tmp_path):
        """Test file hash calculation."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")
        
        # Test SHA256
        hash_sha256 = calculate_file_hash(str(test_file), algorithm="sha256")
        assert len(hash_sha256) == 64  # SHA256 is 64 hex chars
        
        # Test MD5
        hash_md5 = calculate_file_hash(str(test_file), algorithm="md5")
        assert len(hash_md5) == 32  # MD5 is 32 hex chars
        
        # Test invalid algorithm
        with pytest.raises(ValueError):
            calculate_file_hash(str(test_file), algorithm="invalid")

    def test_safe_delete_file(self, tmp_path):
        """Test safe file deletion."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        result = safe_delete_file(str(test_file))
        assert result is True
        assert not test_file.exists()
        
        # Test deleting non-existent file
        result = safe_delete_file(str(test_file))
        assert result is False


class TestStringUtils:
    """Test string utility functions."""

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        assert sanitize_filename("file<name>.txt") == "file_name_.txt"
        assert sanitize_filename('file"name".txt') == "file_name_.txt"
        assert sanitize_filename("file|name?.txt") == "file_name_.txt"
        assert sanitize_filename("  .file  ") == "file"
        assert sanitize_filename("   ") == "unnamed"

    def test_truncate_string(self):
        """Test string truncation."""
        text = "This is a long string"
        assert truncate_string(text, 10) == "This is..."
        assert truncate_string(text, 50) == text
        assert truncate_string(text, 10, suffix="…") == "This is a…"

    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        assert normalize_whitespace("  hello   world  ") == "hello world"
        assert normalize_whitespace("hello\n\nworld") == "hello world"
        assert normalize_whitespace("  ") == ""

    def test_camel_to_snake(self):
        """Test camelCase to snake_case conversion."""
        assert camel_to_snake("myVariableName") == "my_variable_name"
        assert camel_to_snake("HTTPResponse") == "h_t_t_p_response"
        assert camel_to_snake("lowercase") == "lowercase"

    def test_snake_to_camel(self):
        """Test snake_case to camelCase conversion."""
        assert snake_to_camel("my_variable_name") == "myVariableName"
        assert snake_to_camel("my_variable_name", capitalize_first=True) == "MyVariableName"
        assert snake_to_camel("single") == "single"

    def test_extract_numbers(self):
        """Test number extraction from strings."""
        assert extract_numbers("Price: $12.50") == [12.50]
        assert extract_numbers("Numbers: 1, 2.5, -3") == [1.0, 2.5, -3.0]
        assert extract_numbers("No numbers here") == []

    def test_mask_sensitive_data(self):
        """Test sensitive data masking."""
        text = "Email: user@example.com, Password: secret123"
        pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        masked = mask_sensitive_data(text, pattern)
        assert "user@example.com" not in masked
        assert "***" in masked

    def test_count_words(self):
        """Test word counting."""
        assert count_words("Hello world") == 2
        assert count_words("One, two, three!") == 3
        assert count_words("") == 0


class TestDataUtils:
    """Test data utility functions."""

    def test_safe_json_loads(self):
        """Test safe JSON loading."""
        assert safe_json_loads('{"key": "value"}') == {"key": "value"}
        assert safe_json_loads('invalid json', default={}) == {}
        assert safe_json_loads('null') is None

    def test_safe_json_dumps(self):
        """Test safe JSON serialization."""
        assert safe_json_dumps({"key": "value"}) == '{"key": "value"}'
        assert safe_json_dumps({"key": "value"}, indent=2) is not None
        
        # Test with non-serializable object
        class NonSerializable:
            pass
        assert safe_json_dumps(NonSerializable()) is None

    def test_merge_dicts(self):
        """Test dictionary merging."""
        dict1 = {"a": 1, "b": 2}
        dict2 = {"b": 3, "c": 4}
        
        # Shallow merge
        result = merge_dicts(dict1, dict2)
        assert result == {"a": 1, "b": 3, "c": 4}
        
        # Deep merge
        dict1_nested = {"a": {"x": 1, "y": 2}, "b": 3}
        dict2_nested = {"a": {"y": 3, "z": 4}, "c": 5}
        result = merge_dicts(dict1_nested, dict2_nested, deep=True)
        assert result == {"a": {"x": 1, "y": 3, "z": 4}, "b": 3, "c": 5}

    def test_flatten_dict(self):
        """Test dictionary flattening."""
        nested = {
            "a": 1,
            "b": {
                "c": 2,
                "d": {
                    "e": 3
                }
            }
        }
        result = flatten_dict(nested)
        assert result == {"a": 1, "b.c": 2, "b.d.e": 3}
        
        # Test custom separator
        result = flatten_dict(nested, sep="_")
        assert result == {"a": 1, "b_c": 2, "b_d_e": 3}

    def test_chunk_list(self):
        """Test list chunking."""
        data = list(range(10))
        chunks = chunk_list(data, 3)
        assert len(chunks) == 4
        assert chunks[0] == [0, 1, 2]
        assert chunks[-1] == [9]

    def test_remove_duplicates(self):
        """Test duplicate removal."""
        # Simple list
        data = [1, 2, 2, 3, 1, 4]
        result = remove_duplicates(data)
        assert result == [1, 2, 3, 4]
        
        # With key function
        data = [{"id": 1}, {"id": 2}, {"id": 1}]
        result = remove_duplicates(data, key=lambda x: x["id"])
        assert len(result) == 2

    def test_filter_dict_by_keys(self):
        """Test dictionary filtering."""
        data = {"a": 1, "b": 2, "c": 3}
        
        # Include
        result = filter_dict_by_keys(data, ["a", "c"], include=True)
        assert result == {"a": 1, "c": 3}
        
        # Exclude
        result = filter_dict_by_keys(data, ["b"], include=False)
        assert result == {"a": 1, "c": 3}


class TestDatetimeUtils:
    """Test datetime utility functions."""

    def test_format_timestamp(self):
        """Test timestamp formatting."""
        dt = datetime(2024, 1, 15, 14, 30, 0)
        formatted = format_timestamp(dt)
        assert formatted == "2024-01-15 14:30:00"
        
        # Test custom format
        formatted = format_timestamp(dt, format_str="%Y-%m-%d")
        assert formatted == "2024-01-15"
        
        # Test default (current time)
        formatted = format_timestamp()
        assert len(formatted) > 0

    def test_parse_timestamp(self):
        """Test timestamp parsing."""
        dt = parse_timestamp("2024-01-15 14:30:00")
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15
        
        # Test invalid format
        result = parse_timestamp("invalid", format_str="%Y-%m-%d")
        assert result is None

    def test_get_time_delta(self):
        """Test timedelta creation."""
        delta = get_time_delta(days=1, hours=2, minutes=30)
        assert delta.days == 1
        assert delta.seconds == 2 * 3600 + 30 * 60

    def test_is_timestamp_expired(self):
        """Test timestamp expiration checking."""
        # Recent timestamp (not expired)
        recent = datetime.now() - timedelta(seconds=30)
        assert is_timestamp_expired(recent, expiry_seconds=60) is False
        
        # Old timestamp (expired)
        old = datetime.now() - timedelta(seconds=120)
        assert is_timestamp_expired(old, expiry_seconds=60) is True


class TestValidationUtils:
    """Test validation utility functions."""

    def test_is_valid_email(self):
        """Test email validation."""
        assert is_valid_email("user@example.com") is True
        assert is_valid_email("user.name@example.co.uk") is True
        assert is_valid_email("invalid-email") is False
        assert is_valid_email("@example.com") is False
        assert is_valid_email("user@") is False

    def test_is_valid_url(self):
        """Test URL validation."""
        assert is_valid_url("https://example.com") is True
        assert is_valid_url("http://example.com/path") is True
        assert is_valid_url("ftp://example.com") is False
        assert is_valid_url("not-a-url") is False

    def test_is_valid_uuid(self):
        """Test UUID validation."""
        assert is_valid_uuid("550e8400-e29b-41d4-a716-446655440000") is True
        assert is_valid_uuid("550E8400-E29B-41D4-A716-446655440000") is True
        assert is_valid_uuid("invalid-uuid") is False
        assert is_valid_uuid("550e8400-e29b-41d4-a716") is False

    def test_validate_required_fields(self):
        """Test required fields validation."""
        data = {"name": "John", "email": "john@example.com"}
        
        # All fields present
        is_valid, missing = validate_required_fields(data, ["name", "email"])
        assert is_valid is True
        assert missing == []
        
        # Missing fields
        is_valid, missing = validate_required_fields(data, ["name", "email", "age"])
        assert is_valid is False
        assert "age" in missing
        
        # Field with None value
        data_with_none = {"name": "John", "email": None}
        is_valid, missing = validate_required_fields(data_with_none, ["name", "email"])
        assert is_valid is False
        assert "email" in missing
