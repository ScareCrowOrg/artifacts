"""
Stable Fast 3D API Client

This module provides a client for interacting with the Stability AI Stable Fast 3D API.
It handles authentication, image formatting, API requests, and response parsing.

API Documentation: https://platform.stability.ai/docs/api-reference
API Endpoint: https://api.stability.ai/v1/generation/stable-fast-3d

Authentication:
    Requires an API key from Stability AI, passed via the Authorization header
    as a Bearer token.

Image Format:
    Accepts image data as base64-encoded data URL or binary image data.

Response:
    Returns a GLB (binary glTF) file containing the generated 3D mesh.
"""

import base64
import logging
import io
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)


class StableFast3DClient:
    """
    Client for Stable Fast 3D API.
    
    Handles image-to-3D mesh generation using Stability AI's Stable Fast 3D service.
    """
    
    def __init__(
        self,
        api_key: str,
        api_url: str = "https://api.stability.ai/v1/generation/stable-fast-3d",
        timeout: int = 60
    ):
        """
        Initialize Stable Fast 3D client.
        
        Args:
            api_key: Stability AI API key for authentication
            api_url: API endpoint URL (default: production endpoint)
            timeout: Request timeout in seconds (default: 60)
        
        Raises:
            ValueError: If api_key is None or empty
        """
        if not api_key:
            raise ValueError("API key is required for Stable Fast 3D client")
        
        self.api_key = api_key
        self.api_url = api_url
        self.timeout = timeout
        
        logger.info(f"Initialized Stable Fast 3D client with endpoint: {api_url}")
    
    def generate_mesh(
        self,
        image_data: str,
        texture_resolution: int = 1024,
        foreground_ratio: float = 0.85
    ) -> Dict[str, Any]:
        """
        Generate 3D mesh from a single image.
        
        Args:
            image_data: Base64-encoded image data URL (e.g., "data:image/png;base64,...")
            texture_resolution: Texture resolution for the generated mesh (default: 1024)
            foreground_ratio: Ratio of foreground to background (default: 0.85)
        
        Returns:
            Dict containing:
                - success: Boolean indicating if generation succeeded
                - mesh_data: Base64-encoded GLB data URL if successful
                - metadata: Mesh generation metadata
                - error: Error message if failed
        
        Raises:
            ValueError: If image_data is invalid format
        """
        try:
            logger.info("Starting 3D mesh generation via Stable Fast 3D API")
            
            # Convert base64 data URL to binary image data
            image_bytes = self._decode_image_data(image_data)
            
            # Prepare multipart form data
            files = {
                "image": ("image.png", io.BytesIO(image_bytes), "image/png"),
            }
            
            data = {
                "texture_resolution": str(texture_resolution),
                "foreground_ratio": str(foreground_ratio),
            }
            
            # Prepare headers with authentication
            headers = {
                "Authorization": f"Bearer {self.api_key}",
            }
            
            # Make API request
            logger.debug(f"Sending request to {self.api_url}")
            logger.debug(f"Parameters: texture_resolution={texture_resolution}, foreground_ratio={foreground_ratio}")
            
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.api_url,
                    headers=headers,
                    files=files,
                    data=data
                )
            
            # Handle response
            if response.status_code == 200:
                return self._handle_success_response(response)
            else:
                return self._handle_error_response(response)
        
        except ValueError as e:
            logger.error(f"Invalid input: {e}")
            return {
                "success": False,
                "error": f"Invalid input: {str(e)}",
                "mesh_data": None,
                "metadata": None
            }
        
        except httpx.TimeoutException as e:
            logger.error(f"API request timeout: {e}")
            return {
                "success": False,
                "error": f"API request timeout after {self.timeout} seconds. The service may be overloaded.",
                "mesh_data": None,
                "metadata": None
            }
        
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during API request: {e}")
            return {
                "success": False,
                "error": f"Network error: {str(e)}",
                "mesh_data": None,
                "metadata": None
            }
        
        except Exception as e:
            logger.error(f"Unexpected error during mesh generation: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "mesh_data": None,
                "metadata": None
            }
    
    def _decode_image_data(self, image_data: str) -> bytes:
        """
        Decode base64 image data URL to binary bytes.
        
        Args:
            image_data: Base64-encoded image data URL
        
        Returns:
            Binary image data as bytes
        
        Raises:
            ValueError: If image_data format is invalid
        """
        if not image_data:
            raise ValueError("Image data is empty")
        
        # Handle data URL format: "data:image/png;base64,..."
        if image_data.startswith("data:"):
            try:
                # Split on comma to get base64 part
                parts = image_data.split(",", 1)
                if len(parts) != 2:
                    raise ValueError("Invalid data URL format: missing comma separator")
                
                base64_data = parts[1]
            except Exception as e:
                raise ValueError(f"Failed to parse data URL: {e}")
        else:
            # Assume raw base64 string
            base64_data = image_data
        
        # Decode base64
        try:
            image_bytes = base64.b64decode(base64_data)
            logger.debug(f"Decoded image: {len(image_bytes)} bytes")
            return image_bytes
        except Exception as e:
            raise ValueError(f"Failed to decode base64 image data: {e}")
    
    def _handle_success_response(self, response: httpx.Response) -> Dict[str, Any]:
        """
        Handle successful API response.
        
        Args:
            response: HTTP response object
        
        Returns:
            Dict with success status, GLB data, and metadata
        """
        logger.info("Successfully received 3D mesh from API")
        
        # Get GLB binary data
        glb_bytes = response.content
        glb_size_bytes = len(glb_bytes)
        
        logger.info(f"Received GLB file: {glb_size_bytes} bytes")
        
        # Encode GLB to base64 data URL
        glb_base64 = base64.b64encode(glb_bytes).decode('utf-8')
        glb_data_url = f"data:model/gltf-binary;base64,{glb_base64}"
        
        # Create metadata
        metadata = {
            "fileSizeBytes": glb_size_bytes,
            "modelType": "stable_fast_3d",
            "generationSource": "stability_ai_api",
            "note": "Generated via Stable Fast 3D API (cloud)"
        }
        
        return {
            "success": True,
            "mesh_data": glb_data_url,
            "metadata": metadata,
            "error": None
        }
    
    def _handle_error_response(self, response: httpx.Response) -> Dict[str, Any]:
        """
        Handle error API response.
        
        Args:
            response: HTTP response object
        
        Returns:
            Dict with error details
        """
        status_code = response.status_code
        
        # Try to parse error message from response
        try:
            error_data = response.json()
            error_message = error_data.get("message", error_data.get("error", "Unknown error"))
        except Exception:
            error_message = response.text or "No error message provided"
        
        logger.error(f"API error ({status_code}): {error_message}")
        
        # Provide user-friendly error messages based on status code
        if status_code == 401:
            user_message = "Authentication failed. Please check your API key."
        elif status_code == 403:
            user_message = "Access forbidden. Your API key may not have permission for this service."
        elif status_code == 429:
            user_message = "Rate limit exceeded. Please try again later."
        elif status_code == 400:
            user_message = f"Bad request: {error_message}"
        elif status_code >= 500:
            user_message = "Stability AI service error. Please try again later."
        else:
            user_message = f"API error ({status_code}): {error_message}"
        
        return {
            "success": False,
            "error": user_message,
            "mesh_data": None,
            "metadata": {
                "error_code": status_code,
                "error_detail": error_message
            }
        }


