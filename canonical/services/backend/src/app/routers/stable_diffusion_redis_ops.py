"""
Redis Operations Abstraction for Stable Diffusion Queue

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

# Lazy imports for HTTP client
_http_client = None


def _get_http_client():
    """Get or create CentralHub HTTP client (lazy initialization)"""
    global _http_client

    if _http_client is None:
        from ...clients.centralhub_redis_client import CentralHubRedisClient

        auth_token = os.getenv("CENTRALHUB_SERVICE_TOKEN", "dev_token_placeholder")

        _http_client = CentralHubRedisClient(
            auth_token=auth_token, base_url=CENTRALHUB_URL, timeout=CENTRALHUB_TIMEOUT
        )

        logger.info("CentralHub HTTP client initialized for SD: %s", CENTRALHUB_URL)

    return _http_client


async def rpush_job(
    redis_client: redis.Redis, queue_key: str, job_data: Dict[str, Any]
) -> str:
    """Push job to Redis queue (TCP or HTTP based on feature flag)."""
    job_id = job_data.get("job_id")

    if USE_CENTRALHUB_REDIS:
        logger.debug("[%s] Using CentralHub HTTP for rpush (SD)", job_id)
        http_client = _get_http_client()

        queue_name = queue_key.split(":")[-1] if ":" in queue_key else queue_key
        returned_job_id = await http_client.rpush(queue_name, job_data)
        logger.info("[%s] SD job enqueued via HTTP: %s", job_id, returned_job_id)
        return returned_job_id
    else:
        logger.debug("[%s] Using direct TCP for rpush (SD)", job_id)
        redis_client.rpush(queue_key, json.dumps(job_data))
        logger.info("[%s] SD job enqueued via TCP", job_id)
        return job_id


async def brpop_result(
    redis_client: redis.Redis, result_key: str, timeout: int = 300
) -> Optional[Tuple[str, Any]]:
    """Block and pop result from Redis (TCP or HTTP based on feature flag)."""
    job_id = result_key.split(":")[-1] if ":" in result_key else result_key

    if USE_CENTRALHUB_REDIS:
        logger.debug("[%s] Using CentralHub HTTP for brpop (SD long-polling)", job_id)
        http_client = _get_http_client()

        result = await http_client.brpop(job_id, timeout=timeout)

        if result is None:
            logger.warning("[%s] HTTP long-poll timeout after %ss (SD)", job_id, timeout)
            return None

        _, result_data = result
        logger.info("[%s] SD result received via HTTP", job_id)
        return (result_key, json.dumps(result_data))
    else:
        logger.debug("[%s] Using direct TCP for brpop (SD)", job_id)
        result = await asyncio.to_thread(redis_client.brpop, result_key, timeout)

        if result is None:
            logger.warning("[%s] TCP BRPOP timeout after %ss (SD)", job_id, timeout)
            return None

        logger.info("[%s] SD result received via TCP", job_id)
        return result
