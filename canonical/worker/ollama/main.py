"""
Ollama Queue Consumer Worker – Main Entry Point.

Consumes jobs from Redis queue and forwards them to the Ollama LLM service.

Responsibilities:
- BRPOP from Redis queue (scareverse:ollama-jobs:queue)
- Parse job payload (type: ollama_generate or ollama_chat)
- Forward to Ollama API (http://ollama:11434/api/generate or /api/chat)
- Store result in Redis LIST for BRPOP retrieval by backend router
- Handle errors gracefully with structured error results
- Provide /health FastAPI endpoint for Docker health checks
- Graceful shutdown on SIGTERM
"""

import asyncio
import json
import logging
import signal
from typing import Any, Dict, Optional

import httpx
import redis.asyncio as aioredis
import uvicorn
from fastapi import FastAPI

import config

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shutdown event (shared across tasks)
# ---------------------------------------------------------------------------

_shutdown_event = asyncio.Event()


def _handle_signal(sig: int, _frame: Any) -> None:
    logger.info("Signal %d received – initiating graceful shutdown", sig)
    _shutdown_event.set()


# ---------------------------------------------------------------------------
# FastAPI app (health endpoint only)
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Ollama Queue Consumer",
    description="Redis queue consumer for Ollama LLM inference.",
    version="1.0.0",
)


@app.get("/health")
async def health() -> Dict[str, str]:
    """Liveness probe for Docker health check."""
    return {"status": "ok", "service": "ollama-consumer"}


# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------


def _build_redis() -> aioredis.Redis:
    """Construct an async Redis client from config."""
    kwargs: Dict[str, Any] = {
        "host": config.REDIS_L1_HOST,
        "port": config.REDIS_L1_PORT,
        "db": config.REDIS_L1_DB,
        "decode_responses": True,
        "socket_connect_timeout": 10,
        "socket_keepalive": True,
    }
    if config.REDIS_L1_PASSWORD:
        kwargs["password"] = config.REDIS_L1_PASSWORD
    return aioredis.Redis(**kwargs)


async def _store_result(
    redis_client: aioredis.Redis,
    job_id: str,
    result: Dict[str, Any],
) -> None:
    """Store job result in Redis LIST for backend BRPOP retrieval."""
    result_key = f"{config.RESULTS_KEY_PREFIX}:{job_id}"
    try:
        await redis_client.rpush(result_key, json.dumps(result))
        await redis_client.expire(result_key, config.RESULT_KEY_TTL)
        logger.debug(
            "[%s] Result stored at %s (TTL: %ds)",
            job_id,
            result_key,
            config.RESULT_KEY_TTL,
        )
    except Exception as exc:
        logger.error("[%s] Failed to store result in Redis: %s", job_id, exc)


# ---------------------------------------------------------------------------
# Job processors
# ---------------------------------------------------------------------------


