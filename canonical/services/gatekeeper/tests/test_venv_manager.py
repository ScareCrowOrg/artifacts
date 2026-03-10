"""
Unit tests for VenvManager (Phase 3).

Validates:
- Eager setup creates venvs for all discovered workers.
- Existing venvs are reused (not recreated).
- Venv verification correctly identifies functional / broken venvs.
- Health checks detect requirements.txt staleness and trigger rebuild.
- Health checks detect corrupted venvs and trigger rebuild.
- _rebuild_venv removes and recreates the venv.
- Metadata is tracked (status, creation_time_sec, size_mb).
- Metrics are recorded when a metrics instance is attached.
- log_summary emits correct messages.

These tests create real subprocesses using the system Python.
Requires pytest-asyncio.
"""

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import helpers (Docker path / local path)
# ---------------------------------------------------------------------------

try:
    from venv_manager import VenvManager
except ImportError:
    _gk_dir = Path(__file__).resolve().parents[1]
    if str(_gk_dir) not in sys.path:
        sys.path.insert(0, str(_gk_dir))
    from venv_manager import VenvManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_worker(
    workers_path: Path,
    name: str,
    has_requirements: bool = True,
    req_content: str = "",
) -> Path:
    """Create a minimal worker directory."""
    worker_dir = workers_path / name
    worker_dir.mkdir(parents=True, exist_ok=True)
    (worker_dir / "main.py").write_text("# stub\n")
    if has_requirements:
        (worker_dir / "requirements.txt").write_text(req_content)
    return worker_dir


def _make_discovered(workers_path: Path, *names: str) -> dict:
    """Build a minimal WorkerDiscovery-style dict for setup_all_venvs."""
    return {name: {"name": name, "path": str(workers_path / name)} for name in names}


# ---------------------------------------------------------------------------
# Eager setup
# ---------------------------------------------------------------------------


class TestEagerSetup:
    @pytest.mark.asyncio
    async def test_setup_creates_venv_for_all_workers(self, tmp_path):
        """setup_all_venvs creates a .venv for every discovered worker."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "worker-a")
        _make_worker(workers_path, "worker-b")
        discovered = _make_discovered(workers_path, "worker-a", "worker-b")

        manager = VenvManager(workers_path)
        results = await manager.setup_all_venvs(discovered)

        assert results == {"worker-a": True, "worker-b": True}
        assert (workers_path / "worker-a" / ".venv").exists()
        assert (workers_path / "worker-b" / ".venv").exists()

    @pytest.mark.asyncio
    async def test_setup_populates_ready_venvs(self, tmp_path):
        """After setup_all_venvs, get_venv_python returns a valid path."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "my-worker")
        discovered = _make_discovered(workers_path, "my-worker")

        manager = VenvManager(workers_path)
        await manager.setup_all_venvs(discovered)

        python_exe = manager.get_venv_python("my-worker")
        assert python_exe is not None
        assert python_exe.exists()

    @pytest.mark.asyncio
    async def test_setup_reuses_existing_venv(self, tmp_path):
        """If .venv already exists, setup_all_venvs reuses it (metadata status=reused)."""
        workers_path = tmp_path / "workers"
        worker_dir = _make_worker(workers_path, "pre-worker")

        # Pre-create real venv
        venv_dir = worker_dir / ".venv"
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "venv",
            str(venv_dir),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        mtime_before = venv_dir.stat().st_mtime

        discovered = _make_discovered(workers_path, "pre-worker")
        manager = VenvManager(workers_path)
        results = await manager.setup_all_venvs(discovered)

        mtime_after = venv_dir.stat().st_mtime
        assert results["pre-worker"] is True
        assert mtime_before == mtime_after  # Not recreated
        assert manager.venv_metadata["pre-worker"]["status"] == "reused"

    @pytest.mark.asyncio
    async def test_setup_returns_false_for_failed_worker(self, tmp_path):
        """If venv creation fails, setup_all_venvs returns False for that worker."""
        workers_path = tmp_path / "workers"
        # Create worker dir but no main.py (so it exists, but we mock _setup_venv to fail)
        _make_worker(workers_path, "bad-worker")
        discovered = _make_discovered(workers_path, "bad-worker")

        manager = VenvManager(workers_path)
        with patch.object(
            manager, "_setup_venv", side_effect=RuntimeError("simulated failure")
        ):
            results = await manager.setup_all_venvs(discovered)

        assert results["bad-worker"] is False
        assert "bad-worker" not in manager.ready_venvs

    @pytest.mark.asyncio
    async def test_setup_records_metadata_on_creation(self, tmp_path):
        """Created venvs have status, creation_time_sec, and size_mb in metadata."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "meta-worker")
        discovered = _make_discovered(workers_path, "meta-worker")

        manager = VenvManager(workers_path)
        await manager.setup_all_venvs(discovered)

        meta = manager.venv_metadata["meta-worker"]
        assert meta["status"] == "created"
        assert meta["creation_time_sec"] >= 0
        assert meta["size_mb"] >= 0

    @pytest.mark.asyncio
    async def test_setup_no_requirements_txt(self, tmp_path):
        """setup_all_venvs succeeds when requirements.txt is absent."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "no-req", has_requirements=False)
        discovered = _make_discovered(workers_path, "no-req")

        manager = VenvManager(workers_path)
        results = await manager.setup_all_venvs(discovered)

        assert results["no-req"] is True

    @pytest.mark.asyncio
    async def test_get_venv_python_returns_none_for_unknown(self, tmp_path):
        """get_venv_python returns None for a worker not yet set up."""
        manager = VenvManager(tmp_path / "workers")
        assert manager.get_venv_python("ghost-worker") is None


