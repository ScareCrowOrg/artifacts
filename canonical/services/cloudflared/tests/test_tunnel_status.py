"""
Tests for tunnel status detection and configuration parsing.

Validates:
- _cloudflared_process_running() returns correct boolean based on pgrep exit code.
- _cloudflared_process_running() handles subprocess exceptions gracefully.
- Config INGRESS_RULES parsing – valid JSON, invalid JSON, non-list JSON.
- Config defaults are sensible.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_service_dir = Path(__file__).resolve().parents[1]
_artifacts_dir = _service_dir.parents[3]
for _p in [str(_service_dir), str(_artifacts_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main  # noqa: E402
import config  # noqa: E402


# ── _cloudflared_process_running ─────────────────────────────────────────────


class TestCloudflaredProcessRunning:
    """Unit tests for main._cloudflared_process_running()."""

    def test_returns_true_on_zero_exit(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("main.subprocess.run", return_value=mock_result) as mock_run:
            result = main._cloudflared_process_running()
        assert result is True
        mock_run.assert_called_once_with(
            ["pgrep", "-x", "cloudflared"],
            capture_output=True,
            timeout=3,
        )

    def test_returns_false_on_nonzero_exit(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("main.subprocess.run", return_value=mock_result):
            result = main._cloudflared_process_running()
        assert result is False

    def test_returns_false_on_file_not_found(self):
        with patch("main.subprocess.run", side_effect=FileNotFoundError):
            result = main._cloudflared_process_running()
        assert result is False

    def test_returns_false_on_timeout(self):
        import subprocess as sp
        with patch("main.subprocess.run", side_effect=sp.TimeoutExpired(cmd="pgrep", timeout=3)):
            result = main._cloudflared_process_running()
        assert result is False

    def test_returns_false_on_os_error(self):
        with patch("main.subprocess.run", side_effect=OSError("no such file")):
            result = main._cloudflared_process_running()
        assert result is False


# ── Config defaults ───────────────────────────────────────────────────────────


class TestConfigDefaults:
    """Verify config module provides expected defaults."""

    def test_tunnel_name_default(self):
        with patch.dict(os.environ, {}, clear=False):
            import importlib
            import config as cfg
            importlib.reload(cfg)
            assert cfg.TUNNEL_NAME == os.getenv("TUNNEL_NAME", "scareverse-tunnel")

    def test_health_port_default(self):
        assert config.HEALTH_PORT == int(os.getenv("HEALTH_PORT", "8000"))

    def test_worker_id_default(self):
        assert config.WORKER_ID == os.getenv("WORKER_ID", "cloudflared")

    def test_heartbeat_interval_default(self):
        assert config.HEARTBEAT_INTERVAL == int(os.getenv("HEARTBEAT_INTERVAL", "20"))

    def test_heartbeat_ttl_default(self):
        assert config.HEARTBEAT_TTL == int(os.getenv("HEARTBEAT_TTL", "60"))


# ── Ingress rules parsing ─────────────────────────────────────────────────────


class TestIngressRulesParsing:
    """Verify INGRESS_RULES env var parsing in config module."""

    def _reload_config_with_env(self, value: str):
        import importlib
        with patch.dict(os.environ, {"INGRESS_RULES": value}):
            import config as cfg
            importlib.reload(cfg)
            return cfg.INGRESS_RULES

    def test_valid_json_array_parsed(self):
        rules = [{"hostname": "api.example.com", "service": "http://backend:5051"}]
        result = self._reload_config_with_env(json.dumps(rules))
        assert result == rules

    def test_empty_array_default(self):
        result = self._reload_config_with_env("[]")
        assert result == []

    def test_invalid_json_returns_empty_list(self):
        result = self._reload_config_with_env("not-valid-json")
        assert result == []

    def test_non_list_json_returns_empty_list(self):
        result = self._reload_config_with_env('{"key": "value"}')
        assert result == []
