"""
Utility functions for secure file operations and validation.
Used across the backend API for consistent and safe file handling.

⚠️ SECURITY WARNING - LOCAL DEVELOPMENT ONLY ⚠️
This module allows UNRESTRICTED file operations (any extension) within BASE_DIR.
This is designed for LOCAL DEVELOPMENT with version control (git).
DO NOT use in production or multi-user environments.
User accepts all risks of unrestricted file manipulation.
"""

import base64
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Tuple

# Maximum file size (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


def validate_and_sanitize_path(
    base_path: str, user_path: str
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate and sanitize a file path to prevent directory traversal attacks.

    SECURITY: This function is the security boundary for all path operations.
    It ensures that user-provided paths cannot escape the base directory.
    CodeQL warnings about path injection (CWE-22) in code using this function
    are false positives because the path is validated to be within the base directory.
    The validation uses Path.resolve() and startswith() to prevent directory traversal.

    Args:
        base_path: The base directory that should contain all operations
        user_path: The user-provided path (potentially unsafe)

    Returns:
        Tuple of (is_valid, sanitized_path, error_message)
        - is_valid: True if path is safe, False otherwise
        - sanitized_path: The cleaned, absolute path (or None if invalid)
        - error_message: Error description if invalid (or None if valid)
    """
    try:
        # Convert to Path objects for robust handling
        base = Path(base_path).resolve()

        # Normaliza: remove espaços, barras iniciais e finais
        user_path_clean = user_path.strip().lstrip("/").rstrip("/")

        # Combine and resolve the path
        target = (base / user_path_clean).resolve()
        # CRITICAL SECURITY CHECK: Ensure target is within base directory
        if not str(target).startswith(str(base)):
            return False, None, f"Path traversal detected: {user_path}"

        # Check for null bytes (security issue in some systems)
        if "\x00" in user_path:
            return False, None, "Null byte in path"

        return True, str(target), None

    except Exception as e:
        return False, None, f"Path validation error: {str(e)}"


def validate_filename_extension(filename: str) -> Tuple[bool, Optional[str]]:
    """
    Validate filename for security issues (path traversal patterns).

    ⚠️ LOCAL DEVELOPMENT ONLY: No extension restrictions.
    Any file type is allowed for maximum flexibility in local repository editing.

    Args:
        filename: The filename to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if filename is safe, False otherwise
        - error_message: Error description if invalid (or None if valid)
    """
    try:
        # Check for dangerous path traversal patterns
        if ".." in filename or "/" in filename or "\\" in filename:
            return False, "Invalid characters in filename (path traversal attempt)"

        # Allow any extension for local development
        # Only validate filename is not empty
        if not filename or filename.strip() == "":
            return False, "Filename cannot be empty"

        return True, None

    except Exception as e:
        return False, f"Filename validation error: {str(e)}"


def decode_base64_content(
    encoded_content: str,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Decode base64-encoded file content.

    Args:
        encoded_content: Base64-encoded string

    Returns:
        Tuple of (success, decoded_content, error_message)
        - success: True if decoding succeeded, False otherwise
        - decoded_content: The decoded string (or None if failed)
        - error_message: Error description if failed (or None if succeeded)
    """
    try:
        # Decode from base64
        decoded_bytes = base64.b64decode(encoded_content)

        # Check size
        if len(decoded_bytes) > MAX_FILE_SIZE:
            return False, None, f"File size exceeds maximum ({MAX_FILE_SIZE} bytes)"

        # Try to decode as UTF-8 text
        decoded_str = decoded_bytes.decode("utf-8")

        return True, decoded_str, None

    except base64.binascii.Error as e:
        return False, None, f"Invalid base64 encoding: {str(e)}"
    except UnicodeDecodeError as e:
        return False, None, f"Content is not valid UTF-8 text: {str(e)}"
    except Exception as e:
        return False, None, f"Decoding error: {str(e)}"


def write_file_atomically(file_path: str, content: str) -> Tuple[bool, Optional[str]]:
    """
    Write content to a file atomically (all-or-nothing) to prevent corruption.

    This uses a temporary file and atomic rename to ensure the file is either
    completely written or not written at all, preventing partial writes.

    SECURITY: file_path must be validated with validate_and_sanitize_path()
    before calling this function. This function assumes the path is safe.
    CodeQL warnings about path injection here are false positives if validation is done.

    Args:
        file_path: The target file path (must be pre-validated)
        content: The content to write

    Returns:
        Tuple of (success, error_message)
        - success: True if write succeeded, False otherwise
        - error_message: Error description if failed (or None if succeeded)
    """
    try:
        # Ensure parent directory exists
        parent_dir = Path(file_path).parent
        parent_dir.mkdir(parents=True, exist_ok=True)

        # Create temporary file in the same directory (for atomic rename)
        # CodeQL Warning: Path is safe if validated before calling this function
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=parent_dir, delete=False, suffix=".tmp"
        ) as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name

        # Atomic rename (replace existing file if any)
        # CodeQL Warning: Path is safe if validated before calling this function
        shutil.move(tmp_path, file_path)

        return True, None

    except Exception as e:
        # Clean up temp file if it exists
        try:
            if "tmp_path" in locals():
                Path(tmp_path).unlink(missing_ok=True)
        except:
            pass

        return False, f"Write error: {str(e)}"