def create_client(
    api_key: Optional[str] = None,
    api_url: Optional[str] = None,
    timeout: Optional[int] = None
) -> Optional[StableFast3DClient]:
    """
    Factory function to create Stable Fast 3D client with configuration.

    This function attempts to load configuration from the backend config module first,
    then falls back to environment variables. For most use cases within the cell
    execution context, rely on the cell's main.py to pass the config.

    Args:
        api_key: API key (optional, loads from config/environment if not provided)
        api_url: API endpoint URL (optional, uses default if not provided)
        timeout: Request timeout (optional, uses default if not provided)

    Returns:
        StableFast3DClient instance if API key is available, None otherwise
    """
    import os

    # Try to get API key from provided argument first, then from app config, then from environment
    if not api_key:
        try:
            from app.config import STABLE_FAST_3D_API_KEY as config_api_key
            api_key = config_api_key
        except ImportError:
            api_key = os.getenv("STABLE_FAST_3D_API_KEY")

    # Get other config values
    if not api_url:
        try:
            from app.config import STABLE_FAST_3D_URL as config_url
            api_url = config_url
        except ImportError:
            api_url = os.getenv("STABLE_FAST_3D_URL", "https://api.stability.ai/v1/generation/stable-fast-3d")

    if not timeout:
        try:
            from app.config import STABLE_FAST_3D_TIMEOUT as config_timeout
            timeout = config_timeout
        except ImportError:
            timeout_str = os.getenv("STABLE_FAST_3D_TIMEOUT", "60")
            timeout = int(timeout_str)

    # Check if API key is available
    if not api_key:
        logger.warning("No Stable Fast 3D API key provided. Cloud-API mode will not be available.")
        return None

    return StableFast3DClient(api_key=api_key, api_url=api_url, timeout=timeout)
