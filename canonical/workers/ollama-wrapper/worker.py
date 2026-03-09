"""
Ollama Wrapper Worker – BaseWorker implementation.

Forwards jobs to the Ollama LLM inference service via HTTP.
Supports job types: ollama_generate, ollama_chat.
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

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://scareverse-ollama-service:11434")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_REQUEST_TIMEOUT", "120"))


class OllamaWorker(BaseWorker):
    """HTTP wrapper that forwards jobs to the Ollama service."""

    def setup(self) -> None:
        self._client = httpx.Client(base_url=OLLAMA_HOST, timeout=OLLAMA_TIMEOUT)

    def execute(self) -> Dict[str, Any]:
        job_type = self.job_type
        payload = self.input_data.get("payload") or self.input_data

        if job_type == "ollama_generate":
            endpoint = "/api/generate"
            body = {
                "model": payload.get("model", "mistral"),
                "prompt": payload.get("prompt", ""),
                "stream": False,
                "options": payload.get("options", {}),
            }
        elif job_type == "ollama_chat":
            endpoint = "/api/chat"
            body = {
                "model": payload.get("model", "mistral"),
                "messages": payload.get("messages", []),
                "stream": False,
                "options": payload.get("options", {}),
            }
        else:
            raise ValueError(f"Unsupported job_type for OllamaWorker: {job_type}")

        self.logger.info("POST %s model=%s", endpoint, body.get("model"))
        response = self._client.post(endpoint, json=body)
        response.raise_for_status()
        return response.json()

    def teardown(self) -> None:
        if hasattr(self, "_client"):
            self._client.close()
