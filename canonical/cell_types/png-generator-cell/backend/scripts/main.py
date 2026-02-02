"""
Main execution logic for png-generator-cell.

This module provides PNG image generation functionality using Stable Diffusion.
"""

from typing import Dict, Any
import logging
import asyncio
import base64
from io import BytesIO

logger = logging.getLogger(__name__)

# Minimal 1x1 transparent PNG as ultra-fallback (67 bytes)
# Used when PIL is not available - smallest possible valid PNG
MINIMAL_FALLBACK_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="

# System prompt for Ollama when acting as Prompt Architect
# This instructs Mistral to optimize prompts for 3D asset reconstruction (SF3D)
OLLAMA_SYSTEM_PROMPT_3D_ARCHITECT = """You are the ScareVerse Prompt Architect. Your mission is to transform simple descriptions into technical prompts for Stable Diffusion.

Objective: Generate prompts optimized for 3D asset reconstruction (Stable Fast 3D / SF3D).

Rules:
- Use flat lighting (no dramatic shadows or highlights)
- Neutral gray background (studio setup)
- Orthographic front view (centered, full object visible)
- Full body or complete object isolation
- High resolution and clear geometry
- No artistic interpretation - technical precision only

CRITICAL PROHIBITION: 
- If the user requests an OBJECT (weapon, tool, furniture, prop, item), DO NOT include humans, hands, faces, or any biological elements
- Objects must be standalone - no interaction, no context with living beings
- Focus solely on the geometric and material properties of the object itself

Output format: Return ONLY the optimized prompt string. Do not explain, do not add commentary. Just the prompt."""

# Base negative prompt keywords for 3D asset generation
# These prevent biological contamination and ensure technical precision
NEGATIVE_PROMPT_3D_ASSET_BASE = "humans, people, hands, fingers, faces, portraits, person, man, woman, child, body parts, biological elements, dramatic lighting, shadows, high contrast, depth of field, bokeh, cluttered background, side view, back view, artistic interpretation"

# Static enhancement suffixes for 3D asset mode (used in fallback)
POSITIVE_SUFFIX_3D_ASSET = ", full body, standing, centered, front view, flat lighting, studio background, neutral gray background, high resolution, orthographic view"
NEGATIVE_SUFFIX_3D_ASSET = ", shadows, dramatic lighting, high contrast, depth of field, bokeh, cluttered background, side view, back view"


def _apply_static_3d_enhancement(prompt: str, negative_prompt: str = None) -> tuple:
    """
    Apply static 3D asset prompt enhancements (fallback when Ollama is unavailable).
    
    This is the legacy enhancement method, used as a fallback when Ollama
    orchestration is not available.
    
    Args:
        prompt: Original user prompt
        negative_prompt: User's negative prompt (optional)
        
    Returns:
        Tuple of (enhanced_prompt, enhanced_negative_prompt)
    """
    # Use module-level constants for consistency
    enhanced_prompt = f"{prompt}{POSITIVE_SUFFIX_3D_ASSET}"
    
    # Merge negative prompts, avoiding duplicate keywords
    enhanced_negative = negative_prompt or ""
    if enhanced_negative:
        # Split both prompts into keywords, deduplicate, and rejoin
        user_keywords = [k.strip() for k in enhanced_negative.split(',')]
        suffix_keywords = [k.strip() for k in NEGATIVE_SUFFIX_3D_ASSET.lstrip(', ').split(',')]
        all_keywords = user_keywords + [k for k in suffix_keywords if k not in user_keywords]
        enhanced_negative = ', '.join(all_keywords)
    else:
        enhanced_negative = NEGATIVE_SUFFIX_3D_ASSET.lstrip(", ")
    
    return enhanced_prompt, enhanced_negative


