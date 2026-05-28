"""
ComfyUI ScareVerse Wrapper
FastAPI wrapper that translates ScareVerse-style API to ComfyUI native API.

Endpoints:
- GET /health: Health check
- POST /generate: Generates image from prompt via ComfyUI workflow
- POST /workflow: (Future) Executes raw ComfyUI workflow JSON
"""

import asyncio
import base64
import httpx
import logging
import os
import random
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

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

_COMFYUI_BASE = f"http://{config.COMFYUI_HOST}:{config.COMFYUI_PORT}"


# ── Pydantic models ──────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    width: int = Field(default=1024, ge=64, le=2048)
    height: int = Field(default=1024, ge=64, le=2048)
    steps: int = Field(default=20, ge=1, le=150)
    cfg_scale: float = Field(default=7.0, ge=1.0, le=30.0)
    seed: int = -1  # -1 = random
    model: str = "sd_xl_base_1.0.safetensors"


class GenerateResponse(BaseModel):
    status: str
    image_base64: str
    seed: int


# ── Lifecycle ────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    service = BaseService(_SERVICE_NAME, logger=logger, service_port=config.WRAPPER_PORT)
    asyncio.create_task(service.heartbeat())
    logger.info("Redis heartbeat started for service '%s' (port %d)", _SERVICE_NAME, config.WRAPPER_PORT)


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "service": _SERVICE_NAME}


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    start_log = dict(req, prompt=req.prompt[:80])
    logger.info("POST /generate called: %s", start_log)

    # Resolve seed (-1 = random)
    seed = random.randint(0, 2**31 - 1) if req.seed == -1 else req.seed

    # Build ComfyUI workflow JSON
    prompt_id = str(uuid.uuid4())
    workflow = _build_workflow(req, seed, prompt_id)
    logger.info("Workflow built with %d nodes, prompt_id prefix=%s", len(workflow), prompt_id)

    # Submit to ComfyUI native API
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            submit_payload = {"prompt": workflow}
            logger.debug("POST %s/prompt", _COMFYUI_BASE)
            submit_resp = await client.post(f"{_COMFYUI_BASE}/prompt", json=submit_payload)
            submit_resp.raise_for_status()
            submit_data = submit_resp.json()
            comfy_prompt_id = submit_data["prompt_id"]
            logger.info("ComfyUI accepted prompt: %s", comfy_prompt_id)
    except Exception as exc:
        logger.error("Failed to submit workflow to ComfyUI: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"ComfyUI submission failed: {exc}")

    # Poll /history/{prompt_id} until completed or timeout
    image_filename = await _poll_for_result(comfy_prompt_id, config.COMFYUI_GENERATE_TIMEOUT)
    if image_filename is None:
        logger.error("Timeout polling ComfyUI history for prompt %s", comfy_prompt_id)
        raise HTTPException(status_code=504, detail=f"ComfyUI generation timed out after {config.COMFYUI_GENERATE_TIMEOUT}s")

    # Read image from disk and encode as base64
    output_dir = "/app/comfyui/output"
    image_path = os.path.join(output_dir, image_filename)
    if not os.path.exists(image_path):
        logger.error("Image file not found: %s", image_path)
        raise HTTPException(status_code=502, detail=f"Output image not found: {image_filename}")

    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode("utf-8")

    logger.info("Image generated: %s (%d bytes, seed=%d)", image_filename, len(image_base64), seed)
    return GenerateResponse(status="success", image_base64=image_base64, seed=seed)


@app.post("/workflow")
async def workflow():
    """Future: Execute raw ComfyUI workflow JSON."""
    raise HTTPException(status_code=501, detail="Raw workflow execution not yet implemented")


# ── Workflow builder ─────────────────────────────────────────────────────────

def _build_workflow(req: GenerateRequest, seed: int, prefix: str) -> Dict[str, Any]:
    """
    Build a standard SDXL ComfyUI workflow from generation parameters.

    Node graph:
        CheckpointLoaderSimple → CLIPTextEncode (pos+neg) → EmptyLatentImage
            → KSampler → VAEDecode → SaveImage
    """
    return {
        "1": {  # Load Checkpoint
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": req.model},
        },
        "2": {  # Positive prompt encode
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": req.prompt,
                "clip": ["1", 1],
            },
        },
        "3": {  # Negative prompt encode
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": req.negative_prompt,
                "clip": ["1", 1],
            },
        },
        "4": {  # Empty latent
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": req.width,
                "height": req.height,
                "batch_size": 1,
            },
        },
        "5": {  # KSampler
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": req.steps,
                "cfg": req.cfg_scale,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {  # VAE Decode
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["5", 0],
                "vae": ["1", 2],
            },
        },
        "7": {  # Save Image
            "class_type": "SaveImage",
            "inputs": {
                "images": ["6", 0],
                "filename_prefix": f"scareverse_{prefix}",
            },
        },
    }


# ── History polling ──────────────────────────────────────────────────────────

async def _poll_for_result(comfy_prompt_id: str, timeout: int) -> Optional[str]:
    """
    Poll GET /history/{prompt_id} until ComfyUI marks the prompt as completed.

    Returns the output image filename, or None on timeout.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    url = f"{_COMFYUI_BASE}/history/{comfy_prompt_id}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        while asyncio.get_running_loop().time() < deadline:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    entry = data.get(comfy_prompt_id)
                    if entry and entry.get("status", {}).get("completed") is True:
                        filename = _extract_output_filename(entry)
                        if filename:
                            return filename
                        logger.warning("History completed but no output image found for %s", comfy_prompt_id)
                        return None
            except Exception as exc:
                logger.debug("Poll attempt failed for %s: %s", comfy_prompt_id, exc)

            await asyncio.sleep(config.COMFYUI_POLL_INTERVAL)

    return None  # timeout


def _extract_output_filename(history_entry: Dict[str, Any]) -> Optional[str]:
    """
    Extract the first output image filename from a ComfyUI history entry.

    The outputs dict is keyed by node_id. SaveImage (node 7) produces
    an images array with filename/subfolder/type entries.
    """
    outputs: Dict[str, Any] = history_entry.get("outputs", {})
    for node_id, node_output in outputs.items():
        images: List[Dict[str, str]] = node_output.get("images", [])
        for img in images:
            fname = img.get("filename")
            if fname:
                subfolder = img.get("subfolder", "")
                if subfolder:
                    return os.path.join(subfolder, fname)
                return fname
    return None


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting ComfyUI wrapper on 0.0.0.0:%d", config.WRAPPER_PORT)
    uvicorn.run(app, host="0.0.0.0", port=config.WRAPPER_PORT, log_level="info")
