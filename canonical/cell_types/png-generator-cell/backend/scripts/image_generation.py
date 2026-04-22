"""
Image Generation Integration for PNG Generator Cell

Provides GPU-accelerated image generation via Stable Diffusion by delegating to
the Windows Worker via Redis queue using canonical redis_client.
"""

import logging
import uuid
import time
import json
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Redis L1 client from canonical shared (single source of truth)
try:
    from canonical.shared.redis_client import get_redis_client
except ImportError:
    # Local dev fallback: add shared to path
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / 'shared'))
    from redis_client import get_redis_client

# Result key prefix must match stable_diffusion_queue router config
_SD_RESULT_KEY_PREFIX = "scareverse:sd-results"
_SD_RESULT_TTL = 300


async def queue_image_generation_job(
    prompt: str,
    negative_prompt: str = "",
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg_scale: float = 7.5,
    seed: int = -1,
    model: str = "stabilityai/stable-diffusion-xl-base-1.0",
    timeout: float = 300.0
) -> Dict[str, Any]:
    """
    Queue an image generation job to Redis for GPU Worker processing.

    This function:
    1. Calls redis_job_client.create_job() with owner-first scheduling
       (checks worker availability; enqueues to L1 if available, L2 otherwise)
    2. Uses BRPOP to wait for the result pushed by GateKeeper to L1
    3. Returns the generated PNG result

    Args:
        prompt: Text description of the desired image
        negative_prompt: Things to avoid in generation (optional)
        width: Image width in pixels (256-1024)
        height: Image height in pixels (256-1024)
        steps: Number of denoising steps (1-100)
        cfg_scale: Classifier-free guidance scale
        seed: Random seed (-1 for random)
        model: HuggingFace model ID
        timeout: Maximum time to wait for job completion in seconds

    Returns:
        Dict containing:
            - success: Boolean indicating success/failure
            - image_base64: Base64-encoded PNG (if success)
            - error: Error message (if failure)
            - job_id: Unique job identifier
            - processing_time: Time taken by GPU worker

    Raises:
        Exception: If Redis connection fails or job times out
    """
    job_id = None
    try:
        job_id = str(uuid.uuid4())
        logger.info("Queueing image generation job: %s", job_id)

        # Build job payload (matches SD worker expectations)
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "num_inference_steps": steps,
            "guidance_scale": cfg_scale,
            "seed": seed,
            "model": model,
            "timestamp": time.time(),
        }

        # Enqueue via unified redis_job_client (owner-first scheduling)
        try:
            from app.services.redis_job_client import create_job
            enqueued_job_id, location = await create_job(
                job_type="sd_generate",
                payload=payload,
                owner_user_id="cell-script",
                job_id=job_id,
            )
            logger.info("Job enqueued via redis_job_client to %s: %s", location, job_id)
        except (ImportError, ModuleNotFoundError):
            # Fallback: direct LPUSH when running outside backend app context.
            # Matches the job_data structure that create_job() would produce.
            logger.warning("redis_job_client not available; using direct LPUSH fallback")
            redis_client = await get_redis_client()
            job_data = {
                "job_id": job_id,
                "job_type": "sd_generate",
                "user_id": "cell-script",
                "queue": "scareverse:gpu-jobs:queue",
                **payload,
            }
            await redis_client.lpush("scareverse:gpu-jobs:queue", json.dumps(job_data))

        # Wait for result via BRPOP (GateKeeper pushes result to this key)
        redis_client = await get_redis_client()
        result_key = f"{_SD_RESULT_KEY_PREFIX}:{job_id}"
        result = await brpop_result(redis_client, result_key, timeout)

        if result is None:
            logger.error("Image generation timeout: %s", job_id)
            return {
                "success": False,
                "error": f"Job did not complete within {timeout} seconds",
                "job_id": job_id,
            }

        if result.get("status") == "error":
            error_msg = result.get("error", "Unknown error")
            logger.error("Image generation failed: %s – %s", job_id, error_msg)
            return {
                "success": False,
                "error": error_msg,
                "job_id": job_id,
            }

        logger.info("Image generation completed: %s", job_id)
        return {
            "success": True,
            "image_base64": result.get("image_base64", ""),
            "job_id": job_id,
            "processing_time": result.get("processing_time_ms", 0),
            "metadata": {
                "model": result.get("model", model),
                "prompt": prompt,
            }
        }

    except Exception as e:
        logger.error("Failed to queue image generation job: %s", e, exc_info=True)
        return {
            "success": False,
            "error": f"Failed to queue job: {str(e)}",
            "job_id": job_id,
        }


async def brpop_result(
    redis_client,
    result_key: str,
    timeout: float = 300.0,
) -> Optional[Dict[str, Any]]:
    """
    Wait for a job result via BRPOP from Redis L1.

    GateKeeper pushes the result JSON to `result_key` via RPUSH after the
    worker completes. This function blocks until the result arrives
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


# Synchronous wrapper for backward compatibility
def queue_image_generation_job_sync(
    prompt: str,
    negative_prompt: str = "",
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg_scale: float = 7.5,
    seed: int = -1,
    model: str = "stabilityai/stable-diffusion-xl-base-1.0",
    timeout: float = 300.0
) -> Dict[str, Any]:
    """
    Synchronous wrapper for queue_image_generation_job.

    Uses asyncio.run to execute the async function.
    Useful for non-async contexts.

    Args:
        prompt: Text description of the desired image
        negative_prompt: Things to avoid in generation
        width: Image width in pixels
        height: Image height in pixels
        steps: Number of denoising steps
        cfg_scale: Classifier-free guidance scale
        seed: Random seed (-1 for random)
        model: HuggingFace model ID
        timeout: Maximum wait time

    Returns:
        Dict with job result
    """
    return asyncio.run(queue_image_generation_job(
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        steps=steps,
        cfg_scale=cfg_scale,
        seed=seed,
        model=model,
        timeout=timeout
    ))


if __name__ == "__main__":
    # Test script for standalone execution
    import sys

    if len(sys.argv) < 2:
        print("Usage: python image_generation.py '<prompt>'")
        sys.exit(1)

    prompt = sys.argv[1]
    result = queue_image_generation_job_sync(prompt)

    print(json.dumps(result, indent=2))
