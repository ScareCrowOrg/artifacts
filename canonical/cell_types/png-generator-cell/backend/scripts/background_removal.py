"""
Background Removal Integration for PNG Generator Cell

Provides GPU-accelerated background removal by delegating to the
Windows Worker via Redis queue.
"""

import logging
import uuid
import time
import json
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Result key prefix must match GateKeeper config
_REMBG_RESULT_KEY_PREFIX = "scareverse:rembg-results"
_REMBG_RESULT_TTL = 120


async def queue_background_removal_job(
    input_image_base64: str,
    alpha_matting: bool = True,
    timeout: float = 60.0
) -> Dict[str, Any]:
    """
    Queue a background removal job to Redis for GPU Worker processing.

    This function:
    1. Calls redis_job_client.create_job() with owner-first scheduling
       (checks worker availability; enqueues to L1 if available, L2 otherwise)
    2. Uses BRPOP to wait for the result pushed by GateKeeper to L1
    3. Returns the transparent PNG result

    Args:
        input_image_base64: Base64-encoded input image (with or without data URI prefix)
        alpha_matting: Enable alpha matting for better edge quality (default: True)
        timeout: Maximum time to wait for job completion in seconds

    Returns:
        Dict containing:
            - success: Boolean indicating success/failure
            - output_image_base64: Base64-encoded transparent PNG (if success)
            - error: Error message (if failure)
            - job_id: Unique job identifier
            - processing_time: Time taken by GPU worker

    Raises:
        Exception: If Redis connection fails or job times out
    """
    job_id = None
    try:
        job_id = str(uuid.uuid4())
        logger.info("Queueing background removal job: %s", job_id)

        # Strip data URI prefix if present
        if ',' in input_image_base64:
            input_image_base64 = input_image_base64.split(',', 1)[1]

        # Build job payload
        payload = {
            "image_data": input_image_base64,
            "alpha_matting": alpha_matting,
            "timestamp": time.time(),
        }

        # Enqueue via unified redis_job_client (owner-first scheduling)
        try:
            from app.services.redis_job_client import create_job
            enqueued_job_id, location = await create_job(
                job_type="rembg_removebackground",
                payload=payload,
                owner_user_id="cell-script",
                job_id=job_id,
            )
            logger.info("Job enqueued via redis_job_client to %s: %s", location, job_id)
        except (ImportError, ModuleNotFoundError):
            # Fallback: direct LPUSH when running outside backend app context.
            # Matches the job_data structure that create_job() would produce.
            logger.warning("redis_job_client not available; using direct LPUSH fallback")
            redis_client = await _get_redis_client()
            job_data = {
                "job_id": job_id,
                "job_type": "rembg_removebackground",
                "user_id": "cell-script",
                "queue": "scareverse:cpu-jobs:queue",
                **payload,
            }
            await redis_client.lpush("scareverse:cpu-jobs:queue", json.dumps(job_data))

        # Wait for result via BRPOP (GateKeeper pushes result to this key)
        redis_client = await _get_redis_client()
        result_key = f"{_REMBG_RESULT_KEY_PREFIX}:{job_id}"
        result = await brpop_result(redis_client, result_key, timeout)

        if result is None:
            logger.error("Background removal timeout: %s", job_id)
            return {
                "success": False,
                "error": f"Job did not complete within {timeout} seconds",
                "job_id": job_id,
            }

        if result.get("status") == "error":
            error_msg = result.get("error", "Unknown error")
            logger.error("Background removal failed: %s – %s", job_id, error_msg)
            return {
                "success": False,
                "error": error_msg,
                "job_id": job_id,
            }

        logger.info("Background removal completed: %s", job_id)
        return {
            "success": True,
            "output_image_base64": result.get("result", ""),
            "job_id": job_id,
            "processing_time": result.get("processing_time", 0),
        }

    except Exception as e:
        logger.error("Failed to queue background removal job: %s", e, exc_info=True)
        return {
            "success": False,
            "error": f"Failed to queue job: {str(e)}",
            "job_id": job_id,
        }


async def brpop_result(
    redis_client,
    result_key: str,
    timeout: float = 60.0,
) -> Optional[Dict[str, Any]]:
    """
    Wait for a job result via BRPOP from Redis L1.

    GateKeeper pushes the result JSON to `result_key` via RPUSH after the
    atomic worker completes. This function blocks until the result arrives
    or the timeout elapses.

    Args:
        redis_client: Redis client instance
        result_key: Full Redis key to BRPOP from
        timeout: Maximum time to wait in seconds

    Returns:
        Parsed result dict, or None on timeout
    """
    logger.debug(f"Waiting for result via BRPOP: key={result_key} timeout={timeout}s")
    try:
        result = await redis_client.brpop(result_key, timeout=timeout)
        if result is None:
            return None
        _key, raw_value = result
        return json.loads(raw_value)
    except Exception as e:
        logger.error(f"BRPOP failed for key {result_key}: {e}")
        return None


async def _get_redis_client():
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
            # Use Redis L1 (local cache), not L2
            import redis.asyncio as redis
            import os

            redis_host = os.getenv('REDIS_L1_HOST', 'redis-local')
            redis_port = int(os.getenv('REDIS_L1_PORT', '6380'))
            redis_password = os.getenv('REDIS_L1_PASSWORD', 'scarerunner')
            redis_db = int(os.getenv('REDIS_L1_DB', '0'))

            redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
            logger.info(f"Creating standalone Redis L1 client: {redis_host}:{redis_port}")
            return redis.from_url(redis_url, decode_responses=True)
    except Exception as e:
        logger.error(f"Failed to get Redis client: {e}")
        raise


# Synchronous wrapper for backward compatibility
def queue_background_removal_job_sync(
    input_image_base64: str,
    alpha_matting: bool = True,
    timeout: float = 60.0
) -> Dict[str, Any]:
    """
    Synchronous wrapper for queue_background_removal_job.
    
    Uses asyncio.run to execute the async function.
    Useful for non-async contexts.
    
    Args:
        input_image_base64: Base64-encoded input image
        alpha_matting: Enable alpha matting
        timeout: Maximum wait time
        
    Returns:
        Dict with job result
    """
    return asyncio.run(queue_background_removal_job(
        input_image_base64=input_image_base64,
        alpha_matting=alpha_matting,
        timeout=timeout
    ))


if __name__ == "__main__":
    # Test script for standalone execution
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python background_removal.py <base64_image>")
        sys.exit(1)
    
    input_image = sys.argv[1]
    result = queue_background_removal_job_sync(input_image)
    
    print(json.dumps(result, indent=2))

