"""
Redis Client Management for 3D Mesh Generation Job Queue

Provides Redis client initialization and connection management for
hybrid Windows Worker integration.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def get_redis_client() -> Any:
    """
    Get Redis client for job queueing.
    
    Attempts to import from core backend app first, falls back to
    standalone Redis client for direct script execution.
    
    Returns:
        Redis client instance with async support
        
    Raises:
        Exception: If Redis connection fails
    """
    try:
        # Try to import from core (when running as part of backend app)
        try:
            from app.core.redis_client import get_redis_client as get_core_redis
            return await get_core_redis()
        except (ImportError, ModuleNotFoundError):
            # Fallback: create Redis client directly (standalone execution)
            import redis.asyncio as redis
            import os
            
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            logger.info(f"Creating standalone Redis client: {redis_url}")
            return redis.from_url(redis_url, decode_responses=True)
    except Exception as e:
        logger.error(f"Failed to get Redis client: {e}")
        raise