def _create_fallback_png() -> str:
    """
    Create a 1x1 red pixel PNG as fallback placeholder.
    
    Returns:
        Base64-encoded PNG with data URI prefix
    """
    try:
        from PIL import Image
        
        # Create 1x1 red pixel image
        img = Image.new('RGB', (1, 1), color='red')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Encode to base64 with proper prefix
        base64_data = base64.b64encode(buffer.read()).decode('utf-8')
        return f"data:image/png;base64,{base64_data}"
    except Exception as e:
        logger.error(f"Failed to create fallback PNG: {e}")
        # Ultra-minimal fallback - smallest possible PNG (1x1 transparent)
        return f"data:image/png;base64,{MINIMAL_FALLBACK_PNG}"


async def execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the PNG generator cell.
    
    This function generates a PNG image from a text prompt if one doesn't already exist.
    Falls back to a mock placeholder if the Stable Diffusion service is unavailable.
    
    Args:
        cell_data: Cell instance data containing 'prompt' and optional 'generatedPng'
        
    Returns:
        Dict with execution results including generated PNG
        
    Example:
        >>> await execute_cell({"prompt": "A red dragon", "generatedPng": None})
        {
            "success": True,
            "message": "PNG generated successfully",
            "prompt": "A red dragon",
            "has_png": True,
            "generatedPng": "data:image/png;base64,..."
        }
    """
    prompt = cell_data.get('prompt', '')
    generated_png = cell_data.get('generatedPng', None)
    
    logger.info(f"PNG generator cell executed with prompt: {prompt[:50]}...")
    
    # If PNG already exists, just return success
    if generated_png:
        return {
            "success": True,
            "message": "PNG generator cell ready",
            "prompt": prompt,
            "has_png": True,
            "generatedPng": generated_png
        }
    
    # If no prompt provided, return without generating
    if not prompt or not prompt.strip():
        logger.warning("No prompt provided for PNG generation")
        return {
            "success": True,
            "message": "No prompt provided",
            "prompt": prompt,
            "has_png": False
        }
    
    # Generate PNG from prompt
    logger.info(f"Generating PNG for prompt: {prompt}")
    
    # Extract generation parameters if provided
    gen_params = cell_data.get('generationParams', {})
    width = gen_params.get('width', 512)
    height = gen_params.get('height', 512)
    steps = gen_params.get('steps', 20)
    cfg_scale = gen_params.get('cfg_scale', 7.0)
    seed = gen_params.get('seed', -1)
    
    # Extract 3D Asset Mode and negative prompt from cell_data
    negative_prompt = cell_data.get('negativePrompt', '')
    asset_3d_mode = cell_data.get('asset3dMode', False)
    
    try:
        # Call async generation function directly
        # This works because execute_cell is now async and can be called
        # from FastAPI's async context without creating a new event loop
        result = await generate_png_from_prompt(
            prompt=prompt,
            width=width,
            height=height,
            steps=steps,
            cfg_scale=cfg_scale,
            seed=seed,
            negative_prompt=negative_prompt,
            asset_3d_mode=asset_3d_mode
        )
        
        if result.get("success"):
            # Ensure proper Base64 prefix
            image_data = result.get("image_base64", "")
            if not image_data.startswith("data:image/png;base64,"):
                image_data = f"data:image/png;base64,{image_data}"
            
            logger.info("PNG generation successful")
            return {
                "success": True,
                "message": "PNG generated successfully",
                "prompt": prompt,
                "has_png": True,
                "generatedPng": image_data,
                "metadata": result.get("metadata", {})
            }
        else:
            # Service failed, use fallback
            logger.warning(f"PNG generation failed, using fallback: {result.get('error')}")
            fallback_png = _create_fallback_png()
            
            return {
                "success": True,
                "message": "PNG generation failed, using fallback placeholder",
                "prompt": prompt,
                "has_png": True,
                "generatedPng": fallback_png,
                "error": result.get("error"),
                "fallback": True
            }
    except Exception as e:
        # Unexpected error, use fallback
        logger.error(f"Unexpected error during PNG generation: {e}", exc_info=True)
        fallback_png = _create_fallback_png()
        
        return {
            "success": True,
            "message": "PNG generation error, using fallback placeholder",
            "prompt": prompt,
            "has_png": True,
            "generatedPng": fallback_png,
            "error": str(e),
            "fallback": True
        }


async def generate_png_from_prompt(
    prompt: str,
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg_scale: float = 7.0,
    seed: int = -1,
    negative_prompt: str = None,
    asset_3d_mode: bool = False
) -> Dict[str, Any]:
    """
    Generate PNG image from a text prompt using Stable Diffusion.
    
    Falls back to a placeholder if the Stable Diffusion service is unavailable.
    
    When asset_3d_mode is enabled, orchestrates with Ollama to generate
    an optimized prompt before calling Stable Diffusion.
    
    Args:
        prompt: Text description of the desired image
        width: Image width in pixels
        height: Image height in pixels
        steps: Number of denoising steps
        cfg_scale: Classifier-free guidance scale
        seed: Random seed (-1 for random)
        negative_prompt: Things to avoid in generation
        asset_3d_mode: Enable 3D Asset optimization (uses Ollama orchestration)
        
    Returns:
        Dict with generated PNG or error information
        
    Example:
        >>> await generate_png_from_prompt("A blue crystal")
        {
            "success": True,
            "image_base64": "iVBORw0KGgoAAAANS...",
            "prompt": "A blue crystal",
            "metadata": {...}
        }
    """
    # Initialize prompt variables
    enhanced_prompt = prompt
    enhanced_negative = negative_prompt or ""
    
    # If 3D Asset Mode is enabled, use Ollama orchestration
    if asset_3d_mode:
        logger.info(f"3D Asset Mode enabled - orchestrating with Ollama for prompt optimization")
        
        try:
            # Import Ollama service for prompt orchestration
            # NOTE: Import is conditional because this is an optional enhancement.
            # If import fails, we gracefully fall back to static enhancement.
            from app.ollama_service import chamar_ollama, verificar_ollama_disponivel
            
            # Check if Ollama is available
            ollama_available = await verificar_ollama_disponivel()
            
            if ollama_available:
                # Build the full prompt for Ollama using module-level constant
                ollama_prompt = f"""{OLLAMA_SYSTEM_PROMPT_3D_ARCHITECT}

