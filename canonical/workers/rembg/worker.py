"""
Rembg Worker – BaseWorker implementation for background removal.

Executes synchronously: setup (load model) → execute (process image) → teardown.
"""

import base64
import io
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Allow importing shared BaseWorker both when running from GateKeeper
# (PYTHONPATH=/app/artifacts) and when running tests from within the worker dir.
try:
    from canonical.shared.base_worker import BaseWorker
    from canonical.shared.utils import strip_data_uri_prefix
except ImportError:
    # Fallback for isolated development / direct execution
    _shared = Path(__file__).resolve().parents[2] / "shared"
    if str(_shared) not in sys.path:
        sys.path.insert(0, str(_shared.parent.parent))
    from canonical.shared.base_worker import BaseWorker
    from canonical.shared.utils import strip_data_uri_prefix


class RembgWorker(BaseWorker):
    """Background removal worker using rembg + ONNX Runtime."""

    def __init__(self, job_id: str, job_type: str, input_data: Dict[str, Any]):
        super().__init__(job_id, job_type, input_data)
        self._session = None

    def setup(self) -> None:
        """Load the rembg ONNX model into memory."""
        import rembg

        model_name = self.input_data.get("model", os.getenv("REMBG_MODEL_NAME", "u2net"))
        cache_dir = os.getenv("REMBG_CACHE_DIR", "/root/.u2net")
        Path(cache_dir).mkdir(parents=True, exist_ok=True)

        self.logger.info("Loading rembg model: %s", model_name)
        self._session = rembg.new_session(
            model_name=model_name,
            providers=["CPUExecutionProvider"],
        )
        self.logger.info("Model loaded")

    def execute(self) -> Dict[str, Any]:
        """Remove background from base64-encoded input image."""
        import rembg
        from PIL import Image

        image_base64 = strip_data_uri_prefix(self.input_data["image_base64"])
        alpha_matting: bool = self.input_data.get("alpha_matting", True)

        # Decode input
        image_bytes = base64.b64decode(image_base64)
        input_image = Image.open(io.BytesIO(image_bytes))
        self.logger.info("Input image: %s %s", input_image.mode, input_image.size)

        # Remove background
        output_image = rembg.remove(
            input_image,
            session=self._session,
            alpha_matting=alpha_matting,
        )

        # Ensure RGBA output
        if output_image.mode != "RGBA":
            output_image = output_image.convert("RGBA")

        # Encode result
        buf = io.BytesIO()
        output_image.save(buf, format="PNG")
        result_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        self.logger.info(
            "Background removed: %s %s → %d chars base64",
            output_image.mode,
            output_image.size,
            len(result_base64),
        )
        return {"image_base64": result_base64}

    def teardown(self) -> None:
        """Release model resources."""
        if self._session is not None:
            del self._session
            self._session = None
