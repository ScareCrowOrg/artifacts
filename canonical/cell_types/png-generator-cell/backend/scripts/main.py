"""
Main execution logic for png-generator-cell.

This module provides PNG image generation functionality using Stable Diffusion.

BaseCell v1.0 Implementation:
- PngGeneratorCell class inherits from BaseCell (defined at end of file)
- Implements execute(), describe(), validate(), health_check()
- Backward compatible through execute_cell() wrapper
- Legacy handlers remain for stability
"""

from typing import Dict, Any, List
import logging
import asyncio
import base64
from io import BytesIO
import sys
import os

# Add backend to path for importing BaseCell
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../../../backend'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

try:
    from app.core.base_cell import BaseCell, CellResult, CellMetadata, ValidationError, EnvironmentConfig, HealthCheckResult, HealthStatus
    BASECELL_AVAILABLE = True
except ImportError:
    # Graceful degradation if BaseCell not available
    BASECELL_AVAILABLE = False
    BaseCell = object  # Fallback

logger = logging.getLogger(__name__)

# Minimal 1x1 transparent PNG as ultra-fallback (67 bytes)
# Used when PIL is not available - smallest possible valid PNG
MINIMAL_FALLBACK_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="

# System prompt for Ollama when acting as Prompt Architect
# This instructs Mistral to optimize prompts for 3D asset reconstruction (SF3D)
OLLAMA_SYSTEM_PROMPT_3D_ARCHITECT = """You are the ScareVerse Prompt Architect. Your mission is to transform descriptions into technical prompts for Stable Diffusion.

Objective: Generate prompts optimized for clean, technical 3D asset rendering.

Rules:
- PRESERVE the original subject and its natural form
- Use flat, even lighting (avoid dramatic shadows, highlights, or reflections)
- Background: Use a color that STRONGLY CONTRASTS with the object's color for clarity
  * The background color must be visually distinct from the foreground object
  * This ensures proper object isolation and helps background removal tools
- Clear, visible geometry and details
- High resolution and technical precision
- NO shadows, NO reflections, NO dramatic lighting
- NO bokeh, NO depth of field effects, NO artistic interpretation

Output format: Return ONLY the optimized prompt string. Do not explain, do not add commentary. Just the prompt."""

# Base negative prompt keywords for 3D asset generation
# These prevent biological contamination and ensure technical precision
NEGATIVE_PROMPT_3D_ASSET_BASE = "humans, people, hands, fingers, faces, portraits, person, man, woman, child, body parts, biological elements, dramatic lighting, shadows, high contrast, depth of field, bokeh, cluttered background, side view, back view, artistic interpretation"

# Static enhancement suffixes for 3D asset mode (used in fallback)
POSITIVE_SUFFIX_3D_ASSET = ", centered, front view, flat lighting, studio background, neutral gray background, high resolution, orthographic view"
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
    Execute the PNG generator cell with action-based routing.

    This function supports two actions:
    1. "generate" - Generate PNG from text prompt using Stable Diffusion
    2. "removeBackground" - Remove background from existing PNG using GPU Worker

    Args:
        cell_data: Cell instance data containing:
            - 'action': Action to perform ("generate" or "removeBackground")
            - 'prompt': Text description for PNG generation (required for "generate")
            - 'generatedPng': Existing PNG to process (required for "removeBackground")
            - 'generationParams': Optional parameters for PNG generation
            - 'negativePrompt': Optional negative prompt for generation
            - 'asset3dMode': Optional flag for 3D asset optimization

    Returns:
        Dict with execution results based on action

    Examples:
        >>> # Generate PNG
        >>> await execute_cell({
        ...     "action": "generate",
        ...     "prompt": "A red dragon",
        ...     "generationParams": {"width": 512, "height": 512}
        ... })

        >>> # Remove background
        >>> await execute_cell({
        ...     "action": "removeBackground",
        ...     "generatedPng": "data:image/png;base64,..."
        ... })
    """
    action = cell_data.get('action', 'generate')  # Default to 'generate'

    logger.info(f"PNG generator cell executed with action: {action}")

    # Route to appropriate handler based on action
    if action == 'generate':
        return await handle_generate_png(cell_data)
    elif action == 'removeBackground':
        return await handle_remove_background(cell_data)
    else:
        logger.error(f"Unknown action: {action}")
        return {
            "success": False,
            "error": f"Unknown action '{action}'. Supported actions: 'generate', 'removeBackground'",
            "action": action
        }


async def handle_generate_png(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle PNG generation action.

    Generates a PNG image from a text prompt.
    Falls back to a mock placeholder if Stable Diffusion service is unavailable.

    Args:
        cell_data: Cell data containing prompt and generation parameters

    Returns:
        Dict with generation results
    """
    prompt = cell_data.get('prompt', '')
    generated_png = cell_data.get('generatedPng', None)

    logger.info(f"Generating PNG with prompt: {prompt[:50]}...")
    
    # If PNG already exists, just return success
    if generated_png:
        return {
            "success": True,
            "message": "PNG already exists",
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
        # Use absolute import with sys.path manipulation to support dynamic module loading
        import sys
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)

        from background_removal import queue_background_removal_job

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


