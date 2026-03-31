"""
Tests for nginx-unity configuration validation.

Validates:
- Config defaults are sensible and of correct types.
- SIDECAR_PORT, HEARTBEAT_INTERVAL, HEARTBEAT_TTL are integers.
- LOG_LEVEL defaults to 'info'.
- WORKER_ID defaults to 'nginx-unity'.
- Redis config env var overrides are applied correctly.
"""

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_service_dir = Path(__file__).resolve().parents[1]
_artifacts_dir = _service_dir.parents[3]
for _p in [str(_service_dir), str(_artifacts_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config  # noqa: E402


def _reload_config(env_overrides: dict) -> object:
    """Reload config module with temporary env overrides."""
    with patch.dict(os.environ, env_overrides):
        importlib.reload(config)
        return config


class TestConfigDefaults:
    """Verify default values for all config settings."""

    def test_log_level_default(self):
        assert config.LOG_LEVEL == os.getenv("LOG_LEVEL", "info").lower()

    def test_sidecar_port_is_int(self):
        assert isinstance(config.SIDECAR_PORT, int)

    def test_sidecar_port_default(self):
        cfg = _reload_config({})
        assert cfg.SIDECAR_PORT == int(os.getenv("SIDECAR_PORT", "9000"))

    def test_worker_id_default(self):
        cfg = _reload_config({})
        assert cfg.WORKER_ID == os.getenv("WORKER_ID", "nginx-unity")

    def test_heartbeat_interval_is_int(self):
        assert isinstance(config.HEARTBEAT_INTERVAL, int)

    def test_heartbeat_ttl_is_int(self):
        assert isinstance(config.HEARTBEAT_TTL, int)

    def test_redis_port_is_int(self):
        assert isinstance(config.REDIS_L1_PORT, int)

    def test_redis_db_is_int(self):
        assert isinstance(config.REDIS_L1_DB, int)

    def test_no_upstream_check_timeout(self):
        """UPSTREAM_CHECK_TIMEOUT removed – upstream health is now Redis-driven."""
        assert not hasattr(config, "UPSTREAM_CHECK_TIMEOUT")

    def test_no_upstreams_dict(self):
        """UPSTREAMS dict removed – routes registered dynamically via Nginx Unit API."""
        assert not hasattr(config, "UPSTREAMS")

    def test_no_nginx_port(self):
        """NGINX_PORT removed – Nginx Unit port is fixed at 80."""
        assert not hasattr(config, "NGINX_PORT")


class TestConfigOverrides:
    """Verify environment variable overrides are respected."""

    def test_worker_id_override(self):
        cfg = _reload_config({"WORKER_ID": "my-nginx"})
        assert cfg.WORKER_ID == "my-nginx"

    def test_heartbeat_interval_override(self):
        cfg = _reload_config({"HEARTBEAT_INTERVAL": "30"})
        assert cfg.HEARTBEAT_INTERVAL == 30

    def test_heartbeat_ttl_override(self):
        cfg = _reload_config({"HEARTBEAT_TTL": "90"})
        assert cfg.HEARTBEAT_TTL == 90

    def test_redis_host_override(self):
        cfg = _reload_config({"REDIS_L1_HOST": "myredis"})
        assert cfg.REDIS_L1_HOST == "myredis"

    def test_redis_port_override(self):
        cfg = _reload_config({"REDIS_L1_PORT": "6379"})
        assert cfg.REDIS_L1_PORT == 6379

    def test_redis_password_override(self):
        cfg = _reload_config({"REDIS_L1_PASSWORD": "secret123"})
        assert cfg.REDIS_L1_PASSWORD == "secret123"

    def test_sidecar_port_override(self):
        cfg = _reload_config({"SIDECAR_PORT": "9999"})
        assert cfg.SIDECAR_PORT == 9999
