"""
Redis cache facade for JSONDatabase.

Provides a caching layer that wraps JSONDatabase to optimize read operations
with lazy loading and TTL-based caching. Write operations persist to disk
and invalidate/update the cache for consistency.

Architecture:
- Read operations: Check cache first, load from disk on miss, then cache
- Write operations: Persist to disk (source of truth), then invalidate cache
- Smart cache key generation based on collection, user, session, and canonical flag
- Configurable TTL per collection type
"""

from .redis_cache_write_ops import RedisCachedJSONDatabase

__all__ = ["RedisCachedJSONDatabase"]
