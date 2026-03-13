"""
File utility functions for the backend application.

This module provides functions for file and directory operations including:
- Directory management
- File size and type detection
- File reading/writing
- File listing and searching
- Hash calculation
- Safe file deletion

Following naming convention Rule 1.3: Using 'backend_file_utils' instead of
generic 'file_utils' to avoid namespace conflicts.
"""

import os
import hashlib
import mimetypes
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


def ensure_directory_exists(directory_path: str) -> None:
    """
    Ensure that a directory exists, creating it if necessary.
    
    Args:
        directory_path: Path to the directory to create
        
    Raises:
        OSError: If directory creation fails
    """
    try:
        os.makedirs(directory_path, exist_ok=True)
        logger.debug(f"Directory ensured: {directory_path}")
    except OSError as e:
        logger.error(f"Failed to create directory {directory_path}: {e}")
        raise


def get_file_size(file_path: str) -> int:
    """
    Get the size of a file in bytes.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File size in bytes
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    return os.path.getsize(file_path)


def get_file_extension(file_path: str) -> str:
    """
    Get the extension of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File extension without the dot (e.g., 'txt', 'py')
    """
    return Path(file_path).suffix.lstrip('.')


def get_mime_type(file_path: str) -> Optional[str]:
    """
    Get the MIME type of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        MIME type string or None if unknown
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type


def is_text_file(file_path: str) -> bool:
    """
    Check if a file is a text file based on MIME type.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if file is text, False otherwise
    """
    mime_type = get_mime_type(file_path)
    if mime_type:
        return mime_type.startswith('text/') or mime_type in [
            'application/json',
            'application/xml',
            'application/javascript'
        ]
    return False


def read_file_content(file_path: str, encoding: str = 'utf-8') -> str:
    """
    Read the content of a text file.
    
    Args:
        file_path: Path to the file
        encoding: File encoding (default: utf-8)
        
    Returns:
        File content as string
        
    Raises:
        FileNotFoundError: If file does not exist
        UnicodeDecodeError: If file cannot be decoded with given encoding
    """
    with open(file_path, 'r', encoding=encoding) as f:
        return f.read()


def write_file_content(file_path: str, content: str, encoding: str = 'utf-8') -> None:
    """
    Write content to a text file.
    
    Args:
        file_path: Path to the file
        content: Content to write
        encoding: File encoding (default: utf-8)
    """
    ensure_directory_exists(os.path.dirname(file_path))
    with open(file_path, 'w', encoding=encoding) as f:
        f.write(content)
    logger.info(f"Written {len(content)} characters to {file_path}")


def list_files_in_directory(
    directory_path: str,
    pattern: Optional[str] = None,
    recursive: bool = False
) -> List[str]:
    """
    List files in a directory, optionally filtering by pattern.
    
    Args:
        directory_path: Path to the directory
        pattern: Optional glob pattern to filter files (e.g., '*.py')
        recursive: Whether to search recursively
        
    Returns:
        List of file paths
    """
    path = Path(directory_path)
    
    if not path.exists():
        return []
    
    if pattern:
        if recursive:
            files = path.rglob(pattern)
        else:
            files = path.glob(pattern)
    else:
        if recursive:
            files = path.rglob('*')
        else:
            files = path.glob('*')
    
    return [str(f) for f in files if f.is_file()]


def calculate_file_hash(file_path: str, algorithm: str = 'sha256') -> str:
    """
    Calculate the hash of a file.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm (md5, sha1, sha256, etc.)
        
    Returns:
        Hexadecimal hash string
        
    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If algorithm is not supported
    """
    if algorithm not in hashlib.algorithms_available:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")
    
    hash_obj = hashlib.new(algorithm)
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_obj.update(chunk)
    
    return hash_obj.hexdigest()


def safe_delete_file(file_path: str) -> bool:
    """
    Safely delete a file, logging errors instead of raising.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted file: {file_path}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to delete file {file_path}: {e}")
        return False
