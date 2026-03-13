"""
Data utility functions for the backend application.

This module provides functions for data processing and manipulation including:
- Safe JSON operations
- Dictionary merging and flattening
- List chunking and deduplication
- Dictionary filtering

Following naming convention Rule 1.3: Using 'backend_data_utils' instead of
generic 'data_utils' to avoid namespace conflicts.
"""

import json
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def safe_json_loads(json_string: str, default: Any = None) -> Any:
    """
    Safely load JSON, returning default value on error.
    
    Args:
        json_string: JSON string to parse
        default: Default value to return on error
        
    Returns:
        Parsed JSON or default value
    """
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to parse JSON: {e}")
        return default


def safe_json_dumps(data: Any, default: Any = None, **kwargs) -> Optional[str]:
    """
    Safely serialize data to JSON, returning None on error.
    
    Args:
        data: Data to serialize
        default: Default value to return on error
        **kwargs: Additional arguments for json.dumps
        
    Returns:
        JSON string or None
    """
    try:
        return json.dumps(data, **kwargs)
    except (TypeError, ValueError) as e:
        logger.warning(f"Failed to serialize to JSON: {e}")
        return default


def merge_dicts(dict1: Dict, dict2: Dict, deep: bool = False) -> Dict:
    """
    Merge two dictionaries.
    
    Args:
        dict1: First dictionary
        dict2: Second dictionary (takes precedence)
        deep: Whether to perform deep merge for nested dicts
        
    Returns:
        Merged dictionary
    """
    if not deep:
        return {**dict1, **dict2}
    
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value, deep=True)
        else:
            result[key] = value
    
    return result


def flatten_dict(data: Dict, parent_key: str = '', sep: str = '.') -> Dict:
    """
    Flatten a nested dictionary.
    
    Args:
        data: Dictionary to flatten
        parent_key: Prefix for keys (used in recursion)
        sep: Separator for nested keys
        
    Returns:
        Flattened dictionary
    """
    items = []
    for key, value in data.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        if isinstance(value, dict):
            items.extend(flatten_dict(value, new_key, sep=sep).items())
        else:
            items.append((new_key, value))
    
    return dict(items)


def chunk_list(data: List, chunk_size: int) -> List[List]:
    """
    Split a list into chunks of specified size.
    
    Args:
        data: List to chunk
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
    """
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]


def remove_duplicates(data: List, key: Optional[callable] = None) -> List:
    """
    Remove duplicates from a list while preserving order.
    
    Args:
        data: List to deduplicate
        key: Optional function to extract comparison key
        
    Returns:
        List without duplicates
    """
    if key is None:
        seen = set()
        result = []
        for item in data:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result
    else:
        seen = set()
        result = []
        for item in data:
            k = key(item)
            if k not in seen:
                seen.add(k)
                result.append(item)
        return result


def filter_dict_by_keys(data: Dict, keys: List[str], include: bool = True) -> Dict:
    """
    Filter dictionary by including or excluding specified keys.
    
    Args:
        data: Dictionary to filter
        keys: List of keys to include/exclude
        include: If True, include only specified keys; if False, exclude them
        
    Returns:
        Filtered dictionary
    """
    if include:
        return {k: v for k, v in data.items() if k in keys}
    else:
        return {k: v for k, v in data.items() if k not in keys}
