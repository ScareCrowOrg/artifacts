"""
Integration tests for Phase 3 features.

Validates end-to-end integration between:
- GateKeeper startup with eager venv setup.
- VenvManager health-check background loop.
- Metrics collection during dispatch.
- Prometheus export format from metrics.
- JSONFormatter output structure.

These tests mock Redis and HTTP connections but use the real VenvManager,
GateKeeperMetrics, and JSONFormatter implementations.
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------

_gk_dir = Path(__file__).resolve().parents[1]
if str(_gk_dir) not in sys.path:
    sys.path.insert(0, str(_gk_dir))

from json_logger import JSONFormatter
from metrics import GateKeeperMetrics
from venv_manager import VenvManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_worker(workers_path: Path, name: str, has_requirements: bool = True) -> Path:
    worker_dir = workers_path / name
    worker_dir.mkdir(parents=True, exist_ok=True)
    (worker_dir / "main.py").write_text("# stub\n")
    if has_requirements:
        (worker_dir / "requirements.txt").write_text("")
    return worker_dir


def _make_discovered(workers_path: Path, *names: str) -> dict:
    return {name: {"name": name, "path": str(workers_path / name)} for name in names}


# ---------------------------------------------------------------------------
# GateKeeper startup: eager venv creation
# ---------------------------------------------------------------------------


class TestGateKeeperPhase3Integration:
    @pytest.mark.asyncio
    async def test_startup_creates_all_venvs_eagerly(self, tmp_path):
        """
        On startup, VenvManager.setup_all_venvs should create venvs for all
        discovered workers before any job is processed.
        """
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "worker-1")
        _make_worker(workers_path, "worker-2")
        _make_worker(workers_path, "worker-3")
        _make_worker(workers_path, "worker-4")
        discovered = _make_discovered(
            workers_path, "worker-1", "worker-2", "worker-3", "worker-4"
        )

        manager = VenvManager(workers_path)
        start = time.time()
        results = await manager.setup_all_venvs(discovered)
        elapsed = time.time() - start

        assert all(results.values()), f"Some venvs failed: {results}"
        assert elapsed < 60, f"Setup took too long: {elapsed:.1f}s"

        for name in ("worker-1", "worker-2", "worker-3", "worker-4"):
            python_exe = manager.get_venv_python(name)
            assert python_exe is not None
            assert python_exe.exists()

    @pytest.mark.asyncio
    async def test_health_checks_task_runs_and_cancels(self, tmp_path):
        """Background health-check task runs and stops cleanly on cancellation."""
        manager = VenvManager(tmp_path / "workers", health_check_interval=0)

        check_invocations: list = []

        async def _mock_health_checks():
            check_invocations.append(1)

        manager._run_health_checks = _mock_health_checks

        task = asyncio.create_task(manager.start_health_checks())
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(check_invocations) >= 1, "Health checks never ran"

    @pytest.mark.asyncio
    async def test_stale_venv_auto_rebuilt_in_health_check(self, tmp_path):
        """
        When requirements.txt is updated, the health-check run should
        automatically rebuild the stale venv.
        """
        workers_path = tmp_path / "workers"
        worker_dir = _make_worker(workers_path, "stale-w")
        discovered = _make_discovered(workers_path, "stale-w")

        manager = VenvManager(workers_path)
        await manager.setup_all_venvs(discovered)

        # Make requirements.txt newer than the venv directory.
        await asyncio.sleep(0.02)
        (worker_dir / "requirements.txt").touch()

        rebuilt: list = []
        original_rebuild = manager._rebuild_venv

        async def _track(name: str) -> None:
            rebuilt.append(name)
            await original_rebuild(name)

        manager._rebuild_venv = _track
        await manager._run_health_checks()

        assert "stale-w" in rebuilt
        # Venv should still be accessible after rebuild.
        assert manager.get_venv_python("stale-w") is not None


# ---------------------------------------------------------------------------
# Metrics: collection during job dispatch simulation
# ---------------------------------------------------------------------------


class TestMetricsCollection:
    def test_venv_creation_recorded(self):
        """record_venv_creation persists time and size."""
        m = GateKeeperMetrics()
        m.record_venv_creation("rembg", 4.5, 180.0)

        summary = m.get_summary()
        assert "rembg" in summary["venv_stats"]
        assert summary["venv_stats"]["rembg"]["creation_count"] == 1

    def test_job_execution_recorded_success(self):
        """record_job_execution tracks success correctly."""
        m = GateKeeperMetrics()
        m.record_job_execution("REMOTE_REMBG", 1.2, success=True)
        m.record_job_execution("REMOTE_REMBG", 0.9, success=True)
        m.record_job_execution("REMOTE_REMBG", 2.1, success=False)

        summary = m.get_summary()
        js = summary["job_stats"]["REMOTE_REMBG"]
        assert js["successes"] == 2
        assert js["failures"] == 1

    def test_metrics_endpoint_returns_prometheus_format(self):
        """prometheus_export returns valid Prometheus text-format lines."""
        m = GateKeeperMetrics()
        m.record_venv_creation("rembg", 3.0, 150.0)
        m.record_job_execution("REMOTE_REMBG", 1.5, success=True)
        m.record_job_execution("REMOTE_REMBG", 2.0, success=False)

        output = m.prometheus_export()

        # Must have HELP + TYPE comments.
        assert "# HELP" in output
        assert "# TYPE" in output

        # Must have actual metric lines.
        data_lines = [
            ln for ln in output.splitlines() if ln and not ln.startswith("#")
        ]
        assert len(data_lines) > 0

        # Prometheus label format: key="value".
        for line in data_lines:
            assert "{" in line, f"Expected label in: {line}"
            assert "}" in line, f"Expected closing brace in: {line}"

    def test_venv_rebuild_tracked_in_metrics(self):
        """record_venv_rebuild increments the per-worker rebuild counter."""
        m = GateKeeperMetrics()
        m.record_venv_creation("w", 1.0, 50.0)
        m.record_venv_rebuild("w")
        m.record_venv_rebuild("w")

        output = m.prometheus_export()
        assert 'venv_rebuild_count{worker="w"} 2' in output


# ---------------------------------------------------------------------------
# JSON logging format
# ---------------------------------------------------------------------------


class TestJSONLoggingFormat:
    def test_formatter_produces_valid_json(self):
        """JSONFormatter outputs a parseable JSON object per record."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="venv_manager",
            level=logging.INFO,
            pathname="venv_manager.py",
            lineno=42,
            msg="✅ [rembg] Venv ready",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "venv_manager"
        assert "✅ [rembg] Venv ready" in parsed["message"]
        assert "timestamp" in parsed

    def test_formatter_includes_extra_worker_field(self):
        """Extra 'worker' field is propagated to the JSON output."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="venv lifecycle",
            args=(),
            exc_info=None,
        )
        record.worker = "rembg"
        record.action = "created"
        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["worker"] == "rembg"
        assert parsed["action"] == "created"

    def test_formatter_handles_exception_info(self):
        """JSONFormatter includes exc_info when an exception is attached."""
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys as _sys

            exc_info = _sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Something went wrong",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert "exc_info" in parsed
        assert "ValueError" in parsed["exc_info"]

    def test_formatter_missing_extra_fields_not_included(self):
        """Extra fields absent from the record are not present in the JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="plain message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        for field in ("worker", "action", "duration_sec", "size_mb", "job_type"):
            assert field not in parsed, f"Unexpected field '{field}' in output"
