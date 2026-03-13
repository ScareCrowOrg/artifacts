"""
Redis Coordination Patterns for HybridDatabase.

Provides Redis-based coordination for atomic operations, distributed locking,
and pub/sub patterns for cache synchronization across instances.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional

from redis.asyncio import Redis

from ...core.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class RedisCoordinator:
    """
    Coordinates database operations using Redis primitives.

    Provides:
    - Distributed locks for atomic operations
    - Pub/sub patterns for cache invalidation events
    - Coordination across multiple HybridDatabase instances
    """

    def __init__(self):
        """Initialize Redis coordinator."""
        self._redis_client: Optional[Redis] = None
        self._pubsub = None

    async def _ensure_redis(self) -> Optional[Redis]:
        """
        Ensure Redis client is initialized.

        Returns:
            Redis client or None if unavailable
        """
        if self._redis_client is None:
            self._redis_client = await get_redis_client()
        return self._redis_client

    @asynccontextmanager
    async def distributed_lock(
        self, lock_key: str, timeout: int = 10, blocking_timeout: Optional[int] = None
    ):
        """
        Acquire a distributed lock for atomic operations.

        Usage:
            async with coordinator.distributed_lock("cells:update:cel_123"):
                # Perform atomic operation
                await db.update(...)

        Args:
            lock_key: Unique key for the lock
            timeout: Lock timeout in seconds (default 10)
            blocking_timeout: Max time to wait for lock acquisition (None = wait forever)

        Yields:
            Lock is held during context
        """
        redis = await self._ensure_redis()
        if redis is None:
            logger.warning("Redis unavailable - proceeding without lock")
            yield
            return

        lock = redis.lock(
            name=f"lock:{lock_key}", timeout=timeout, blocking_timeout=blocking_timeout
        )

        try:
            acquired = await lock.acquire()
            if not acquired:
                logger.warning("Failed to acquire lock: %s", lock_key)
                raise TimeoutError(f"Could not acquire lock: {lock_key}")

            logger.debug("Acquired lock: %s", lock_key)
            yield

        finally:
            try:
                await lock.release()
                logger.debug("Released lock: %s", lock_key)
            except Exception as e:
                logger.error("Error releasing lock %s: %s", lock_key, e)

    async def publish_cache_invalidation(
        self,
        collection: str,
        operation: str,
        doc_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """
        Publish cache invalidation event to all HybridDatabase instances.

        Args:
            collection: Collection name
            operation: Operation type (insert, update, delete)
            doc_id: Document ID (if specific document)
            user_id: User ID (if user-scoped)
        """
        redis = await self._ensure_redis()
        if redis is None:
            logger.debug("Redis unavailable - cache invalidation not published")
            return

        import json

        message = {
            "collection": collection,
            "operation": operation,
            "doc_id": doc_id,
            "user_id": user_id,
        }

        channel = "hybrid_db:cache_invalidation"

        try:
            await redis.publish(channel, json.dumps(message))
            logger.debug("Published cache invalidation: %s", message)
        except Exception as e:
            logger.error("Error publishing cache invalidation: %s", e)

    async def subscribe_cache_invalidation(self, callback: Callable[[dict], Any]):
        """
        Subscribe to cache invalidation events.

        Args:
            callback: Async function to call when invalidation event received
        """
        redis = await self._ensure_redis()
        if redis is None:
            logger.warning("Redis unavailable - cannot subscribe to cache invalidation")
            return

        channel = "hybrid_db:cache_invalidation"

        try:
            self._pubsub = redis.pubsub()
            await self._pubsub.subscribe(channel)
            logger.info("Subscribed to cache invalidation on channel: %s", channel)

            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    try:
                        # Parse message as JSON
                        import json

                        data = json.loads(message["data"])
                        await callback(data)
                    except Exception as e:
                        logger.error("Error processing cache invalidation message: %s", e)

        except Exception as e:
            logger.error("Error in cache invalidation subscription: %s", e)

    async def close(self):
        """Close Redis connections."""
        if self._pubsub:
            try:
                await self._pubsub.unsubscribe()
                await self._pubsub.close()
            except Exception as e:
                logger.error("Error closing pubsub: %s", e)

    async def atomic_write_with_cache_sync(
        self,
        write_operation: Callable,
        collection: str,
        doc_id: str,
        user_id: Optional[str] = None,
    ) -> Any:
        """
        Perform atomic write operation with automatic cache synchronization.

        This combines distributed locking and cache invalidation publication
        for a complete atomic write pattern.

        Args:
            write_operation: Async callable that performs the write
            collection: Collection name
            doc_id: Document ID
            user_id: User ID (if applicable)

        Returns:
            Result from write_operation
        """
        lock_key = f"{collection}:{doc_id}"

        async with self.distributed_lock(lock_key):
            # Perform the write operation
            result = await write_operation()

            # Publish cache invalidation event
            await self.publish_cache_invalidation(
                collection=collection, operation="write", doc_id=doc_id, user_id=user_id
            )

            return result


# Global coordinator instance
_coordinator: Optional[RedisCoordinator] = None


def get_coordinator() -> RedisCoordinator:
    """
    Get or create the global Redis coordinator instance.

    Returns:
        RedisCoordinator instance
    """
    global _coordinator
    if _coordinator is None:
        _coordinator = RedisCoordinator()
    return _coordinator
