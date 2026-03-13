"""
Stable Diffusion Queue Router - Queue-Based Image Generation API

This router provides a queue-based API for Stable Diffusion image generation,
implementing asynchronous processing with VRAM management via the Windows Worker.

Architecture:
    Backend/Client → POST /api/images/generate
                   ↓ RPUSH to Redis queue
                   ↓ BRPOP blocking wait (300s timeout)
                   ↓ Worker processes job (GPU)
                   ↓ Result published to Redis
                   ↓ BRPOP returns result
                   ↓ Response to client (Base64 PNG)

Features:
    - Queue-based processing (non-blocking backend)
    - VRAM-aware orchestration (coordinated with Ollama/3D jobs)
    - OOM handling with retry
    - Latency tracking (processing_time_ms)
    - Dead-letter queue for failed jobs
    - Auto-cleanup with TTL on result keys

Reference: Stable Diffusion Queue Bridge Implementation (SCARE-XXX)
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
import redis

from ..config.database import REDIS_L1_HOST, REDIS_L1_PORT, REDIS_L1_PASSWORD, REDIS_L1_DB
from .stable_diffusion_redis_ops import brpop_result

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/images", tags=["stable-diffusion"])

# Timeout configuration
REDIS_BRPOP_TIMEOUT = 300  # Redis BRPOP timeout in seconds (5 minutes)
ASYNCIO_TIMEOUT = 310  # AsyncIO timeout with 10s margin
RESULT_KEY_TTL = 120  # Auto-cleanup TTL for result keys

# SD configuration
SD_JOBS_QUEUE = "scareverse:sd-jobs:queue"
SD_RESULTS_PREFIX = "scareverse:sd-results"
SD_DEFAULT_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"  # SDXL for asset rendering with flat lighting


# ============================================================================
# Redis Client Singleton
# ============================================================================

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """
    Get or create Redis client singleton.

    Returns:
        redis.Redis: Connected Redis client

    Raises:
        ConnectionError: If Redis connection fails
    """
    global _redis_client

    if _redis_client is None:
        try:
            # Build Redis URL
            if REDIS_L1_PASSWORD:
                redis_url = f"redis://:{REDIS_L1_PASSWORD}@{REDIS_L1_HOST}:{REDIS_L1_PORT}/{REDIS_L1_DB}"
            else:
                redis_url = f"redis://{REDIS_L1_HOST}:{REDIS_L1_PORT}/{REDIS_L1_DB}"

            _redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=10,
                socket_keepalive=True,
                retry_on_timeout=True,
            )

            # Test connection
            _redis_client.ping()
            logger.info("✅ Redis client connected: %s:%s", REDIS_L1_HOST, REDIS_L1_PORT)

        except Exception as e:
            logger.error("❌ Redis connection failed: %s", e)
            raise ConnectionError(f"Failed to connect to Redis: {e}") from e

    return _redis_client


def get_sd_result_key(job_id: str) -> str:
    """
    Get the Redis key for a specific SD job result.

    Args:
        job_id: Unique job identifier

    Returns:
        str: Full Redis key (e.g., "scareverse:sd-results:abc-123")
    """
    return f"{SD_RESULTS_PREFIX}:{job_id}"


# ============================================================================
# Request/Response Models
# ============================================================================

class StableDiffusionGenerateRequest(BaseModel):
    """Request model for SD image generation."""

    prompt: str = Field(
        ...,
        description="Text description of the desired image",
        min_length=1
    )
    model: Optional[str] = Field(
        default=SD_DEFAULT_MODEL,
        description="HuggingFace model ID (default: stabilityai/stable-diffusion-xl-base-1.0)"
    )
    negative_prompt: Optional[str] = Field(
        default="",
        description="Things to avoid in the generation"
    )
    height: int = Field(
        default=512,
        ge=256,
        le=1024,
        description="Image height in pixels (256-1024)"
    )
    width: int = Field(
        default=512,
        ge=256,
        le=1024,
        description="Image width in pixels (256-1024)"
    )
    num_inference_steps: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of denoising steps (1-100)"
    )
    guidance_scale: float = Field(
        default=7.5,
        ge=1.0,
        le=20.0,
        description="Classifier-free guidance scale (1.0-20.0)"
    )
    seed: int = Field(
        default=-1,
        description="Random seed (-1 for random)"
    )


class StableDiffusionGenerateResponse(BaseModel):
    """Response model for SD image generation."""

    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status (success, error, timeout)")
    image_base64: Optional[str] = Field(None, description="Base64-encoded PNG image (if success)")
    model: Optional[str] = Field(None, description="Model used (if success)")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")
    error: Optional[str] = Field(None, description="Error message (if failed)")


# ============================================================================
# Job Enqueueing Helper
# ============================================================================


async def _enqueue_sd_job(job_id: str, payload: Dict[str, Any]) -> None:
    """
    Enqueue a Stable Diffusion job via the canonical shared redis_client.

    Uses ``create_job()`` from ``artifacts/canonical/shared`` to check
    service availability (``state:service:stable-diffusion:available``) and
    route to Redis L1 (fast path) or CentralHub L2 (fallback).

    Falls back to legacy direct RPUSH if the canonical module cannot be loaded.

    Args:
        job_id: Pre-generated job ID.
        payload: SD job-specific data (model, prompt, dimensions, etc.)
    """
    try:
        from ..services.canonical_client import create_job
        await create_job(
            job_type="sd_generate",
            payload=payload,
            owner_user_id="sd-proxy",
            job_id=job_id,
        )
    except Exception as exc:
        # Fallback: legacy direct RPUSH (no owner-first scheduling)
        logger.warning(
            "[%s] canonical create_job unavailable (%s) – falling back to legacy rpush",
            job_id,
            exc,
        )
        from .stable_diffusion_redis_ops import rpush_job as _rpush_job
        redis_client = get_redis_client()
        legacy_job_data = {
            "job_id": job_id,
            "type": "sd_generate",
            "payload": payload,
            "attempts": 0,
            "created_at": time.time(),
        }
        await _rpush_job(redis_client, SD_JOBS_QUEUE, legacy_job_data)



# ============================================================================
# Router Endpoints
# ============================================================================

@router.post("/generate", response_model=StableDiffusionGenerateResponse)
async def generate_image(request: StableDiffusionGenerateRequest):
    """
    Generate image using Stable Diffusion (queue-based, async).

    This endpoint enqueues the generation job and waits for the result.
    The Windows Worker processes the job with GPU VRAM management.

    Args:
        request: StableDiffusionGenerateRequest with generation parameters

    Returns:
        StableDiffusionGenerateResponse with image_base64 or error

    Raises:
        HTTPException: On timeout (504) or service unavailable (503)
    """
    # Generate unique job ID
    job_id = str(uuid.uuid4())

    logger.info(
        "[%s] SD generate request: prompt='%s...', model=%s, size=%sx%s, steps=%s",
        job_id, request.prompt[:50], request.model, request.width, request.height, request.num_inference_steps
    )

    try:
        # Get Redis client
        redis_client = get_redis_client()

        # Build job payload
        sd_payload = {
            "model": request.model,
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "height": request.height,
            "width": request.width,
            "num_inference_steps": request.num_inference_steps,
            "guidance_scale": request.guidance_scale,
            "seed": request.seed,
        }

        # Enqueue via unified redis_job_client (owner-first scheduling)
        logger.info("[%s] Enqueuing SD job", job_id)
        await _enqueue_sd_job(job_id, sd_payload)

        # Wait for result with timeout (abstracted for HTTP migration)
        result_key = get_sd_result_key(job_id)
        logger.info("[%s] Waiting for result (timeout: %ss)", job_id, ASYNCIO_TIMEOUT)

        try:
            result = await asyncio.wait_for(
                brpop_result(redis_client, result_key, REDIS_BRPOP_TIMEOUT),
                timeout=ASYNCIO_TIMEOUT
            )

            if result is None:
                # Timeout - no result received
                logger.error("[%s] Job timeout after %ss", job_id, REDIS_BRPOP_TIMEOUT)
                raise HTTPException(
                    status_code=504,
                    detail=f"Image generation timeout after {REDIS_BRPOP_TIMEOUT} seconds"
                )

            # Parse result (BRPOP returns tuple of (key, value))
            _, result_json = result
            result_data = json.loads(result_json)

            logger.info("[%s] Result received: status=%s", job_id, result_data.get('status'))

            # Check status
            if result_data.get("status") == "success":
                return StableDiffusionGenerateResponse(
                    job_id=job_id,
                    status="success",
                    image_base64=result_data.get("image_base64"),
                    model=result_data.get("model"),
                    processing_time_ms=result_data.get("processing_time_ms")
                )
            else:
                # Error result
                error_msg = result_data.get("error", "Unknown error")
                logger.error("[%s] Job failed: %s", job_id, error_msg)
                return StableDiffusionGenerateResponse(
                    job_id=job_id,
                    status="error",
                    error=error_msg
                )

        except asyncio.TimeoutError:
            # AsyncIO timeout (should not happen with margin)
            logger.error("[%s] AsyncIO timeout after %ss", job_id, ASYNCIO_TIMEOUT)
            raise HTTPException(
                status_code=504,
                detail=f"Image generation timeout after {ASYNCIO_TIMEOUT} seconds"
            )

    except ConnectionError as e:
        # Redis connection error
        logger.error("[%s] Redis connection error: %s", job_id, e)
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable (Redis connection error)"
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        # Unexpected error
        logger.error("[%s] Unexpected error: %s", job_id, e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint for SD router.

    Returns:
        dict: Health status
    """
    try:
        redis_client = get_redis_client()
        redis_client.ping()
        return {"status": "healthy", "service": "stable-diffusion-queue"}
    except Exception as e:
        logger.error("Health check failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Service unhealthy (Redis connection error)"
        )