# ---------------------------------------------------------------------------
# Venv verification
# ---------------------------------------------------------------------------


class TestVenvVerification:
    @pytest.mark.asyncio
    async def test_verify_functional_venv_returns_true(self, tmp_path):
        """_verify_venv returns True for a working Python executable."""
        workers_path = tmp_path / "workers"
        worker_dir = _make_worker(workers_path, "verify-worker")
        venv_dir = worker_dir / ".venv"
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "venv",
            str(venv_dir),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        python_exe = venv_dir / "bin" / "python"

        manager = VenvManager(workers_path)
        result = await manager._verify_venv("verify-worker", python_exe)

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_nonexistent_executable_returns_false(self, tmp_path):
        """_verify_venv returns False when python_exe does not exist."""
        manager = VenvManager(tmp_path / "workers")
        fake_exe = tmp_path / "nonexistent" / "python"

        result = await manager._verify_venv("ghost", fake_exe)

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_timeout_returns_false(self, tmp_path):
        """_verify_venv returns False when the check times out."""
        workers_path = tmp_path / "workers"
        manager = VenvManager(workers_path)

        # Patch _run_async to raise TimeoutError
        with patch.object(
            VenvManager,
            "_run_async",
            new_callable=AsyncMock,
            side_effect=asyncio.TimeoutError,
        ):
            result = await manager._verify_venv("w", Path("/fake/python"))

        assert result is False


# ---------------------------------------------------------------------------
# Health checks – staleness detection
# ---------------------------------------------------------------------------


