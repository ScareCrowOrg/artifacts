"""
Redis L1 (Local Cache) client setup and utilities for ScareVerse.

Provides async Redis L1 client for local caching and event streaming.
Used by the database cache layer and real-time features.

IMPORTANT: This module handles ONLY Redis L1 (local cache).
For Redis L2 (cluster cache), use CentralHubClient HTTP API instead.
"""

import logging
from typing import Optional

import redis.asyncio as aioredis
from redis.asyncio import Redis

from ..config.database import (
    REDIS_L1_DB,
    REDIS_L1_ENABLED,
    REDIS_L1_HOST,
    REDIS_L1_PASSWORD,
    REDIS_L1_PORT,
)

logger = logging.getLogger(__name__)

# Global Redis L1 client instance
_redis_l1_client: Optional[Redis] = None


async def get_redis_client() -> Optional[Redis]:
    """
    Get or create async Redis L1 (local cache) client instance.

    Returns:
        Redis L1 client instance or None if Redis L1 is disabled or unavailable
    """
    global _redis_l1_client

    if not REDIS_L1_ENABLED:
        logger.debug("Redis L1 is disabled in configuration")
        return None

    if _redis_l1_client is not None:
        return _redis_l1_client

    try:
        _redis_l1_client = aioredis.Redis(
            host=REDIS_L1_HOST,
            port=REDIS_L1_PORT,
            db=REDIS_L1_DB,
            password=REDIS_L1_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
        )

        # Test connection
        await _redis_l1_client.ping()
        logger.info("Redis L1 client initialized: %s:%s", REDIS_L1_HOST, REDIS_L1_PORT)
        return _redis_l1_client

    except Exception as e:
        logger.warning("Failed to connect to Redis L1: %s. Caching will be disabled.", e)
        _redis_l1_client = None
        return None


async def close_redis_client():
    """Close Redis L1 client connection."""
    global _redis_l1_client

    if _redis_l1_client is not None:
        try:
            await _redis_l1_client.close()
            logger.info("Redis L1 client closed")
        except Exception as e:
            logger.error("Error closing Redis L1 client: %s", e)
        finally:
            _redis_l1_client = None


def reset_redis_client():
    """Reset Redis L1 client (for testing)."""
    global _redis_l1_client
    _redis_l1_client = None


async def invalidate_all_cache() -> dict:
    """
    Invalidate all cache keys in Redis L1 (FLUSHDB).

    This operation removes all keys from the current Redis L1 database.
    Use with caution as it will clear all cached data.

    Returns:
        dict: Result containing success status and number of keys deleted

    Raises:
        Exception: If Redis operation fails
    """
    redis = await get_redis_client()

    if redis is None:
        logger.warning("Cannot invalidate cache: Redis L1 is not available")
        return {
            "success": False,
            "message": "Redis L1 is not available",
            "keys_deleted": 0,
        }

    try:
        # Get count of keys before flushing
        keys_count = await redis.dbsize()

        # Flush all keys in current database
        await redis.flushdb(asynchronous=True)

        logger.info("Redis L1 cache invalidated successfully. %s keys deleted.", keys_count)

        return {
            "success": True,
            "message": f"Successfully invalidated L1 cache. {keys_count} keys deleted.",
            "keys_deleted": keys_count,
        }

    except Exception as e:
        logger.error("Error invalidating L1 cache: %s", e)
        raise Exception(f"Failed to invalidate L1 cache: {str(e)}") from e
