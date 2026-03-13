"""
Document Tools for Function Calling

Provides tools for reading local documents via OpenAI Function Calling.
This enables the LLM to request document content on-demand instead of
sending large documents inline in the prompt.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict

from .config import BASE_DIR

logger = logging.getLogger(__name__)

# Maximum file size (10 MB by default)
MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_DOCUMENT_SIZE_BYTES", 10 * 1024 * 1024))

# Allowed base directories for document reading (relative to BASE_DIR)
ALLOWED_DOCUMENT_DIRS = [
    "backend/app",
    "backend/docs",
    "docs",
    "scripts",
    "cockpit",
    "cockpit-vue",
]


def read_local_document(file_path: str) -> str:
    """
    Read the content of a local document file.

    This function is designed to be called by the LLM via Function Calling
    to retrieve document content on-demand.

    Args:
        file_path: Relative path to the document file from BASE_DIR

    Returns:
        String with the document content

    Raises:
        ValueError: If the file path is invalid or not allowed
        FileNotFoundError: If the file does not exist
        PermissionError: If there are permission issues reading the file
        OSError: For other file reading errors

    Security:
        - Only allows reading files within ALLOWED_DOCUMENT_DIRS
        - Prevents path traversal attacks
        - Enforces maximum file size limit

    Example:
        >>> content = read_local_document("docs/README.md")
        >>> content = read_local_document("backend/app/config.py")
    """
    # Normalize the file path (remove .. and resolve)
    try:
        # Convert to Path object relative to BASE_DIR
        abs_path = (BASE_DIR / file_path).resolve()

        # Security check: ensure the resolved path is within BASE_DIR
        if not str(abs_path).startswith(str(BASE_DIR.resolve())):
            raise ValueError(
                f"Security error: file path '{file_path}' resolves outside BASE_DIR. "
                "This may be a path traversal attack."
            )

        # Check if path is within allowed directories
        relative_to_base = abs_path.relative_to(BASE_DIR.resolve())
        path_allowed = False

        for allowed_dir in ALLOWED_DOCUMENT_DIRS:
            allowed_path = Path(allowed_dir)
            try:
                relative_to_base.relative_to(allowed_path)
                path_allowed = True
                break
            except ValueError:
                # Not relative to this allowed dir, try next
                continue

        if not path_allowed:
            raise ValueError(
                f"Access denied: file path '{file_path}' is not in allowed directories. "
                f"Allowed directories: {', '.join(ALLOWED_DOCUMENT_DIRS)}"
            )

        # Check if file exists
        if not abs_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check if it's a file (not a directory)
        if not abs_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        # Check file size
        file_size = abs_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE_BYTES} bytes). "
                "Consider splitting the file or increasing MAX_DOCUMENT_SIZE_BYTES."
            )

        # Read the file content
        logger.info("Reading local document: %s (%s bytes)", file_path, file_size)

        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()

            logger.info("Successfully read document: %s", file_path)
            return content

        except UnicodeDecodeError:
            # Try with latin-1 encoding as fallback
            logger.warning("UTF-8 decode failed for %s, trying latin-1", file_path)
            with open(abs_path, "r", encoding="latin-1") as f:
                content = f.read()
            return content

    except ValueError as e:
        logger.error("Invalid file path: %s - %s", file_path, e)
        raise
    except FileNotFoundError:
        logger.error("File not found: %s", file_path)
        raise
    except PermissionError:
        logger.error("Permission denied reading file: %s", file_path)
        raise
    except Exception as e:
        logger.error("Error reading file %s: %s", file_path, e)
        raise OSError(f"Failed to read file: {e}") from e


def get_read_document_tool_definition() -> Dict[str, Any]:
    """
    Get the OpenAI Function Calling tool definition for read_local_document.

    Returns:
        Dictionary with the tool definition in OpenAI format

    Example:
        >>> tool_def = get_read_document_tool_definition()
        >>> tools = [tool_def]
        >>> response = await chamar_openai(payload, tools=tools)
    """
    return {
        "type": "function",
        "function": {
            "name": "read_local_document",
            "description": (
                "Read the content of a local document file from the repository. "
                "Use this when you need to analyze, review, or process a large document "
                "that was mentioned by the user. The document must be a text file located "
                "in the project directories (docs, backend, scripts, etc.). "
                "Examples: 'docs/README.md', 'backend/app/config.py', 'docs/ARCHITECTURE.md'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": (
                            "Relative path to the document file from the project root. "
                            "Example: 'docs/README.md' or 'backend/app/models.py'"
                        ),
                    }
                },
                "required": ["file_path"],
            },
        },
    }


def execute_tool_call(tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    Execute a tool function call based on the tool name.

    This function maps tool names to their implementations and executes them.

    Args:
        tool_name: Name of the tool to execute
        arguments: Arguments to pass to the tool function

    Returns:
        String with the result of the tool execution

    Raises:
        ValueError: If the tool name is unknown

    Example:
        >>> result = execute_tool_call("read_local_document", {"file_path": "docs/README.md"})
    """
    if tool_name == "read_local_document":
        file_path = arguments.get("file_path")
        if not file_path:
            raise ValueError("Missing required argument: file_path")

        try:
            return read_local_document(file_path)
        except Exception as e:
            # Return error message as string (LLM can understand and retry)
            error_msg = f"Error reading document '{file_path}': {str(e)}"
            logger.error(error_msg)
            return error_msg
    else:
        raise ValueError(f"Unknown tool: {tool_name}")
