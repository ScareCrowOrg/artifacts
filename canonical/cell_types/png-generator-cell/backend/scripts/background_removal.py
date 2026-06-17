"""
Background Removal Integration for PNG Generator Cell

Provides GPU-accelerated background removal by delegating to the
Windows Worker via Redis queue.

ASYNC FLOW (v6.0):
1. Create JobDocument in MongoDB (SSOT)
2. LPUSH job to Redis queue
3. Return { job_id, status: "queued" } immediately — no BRPOP
"""

import asyncio
import json
import logging
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


async def queue_background_removal_job(
    input_image_base64: str,
    alpha_matting: bool = True,
    current_user: Any = None,
) -> Dict[str, Any]:
    """
    Queue a background removal job to Redis and return immediately.

    ASYNC FLOW (v6.0):
    1. Create JobDocument in MongoDB (persistent SSOT)
    2. LPUSH job to Redis queue via canonical redis_client
    3. Return { job_id, status: "queued" } immediately

    Args:
        input_image_base64: Base64-encoded input image (with or without data URI prefix)
        alpha_matting: Enable alpha matting for better edge quality (default: True)

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
        logger.info("Queueing background removal job (async): %s", job_id)

        # Strip data URI prefix if present
        if ',' in input_image_base64:
            input_image_base64 = input_image_base64.split(',', 1)[1]

        # Build job payload (matches rembg worker expectations)
        payload: Dict[str, Any] = {
            "image_base64": input_image_base64,
            "alpha_matting": alpha_matting,
            "timestamp": time.time(),
        }

        # ── Step 1: Create JobDocument in MongoDB ──
        try:
            from app.models.job import create_job_document

            await create_job_document(
                job_id=job_id,
                job_type="rembg_removebackground",
                user_id="cell-script",
                payload=payload,
                cell_type="png-generator-cell",
                status="queued",
                current_user=current_user,
            )
        except ImportError:
            logger.warning(
                "create_job_document not available — continuing without MongoDB persistence"
            )
        except Exception as jdoc_err:
            logger.warning(
                "Failed to create JobDocument (non-blocking): %s", jdoc_err
            )

        # ── Step 2: LPUSH to Redis queue ──
        try:
            from canonical.shared.redis_client import create_job

            enqueued_job_id, location = await create_job(
                job_type="rembg_removebackground",
                payload=payload,
                owner_user_id="cell-script",
                job_id=job_id,
            )
            logger.info("Job enqueued via canonical redis_client to %s: %s", location, job_id)
        except Exception as exc:
            logger.warning("canonical create_job unavailable (%s); using direct LPUSH fallback", exc)
            redis_client = await get_redis_client()
            job_data = {
                "job_id": job_id,
                "job_type": "rembg_removebackground",
                "user_id": "cell-script",
                "queue": "scareverse:cpu-jobs:queue",
                **payload,
            }
            await redis_client.lpush("scareverse:cpu-jobs:queue", json.dumps(job_data))

        # ── Step 3: Return immediately (no BRPOP) ──
        logger.info(
            "Background removal job queued async: job_id=%s (frontend will poll)",
            job_id,
        )
        return {
            "success": True,
            "job_id": job_id,
            "status": "queued",
        }

    except Exception as exc:
        logger.error("Failed to queue background removal job: %s", exc, exc_info=True)
        return {
            "success": False,
            "error": f"Failed to queue job: {str(exc)}",
            "job_id": job_id,
        }


# Synchronous wrapper for backward compatibility
def queue_background_removal_job_sync(
    input_image_base64: str,
    alpha_matting: bool = True,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    """
    Synchronous wrapper for queue_background_removal_job.

    NOTE: timeout parameter is accepted but ignored in async flow.

    Args:
        input_image_base64: Base64-encoded input image
        alpha_matting: Enable alpha matting
        timeout: Ignored (kept for backward compat)

    Returns:
        Dict with job result
    """
    return asyncio.run(queue_background_removal_job(
        input_image_base64=input_image_base64,
        alpha_matting=alpha_matting,
    ))


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python background_removal.py <base64_image>")
        sys.exit(1)

    input_image = sys.argv[1]
    result = queue_background_removal_job_sync(input_image)

    print(json.dumps(result, indent=2))
