"""
Rembg Background Removal Service

CPU-based background removal using Rembg with ONNX Runtime.
Implements singleton pattern to maintain model in memory across requests.

Phase 1: CPU-only (stable, ~40-50ms per image)
Phase 2: GPU support planned when CUDA ABI issues are resolved
"""

import logging
import base64
from io import BytesIO
from pathlib import Path
from typing import Optional
from PIL import Image

logger = logging.getLogger(__name__)


class RembgServiceError(Exception):
    """Exception raised for Rembg service errors."""
    pass


class RembgService:
    """
    Rembg Background Removal Service.

    Provides CPU-based background removal using Rembg with ONNX Runtime.
    Implements singleton pattern to maintain a single Rembg session in memory,
    avoiding repeated model loading.
    """
    
    _instance: Optional['RembgService'] = None
    _session = None
    _initialized = False
    
    def __new__(cls):
        """Singleton pattern: only one instance allowed."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize Rembg service (lazy loading - model loads on first use)."""
        if not self._initialized:
            logger.info("RembgService initialized (lazy loading - model will load on first use)")
            RembgService._initialized = True
            # Don't load session here - defer to first use
    
    def _initialize_session(self):
        """
        Initialize Rembg session (lazy loading).

        Loads the u2net model with CPU execution provider.
        Called only on first use to avoid consuming memory if Rembg is not used.
        """
        try:
            import rembg
            from rembg import new_session
            import os

            # Get configuration from environment
            model_name = os.getenv('REMBG_MODEL_NAME', 'u2net')
            cache_dir = os.getenv('REMBG_CACHE_DIR', '/root/.u2net')
            execution_provider = os.getenv('ONNX_EXECUTION_PROVIDER', 'CUDAExecutionProvider')

            logger.info(f"Loading Rembg model (lazy initialization):")
            logger.info(f"  Model: {model_name}")
            logger.info(f"  Cache directory: {cache_dir}")
            logger.info(f"  Execution provider: {execution_provider}")

            # Create cache directory if it doesn't exist
            Path(cache_dir).mkdir(parents=True, exist_ok=True)

            # Initialize Rembg session
            # NOTE: GPU provider has CUDA ABI compatibility issues with current ONNX Runtime + libcudnn.so.8
            # Using CPU provider for now - still fast enough for background removal (~40-50ms per image)
            # TODO: Resolve CUDA compatibility and switch back to GPU when onnxruntime CUDA provider is stable
            self._session = new_session(
                model_name=model_name,
                providers=['CPUExecutionProvider']
            )

            logger.info("✅ Rembg model loaded successfully (CPU provider)")

        except ImportError as e:
            logger.error(f"Failed to import rembg: {e}")
            raise RembgServiceError(f"Rembg not available: {e}")
        except Exception as e:
            logger.error(f"Failed to load Rembg model: {e}", exc_info=True)
            raise RembgServiceError(f"Rembg initialization failed: {e}")

    def _ensure_session(self):
        """Ensure Rembg session is loaded (lazy initialization on first use)."""
        if self._session is None:
            logger.info("First Rembg request detected, loading model now...")
            self._initialize_session()
    
    def remove_background(
        self,
        input_path: Path,
        output_path: Path,
        alpha_matting: bool = True,
        alpha_matting_foreground_threshold: int = 240,
        alpha_matting_background_threshold: int = 10,
        alpha_matting_erode_size: int = 10
    ) -> Path:
        """
        Remove background from image using GPU-accelerated Rembg.

        Args:
            input_path: Path to input image (with opaque background)
            output_path: Path to save output image (with transparent background)
            alpha_matting: Enable alpha matting for better edge quality
            alpha_matting_foreground_threshold: Foreground threshold (0-255)
            alpha_matting_background_threshold: Background threshold (0-255)
            alpha_matting_erode_size: Erosion kernel size

        Returns:
            Path to output image with transparent background

        Raises:
            RembgServiceError: If background removal fails
        """
        # Lazy load model on first use
        self._ensure_session()
        
        try:
            from rembg import remove
            
            logger.info(f"Removing background from: {input_path}")
            logger.info(f"Alpha matting: {alpha_matting}")
            
            # Read input image
            input_image = Image.open(input_path)
            
            # Log input image properties
            logger.debug(f"Input image: {input_image.mode} {input_image.size}")
            
            # Remove background using Rembg
            output_image = remove(
                input_image,
                session=self._session,
                alpha_matting=alpha_matting,
                alpha_matting_foreground_threshold=alpha_matting_foreground_threshold,
                alpha_matting_background_threshold=alpha_matting_background_threshold,
                alpha_matting_erode_size=alpha_matting_erode_size
            )
            
            # Ensure output is RGBA
            logger.info(f"🔍 Output image mode after remove(): {output_image.mode}")
            if output_image.mode != 'RGBA':
                logger.warning(f"⚠️  Output image mode is {output_image.mode}, converting to RGBA")
                output_image = output_image.convert('RGBA')
                logger.info(f"✅ Converted to RGBA: {output_image.mode}")

            logger.info(f"📝 Saving PNG with mode: {output_image.mode} to {output_path}")
            # Save output image
            output_image.save(output_path, format='PNG')
            logger.info(f"✅ PNG saved, checking saved file...")

            # Verify saved PNG
            saved_img = Image.open(output_path)
            logger.info(f"✅ Saved PNG verified - mode: {saved_img.mode} | size: {saved_img.size}")
            
            logger.info(f"✅ Background removed successfully: {output_path}")
            logger.info(f"   Output: {output_image.mode} {output_image.size}")
            logger.info(f"   File size: {output_path.stat().st_size} bytes")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Background removal failed: {e}", exc_info=True)
            raise RembgServiceError(f"Background removal failed: {e}")
    
    def remove_background_base64(
        self,
        input_base64: str,
        alpha_matting: bool = True,
        job_id: str = None,
        save_path: Path = None
    ) -> str:
        """
        Remove background from base64-encoded image.

        Convenience method that accepts and returns base64-encoded images.
        Useful for direct API integration.

        Args:
            input_base64: Base64-encoded input image (with or without data URI prefix)
            alpha_matting: Enable alpha matting for better edge quality
            job_id: Optional job ID for logging
            save_path: Optional path to save output image (in addition to returning base64)

        Returns:
            Base64-encoded output image with transparent background (no prefix)

        Raises:
            RembgServiceError: If background removal fails
        """
        # Lazy load model on first use
        self._ensure_session()

        try:
            from rembg import remove

            # Log job context
            if job_id:
                logger.info(f"[Job {job_id}] Starting background removal")

            # Strip data URI prefix if present
            if ',' in input_base64:
                input_base64 = input_base64.split(',', 1)[1]

            # Decode base64 to image
            image_bytes = base64.b64decode(input_base64)
            input_image = Image.open(BytesIO(image_bytes))

            logger.info(f"Processing base64 image: {input_image.mode} {input_image.size}")
            
            # Remove background
            output_image = remove(
                input_image,
                session=self._session,
                alpha_matting=alpha_matting
            )
            
            # Ensure output is RGBA
            logger.info(f"🔍 Output image mode (base64): {output_image.mode}")
            if output_image.mode != 'RGBA':
                logger.warning(f"⚠️  Output image mode is {output_image.mode}, converting to RGBA")
                output_image = output_image.convert('RGBA')
                logger.info(f"✅ Converted to RGBA: {output_image.mode}")

            # Optionally save to disk
            if save_path:
                save_path = Path(save_path)
                save_path.parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"💾 Saving to disk with mode: {output_image.mode}")
                output_image.save(str(save_path), format='PNG')

                # Verify saved file
                saved_check = Image.open(save_path)
                logger.info(f"✅ Saved to disk: {save_path.absolute()}")
                logger.info(f"✅ Saved file verified - mode: {saved_check.mode}")
                if job_id:
                    logger.info(f"[Job {job_id}] Output file: {save_path.absolute()}")

            # Encode to base64
            output_buffer = BytesIO()
            output_image.save(output_buffer, format='PNG')
            output_buffer.seek(0)

            output_base64 = base64.b64encode(output_buffer.read()).decode('utf-8')

            logger.info(f"✅ Background removed (base64): {output_image.mode} {output_image.size}")
            if job_id:
                logger.info(f"[Job {job_id}] Base64 output size: {len(output_base64)} chars")

            return output_base64
            
        except Exception as e:
            logger.error(f"Background removal (base64) failed: {e}", exc_info=True)
            raise RembgServiceError(f"Background removal failed: {e}")


# Module-level function for easy access
def get_rembg_service() -> RembgService:
    """
    Get singleton Rembg service instance.
    
    Returns:
        RembgService singleton instance
    """
    return RembgService()
