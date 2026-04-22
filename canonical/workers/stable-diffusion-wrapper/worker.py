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
        # DEBUG: Log complete input_data structure (matches Ollama pattern)
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
            "model": payload.get("model", SD_MODEL),
            "width": payload.get("width", 512),
            "height": payload.get("height", 512),
            "num_inference_steps": payload.get("num_inference_steps", 20),
            "guidance_scale": payload.get("guidance_scale", 7.5),
        }

        self.logger.info(
            "[%s] POST /api/generate prompt=%.60s model=%s width=%d height=%d steps=%d",
            self.job_id,
            body["prompt"],
            body["model"],
            body["width"],
            body["height"],
            body["num_inference_steps"],
        )
        response = self._client.post("/api/generate", json=body)
        response.raise_for_status()
        return response.json()

    def teardown(self) -> None:
        if hasattr(self, "_client"):
            self._client.close()
