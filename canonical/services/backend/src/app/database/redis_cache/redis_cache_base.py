"""
Redis Cache Base Utilities

Provides base utilities for Redis-cached JSONDatabase operations including
cache key generation, TTL management, and Redis client initialization.

NOTE on cyclic imports (R0401):
  This module imports JSONDatabase from database.connection, which creates
  a cycle:
    database.__init__ → hybrid → hybrid.router → redis_cache
    → redis_cache_base → database.connection → database.__init__
  The cycle is broken at runtime by the lazy __getattr__ in database/__init__.py
  (HybridDatabase / RedisCachedJSONDatabase are only imported on first attribute
  access, after connection is fully initialised).
"""
# pylint: disable=cyclic-import

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

from redis.asyncio import Redis

from ...config.database import (
    REDIS_CACHE_ENABLED,
    REDIS_CACHE_TTL,
    REDIS_CACHE_TTL_CANONICAL,
    REDIS_CACHE_TTL_CELULAS,
    REDIS_CACHE_TTL_CONFIG,
    REDIS_CACHE_TTL_LIVROS,
)
from ...core.redis_client import get_redis_client
from ..connection import JSONDatabase

logger = logging.getLogger(__name__)


class RedisCacheBase(JSONDatabase):
    """
    Base class for Redis-cached JSON database operations.

    Provides utilities for cache key generation, TTL management,
    and Redis client initialization.
    """

    def __init__(self, base_path: Optional[Path] = None, is_test_env: bool = False):
        """
        Initialize the cached database.

        Args:
            base_path: Base path for artifact storage
            is_test_env: Flag to indicate if running in a test environment
        """
        super().__init__(base_path=base_path, is_test_env=is_test_env)
        self._redis_client: Optional[Redis] = None
        self._cache_enabled = REDIS_CACHE_ENABLED

    async def _ensure_redis(self) -> Optional[Redis]:
        """
        Ensure Redis client is initialized.

        Returns:
            Redis client or None if disabled/unavailable
        """
        if not self._cache_enabled:
            return None

        if self._redis_client is None:
            self._redis_client = await get_redis_client()

        return self._redis_client

    def _get_cache_key(
        self,
        operation: str,
        collection: str,
        doc_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
        field: Optional[str] = None,
        value: Optional[any] = None,
        fields: Optional[dict] = None,
    ) -> str:
        """
        Generate a unique cache key for an operation.

        Args:
            operation: Operation type (find_one, find_many, etc.)
            collection: Collection name
            doc_id: Document ID
            user_id: User ID
            session_id: Session ID
            is_canonical: Whether this is a canonical artifact
            field: Field name for find_by_field
            value: Field value for find_by_field
            fields: Fields dict for find_by_fields

        Returns:
            Unique cache key string
        """
        key_parts = [
            "jsondatabase",
            operation,
            collection,
            "canonical" if is_canonical else "runtime",
        ]

        if doc_id:
            key_parts.append(f"id:{doc_id}")
        if user_id:
            key_parts.append(f"user:{user_id}")
        if session_id:
            key_parts.append(f"session:{session_id}")
        if field and value is not None:
            # Create hash for value to handle complex types
            value_str = str(value)
            value_hash = hashlib.md5(value_str.encode()).hexdigest()[:8]
            key_parts.append(f"field:{field}:{value_hash}")
        if fields:
            # Create hash for fields dict
            fields_str = json.dumps(fields, sort_keys=True)
            fields_hash = hashlib.md5(fields_str.encode()).hexdigest()[:8]
            key_parts.append(f"fields:{fields_hash}")

        return ":".join(key_parts)

    def _get_ttl(self, collection: str, is_canonical: bool = False) -> int:
        """
        Get TTL for a collection.

        Args:
            collection: Collection name
            is_canonical: Whether this is a canonical artifact

        Returns:
            TTL in seconds
        """
        if is_canonical:
            return REDIS_CACHE_TTL_CANONICAL

        # Collection-specific TTLs
        ttl_map = {
            "cells": REDIS_CACHE_TTL_CELULAS,
            "books": REDIS_CACHE_TTL_LIVROS,
            "config": REDIS_CACHE_TTL_CONFIG,
        }

        return ttl_map.get(collection, REDIS_CACHE_TTL)

    async def _invalidate_cache_pattern(self, pattern: str):
        """
        Invalidate all cache keys matching a pattern.

        Args:
            pattern: Redis key pattern (supports wildcards)
        """
        redis = await self._ensure_redis()
        if redis is None:
            return

        try:
            # Scan and delete matching keys
            cursor = 0
            deleted_count = 0
            while True:
                cursor, keys = await redis.scan(cursor, match=pattern, count=100)
                if keys:
                    deleted_count += await redis.delete(*keys)
                if cursor == 0:
                    break

            if deleted_count > 0:
                logger.debug("Invalidated %s cache keys matching '%s'", deleted_count, pattern)
        except Exception as e:
            logger.error("Error invalidating cache pattern '%s': %s", pattern, e)