class TestHealthChecks:
    @pytest.mark.asyncio
    async def test_stale_requirements_triggers_rebuild(self, tmp_path):
        """Health check rebuilds venv when requirements.txt is newer than .venv."""
        workers_path = tmp_path / "workers"
        worker_dir = _make_worker(workers_path, "stale-worker")

        manager = VenvManager(workers_path)
        discovered = _make_discovered(workers_path, "stale-worker")
        await manager.setup_all_venvs(discovered)

        # Touch requirements.txt to make it newer than the venv.
        req_file = worker_dir / "requirements.txt"
        await asyncio.sleep(0.02)
        req_file.touch()

        rebuild_called = []
        original_rebuild = manager._rebuild_venv

        async def _track_rebuild(name):
            rebuild_called.append(name)
            await original_rebuild(name)

        manager._rebuild_venv = _track_rebuild
        await manager._run_health_checks()

        assert "stale-worker" in rebuild_called

    @pytest.mark.asyncio
    async def test_fresh_requirements_no_rebuild(self, tmp_path):
        """Health check does NOT rebuild when requirements.txt is unchanged."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "fresh-worker")

        manager = VenvManager(workers_path)
        discovered = _make_discovered(workers_path, "fresh-worker")
        await manager.setup_all_venvs(discovered)

        rebuild_called = []

        async def _track_rebuild(name):
            rebuild_called.append(name)

        manager._rebuild_venv = _track_rebuild
        # Patch verify to return True so no corruption detected.
        with patch.object(
            manager, "_verify_venv", new_callable=AsyncMock, return_value=True
        ):
            await manager._run_health_checks()

        assert rebuild_called == []

    @pytest.mark.asyncio
    async def test_corrupted_venv_triggers_rebuild(self, tmp_path):
        """Health check rebuilds venv when Python executable verification fails."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "corrupt-worker", has_requirements=False)

        manager = VenvManager(workers_path)
        discovered = _make_discovered(workers_path, "corrupt-worker")
        await manager.setup_all_venvs(discovered)

        rebuild_called = []
        original_rebuild = manager._rebuild_venv

        async def _track_rebuild(name):
            rebuild_called.append(name)
            await original_rebuild(name)

        manager._rebuild_venv = _track_rebuild
        with patch.object(
            manager, "_verify_venv", new_callable=AsyncMock, return_value=False
        ):
            await manager._run_health_checks()

        assert "corrupt-worker" in rebuild_called

    @pytest.mark.asyncio
    async def test_health_check_loop_runs_periodically(self, tmp_path):
        """start_health_checks calls _run_health_checks at least once then cancels."""
        manager = VenvManager(tmp_path / "workers", health_check_interval=0)

        check_count = []

        async def _mock_checks():
            check_count.append(1)

        manager._run_health_checks = _mock_checks

        task = asyncio.create_task(manager.start_health_checks())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(check_count) >= 1


# ---------------------------------------------------------------------------
# Rebuild
# ---------------------------------------------------------------------------


class TestRebuildVenv:
    @pytest.mark.asyncio
    async def test_rebuild_removes_and_recreates(self, tmp_path):
        """_rebuild_venv removes old .venv and creates a fresh one."""
        workers_path = tmp_path / "workers"
        worker_dir = _make_worker(workers_path, "rebuild-worker")

        manager = VenvManager(workers_path)
        discovered = _make_discovered(workers_path, "rebuild-worker")
        await manager.setup_all_venvs(discovered)

        venv_dir = worker_dir / ".venv"
        assert venv_dir.exists()

        await manager._rebuild_venv("rebuild-worker")

        assert venv_dir.exists()
        assert manager.get_venv_python("rebuild-worker") is not None

    @pytest.mark.asyncio
    async def test_rebuild_updates_ready_venvs(self, tmp_path):
        """After _rebuild_venv, ready_venvs is updated with new python path."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "upd-worker")

        manager = VenvManager(workers_path)
        discovered = _make_discovered(workers_path, "upd-worker")
        await manager.setup_all_venvs(discovered)

        old_exe = manager.ready_venvs["upd-worker"]
        await manager._rebuild_venv("upd-worker")
        new_exe = manager.ready_venvs["upd-worker"]

        # Path is the same string but venv was rebuilt.
        assert new_exe.exists()
        assert str(new_exe) == str(old_exe)

    @pytest.mark.asyncio
    async def test_rebuild_failure_counter_increments(self, tmp_path):
        """Each consecutive rebuild failure increments the failure counter."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "fail-worker")
        discovered = _make_discovered(workers_path, "fail-worker")

        manager = VenvManager(workers_path, max_rebuild_failures=3)
        await manager.setup_all_venvs(discovered)

        with patch.object(
            manager, "_setup_venv", side_effect=RuntimeError("build error")
        ):
            await manager._rebuild_venv("fail-worker")
            await manager._rebuild_venv("fail-worker")

        assert manager._rebuild_failures["fail-worker"] == 2

    @pytest.mark.asyncio
    async def test_rebuild_disables_worker_after_max_failures(self, tmp_path):
        """Worker is removed from ready_venvs after max_rebuild_failures."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "max-fail-worker")
        discovered = _make_discovered(workers_path, "max-fail-worker")

        manager = VenvManager(workers_path, max_rebuild_failures=2)
        await manager.setup_all_venvs(discovered)

        with patch.object(
            manager, "_setup_venv", side_effect=RuntimeError("build error")
        ):
            await manager._rebuild_venv("max-fail-worker")
            await manager._rebuild_venv("max-fail-worker")

        # Worker should be removed from ready_venvs after max failures.
        assert manager.get_venv_python("max-fail-worker") is None

    @pytest.mark.asyncio
    async def test_rebuild_failure_counter_resets_on_success(self, tmp_path):
        """Consecutive failure counter resets after a successful rebuild."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "reset-worker")
        discovered = _make_discovered(workers_path, "reset-worker")

        manager = VenvManager(workers_path, max_rebuild_failures=5)
        await manager.setup_all_venvs(discovered)

        # Simulate one failure.
        with patch.object(
            manager, "_setup_venv", side_effect=RuntimeError("build error")
        ):
            await manager._rebuild_venv("reset-worker")

        assert manager._rebuild_failures.get("reset-worker", 0) == 1

        # Successful rebuild clears the counter.
        await manager._rebuild_venv("reset-worker")
        assert manager._rebuild_failures.get("reset-worker", 0) == 0


