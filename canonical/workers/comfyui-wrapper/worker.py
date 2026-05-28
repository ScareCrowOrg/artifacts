"""
ComfyUI Wrapper Worker – BaseWorker implementation.

Forwards image generation jobs to the ComfyUI inference service via HTTP.
Supports job type: comfyui_generate.
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

COMFYUI_HOST = os.getenv("COMFYUI_HOST", "http://scareverse-comfyui-service:9090")
COMFYUI_TIMEOUT = float(os.getenv("COMFYUI_REQUEST_TIMEOUT", "300"))


class ComfyUIWorker(BaseWorker):
    """HTTP wrapper that forwards jobs to the ComfyUI service."""

    def setup(self) -> None:
        self.logger.info("[%s] Setting up ComfyUI worker: connecting to %s (timeout=%ss)", self.job_id, COMFYUI_HOST, COMFYUI_TIMEOUT)
        self._client = httpx.Client(base_url=COMFYUI_HOST, timeout=COMFYUI_TIMEOUT)
        self.logger.info("[%s] ✅ ComfyUI worker client initialized", self.job_id)

    def execute(self) -> Dict[str, Any]:
        self.logger.info("[%s] === INPUT DATA INSPECTION ===", self.job_id)
        self.logger.info("[%s] job_type: %s", self.job_id, self.job_type)
        self.logger.info("[%s] input_data keys: %s", self.job_id, list(self.input_data.keys()))

        # Handle both redis_client payload structure (top-level) and wrapped structure
        payload = self.input_data.get("payload") or self.input_data

        self.logger.info("[%s] === PAYLOAD AFTER EXTRACTION ===", self.job_id)
        self.logger.info("[%s] payload keys: %s", self.job_id, list(payload.keys()) if isinstance(payload, dict) else "NOT A DICT")

        body = {
            "prompt": payload.get("prompt", ""),
            "negative_prompt": payload.get("negative_prompt", ""),
            "width": payload.get("width", 1024),
            "height": payload.get("height", 1024),
            "steps": payload.get("num_inference_steps", 20),
            "cfg_scale": payload.get("guidance_scale", 7.0),
            "seed": payload.get("seed", -1),
        }

        self.logger.info(
            "[%s] POST /generate prompt=%.60s width=%dx%d steps=%d seed=%d",
            self.job_id,
            body["prompt"],
            body["width"],
            body["height"],
            body["steps"],
            body["seed"],
        )

        try:
            self.logger.debug("[%s] Request body: %s", self.job_id, body)
            response = self._client.post("/generate", json=body)
            self.logger.info(
                "[%s] ✅ Response received: status_code=%d content_length=%s",
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
                image_len = len(result.get("image_base64", ""))
                self.logger.info("[%s] Image base64 length: %d chars", self.job_id, image_len)

            self.logger.info("[%s] ✅ Returning response to BaseWorker", self.job_id)
            return result

        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "[%s] ❌ HTTP error %d: %s",
                self.job_id,
                exc.response.status_code,
                exc.response.text[:500],
                exc_info=True
            )
            raise
        except Exception as exc:
            self.logger.error(
                "[%s] ❌ Request failed: %s",
                self.job_id,
                str(exc),
                exc_info=True
            )
            raise

    def teardown(self) -> None:
        if hasattr(self, "_client"):
            self._client.close()
            self.logger.info("[%s] ✅ ComfyUI worker client closed", self.job_id)
