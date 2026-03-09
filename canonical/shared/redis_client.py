"""
Standalone Redis L1 client for artifacts/canonical.

Adapted from backend/app/core/redis_client.py to be self-contained
(no relative imports from the backend package). Configuration is read
directly from environment variables.

Used by GateKeeper service and can be imported by any component in
artifacts/canonical/ without depending on the backend package.
"""

import logging
import os
from typing import Optional

import redis.asyncio as aioredis
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration from environment variables
# ---------------------------------------------------------------------------

REDIS_L1_HOST: str = os.getenv("REDIS_L1_HOST", "redis-local")
REDIS_L1_PORT: int = int(os.getenv("REDIS_L1_PORT", "6380"))
REDIS_L1_DB: int = int(os.getenv("REDIS_L1_DB", "0"))
REDIS_L1_PASSWORD: Optional[str] = os.getenv("REDIS_L1_PASSWORD", "scarerunner") or None
REDIS_L1_ENABLED: bool = os.getenv("REDIS_L1_ENABLED", "true").lower() == "true"

# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------

_redis_l1_client: Optional[Redis] = None


async def get_redis_client() -> Optional[Redis]:
    """
    Get or create async Redis L1 client instance.

    Returns:
        Redis client or None if Redis is disabled/unavailable.
    """
    global _redis_l1_client

    if not REDIS_L1_ENABLED:
        logger.debug("Redis L1 is disabled in configuration")
        return None

    if _redis_l1_client is not None:
        return _redis_l1_client

    kwargs = {
        "host": REDIS_L1_HOST,
        "port": REDIS_L1_PORT,
        "db": REDIS_L1_DB,
        "decode_responses": True,
        "socket_connect_timeout": 5,
        "socket_keepalive": True,
    }
    if REDIS_L1_PASSWORD:
        kwargs["password"] = REDIS_L1_PASSWORD

    try:
        _redis_l1_client = aioredis.Redis(**kwargs)
        await _redis_l1_client.ping()
        logger.info("Redis L1 client initialized: %s:%s", REDIS_L1_HOST, REDIS_L1_PORT)
        return _redis_l1_client
    except Exception as exc:
        logger.warning("Failed to connect to Redis L1: %s. Caching will be disabled.", exc)
        _redis_l1_client = None
        return None


async def close_redis_client() -> None:
    """Close the Redis L1 client connection."""
    global _redis_l1_client
    if _redis_l1_client is not None:
        try:
            await _redis_l1_client.aclose()
            logger.info("Redis L1 client closed")
        except Exception as exc:
            logger.error("Error closing Redis L1 client: %s", exc)
        finally:
            _redis_l1_client = None


def reset_redis_client() -> None:
    """Reset client singleton (useful for testing)."""
    global _redis_l1_client
    _redis_l1_client = None
