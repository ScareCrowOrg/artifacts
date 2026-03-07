#!/usr/bin/env python3
"""
Stable Diffusion FastAPI Wrapper
Container API for GPU-accelerated image generation with diffusers.

Endpoints:
- POST /generate: Generate image from prompt
- GET /health: Health check endpoint

Architecture:
- Lazy model loading (first request, stays in memory)
- Base64 PNG responses
- Configurable generation parameters
- GPU-accelerated with torch.float16
"""

import os
import sys
import base64
import logging
import time
from io import BytesIO
from typing import Optional

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from diffusers import AutoPipelineForText2Image
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Stable Diffusion API",
    description="GPU-accelerated image generation with Stable Diffusion",
    version="1.0.0"
)

# Global pipeline (lazy-loaded)
# Supports both SD 1.5 and SDXL via AutoPipeline detection
pipeline: Optional[object] = None
current_model: Optional[str] = None


class StableDiffusionRequest(BaseModel):
    """Request model for /generate endpoint."""
    
    model: str = Field(
        default="stabilityai/stable-diffusion-xl-base-1.0",
        description="HuggingFace model ID (SDXL for flat-lighting asset rendering)"
    )
    prompt: str = Field(
        ...,
        description="Text description of the desired image",
        min_length=1
    )
    negative_prompt: str = Field(
        default="",
        description="Things to avoid in the generation"
    )
    height: int = Field(default=512, ge=256, le=1024, description="Image height in pixels")
    width: int = Field(default=512, ge=256, le=1024, description="Image width in pixels")
    num_inference_steps: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of denoising steps"
    )
    guidance_scale: float = Field(
        default=7.5,
        ge=1.0,
        le=20.0,
        description="Classifier-free guidance scale"
    )
    seed: int = Field(default=-1, description="Random seed (-1 for random)")


class StableDiffusionResponse(BaseModel):
    """Response model for /generate endpoint."""
    
    status: str
    image_base64: Optional[str] = None
    model: Optional[str] = None
    error: Optional[str] = None


def load_model(model_name: str):
    """
    Load Stable Diffusion model lazily (supports both SD 1.5 and SDXL).

    If model is already loaded, reuses it. Otherwise, loads from HuggingFace.
    Uses AutoPipelineForText2Image which auto-detects the correct pipeline class.

    Args:
        model_name: HuggingFace model ID (e.g., "stabilityai/stable-diffusion-xl-base-1.0")

    Returns:
        Pipeline instance (type auto-detected)

    Raises:
        RuntimeError: If model loading fails
    """
    global pipeline, current_model

    # Reuse if same model
    if pipeline is not None and current_model == model_name:
        logger.info(f"Model '{model_name}' already loaded (reuse)")
        return pipeline

    # Load new model
    logger.info(f"Loading model: {model_name}")
    start_time = time.time()

    try:
        # Check GPU availability
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA not available")

        # Load pipeline with AutoPipeline (auto-detects SD 1.5 vs SDXL)
        # FP16 for memory efficiency, safety checker disabled for performance
        # Cache dir explicitly set to persist models across container restarts
        cache_dir = os.getenv("HF_HUB_CACHE", "/root/.cache/huggingface")
        pipe = AutoPipelineForText2Image.from_pretrained(
            model_name,
            torch_dtype=torch.float16,
            variant="fp16",  # SDXL requires explicit fp16 variant for safety
            use_safetensors=True,
            cache_dir=cache_dir
        )
        pipe = pipe.to("cuda")

        # Update global state
        pipeline = pipe
        current_model = model_name

        elapsed = time.time() - start_time
        logger.info(f"✅ Model '{model_name}' loaded in {elapsed:.2f}s")

        return pipeline

    except Exception as e:
        logger.error(f"Failed to load model '{model_name}': {e}")
        raise RuntimeError(f"Model loading failed: {e}")


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns 200 with {"status": "healthy"} if API is responsive.
    Does not validate GPU availability (handled by Docker healthcheck).
    """
    return {"status": "healthy"}


@app.post("/generate", response_model=StableDiffusionResponse)
async def generate_image(request: StableDiffusionRequest):
    """
    Generate image from text prompt.
    
    Request:
        - model: HuggingFace model ID
        - prompt: Text description
        - negative_prompt: Things to avoid
        - height: Image height (256-1024)
        - width: Image width (256-1024)
        - num_inference_steps: Denoising steps (1-100)
        - guidance_scale: CFG scale (1.0-20.0)
        - seed: Random seed (-1 for random)
    
    Response:
        - status: "success" or "error"
        - image_base64: Base64-encoded PNG (if success)
        - model: Model used (if success)
        - error: Error message (if failed)
    """
    logger.info(
        f"Generate request: model={request.model}, prompt='{request.prompt[:50]}...', "
        f"size={request.width}x{request.height}, steps={request.num_inference_steps}"
    )
    
    start_time = time.time()
    
    try:
        # Load model (lazy)
        pipe = load_model(request.model)
        
        # Set random seed if provided
        generator = None
        if request.seed >= 0:
            generator = torch.Generator(device="cuda").manual_seed(request.seed)
            logger.debug(f"Using seed: {request.seed}")
        
        # Generate image
        logger.info("Generating image...")
        with torch.no_grad():
            result = pipe(
                prompt=request.prompt,
                negative_prompt=request.negative_prompt if request.negative_prompt else None,
                height=request.height,
                width=request.width,
                num_inference_steps=request.num_inference_steps,
                guidance_scale=request.guidance_scale,
                generator=generator
            )
        
        image = result.images[0]
        
        # Convert to base64 PNG
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"✅ Generation complete in {elapsed_ms:.0f}ms")
        
        return StableDiffusionResponse(
            status="success",
            image_base64=image_base64,
            model=request.model
        )
    
    except torch.cuda.OutOfMemoryError as e:
        # OOM error - log and return error
        error_msg = "GPU out of memory"
        logger.error(f"❌ {error_msg}: {e}")
        
        # Clear CUDA cache
        torch.cuda.empty_cache()
        
        raise HTTPException(status_code=507, detail=error_msg)
    
    except Exception as e:
        # General error
        error_msg = str(e)
        logger.error(f"❌ Generation failed: {error_msg}", exc_info=True)
        
        raise HTTPException(status_code=500, detail=error_msg)


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Stable Diffusion FastAPI Service Starting")
    logger.info("=" * 60)
    
    # Verify GPU
    if not torch.cuda.is_available():
        logger.error("❌ CUDA not available")
        sys.exit(1)
    
    device_name = torch.cuda.get_device_name(0)
    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
    logger.info(f"GPU: {device_name} ({vram_gb:.1f}GB VRAM)")
    
    # Start server
    logger.info("Starting Uvicorn server on 0.0.0.0:9090")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9090,
        log_level="info"
    )
