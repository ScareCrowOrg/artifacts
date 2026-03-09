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

        logger.info("[%s] Launching subprocess worker: %s", job_id, worker_name)

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
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(stdin_bytes),
                timeout=float(timeout),
            )

            if stderr_bytes:
                logger.debug("[%s] Worker stderr: %s", job_id, stderr_bytes.decode()[:2000])

            raw_output = stdout_bytes.decode().strip()
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
                logger.info("[%s] Worker %s completed successfully", job_id, worker_name)
                return output.get("result", {})

            error_msg = output.get("error", "Unknown worker error")
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
            return self._venv_ready[worker_name]

        worker_dir = self.workers_path / worker_name
        venv_dir = worker_dir / ".venv"
        python_exe = venv_dir / "bin" / "python"

        if python_exe.exists():
            self._venv_ready[worker_name] = python_exe
            return python_exe

        logger.info("Creating .venv for worker: %s", worker_name)
        await self._run_command([sys.executable, "-m", "venv", str(venv_dir)])

        requirements = worker_dir / "requirements.txt"
        if requirements.exists():
            logger.info("Installing requirements for worker: %s", worker_name)
            await self._run_command(
                [str(python_exe), "-m", "pip", "install", "--quiet", "-r", str(requirements)]
            )

        logger.info("Venv ready for worker: %s", worker_name)
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
