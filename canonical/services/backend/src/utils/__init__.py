"""
Backend utilities package.

This package provides utility functions for the backend application,
organized into focused modules:

- backend_file_utils: File and directory operations
- backend_string_utils: String manipulation and formatting
- backend_data_utils: Data processing and JSON operations
- backend_datetime_utils: Date and time utilities
- backend_validation_utils: Data validation functions

All functions are re-exported from this package for convenience.

Usage:
    from backend.utils import sanitize_filename, safe_json_loads
    # or
    from backend.utils.backend_string_utils import sanitize_filename
"""

# File utilities
from .backend_file_utils import (
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
)

# String utilities
from .backend_string_utils import (
    sanitize_filename,
    truncate_string,
    normalize_whitespace,
    camel_to_snake,
    snake_to_camel,
    extract_numbers,
    mask_sensitive_data,
    count_words,
)

# Data utilities
from .backend_data_utils import (
    safe_json_loads,
    safe_json_dumps,
    merge_dicts,
    flatten_dict,
    chunk_list,
    remove_duplicates,
    filter_dict_by_keys,
)

# Date/time utilities
from .backend_datetime_utils import (
    format_timestamp,
    parse_timestamp,
    get_time_delta,
    is_timestamp_expired,
)

# Validation utilities
from .backend_validation_utils import (
    is_valid_email,
    is_valid_url,
    is_valid_uuid,
    validate_required_fields,
)

__all__ = [
    # File utilities
    'ensure_directory_exists',
    'get_file_size',
    'get_file_extension',
    'get_mime_type',
    'is_text_file',
    'read_file_content',
    'write_file_content',
    'list_files_in_directory',
    'calculate_file_hash',
    'safe_delete_file',
    # String utilities
    'sanitize_filename',
    'truncate_string',
    'normalize_whitespace',
    'camel_to_snake',
    'snake_to_camel',
    'extract_numbers',
    'mask_sensitive_data',
    'count_words',
    # Data utilities
    'safe_json_loads',
    'safe_json_dumps',
    'merge_dicts',
    'flatten_dict',
    'chunk_list',
    'remove_duplicates',
    'filter_dict_by_keys',
    # Date/time utilities
    'format_timestamp',
    'parse_timestamp',
    'get_time_delta',
    'is_timestamp_expired',
    # Validation utilities
    'is_valid_email',
    'is_valid_url',
    'is_valid_uuid',
    'validate_required_fields',
]
