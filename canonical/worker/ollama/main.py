"""
Ollama Worker – Stateless HTTP Job Processor.

Stateless FastAPI service called by GateKeeper to process Ollama LLM jobs.
GateKeeper handles all queue consumption (BRPOP), retry logic, dead-letter,
and result persistence. This worker is only responsible for calling Ollama.

Endpoints:
- POST /process  – Receive job from GateKeeper, call Ollama, return result
- GET  /health   – Liveness probe for Docker health check

Worker Heartbeat:
  On startup the worker registers availability in Redis L1 under the keys
  state:worker:ollama_generate:available and state:worker:ollama_chat:available
  with a short TTL. A background task refreshes these keys periodically so
  that redis_job_client can discover the worker before enqueuing jobs.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException

import config

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Heartbeat configuration
# ---------------------------------------------------------------------------

HEARTBEAT_INTERVAL = int(getattr(config, "HEARTBEAT_INTERVAL", 20))
HEARTBEAT_TTL = HEARTBEAT_INTERVAL * 3

# Availability keys for all job types handled by this worker
_AVAILABILITY_KEYS = [
    "state:worker:ollama_generate:available",
    "state:worker:ollama_chat:available",
]

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Ollama Worker",
    description="Stateless HTTP worker for Ollama LLM inference. Called by GateKeeper.",
    version="1.0.0",
)

# Shared HTTP client (created at startup, reused across requests)
_http_client: Optional[httpx.AsyncClient] = None

# Redis L1 client for heartbeat (optional – worker continues without it)
_redis_l1: Optional[Any] = None
_heartbeat_task: Optional[asyncio.Task] = None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _build_redis_l1() -> Optional[Any]:
    """Create and return an async Redis L1 client, or None on failure."""
    try:
        import redis.asyncio as aioredis

        redis_host = getattr(config, "REDIS_L1_HOST", "redis-local")
        redis_port = int(getattr(config, "REDIS_L1_PORT", 6380))
        redis_password = getattr(config, "REDIS_L1_PASSWORD", "scarerunner")
        redis_db = int(getattr(config, "REDIS_L1_DB", 0))

        kwargs: Dict[str, Any] = {
            "host": redis_host,
            "port": redis_port,
            "db": redis_db,
            "decode_responses": True,
            "socket_connect_timeout": 5,
        }
        if redis_password:
            kwargs["password"] = redis_password

        client = aioredis.Redis(**kwargs)
        await client.ping()
        logger.info("Ollama worker connected to Redis L1: %s:%d", redis_host, redis_port)
        return client
    except Exception as exc:
        logger.warning(
            "Cannot connect to Redis L1 for heartbeat: %s – "
            "worker will start without availability signaling",
            exc,
        )
        return None


async def _publish_availability(redis_client: Any) -> None:
    """Set all availability keys in Redis L1."""
    payload = json.dumps({
        "worker_id": config.WORKER_ID,
        "service": "ollama",
        "job_types": ["ollama_generate", "ollama_chat"],
        "status": "available",
        "timestamp": _utcnow_iso(),
    })
    for key in _AVAILABILITY_KEYS:
        await redis_client.set(key, payload, ex=HEARTBEAT_TTL)


async def _heartbeat_loop() -> None:
    """Periodically refresh worker availability keys in Redis L1."""
    global _redis_l1

    while True:
        try:
            if _redis_l1 is not None:
                await _publish_availability(_redis_l1)
                logger.debug("Heartbeat refreshed for ollama worker (TTL=%ds)", HEARTBEAT_TTL)
        except Exception as exc:
            logger.warning("Heartbeat publish failed: %s", exc)
            _redis_l1 = await _build_redis_l1()

        await asyncio.sleep(HEARTBEAT_INTERVAL)


@app.on_event("startup")
async def startup() -> None:
    global _http_client, _redis_l1, _heartbeat_task
    _http_client = httpx.AsyncClient()

    # Connect to Redis L1 and register availability (best-effort)
    _redis_l1 = await _build_redis_l1()
    if _redis_l1 is not None:
        try:
            await _publish_availability(_redis_l1)
            logger.info("Ollama worker availability registered")
        except Exception as exc:
            logger.warning("Failed to register initial availability: %s", exc)

    _heartbeat_task = asyncio.create_task(_heartbeat_loop())
    logger.info(
        "Ollama worker %s ready – ollama=%s port=%d",
        config.WORKER_ID,
        config.OLLAMA_HOST,
        config.WORKER_PORT,
    )


@app.on_event("shutdown")
async def shutdown() -> None:
    global _http_client, _redis_l1, _heartbeat_task

    if _heartbeat_task is not None:
        _heartbeat_task.cancel()
        try:
            await _heartbeat_task
        except asyncio.CancelledError:
            pass

    if _redis_l1 is not None:
        try:
            for key in _AVAILABILITY_KEYS:
                await _redis_l1.delete(key)
            logger.info("Ollama worker availability keys removed")
        except Exception as exc:
            logger.warning("Failed to remove availability keys: %s", exc)
        await _redis_l1.aclose()

    if _http_client:
        await _http_client.aclose()
    logger.info("Ollama worker stopped")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> Dict[str, str]:
    """Liveness probe for Docker health check."""
    return {"status": "ok", "service": "ollama-worker"}


@app.post("/process")
async def process(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single Ollama job dispatched by GateKeeper.

    Accepts the raw job dict (same format as backend pushes to queue),
    calls the Ollama service, and returns the result dict that GateKeeper
    will persist for the backend BRPOP to retrieve.
    """
    job_id = job.get("job_id", "unknown")
    # Support both "job_type" (GateKeeper-native) and "type" (backend router format)
    job_type = job.get("job_type") or job.get("type", "")
    payload = job.get("payload", {})

    logger.info("[%s] Processing job: type=%s", job_id, job_type)

    try:
        if job_type == "ollama_generate":
            result = await _process_generate(job_id, payload)
        elif job_type == "ollama_chat":
            result = await _process_chat(job_id, payload)
        else:
            logger.error("[%s] Unknown job type: %s", job_id, job_type)
            raise HTTPException(status_code=400, detail=f"Unknown job type: {job_type}")

        logger.info("[%s] Job completed: status=%s", job_id, result.get("status"))
        return result

    except HTTPException:
        raise
    except httpx.HTTPStatusError as exc:
        logger.error("[%s] Ollama HTTP error: %s", job_id, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Ollama HTTP {exc.response.status_code}: {exc.response.text[:200]}",
        )
    except httpx.TimeoutException:
        logger.error("[%s] Ollama request timed out after %ds", job_id, config.OLLAMA_REQUEST_TIMEOUT)
        raise HTTPException(status_code=504, detail="Ollama request timed out")
    except Exception as exc:
        logger.error("[%s] Unexpected error: %s", job_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Ollama API callers
# ---------------------------------------------------------------------------


async def _process_generate(job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call POST /api/generate on the Ollama service.

    Returns result dict that matches what the backend router expects to
    receive after BRPOP:
        {"status": "success", "data": {"response": "...", "model": "..."}, "error": null}
    """
    endpoint = f"{config.OLLAMA_HOST}/api/generate"
    ollama_request = {
        "model": payload.get("model", "mistral"),
        "prompt": payload.get("prompt", ""),
        "stream": False,
        "options": payload.get("options", {}),
    }
    logger.debug("[%s] Calling Ollama /api/generate: model=%s", job_id, ollama_request["model"])

    assert _http_client is not None
    response = await _http_client.post(
        endpoint,
        json=ollama_request,
        timeout=httpx.Timeout(config.OLLAMA_REQUEST_TIMEOUT),
    )
    response.raise_for_status()
    data = response.json()

    return {
        "status": "success",
        "data": {
            "response": data.get("response", ""),
            "model": data.get("model", ollama_request["model"]),
        },
        "error": None,
    }


async def _process_chat(job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call POST /api/chat on the Ollama service.

    Returns result dict that matches what the backend router expects to
    receive after BRPOP:
        {"status": "success", "data": {"message": {...}, "model": "..."}, "error": null}
    """
    endpoint = f"{config.OLLAMA_HOST}/api/chat"
    ollama_request = {
        "model": payload.get("model", "mistral"),
        "messages": payload.get("messages", []),
        "stream": False,
        "options": payload.get("options", {}),
    }
    logger.debug("[%s] Calling Ollama /api/chat: model=%s", job_id, ollama_request["model"])

    assert _http_client is not None
    response = await _http_client.post(
        endpoint,
        json=ollama_request,
        timeout=httpx.Timeout(config.OLLAMA_REQUEST_TIMEOUT),
    )
    response.raise_for_status()
    data = response.json()

    return {
        "status": "success",
        "data": {
            "message": data.get("message", {}),
            "model": data.get("model", ollama_request["model"]),
        },
        "error": None,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.WORKER_PORT, log_level="warning")