async def _process_generate(
    http: httpx.AsyncClient,
    job_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process an ollama_generate job.

    Calls POST /api/generate on the Ollama service and returns a result
    dict matching the format expected by the backend router:
        {"status": "success", "data": {"response": "...", "model": "..."}, "error": null}
    """
    endpoint = f"{config.OLLAMA_HOST}/api/generate"
    ollama_request = {
        "model": payload.get("model", "mistral"),
        "prompt": payload.get("prompt", ""),
        "stream": False,
        "options": payload.get("options", {}),
    }
    logger.debug(
        "[%s] Calling Ollama /api/generate: model=%s",
        job_id,
        ollama_request["model"],
    )

    response = await http.post(
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


async def _process_chat(
    http: httpx.AsyncClient,
    job_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process an ollama_chat job.

    Calls POST /api/chat on the Ollama service and returns a result
    dict matching the format expected by the backend router:
        {"status": "success", "data": {"message": {...}, "model": "..."}, "error": null}
    """
    endpoint = f"{config.OLLAMA_HOST}/api/chat"
    ollama_request = {
        "model": payload.get("model", "mistral"),
        "messages": payload.get("messages", []),
        "stream": False,
        "options": payload.get("options", {}),
    }
    logger.debug(
        "[%s] Calling Ollama /api/chat: model=%s",
        job_id,
        ollama_request["model"],
    )

    response = await http.post(
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
# Job loop
# ---------------------------------------------------------------------------


async def _job_loop(redis_client: aioredis.Redis, http: httpx.AsyncClient) -> None:
    """Continuously dequeue jobs from Redis and dispatch to Ollama."""
    logger.info("Job loop started – consuming from %s", config.JOB_QUEUE)

    while not _shutdown_event.is_set():
        try:
            brpop_result = await redis_client.brpop(
                config.JOB_QUEUE,
                timeout=config.BRPOP_TIMEOUT,
            )
            if brpop_result is None:
                logger.debug("BRPOP timeout – no job available, waiting")
                continue

            _, raw_job = brpop_result
            try:
                job = json.loads(raw_job)
            except json.JSONDecodeError as exc:
                logger.error(
                    "Invalid JSON payload – skipping: %s | raw=%s",
                    exc,
                    raw_job[:200],
                )
                continue

            job_id = job.get("job_id", "unknown")
            job_type = job.get("type", "")
            payload = job.get("payload", {})

            logger.info("[%s] Job received: type=%s", job_id, job_type)

            try:
                if job_type == "ollama_generate":
                    result_data = await _process_generate(http, job_id, payload)
                elif job_type == "ollama_chat":
                    result_data = await _process_chat(http, job_id, payload)
                else:
                    logger.error("[%s] Unknown job type: %s", job_id, job_type)
                    result_data = {
                        "status": "error",
                        "data": None,
                        "error": f"Unknown job type: {job_type}",
                    }

                logger.info(
                    "[%s] Job processed: status=%s",
                    job_id,
                    result_data.get("status"),
                )

            except httpx.HTTPStatusError as exc:
                logger.error("[%s] Ollama HTTP error: %s", job_id, exc)
                result_data = {
                    "status": "error",
                    "data": None,
                    "error": f"Ollama HTTP {exc.response.status_code}: {exc.response.text[:200]}",
                }
            except httpx.TimeoutException:
                logger.error("[%s] Ollama request timed out after %ds", job_id, config.OLLAMA_REQUEST_TIMEOUT)
                result_data = {
                    "status": "error",
                    "data": None,
                    "error": "Ollama request timed out",
                }
            except Exception as exc:
                logger.error("[%s] Unexpected error processing job: %s", job_id, exc, exc_info=True)
                result_data = {
                    "status": "error",
                    "data": None,
                    "error": str(exc),
                }

            await _store_result(redis_client, job_id, result_data)

        except asyncio.CancelledError:
            logger.info("Job loop cancelled – exiting")
            break
        except Exception as exc:
            logger.error("Job loop top-level error: %s", exc, exc_info=True)
            await asyncio.sleep(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info(
        "Ollama consumer %s starting – queue=%s, ollama=%s",
        config.WORKER_ID,
        config.JOB_QUEUE,
        config.OLLAMA_HOST,
    )

    redis_client = _build_redis()

    uvicorn_config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=config.HEALTH_PORT,
        log_level="warning",
    )
    server = uvicorn.Server(uvicorn_config)

    async with httpx.AsyncClient() as http:
        job_task = asyncio.create_task(_job_loop(redis_client, http), name="job_loop")
        server_task = asyncio.create_task(server.serve(), name="health_server")

        await _shutdown_event.wait()
        logger.info("Shutdown requested – stopping tasks")

        job_task.cancel()
        server.should_exit = True

        await asyncio.gather(job_task, server_task, return_exceptions=True)

    await redis_client.aclose()
    logger.info("Ollama consumer stopped")


if __name__ == "__main__":
    asyncio.run(main())
