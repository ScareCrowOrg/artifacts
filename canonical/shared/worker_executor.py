"""
WorkerExecutor – Subprocess orchestration for GateKeeper.

Manages the lifecycle of job worker subprocesses:
  1. Ensure isolated .venv per worker (auto-created on first run).
  2. Spawn the worker as a subprocess.
  3. Pass job data via stdin (JSON).
  4. Capture stdout (result JSON).
  5. Return structured result or raise on failure/timeout.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class WorkerExecutor:
    """
    Manages subprocess lifecycle for job workers.

    Each worker lives in ``workers_path/{worker_name}/`` and has:
      - ``main.py``: entry point
      - ``requirements.txt``: dependencies
      - ``.venv/``: auto-created isolated Python environment
    """

    def __init__(self, workers_path: str = "/app/artifacts/canonical/workers"):
        self.workers_path = Path(workers_path)
        self._venv_ready: dict = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(
        self,
        job_type: str,
        job_id: str,
        input_data: Dict[str, Any],
        worker_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a job worker as a subprocess and return its result.

        Args:
            job_type: Job type name (e.g. "rembg_removebackground").
            job_id: Unique job identifier.
            input_data: Arbitrary job input passed to the worker.
            worker_config: Full job-type definition dict (from job-types/*.json).
                           Must contain worker.path and configuration.timeout_seconds.

        Returns:
            The ``result`` dict from the worker's stdout JSON.

        Raises:
            TimeoutError: If the worker exceeds the configured timeout.
            ValueError: If the worker returns invalid JSON or signals failure.
            Exception: On subprocess execution errors.
        """
        worker_rel_path: str = worker_config["worker"]["path"]
        worker_name = Path(worker_rel_path).name
        timeout: int = worker_config.get("configuration", {}).get("timeout_seconds", 60)

        python_exe = await self._ensure_venv(worker_name)

        worker_input = {
            "job_id": job_id,
            "job_type": job_type,
            "input_data": input_data,
        }
        worker_dir = self.workers_path / worker_name
        entry_point = worker_dir / worker_config["worker"].get("entry_point", "main.py")

        logger.info(
            "[%s] Launching subprocess worker: %s (timeout=%ds, entry=%s)",
            job_id,
            worker_name,
            timeout,
            entry_point.name,
        )
        logger.debug("[%s] Worker input data: %s", job_id, json.dumps(worker_input)[:500])

        try:
            proc = await asyncio.create_subprocess_exec(
                str(python_exe),
                str(entry_point),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(worker_dir),
            )

            stdin_bytes = json.dumps(worker_input).encode()
            logger.debug("[%s] Sending %d bytes to worker stdin", job_id, len(stdin_bytes))

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(stdin_bytes),
                timeout=float(timeout),
            )

            if stderr_bytes:
                stderr_text = stderr_bytes.decode()
                logger.info("[%s] Worker stderr (%d bytes): %s", job_id, len(stderr_bytes), stderr_text[:1500])

            raw_output = stdout_bytes.decode().strip()
            logger.debug("[%s] Worker stdout (%d bytes): %s", job_id, len(stdout_bytes), raw_output[:500])

            if not raw_output:
                raise ValueError(
                    f"Worker {worker_name} produced no stdout output. "
                    f"stderr: {stderr_bytes.decode()[:500]}"
                )

            try:
                output = json.loads(raw_output)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Worker {worker_name} returned invalid JSON: {raw_output[:500]}"
                ) from exc

            if output.get("success"):
                logger.info(
                    "[%s] Worker %s completed successfully with result: %s",
                    job_id,
                    worker_name,
                    json.dumps(output.get("result", {}))[:300],
                )
                return output.get("result", {})

            error_msg = output.get("error", "Unknown worker error")
            logger.error("[%s] Worker %s reported failure: %s", job_id, worker_name, error_msg)
            raise ValueError(f"Worker {worker_name} reported failure: {error_msg}")

        except asyncio.TimeoutError as exc:
            logger.error("[%s] Worker %s timed out after %ds", job_id, worker_name, timeout)
            raise TimeoutError(
                f"Worker {worker_name} exceeded {timeout}s timeout"
            ) from exc
        except (ValueError, TimeoutError):
            raise
        except Exception as exc:
            logger.error(
                "[%s] Worker %s execution error: %s", job_id, worker_name, exc, exc_info=True
            )
            raise

    # ------------------------------------------------------------------
    # Venv Management
    # ------------------------------------------------------------------

    async def _ensure_venv(self, worker_name: str) -> Path:
        """
        Return the Python executable for worker_name, creating the .venv
        and installing requirements if it doesn't already exist.
        """
        if worker_name in self._venv_ready:
            logger.debug("Venv cache hit for worker: %s", worker_name)
            return self._venv_ready[worker_name]

        worker_dir = self.workers_path / worker_name
        venv_dir = worker_dir / ".venv"
        python_exe = venv_dir / "bin" / "python"

        if python_exe.exists():
            logger.info("Venv already exists for worker %s at %s", worker_name, venv_dir)
            self._venv_ready[worker_name] = python_exe
            return python_exe

        logger.info("Creating .venv for worker: %s (path=%s)", worker_name, venv_dir)
        try:
            await self._run_command([sys.executable, "-m", "venv", str(venv_dir)])
            logger.info("Venv created successfully for worker: %s", worker_name)
        except RuntimeError as exc:
            logger.error("Failed to create venv for worker %s: %s", worker_name, exc)
            raise

        requirements = worker_dir / "requirements.txt"
        if requirements.exists():
            logger.info("Installing requirements for worker: %s (file=%s)", worker_name, requirements)
            try:
                await self._run_command(
                    [str(python_exe), "-m", "pip", "install", "--quiet", "-r", str(requirements)]
                )
                logger.info("Requirements installed successfully for worker: %s", worker_name)
            except RuntimeError as exc:
                logger.error("Failed to install requirements for worker %s: %s", worker_name, exc)
                raise
        else:
            logger.debug("No requirements.txt found for worker: %s", worker_name)

        logger.info("Venv ready for worker: %s, python=%s", worker_name, python_exe)
        self._venv_ready[worker_name] = python_exe
        return python_exe

    async def _run_command(self, cmd: list) -> None:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"Command {cmd[0]} failed (exit {proc.returncode}): {stderr.decode()[:500]}"
            )

    def invalidate_venv_cache(self, worker_name: Optional[str] = None) -> None:
        """Force re-check of venv on next execution (useful after updates)."""
        if worker_name:
            self._venv_ready.pop(worker_name, None)
        else:
            self._venv_ready.clear()
