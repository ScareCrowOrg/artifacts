"""
Stable Diffusion Wrapper Worker – BaseWorker implementation.

Forwards image generation jobs to the Stable Diffusion inference service via HTTP.
Supports job type: sd_generate.
"""

import base64
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

SD_HOST = os.getenv("SD_HOST", "http://scareverse-sd-service:9090")
SD_TIMEOUT = float(os.getenv("SD_REQUEST_TIMEOUT", "300"))
SD_MODEL = os.getenv("SD_MODEL", "stabilityai/stable-diffusion-xl-base-1.0")


class StableDiffusionWorker(BaseWorker):
    """HTTP wrapper that forwards jobs to the Stable Diffusion service."""

    def setup(self) -> None:
        self._client = httpx.Client(base_url=SD_HOST, timeout=SD_TIMEOUT)

    def execute(self) -> Dict[str, Any]:
        payload = self.input_data.get("payload") or self.input_data

        body = {
            "prompt": payload.get("prompt", ""),
            "negative_prompt": payload.get("negative_prompt", ""),
            "model": payload.get("model", SD_MODEL),
            "width": payload.get("width", 512),
            "height": payload.get("height", 512),
            "num_inference_steps": payload.get("num_inference_steps", 20),
            "guidance_scale": payload.get("guidance_scale", 7.5),
        }

        self.logger.info(
            "POST /api/generate prompt=%.60s model=%s",
            body["prompt"],
            body["model"],
        )
        response = self._client.post("/api/generate", json=body)
        response.raise_for_status()
        return response.json()

    def teardown(self) -> None:
        if hasattr(self, "_client"):
            self._client.close()
