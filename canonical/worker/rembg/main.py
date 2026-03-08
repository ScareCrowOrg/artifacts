"""
Rembg Atomic Worker – FastAPI Service.

Stateless background removal service. Accepts base64-encoded images via
HTTP POST /process and returns the result as a base64-encoded PNG.

Endpoints:
  POST /process   – Remove background from image.
  GET  /health    – Liveness probe.

Worker Heartbeat:
  On startup the worker registers availability in Redis L1 under the key
  state:worker:rembg_removebackground:available with a short TTL.
  A background task refreshes this key periodically so that the
  redis_job_client can discover the worker before enqueuing jobs.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from rembg_service import RembgService, RembgServiceError

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WORKER_ID = os.getenv("WORKER_ID", "rembg-worker-01")
WORKER_PORT = int(os.getenv("WORKER_PORT", "9000"))

# Redis L1 – used only for heartbeat/availability signaling
REDIS_L1_HOST = os.getenv("REDIS_L1_HOST", "redis-local")
REDIS_L1_PORT_NUM = int(os.getenv("REDIS_L1_PORT", "6380"))
REDIS_L1_PASSWORD = os.getenv("REDIS_L1_PASSWORD", "scarerunner")
REDIS_L1_DB = int(os.getenv("REDIS_L1_DB", "0"))

# Heartbeat interval and TTL (TTL = 3 × interval for safety margin)
HEARTBEAT_INTERVAL = int(os.getenv("WORKER_HEARTBEAT_INTERVAL", "20"))
HEARTBEAT_TTL = HEARTBEAT_INTERVAL * 3

# Key pattern expected by redis_job_client worker availability check
_AVAILABILITY_KEY = "state:worker:rembg_removebackground:available"

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Rembg Worker",
    description="Atomic background removal service for ScareVerse.",
    version="1.0.0",
)

# Singleton service (lazy-loaded on first request)
_rembg_service: Optional[RembgService] = None

# Redis L1 client for heartbeat (optional – worker continues without it)
_redis_l1: Optional[Any] = None
_heartbeat_task: Optional[asyncio.Task] = None


def get_service() -> RembgService:
    """Return the singleton RembgService, creating it on first call."""
    global _rembg_service
    if _rembg_service is None:
        _rembg_service = RembgService()
    return _rembg_service


# ---------------------------------------------------------------------------
# Heartbeat helpers
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _build_redis_l1() -> Optional[Any]:
    """Create and return an async Redis L1 client, or None on failure."""
    try:
        import redis.asyncio as aioredis

        kwargs: Dict[str, Any] = {
            "host": REDIS_L1_HOST,
            "port": REDIS_L1_PORT_NUM,
            "db": REDIS_L1_DB,
            "decode_responses": True,
            "socket_connect_timeout": 5,
        }
        if REDIS_L1_PASSWORD:
            kwargs["password"] = REDIS_L1_PASSWORD

        client = aioredis.Redis(**kwargs)
        await client.ping()
        logger.info(
            "Rembg worker connected to Redis L1: %s:%d",
            REDIS_L1_HOST, REDIS_L1_PORT_NUM,
        )
        return client
    except Exception as exc:
        logger.warning(
            "Cannot connect to Redis L1 for heartbeat (%s:%d): %s – "
            "worker will start without availability signaling",
            REDIS_L1_HOST, REDIS_L1_PORT_NUM, exc,
        )
        return None


async def _heartbeat_loop() -> None:
    """Periodically refresh the worker availability key in Redis L1."""
    global _redis_l1

    payload = json.dumps({
        "worker_id": WORKER_ID,
        "service": "rembg",
        "job_types": ["rembg_removebackground", "REMOTE_REMBG", "background_removal"],
        "status": "available",
    })

    _last_reconnect_attempt: float = 0.0
    _reconnect_cooldown: float = 60.0  # Minimum seconds between reconnect attempts

    while True:
        try:
            if _redis_l1 is not None:
                await _redis_l1.set(_AVAILABILITY_KEY, payload, ex=HEARTBEAT_TTL)
                logger.debug(
                    "Heartbeat refreshed: key=%s TTL=%ds", _AVAILABILITY_KEY, HEARTBEAT_TTL
                )
        except Exception as exc:
            logger.warning("Heartbeat publish failed: %s", exc)
            import time as _time
            now = _time.monotonic()
            if now - _last_reconnect_attempt >= _reconnect_cooldown:
                _last_reconnect_attempt = now
                _redis_l1 = await _build_redis_l1()

        await asyncio.sleep(HEARTBEAT_INTERVAL)


# ---------------------------------------------------------------------------
# Lifecycle events
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup() -> None:
    global _redis_l1, _heartbeat_task

    logger.info("Rembg worker %s starting on port %d", WORKER_ID, WORKER_PORT)

    # Connect to Redis L1 (best-effort – worker still runs without it)
    _redis_l1 = await _build_redis_l1()

    # Publish initial availability immediately
    if _redis_l1 is not None:
        try:
            payload = json.dumps({
                "worker_id": WORKER_ID,
                "service": "rembg",
                "job_types": ["rembg_removebackground", "REMOTE_REMBG", "background_removal"],
                "status": "available",
                "timestamp": _utcnow_iso(),
            })
            await _redis_l1.set(_AVAILABILITY_KEY, payload, ex=HEARTBEAT_TTL)
            logger.info("Worker availability registered: key=%s", _AVAILABILITY_KEY)
        except Exception as exc:
            logger.warning("Failed to register initial availability: %s", exc)

    # Start periodic heartbeat refresh
    _heartbeat_task = asyncio.create_task(_heartbeat_loop())
    logger.info("Rembg worker %s ready", WORKER_ID)


@app.on_event("shutdown")
async def shutdown() -> None:
    global _heartbeat_task, _redis_l1

    logger.info("Rembg worker %s shutting down", WORKER_ID)

    # Cancel heartbeat task
    if _heartbeat_task is not None:
        _heartbeat_task.cancel()
        try:
            await _heartbeat_task
        except asyncio.CancelledError:
            pass

    # Remove availability key so redis_job_client stops routing to this worker
    if _redis_l1 is not None:
        try:
            await _redis_l1.delete(_AVAILABILITY_KEY)
            logger.info("Worker availability key removed: %s", _AVAILABILITY_KEY)
        except Exception as exc:
            logger.warning("Failed to remove availability key: %s", exc)
        await _redis_l1.aclose()


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class ProcessRequest(BaseModel):
    """Payload accepted by POST /process."""

    job_id: str
    image_data: str  # Base64-encoded image (with or without data-URI prefix)
    alpha_matting: bool = True


class ProcessResponse(BaseModel):
    """Response returned by POST /process."""

    job_id: str
    result: str  # Base64-encoded PNG (no prefix)
    status: str  # "ok"


class HealthResponse(BaseModel):
    status: str
    service: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/process", response_model=ProcessResponse)
async def process_image(request: ProcessRequest) -> ProcessResponse:
    """
    Remove background from a base64-encoded image.

    Returns a base64-encoded RGBA PNG with the background removed.
    """
    logger.info("Processing job_id=%s alpha_matting=%s", request.job_id, request.alpha_matting)

    try:
        service = get_service()
        result_b64 = service.remove_background_base64(
            input_base64=request.image_data,
            alpha_matting=request.alpha_matting,
            job_id=request.job_id,
        )
        logger.info("Job %s completed successfully", request.job_id)
        return ProcessResponse(job_id=request.job_id, result=result_b64, status="ok")

    except RembgServiceError as exc:
        logger.error("Job %s failed: %s", request.job_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    except Exception as exc:
        logger.error("Unexpected error for job %s: %s", request.job_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness probe – always returns 200 if the process is running."""
    return HealthResponse(status="ok", service="rembg")

