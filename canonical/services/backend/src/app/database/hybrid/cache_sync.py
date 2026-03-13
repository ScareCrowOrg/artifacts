"""
Cache Synchronization between File System and MongoDB.

Provides utilities for keeping Redis cache synchronized when data is written
to either file system (JSONDatabase) or MongoDB.
"""

import logging
from typing import Optional

from redis.asyncio import Redis

from ...core.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class CacheSynchronizer:
    """
    Synchronizes cache state between file-based and MongoDB storage.

    When data is written to MongoDB, ensures that:
    1. Redis cache is properly invalidated
    2. File-based cache (if any) is aware of MongoDB changes
    3. Next read gets fresh data from the correct source
    """

    def __init__(self):
        """Initialize cache synchronizer."""
        self._redis_client: Optional[Redis] = None

    async def _ensure_redis(self) -> Optional[Redis]:
        """
        Ensure Redis client is initialized.

        Returns:
            Redis client or None if unavailable
        """
        if self._redis_client is None:
            self._redis_client = await get_redis_client()
        return self._redis_client

    async def invalidate_on_mongodb_write(
        self,
        collection: str,
        doc_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """
        Invalidate cache after MongoDB write operation.

        Args:
            collection: Collection name
            doc_id: Document ID (if specific document)
            user_id: User ID (for scoped invalidation)
            session_id: Session ID (for scoped invalidation)
        """
        redis = await self._ensure_redis()
        if redis is None:
            logger.debug("Redis unavailable - cache invalidation skipped")
            return

        # Build cache key patterns to invalidate
        patterns = []

        # Base pattern for collection
        base_pattern = f"jsondatabase:*:{collection}:runtime"

        # Add user-specific pattern if applicable
        if user_id:
            user_pattern = f"{base_pattern}:user:{user_id}*"
            patterns.append(user_pattern)

        # Add session-specific pattern if applicable
        if user_id and session_id:
            session_pattern = f"{base_pattern}:user:{user_id}:session:{session_id}*"
            patterns.append(session_pattern)

        # Add document-specific pattern if applicable
        if doc_id:
            if user_id and session_id:
                doc_pattern = (
                    f"{base_pattern}:user:{user_id}:session:{session_id}:doc:{doc_id}"
                )
                patterns.append(doc_pattern)
            else:
                doc_pattern = f"{base_pattern}:*:doc:{doc_id}"
                patterns.append(doc_pattern)

        # Invalidate all matching patterns
        for pattern in patterns:
            try:
                cursor = 0
                while True:
                    cursor, keys = await redis.scan(cursor, match=pattern, count=100)
                    if keys:
                        await redis.delete(*keys)
                        logger.debug("Invalidated %s cache keys matching: %s", len(keys), pattern)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.error("Error invalidating cache pattern %s: %s", pattern, e)

    async def invalidate_collection(
        self, collection: str, user_id: Optional[str] = None
    ):
        """
        Invalidate all cache entries for a collection.

        Args:
            collection: Collection name
            user_id: User ID (if user-scoped)
        """
        await self.invalidate_on_mongodb_write(collection=collection, user_id=user_id)

    async def warm_cache_from_mongodb(
        self,
        collection: str,
        doc_id: str,
        data: dict,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ttl: int = 3600,
    ):
        """
        Warm Redis cache with MongoDB data after read.

        Args:
            collection: Collection name
            doc_id: Document ID
            data: Document data (as dict)
            user_id: User ID
            session_id: Session ID
            ttl: Time-to-live in seconds
        """
        redis = await self._ensure_redis()
        if redis is None:
            return

        # Build cache key
        cache_key_parts = ["jsondatabase", "find_one", collection, "runtime"]

        if user_id and session_id:
            cache_key_parts.extend(
                ["user", user_id, "session", session_id, "doc", doc_id]
            )
        elif user_id:
            cache_key_parts.extend(["user", user_id, "doc", doc_id])
        else:
            cache_key_parts.extend(["doc", doc_id])

        cache_key = ":".join(cache_key_parts)

        try:
            import json

            await redis.setex(cache_key, ttl, json.dumps(data))
            logger.debug("Warmed cache for %s (TTL: %ss)", cache_key, ttl)
        except Exception as e:
            logger.error("Error warming cache: %s", e)

    async def sync_file_to_mongodb(
        self,
        collection: str,
        doc_id: str,
        _user_id: Optional[str] = None,
        _session_id: Optional[str] = None,
    ):
        """
        Trigger synchronization from file system to MongoDB (if needed).

        This is a placeholder for future bidirectional sync functionality.
        Currently, HybridDatabase routes writes to one backend only.

        Args:
            collection: Collection name
            doc_id: Document ID
            user_id: User ID
            session_id: Session ID
        """
        logger.debug("Sync file->MongoDB not implemented for %s/%s", collection, doc_id)
        # TODO: Implement if bidirectional sync is needed

    async def check_consistency(
        self,
        collection: str,
        doc_id: str,
        _user_id: Optional[str] = None,
        _session_id: Optional[str] = None,
    ) -> dict:
        """
        Check consistency between file system and MongoDB for a document.

        Args:
            collection: Collection name
            doc_id: Document ID
            user_id: User ID
            session_id: Session ID

        Returns:
            Dictionary with consistency status
        """
        # This is a diagnostic tool for verifying data consistency
        # Returns info about where the document exists
        result = {
            "collection": collection,
            "doc_id": doc_id,
            "exists_in_files": False,
            "exists_in_mongodb": False,
            "cached_in_redis": False,
            "consistent": True,
            "discrepancies": [],
        }

        # TODO: Implement actual consistency checks
        logger.debug("Consistency check for %s/%s: %s", collection, doc_id, result)
        return result


# Global synchronizer instance
_synchronizer: Optional[CacheSynchronizer] = None


def get_synchronizer() -> CacheSynchronizer:
    """
    Get or create the global cache synchronizer instance.

    Returns:
        CacheSynchronizer instance
    """
    global _synchronizer
    if _synchronizer is None:
        _synchronizer = CacheSynchronizer()
    return _synchronizer
