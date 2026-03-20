"""
Tests for nginx-unity configuration validation.

Validates:
- Config defaults are sensible and of correct types.
- All upstream env vars are reflected in config.UPSTREAMS.
- NGINX_PORT, SIDECAR_PORT, HEARTBEAT_INTERVAL, HEARTBEAT_TTL are integers.
- LOG_LEVEL defaults to 'info'.
- WORKER_ID defaults to 'nginx-unity'.
- Upstream env var overrides are applied correctly.
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

    def test_nginx_port_is_int(self):
        assert isinstance(config.NGINX_PORT, int)

    def test_nginx_port_default(self):
        cfg = _reload_config({})
        assert cfg.NGINX_PORT == int(os.getenv("NGINX_PORT", "80"))

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

    def test_upstream_check_timeout_is_float(self):
        assert isinstance(config.UPSTREAM_CHECK_TIMEOUT, float)

    def test_redis_port_is_int(self):
        assert isinstance(config.REDIS_L1_PORT, int)

    def test_redis_db_is_int(self):
        assert isinstance(config.REDIS_L1_DB, int)


class TestConfigOverrides:
    """Verify environment variable overrides are respected."""

    def test_nginx_port_override(self):
        cfg = _reload_config({"NGINX_PORT": "8080"})
        assert cfg.NGINX_PORT == 8080

    def test_centralhub_upstream_override(self):
        cfg = _reload_config({"CENTRALHUB_UPSTREAM": "myhub:9999"})
        assert cfg.CENTRALHUB_UPSTREAM == "myhub:9999"
        assert cfg.UPSTREAMS["centralhub"] == "myhub:9999"

    def test_frontend_upstream_override(self):
        cfg = _reload_config({"FRONTEND_UPSTREAM": "myfe:4000"})
        assert cfg.FRONTEND_UPSTREAM == "myfe:4000"
        assert cfg.UPSTREAMS["frontend"] == "myfe:4000"

    def test_scarerunner_upstream_override(self):
        cfg = _reload_config({"SCARERUNNER_UPSTREAM": "myrunner:7777"})
        assert cfg.SCARERUNNER_UPSTREAM == "myrunner:7777"
        assert cfg.UPSTREAMS["scarerunner"] == "myrunner:7777"

    def test_gatekeeper_upstream_override(self):
        cfg = _reload_config({"GATEKEEPER_UPSTREAM": "mygk:3333"})
        assert cfg.GATEKEEPER_UPSTREAM == "mygk:3333"
        assert cfg.UPSTREAMS["gatekeeper"] == "mygk:3333"

    def test_worker_id_override(self):
        cfg = _reload_config({"WORKER_ID": "my-nginx"})
        assert cfg.WORKER_ID == "my-nginx"

    def test_heartbeat_interval_override(self):
        cfg = _reload_config({"HEARTBEAT_INTERVAL": "30"})
        assert cfg.HEARTBEAT_INTERVAL == 30

    def test_heartbeat_ttl_override(self):
        cfg = _reload_config({"HEARTBEAT_TTL": "90"})
        assert cfg.HEARTBEAT_TTL == 90
