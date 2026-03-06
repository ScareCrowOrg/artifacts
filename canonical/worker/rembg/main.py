"""
Rembg Atomic Worker – FastAPI Service.

Stateless background removal service. Accepts base64-encoded images via
HTTP POST /process and returns the result as a base64-encoded PNG.

Endpoints:
  POST /process   – Remove background from image.
  GET  /health    – Liveness probe.
"""

import logging
import os
from typing import Optional

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
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Rembg Worker",
    description="Atomic background removal service for ScareVerse.",
    version="1.0.0",
)

# Singleton service (lazy-loaded on first request)
_rembg_service: Optional[RembgService] = None


def get_service() -> RembgService:
    """Return the singleton RembgService, creating it on first call."""
    global _rembg_service
    if _rembg_service is None:
        _rembg_service = RembgService()
    return _rembg_service


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
