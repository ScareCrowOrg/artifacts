"""
VenvManager – Venv lifecycle management for subprocess workers.

Provides:
- Eager venv setup on GateKeeper startup (not lazy on first job).
- Venv verification (Python executable test).
- Periodic health checks with staleness detection (requirements.txt mtime).
- Auto-rebuild on corruption or staleness.
- Metadata tracking (creation time, size, status).
"""

import asyncio
import logging
import shutil
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Optional

if TYPE_CHECKING:
    from metrics import GateKeeperMetrics

logger = logging.getLogger(__name__)


class VenvManager:
    """
    Manage venv setup, verification, and health checks for subprocess workers.

    Usage::

        manager = VenvManager(workers_path)
        results = await manager.setup_all_venvs(discovered_workers)
        manager.log_summary()

        # In GateKeeper.run():
        asyncio.create_task(manager.start_health_checks())
    """

    def __init__(
        self,
        workers_path: Path,
        health_check_interval: int = 60,
        metrics: "Optional[GateKeeperMetrics]" = None,
        max_rebuild_failures: int = 3,
    ) -> None:
        self.workers_path = Path(workers_path)
        self.health_check_interval = health_check_interval
        self.metrics = metrics
        self.max_rebuild_failures = max_rebuild_failures

        # worker_name → Path to venv python executable
        self.ready_venvs: Dict[str, Path] = {}
        # worker_name → metadata dict
        self.venv_metadata: Dict[str, dict] = {}
        # worker_name → consecutive rebuild failure count
        self._rebuild_failures: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def setup_all_venvs(
        self, discovered_workers: Dict[str, dict]
    ) -> Dict[str, bool]:
        """
        Eagerly create or verify venvs for all discovered workers.

        Runs at GateKeeper startup so that every worker is ready before
        the first job arrives.

        Args:
            discovered_workers: Mapping returned by WorkerDiscovery.discover().

        Returns:
            Mapping of worker_name → setup_success.
        """
        results: Dict[str, bool] = {}
        for worker_name in discovered_workers:
            try:
                logger.info("[%s] Setting up venv...", worker_name)
                python_exe = await self._setup_venv(worker_name)
                self.ready_venvs[worker_name] = python_exe
                results[worker_name] = True
                logger.info("✅ [%s] Venv ready", worker_name)
            except Exception as exc:
                logger.error("❌ [%s] Venv setup failed: %s", worker_name, exc)
                results[worker_name] = False

        return results

    def get_venv_python(self, worker_name: str) -> Optional[Path]:
        """Return the Python executable for *worker_name*, or None if not ready."""
        return self.ready_venvs.get(worker_name)

    def set_metrics(self, metrics: "GateKeeperMetrics") -> None:
        """Attach a GateKeeperMetrics instance for recording creation events."""
        self.metrics = metrics

    # ------------------------------------------------------------------
    # Health check loop
    # ------------------------------------------------------------------

    async def start_health_checks(self) -> None:
        """
        Background loop that periodically checks all venvs for staleness /
        corruption and triggers auto-rebuild as needed.

        Designed to run as an ``asyncio.create_task``.  Interval is
        configurable via *health_check_interval* (default 60 s).
        """
        logger.info(
            "🔍 Venv health-check loop started (interval=%ds)",
            self.health_check_interval,
        )
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._run_health_checks()
            except asyncio.CancelledError:
                logger.info("Venv health-check loop cancelled")
                break
            except Exception as exc:
                logger.error("Venv health-check iteration failed: %s", exc, exc_info=True)

    async def _run_health_checks(self) -> None:
        """Inspect every ready venv for corruption and requirements staleness."""
        for worker_name, python_exe in list(self.ready_venvs.items()):
            try:
                worker_dir = self.workers_path / worker_name

                # Check 1: Python executable still works.
                if not await self._verify_venv(worker_name, python_exe):
                    logger.warning(
                        "[%s] Venv corrupted – auto-rebuilding...", worker_name
                    )
                    await self._rebuild_venv(worker_name)
                    continue

                # Check 2: requirements.txt was modified after the venv was created.
                requirements = worker_dir / "requirements.txt"
                if requirements.exists():
                    req_mtime = requirements.stat().st_mtime
                    venv_mtime = (worker_dir / ".venv").stat().st_mtime
                    if req_mtime > venv_mtime:
                        logger.info(
                            "[%s] requirements.txt changed – rebuilding venv...",
                            worker_name,
                        )
                        await self._rebuild_venv(worker_name)

            except Exception as exc:
                logger.error(
                    "[%s] Health-check error: %s", worker_name, exc, exc_info=True
                )

    # ------------------------------------------------------------------
    # Internal venv operations
    # ------------------------------------------------------------------

    async def _setup_venv(self, worker_name: str) -> Path:
        """Create (or reuse) the venv for *worker_name*.

        Returns:
            Path to the venv Python executable.
        """
        worker_dir = self.workers_path / worker_name
        venv_path = worker_dir / ".venv"
        python_exe = venv_path / "bin" / "python"

        if python_exe.exists():
            # Verify the existing venv is still functional before reusing it.
            is_valid = await self._verify_venv(worker_name, python_exe)
            if not is_valid:
                logger.warning(
                    "[%s] Existing venv failed verification – rebuilding", worker_name
                )
                shutil.rmtree(venv_path, ignore_errors=True)
                # Fall through to create a new venv below.
            else:
                self.venv_metadata[worker_name] = {"status": "reused"}
                logger.debug("[%s] Reusing existing venv", worker_name)
                return python_exe

        # Create a new venv.
        logger.info("[%s] Creating new venv at %s", worker_name, venv_path)
        start_time = time.time()

        await self._run_async([sys.executable, "-m", "venv", str(venv_path)])

        requirements = worker_dir / "requirements.txt"
        if requirements.exists():
            logger.info("[%s] Installing requirements...", worker_name)
            await self._run_async(
                [
                    str(python_exe),
                    "-m",
                    "pip",
                    "install",
                    "--quiet",
                    "-r",
                    str(requirements),
                ]
            )

        elapsed = time.time() - start_time
        size_mb = self._get_dir_size_mb(venv_path)

        self.venv_metadata[worker_name] = {
            "status": "created",
            "created_at": time.time(),
            "creation_time_sec": elapsed,
            "size_mb": size_mb,
        }

        logger.info(
            "[%s] Venv created in %.2fs (size: %.1f MB)",
            worker_name,
            elapsed,
            size_mb,
        )

        if self.metrics is not None:
            self.metrics.record_venv_creation(worker_name, elapsed, size_mb)

        return python_exe

    async def _verify_venv(self, worker_name: str, python_exe: Path) -> bool:
        """
        Verify *python_exe* is functional by testing Python and real worker
        dependencies (httpx).

        Returns:
            True if verification passed, False otherwise.
        """
        try:
            # PERMANENTE: melhoria de observabilidade — test real worker dependencies
            return_code = await self._run_async(
                [str(python_exe), "-c", "import sys; import httpx; sys.exit(0)"],
                timeout=5,
            )
            if return_code == 0:
                logger.debug("[%s] Venv verification passed (sys + httpx)", worker_name)
                return True
            logger.warning(
                "[%s] Venv verification returned non-zero: %d",
                worker_name,
                return_code,
            )
            # DIAG: hunyuan3d-worker-httpx-crash -- remover apos fix
            logger.info(
                "DIAG [%s] Venv verification failed (exit=%d) — worker will fail on first job",
                worker_name, return_code,
            )
            return False
        except Exception as exc:
            logger.warning("[%s] Venv verification failed: %s", worker_name, exc)
            # DIAG: hunyuan3d-worker-httpx-crash -- remover apos fix
            logger.info(
                "DIAG [%s] Venv verification threw exception: %s",
                worker_name, exc,
            )
            return False

    async def _rebuild_venv(self, worker_name: str) -> None:
        """Remove and recreate the venv for *worker_name*.

        Consecutive rebuild failures are tracked.  After *max_rebuild_failures*
        consecutive failures the worker is removed from ``ready_venvs`` so that
        health checks stop attempting (and to prevent silently serving a broken
        venv to the job dispatcher).
        """
        venv_path = self.workers_path / worker_name / ".venv"
        try:
            if venv_path.exists():
                shutil.rmtree(venv_path)
                logger.debug("[%s] Removed old venv", worker_name)

            python_exe = await self._setup_venv(worker_name)
            self.ready_venvs[worker_name] = python_exe
            # Reset failure counter on success.
            self._rebuild_failures.pop(worker_name, None)
            logger.info("✅ [%s] Venv rebuilt successfully", worker_name)
        except Exception as exc:
            failure_count = self._rebuild_failures.get(worker_name, 0) + 1
            self._rebuild_failures[worker_name] = failure_count
            logger.error(
                "❌ [%s] Venv rebuild failed (%d/%d): %s",
                worker_name,
                failure_count,
                self.max_rebuild_failures,
                exc,
            )
            if failure_count >= self.max_rebuild_failures:
                logger.error(
                    "🚨 [%s] Disabling worker: exceeded %d consecutive rebuild failures",
                    worker_name,
                    self.max_rebuild_failures,
                )
                self.ready_venvs.pop(worker_name, None)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log_summary(self) -> None:
        """Log a human-readable summary of all venv setup outcomes."""
        if not self.venv_metadata:
            logger.warning("⚠️  No venvs initialised")
            return

        logger.info(
            "🎯 Venv Manager Summary: %d venv(s) ready",
            len(self.ready_venvs),
        )
        items = list(self.venv_metadata.items())
        for i, (worker_name, meta) in enumerate(items):
            prefix = "  └─" if i == len(items) - 1 else "  ├─"
            status = meta.get("status", "unknown")
            if status == "created":
                logger.info(
                    "%s %s: ✅ created (%.2fs, %.1f MB)",
                    prefix,
                    worker_name,
                    meta.get("creation_time_sec", 0.0),
                    meta.get("size_mb", 0.0),
                )
            elif status == "reused":
                logger.info("%s %s: ⏳ reused", prefix, worker_name)
            else:
                logger.info("%s %s: ❓ %s", prefix, worker_name, status)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _get_dir_size_mb(path: Path) -> float:
        """Return the total size of *path* (recursively) in megabytes."""
        total = 0
        for entry in path.rglob("*"):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
        return total / (1024 * 1024)

    @staticmethod
    async def _run_async(cmd: list, timeout: Optional[int] = None) -> int:
        """
        Run *cmd* asynchronously and return the process exit code.

        Args:
            cmd: Command and arguments list.
            timeout: Optional timeout in seconds.

        Returns:
            Process return code.

        Raises:
            asyncio.TimeoutError: If *timeout* is set and exceeded.
            RuntimeError: If the process exits with a non-zero code (only when
                          timeout is None, i.e. during setup steps).
        """
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        if timeout is not None:
            try:
                return_code = await asyncio.wait_for(proc.wait(), timeout=timeout)
                return return_code
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise

        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            # Limit stderr to 200 chars to avoid leaking sensitive path/env details.
            stderr_snippet = (stderr.decode()[:200] if stderr else "").strip()
            raise RuntimeError(
                f"Command failed (exit {proc.returncode}): "
                f"{Path(cmd[0]).name} – {stderr_snippet}"
            )
        return proc.returncode