# ---------------------------------------------------------------------------
# Metrics integration
# ---------------------------------------------------------------------------


class TestVenvMetricsIntegration:
    @pytest.mark.asyncio
    async def test_metrics_recorded_on_venv_creation(self, tmp_path):
        """VenvManager calls metrics.record_venv_creation on new venv."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "metrics-worker")
        discovered = _make_discovered(workers_path, "metrics-worker")

        mock_metrics = MagicMock()
        manager = VenvManager(workers_path, metrics=mock_metrics)
        await manager.setup_all_venvs(discovered)

        mock_metrics.record_venv_creation.assert_called_once()
        call_args = mock_metrics.record_venv_creation.call_args
        assert call_args[0][0] == "metrics-worker"
        assert call_args[0][1] >= 0  # creation_time_sec
        assert call_args[0][2] >= 0  # size_mb

    @pytest.mark.asyncio
    async def test_metrics_not_recorded_on_reuse(self, tmp_path):
        """VenvManager does NOT call metrics.record_venv_creation on reuse."""
        workers_path = tmp_path / "workers"
        worker_dir = _make_worker(workers_path, "reuse-metrics")

        # Pre-create venv
        venv_dir = worker_dir / ".venv"
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "venv",
            str(venv_dir),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()

        mock_metrics = MagicMock()
        manager = VenvManager(workers_path, metrics=mock_metrics)
        discovered = _make_discovered(workers_path, "reuse-metrics")
        await manager.setup_all_venvs(discovered)

        mock_metrics.record_venv_creation.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_metrics_attaches_instance(self, tmp_path):
        """set_metrics attaches a GateKeeperMetrics instance after construction."""
        manager = VenvManager(tmp_path / "workers")
        mock_metrics = MagicMock()
        manager.set_metrics(mock_metrics)
        assert manager.metrics is mock_metrics


# ---------------------------------------------------------------------------
# log_summary
# ---------------------------------------------------------------------------


class TestLogSummary:
    @pytest.mark.asyncio
    async def test_log_summary_created(self, tmp_path, caplog):
        """log_summary logs 'created' line for a freshly made venv."""
        import logging

        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "sum-worker")
        discovered = _make_discovered(workers_path, "sum-worker")

        manager = VenvManager(workers_path)
        await manager.setup_all_venvs(discovered)

        with caplog.at_level(logging.INFO, logger="venv_manager"):
            manager.log_summary()

        assert any("sum-worker" in r.message for r in caplog.records)

    def test_log_summary_no_metadata_warns(self, tmp_path, caplog):
        """log_summary warns when no venvs have been initialised."""
        import logging

        manager = VenvManager(tmp_path / "workers")
        with caplog.at_level(logging.WARNING, logger="venv_manager"):
            manager.log_summary()

        assert any("No venvs" in r.message for r in caplog.records)
