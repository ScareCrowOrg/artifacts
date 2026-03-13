"""
Backward compatibility shim for redis_cache module.

This file maintains backward compatibility by re-exporting RedisCachedJSONDatabase
from the modularized redis_cache package.

For new code, prefer importing from the package:
    from app.database.redis_cache import RedisCachedJSONDatabase
"""

from .redis_cache import RedisCachedJSONDatabase

__all__ = ["RedisCachedJSONDatabase"]
