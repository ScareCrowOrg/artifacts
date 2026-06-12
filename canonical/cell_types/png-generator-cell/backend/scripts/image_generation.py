"""
Image Generation Integration for PNG Generator Cell

Provides GPU-accelerated image generation via ComfyUI by delegating to
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

# Result key prefix must match comfyui_generate queue router config
_COMFYUI_RESULT_KEY_PREFIX = "scareverse:comfyui-results"
_COMFYUI_RESULT_TTL = 300


async def queue_image_generation_job(
    prompt: str,
    negative_prompt: str = "",
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg_scale: float = 7.5,
    seed: int = -1,
    model: str = "stabilityai/stable-diffusion-xl-base-1.0",
    timeout: float = 300.0,
    assignee_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Queue an image generation job to Redis for ComfyUI GPU Worker processing.

    This function:
    1. Calls redis_job_client.create_job() with owner-first scheduling
       (checks worker availability; enqueues to L1 if available, L2 otherwise)
    2. Uses BRPOP to wait for the result pushed by GateKeeper to L1
    3. Returns the base64-encoded PNG result

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
        assignee_id: User ID for Redis Magro content reference.
            When provided, the worker saves the PNG to disk at
            runtime/user/{assignee_id}/contents/{job_id}/{filename}.png
            instead of returning image_base64 inline (~300KB).

    Returns:
        Dict containing:
            - success: Boolean indicating success/failure
            - image_base64: Base64-encoded PNG (if success, legacy format)
            - relative_url: Content reference URL (if success, Redis Magro format)
            - content_id: Content identifier (if success, Redis Magro format)
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
        # Redis Magro: add assignee_id and content_id so the worker can save PNG to disk
        # When assignee_id is provided, worker saves to runtime/user/{assignee_id}/contents/{job_id}/
        # and returns a lightweight content reference instead of ~300KB base64
        if assignee_id:
            payload["assignee_id"] = assignee_id
            payload["content_id"] = job_id
        # DIAG: Log payload completeness — confirm assignee_id and content_id are now present
        logger.debug("IMAGE-GEN-DEBUG: payload keys=%s, assignee_id=%s, content_id=%s",
                     list(payload.keys()),
                     payload.get("assignee_id", "MISSING"),
                     payload.get("content_id", "MISSING"))

        # Enqueue via canonical redis_client (owner-first scheduling, single source of truth)
        try:
            from canonical.shared.redis_client import create_job
            enqueued_job_id, location = await create_job(
                job_type="comfyui_generate",
                payload=payload,
                owner_user_id="cell-script",
                job_id=job_id,
            )
            logger.info("Job enqueued via canonical redis_client to %s: %s", location, job_id)
        except Exception as e:
            # Fallback: direct LPUSH when create_job fails
            logger.warning("canonical create_job unavailable (%s); using direct LPUSH fallback", e)
            redis_client = await get_redis_client()
            job_data = {
                "job_id": job_id,
                "job_type": "comfyui_generate",
                "user_id": "cell-script",
                "queue": "scareverse:comfyui-jobs:queue",
                **payload,
            }
            await redis_client.lpush("scareverse:comfyui-jobs:queue", json.dumps(job_data))

        # Wait for result via BRPOP (GateKeeper pushes result to this key)
        redis_client = await get_redis_client()
        result_key = f"{_COMFYUI_RESULT_KEY_PREFIX}:{job_id}"
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

        # GateKeeper wraps result in envelope: {"status": "success", "data": {...actual result...}}
        # Extract the actual result from the "data" field
        actual_result = result.get("data", result)  # Fallback to result if no data envelope
        logger.debug("Result structure - keys: %s, has 'data' envelope: %s",
                    list(result.keys()), "data" in result)

        # ======================================================================
        # REDIS MAGRO (Content Reference): Detect if worker returned a content
        # reference (relative_url) instead of inline base64.
        #
        # When the worker saves the PNG to disk at:
        #   runtime/user/{assignee_id}/contents/{job_id}/{filename}.png
        # it returns {"content_id": ..., "relative_url": "...", "mime_type": "image/png"}
        #
        # This eliminates ~500KB-1MB of base64 from Redis L1 — only ~200 bytes of JSON.
        # Backward compatible: if "image_base64" is present (legacy), extract as before.
        # ======================================================================
        if "relative_url" in actual_result or "content_id" in actual_result:
            # Redis Magro: content reference — return as-is, no base64 in Redis
            logger.info("📦 REDIS MAGRO: result contains content reference (relative_url=%s, content_id=%s)",
                        actual_result.get("relative_url", "N/A"),
                        actual_result.get("content_id", "N/A"))
            # DIAG: log raw BRPOP payload size vs stripped return size
            _raw_size = len(json.dumps(actual_result, default=str))
            _stripped_size = len(json.dumps({
                "success": True,
                "content_id": actual_result.get("content_id", job_id),
                "relative_url": actual_result.get("relative_url", ""),
                "mime_type": actual_result.get("mime_type", "image/png"),
                "job_id": job_id,
                "processing_time": actual_result.get("processing_time_ms", 0),
                "metadata": {
                    "model": actual_result.get("model", model),
                    "prompt": prompt,
                }
            }))
            logger.info("📊 DIAG-PAYLOAD-SIZE: raw_payload=%d bytes → stripped=%d bytes (saved %d bytes)",
                        _raw_size, _stripped_size, _raw_size - _stripped_size)
            return {
                "success": True,
                "content_id": actual_result.get("content_id", job_id),
                "relative_url": actual_result.get("relative_url", ""),
                "mime_type": actual_result.get("mime_type", "image/png"),
                "job_id": job_id,
                "processing_time": actual_result.get("processing_time_ms", 0),
                "metadata": {
                    "model": actual_result.get("model", model),
                    "prompt": prompt,
                }
            }

        # Legacy: content has inline base64 — extract and return as before
        image_b64 = actual_result.get("image_base64", "")
        image_len = len(image_b64) if image_b64 else 0
        logger.info("📦 RETURN VALUE - image_base64 length: %d chars", image_len)
        if image_len == 0:
            logger.error("🚨 CRITICAL: image_base64 is EMPTY! Result keys: %s, Data keys: %s",
                        list(result.keys()), list(actual_result.keys()) if isinstance(actual_result, dict) else "NOT A DICT")
            logger.error("🚨 Full result from Redis: %s", json.dumps(actual_result, default=str)[:500])
        return {
            "success": True,
            "image_base64": image_b64,
            "job_id": job_id,
            "processing_time": actual_result.get("processing_time_ms", 0),
            "metadata": {
                "model": actual_result.get("model", model),
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
            logger.warning(f"BRPOP timeout or no data for key: {result_key}")
            return None
        _key, raw_value = result
        logger.debug(f"BRPOP received raw_value length: {len(raw_value)} bytes")
        parsed = json.loads(raw_value)
        logger.debug(f"Parsed result keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'NOT A DICT'}")
        if isinstance(parsed, dict) and 'image_base64' in parsed:
            image_b64_len = len(parsed.get('image_base64', ''))
            logger.info(f"✅ Result contains image_base64: {image_b64_len} chars")
        elif isinstance(parsed, dict) and ('relative_url' in parsed or 'content_id' in parsed):
            logger.info(f"📦 Magro content reference result (no base64 expected). Keys: {list(parsed.keys())}")
        else:
            logger.warning(f"⚠️ Result missing image_base64 field. Keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'NOT A DICT'}")
        return parsed
    except Exception as e:
        logger.error(f"BRPOP failed for key {result_key}: {e}", exc_info=True)
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
    timeout: float = 300.0,
    assignee_id: Optional[str] = None,
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
        assignee_id: User ID for Redis Magro content reference

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
        timeout=timeout,
        assignee_id=assignee_id,
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
