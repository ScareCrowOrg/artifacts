"""
String utility functions for the backend application.

This module provides functions for string manipulation including:
- Filename sanitization
- String truncation
- Whitespace normalization
- Case conversion (camelCase, snake_case)
- Number extraction
- Sensitive data masking
- Word counting

Following naming convention Rule 1.3: Using 'backend_string_utils' instead of
generic 'string_utils' to avoid namespace conflicts.
"""

import re
from typing import List


def sanitize_filename(filename: str, replacement: str = '_') -> str:
    """
    Sanitize a filename by removing or replacing invalid characters.
    
    Args:
        filename: Original filename
        replacement: Character to replace invalid characters with
        
    Returns:
        Sanitized filename
    """
    # Remove invalid characters for most filesystems
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, replacement, filename)
    
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip('. ')
    
    # Ensure filename is not empty
    if not sanitized:
        sanitized = 'unnamed'
    
    return sanitized


def truncate_string(text: str, max_length: int, suffix: str = '...') -> str:
    """
    Truncate a string to a maximum length, adding suffix if truncated.
    
    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncating
        
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    
    truncate_at = max_length - len(suffix)
    return text[:truncate_at] + suffix


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in a string (collapse multiple spaces, trim).
    
    Args:
        text: Text to normalize
        
    Returns:
        Normalized text
    """
    # Replace multiple whitespace with single space
    normalized = re.sub(r'\s+', ' ', text)
    # Trim leading/trailing whitespace
    return normalized.strip()


def camel_to_snake(text: str) -> str:
    """
    Convert camelCase string to snake_case.
    
    Args:
        text: CamelCase string
        
    Returns:
        snake_case string
    """
    # Insert underscore before uppercase letters
    snake = re.sub(r'(?<!^)(?=[A-Z])', '_', text)
    return snake.lower()


def snake_to_camel(text: str, capitalize_first: bool = False) -> str:
    """
    Convert snake_case string to camelCase.
    
    Args:
        text: snake_case string
        capitalize_first: Whether to capitalize the first letter
        
    Returns:
        camelCase string
    """
    components = text.split('_')
    if capitalize_first:
        return ''.join(x.capitalize() for x in components)
    else:
        return components[0] + ''.join(x.capitalize() for x in components[1:])


def extract_numbers(text: str) -> List[float]:
    """
    Extract all numbers from a string.
    
    Args:
        text: Text to extract numbers from
        
    Returns:
        List of numbers found
    """
    pattern = r'-?\d+\.?\d*'
    matches = re.findall(pattern, text)
    return [float(m) for m in matches]


def mask_sensitive_data(text: str, pattern: str, replacement: str = '***') -> str:
    """
    Mask sensitive data in a string based on a regex pattern.
    
    Args:
        text: Text containing sensitive data
        pattern: Regex pattern to match sensitive data
        replacement: Replacement string for masked data
        
    Returns:
        Text with masked data
    """
    return re.sub(pattern, replacement, text)


def count_words(text: str) -> int:
    """
    Count the number of words in a string.
    
    Args:
        text: Text to count words in
        
    Returns:
        Word count
    """
    words = re.findall(r'\b\w+\b', text)
    return len(words)
