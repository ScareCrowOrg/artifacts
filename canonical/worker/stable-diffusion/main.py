"""
Stable Diffusion Worker – Stateless HTTP Job Processor.

Stateless FastAPI service called by GateKeeper to process SD image generation jobs.
GateKeeper handles all queue consumption (BRPOP), retry logic, dead-letter,
and result persistence. This worker is only responsible for calling the SD API.

Endpoints:
- POST /process  – Receive job from GateKeeper, call SD API, return result
- GET  /health   – Liveness probe for Docker health check
"""

import logging
import time
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
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Stable Diffusion Worker",
    description="Stateless HTTP worker for SD image generation. Called by GateKeeper.",
    version="1.0.0",
)

# Shared HTTP client (created at startup, reused across requests)
_http_client: Optional[httpx.AsyncClient] = None


@app.on_event("startup")
async def startup() -> None:
    global _http_client
    _http_client = httpx.AsyncClient()
    logger.info(
        "SD worker %s ready – sd_host=%s port=%d",
        config.WORKER_ID,
        config.SD_HOST,
        config.WORKER_PORT,
    )


@app.on_event("shutdown")
async def shutdown() -> None:
    global _http_client
    if _http_client:
        await _http_client.aclose()
    logger.info("SD worker stopped")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> Dict[str, str]:
    """Liveness probe for Docker health check."""
    return {"status": "ok", "service": "sd-worker"}


@app.post("/process")
async def process(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single SD image generation job dispatched by GateKeeper.

    Accepts the raw job dict (same format as backend pushes to queue),
    calls the ScareNode-SD service, and returns the result dict that
    GateKeeper will persist for the backend BRPOP to retrieve.
    """
    job_id = job.get("job_id", "unknown")
    # Support both "job_type" (GateKeeper-native) and "type" (backend router format)
    job_type = job.get("job_type") or job.get("type", "")
    payload = job.get("payload", {})

    logger.info("[%s] Processing job: type=%s", job_id, job_type)

    try:
        if job_type == "sd_generate":
            result = await _process_sd_generate(job_id, payload)
        else:
            logger.error("[%s] Unknown job type: %s", job_id, job_type)
            raise HTTPException(status_code=400, detail=f"Unknown job type: {job_type}")

        logger.info("[%s] Job completed: status=%s", job_id, result.get("status"))
        return result

    except HTTPException:
        raise
    except httpx.HTTPStatusError as exc:
        logger.error(
            "[%s] SD API HTTP error: %d - %s",
            job_id,
            exc.response.status_code,
            exc.response.text[:200],
        )
        raise HTTPException(
            status_code=502,
            detail=f"SD API HTTP {exc.response.status_code}: {exc.response.text[:200]}",
        )
    except httpx.TimeoutException:
        logger.error("[%s] SD request timed out after %ds", job_id, config.SD_REQUEST_TIMEOUT)
        raise HTTPException(status_code=504, detail="SD generation request timed out")
    except Exception as exc:
        logger.error("[%s] Unexpected error: %s", job_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# SD API caller
# ---------------------------------------------------------------------------


async def _process_sd_generate(
    job_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Call POST /generate on the ScareNode-SD service.

    Returns result dict that matches what the backend router expects to
    receive after BRPOP:
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
    assert _http_client is not None
    response = await _http_client.post(
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
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=config.WORKER_PORT, log_level="warning")
