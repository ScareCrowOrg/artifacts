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
    
    Args:
        prompt: Text description of the desired image
        width: Image width in pixels
        height: Image height in pixels
        steps: Number of denoising steps
        cfg_scale: Classifier-free guidance scale
        seed: Random seed (-1 for random)
        negative_prompt: Things to avoid in generation
        asset_3d_mode: Enable 3D Asset optimization (adds technical suffixes)
        
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
    # Apply 3D Asset Mode suffixes if enabled
    enhanced_prompt = prompt
    enhanced_negative = negative_prompt or ""
    
    if asset_3d_mode:
        # Positive prompt suffix for 3D asset generation
        positive_suffix = ", full body, standing, centered, front view, flat lighting, studio background, neutral gray background, high resolution, orthographic view"
        enhanced_prompt = f"{prompt}{positive_suffix}"
        
        # Negative prompt suffix for 3D asset generation
        negative_suffix = ", shadows, dramatic lighting, high contrast, depth of field, bokeh, cluttered background, side view, back view"
        
        # Merge negative prompts, avoiding duplicate keywords
        if enhanced_negative:
            # Split both prompts into keywords, deduplicate, and rejoin
            user_keywords = [k.strip() for k in enhanced_negative.split(',')]
            suffix_keywords = [k.strip() for k in negative_suffix.lstrip(', ').split(',')]
            all_keywords = user_keywords + [k for k in suffix_keywords if k not in user_keywords]
            enhanced_negative = ', '.join(all_keywords)
        else:
            enhanced_negative = negative_suffix.lstrip(", ")
    
    logger.info(f"Generating PNG with 3D Asset Mode: {asset_3d_mode}")
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
