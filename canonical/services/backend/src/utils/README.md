---
processed: true
processed_date: 2025-12-10
themes:
  - architecture
  - utilities
  - modularization
modules:
  - backend
code_verified: true
dead_docs_found: false
updated_docs:
  - docs/official/backend/architecture/utilities-package.md
verified_files:
  - backend/utils/__init__.py
  - backend/utils/backend_file_utils.py
  - backend/utils/backend_string_utils.py
  - backend/utils/backend_data_utils.py
  - backend/utils/backend_datetime_utils.py
  - backend/utils/backend_validation_utils.py
---
# Backend Utils Package

This directory contains modularized utility functions for the backend application. The original `backend/utils.py` (654 lines) was split into focused, single-responsibility modules to comply with the project's 500-line limit rule (RULESET.md Rule 1.1).

## Directory Structure

```
backend/utils/
├── __init__.py                      # Package exports (all functions re-exported)
├── backend_file_utils.py            # File and directory operations
├── backend_string_utils.py          # String manipulation utilities
├── backend_data_utils.py            # Data processing and JSON utilities
├── backend_datetime_utils.py        # Date/time utilities
├── backend_validation_utils.py      # Data validation functions
└── README.md                        # This file
```

## Module Overview

### backend_file_utils.py

File and directory operations including:
- **Directory management**: `ensure_directory_exists()`
- **File info**: `get_file_size()`, `get_file_extension()`, `get_mime_type()`, `is_text_file()`
- **File I/O**: `read_file_content()`, `write_file_content()`
- **File listing**: `list_files_in_directory()` (with glob patterns and recursive search)
- **File hashing**: `calculate_file_hash()` (MD5, SHA256, etc.)
- **Safe deletion**: `safe_delete_file()` (with error logging)

### backend_string_utils.py

String manipulation and formatting:
- **Sanitization**: `sanitize_filename()` (remove invalid filesystem characters)
- **Formatting**: `truncate_string()`, `normalize_whitespace()`
- **Case conversion**: `camel_to_snake()`, `snake_to_camel()`
- **Extraction**: `extract_numbers()` (regex-based number extraction)
- **Security**: `mask_sensitive_data()` (regex-based masking)
- **Analysis**: `count_words()`

### backend_data_utils.py

Data processing and manipulation:
- **Safe JSON**: `safe_json_loads()`, `safe_json_dumps()` (with error handling)
- **Dictionary operations**: `merge_dicts()`, `flatten_dict()`, `filter_dict_by_keys()`
- **List operations**: `chunk_list()`, `remove_duplicates()`

### backend_datetime_utils.py

Date and time utilities:
- **Formatting**: `format_timestamp()` (datetime to string)
- **Parsing**: `parse_timestamp()` (string to datetime)
- **Timedelta**: `get_time_delta()` (create timedelta from components)
- **Validation**: `is_timestamp_expired()` (check if timestamp is older than threshold)

### backend_validation_utils.py

Data validation functions:
- **Email validation**: `is_valid_email()` (regex-based)
- **URL validation**: `is_valid_url()` (http/https only)
- **UUID validation**: `is_valid_uuid()` (format check)
- **Required fields**: `validate_required_fields()` (check dictionary for required keys)

## Usage Examples

### Importing Functions

```python
# Import from package (recommended - maintains backward compatibility)
from backend.utils import sanitize_filename, safe_json_loads, is_valid_email

# Import from specific module (explicit)
from backend.utils.backend_string_utils import sanitize_filename
from backend.utils.backend_data_utils import safe_json_loads
from backend.utils.backend_validation_utils import is_valid_email
```

### File Operations

```python
from backend.utils import ensure_directory_exists, write_file_content, calculate_file_hash

# Ensure directory exists before writing
ensure_directory_exists("/tmp/my_app/data")

# Write content to file
write_file_content("/tmp/my_app/data/output.txt", "Hello, World!")

# Calculate file hash
hash_value = calculate_file_hash("/tmp/my_app/data/output.txt", algorithm="sha256")
print(f"SHA256: {hash_value}")
```

### String Manipulation

```python
from backend.utils import sanitize_filename, truncate_string, camel_to_snake

# Sanitize a filename
safe_name = sanitize_filename("my<file>name?.txt")  # Returns: "my_file_name_.txt"

# Truncate long text
short_text = truncate_string("This is a very long text", max_length=15)  # Returns: "This is a ve..."

# Convert case
snake = camel_to_snake("myVariableName")  # Returns: "my_variable_name"
```

### Data Processing

```python
from backend.utils import safe_json_loads, merge_dicts, chunk_list

# Safe JSON parsing
data = safe_json_loads('{"key": "value"}', default={})

# Merge dictionaries
dict1 = {"a": 1, "b": 2}
dict2 = {"b": 3, "c": 4}
merged = merge_dicts(dict1, dict2)  # Returns: {"a": 1, "b": 3, "c": 4}

# Chunk a large list
items = list(range(100))
chunks = chunk_list(items, chunk_size=10)  # Returns: [[0-9], [10-19], ...]
```

### Date/Time Operations

```python
from backend.utils import format_timestamp, parse_timestamp, is_timestamp_expired
from datetime import datetime

# Format current timestamp
now_str = format_timestamp()  # Returns: "2024-01-15 14:30:00"

# Parse timestamp
timestamp = parse_timestamp("2024-01-15 14:30:00")

# Check expiration
is_expired = is_timestamp_expired(timestamp, expiry_seconds=3600)  # 1 hour
```

### Data Validation

```python
from backend.utils import is_valid_email, is_valid_url, validate_required_fields

# Validate email
is_valid_email("user@example.com")  # Returns: True
is_valid_email("invalid-email")     # Returns: False

# Validate URL
is_valid_url("https://example.com")  # Returns: True

# Validate required fields
data = {"name": "John", "email": "john@example.com"}
is_valid, missing = validate_required_fields(data, ["name", "email", "age"])
# Returns: (False, ["age"])
```

## Backward Compatibility

All functions from the original `backend/utils.py` are re-exported from the `__init__.py` file, ensuring backward compatibility. Existing imports like:

```python
from backend.utils import sanitize_filename
```

will continue to work without modifications.

## Testing

Tests for these utilities should be added to:
- `tests/unit/backend/test_file_utils.py`
- `tests/unit/backend/test_string_utils.py`
- `tests/unit/backend/test_data_utils.py`
- `tests/unit/backend/test_datetime_utils.py`
- `tests/unit/backend/test_validation_utils.py`

## Naming Convention

All module names use the `backend_` prefix (e.g., `backend_file_utils.py` instead of `file_utils.py`) to follow **RULESET.md Rule 1.3** and avoid namespace conflicts in larger codebases.

## Line Counts

- `backend_file_utils.py`: ~220 lines ✅
- `backend_string_utils.py`: ~160 lines ✅
- `backend_data_utils.py`: ~140 lines ✅
- `backend_datetime_utils.py`: ~90 lines ✅
- `backend_validation_utils.py`: ~40 lines ✅
- `__init__.py`: ~60 lines ✅

**All modules comply with the 500-line limit.**

## References

- [RULESET.md](../../RULESET.md) - Project coding standards
- [Original Issue](https://github.com/ScareCrowOrg/ScareVerseLab/issues/XXX) - Modularization task
