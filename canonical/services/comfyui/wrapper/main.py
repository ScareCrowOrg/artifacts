"""
ComfyUI ScareVerse Wrapper
FastAPI wrapper that translates ScareVerse-style API to ComfyUI native API.

Endpoints:
- GET /health: Health check
- POST /generate: Generates image from prompt via ComfyUI workflow (SDXL)
- POST /generate-3d: Generates 3D mesh from image via Hunyuan3DWrapper workflow
- POST /workflow: Executes raw ComfyUI workflow JSON
"""

import asyncio
import base64
import httpx
import json
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
    version="1.1.0"
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


class Generate3DRequest(BaseModel):
    image_base64: str = Field(..., description="Base64-encoded PNG image")
    seed: int = Field(-1, description="Random seed (-1 = random)")


class Generate3DResponse(BaseModel):
    status: str
    mesh_base64: str
    mesh_format: str = "glb"
    seed: int


class WorkflowRequest(BaseModel):
    workflow: Dict[str, Any] = Field(..., description="Raw ComfyUI workflow JSON")
    timeout: int = Field(default=300, ge=30, le=600, description="Max polling timeout in seconds")
    output_node_id: Optional[str] = Field(default=None, description="Node ID to extract output from (auto-detected if None)")
    output_key: str = Field(default="images", description="Output key to extract from the node output")


class WorkflowResponse(BaseModel):
    status: str
    prompt_id: str
    outputs: Dict[str, Any]


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