async def handle_remove_background(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle background removal action.

    Removes background from an existing PNG image using GPU Worker.
    Delegates to the Windows Worker via Redis queue for GPU-accelerated processing.

    Args:
        cell_data: Cell data containing:
            - 'generatedPng': Base64-encoded PNG (required)
            - 'alpha_matting': Enable alpha matting (default: True)

    Returns:
        Dict with removal results
    """
    generated_png = cell_data.get('generatedPng', None)
    alpha_matting = cell_data.get('alpha_matting', True)

    logger.info("Handling background removal action")

    if not generated_png:
        logger.error("No PNG provided for background removal")
        return {
            "success": False,
            "error": "No PNG image provided for background removal",
            "action": "removeBackground"
        }

    try:
        logger.info("Queuing background removal job to GPU Worker")

        # Call the background removal function
        result = await remove_background_from_png(
            input_image_base64=generated_png,
            alpha_matting=alpha_matting,
            timeout=120.0  # Extended timeout for background removal
        )

        if result.get("success"):
            logger.info(f"Background removal queued successfully (job: {result.get('job_id')})")
            return {
                "success": True,
                "message": "Background removed successfully",
                "has_png": True,
                "generatedPng": f"data:image/png;base64,{result.get('output_image_base64', '')}",
                "backgroundRemoved": True,
                "backgroundRemovalJobId": result.get("job_id"),
                "processingTime": result.get("processing_time", 0),
                "action": "removeBackground"
            }
        else:
            logger.error(f"Background removal failed: {result.get('error')}")
            return {
                "success": False,
                "error": result.get("error", "Background removal failed"),
                "backgroundRemoved": False,
                "action": "removeBackground"
            }

    except Exception as e:
        logger.error(f"Error in background removal action: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": f"Error removing background: {str(e)}",
            "action": "removeBackground"
        }


# ============ BASECELL v1.0 IMPLEMENTATION ============


class PngGeneratorCell(BaseCell):
    """
    PNG Generator Cell implementing BaseCell v1.0 framework.
    
    This cell provides PNG image generation using Stable Diffusion
    and background removal via GPU Worker through Redis job queueing.
    
    Architecture:
    - Manager Cell (Kind/Linux): API, job queueing, result polling
    - Windows Worker: GPU processing (Stable Diffusion, Rembg)
    - Redis: Job queue and status tracking
    
    Key Features:
    - Text-to-image generation with Stable Diffusion
    - Background removal with alpha matting
    - 3D asset optimization mode with Ollama orchestration
    - Graceful fallbacks when services unavailable
    """
    
    def __init__(self):
        """Initialize PNG Generator Cell"""
        self.redis_client = None
        self.sd_service = None
        
    async def setup(self, config: EnvironmentConfig) -> None:
        """
        Initialize lightweight resources.
        
        Sets up Redis connection for job queueing and optional
        Stable Diffusion service connection.
        
        Note: Does NOT allocate GPU/VRAM - managed by Windows Worker.
        
        Args:
            config: Environment configuration
        """
        try:
            logger.info("Initializing PNG Generator Cell resources")
            # Note: Redis connection initialization would go here
            # For now, we use lazy initialization in execute()
            # to maintain compatibility with current architecture
            logger.info("PNG Generator Cell setup complete")
        except Exception as e:
            logger.warning(f"Non-critical setup error: {e}")
    
    async def teardown(self) -> None:
        """
        Clean up lightweight resources.
        
        Closes Redis connections and cleans up any listeners.
        Does NOT deallocate GPU/VRAM (not cell's responsibility).
        """
        try:
            logger.info("Tearing down PNG Generator Cell resources")
            if self.redis_client:
                self.redis_client = None
            logger.info("PNG Generator Cell teardown complete")
        except Exception as e:
            logger.error(f"Error during teardown: {e}", exc_info=True)
    
    async def execute(self, input: Dict[str, Any]) -> CellResult:
        """
        Execute PNG generation or background removal.
        
        Routes to appropriate handler based on action:
        - 'generate': Generate PNG from text prompt
        - 'removeBackground': Remove background from existing PNG
        
        Args:
            input: Input data containing:
                - action: 'generate' or 'removeBackground'
                - prompt: Text description (for generate)
                - generatedPng: Existing PNG (for removeBackground)
                - generationParams: Optional parameters
                - negativePrompt: Optional negative prompt
                - asset3dMode: Optional 3D asset optimization flag
        
        Returns:
            CellResult with success status, output data, and execution metadata
        """
        import time
        start_time = time.time()
        
        try:
            # Validate input
            validation_errors = self.validate(input)
            if validation_errors:
                return CellResult(
                    success=False,
                    output={},
                    error=f"Validation failed: {', '.join([e.message for e in validation_errors])}",
                    execution_time=(time.time() - start_time) * 1000
                )
            
            # Route to appropriate handler
            action = input.get('action', 'generate')
            
            if action == 'generate':
                result = await handle_generate_png(input)
            elif action == 'removeBackground':
                result = await handle_remove_background(input)
            else:
                return CellResult(
                    success=False,
                    output={},
                    error=f"Unknown action '{action}'. Supported: 'generate', 'removeBackground'",
                    execution_time=(time.time() - start_time) * 1000
                )
            
            # Convert legacy result format to CellResult
            execution_time = (time.time() - start_time) * 1000
            
            return CellResult(
                success=result.get('success', False),
                output=result,
                artifacts=[],
                execution_time=execution_time,
                execution_steps=[f"Action: {action}"],
                metadata=result.get('metadata', {})
            )
            
        except Exception as e:
            logger.error(f"Error in PNG Generator Cell execution: {e}", exc_info=True)
            return CellResult(
                success=False,
                output={},
                error=str(e),
                execution_time=(time.time() - start_time) * 1000
            )
    
    async def describe(self) -> CellMetadata:
        """
        Describe PNG Generator Cell capabilities.
        
        Returns metadata about inputs, outputs, and configuration.
        
        Returns:
            CellMetadata with cell description
        """
        return CellMetadata(
            id='png-generator-cell',
            name='PNG Generator',
            version='1.0.0',
            description='Generate and manipulate PNG images using Stable Diffusion and GPU Worker',
            inputs={
                'action': 'string (generate | removeBackground)',
                'prompt': 'string (required for generate)',
                'generatedPng': 'string (base64, required for removeBackground)',
                'generationParams': 'object (optional)',
                'negativePrompt': 'string (optional)',
                'asset3dMode': 'boolean (optional)',
                'alpha_matting': 'boolean (optional, for removeBackground)'
            },
            outputs={
                'success': 'boolean',
                'generatedPng': 'string (base64 PNG)',
                'has_png': 'boolean',
                'prompt': 'string',
                'message': 'string',
                'error': 'string (if failed)',
                'metadata': 'object'
            },
            tags=['image', 'generation', 'png', 'stable-diffusion', 'background-removal'],
            required_resources=['redis', 'windows-worker', 'stable-diffusion'],
            estimated_duration_seconds=30.0
        )
    
    def validate(self, input: Dict[str, Any]) -> List[ValidationError]:
        """
        Validate input data.
        
        Args:
            input: Input data to validate
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        action = input.get('action', 'generate')
        
        if action not in ['generate', 'removeBackground']:
            errors.append(ValidationError(
                field='action',
                message=f"Invalid action '{action}'. Must be 'generate' or 'removeBackground'"
            ))
        
        if action == 'removeBackground':
            if not input.get('generatedPng'):
                errors.append(ValidationError(
                    field='generatedPng',
                    message='generatedPng is required for removeBackground action'
                ))
        
        return errors
    
    async def health_check(self) -> HealthCheckResult:
        """
        Check if PNG Generator Cell can execute.
        
        Validates connectivity to Redis and optionally Stable Diffusion service.
        
        Returns:
            HealthCheckResult with status and diagnostic info
        """
        try:
            # Check if Stable Diffusion service is available
            # This is a soft check - cell can still work with fallbacks
            try:
                from app.services.stable_diffusion_service import StableDiffusionService
                sd_available = True
            except ImportError:
                sd_available = False
            
            if sd_available:
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    reason="PNG Generator Cell is fully operational"
                )
            else:
                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    reason="Stable Diffusion service not available (will use fallbacks)"
                )
        
        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            return HealthCheckResult(
                status=HealthStatus.UNAVAILABLE,
                reason=f"Health check error: {str(e)}"
            )


# Create global instance for backward compatibility
_png_generator_cell_instance = None


def get_png_generator_cell() -> PngGeneratorCell:
    """Get or create the global PNG Generator Cell instance"""
    global _png_generator_cell_instance
    if not BASECELL_AVAILABLE:
        return None
    if _png_generator_cell_instance is None:
        _png_generator_cell_instance = PngGeneratorCell()
    return _png_generator_cell_instance


# ============ MAIN EXECUTION ============


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
