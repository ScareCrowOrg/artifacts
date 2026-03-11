#!/usr/bin/env python3
"""
InstantMesh FastAPI Service

Provides 3D mesh generation via the InstantMesh model with Redis L1 heartbeat
registration so GateKeeper can detect this service without HTTP probing.

Endpoints:
- POST /generate: Generate 3D mesh from an input image (base64)
- GET /health: Health check

Architecture:
- Redis L1 heartbeat: registers state:service:instantmesh:available on startup
- Fire-and-forget heartbeat pattern (doesn't block service startup)
- Listens on port 8000 (matches instantmesh.json endpoint config)
"""

import asyncio
import logging
import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from canonical.shared.services.base_service import BaseService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="InstantMesh Service",
    description="3D mesh generation service with Redis heartbeat",
    version="1.0.0",
)

_SERVICE_NAME = "instantmesh"
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8000"))
SERVICE_HOST = os.getenv("SERVICE_HOST", "0.0.0.0")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    """Request model for /generate endpoint."""

    image_base64: str = Field(..., description="Base64-encoded input image")
    num_views: int = Field(default=6, ge=1, le=8, description="Number of views for 3D reconstruction")


class GenerateResponse(BaseModel):
    """Response model for /generate endpoint."""

    status: str
    mesh_base64: Optional[str] = None
    mesh_url: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup_event() -> None:
    """Start the Redis heartbeat loop as a background task on app startup."""
    service = BaseService(_SERVICE_NAME, logger=logger)
    asyncio.create_task(service.heartbeat())
    logger.info("Redis heartbeat task started for service '%s'", _SERVICE_NAME)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    """
    Generate a 3D mesh from an input image.

    Args:
        request: GenerateRequest with base64-encoded image and optional num_views.

    Returns:
        GenerateResponse with mesh_base64 or mesh_url on success, error on failure.
    """
    logger.info(
        "Generate request: num_views=%d, image_base64_len=%d",
        request.num_views,
        len(request.image_base64),
    )

    try:
        # TODO: Integrate actual InstantMesh model inference here.
        # Steps:
        #   1. Decode image_base64 to PIL Image
        #   2. Run InstantMesh model (https://github.com/TencentARC/InstantMesh)
        #   3. Return generated mesh as base64 or presigned URL
        # For an external service setup, proxy the request to the external endpoint.
        raise NotImplementedError("InstantMesh inference not yet implemented")

    except NotImplementedError as exc:
        logger.error("InstantMesh generation not implemented: %s", exc)
        raise HTTPException(status_code=501, detail=str(exc))

    except Exception as exc:
        logger.error("InstantMesh generation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=SERVICE_HOST, port=SERVICE_PORT, log_level="info")
