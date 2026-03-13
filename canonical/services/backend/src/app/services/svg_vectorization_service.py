"""
SVG vectorization service.

This service converts PNG images to SVG format using OpenCV + Potrace pipeline
for production-quality vectorization with Bézier curves suitable for 3D extrusion.
"""

import base64
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class SVGVectorizationService:
    """Service for converting PNG images to SVG format using OpenCV + Potrace."""

    def __init__(self):
        """
        Initialize the vectorization service.

        Raises:
            RuntimeError: If potrace binary is not found in system PATH
        """
        self._potrace_path = self._verify_potrace_installation()

    def _verify_potrace_installation(self) -> str:
        """
        Verify that potrace binary is installed and accessible.

        Returns:
            str: Full path to the potrace binary

        Raises:
            RuntimeError: If potrace is not found in system PATH or not in trusted location
        """
        try:
            # Use shutil.which to get full path and verify binary exists
            potrace_path = shutil.which("potrace")
            if not potrace_path:
                raise FileNotFoundError("Potrace not found in PATH")

            # Validate that the binary is in a trusted system directory
            trusted_dirs = ["/usr/bin", "/usr/local/bin", "/bin", "/opt/homebrew/bin"]
            # On Windows, also allow Program Files
            if os.name == "nt":
                trusted_dirs.extend(
                    [
                        os.path.join(
                            os.environ.get("ProgramFiles", "C:\\Program Files"),
                            "potrace",
                        ),
                        os.path.join(
                            os.environ.get(
                                "ProgramFiles(x86)", "C:\\Program Files (x86)"
                            ),
                            "potrace",
                        ),
                    ]
                )

            # Normalize path for comparison
            potrace_path_normalized = os.path.normpath(potrace_path)
            is_trusted = any(
                potrace_path_normalized.startswith(os.path.normpath(trusted_dir))
                for trusted_dir in trusted_dirs
            )

            if not is_trusted:
                logger.warning(
                    "Potrace found at non-standard location: %s. Expected in one of: %s",
                    potrace_path, ', '.join(trusted_dirs)
                )

            # Verify the binary is executable and works
            result = subprocess.run(
                [potrace_path, "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                logger.info("Potrace found at %s: %s", potrace_path, result.stdout.strip())
                return potrace_path
            else:
                raise RuntimeError(
                    "Potrace binary found but returned non-zero exit code"
                )
        except FileNotFoundError:
            error_msg = (
                "Potrace binary not found. Please install potrace:\n"
                "  - Ubuntu/Debian: sudo apt-get install potrace\n"
                "  - macOS: brew install potrace\n"
                "  - Windows: Download from http://potrace.sourceforge.net/"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        except subprocess.TimeoutExpired:
            raise RuntimeError("Potrace verification timed out")
        except Exception as e:
            raise RuntimeError(f"Failed to verify potrace installation: {str(e)}") from e

    async def vectorize_image(
        self, image_base64: str, simplify: bool = True, _threshold: int = 128
    ) -> Dict[str, Any]:
        """
        Convert a PNG image to SVG format using OpenCV + Potrace pipeline.

        Pipeline:
        1. Decode Base64 image
        2. OpenCV: Binarization (Otsu thresholding) for high contrast
        3. OpenCV: Morphological operations to remove noise
        4. Potrace: Vectorization with Bézier curve smoothing

        This produces clean curves suitable for 3D extrusion in Three.js.

        Args:
            image_base64: Base64-encoded PNG image
            simplify: Whether to use Potrace curve smoothing (alphamax)
            threshold: DEPRECATED - Not used with Otsu auto-thresholding.
                      Kept for backward API compatibility. Will be removed in v2.0.

        Returns:
            Dict containing:
                - success: bool
                - svg: SVG markup string (if success)
                - error: Error message (if failed)
                - metadata: Vectorization parameters
        """
        if not image_base64:
            return {"success": False, "error": "No image data provided"}

        tmp_bmp_path = None
        try:
            # 1. Decode & Convert to OpenCV format
            img_data = base64.b64decode(image_base64)
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)

            if img is None:
                return {"success": False, "error": "Failed to decode image"}

            # Get dimensions
            height, width = img.shape

            # 2. Image Processing (Cleaning)
            # Apply Otsu's thresholding for automatic binary conversion
            # This creates perfect black and white without guessing threshold
            # Note: The first parameter (0) is ignored when using THRESH_OTSU,
            # as Otsu's method automatically determines the optimal threshold value
            _, binary_img = cv2.threshold(
                img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )

            # 3. Morphological operations to remove noise (small isolated pixels)
            kernel = np.ones((2, 2), np.uint8)
            binary_img = cv2.morphologyEx(binary_img, cv2.MORPH_OPEN, kernel)

            # 4. Save as BMP for Potrace using secure temporary file
            # Use context manager to ensure file is properly closed before potrace reads it
            with tempfile.NamedTemporaryFile(
                suffix=".bmp", delete=False, dir=tempfile.gettempdir()
            ) as tmp_bmp:
                tmp_bmp_path = tmp_bmp.name
                Image.fromarray(binary_img).save(tmp_bmp.name)

            # Validate that the file was created successfully
            if not os.path.exists(tmp_bmp_path):
                return {"success": False, "error": "Failed to create temporary file"}

            # 5. Run Potrace using validated full path
            # -s: SVG output
            # --alphamax 1.0: Smooths curves (avoids sharp corners where rounded)
            # --turdsize 2: Removes 'islands' of pixels smaller than 2px (noise cleanup)
            # -o -: Output to stdout
            potrace_args = [self._potrace_path, tmp_bmp_path, "-s"]

            if simplify:
                potrace_args.extend(["--alphamax", "1.0", "--turdsize", "2"])

            potrace_args.extend(["-o", "-"])

            proc = subprocess.run(
                potrace_args,
                capture_output=True,
                text=True,
                check=True,
                timeout=15,  # 15 seconds should be sufficient for most images
            )
            svg_content = proc.stdout

            return {
                "success": True,
                "svg": svg_content,
                "metadata": {
                    "width": width,
                    "height": height,
                    "method": "opencv_otsu_potrace",
                    "simplified": simplify,
                    "pipeline": "OpenCV (Otsu + Morphology) -> Potrace (Bézier)",
                },
            }

        except subprocess.CalledProcessError as e:
            logger.error("Potrace failed: %s", e.stderr, exc_info=True)
            return {
                "success": False,
                "error": f"Potrace vectorization failed: {e.stderr}",
            }
        except subprocess.TimeoutExpired:
            logger.error("Potrace execution timed out")
            return {
                "success": False,
                "error": "Vectorization timed out (>15s). Image may be too complex.",
            }
        except Exception as e:
            logger.error("Vectorization error: %s", e, exc_info=True)
            return {"success": False, "error": f"Vectorization failed: {str(e)}"}
        finally:
            # Cleanup temporary file with robust error handling
            if tmp_bmp_path:
                try:
                    if os.path.exists(tmp_bmp_path):
                        os.remove(tmp_bmp_path)
                        logger.debug("Cleaned up temporary file: %s", tmp_bmp_path)
                except OSError as e:
                    # Log but don't raise - cleanup failure shouldn't break the flow
                    logger.warning("Failed to remove temp file %s: %s", tmp_bmp_path, e)
                except Exception as e:
                    logger.warning("Unexpected error cleaning temp file %s: %s", tmp_bmp_path, e)


# Singleton instance
_vectorization_service: Optional[SVGVectorizationService] = None


def get_vectorization_service() -> SVGVectorizationService:
    """Get or create the vectorization service singleton."""
    global _vectorization_service
    if _vectorization_service is None:
        _vectorization_service = SVGVectorizationService()
    return _vectorization_service
