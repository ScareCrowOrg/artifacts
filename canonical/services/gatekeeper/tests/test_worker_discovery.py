"""
Tests for WorkerDiscovery module.

Validates worker scanning, metadata extraction, and logging summary.
"""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from ..worker_discovery import WorkerDiscovery


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_worker_dir(base: Path, name: str, has_requirements: bool = True, has_venv: bool = False) -> Path:
    """Create a minimal valid worker directory for testing."""
    worker_dir = base / name
    worker_dir.mkdir(parents=True)
    (worker_dir / "main.py").write_text("# stub")
    if has_requirements:
        (worker_dir / "requirements.txt").write_text("")
    if has_venv:
        (worker_dir / ".venv" / "bin").mkdir(parents=True)
    return worker_dir


# ---------------------------------------------------------------------------
# Discovery tests
# ---------------------------------------------------------------------------


class TestWorkerDiscoveryDiscover:
    def test_discovers_valid_workers(self, tmp_path):
        """Workers with main.py are discovered correctly."""
        _make_worker_dir(tmp_path, "rembg")
        _make_worker_dir(tmp_path, "ollama-wrapper")

        discovery = WorkerDiscovery(tmp_path)
        result = discovery.discover()

        assert "rembg" in result
        assert "ollama-wrapper" in result
        assert len(result) == 2

    def test_worker_metadata_structure(self, tmp_path):
        """Each discovered worker has the expected metadata fields."""
        _make_worker_dir(tmp_path, "rembg", has_requirements=True, has_venv=False)

        discovery = WorkerDiscovery(tmp_path)
        result = discovery.discover()

        meta = result["rembg"]
        assert meta["name"] == "rembg"
        assert meta["has_requirements"] is True
        assert meta["has_venv"] is False
        assert meta["entry_point"] == "main.py"
        assert "path" in meta
        assert str(tmp_path / "rembg") == meta["path"]

    def test_venv_presence_detected(self, tmp_path):
        """has_venv is True when .venv/ directory exists."""
        _make_worker_dir(tmp_path, "rembg", has_venv=True)

        discovery = WorkerDiscovery(tmp_path)
        result = discovery.discover()

        assert result["rembg"]["has_venv"] is True

    def test_skips_directories_without_main_py(self, tmp_path):
        """Directories missing main.py are silently skipped."""
        (tmp_path / "no-main").mkdir()
        (tmp_path / "no-main" / "worker.py").write_text("")

        _make_worker_dir(tmp_path, "valid-worker")

        discovery = WorkerDiscovery(tmp_path)
        result = discovery.discover()

        assert "no-main" not in result
        assert "valid-worker" in result

    def test_skips_private_directories(self, tmp_path):
        """Directories starting with _ (e.g. __pycache__) are ignored."""
        _make_worker_dir(tmp_path, "__pycache__")
        _make_worker_dir(tmp_path, "_internal")
        _make_worker_dir(tmp_path, "real-worker")

        discovery = WorkerDiscovery(tmp_path)
        result = discovery.discover()

        assert "__pycache__" not in result
        assert "_internal" not in result
        assert "real-worker" in result

    def test_skips_files_in_workers_root(self, tmp_path):
        """Non-directory entries (files) in workers/ are ignored."""
        (tmp_path / "README.md").write_text("# readme")
        (tmp_path / "__init__.py").write_text("")
        _make_worker_dir(tmp_path, "real-worker")

        discovery = WorkerDiscovery(tmp_path)
        result = discovery.discover()

        assert "README.md" not in result
        assert "__init__.py" not in result
        assert "real-worker" in result

    def test_missing_workers_path_returns_empty(self, tmp_path):
        """When workers_path does not exist, discover() returns empty dict."""
        missing_path = tmp_path / "nonexistent"
        discovery = WorkerDiscovery(missing_path)
        result = discovery.discover()

        assert result == {}
        assert discovery.discovered_workers == {}

    def test_empty_workers_directory_returns_empty(self, tmp_path):
        """An empty workers/ directory returns empty dict."""
        discovery = WorkerDiscovery(tmp_path)
        result = discovery.discover()

        assert result == {}

    def test_discovered_workers_stored_on_instance(self, tmp_path):
        """discover() stores result in self.discovered_workers."""
        _make_worker_dir(tmp_path, "rembg")

        discovery = WorkerDiscovery(tmp_path)
        discovery.discover()

        assert "rembg" in discovery.discovered_workers

    def test_no_requirements_flagged_correctly(self, tmp_path):
        """has_requirements is False when requirements.txt is absent."""
        _make_worker_dir(tmp_path, "simple-worker", has_requirements=False)

        discovery = WorkerDiscovery(tmp_path)
        result = discovery.discover()

        assert result["simple-worker"]["has_requirements"] is False


# ---------------------------------------------------------------------------
# Status query tests
# ---------------------------------------------------------------------------


class TestWorkerDiscoveryStatus:
    def test_get_status_returns_metadata_for_known_worker(self, tmp_path):
        """get_status() returns full metadata dict for a discovered worker."""
        _make_worker_dir(tmp_path, "rembg")

        discovery = WorkerDiscovery(tmp_path)
        discovery.discover()
        status = discovery.get_status("rembg")

        assert status is not None
        assert status["name"] == "rembg"

    def test_get_status_returns_none_for_unknown_worker(self, tmp_path):
        """get_status() returns None for a worker not in discovered set."""
        discovery = WorkerDiscovery(tmp_path)
        discovery.discover()

        assert discovery.get_status("nonexistent") is None

    def test_is_available_true_for_discovered(self, tmp_path):
        """is_available() returns True for a discovered worker."""
        _make_worker_dir(tmp_path, "rembg")

        discovery = WorkerDiscovery(tmp_path)
        discovery.discover()

        assert discovery.is_available("rembg") is True

    def test_is_available_false_for_undiscovered(self, tmp_path):
        """is_available() returns False for a non-discovered worker."""
        discovery = WorkerDiscovery(tmp_path)
        discovery.discover()

        assert discovery.is_available("unknown-worker") is False


# ---------------------------------------------------------------------------
# Logging tests
# ---------------------------------------------------------------------------


class TestWorkerDiscoveryLogSummary:
    def test_log_summary_emits_warning_when_empty(self, tmp_path, caplog):
        """log_summary() emits a warning when no workers found."""
        discovery = WorkerDiscovery(tmp_path)
        discovery.discover()

        with caplog.at_level(logging.WARNING):
            discovery.log_summary()

        assert any("No workers discovered" in r.message for r in caplog.records)

    def test_log_summary_emits_info_for_each_worker(self, tmp_path, caplog):
        """log_summary() emits an info log line for each discovered worker."""
        _make_worker_dir(tmp_path, "rembg")
        _make_worker_dir(tmp_path, "ollama-wrapper")

        discovery = WorkerDiscovery(tmp_path)
        discovery.discover()

        with caplog.at_level(logging.INFO):
            discovery.log_summary()

        messages = " ".join(r.message for r in caplog.records)
        assert "rembg" in messages
        assert "ollama-wrapper" in messages

    def test_log_summary_shows_venv_status(self, tmp_path, caplog):
        """log_summary() indicates whether .venv is present or pending."""
        _make_worker_dir(tmp_path, "rembg-with-venv", has_venv=True)
        _make_worker_dir(tmp_path, "rembg-no-venv", has_venv=False)

        discovery = WorkerDiscovery(tmp_path)
        discovery.discover()

        with caplog.at_level(logging.INFO):
            discovery.log_summary()

        messages = " ".join(r.message for r in caplog.records)
        assert "ready" in messages or "pending" in messages
