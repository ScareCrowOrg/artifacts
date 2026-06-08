"""
Hunyuan3D Worker — Bridge between GateKeeper and ComfyUI/Hunyuan3D.

Forwards 3D mesh generation jobs to the ComfyUI inference service via HTTP.
Supports job type: hunyuan3d_generate.

Execution model: subprocess (spawned by GateKeeper WorkerExecutor)
"""

import base64
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

# DIAG: hunyuan3d-worker-httpx-crash — remover apos fix
try:
    import httpx
except Exception as _httpx_import_err:
    import traceback as _traceback
    print(
        f"[Hunyuan3D-Worker] CRITICAL: Failed to import httpx: {_httpx_import_err}",
        file=sys.stderr,
    )
    print(
        f"[Hunyuan3D-Worker] Traceback:\n{_traceback.format_exc()}",
        file=sys.stderr,
    )
    print(
        f"[Hunyuan3D-Worker] Python version: {sys.version}",
        file=sys.stderr,
    )
    print(
        f"[Hunyuan3D-Worker] sys.path: {sys.path}",
        file=sys.stderr,
    )
    raise

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
    """HTTP wrapper that forwards 3D generation jobs to the ComfyUI service.

    Supports two input modes:
    1. Content reference (new): input_image.content_id / input_image.relative_url
       — reads input image from disk at runtime/user/{assignee}/contents/
    2. Legacy (fallback): image_base64 — raw base64 string in Redis payload

    Output is saved to runtime/user/{assignee}/contents/{content_id}/mesh.glb
    and the worker returns lightweight { content_id, relative_url }.
    """

    def _resolve_content_path(self, relative_url: str) -> Path:
        """Resolve a relative_url (e.g. /runtime/user/...) to an absolute path."""
        artifacts_root = os.getenv("ARTIFACTS_ROOT", "/app/artifacts")
        return Path(artifacts_root) / relative_url.lstrip("/")

    def _load_input_image(self) -> str:
        """Load input image from content reference or legacy base64.

        Priority:
        1. input_image.relative_url (content reference — new jobs)
        2. input_image as raw string (legacy content reference)
        3. image_base64 (legacy fallback — old jobs)
        """
        payload = self.input_data.get("payload") or self.input_data
        input_image = payload.get("input_image", {})
        image_base64 = payload.get("image_base64", "")

        # NEW: Content reference path — read from disk
        if isinstance(input_image, dict) and input_image.get("relative_url"):
            path = self._resolve_content_path(input_image["relative_url"])
            self.logger.info(
                "[%s] Reading input image from disk: %s",
                self.job_id,
                path,
            )
            if not path.exists():
                self.logger.warning(
                    "[%s] Content file not found at %s, falling back to image_base64",
                    self.job_id,
                    path,
                )
                if image_base64:
                    return image_base64
                raise FileNotFoundError(f"Content file not found: {path}")
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")

        # LEGACY: Direct base64 fallback (old jobs)
        if image_base64:
            return image_base64

        # LEGACY: input_image as raw string
        if isinstance(input_image, str) and len(input_image) > 100:
            return input_image

        raise ValueError("No input image found: neither content reference nor image_base64")

    def setup(self) -> None:
        self.logger.info(
            "[%s] Setting up Hunyuan3D worker: connecting to %s",
            self.job_id,
            COMFYUI_SERVICE_URL,
        )
        self._client = httpx.Client(base_url=COMFYUI_SERVICE_URL, timeout=600.0)
        self.logger.info("[%s] Hunyuan3D worker client initialized", self.job_id)

    def execute(self) -> Dict[str, Any]:
        self.logger.info("[%s] === HUNYUAN3D EXECUTION ===", self.job_id)
        self.logger.info("[%s] job_type: %s", self.job_id, self.job_type)
        self.logger.info("[%s] input_data keys: %s", self.job_id, list(self.input_data.keys()))

        # Handle both redis_client payload structure (top-level) and wrapped structure
        payload = self.input_data.get("payload") or self.input_data
        seed = payload.get("seed", -1)

        # Load input image from disk (content reference) or legacy base64
        try:
            image_base64 = self._load_input_image()
        except (FileNotFoundError, ValueError) as exc:
            error_msg = str(exc)
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

            # Save output GLB to runtime/user/ for direct Vite serving
            mesh_base64 = result.get("mesh_base64", "")
            if mesh_base64:
                assignee_id = payload.get("assignee_id", "unknown")
                if assignee_id == "unknown":
                    self.logger.warning(
                        "[%s] assignee_id is 'unknown' — user context missing. "
                        "File will be saved to runtime/user/unknown/",
                        self.job_id,
                    )
                content_id = str(uuid.uuid4())
                rel_path = f"runtime/user/{assignee_id}/contents/{content_id}/mesh.glb"
                abs_path = self._resolve_content_path(rel_path)
                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                with open(abs_path, "wb") as f:
                    f.write(base64.b64decode(mesh_base64))

                self.logger.info(
                    "[%s] Mesh saved to disk: %s (%d bytes)",
                    self.job_id,
                    abs_path,
                    len(mesh_base64),
                )

                # Return lightweight result
                return {
                    "success": True,
                    "status": "success",
                    "content_id": content_id,
                    "relative_url": f"/{rel_path}",
                    "mesh_format": result.get("mesh_format", "glb"),
                }

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