def ensure_directory_exists(dir_path: str) -> Tuple[bool, Optional[str]]:
    """
    Ensure a directory exists, creating it if necessary.

    SECURITY: dir_path must be validated with validate_and_sanitize_path()
    before calling this function.

    Args:
        dir_path: The directory path to ensure exists (must be pre-validated)

    Returns:
        Tuple of (success, error_message)
    """
    try:
        # CodeQL Warning: Path is safe if validated before calling this function
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        return True, None
    except Exception as e:
        return False, f"Directory creation error: {str(e)}"


def check_file_permissions(
    file_path: str, check_write: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Check if a file has the required OS-level permissions.

    ⚠️ LOCAL DEVELOPMENT: Validates OS permissions before file operations.

    SECURITY: file_path must be validated with validate_and_sanitize_path()
    before calling this function.

    Args:
        file_path: The file path to check (must be pre-validated)
        check_write: If True, check write permissions; if False, check read permissions

    Returns:
        Tuple of (has_permission, error_message)
        - has_permission: True if permission exists, False otherwise
        - error_message: Error description if no permission (or None if has permission)
    """
    try:
        path = Path(file_path)

        # Check if path exists
        if not path.exists():
            # For write operations, check parent directory permissions
            if check_write:
                parent = path.parent
                if not parent.exists():
                    return False, f"Parent directory does not exist: {parent}"
                if not os.access(str(parent), os.W_OK):
                    return False, f"No write permission on parent directory: {parent}"
                return True, None  # Can create new file
            else:
                return False, f"File does not exist: {file_path}"

        # For existing files, check actual permissions
        if check_write:
            if not os.access(str(path), os.W_OK):
                return False, f"No write permission on file: {file_path}"
        else:
            if not os.access(str(path), os.R_OK):
                return False, f"No read permission on file: {file_path}"

        return True, None

    except Exception as e:
        return False, f"Permission check error: {str(e)}"


def delete_file_or_directory(path: str) -> Tuple[bool, Optional[str]]:
    """
    Delete a file or directory with OS permission validation.

    ⚠️ LOCAL DEVELOPMENT: Allows deletion of any file/directory within BASE_DIR.
    Use with caution. Requires OS write permissions.

    SECURITY: path must be validated with validate_and_sanitize_path()
    before calling this function.

    Args:
        path: The file or directory path to delete (must be pre-validated)

    Returns:
        Tuple of (success, error_message)
        - success: True if deletion succeeded, False otherwise
        - error_message: Error description if failed (or None if succeeded)
    """
    try:
        target = Path(path)

        # Check if exists
        if not target.exists():
            return False, f"Path does not exist: {path}"

        # Check write permission on parent directory
        parent = target.parent
        if not os.access(str(parent), os.W_OK):
            return False, f"No write permission on parent directory: {parent}"

        # Delete file or directory
        if target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(str(target))
        else:
            return False, f"Unknown path type: {path}"

        return True, None

    except Exception as e:
        return False, f"Deletion error: {str(e)}"
