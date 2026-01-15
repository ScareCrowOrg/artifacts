"""
Main execution logic for asset-prototyping-cell.

This module orchestrates the asset prototyping pipeline:
1. Generate PNG from text prompt using Stable Diffusion
2. Vectorize PNG to SVG
3. Provide data for 3D prototyping with Three.js
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


async def generate_png(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate PNG image from text prompt.
    
    Args:
        cell_data: Cell instance data containing:
            - prompt: Text description
            - selectedModel: AI model to use (for prompt enhancement)
            
    Returns:
        Dict with execution results
    """
    try:
        from app.services.stable_diffusion_service import get_stable_diffusion_service
        
        prompt = cell_data.get('prompt', '')
        if not prompt:
            return {
                "success": False,
                "error": "No prompt provided"
            }
        
        sd_service = get_stable_diffusion_service()
        result = await sd_service.generate_image(
            prompt=prompt,
            width=512,
            height=512,
            steps=20,
            cfg_scale=7.0
        )
        
        return result
        
    except Exception as e:
        logger.error(f"PNG generation error: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Generation failed: {str(e)}"
        }


async def vectorize_png(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Vectorize PNG image to SVG format.
    
    Args:
        cell_data: Cell instance data containing:
            - selectedPng: Base64-encoded PNG image
            
    Returns:
        Dict with vectorization results
    """
    try:
        from app.services.svg_vectorization_service import get_vectorization_service
        
        png_data = cell_data.get('selectedPng')
        if not png_data:
            return {
                "success": False,
                "error": "No PNG image selected"
            }
        
        vectorization_service = get_vectorization_service()
        result = await vectorization_service.vectorize_image(
            image_base64=png_data,
            simplify=True,
            threshold=128
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Vectorization error: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Vectorization failed: {str(e)}"
        }


async def validate_3d_config(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate 3D mesh configuration.
    
    Args:
        cell_data: Cell instance data containing:
            - mesh3dConfig: ExtrudeGeometry parameters
            
    Returns:
        Dict with validation results
    """
    try:
        config = cell_data.get('mesh3dConfig', {})
        
        # Validate required parameters
        required = ['depth', 'bevelEnabled', 'bevelThickness', 'bevelSize', 'bevelSegments']
        missing = [field for field in required if field not in config]
        
        if missing:
            return {
                "success": False,
                "error": f"Missing configuration fields: {', '.join(missing)}"
            }
        
        # Validate value ranges
        if config['depth'] <= 0:
            return {
                "success": False,
                "error": "Depth must be greater than 0"
            }
        
        if config['bevelThickness'] < 0:
            return {
                "success": False,
                "error": "Bevel thickness cannot be negative"
            }
        
        return {
            "success": True,
            "config": config
        }
        
    except Exception as e:
        logger.error(f"3D config validation error: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Validation failed: {str(e)}"
        }


async def execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute cell based on current step.
    
    Args:
        cell_data: Cell instance data
        
    Returns:
        Dict with execution results
    """
    current_step = cell_data.get('currentStep', 1)
    
    if current_step == 1:
        # Step 1: Generate PNG
        return await generate_png(cell_data)
    elif current_step == 2:
        # Step 2: Vectorize to SVG
        return await vectorize_png(cell_data)
    elif current_step == 3:
        # Step 3: Validate 3D configuration
        return await validate_3d_config(cell_data)
    else:
        return {
            "success": False,
            "error": f"Invalid step: {current_step}"
        }
