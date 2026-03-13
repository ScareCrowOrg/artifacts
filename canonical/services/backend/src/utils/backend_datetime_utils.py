"""
Date/time utility functions for the backend application.

This module provides functions for date and time operations including:
- Timestamp formatting and parsing
- Timedelta creation
- Timestamp expiration checking

Following naming convention Rule 1.3: Using 'backend_datetime_utils' instead of
generic 'datetime_utils' to avoid namespace conflicts.
"""

from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def format_timestamp(timestamp: Optional[datetime] = None, format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
    """
    Format a timestamp as a string.
    
    Args:
        timestamp: Datetime object (default: current time)
        format_str: Format string
        
    Returns:
        Formatted timestamp string
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    return timestamp.strftime(format_str)


def parse_timestamp(timestamp_str: str, format_str: str = '%Y-%m-%d %H:%M:%S') -> Optional[datetime]:
    """
    Parse a timestamp string into a datetime object.
    
    Args:
        timestamp_str: Timestamp string
        format_str: Format string
        
    Returns:
        Datetime object or None if parsing fails
    """
    try:
        return datetime.strptime(timestamp_str, format_str)
    except ValueError as e:
        logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}")
        return None


def get_time_delta(
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    seconds: int = 0
) -> timedelta:
    """
    Create a timedelta object from components.
    
    Args:
        days: Number of days
        hours: Number of hours
        minutes: Number of minutes
        seconds: Number of seconds
        
    Returns:
        Timedelta object
    """
    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)


def is_timestamp_expired(timestamp: datetime, expiry_seconds: int) -> bool:
    """
    Check if a timestamp has expired.
    
    Args:
        timestamp: Timestamp to check
        expiry_seconds: Expiry time in seconds
        
    Returns:
        True if expired, False otherwise
    """
    now = datetime.now()
    age = (now - timestamp).total_seconds()
    return age > expiry_seconds
