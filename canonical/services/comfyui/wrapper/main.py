"""
ComfyUI ScareVerse Wrapper
FastAPI wrapper that translates ScareVerse-style API to ComfyUI native API.
Currently a scaffold — job type integration comes in future phases.

Endpoints:
- GET /health: Health check
- POST /generate: (Future) Generates image/mesh via ComfyUI workflow
- POST /workflow: (Future) Executes raw ComfyUI workflow JSON
"""

import asyncio
import logging

from fastapi import FastAPI, HTTPException

from canonical.shared.services.base_service import BaseService
from wrapper import config

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

_SERVICE_NAME = "comfyui"

app = FastAPI(
    title="ComfyUI ScareVerse Wrapper",
    description="Unified GPU-accelerated generation (2D image + 3D mesh) via ComfyUI",
    version="1.0.0"
)


@app.on_event("startup")
async def startup_event():
    """Register Redis heartbeat on startup."""
    service = BaseService(_SERVICE_NAME, logger=logger, service_port=config.WRAPPER_PORT)
    asyncio.create_task(service.heartbeat())
    logger.info("Redis heartbeat started for service '%s' (port %d)", _SERVICE_NAME, config.WRAPPER_PORT)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": _SERVICE_NAME}


@app.post("/generate")
async def generate():
    """Future: Generate image/mesh from prompt. Requires job-type integration."""
    raise HTTPException(status_code=501, detail="Job type integration not yet implemented")


@app.post("/workflow")
async def workflow():
    """Future: Execute raw ComfyUI workflow JSON."""
    raise HTTPException(status_code=501, detail="Job type integration not yet implemented")


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting ComfyUI wrapper on 0.0.0.0:%d", config.WRAPPER_PORT)
    uvicorn.run(app, host="0.0.0.0", port=config.WRAPPER_PORT, log_level="info")
