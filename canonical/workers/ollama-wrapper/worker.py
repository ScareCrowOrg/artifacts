"""
Ollama Wrapper Worker – BaseWorker implementation.

Forwards jobs to the Ollama LLM inference service via HTTP.
Supports job types: ollama_generate, ollama_chat.
"""

import json
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

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://scareverse-ollama-raw:11434")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_REQUEST_TIMEOUT", "120"))


class OllamaWorker(BaseWorker):
    """HTTP wrapper that forwards jobs to the Ollama service."""

    def setup(self) -> None:
        self.logger.info(
            "[%s] Setting up OllamaWorker: connecting to %s (timeout=%s)",
            self.job_id,
            OLLAMA_HOST,
            OLLAMA_TIMEOUT,
        )
        self._client = httpx.Client(base_url=OLLAMA_HOST, timeout=OLLAMA_TIMEOUT)
        self.logger.info("[%s] OllamaWorker client initialized", self.job_id)

    def execute(self) -> Dict[str, Any]:
        job_type = self.job_type
        payload = self.input_data.get("payload") or self.input_data

        self.logger.debug("[%s] Input payload: %s", self.job_id, json.dumps(payload)[:500])

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

        self.logger.info(
            "[%s] Sending POST request to %s (model=%s, endpoint=%s)",
            self.job_id,
            OLLAMA_HOST,
            body.get("model"),
            endpoint,
        )
        self.logger.debug("[%s] Request body: %s", self.job_id, json.dumps(body)[:800])

        try:
            response = self._client.post(endpoint, json=body)
            self.logger.info(
                "[%s] Response received: status=%d, content_length=%s",
                self.job_id,
                response.status_code,
                len(response.content),
            )
            self.logger.debug("[%s] Response body: %s", self.job_id, response.text[:500])
            response.raise_for_status()
            result = response.json()
            self.logger.info("[%s] Successfully parsed response JSON", self.job_id)
            return result
        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "[%s] HTTP error %d from Ollama: %s",
                self.job_id,
                exc.response.status_code,
                exc.response.text[:500],
            )
            raise
        except httpx.RequestError as exc:
            self.logger.error(
                "[%s] Request error connecting to Ollama at %s: %s",
                self.job_id,
                OLLAMA_HOST,
                exc,
            )
            raise
        except Exception as exc:
            self.logger.error("[%s] Unexpected error: %s", self.job_id, exc, exc_info=True)
            raise

    def teardown(self) -> None:
        if hasattr(self, "_client"):
            self.logger.debug("[%s] Closing OllamaWorker client", self.job_id)
            self._client.close()