@app.post("/generate-3d", response_model=Generate3DResponse)
async def generate_3d(req: Generate3DRequest):
    """
    Generate 3D mesh from image via Hunyuan3DWrapper (ComfyUI).

    1. Save input image to /app/comfyui/input/
    2. Build Hunyuan3D workflow (LoadImage → Hunyuan3DWrapper → SaveGLB)
    3. POST to ComfyUI /prompt
    4. Poll /history/{prompt_id}
    5. Read GLB output, base64-encode
    6. Return base64 GLB + seed
    """
    logger.info("POST /generate-3d called (seed=%d, image_base64 length=%d)", req.seed, len(req.image_base64[:100]))

    # Resolve seed
    seed = random.randint(0, 2 ** 31 - 1) if req.seed == -1 else req.seed

    # Save input image
    input_filename = f"hunyuan3d_input_{uuid.uuid4().hex}.png"
    input_dir = "/app/comfyui/input"
    os.makedirs(input_dir, exist_ok=True)
    input_path = os.path.join(input_dir, input_filename)

    try:
        image_bytes = base64.b64decode(req.image_base64)
        with open(input_path, "wb") as f:
            f.write(image_bytes)
        logger.info("Input image saved: %s (%d bytes)", input_path, len(image_bytes))
    except Exception as exc:
        logger.error("Failed to save input image: %s", exc)
        raise HTTPException(status_code=400, detail=f"Invalid image data: {exc}")

    # Build Hunyuan3D workflow
    prompt_id = str(uuid.uuid4())
    workflow = _build_hunyuan3d_workflow(input_filename, seed, prompt_id)
    logger.info("Hunyuan3D workflow built with %d nodes", len(workflow))

    # Submit to ComfyUI
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            submit_payload = {"prompt": workflow}
            submit_resp = await client.post(f"{_COMFYUI_BASE}/prompt", json=submit_payload)
            submit_resp.raise_for_status()
            submit_data = submit_resp.json()
            comfy_prompt_id = submit_data["prompt_id"]
            logger.info("ComfyUI accepted Hunyuan3D prompt: %s", comfy_prompt_id)
    except Exception as exc:
        logger.error("Failed to submit Hunyuan3D workflow to ComfyUI: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"ComfyUI submission failed: {exc}")

    # Poll for result
    glb_filename = await _poll_for_result_3d(comfy_prompt_id, config.HUNYUAN3D_GENERATE_TIMEOUT)
    if glb_filename is None:
        logger.error("Timeout polling ComfyUI history for Hunyuan3D prompt %s", comfy_prompt_id)
        raise HTTPException(status_code=504, detail=f"Hunyuan3D generation timed out after {config.HUNYUAN3D_GENERATE_TIMEOUT}s")

    # Read GLB from disk
    output_dir = "/app/comfyui/output"
    glb_path = os.path.join(output_dir, glb_filename)
    if not os.path.exists(glb_path):
        logger.error("GLB file not found: %s", glb_path)
        raise HTTPException(status_code=502, detail=f"Output GLB not found: {glb_filename}")

    with open(glb_path, "rb") as f:
        mesh_base64 = base64.b64encode(f.read()).decode("utf-8")

    logger.info("3D mesh generated: %s (%d bytes, seed=%d)", glb_filename, len(mesh_base64), seed)
    return Generate3DResponse(status="success", mesh_base64=mesh_base64, seed=seed)


@app.post("/workflow", response_model=WorkflowResponse)
async def execute_workflow(req: WorkflowRequest):
    """
    Execute raw ComfyUI workflow JSON.

    Accepts any valid ComfyUI workflow, submits to native API,
    polls for completion, and returns all output files as a dict.

    If output_node_id is provided, only outputs from that node are returned.
    Otherwise, all node outputs are returned.
    """
    logger.info("POST /workflow called (%d nodes, timeout=%ds)", len(req.workflow), req.timeout)

    # Submit to ComfyUI
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            submit_payload = {"prompt": req.workflow}
            submit_resp = await client.post(f"{_COMFYUI_BASE}/prompt", json=submit_payload)
            submit_resp.raise_for_status()
            submit_data = submit_resp.json()
            comfy_prompt_id = submit_data["prompt_id"]
            logger.info("ComfyUI accepted workflow prompt: %s", comfy_prompt_id)
    except Exception as exc:
        logger.error("Failed to submit workflow to ComfyUI: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"Workflow submission failed: {exc}")

    # Poll for completion
    history_entry = await _poll_for_history(comfy_prompt_id, req.timeout)
    if history_entry is None:
        logger.error("Timeout polling workflow %s", comfy_prompt_id)
        raise HTTPException(status_code=504, detail=f"Workflow timed out after {req.timeout}s")

    # Extract outputs
    outputs = history_entry.get("outputs", {})

    # Filter by output_node_id if specified
    if req.output_node_id:
        filtered = {}
        node_output = outputs.get(req.output_node_id, {})
        # Return the specific key requested (default "images")
        filtered[req.output_key] = node_output.get(req.output_key, [])
        outputs = filtered

    logger.info("Workflow %s completed, %d output nodes", comfy_prompt_id, len(outputs))
    return WorkflowResponse(
        status="success",
        prompt_id=comfy_prompt_id,
        outputs=outputs,
    )


# ── Workflow builders ────────────────────────────────────────────────────────

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


# ── Hunyuan3D 3D mesh workflow ─────────────────────────────────────────────

def _build_hunyuan3d_workflow(image_filename: str, seed: int, prefix: str) -> Dict[str, Any]:
    """
    Build a Hunyuan3D v2 FP8 ComfyUI workflow.

    Node graph:
        LoadImage → Hunyuan3DWrapper → SaveGLB

    The Hunyuan3DWrapper custom node (Kijai) takes an image as input and
    generates a 3D mesh (GLB) as output. The SaveGLB node writes the
    mesh to /app/comfyui/output/.
    """
    return {
        "1": {  # Load Image
            "class_type": "LoadImage",
            "inputs": {"image": image_filename},
        },
        "2": {  # Hunyuan3DWrapper v2 FP8 — Image to 3D
            "class_type": "Hunyuan3DWrapper",
            "inputs": {
                "image": ["1", 0],
                "seed": seed,
                "model_type": config.HUNYUAN3D_MODEL_NAME,
                "output_format": "glb",
            },
        },
        "3": {  # Save GLB
            "class_type": "SaveGLB",
            "inputs": {
                "mesh": ["2", 0],
                "filename_prefix": f"hunyuan3d_{prefix}",
            },
        },
    }


async def _poll_for_result_3d(comfy_prompt_id: str, timeout: int) -> Optional[str]:
    """
    Poll GET /history/{prompt_id} until ComfyUI marks prompt as completed.

    Returns the output GLB filename, or None on timeout.
    Extracts from any node output that has 'glb' files or the first
    non-image output.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    url = f"{_COMFYUI_BASE}/history/{comfy_prompt_id}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        while asyncio.get_running_loop().time() < deadline:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    entry = data.get(comfy_prompt_id)
                    if entry and entry.get("status", {}).get("completed") is True:
                        glb_filename = _extract_glb_filename(entry)
                        if glb_filename:
                            return glb_filename
                        logger.warning("History completed but no GLB output found for %s", comfy_prompt_id)
                        return None
            except Exception as exc:
                logger.debug("Poll attempt failed for %s: %s", comfy_prompt_id, exc)

            await asyncio.sleep(config.HUNYUAN3D_POLL_INTERVAL)

    return None  # timeout


def _extract_glb_filename(history_entry: Dict[str, Any]) -> Optional[str]:
    """
    Extract the first GLB output filename from a ComfyUI history entry.

    Looks for:
    1. 'glb' key in node outputs (direct GLB output)
    2. Any 'files' array with file entries ending in .glb
    3. First 'images' entry (fallback — some custom nodes report GLBs as images)
    """
    outputs: Dict[str, Any] = history_entry.get("outputs", {})
    for node_id, node_output in outputs.items():
        # Check for direct 'glb' key
        glb_data = node_output.get("glb")
        if glb_data and isinstance(glb_data, dict):
            filename = glb_data.get("filename")
            if filename:
                return filename

        # Check for generic 'files' array (SaveGLB may use this)
        files: List[Dict[str, str]] = node_output.get("files", [])
        for f in files:
            fname = f.get("filename", "")
            if fname.endswith(".glb"):
                subfolder = f.get("subfolder", "")
                if subfolder:
                    return os.path.join(subfolder, fname)
                return fname

        # Fallback: check images array
        images: List[Dict[str, str]] = node_output.get("images", [])
        for img in images:
            fname = img.get("filename", "")
            if fname.endswith(".glb"):
                subfolder = img.get("subfolder", "")
                if subfolder:
                    return os.path.join(subfolder, fname)
                return fname

    return None


async def _poll_for_history(comfy_prompt_id: str, timeout: int) -> Optional[Dict[str, Any]]:
    """
    Poll GET /history/{prompt_id} until ComfyUI marks the prompt as completed.

    Returns the full history entry dict, or None on timeout.
    Used by the generic /workflow endpoint to support arbitrary workflows.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    url = f"{_COMFYUI_BASE}/history/{comfy_prompt_id}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        while asyncio.get_running_loop().time() < deadline:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    entry = data.get(comfy_prompt_id)
                    if entry and entry.get("status", {}).get("completed") is True:
                        return entry
            except Exception as exc:
                logger.debug("Poll attempt failed for %s: %s", comfy_prompt_id, exc)

            await asyncio.sleep(config.COMFYUI_POLL_INTERVAL)

    return None  # timeout


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting ComfyUI wrapper on 0.0.0.0:%d", config.WRAPPER_PORT)
    uvicorn.run(app, host="0.0.0.0", port=config.WRAPPER_PORT, log_level="info")
