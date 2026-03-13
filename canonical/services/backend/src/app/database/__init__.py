"""
Database module - Hybrid storage system for ScareVerse.

This module provides an intelligent hybrid storage solution that routes data
between file-based storage (canonical) and MongoDB (runtime).

Main exports:
- JSONDatabase: Core file-based database class with CRUD operations
- RedisCachedJSONDatabase: Redis-cached wrapper for optimized reads
- HybridDatabase: Intelligent router between file-based and MongoDB storage (PRIMARY)
- get_db_instance: Function to get the appropriate database instance
- db: Lazy proxy to the global database instance (initialized during lifespan)

NOTE on cyclic imports (R0401):
  HybridDatabase and RedisCachedJSONDatabase are loaded lazily (via module
  __getattr__) to break the static import cycle:
    database.connection → database.__init__ → hybrid → hybrid.router
    → redis_cache → redis_cache_base → database.connection
  All cross-module calls complete at runtime without hitting a partially-
  initialised module.
"""
# pylint: disable=cyclic-import

from . import connection
from .connection import JSONDatabase, get_db_instance

# HybridDatabase and RedisCachedJSONDatabase are loaded lazily via __getattr__ below.
# Eager top-level imports create a cyclic-import chain:
#   database.connection → database.__init__ → hybrid → hybrid.router
#   → redis_cache → redis_cache_base → database.connection
# Using module-level __getattr__ defers those imports until first access,
# which breaks the cycle without affecting external callers.


def __getattr__(name: str):
    """Lazily import heavy sub-modules to avoid cyclic imports."""
    if name == "HybridDatabase":
        from .hybrid import HybridDatabase  # noqa: PLC0415
        return HybridDatabase
    if name == "RedisCachedJSONDatabase":
        from .redis_cache import RedisCachedJSONDatabase  # noqa: PLC0415
        return RedisCachedJSONDatabase
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class _DatabaseProxy:
    """
    Proxy object that lazily delegates to the global db instance.

    This allows `from ..database import db` to work at import time (when db is None),
    but then transparently delegate to the actual initialized instance when methods
    are called at runtime.
    """

    def __getattr__(self, name):
        """Delegate attribute access to the current global db instance."""
        if connection.db is None:
            raise RuntimeError(
                "Database not initialized. Ensure initialize_db() is called during app lifespan."
            )
        return getattr(connection.db, name)

    def __await__(self):
        """Support for async iteration."""
        if connection.db is None:
            raise RuntimeError(
                "Database not initialized. Ensure initialize_db() is called during app lifespan."
            )
        return connection.db.__await__()


# Create a single proxy instance that routers can import
db = _DatabaseProxy()

__all__ = [
    "JSONDatabase",
    "RedisCachedJSONDatabase",
    "HybridDatabase",
    "get_db_instance",
    "db",
]
