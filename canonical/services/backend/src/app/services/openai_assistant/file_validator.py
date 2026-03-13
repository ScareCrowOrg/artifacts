"""
OpenAI File Validator Module

Validates files before upload to OpenAI Files API.
Checks size limits, MIME types, and file formats according to OpenAI specifications.

Technical naming: All functions and variables in English.
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# OpenAI Files API limits (November 2024 - verify current limits at https://platform.openai.com/docs/assistants/tools/file-search/supported-files)
# https://platform.openai.com/docs/assistants/tools/file-search/supported-files
MAX_FILE_SIZE_BYTES = 512 * 1024 * 1024  # 512 MB per file
MAX_FILES_PER_ASSISTANT = 10000  # Per assistant
MAX_FILE_SIZE_FOR_VISION = 20 * 1024 * 1024  # 20 MB for vision

# Supported file extensions for file_search tool
SUPPORTED_EXTENSIONS_FILE_SEARCH = {
    ".c",
    ".cpp",
    ".cs",
    ".css",
    ".doc",
    ".docx",
    ".go",
    ".html",
    ".java",
    ".js",
    ".json",
    ".md",
    ".pdf",
    ".php",
    ".pptx",
    ".py",
    ".rb",
    ".sh",
    ".tex",
    ".ts",
    ".txt",
}

# Supported MIME types mapping
MIME_TYPE_MAPPING = {
    ".c": "text/x-c",
    ".cpp": "text/x-c++",
    ".cs": "text/x-csharp",
    ".css": "text/css",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".go": "text/x-go",
    ".html": "text/html",
    ".java": "text/x-java",
    ".js": "text/javascript",
    ".json": "application/json",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".php": "text/x-php",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".py": "text/x-python",
    ".rb": "text/x-ruby",
    ".sh": "text/x-sh",
    ".tex": "text/x-tex",
    ".ts": "text/typescript",
    ".txt": "text/plain",
}


def validate_file_for_upload(
    file_path: Path, purpose: str = "assistants"
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate file for OpenAI Files API upload.

    Checks:
    - File exists and is readable
    - File size within limits
    - File extension is supported (for assistants purpose)
    - Returns appropriate MIME type

    Args:
        file_path: Path to file to validate
        purpose: Upload purpose ("assistants", "vision", etc.)

    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str], mime_type: Optional[str])

    Example:
        >>> valid, error, mime = validate_file_for_upload(Path("test.py"))
        >>> if valid:
        ...     print(f"File OK, MIME type: {mime}")
        ... else:
        ...     print(f"Validation failed: {error}")
    """
    # Check file exists
    if not file_path.exists():
        return False, f"File not found: {file_path}", None

    if not file_path.is_file():
        return False, f"Path is not a file: {file_path}", None

    # Check file size
    file_size = file_path.stat().st_size

    if purpose == "assistants":
        max_size = MAX_FILE_SIZE_BYTES
    elif purpose == "vision":
        max_size = MAX_FILE_SIZE_FOR_VISION
    else:
        max_size = MAX_FILE_SIZE_BYTES

    if file_size > max_size:
        return (
            False,
            (
                f"File size {file_size} bytes exceeds maximum {max_size} bytes "
                f"for purpose '{purpose}'"
            ),
            None,
        )

    # Check file extension (for assistants purpose with file_search)
    file_extension = file_path.suffix.lower()

    if purpose == "assistants":
        if file_extension not in SUPPORTED_EXTENSIONS_FILE_SEARCH:
            return (
                False,
                (
                    f"File extension '{file_extension}' not supported for file_search. "
                    f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS_FILE_SEARCH))}"
                ),
                None,
            )

    # Get MIME type
    mime_type = MIME_TYPE_MAPPING.get(file_extension, "application/octet-stream")

    logger.debug("File validation passed: %s, size: %s bytes, MIME: %s", file_path.name, file_size, mime_type)

    return True, None, mime_type


def get_file_info(file_path: Path) -> dict:
    """
    Get detailed file information for diagnostics.

    Args:
        file_path: Path to file

    Returns:
        Dictionary with file information
    """
    if not file_path.exists():
        return {"exists": False, "error": "File not found"}

    stats = file_path.stat()
    extension = file_path.suffix.lower()

    return {
        "exists": True,
        "name": file_path.name,
        "size_bytes": stats.st_size,
        "size_mb": round(stats.st_size / (1024 * 1024), 2),
        "extension": extension,
        "is_supported": extension in SUPPORTED_EXTENSIONS_FILE_SEARCH,
        "mime_type": MIME_TYPE_MAPPING.get(extension, "application/octet-stream"),
        "within_size_limit": stats.st_size <= MAX_FILE_SIZE_BYTES,
        "modified": stats.st_mtime,
    }
