"""
Main execution logic for png-generator-cell.

This module provides PNG image generation functionality using Stable Diffusion.
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the PNG generator cell.
    
    This function is called when the cell is executed from the backend.
    The actual PNG generation is handled via the frontend calling
    the Stable Diffusion service through a dedicated API endpoint.
    
    Args:
        cell_data: Cell instance data containing 'prompt' and optional 'generatedPng'
        
    Returns:
        Dict with execution results
        
    Example:
        >>> execute_cell({"prompt": "A red dragon", "generatedPng": "data:image/png;base64,..."})
        {
            "success": True,
            "message": "PNG generator cell ready",
            "prompt": "A red dragon"
        }
    """
    prompt = cell_data.get('prompt', '')
    generated_png = cell_data.get('generatedPng', None)
    
    logger.info(f"PNG generator cell executed with prompt: {prompt[:50]}...")
    
    return {
        "success": True,
        "message": "PNG generator cell ready",
        "prompt": prompt,
        "has_png": generated_png is not None
    }


async def generate_png_from_prompt(
    prompt: str,
    width: int = 512,
    height: int = 512,
    steps: int = 20,
    cfg_scale: float = 7.0,
    seed: int = -1,
    negative_prompt: str = None
) -> Dict[str, Any]:
    """
    Generate PNG image from a text prompt using Stable Diffusion.
    
    This function can be called by API endpoints to generate images.
    
    Args:
        prompt: Text description of the desired image
        width: Image width in pixels
        height: Image height in pixels
        steps: Number of denoising steps
        cfg_scale: Classifier-free guidance scale
        seed: Random seed (-1 for random)
        negative_prompt: Things to avoid in generation
        
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
    try:
        # Import here to avoid circular dependencies
        from app.services.stable_diffusion_service import StableDiffusionService
        
        # Initialize Stable Diffusion service
        sd_service = StableDiffusionService()
        
        # Generate image
        result = await sd_service.generate_image(
            prompt=prompt,
            negative_prompt=negative_prompt,
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
    
    result = execute_cell(cell_data)
    print(json.dumps(result, indent=2))
