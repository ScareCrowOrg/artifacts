"""
Stable Diffusion Queue Consumer Worker – Main Entry Point.

Consumes jobs from Redis queue and forwards them to the ScareNode-SD API service.

Responsibilities:
- BRPOP from Redis queue (scareverse:sd-jobs:queue)
- Parse job payload (type: sd_generate)
- Forward to SD API (http://scarenode-sd:9090/generate)
- Store result in Redis LIST for BRPOP retrieval by backend router
- Track processing time (processing_time_ms)
- Handle errors gracefully with structured error results
- Provide /health FastAPI endpoint for Docker health checks
- Graceful shutdown on SIGTERM
"""

import asyncio
import json
import logging
import signal
import time
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
    title="Stable Diffusion Queue Consumer",
    description="Redis queue consumer for Stable Diffusion image generation.",
    version="1.0.0",
)


@app.get("/health")
async def health() -> Dict[str, str]:
    """Liveness probe for Docker health check."""
    return {"status": "ok", "service": "sd-consumer"}


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
# Job processor
# ---------------------------------------------------------------------------


async def _process_sd_generate(
    http: httpx.AsyncClient,
    job_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process an sd_generate job.

    Calls POST /generate on the ScareNode-SD service and returns a result
    dict matching the format expected by the backend router:
        {
            "status": "success",
            "image_base64": "...",
            "model": "stabilityai/...",
            "processing_time_ms": 1234.5
        }
    """
    endpoint = f"{config.SD_HOST}/generate"
    sd_request = {
        "model": payload.get("model", config.SD_MODEL),
        "prompt": payload.get("prompt", ""),
        "negative_prompt": payload.get("negative_prompt", ""),
        "height": payload.get("height", 512),
        "width": payload.get("width", 512),
        "num_inference_steps": payload.get("num_inference_steps", 20),
        "guidance_scale": payload.get("guidance_scale", 7.5),
        "seed": payload.get("seed", -1),
    }
    logger.debug(
        "[%s] Calling SD /generate: model=%s size=%dx%d steps=%d",
        job_id,
        sd_request["model"],
        sd_request["width"],
        sd_request["height"],
        sd_request["num_inference_steps"],
    )

    start_time = time.monotonic()
    response = await http.post(
        endpoint,
        json=sd_request,
        timeout=httpx.Timeout(config.SD_REQUEST_TIMEOUT),
    )
    response.raise_for_status()
    processing_time_ms = (time.monotonic() - start_time) * 1000

    data = response.json()

    if data.get("status") == "success":
        return {
            "status": "success",
            "image_base64": data.get("image_base64"),
            "model": data.get("model", sd_request["model"]),
            "processing_time_ms": processing_time_ms,
        }

    # SD API returned non-success status
    error_msg = data.get("error", "SD API returned non-success status")
    logger.error("[%s] SD API error: %s", job_id, error_msg)
    return {
        "status": "error",
        "image_base64": None,
        "model": None,
        "error": error_msg,
    }


# ---------------------------------------------------------------------------
# Job loop
# ---------------------------------------------------------------------------


async def _job_loop(redis_client: aioredis.Redis, http: httpx.AsyncClient) -> None:
    """Continuously dequeue jobs from Redis and dispatch to SD service."""
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
                if job_type == "sd_generate":
                    result_data = await _process_sd_generate(http, job_id, payload)
                else:
                    logger.error("[%s] Unknown job type: %s", job_id, job_type)
                    result_data = {
                        "status": "error",
                        "image_base64": None,
                        "model": None,
                        "error": f"Unknown job type: {job_type}",
                    }

                logger.info(
                    "[%s] Job processed: status=%s",
                    job_id,
                    result_data.get("status"),
                )

            except httpx.HTTPStatusError as exc:
                logger.error(
                    "[%s] SD API HTTP error: %d – %s",
                    job_id,
                    exc.response.status_code,
                    exc.response.text[:200],
                )
                result_data = {
                    "status": "error",
                    "image_base64": None,
                    "model": None,
                    "error": f"SD API HTTP {exc.response.status_code}: {exc.response.text[:200]}",
                }
            except httpx.TimeoutException:
                logger.error(
                    "[%s] SD API request timed out after %ds",
                    job_id,
                    config.SD_REQUEST_TIMEOUT,
                )
                result_data = {
                    "status": "error",
                    "image_base64": None,
                    "model": None,
                    "error": "SD generation request timed out",
                }
            except Exception as exc:
                logger.error(
                    "[%s] Unexpected error processing job: %s",
                    job_id,
                    exc,
                    exc_info=True,
                )
                result_data = {
                    "status": "error",
                    "image_base64": None,
                    "model": None,
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
        "SD consumer %s starting – queue=%s, sd_host=%s",
        config.WORKER_ID,
        config.JOB_QUEUE,
        config.SD_HOST,
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
    logger.info("SD consumer stopped")


if __name__ == "__main__":
    asyncio.run(main())
