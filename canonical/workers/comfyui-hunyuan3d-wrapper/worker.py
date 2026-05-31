"""
Hunyuan3D Worker — Bridge between GateKeeper and ComfyUI/Hunyuan3D.

Forwards 3D mesh generation jobs to the ComfyUI inference service via HTTP.
Supports job type: hunyuan3d_generate.

Execution model: subprocess (spawned by GateKeeper WorkerExecutor)
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict

import httpx

try:
    from canonical.shared.base_worker import BaseWorker
except ImportError:
    _canonical = Path(__file__).resolve().parents[2]
    if str(_canonical.parent) not in sys.path:
        sys.path.insert(0, str(_canonical.parent))
    from canonical.shared.base_worker import BaseWorker

COMFYUI_SERVICE_URL = os.getenv(
    "COMFYUI_SERVICE_URL",
    "http://scareverse-comfyui-service:9090",
)


class Hunyuan3DWorker(BaseWorker):
    """HTTP wrapper that forwards 3D generation jobs to the ComfyUI service."""

    def setup(self) -> None:
        self.logger.info(
            "[%s] Setting up Hunyuan3D worker: connecting to %s",
            self.job_id,
            COMFYUI_SERVICE_URL,
        )
        self._client = httpx.Client(base_url=COMFYUI_SERVICE_URL, timeout=300.0)
        self.logger.info("[%s] Hunyuan3D worker client initialized", self.job_id)

    def execute(self) -> Dict[str, Any]:
        self.logger.info("[%s] === HUNYUAN3D EXECUTION ===", self.job_id)
        self.logger.info("[%s] job_type: %s", self.job_id, self.job_type)
        self.logger.info("[%s] input_data keys: %s", self.job_id, list(self.input_data.keys()))

        # Handle both redis_client payload structure (top-level) and wrapped structure
        payload = self.input_data.get("payload") or self.input_data

        # Extract image_base64 and seed from payload
        image_base64 = payload.get("image_base64", "")
        seed = payload.get("seed", -1)

        if not image_base64:
            error_msg = "No image_base64 provided in input_data"
            self.logger.error("[%s] %s", self.job_id, error_msg)
            return {"success": False, "error": error_msg}

        body = {
            "image_base64": image_base64,
            "seed": seed,
        }

        self.logger.info(
            "[%s] POST /generate-3d seed=%d image_base64 length=%d",
            self.job_id,
            seed,
            len(image_base64[:100]),
        )

        try:
            self.logger.debug("[%s] Request body keys: %s", self.job_id, list(body.keys()))
            response = self._client.post("/generate-3d", json=body)
            self.logger.info(
                "[%s] Response received: status_code=%d content_length=%d",
                self.job_id,
                response.status_code,
                len(response.content),
            )
            response.raise_for_status()

            result = response.json()
            self.logger.info("[%s] === RESPONSE INSPECTION ===", self.job_id)
            self.logger.info("[%s] Response keys: %s", self.job_id, list(result.keys()))
            self.logger.info("[%s] Response status: %s", self.job_id, result.get("status"))

            if result.get("status") == "success":
                mesh_len = len(result.get("mesh_base64", ""))
                self.logger.info(
                    "[%s] Mesh base64 length: %d chars (format: %s)",
                    self.job_id,
                    mesh_len,
                    result.get("mesh_format", "glb"),
                )

            self.logger.info("[%s] Returning response to BaseWorker", self.job_id)
            return result

        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "[%s] HTTP error %d: %s",
                self.job_id,
                exc.response.status_code,
                exc.response.text[:500],
                exc_info=True,
            )
            raise
        except Exception as exc:
            self.logger.error(
                "[%s] Request failed: %s",
                self.job_id,
                str(exc),
                exc_info=True,
            )
            raise

    def teardown(self) -> None:
        if hasattr(self, "_client"):
            self._client.close()
            self.logger.info("[%s] Hunyuan3D worker client closed", self.job_id)
