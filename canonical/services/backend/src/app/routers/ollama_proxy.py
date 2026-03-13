"""
Ollama Proxy Router - Transparent Ollama-Compatible API

This router provides a transparent proxy to Ollama with Ollama-compatible endpoints,
implementing queue-based processing with VRAM management behind the scenes.

Architecture:
    Backend/Client → POST /api/{action} (Ollama-compatible)
                   ↓ RPUSH to Redis queue
                   ↓ BRPOP blocking wait (300s timeout)
                   ↓ Worker processes job
                   ↓ Result published to Redis
                   ↓ BRPOP returns result
                   ↓ Response to client

Features:
    - 100% Ollama-compatible API signature
    - Transparent queueing (client unaware of queue)
    - BRPOP blocking with AsyncIO timeout protection
    - Client disconnect handling (graceful cleanup)
    - Structured logging with job_id
    - 300s global timeout with 10s margin
    - Auto-cleanup with TTL on result keys

Reference: SCARE-042 - Ollama Queue Bridge Implementation (Refactored)
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import redis
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, validator

from ..config import AVAILABLE_OLLAMA_MODELS, OLLAMA_DEFAULT_MODEL
from ..config.database import (
    REDIS_L1_DB,
    REDIS_L1_HOST,
    REDIS_L1_PASSWORD,
    REDIS_L1_PORT,
)
from ..config.redis_keys import (
    OLLAMA_JOBS_QUEUE,
    get_ollama_result_key,
)
from .ollama_proxy_redis_ops import brpop_result, delete_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ollama"])

# Timeout configuration
REDIS_BRPOP_TIMEOUT = 300  # Redis BRPOP timeout in seconds
ASYNCIO_TIMEOUT = 310  # AsyncIO timeout with 10s margin
RESULT_KEY_TTL = 60  # Auto-cleanup TTL for result keys


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


# ============================================================================
# Request/Response Models
# ============================================================================


class OllamaGenerateRequest(BaseModel):
    """Request model for Ollama generate endpoint."""

    prompt: str = Field(..., description="Text prompt for generation", min_length=1)
    model: Optional[str] = Field(
        default=None,
        description=f"Ollama model to use. Available: {', '.join(AVAILABLE_OLLAMA_MODELS)}",
    )
    stream: bool = Field(
        default=False,
        description="Enable streaming (not supported in MVP, reserved for Phase 2)",
    )
    options: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional model options (temperature, top_p, etc.)"
    )

    @validator("model", pre=True, always=True)
    def validate_model(cls, v):
        """Validate model is in available models list."""
        if v is None:
            return OLLAMA_DEFAULT_MODEL
        if v not in AVAILABLE_OLLAMA_MODELS:
            raise ValueError(
                f"Model '{v}' not available. Choose from: {', '.join(AVAILABLE_OLLAMA_MODELS)}"
            )
        return v


class OllamaChatRequest(BaseModel):
    """Request model for Ollama chat endpoint."""

    messages: List[Dict[str, str]] = Field(
        ...,
        description="Chat messages in OpenAI format [{role, content}, ...]",
        min_length=1,
    )
    model: Optional[str] = Field(
        default=None,
        description=f"Ollama model to use. Available: {', '.join(AVAILABLE_OLLAMA_MODELS)}",
    )
    stream: bool = Field(
        default=False,
        description="Enable streaming (not supported in MVP, reserved for Phase 2)",
    )
    options: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional model options"
    )

    @validator("model", pre=True, always=True)
    def validate_model(cls, v):
        """Validate model is in available models list."""
        if v is None:
            return OLLAMA_DEFAULT_MODEL
        if v not in AVAILABLE_OLLAMA_MODELS:
            raise ValueError(
                f"Model '{v}' not available. Choose from: {', '.join(AVAILABLE_OLLAMA_MODELS)}"
            )
        return v


class OllamaQueueResponse(BaseModel):
    """Response model for queued Ollama requests."""

    status: str = Field(..., description="Status: success or error")
    job_id: str = Field(..., description="Unique job identifier")
    response: Optional[str] = Field(None, description="Generated text response")
    model: Optional[str] = Field(None, description="Model used for generation")
    error: Optional[str] = Field(None, description="Error message if failed")
    latency_ms: Optional[float] = Field(
        None, description="Total latency in milliseconds"
    )


# ============================================================================
# Job Enqueueing Helper
# ============================================================================


async def _enqueue_ollama_job(job_id: str, job_type: str, payload: Dict[str, Any]) -> None:
    """
    Enqueue an Ollama job via the canonical shared redis_client.

    Uses ``create_job()`` from ``artifacts/canonical/shared`` to check
    service availability (``state:service:ollama:available``) and route to
    Redis L1 (fast path) or CentralHub L2 (fallback).

    Falls back to legacy direct RPUSH if the canonical module cannot be loaded.

    Args:
        job_id: Pre-generated job ID.
        job_type: Canonical job type ("ollama_generate" or "ollama_chat").
        payload: Job-specific data (prompt/messages, model, options, etc.)
    """
    try:
        from ..services.canonical_client import create_job
        await create_job(
            job_type=job_type,
            payload=payload,
            owner_user_id="ollama-proxy",
            job_id=job_id,
        )
    except Exception as exc:
        # Fallback: legacy direct RPUSH (no owner-first scheduling)
        logger.warning(
            "[%s] canonical create_job unavailable (%s) – falling back to legacy rpush",
            job_id,
            exc,
        )
        from .ollama_proxy_redis_ops import rpush_job as _rpush_job
        redis_client = get_redis_client()
        legacy_job_data = {
            "job_id": job_id,
            "type": job_type,
            "payload": payload,
            "created_at": time.time(),
            "attempts": 0,
        }
        await _rpush_job(redis_client, OLLAMA_JOBS_QUEUE, legacy_job_data)



# ============================================================================
# Endpoint Handlers
# ============================================================================


@router.get("/tags")
async def get_tags() -> Dict[str, Any]:
    """
    Get available Ollama models (Ollama-compatible endpoint).

    This endpoint provides health check and model availability information
    without requiring actual Ollama processing.

    Models are sourced from artifacts/canonical/ai_models/ (providers="ollama")
    and represent the models actually supported by the system.

    Returns:
        Dict with available models (compatible with Ollama /api/tags response)

    Reference: https://github.com/ollama/ollama/blob/main/docs/api.md#list-local-models
    """
    try:
        logger.info("GET /api/tags - Listing available models")

        # Models from artifacts/canonical/ai_models/ with provider="ollama"
        available_models = [
            "mistral",
            "phi3:latest",
            "deepseek-coder:6.7b",
            "qwen2.5-coder:14b",
            "gemma:7b",
        ]

        # Return Ollama-compatible response with available models
        models = [
            {
                "name": model,
                "modified_at": "2024-01-01T00:00:00Z",
                "size": 0,
                "digest": f"sha256:{'0' * 64}",
            }
            for model in available_models
        ]

        return {"models": models}

    except Exception as e:
        logger.error("Error in /api/tags: %s", e)
        raise HTTPException(status_code=500, detail=f"Error fetching models: {str(e)}") from e


@router.post("/generate", response_model=OllamaQueueResponse)
async def generate(
    request: OllamaGenerateRequest, _http_request: Request
) -> OllamaQueueResponse:
    """
    Generate text via Ollama (Ollama-compatible endpoint).

    This is a transparent proxy that queues the request internally and blocks
    until the worker processes it, providing the same interface as Ollama.

    Flow:
        1. Generate unique job_id
        2. RPUSH job to Redis queue (internal)
        3. BRPOP blocking wait for result (300s timeout)
        4. Return result to client

    Args:
        request: Generation request parameters (Ollama-compatible)
        http_request: FastAPI request object (for disconnect detection)

    Returns:
        OllamaQueueResponse: Generated text or error

    Raises:
        HTTPException: 504 on timeout, 500 on internal error
    """
    job_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info("[%s] New generate request - Prompt length: %s chars", job_id, len(request.prompt))

    redis_client = get_redis_client()
    result_key = get_ollama_result_key(job_id)

    try:
        # Step 1: Enqueue job via unified redis_job_client (owner-first scheduling)
        await _enqueue_ollama_job(job_id, "ollama_generate", {
            "prompt": request.prompt,
            "model": request.model,
            "stream": request.stream,
            "options": request.options or {},
        })
        logger.info("[%s] Job enqueued (ollama_generate)", job_id)

        # Step 2: BRPOP blocking wait (abstracted for HTTP migration)
        try:
            result = await asyncio.wait_for(
                brpop_result(redis_client, result_key, REDIS_BRPOP_TIMEOUT),
                timeout=ASYNCIO_TIMEOUT,
            )

            if result is None:
                # Redis timeout expired
                logger.warning("[%s] BRPOP timeout after %ss (generate)", job_id, REDIS_BRPOP_TIMEOUT)
                await delete_key(redis_client, result_key)
                raise HTTPException(
                    status_code=504,
                    detail=f"Ollama timeout after {REDIS_BRPOP_TIMEOUT}s",
                )

            # Parse result
            _, result_json = result
            result_data = json.loads(result_json)

            latency_ms = (time.time() - start_time) * 1000
            logger.info("[%s] Job completed in %sms", job_id, latency_ms)

            # Build response
            if result_data.get("status") == "success":
                return OllamaQueueResponse(
                    status="success",
                    job_id=job_id,
                    response=result_data.get("data", {}).get("response"),
                    model=result_data.get("data", {}).get("model"),
                    latency_ms=latency_ms,
                )
            else:
                # Job failed in worker
                error_msg = result_data.get("error", "Unknown error")
                logger.error("[%s] Job failed in worker: %s", job_id, error_msg)
                return OllamaQueueResponse(
                    status="error",
                    job_id=job_id,
                    error=error_msg,
                    latency_ms=latency_ms,
                )

        except asyncio.TimeoutError:
            # AsyncIO timeout (should not happen if margin is correct)
            logger.error("[%s] AsyncIO timeout after %ss", job_id, ASYNCIO_TIMEOUT)
            await delete_key(redis_client, result_key)
            raise HTTPException(
                status_code=504, detail=f"Ollama timeout after {ASYNCIO_TIMEOUT}s"
            )

        except asyncio.CancelledError:
            # Client disconnected
            logger.info("[%s] Client disconnected, cleaning up", job_id)
            await delete_key(redis_client, result_key)
            raise

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        # Unexpected error
        logger.error("[%s] Unexpected error: %s", job_id, e, exc_info=True)
        try:
            await delete_key(redis_client, result_key)
        except Exception:
            pass

        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}") from e


@router.post("/chat", response_model=OllamaQueueResponse)
async def chat(
    request: OllamaChatRequest, _http_request: Request
) -> OllamaQueueResponse:
    """
    Chat with Ollama (Ollama-compatible endpoint).

    This is a transparent proxy that uses chat format with message history,
    queuing the request internally for processing.

    Flow:
        1. Generate unique job_id
        2. RPUSH job to Redis queue (internal)
        3. BRPOP blocking wait for result (300s timeout)
        4. Return result to client

    Args:
        request: Chat request with messages (Ollama-compatible)
        http_request: FastAPI request object

    Returns:
        OllamaQueueResponse: Generated response or error

    Raises:
        HTTPException: 504 on timeout, 500 on internal error
    """
    job_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info("[%s] New chat request - Messages: %s", job_id, len(request.messages))

    redis_client = get_redis_client()
    result_key = get_ollama_result_key(job_id)

    try:
        # Step 1: Enqueue job via unified redis_job_client (owner-first scheduling)
        await _enqueue_ollama_job(job_id, "ollama_chat", {
            "messages": request.messages,
            "model": request.model,
            "stream": request.stream,
            "options": request.options or {},
        })
        logger.info("[%s] Chat job enqueued (ollama_chat)", job_id)

        # Step 2: BRPOP blocking wait (abstracted for HTTP migration)
        try:
            result = await asyncio.wait_for(
                brpop_result(redis_client, result_key, REDIS_BRPOP_TIMEOUT),
                timeout=ASYNCIO_TIMEOUT,
            )

            if result is None:
                # Redis timeout expired
                logger.warning("[%s] BRPOP timeout after %ss (chat)", job_id, REDIS_BRPOP_TIMEOUT)
                await delete_key(redis_client, result_key)
                raise HTTPException(
                    status_code=504,
                    detail=f"Ollama timeout after {REDIS_BRPOP_TIMEOUT}s",
                )

            # Parse result
            _, result_json = result
            result_data = json.loads(result_json)

            latency_ms = (time.time() - start_time) * 1000
            logger.info("[%s] Chat job completed in %sms", job_id, latency_ms)

            # Build response
            if result_data.get("status") == "success":
                return OllamaQueueResponse(
                    status="success",
                    job_id=job_id,
                    response=result_data.get("data", {})
                    .get("message", {})
                    .get("content"),
                    model=result_data.get("data", {}).get("model"),
                    latency_ms=latency_ms,
                )
            else:
                # Job failed in worker
                error_msg = result_data.get("error", "Unknown error")
                logger.error("[%s] Chat job failed in worker: %s", job_id, error_msg)
                return OllamaQueueResponse(
                    status="error",
                    job_id=job_id,
                    error=error_msg,
                    latency_ms=latency_ms,
                )

        except asyncio.TimeoutError:
            # AsyncIO timeout
            logger.error("[%s] AsyncIO timeout after %ss", job_id, ASYNCIO_TIMEOUT)
            await delete_key(redis_client, result_key)
            raise HTTPException(
                status_code=504, detail=f"Ollama timeout after {ASYNCIO_TIMEOUT}s"
            )

        except asyncio.CancelledError:
            # Client disconnected
            logger.info("[%s] Client disconnected for chat, cleaning up", job_id)
            await delete_key(redis_client, result_key)
            raise

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        # Unexpected error
        logger.error("[%s] Unexpected error in chat: %s", job_id, e, exc_info=True)
        try:
            await delete_key(redis_client, result_key)
        except Exception:
            pass

        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}") from e


# ============================================================================
# Optional Status Endpoint (Fallback Polling)
# ============================================================================


@router.get("/status/{job_id}", response_model=Dict[str, Any])
async def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Get status of an Ollama job (optional fallback polling).

    This endpoint allows clients to poll for job status instead of
    blocking on the primary endpoints. Useful for long-running jobs or debugging.

    Args:
        job_id: Unique job identifier

    Returns:
        Dict with job status information

    Raises:
        HTTPException: 404 if job not found
    """
    redis_client = get_redis_client()
    result_key = get_ollama_result_key(job_id)

    try:
        # Check if result exists
        result = redis_client.get(result_key)

        if result is None:
            # Job not found or expired
            raise HTTPException(
                status_code=404, detail=f"Job {job_id} not found or expired"
            )

        # Parse and return result
        result_data = json.loads(result)
        return {
            "job_id": job_id,
            "status": result_data.get("status", "unknown"),
            "data": result_data.get("data"),
            "error": result_data.get("error"),
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Error fetching job status %s: %s", job_id, e)
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch job status: {str(e)}"
        )
