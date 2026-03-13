"""
Stable Diffusion Queue Bridge client.

Uses queue-based architecture instead of direct HTTP calls.
Pattern: Backend → Redis queue → Worker → Container SD → Result

This client provides a drop-in replacement for StableDiffusionService
but uses the new queue-based architecture for better VRAM management
and non-blocking operation.

Reference: IMPLEMENTATION_SUMMARY_SD_QUEUE_BRIDGE.md
"""

import httpx
import logging
from typing import Dict, Any, Optional
from app.config import SD_QUEUE_URL, SD_QUEUE_TIMEOUT, SD_DEFAULT_MODEL

logger = logging.getLogger(__name__)


class StableDiffusionQueueClient:
    """Client for queue-based SD generation via SD Queue Bridge."""

    def __init__(self):
        """Initialize the SD Queue client."""
        self.base_url = SD_QUEUE_URL
        self.timeout = SD_QUEUE_TIMEOUT
        self.default_model = SD_DEFAULT_MODEL

    async def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 512,
        height: int = 512,
        steps: int = 20,
        cfg_scale: float = 7.5,
        seed: int = -1,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate image via queue bridge (non-blocking).

        This method enqueues the job and waits for the result.
        The worker processes it with VRAM coordination.

        Args:
            prompt: Text description of the desired image
            negative_prompt: Things to avoid in the generation
            width: Image width in pixels (256-1024)
            height: Image height in pixels (256-1024)
            steps: Number of denoising steps (1-100)
            cfg_scale: Classifier-free guidance scale (1.0-20.0)
            seed: Random seed (-1 for random)
            model: HuggingFace model ID (optional, uses default if None)

        Returns:
            Dict with:
                - success: bool indicating success/failure
                - image_base64: Base64-encoded PNG (if success)
                - metadata: Generation parameters (if success)
                - error: Error message (if failed)
        """
        try:
            # Build payload for queue endpoint
            payload = {
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "width": width,
                "height": height,
                "num_inference_steps": steps,
                "guidance_scale": cfg_scale,
                "seed": seed,
                "model": model or self.default_model,
            }

            logger.info(
                "SD Queue: Generating image - prompt='%s...', size=%sx%s, steps=%s",
                prompt[:50], width, height, steps
            )

            # Call queue endpoint
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/images/generate",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

            # Parse response from queue bridge
            if result.get("status") == "success":
                logger.info("SD Queue: Generation successful - processing_time=%sms", result.get('processing_time_ms'))

                # Return in format compatible with legacy service
                return {
                    "success": True,
                    "image_base64": result.get("image_base64"),
                    "metadata": {
                        "prompt": prompt,
                        "negative_prompt": negative_prompt,
                        "width": width,
                        "height": height,
                        "steps": steps,
                        "cfg_scale": cfg_scale,
                        "seed": seed,
                        "model": result.get("model"),
                        "processing_time_ms": result.get("processing_time_ms"),
                    },
                }
            else:
                # Error from queue bridge
                error_msg = result.get("error", "Unknown error")
                logger.error("SD Queue: Generation failed - %s", error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                }

        except httpx.TimeoutException:
            logger.error("SD Queue: Timeout after %ss", self.timeout)
            return {
                "success": False,
                "error": f"Generation timeout after {self.timeout} seconds"
            }
        except httpx.HTTPError as e:
            logger.error("SD Queue: HTTP error - %s", e)
            return {
                "success": False,
                "error": f"Queue bridge error: {str(e)}"
            }
        except Exception as e:
            logger.error("SD Queue: Unexpected error - %s", e, exc_info=True)
            return {
                "success": False,
                "error": f"Generation failed: {str(e)}"
            }

    async def check_health(self) -> Dict[str, Any]:
        """
        Check if SD Queue Bridge is available.

        Returns:
            Dict with success flag and status information
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/images/health")
                response.raise_for_status()

                return {
                    "success": True,
                    "available": True,
                    "service": "sd-queue-bridge",
                }
        except Exception as e:
            logger.warning("SD Queue Bridge not available: %s", e)
            return {
                "success": False,
                "available": False,
                "error": str(e)
            }


# Singleton instance
_sd_queue_client: Optional[StableDiffusionQueueClient] = None


def get_stable_diffusion_queue_client() -> StableDiffusionQueueClient:
    """Get or create the SD Queue client singleton."""
    global _sd_queue_client
    if _sd_queue_client is None:
        _sd_queue_client = StableDiffusionQueueClient()
    return _sd_queue_client
