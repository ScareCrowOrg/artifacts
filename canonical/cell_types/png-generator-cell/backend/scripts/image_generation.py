"""
Image Generation Integration for PNG Generator Cell

Provides GPU-accelerated image generation via ComfyUI by delegating to
the Windows Worker via Redis queue using canonical redis_client.

ASYNC FLOW (v6.0):
1. Create JobDocument in MongoDB (SSOT)
2. LPUSH job to Redis queue
3. Return { job_id, status: "queued" } immediately — no BRPOP

JobConsumer persists results to MongoDB when GateKeeper completes.
Frontend polls GET /api/cells/job-status/{job_id} for completion.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Redis L1 client from canonical shared (single source of truth)
try:
    from canonical.shared.redis_client import get_redis_client
except ImportError:
    # Local dev fallback: add shared to path
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / 'shared'))
    from redis_client import get_redis_client  # noqa: F811


async def queue_image_generation_job(
    prompt: str,
    negative_prompt: str = "",
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg_scale: float = 7.5,
    seed: int = -1,
    model: str = "stabilityai/stable-diffusion-xl-base-1.0",
    assignee_id: Optional[str] = None,
    current_user: Any = None,
) -> Dict[str, Any]:
    """
    Queue an image generation job to Redis and return immediately.

    ASYNC FLOW (v6.0):
    1. Create JobDocument in MongoDB (persistent SSOT)
    2. LPUSH job to Redis queue via canonical redis_client
    3. Return { job_id, status: "queued" } immediately

    The JobConsumer background service will persist the result
    to MongoDB when GateKeeper completes the job.

    Args:
        prompt: Text description of the desired image
        negative_prompt: Things to avoid in generation
        width: Image width in pixels (256-1024)
        height: Image height in pixels (256-1024)
        steps: Number of denoising steps (1-100)
        cfg_scale: Classifier-free guidance scale
        seed: Random seed (-1 for random)
        model: HuggingFace model ID
        assignee_id: User ID for Redis Magro content reference.
            When provided, the worker saves the PNG to disk at
            runtime/user/{assignee_id}/contents/{job_id}/{filename}.png

    Returns:
        Dict containing:
            - success: Boolean indicating success/failure
            - job_id: Unique job identifier (for polling)
            - status: "queued" | "failed"
            - error: Error message (if failure)
    """
    job_id = None
    try:
        job_id = str(uuid.uuid4())
        logger.info("Queueing image generation job (async): %s", job_id)

        # Build job payload (matches SD worker expectations)
        payload: Dict[str, Any] = {
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
        if assignee_id:
            payload["assignee_id"] = assignee_id
            payload["content_id"] = job_id
            logger.debug("PNG-DIAG: payload.assignee_id=%s payload.content_id=%s", assignee_id, job_id)

        # ── Step 1: Create JobDocument in MongoDB ──
        try:
            from app.models.job import create_job_document

            logger.debug(
                "DIAG [queue_image_generation_job] Calling create_job_document: "
                "job_id=%s, user_id=%s, current_user=%s",
                job_id,
                assignee_id or "cell-script",
                current_user,
            )
            jdoc_result = await create_job_document(
                job_id=job_id,
                job_type="comfyui_generate",
                user_id=assignee_id or "cell-script",
                payload=payload,
                cell_type="png-generator-cell",
                status="queued",
                current_user=current_user,
                planet_id=os.getenv("PLANET_NAME", ""),
            )
            logger.debug(
                "DIAG [queue_image_generation_job] create_job_document returned: "
                "doc=%s (type=%s)",
                jdoc_result,
                type(jdoc_result).__name__,
            )
            logger.debug(
                "DIAG [PNG-JOB] IMAGE_GEN_JOB_DOC: "
                "jdoc_result_type=%s jdoc_result_val=%s job_id=%s",
                type(jdoc_result).__name__,
                jdoc_result,
                job_id,
            )
            if jdoc_result is None:
                logger.critical(
                    "PERMANENTE [queue_image_generation_job] MongoDB insert FAILED for job=%s. "
                    "Aborting queue chain to prevent ghost job — job was NOT enqueued.",
                    job_id,
                )
                return {
                    "success": False,
                    "error": "Database persistence failed. Job was not enqueued to protect data integrity. "
                             "Please try again or contact support if the issue persists.",
                }
        except ImportError:
            logger.warning(
                "create_job_document not available (app.models.job not imported) — "
                "continuing without MongoDB persistence"
            )
            logger.warning(
                "PERMANENTE [PNG-JOB] KNOWN_GAP: ImportError on create_job_document — "
                "job=%s will be enqueued via LPUSH without MongoDB document. "
                "Ghost job risk: if job completes, result has no SSOT document.",
                job_id,
            )
        except Exception as jdoc_err:
            logger.warning(
                "Failed to create JobDocument (non-blocking): %s", jdoc_err
            )
            logger.warning(
                "PERMANENTE [PNG-JOB] KNOWN_GAP: Exception on create_job_document — "
                "job=%s error=%s. Job will be enqueued via LPUSH without MongoDB document. "
                "Ghost job risk: if job completes, result has no SSOT document.",
                job_id, jdoc_err,
            )

        # ── Step 2: LPUSH to Redis queue (existing) ──
        try:
            from canonical.shared.redis_client import create_job

            logger.debug(
                "DIAG [queue_image_generation_job] Calling create_job: "
                "owner_user_id=%s, assignee_id in payload=%s",
                "cell-script",
                assignee_id or "NOT_SET",
            )
            logger.warning(
                "PNG-PERMANENTE: owner_user_id='cell-script' (FIXED STRING) — top-level user_id will be "
                "'cell-script', not real assignee UUID. payload.assignee_id=%s",
                assignee_id or "NOT_SET",
            )
            enqueued_job_id, location = await create_job(
                job_type="comfyui_generate",
                payload=payload,
                owner_user_id=assignee_id or "cell-script",
                job_id=job_id,
                planet_id=os.getenv("PLANET_NAME", ""),
            )
            logger.info("Job enqueued via canonical redis_client to %s: %s", location, job_id)
        except Exception as exc:
            logger.warning("canonical create_job unavailable (%s); using direct LPUSH fallback", exc)
            logger.debug(
                "DIAG [queue_image_generation_job] create_job failed, "
                "using direct LPUSH fallback: %s",
                exc,
            )
            redis_client = await get_redis_client()
            job_data = {
                "job_id": job_id,
                "job_type": "comfyui_generate",
                "user_id": assignee_id or "cell-script",
                "queue": "scareverse:comfyui-jobs:queue",
                **payload,
            }
            await redis_client.lpush("scareverse:comfyui-jobs:queue", json.dumps(job_data))

        # ── Step 3: Return immediately (no BRPOP) ──
        logger.info(
            "Image generation job queued async: job_id=%s (frontend will poll)",
            job_id,
        )
        return {
            "success": True,
            "job_id": job_id,
            "status": "queued",
        }

    except Exception as exc:
        logger.error("Failed to queue image generation job: %s", exc, exc_info=True)
        return {
            "success": False,
            "error": f"Failed to queue job: {str(exc)}",
            "job_id": job_id,
        }


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

    NOTE: The timeout parameter is accepted but ignored in async flow
    (jobs no longer block waiting for results).

    Args:
        prompt: Text description of the desired image
        negative_prompt: Things to avoid in generation
        width: Image width in pixels
        height: Image height in pixels
        steps: Number of denoising steps
        cfg_scale: Classifier-free guidance scale
        seed: Random seed (-1 for random)
        model: HuggingFace model ID
        timeout: Ignored in async flow (kept for backward compat)
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
