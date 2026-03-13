"""
Stable Diffusion API integration service.

This service provides integration with Stable Diffusion (SD-Forge) API
for generating images from text prompts.
"""

import json
import logging
from typing import Any, Dict, Optional

import httpx

from app import config

logger = logging.getLogger(__name__)


class StableDiffusionService:
    """Service for interacting with Stable Diffusion API."""

    def __init__(self):
        """Initialize the Stable Diffusion service."""
        self.base_url = config.STABLE_DIFFUSION_URL
        self.timeout = config.STABLE_DIFFUSION_TIMEOUT

    async def generate_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = 512,
        height: int = 512,
        steps: int = 20,
        cfg_scale: float = 7.0,
        seed: int = -1,
    ) -> Dict[str, Any]:
        """
        Generate an image using Stable Diffusion API.

        Args:
            prompt: Text description of the desired image
            negative_prompt: Things to avoid in the generation
            width: Image width in pixels
            height: Image height in pixels
            steps: Number of denoising steps
            cfg_scale: Classifier-free guidance scale
            seed: Random seed (-1 for random)

        Returns:
            Dict containing:
                - success: bool
                - image_base64: Base64-encoded PNG image (if success)
                - error: Error message (if failed)
                - metadata: Generation parameters used
        """
        try:
            # Enhance prompt for clean silhouette with white background
            enhanced_prompt = (
                f"{prompt}, clean silhouette, white background, "
                f"simple shapes, high contrast, vector-style, "
                f"minimalist design, clear outlines"
            )

            default_negative = (
                "complex details, gradients, shadows, "
                "photo-realistic, texture, blur, noise"
            )

            final_negative = (
                f"{negative_prompt}, {default_negative}"
                if negative_prompt
                else default_negative
            )

            payload = {
                "prompt": enhanced_prompt,
                "negative_prompt": final_negative,
                "width": width,
                "height": height,
                "steps": steps,
                "cfg_scale": cfg_scale,
                "seed": seed,
                "sampler_name": "Euler a",
                "restore_faces": False,
                "tiling": False,
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/sdapi/v1/txt2img", json=payload
                )
                response.raise_for_status()

                result = response.json()

                # Validate response is a dictionary
                if not isinstance(result, dict):
                    logger.error("Invalid SD-API response type: %s. Expected dict, got: %s", type(result), result)
                    return {
                        "success": False,
                        "error": f"Invalid API response format: expected JSON object, got {type(result).__name__}",
                    }

                # Extract the first generated image
                if result.get("images") and len(result["images"]) > 0:
                    # Safely extract seed from info field
                    # The 'info' field can be a string (JSON) or dict, handle both cases
                    info_field = result.get("info", {})
                    extracted_seed = seed  # Default to input seed

                    if isinstance(info_field, dict):
                        extracted_seed = info_field.get("seed", seed)
                    elif isinstance(info_field, str):
                        # If info is a JSON string, try to parse it
                        try:
                            info_dict = json.loads(info_field)
                            extracted_seed = info_dict.get("seed", seed)
                        except (json.JSONDecodeError, AttributeError):
                            logger.warning("Could not parse 'info' field as JSON: %s", info_field)

                    return {
                        "success": True,
                        "image_base64": result["images"][0],
                        "metadata": {
                            "prompt": enhanced_prompt,
                            "negative_prompt": final_negative,
                            "width": width,
                            "height": height,
                            "steps": steps,
                            "cfg_scale": cfg_scale,
                            "seed": extracted_seed,
                        },
                    }
                else:
                    return {"success": False, "error": "No images generated"}

        except httpx.TimeoutException:
            logger.error("Stable Diffusion API timeout after %ss", self.timeout)
            return {
                "success": False,
                "error": f"Generation timeout after {self.timeout} seconds",
            }
        except httpx.HTTPError as e:
            logger.error("Stable Diffusion API HTTP error: %s", e)
            return {"success": False, "error": f"API error: {str(e)}"}
        except Exception as e:
            logger.error("Stable Diffusion generation error: %s", e, exc_info=True)
            return {"success": False, "error": f"Generation failed: {str(e)}"}

    async def check_health(self) -> Dict[str, Any]:
        """
        Check if Stable Diffusion API is available.

        Returns:
            Dict with success flag and status information
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/sdapi/v1/sd-models")
                response.raise_for_status()

                models = response.json()
                return {
                    "success": True,
                    "available": True,
                    "models_count": len(models) if models else 0,
                }
        except Exception as e:
            logger.warning("Stable Diffusion API not available: %s", e)
            return {"success": False, "available": False, "error": str(e)}


# Singleton instance
_sd_service: Optional[StableDiffusionService] = None


def get_stable_diffusion_service() -> StableDiffusionService:
    """Get or create the Stable Diffusion service singleton."""
    global _sd_service
    if _sd_service is None:
        _sd_service = StableDiffusionService()
    return _sd_service
