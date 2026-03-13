"""
Redis Operations Abstraction for Ollama Proxy

Provides dual-mode Redis access (TCP or HTTP via CentralHub) with feature flag.
This allows gradual migration from direct Redis access to HTTP abstraction.

Reference: Phase 1B Redis HTTP Abstraction - Backend Migration
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional, Tuple

import redis

from ..config.database import (
    CENTRALHUB_TIMEOUT,
    CENTRALHUB_URL,
    USE_CENTRALHUB_REDIS,
)

logger = logging.getLogger(__name__)

# Lazy imports for HTTP client (only if feature flag is enabled)
_http_client = None


def _get_http_client():
    """Get or create CentralHub HTTP client (lazy initialization)"""
    global _http_client

    if _http_client is None:
        from ...clients.centralhub_redis_client import CentralHubRedisClient

        # TODO: Get token from auth context or service account
        # For Phase 1B, we'll use a placeholder
        auth_token = os.getenv("CENTRALHUB_SERVICE_TOKEN", "dev_token_placeholder")

        _http_client = CentralHubRedisClient(
            auth_token=auth_token, base_url=CENTRALHUB_URL, timeout=CENTRALHUB_TIMEOUT
        )

        logger.info("CentralHub HTTP client initialized: %s", CENTRALHUB_URL)

    return _http_client


async def rpush_job(
    redis_client: redis.Redis, queue_key: str, job_data: Dict[str, Any]
) -> str:
    """
    Push job to Redis queue (TCP or HTTP based on feature flag).

    Args:
        redis_client: Legacy Redis client (TCP) - ignored if HTTP enabled
        queue_key: Queue key (e.g., OLLAMA_JOBS_QUEUE)
        job_data: Job payload dictionary

    Returns:
        job_id: Job identifier
    """
    job_id = job_data.get("job_id")

    if USE_CENTRALHUB_REDIS:
        # New path: HTTP via CentralHub
        logger.debug("[%s] Using CentralHub HTTP for rpush", job_id)
        http_client = _get_http_client()

        # Extract queue name from key
        queue_name = queue_key.split(":")[-1] if ":" in queue_key else queue_key

        returned_job_id = await http_client.rpush(queue_name, job_data)
        logger.info("[%s] Job enqueued via HTTP: %s", job_id, returned_job_id)
        return returned_job_id
    else:
        # Legacy path: Direct TCP
        logger.debug("[%s] Using direct TCP for rpush", job_id)
        redis_client.rpush(queue_key, json.dumps(job_data))
        logger.info("[%s] Job enqueued via TCP", job_id)
        return job_id


async def brpop_result(
    redis_client: redis.Redis, result_key: str, timeout: int = 300
) -> Optional[Tuple[str, Any]]:
    """
    Block and pop result from Redis (TCP or HTTP based on feature flag).

    Args:
        redis_client: Legacy Redis client (TCP) - ignored if HTTP enabled
        result_key: Result key to wait for
        timeout: Timeout in seconds

    Returns:
        Tuple of (key, result_data) or None if timeout
    """
    job_id = result_key.split(":")[-1] if ":" in result_key else result_key

    if USE_CENTRALHUB_REDIS:
        # New path: HTTP long-polling via CentralHub
        logger.debug("[%s] Using CentralHub HTTP for brpop (long-polling)", job_id)
        http_client = _get_http_client()

        result = await http_client.brpop(job_id, timeout=timeout)

        if result is None:
            logger.warning("[%s] HTTP long-poll timeout after %ss", job_id, timeout)
            return None

        _, result_data = result
        logger.info("[%s] Result received via HTTP", job_id)
        return (result_key, json.dumps(result_data))
    else:
        # Legacy path: Direct TCP with BRPOP
        logger.debug("[%s] Using direct TCP for brpop", job_id)
        result = await asyncio.to_thread(redis_client.brpop, result_key, timeout)

        if result is None:
            logger.warning("[%s] TCP BRPOP timeout after %ss", job_id, timeout)
            return None

        logger.info("[%s] Result received via TCP", job_id)
        return result


async def delete_key(redis_client: redis.Redis, key: str) -> int:
    """
    Delete key from Redis (TCP or HTTP based on feature flag).

    Args:
        redis_client: Legacy Redis client (TCP)
        key: Key to delete

    Returns:
        Number of keys deleted
    """
    if USE_CENTRALHUB_REDIS:
        # New path: HTTP via CentralHub
        logger.debug("Using CentralHub HTTP for delete: %s", key)
        http_client = _get_http_client()
        return await http_client.delete(key)
    else:
        # Legacy path: Direct TCP
        logger.debug("Using direct TCP for delete: %s", key)
        return await asyncio.to_thread(redis_client.delete, key)
