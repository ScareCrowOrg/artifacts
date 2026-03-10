"""
Integration tests for Rembg subprocess execution via WorkerExecutor.

These tests validate the subprocess dispatch contract, stdin/stdout JSON
communication, and error handling paths **without** requiring the real
rembg / ONNX libraries to be installed.

A lightweight ``fake_main.py`` is written to a temporary directory so
that WorkerExecutor can call it as a real subprocess.

Requires pytest-asyncio.
"""

import asyncio
import json
import sys
import textwrap
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
# Minimal 1×1 PNG base64 (no PIL required)
# ---------------------------------------------------------------------------

_MINIMAL_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


# ---------------------------------------------------------------------------
# Helpers – fake worker scripts
# ---------------------------------------------------------------------------


def _write_fake_worker(worker_dir: Path, script: str) -> None:
    """Write a fake main.py into worker_dir for use as a subprocess."""
    (worker_dir / "main.py").write_text(
        f"#!{sys.executable}\n" + textwrap.dedent(script)
    )
    # No requirements.txt → WorkerExecutor will skip pip install
    # .venv is NOT created; WorkerExecutor._ensure_venv creates it lazily


def _write_echo_worker(worker_dir: Path) -> None:
    """
    Worker that reads JSON stdin and echoes back a success result.
    No external dependencies; uses only stdlib.
    """
    _write_fake_worker(
        worker_dir,
        """\
        import json, sys
        data = json.loads(sys.stdin.read())
        print(json.dumps({"success": True, "result": {"job_id": data["job_id"], "echoed": True}}))
        sys.exit(0)
        """,
    )


def _write_error_worker(worker_dir: Path) -> None:
    """Worker that always signals failure in its JSON output."""
    _write_fake_worker(
        worker_dir,
        """\
        import json, sys
        print(json.dumps({"success": False, "error": "intentional worker failure"}))
        sys.exit(0)
        """,
    )


def _write_crash_worker(worker_dir: Path) -> None:
    """Worker that crashes (non-zero exit, no stdout)."""
    _write_fake_worker(
        worker_dir,
        """\
        import sys
        sys.exit(2)
        """,
    )


def _write_slow_worker(worker_dir: Path) -> None:
    """Worker that sleeps forever – used to test timeout handling."""
    _write_fake_worker(
        worker_dir,
        """\
        import time, sys
        time.sleep(999)
        """,
    )


