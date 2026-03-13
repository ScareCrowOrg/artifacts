"""
JSON serialization utilities for handling non-serializable types.

This module provides utilities for safely converting Python objects
to JSON-serializable formats, with special handling for datetime objects
and nested data structures.
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)


def serialize_for_json(obj: Any) -> Any:
    """
    Recursively convert an object to a JSON-serializable format.

    Handles:
    - datetime/date objects -> ISO format strings
    - Dictionaries -> recursively process values
    - Lists/tuples -> recursively process items
    - Other types -> pass through unchanged

    Args:
        obj: Any Python object to serialize

    Returns:
        JSON-serializable version of the object

    Examples:
        >>> from datetime import datetime
        >>> data = {"created_at": datetime(2023, 1, 1, 12, 0, 0)}
        >>> serialize_for_json(data)
        {"created_at": "2023-01-01T12:00:00"}

        >>> nested = {"user": {"joined": datetime(2023, 1, 1)}, "count": 5}
        >>> serialize_for_json(nested)
        {"user": {"joined": "2023-01-01T00:00:00"}, "count": 5}
    """
    # Handle datetime and date objects
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    # Handle dictionaries recursively
    if isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}

    # Handle lists and tuples recursively
    if isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]

    # Handle Pydantic models with model_dump
    if hasattr(obj, "model_dump"):
        try:
            # Get dict representation and recursively serialize
            dumped = obj.model_dump()
            return serialize_for_json(dumped)
        except Exception as e:
            logger.error("Failed to serialize Pydantic model: %s", e, exc_info=True)
            # Return a structured error object instead of string representation
            return {
                "error": "PydanticSerializationError",
                "model_type": type(obj).__name__,
                "message": str(e),
            }

    # Pass through other types unchanged
    # (None, bool, int, float, str are already JSON-serializable)
    return obj


def safe_json_serialize(
    data: Union[Dict[str, Any], List[Any], Any],
) -> Union[Dict[str, Any], List[Any], Any]:
    """
    Safely serialize data for JSON encoding.

    This is a convenience wrapper around serialize_for_json with additional
    error handling and logging.

    Args:
        data: Data to serialize (typically a dict or list)

    Returns:
        JSON-serializable version of the data
    """
    try:
        return serialize_for_json(data)
    except Exception as e:
        logger.error("Error during JSON serialization: %s", e, exc_info=True)
        # Return a safe error representation
        return {"error": "Serialization failed", "message": str(e)}
