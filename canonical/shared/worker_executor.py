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

        # GateKeeper extracts input_data from job payload (which may be at top level)
        # Pass extracted input_data wrapped back (worker interface expects input_data key)
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
        logger.info(
            "[%s] Worker environment: python=%s, cwd=%s, entry_point=%s",
            job_id,
            python_exe,
            worker_dir,
            entry_point,
        )
        logger.info("[%s] Entry point exists: %s", job_id, entry_point.exists())

        # DEBUG: Log complete worker input that will be sent via stdin
        logger.info("[%s] === WORKER INPUT TO STDIN ===", job_id)
        logger.info("[%s] worker_input keys: %s", job_id, list(worker_input.keys()))
        logger.info("[%s] job_type: %s", job_id, worker_input.get("job_type"))
        logger.info("[%s] input_data keys: %s", job_id, list(worker_input.get("input_data", {}).keys()))
        logger.info("[%s] Complete stdin payload: %s", job_id, json.dumps(worker_input, default=str)[:1500])
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

            logger.debug("[%s] Subprocess created with PID: %s", job_id, proc.pid)

            stdin_bytes = json.dumps(worker_input).encode()
            logger.debug("[%s] Sending %d bytes to worker stdin", job_id, len(stdin_bytes))

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(stdin_bytes),
                timeout=float(timeout),
            )

            logger.info("[%s] Worker process exited with returncode: %d", job_id, proc.returncode)

            if stderr_bytes:
                stderr_text = stderr_bytes.decode()
                logger.info("[%s] Worker stderr (%d bytes): %s", job_id, len(stderr_bytes), stderr_text[:2000])

            raw_output = stdout_bytes.decode().strip()

            # DEBUG: Log raw stdout before parsing
            logger.info("[%s] === WORKER STDOUT INSPECTION ===", job_id)
            logger.info("[%s] stdout length: %d bytes", job_id, len(stdout_bytes))
            logger.info("[%s] raw_output: %s", job_id, raw_output[:1500])
            logger.debug("[%s] Worker stdout (%d bytes): %s", job_id, len(stdout_bytes), raw_output[:500])

            if not raw_output:
                # DIAG: hunyuan3d-worker-httpx-crash -- remover apos fix
                _diag_full_stderr = stderr_bytes.decode() if stderr_bytes else "(no stderr)"
                logger.error(
                    "DIAG [%s] Worker produced no stdout. exit_code=%s. "
                    "Full stderr (%d bytes):\n%s",
                    job_id, proc.returncode, len(_diag_full_stderr), _diag_full_stderr,
                )
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
            # DIAG: hunyuan3d-worker-httpx-crash -- remover apos fix
            try:
                bin_contents = [str(p) for p in (venv_dir / "bin").iterdir()]
                logger.info("DIAG [%s] Venv bin/ directory contents (%d items): %s",
                            worker_name, len(bin_contents), bin_contents)
            except Exception as _diag_venv_err:
                logger.warning("DIAG [%s] Could not list venv bin/ contents: %s", worker_name, _diag_venv_err)
        except RuntimeError as exc:
            logger.error("Failed to create venv for worker %s: %s", worker_name, exc)
            raise

        requirements = worker_dir / "requirements.txt"
        if requirements.exists():
            logger.info("Installing requirements for worker: %s (file=%s)", worker_name, requirements)
            # DIAG: hunyuan3d-worker-httpx-crash -- remover apos fix
            try:
                req_content = requirements.read_text()
                logger.info("DIAG [%s] requirements.txt content:\n%s", worker_name, req_content)
            except Exception as _diag_req_err:
                logger.warning("DIAG [%s] Could not read requirements.txt: %s", worker_name, _diag_req_err)
            try:
                await self._run_command(
                    [str(python_exe), "-m", "pip", "install", "--quiet", "-r", str(requirements)]
                )
                logger.info("Requirements installed successfully for worker: %s", worker_name)
                # DIAG: hunyuan3d-worker-httpx-crash -- remover apos fix
                try:
                    _pip_list_proc = await asyncio.create_subprocess_exec(
                        str(python_exe), "-m", "pip", "list", "--format=columns",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    _pip_stdout, _pip_stderr = await _pip_list_proc.communicate()
                    logger.info("DIAG [%s] pip list (exit=%d):\n%s",
                                worker_name, _pip_list_proc.returncode, _pip_stdout.decode()[:2500])
                    if _pip_stderr:
                        logger.warning("DIAG [%s] pip list stderr:\n%s", worker_name, _pip_stderr.decode()[:1000])
                except Exception as _diag_pip_list_err:
                    logger.warning("DIAG [%s] pip list failed: %s", worker_name, _diag_pip_list_err)

                # PERMANENTE: verificar se httpx funciona apos pip install (1 retry se falhar)
                _pip_ok = False
                for _retry_attempt in range(2):
                    _verify_proc = await asyncio.create_subprocess_exec(
                        str(python_exe), "-c", "import httpx; print(httpx.__version__)",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    _v_out, _v_err = await _verify_proc.communicate()
                    if _verify_proc.returncode == 0:
                        _pip_ok = True
                        _ver = _v_out.decode().strip() if _v_out else "unknown"
                        logger.info(
                            "[%s] Pip install verified: httpx %s imported successfully (attempt %d)",
                            worker_name, _ver, _retry_attempt + 1,
                        )
                        break
                    else:
                        _v_err_text = _v_err.decode()[:500] if _v_err else "(no stderr)"
                        logger.warning(
                            "[%s] Pip install verification FAILED (attempt %d): httpx import error. stderr: %s",
                            worker_name, _retry_attempt + 1, _v_err_text,
                        )
                        if _retry_attempt == 0:
                            logger.info("[%s] Retrying pip install once...", worker_name)
                            await self._run_command(
                                [str(python_exe), "-m", "pip", "install", "--quiet", "-r", str(requirements)]
                            )
                if not _pip_ok:
                    raise RuntimeError(
                        f"Pip install verification failed for {worker_name}: "
                        "httpx import failed after 2 attempts"
                    )
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
