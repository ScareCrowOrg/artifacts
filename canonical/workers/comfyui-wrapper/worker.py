"""
ComfyUI Wrapper Worker – BaseWorker implementation.

Forwards image generation jobs to the ComfyUI inference service via HTTP.
Supports job type: comfyui_generate.

Redis Magro: When assignee_id is provided, the worker saves the PNG to disk at
  runtime/user/{assignee_id}/contents/{content_id}/{filename}.png
and returns a lightweight content reference instead of ~300KB base64 inline.
Backward compatible: if assignee_id is missing, returns image_base64 as before.
"""

import base64
import os
import sys
import uuid
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
    """HTTP wrapper that forwards jobs to the ComfyUI service.

    Supports Redis Magro: when assignee_id is in the payload,
    saves the generated PNG to runtime/user/{assignee}/contents/{content_id}/
    and returns a lightweight { content_id, relative_url } result.
    """

    def _resolve_content_path(self, relative_url: str) -> Path:
        """Resolve a relative_url (e.g. /runtime/user/...) to an absolute path."""
        artifacts_root = os.getenv("ARTIFACTS_ROOT", "/app/artifacts")
        return Path(artifacts_root) / relative_url.lstrip("/")

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
        # DIAG: Check if assignee_id was propagated (currently absent = Gap 1 root cause)
        assignee_id = payload.get("assignee_id", "NOT_PRESENT")
        content_id = payload.get("content_id", "NOT_PRESENT")
        self.logger.info("[%s] WORKER-DEBUG: assignee_id=%s, content_id=%s", self.job_id, assignee_id, content_id)

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

            # ======================================================================
            # REDIS MAGRO: Save PNG to disk and return content reference.
            #
            # When assignee_id is provided AND valid (not "NOT_PRESENT"):
            #   - Decode the base64 PNG
            #   - Save to runtime/user/{assignee_id}/contents/{content_id}/{filename}.png
            #   - Return { content_id, relative_url, mime_type, ... }
            #
            # Backward compatible: if assignee_id is NOT_PRESENT or content_id is
            # NOT_PRESENT, fall back to legacy behavior (return raw result).
            # ======================================================================
            if (assignee_id not in ("NOT_PRESENT", "unknown", None)
                    and content_id not in ("NOT_PRESENT", None)
                    and result.get("status") == "success"):

                image_base64 = result.get("image_base64", "")
                if image_base64:
                    # Use content_id from payload, or generate new one as fallback
                    save_content_id = content_id if content_id != "NOT_PRESENT" else str(uuid.uuid4())
                    mime_type = result.get("mime_type", "image/png")
                    extension = "png"
                    filename = f"{save_content_id}.{extension}"
                    rel_path = f"runtime/user/{assignee_id}/contents/{save_content_id}/{filename}"
                    abs_path = self._resolve_content_path(rel_path)
                    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                    with open(abs_path, "wb") as f:
                        f.write(base64.b64decode(image_base64))

                    self.logger.info(
                        "[%s] REDIS MAGRO: PNG saved to disk: %s (%d bytes, was %d chars base64)",
                        self.job_id,
                        abs_path,
                        os.path.getsize(abs_path),
                        len(image_base64),
                    )

                    # Return content reference (include image_base64 for backward compat)
                    self.logger.info("[%s] REDIS MAGRO: Returning content reference (content_id=%s, relative_url=%s)",
                                     self.job_id, save_content_id, f"/{rel_path}")
                    # DIAG: log result dict size for before/after comparison when removing image_base64
                    self.logger.info("[%s] DIAG-RESULT-SIZE: return dict with image_base64=%d chars (~%d KB)",
                                     self.job_id, len(image_base64), len(image_base64) // 1024)
                    return {
                        "success": True,
                        "status": "success",
                        "content_id": save_content_id,
                        "relative_url": f"/{rel_path}",
                        "mime_type": mime_type,
                    }

            # Legacy: return raw result (no assignee_id or no base64 data)
            self.logger.info("[%s] ✅ Returning response to BaseWorker (legacy mode)", self.job_id)
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
