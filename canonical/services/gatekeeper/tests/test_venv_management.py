"""
Tests for venv auto-setup and management in WorkerExecutor.

Validates:
- .venv is created on first execution if missing.
- .venv is reused (not recreated) on subsequent calls.
- Cache invalidation forces re-check on next call.
- Missing requirements.txt is handled gracefully.
- Venv cache is keyed per worker name.

These tests create real subprocesses using the system Python.
Requires pytest-asyncio.
"""

import asyncio
import sys
from pathlib import Path

import pytest

# Import WorkerExecutor – works both in Docker (PYTHONPATH=/app/artifacts)
# and locally (path resolved relative to this file).
try:
    from canonical.shared.worker_executor import WorkerExecutor
except ImportError:
    _canonical_parent = Path(__file__).resolve().parents[4]
    if str(_canonical_parent) not in sys.path:
        sys.path.insert(0, str(_canonical_parent))
    from canonical.shared.worker_executor import WorkerExecutor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_worker(workers_path: Path, name: str, has_requirements: bool = True) -> Path:
    """Create a minimal worker directory for venv tests."""
    worker_dir = workers_path / name
    worker_dir.mkdir(parents=True)
    (worker_dir / "main.py").write_text("# stub entry point\n")
    if has_requirements:
        # Empty requirements – pip install will be a no-op (fast)
        (worker_dir / "requirements.txt").write_text("")
    return worker_dir


# ---------------------------------------------------------------------------
# Venv creation
# ---------------------------------------------------------------------------


class TestVenvAutoSetup:
    @pytest.mark.asyncio
    async def test_venv_created_when_missing(self, tmp_path):
        """_ensure_venv creates .venv when it does not exist."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "test-worker")

        executor = WorkerExecutor(workers_path=str(workers_path))
        assert "test-worker" not in executor._venv_ready

        python_exe = await executor._ensure_venv("test-worker")

        assert python_exe.exists(), f"Expected python executable at {python_exe}"
        assert (workers_path / "test-worker" / ".venv").exists()

    @pytest.mark.asyncio
    async def test_venv_python_executable_is_valid(self, tmp_path):
        """The returned python executable can run -c 'print(1)'."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "exec-worker")

        executor = WorkerExecutor(workers_path=str(workers_path))
        python_exe = await executor._ensure_venv("exec-worker")

        proc = await asyncio.create_subprocess_exec(
            str(python_exe), "-c", "print('venv ok')",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        assert proc.returncode == 0
        assert b"venv ok" in stdout

    @pytest.mark.asyncio
    async def test_no_requirements_txt_does_not_crash(self, tmp_path):
        """_ensure_venv succeeds even when requirements.txt is absent."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "no-req-worker", has_requirements=False)

        executor = WorkerExecutor(workers_path=str(workers_path))
        # Should not raise
        python_exe = await executor._ensure_venv("no-req-worker")

        assert python_exe.exists()


# ---------------------------------------------------------------------------
# Venv reuse
# ---------------------------------------------------------------------------


class TestVenvReuse:
    @pytest.mark.asyncio
    async def test_venv_reused_on_second_call(self, tmp_path):
        """_ensure_venv returns same path and does NOT recreate .venv."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "reuse-worker")

        executor = WorkerExecutor(workers_path=str(workers_path))

        # First call – creates venv
        python_exe1 = await executor._ensure_venv("reuse-worker")
        mtime1 = (workers_path / "reuse-worker" / ".venv").stat().st_mtime

        # Second call – must reuse
        await asyncio.sleep(0.05)  # ensure mtime would change if recreated
        python_exe2 = await executor._ensure_venv("reuse-worker")
        mtime2 = (workers_path / "reuse-worker" / ".venv").stat().st_mtime

        assert python_exe1 == python_exe2
        assert mtime1 == mtime2, "Venv was recreated on second call (mtime changed)"

    @pytest.mark.asyncio
    async def test_venv_cached_in_ready_dict(self, tmp_path):
        """After _ensure_venv, worker name appears in _venv_ready cache."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "cached-worker")

        executor = WorkerExecutor(workers_path=str(workers_path))
        await executor._ensure_venv("cached-worker")

        assert "cached-worker" in executor._venv_ready

    @pytest.mark.asyncio
    async def test_existing_venv_recognised_without_recreation(self, tmp_path):
        """If .venv/bin/python already exists, _ensure_venv uses it directly."""
        workers_path = tmp_path / "workers"
        worker_dir = _make_worker(workers_path, "pre-venv-worker")

        # Pre-create a real .venv so the executor finds it on first call
        venv_dir = worker_dir / ".venv"
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "venv", str(venv_dir),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()

        executor = WorkerExecutor(workers_path=str(workers_path))
        mtime_before = venv_dir.stat().st_mtime
        python_exe = await executor._ensure_venv("pre-venv-worker")
        mtime_after = venv_dir.stat().st_mtime

        # Mtime should be unchanged (venv not recreated)
        assert mtime_before == mtime_after
        assert python_exe.exists()


# ---------------------------------------------------------------------------
# Cache invalidation
# ---------------------------------------------------------------------------


class TestVenvCacheInvalidation:
    @pytest.mark.asyncio
    async def test_invalidate_specific_worker(self, tmp_path):
        """invalidate_venv_cache(name) removes only that worker from cache."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "worker-a")
        _make_worker(workers_path, "worker-b")

        executor = WorkerExecutor(workers_path=str(workers_path))
        await executor._ensure_venv("worker-a")
        await executor._ensure_venv("worker-b")

        executor.invalidate_venv_cache("worker-a")

        assert "worker-a" not in executor._venv_ready
        assert "worker-b" in executor._venv_ready

    @pytest.mark.asyncio
    async def test_invalidate_all_workers(self, tmp_path):
        """invalidate_venv_cache() with no argument clears entire cache."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "worker-a")
        _make_worker(workers_path, "worker-b")

        executor = WorkerExecutor(workers_path=str(workers_path))
        await executor._ensure_venv("worker-a")
        await executor._ensure_venv("worker-b")

        executor.invalidate_venv_cache()

        assert executor._venv_ready == {}

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_worker_does_not_raise(self, tmp_path):
        """invalidate_venv_cache(unknown) is a no-op and does not raise."""
        executor = WorkerExecutor(workers_path=str(tmp_path))
        # Should not raise KeyError
        executor.invalidate_venv_cache("does-not-exist")


# ---------------------------------------------------------------------------
# Per-worker isolation
# ---------------------------------------------------------------------------


class TestVenvIsolation:
    @pytest.mark.asyncio
    async def test_each_worker_gets_its_own_venv(self, tmp_path):
        """Each worker has an independent .venv in its own directory."""
        workers_path = tmp_path / "workers"
        _make_worker(workers_path, "worker-x")
        _make_worker(workers_path, "worker-y")

        executor = WorkerExecutor(workers_path=str(workers_path))
        exe_x = await executor._ensure_venv("worker-x")
        exe_y = await executor._ensure_venv("worker-y")

        assert exe_x != exe_y
        assert "worker-x" in str(exe_x)
        assert "worker-y" in str(exe_y)
