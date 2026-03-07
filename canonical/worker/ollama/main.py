"""
Ollama Worker – Stateless HTTP Job Processor.

Stateless FastAPI service called by GateKeeper to process Ollama LLM jobs.
GateKeeper handles all queue consumption (BRPOP), retry logic, dead-letter,
and result persistence. This worker is only responsible for calling Ollama.

Endpoints:
- POST /process  – Receive job from GateKeeper, call Ollama, return result
- GET  /health   – Liveness probe for Docker health check
"""

import logging
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
    title="Ollama Worker",
    description="Stateless HTTP worker for Ollama LLM inference. Called by GateKeeper.",
    version="1.0.0",
)

# Shared HTTP client (created at startup, reused across requests)
_http_client: Optional[httpx.AsyncClient] = None


@app.on_event("startup")
async def startup() -> None:
    global _http_client
    _http_client = httpx.AsyncClient()
    logger.info(
        "Ollama worker %s ready – ollama=%s port=%d",
        config.WORKER_ID,
        config.OLLAMA_HOST,
        config.WORKER_PORT,
    )


@app.on_event("shutdown")
async def shutdown() -> None:
    global _http_client
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