User Description: {prompt}

Generate the optimized Stable Diffusion prompt:"""

                # Call Ollama with timeout handling
                logger.debug(f"Calling Ollama for prompt optimization - Original: {prompt[:50]}...")
                ollama_result = await chamar_ollama(ollama_prompt)
                
                # Extract the optimized prompt from Ollama response
                optimized_prompt = ollama_result.get("response", "").strip()
                
                if optimized_prompt:
                    logger.info(f"Ollama optimization successful - Enhanced prompt length: {len(optimized_prompt)}")
                    enhanced_prompt = optimized_prompt
                    
                    # Enhance negative prompt using module-level constant
                    if enhanced_negative:
                        # Merge user negative prompt with base negative
                        user_keywords = [k.strip() for k in enhanced_negative.split(',')]
                        base_keywords = [k.strip() for k in NEGATIVE_PROMPT_3D_ASSET_BASE.split(',')]
                        all_keywords = user_keywords + [k for k in base_keywords if k not in user_keywords]
                        enhanced_negative = ', '.join(all_keywords)
                    else:
                        enhanced_negative = NEGATIVE_PROMPT_3D_ASSET_BASE
                    
                    logger.debug(f"Final enhanced negative prompt: {enhanced_negative[:100]}...")
                else:
                    logger.warning("Ollama returned empty response, falling back to static enhancement")
                    enhanced_prompt, enhanced_negative = _apply_static_3d_enhancement(prompt, negative_prompt)
                    
            else:
                logger.warning("Ollama not available, falling back to static 3D asset enhancement")
                enhanced_prompt, enhanced_negative = _apply_static_3d_enhancement(prompt, negative_prompt)
                
        except Exception as e:
            logger.error(f"Error during Ollama orchestration: {e}", exc_info=True)
            logger.warning("Falling back to static 3D asset enhancement")
            enhanced_prompt, enhanced_negative = _apply_static_3d_enhancement(prompt, negative_prompt)
    
    logger.info(f"Generating PNG - Asset 3D Mode: {asset_3d_mode}, Prompt length: {len(enhanced_prompt)}")
    # Try to import and use Stable Diffusion service
    try:
        from app.services.stable_diffusion_service import StableDiffusionService
        
        # Initialize Stable Diffusion service
        sd_service = StableDiffusionService()
        
        # Generate image with enhanced prompts
        result = await sd_service.generate_image(
            prompt=enhanced_prompt,
            negative_prompt=enhanced_negative,
            width=width,
            height=height,
            steps=steps,
            cfg_scale=cfg_scale,
            seed=seed
        )
        
        if result.get("success"):
            logger.info(f"Successfully generated PNG from prompt: {prompt[:50]}...")
            return {
                "success": True,
                "image_base64": result.get("image_base64"),
                "prompt": prompt,
                "metadata": result.get("metadata", {})
            }
        else:
            logger.warning(f"PNG generation failed: {result.get('error')}")
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "prompt": prompt
            }
    
    except ImportError as e:
        # Service not available in path
        logger.warning(f"StableDiffusionService not available: {e}")
        return {
            "success": False,
            "error": "Stable Diffusion service not available (import failed)",
            "prompt": prompt
        }
    
    except Exception as e:
        logger.error(f"Error generating PNG: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Error generating PNG: {str(e)}",
            "prompt": prompt
        }


async def remove_background_from_png(
    input_image_base64: str,
    alpha_matting: bool = True,
    timeout: float = 60.0
) -> Dict[str, Any]:
    """
    Remove background from PNG image using GPU Worker.
    
    Delegates background removal to the Windows Worker via Redis queue.
    The worker uses Rembg with GPU acceleration (CUDA) for fast processing.
    
    Args:
        input_image_base64: Base64-encoded input PNG (with or without data URI prefix)
        alpha_matting: Enable alpha matting for better edge quality (default: True)
        timeout: Maximum time to wait for processing (default: 60 seconds)
        
    Returns:
        Dict with processing results:
            - success: Boolean indicating success/failure
            - output_image_base64: Base64-encoded transparent PNG (if success)
            - error: Error message (if failure)
            - job_id: Unique job identifier
            - processing_time: Time taken by GPU worker
            
    Example:
        >>> await remove_background_from_png("iVBORw0KGgoAAAANS...")
        {
            "success": True,
            "output_image_base64": "iVBORw0KGgoAAAANS...",
            "job_id": "uuid-1234",
            "processing_time": 2.5
        }
    """
    try:
        # Import background removal utility
        from .background_removal import queue_background_removal_job
        
        logger.info("Queueing background removal job to GPU Worker")
        
        # Queue job to Redis and wait for result
        result = await queue_background_removal_job(
            input_image_base64=input_image_base64,
            alpha_matting=alpha_matting,
            timeout=timeout
        )
        
        if result.get("success"):
            logger.info(f"Background removal completed successfully (job: {result.get('job_id')})")
            return {
                "success": True,
                "output_image_base64": result.get("output_image_base64"),
                "job_id": result.get("job_id"),
                "processing_time": result.get("processing_time", 0),
                "metadata": {
                    "alpha_matting": alpha_matting,
                    "worker": "gpu"
                }
            }
        else:
            logger.warning(f"Background removal failed: {result.get('error')}")
            return {
                "success": False,
                "error": result.get("error", "Unknown error"),
                "job_id": result.get("job_id")
            }
            
    except ImportError as e:
        logger.error(f"Background removal service not available: {e}")
        return {
            "success": False,
            "error": "Background removal service not available (import failed)"
        }
    except Exception as e:
        logger.error(f"Error removing background: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Error removing background: {str(e)}"
        }


if __name__ == "__main__":
    # Allow standalone execution for testing
    import json
    import sys
    
    if len(sys.argv) > 1:
        cell_data = json.loads(sys.argv[1])
    else:
        cell_data = {
            "prompt": "A simple geometric shape",
            "generatedPng": None
        }
    
    result = asyncio.run(execute_cell(cell_data))
    print(json.dumps(result, indent=2))