def _write_invalid_json_worker(worker_dir: Path) -> None:
    """Worker that outputs invalid JSON."""
    _write_fake_worker(
        worker_dir,
        """\
        import sys
        print("this is not json {{{")
        sys.exit(0)
        """,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workers_root(tmp_path) -> Path:
    """Temporary workers/ root with an echo worker pre-installed."""
    workers_path = tmp_path / "workers"
    workers_path.mkdir()
    return workers_path


def _job_type_config(worker_name: str, timeout: float = 10.0) -> dict:
    return {
        "execution_model": "subprocess",
        "worker": {"path": f"artifacts/canonical/workers/{worker_name}"},
        "configuration": {"timeout_seconds": timeout},
    }


# ---------------------------------------------------------------------------
# Echo worker – success path
# ---------------------------------------------------------------------------


class TestSubprocessSuccessPath:
    @pytest.mark.asyncio
    async def test_echo_worker_returns_result(self, workers_root):
        """WorkerExecutor executes subprocess worker and returns stdout result."""
        worker_dir = workers_root / "echo-worker"
        worker_dir.mkdir()
        _write_echo_worker(worker_dir)

        executor = WorkerExecutor(workers_path=str(workers_root))
        # Provide python executable directly so no venv setup needed
        executor._venv_ready["echo-worker"] = Path(sys.executable)

        result = await executor.execute(
            job_type="echo_job",
            job_id="test-echo-001",
            input_data={"image_base64": _MINIMAL_PNG_B64},
            worker_config=_job_type_config("echo-worker"),
        )

        assert isinstance(result, dict)
        assert result.get("job_id") == "test-echo-001"
        assert result.get("echoed") is True

    @pytest.mark.asyncio
    async def test_input_data_forwarded_via_stdin(self, workers_root):
        """Arbitrary input_data is forwarded to worker stdin as JSON."""
        worker_dir = workers_root / "inspect-worker"
        worker_dir.mkdir()
        _write_fake_worker(
            worker_dir,
            """\
            import json, sys
            data = json.loads(sys.stdin.read())
            # Return the received input_data so the test can inspect it
            print(json.dumps({"success": True, "result": {"received": data["input_data"]}}))
            sys.exit(0)
            """,
        )

        executor = WorkerExecutor(workers_path=str(workers_root))
        executor._venv_ready["inspect-worker"] = Path(sys.executable)

        payload = {"custom_key": "custom_value", "number": 42}
        result = await executor.execute(
            job_type="inspect_job",
            job_id="test-inspect-001",
            input_data=payload,
            worker_config=_job_type_config("inspect-worker"),
        )

        assert result["received"]["custom_key"] == "custom_value"
        assert result["received"]["number"] == 42


# ---------------------------------------------------------------------------
# Error handling paths
# ---------------------------------------------------------------------------


class TestSubprocessErrorHandling:
    @pytest.mark.asyncio
    async def test_worker_failure_raises_value_error(self, workers_root):
        """Worker signalling failure (success=false) raises ValueError."""
        worker_dir = workers_root / "error-worker"
        worker_dir.mkdir()
        _write_error_worker(worker_dir)

        executor = WorkerExecutor(workers_path=str(workers_root))
        executor._venv_ready["error-worker"] = Path(sys.executable)

        with pytest.raises(ValueError, match="intentional worker failure"):
            await executor.execute(
                job_type="error_job",
                job_id="test-error-001",
                input_data={},
                worker_config=_job_type_config("error-worker"),
            )

    @pytest.mark.asyncio
    async def test_worker_crash_raises_value_error(self, workers_root):
        """Worker crash (no stdout) raises ValueError."""
        worker_dir = workers_root / "crash-worker"
        worker_dir.mkdir()
        _write_crash_worker(worker_dir)

        executor = WorkerExecutor(workers_path=str(workers_root))
        executor._venv_ready["crash-worker"] = Path(sys.executable)

        with pytest.raises((ValueError, Exception)):
            await executor.execute(
                job_type="crash_job",
                job_id="test-crash-001",
                input_data={},
                worker_config=_job_type_config("crash-worker"),
            )

    @pytest.mark.asyncio
    async def test_worker_timeout_raises_timeout_error(self, workers_root):
        """Worker exceeding timeout raises TimeoutError."""
        worker_dir = workers_root / "slow-worker"
        worker_dir.mkdir()
        _write_slow_worker(worker_dir)

        executor = WorkerExecutor(workers_path=str(workers_root))
        executor._venv_ready["slow-worker"] = Path(sys.executable)

        with pytest.raises(TimeoutError):
            await executor.execute(
                job_type="slow_job",
                job_id="test-timeout-001",
                input_data={},
                worker_config=_job_type_config("slow-worker", timeout=0.1),
            )

    @pytest.mark.asyncio
    async def test_invalid_json_output_raises_value_error(self, workers_root):
        """Worker outputting invalid JSON raises ValueError."""
        worker_dir = workers_root / "bad-json-worker"
        worker_dir.mkdir()
        _write_invalid_json_worker(worker_dir)

        executor = WorkerExecutor(workers_path=str(workers_root))
        executor._venv_ready["bad-json-worker"] = Path(sys.executable)

        with pytest.raises(ValueError, match="invalid JSON"):
            await executor.execute(
                job_type="bad_json_job",
                job_id="test-bad-json-001",
                input_data={},
                worker_config=_job_type_config("bad-json-worker"),
            )


# ---------------------------------------------------------------------------
# Rembg-specific contract tests (mocked worker, no rembg lib needed)
# ---------------------------------------------------------------------------


class TestRembgSubprocessContract:
    @pytest.mark.asyncio
    async def test_rembg_job_type_fields_forwarded(self, workers_root):
        """job_id and job_type fields are correctly forwarded to rembg worker stdin."""
        worker_dir = workers_root / "rembg"
        worker_dir.mkdir()
        _write_fake_worker(
            worker_dir,
            """\
            import json, sys
            data = json.loads(sys.stdin.read())
            assert data["job_type"] == "rembg_removebackground", f"bad job_type: {data['job_type']}"
            assert data["job_id"] == "rembg-test-001"
            print(json.dumps({"success": True, "result": {"image_base64": "abc123"}}))
            sys.exit(0)
            """,
        )

        executor = WorkerExecutor(workers_path=str(workers_root))
        executor._venv_ready["rembg"] = Path(sys.executable)

        result = await executor.execute(
            job_type="rembg_removebackground",
            job_id="rembg-test-001",
            input_data={"image_base64": _MINIMAL_PNG_B64},
            worker_config=_job_type_config("rembg"),
        )

        assert result.get("image_base64") == "abc123"

    @pytest.mark.asyncio
    async def test_rembg_result_structure(self, workers_root):
        """A successful rembg worker returns a dict with image_base64 key."""
        worker_dir = workers_root / "rembg"
        worker_dir.mkdir()
        _write_fake_worker(
            worker_dir,
            """\
            import json, sys
            sys.stdin.read()  # consume stdin
            print(json.dumps({"success": True, "result": {"image_base64": "RESULT_B64"}}))
            sys.exit(0)
            """,
        )

        executor = WorkerExecutor(workers_path=str(workers_root))
        executor._venv_ready["rembg"] = Path(sys.executable)

        result = await executor.execute(
            job_type="rembg_removebackground",
            job_id="rembg-test-002",
            input_data={"image_base64": _MINIMAL_PNG_B64},
            worker_config=_job_type_config("rembg"),
        )

        assert "image_base64" in result
        assert result["image_base64"] == "RESULT_B64"
