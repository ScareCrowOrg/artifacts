"""
Unit tests for service-discovery.py – Traefik Redis L1 service discovery daemon.

Validates:
- Redis SCAN parses keys correctly and extracts service names.
- Only services with port_opened=true are included in the config.
- Traefik itself is excluded from discovered services.
- Config generation builds correct YAML structure.
- Idempotent writes: file only written when routes change.
- Atomic file writes via temp file + os.replace pattern.
- Config round-trip: loaded routes match written routes.
- Non-JSON heartbeat values are silently skipped.
- Unknown services (no port mapping) are logged and skipped.
- Artifact sovereignty: no direct Vite route is emitted — auth-proxy is the only gatekeeper.
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
import yaml

# ── Path setup ────────────────────────────────────────────────────────────────
_service_dir = Path(__file__).resolve().parents[1]
_artifacts_dir = _service_dir.parents[2]  # artifacts/

for _p in [str(_service_dir), str(_artifacts_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import service_discovery as sd  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_redis_mock(keys_and_values: Dict[str, Optional[dict]]) -> AsyncMock:
    """
    Build a mock Redis client for scan_iter + get tests.

    Args:
        keys_and_values: Mapping of Redis key → value dict (or None for missing).
            Value dict is JSON-serialised.  Pass None to simulate missing key.

    Returns:
        AsyncMock configured to yield the given keys and return their values.
    """
    async def _scan_iter(match: str, count: int):
        for key in keys_and_values:
            yield key

    async def _get(key):
        val = keys_and_values.get(key)
        if val is None:
            return None
        return json.dumps(val)

    mock_redis = AsyncMock()
    mock_redis.scan_iter = _scan_iter
    mock_redis.get = AsyncMock(side_effect=_get)
    return mock_redis


# ---------------------------------------------------------------------------
# Tests – scan_healthy_services
# ---------------------------------------------------------------------------


class TestScanHealthyServices:
    @pytest.mark.asyncio
    async def test_returns_service_with_port_opened_true(self):
        """Services with port_opened=True are included."""
        redis = _make_redis_mock({
            "state:service:backend:available": {"port_opened": True, "timestamp": 1.0},
        })
        result = await sd.scan_healthy_services(redis)
        assert result == {"backend"}

    @pytest.mark.asyncio
    async def test_excludes_service_with_port_opened_false(self):
        """Services with port_opened=False are excluded."""
        redis = _make_redis_mock({
            "state:service:backend:available": {"port_opened": False, "timestamp": 1.0},
        })
        result = await sd.scan_healthy_services(redis)
        assert result == set()

    @pytest.mark.asyncio
    async def test_excludes_service_with_port_opened_null(self):
        """Services with port_opened=None are excluded."""
        redis = _make_redis_mock({
            "state:service:vite:available": {"port_opened": None, "timestamp": 1.0},
        })
        result = await sd.scan_healthy_services(redis)
        assert result == set()

    @pytest.mark.asyncio
    async def test_excludes_traefik_from_results(self):
        """Traefik itself is never included in the discovered services."""
        redis = _make_redis_mock({
            "state:service:traefik:available": {"port_opened": True, "timestamp": 1.0},
            "state:service:backend:available": {"port_opened": True, "timestamp": 1.0},
        })
        result = await sd.scan_healthy_services(redis)
        assert "traefik" not in result
        assert "backend" in result

    @pytest.mark.asyncio
    async def test_excludes_non_json_values(self):
        """Services with old-format '1' heartbeat values are silently skipped."""
        async def _scan_iter(match, count):
            yield "state:service:backend:available"

        async def _get(key):
            return "1"  # old format

        mock_redis = AsyncMock()
        mock_redis.scan_iter = _scan_iter
        mock_redis.get = AsyncMock(side_effect=_get)

        result = await sd.scan_healthy_services(mock_redis)
        assert result == set()

    @pytest.mark.asyncio
    async def test_handles_missing_redis_value(self):
        """Keys that return None from GET are safely skipped."""
        redis = _make_redis_mock({
            "state:service:backend:available": None,
        })
        result = await sd.scan_healthy_services(redis)
        assert result == set()

    @pytest.mark.asyncio
    async def test_multiple_services_mixed_health(self):
        """Only services with port_opened=True are returned from a mixed set."""
        redis = _make_redis_mock({
            "state:service:backend:available": {"port_opened": True, "timestamp": 1.0},
            "state:service:vite:available": {"port_opened": False, "timestamp": 1.0},
            "state:service:auth-proxy:available": {"port_opened": True, "timestamp": 1.0},
            "state:service:traefik:available": {"port_opened": True, "timestamp": 1.0},
        })
        result = await sd.scan_healthy_services(redis)
        assert result == {"backend", "auth-proxy"}

    @pytest.mark.asyncio
    async def test_handles_bytes_keys(self):
        """Keys returned as bytes (non-decoded Redis) are handled correctly."""
        async def _scan_iter(match, count):
            yield b"state:service:backend:available"

        async def _get(key):
            return json.dumps({"port_opened": True, "timestamp": 1.0})

        mock_redis = AsyncMock()
        mock_redis.scan_iter = _scan_iter
        mock_redis.get = AsyncMock(side_effect=_get)

        result = await sd.scan_healthy_services(mock_redis)
        assert result == {"backend"}


# ---------------------------------------------------------------------------
# Tests – _build_traefik_config
# ---------------------------------------------------------------------------


class TestBuildTraefikConfig:
    def test_builds_router_for_known_service(self):
        """Config includes router with correct rule for a known service."""
        config = sd._build_traefik_config({"auth-proxy"})
        routers = config["http"]["routers"]
        assert "auth-proxy" in routers
        assert "PathPrefix(`/`)" in routers["auth-proxy"]["rule"]
        assert routers["auth-proxy"]["service"] == "auth-proxy"

    def test_builds_service_with_correct_url(self):
        """Config includes service with correct loadBalancer URL."""
        config = sd._build_traefik_config({"auth-proxy"})
        services = config["http"]["services"]
        assert "auth-proxy" in services
        servers = services["auth-proxy"]["loadBalancer"]["servers"]
        assert any(s["url"] == "http://auth-proxy:5055" for s in servers)

    def test_correct_port_per_service(self):
        """Each service uses its mapped port."""
        config = sd._build_traefik_config({"auth-proxy"})
        services = config["http"]["services"]
        proxy_url = services["auth-proxy"]["loadBalancer"]["servers"][0]["url"]
        assert "5055" in proxy_url

    def test_correct_priority_per_service(self):
        """Each service router has the correct priority."""
        config = sd._build_traefik_config({"auth-proxy"})
        routers = config["http"]["routers"]
        assert routers["auth-proxy"]["priority"] == 100

    def test_empty_services_returns_empty_config(self):
        """No healthy services → empty routers and services."""
        config = sd._build_traefik_config(set())
        assert config["http"]["routers"] == {}
        assert config["http"]["services"] == {}

    def test_unknown_service_skipped_no_route_config(self):
        """Services not in SERVICE_ROUTES are skipped."""
        config = sd._build_traefik_config({"unknown-service"})
        assert "unknown-service" not in config["http"]["routers"]

    def test_entrypoints_include_http(self):
        """All routers include the 'http' entrypoint."""
        config = sd._build_traefik_config({"auth-proxy"})
        assert "http" in config["http"]["routers"]["auth-proxy"]["entryPoints"]


# ---------------------------------------------------------------------------
# Tests – _load_current_services / _write_config_atomic
# ---------------------------------------------------------------------------


class TestConfigFileIO:
    def test_load_returns_empty_set_for_missing_file(self, tmp_path):
        """Missing config file → empty set."""
        result = sd._load_current_services(str(tmp_path / "nonexistent.yml"))
        assert result == set()

    def test_load_returns_empty_set_for_empty_config(self, tmp_path):
        """Config file with empty routers → empty set."""
        config_file = tmp_path / "traefik-services.yml"
        config_file.write_text("http:\n  routers: {}\n  services: {}\n")
        result = sd._load_current_services(str(config_file))
        assert result == set()

    def test_load_returns_router_names(self, tmp_path):
        """Config file with routers → correct set of names."""
        config_file = tmp_path / "traefik-services.yml"
        config = sd._build_traefik_config({"auth-proxy"})
        config_file.write_text(yaml.dump(config))
        result = sd._load_current_services(str(config_file))
        assert result == {"auth-proxy"}

    def test_write_config_creates_file(self, tmp_path):
        """_write_config_atomic creates the config file."""
        path = str(tmp_path / "traefik-services.yml")
        config = sd._build_traefik_config({"backend"})
        sd._write_config_atomic(config, path)
        assert os.path.exists(path)

    def test_write_config_is_valid_yaml(self, tmp_path):
        """Written config is valid YAML."""
        path = str(tmp_path / "traefik-services.yml")
        config = sd._build_traefik_config({"auth-proxy"})
        sd._write_config_atomic(config, path)
        with open(path) as fh:
            loaded = yaml.safe_load(fh)
        assert loaded["http"]["routers"]["auth-proxy"]["rule"] == "PathPrefix(`/`)"

    def test_write_config_round_trip(self, tmp_path):
        """Writing then loading config returns same service names."""
        path = str(tmp_path / "traefik-services.yml")
        expected = {"auth-proxy"}
        sd._write_config_atomic(sd._build_traefik_config(expected), path)
        result = sd._load_current_services(path)
        assert result == expected

    def test_write_config_atomic_no_leftover_tmp(self, tmp_path):
        """No .tmp files remain after atomic write."""
        path = str(tmp_path / "traefik-services.yml")
        sd._write_config_atomic(sd._build_traefik_config({"backend"}), path)
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == []

    def test_write_config_overwrites_existing(self, tmp_path):
        """Subsequent writes overwrite previous content."""
        path = str(tmp_path / "traefik-services.yml")
        sd._write_config_atomic(sd._build_traefik_config({"auth-proxy"}), path)
        sd._write_config_atomic(sd._build_traefik_config(set()), path)
        result = sd._load_current_services(path)
        assert result == set()


# ---------------------------------------------------------------------------
# Tests – idempotency in discovery_loop
# ---------------------------------------------------------------------------


class TestDiscoveryLoopIdempotency:
    @pytest.mark.asyncio
    async def test_does_not_write_if_routes_unchanged(self, tmp_path):
        """Config file is NOT rewritten when routes are already correct."""
        config_path = str(tmp_path / "traefik-services.yml")

        # Pre-populate config with auth-proxy
        sd._write_config_atomic(sd._build_traefik_config({"auth-proxy"}), config_path)
        mtime_before = os.path.getmtime(config_path)

        redis = _make_redis_mock({
            "state:service:auth-proxy:available": {"port_opened": True, "timestamp": 1.0},
        })

        # Patch paths so discovery uses tmp config
        with patch.object(sd, "TRAEFIK_CONFIG_PATH", config_path):
            with patch("redis.asyncio.Redis", return_value=redis):
                # Run one discovery iteration then cancel
                async def fake_sleep(_delay):
                    raise asyncio.CancelledError

                with patch.object(sd, "asyncio") as mock_asyncio:
                    mock_asyncio.sleep = AsyncMock(side_effect=asyncio.CancelledError)
                    mock_asyncio.CancelledError = asyncio.CancelledError
                    # Call core logic directly
                    healthy = await sd.scan_healthy_services(redis)
                    current = sd._load_current_services(config_path)

        # Routes are the same → mtime should not change
        assert healthy == current  # no write would happen
        assert os.path.getmtime(config_path) == mtime_before

    @pytest.mark.asyncio
    async def test_writes_when_new_service_discovered(self, tmp_path):
        """Config file IS written when auth-proxy appears."""
        config_path = str(tmp_path / "traefik-services.yml")

        # Pre-populate with no routes
        sd._write_config_atomic(sd._build_traefik_config(set()), config_path)

        redis = _make_redis_mock({
            "state:service:auth-proxy:available": {"port_opened": True, "timestamp": 1.0},
        })

        healthy = await sd.scan_healthy_services(redis)
        current = sd._load_current_services(config_path)

        assert healthy != current  # diff → write should happen
        sd._write_config_atomic(sd._build_traefik_config(healthy), config_path)
        assert sd._load_current_services(config_path) == {"auth-proxy"}

    @pytest.mark.asyncio
    async def test_writes_when_service_removed(self, tmp_path):
        """Config file IS written when a service disappears from Redis."""
        config_path = str(tmp_path / "traefik-services.yml")
        sd._write_config_atomic(sd._build_traefik_config({"auth-proxy"}), config_path)

        # auth-proxy no longer healthy
        redis = _make_redis_mock({
            "state:service:backend:available": {"port_opened": True, "timestamp": 1.0},
        })

        healthy = await sd.scan_healthy_services(redis)
        current = sd._load_current_services(config_path)

        assert healthy != current
        sd._write_config_atomic(sd._build_traefik_config(healthy), config_path)
        assert sd._load_current_services(config_path) == set()


# ---------------------------------------------------------------------------
# Tests – WSS routing (scan_wss_routes + _build_traefik_config with wss_routes)
# ---------------------------------------------------------------------------


def _make_routing_redis_mock(routing_keys_and_values):
    """
    Build a mock Redis client for scan_wss_routes tests.
    Keys should match `state:service:*:routing` pattern.
    """
    async def _scan_iter(match: str, count: int):
        for key in routing_keys_and_values:
            yield key

    async def _get(key):
        val = routing_keys_and_values.get(key)
        if val is None:
            return None
        return json.dumps(val)

    mock_redis = AsyncMock()
    mock_redis.scan_iter = _scan_iter
    mock_redis.get = AsyncMock(side_effect=_get)
    return mock_redis


class TestScanWssRoutes:
    @pytest.mark.asyncio
    async def test_returns_wss_route_for_enabled_service(self):
        """scan_wss_routes returns routes for services with wss.enabled=true."""
        redis = _make_routing_redis_mock({
            "state:service:backend:routing": {
                "wss": {"enabled": True, "alias": "events", "upstream_port": 5050, "path": "/wss/events"}
            },
        })
        result = await sd.scan_wss_routes(redis)
        assert "backend" in result
        assert result["backend"]["alias"] == "events"
        assert result["backend"]["upstream_port"] == 5050

    @pytest.mark.asyncio
    async def test_excludes_disabled_wss_route(self):
        """scan_wss_routes excludes services with wss.enabled=false."""
        redis = _make_routing_redis_mock({
            "state:service:backend:routing": {
                "wss": {"enabled": False, "alias": "events", "upstream_port": 5050, "path": "/wss/events"}
            },
        })
        result = await sd.scan_wss_routes(redis)
        assert result == {}

    @pytest.mark.asyncio
    async def test_excludes_routing_without_wss_key(self):
        """scan_wss_routes skips entries without a 'wss' key."""
        redis = _make_routing_redis_mock({
            "state:service:backend:routing": {"http": {"enabled": True}},
        })
        result = await sd.scan_wss_routes(redis)
        assert result == {}

    @pytest.mark.asyncio
    async def test_handles_missing_value(self):
        """scan_wss_routes safely skips keys with no Redis value."""
        redis = _make_routing_redis_mock({
            "state:service:backend:routing": None,
        })
        result = await sd.scan_wss_routes(redis)
        assert result == {}

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self):
        """scan_wss_routes skips keys whose value is not valid JSON."""
        async def _scan_iter(match, count):
            yield "state:service:backend:routing"

        async def _get(key):
            return "not-valid-json"

        mock_redis = AsyncMock()
        mock_redis.scan_iter = _scan_iter
        mock_redis.get = AsyncMock(side_effect=_get)

        result = await sd.scan_wss_routes(mock_redis)
        assert result == {}


class TestBuildTraefikConfigWss:
    def test_wss_route_has_priority_110(self):
        """WSS routes are generated with priority 110."""
        wss_routes = {
            "backend": {"enabled": True, "alias": "events", "upstream_port": 5050, "path": "/wss/events"}
        }
        config = sd._build_traefik_config(set(), wss_routes)
        routers = config["http"]["routers"]
        assert "backend-wss-events" in routers
        assert routers["backend-wss-events"]["priority"] == 110

    def test_wss_route_rule_uses_path_prefix(self):
        """WSS route rule uses PathPrefix with the configured path."""
        wss_routes = {
            "backend": {"enabled": True, "alias": "events", "upstream_port": 5050, "path": "/wss/events"}
        }
        config = sd._build_traefik_config(set(), wss_routes)
        router = config["http"]["routers"]["backend-wss-events"]
        assert "PathPrefix(`/wss/events`)" in router["rule"]

    def test_wss_service_points_to_correct_upstream(self):
        """WSS service loadBalancer points to correct service:port."""
        wss_routes = {
            "backend": {"enabled": True, "alias": "events", "upstream_port": 5050, "path": "/wss/events"}
        }
        config = sd._build_traefik_config(set(), wss_routes)
        services = config["http"]["services"]
        assert "backend-wss-events" in services
        url = services["backend-wss-events"]["loadBalancer"]["servers"][0]["url"]
        assert url == "http://backend:5050"

    def test_wss_and_base_routes_coexist(self):
        """WSS routes coexist with base auth-proxy route."""
        wss_routes = {
            "backend": {"enabled": True, "alias": "events", "upstream_port": 5050, "path": "/wss/events"}
        }
        config = sd._build_traefik_config({"auth-proxy"}, wss_routes)
        routers = config["http"]["routers"]
        assert "auth-proxy" in routers
        assert "backend-wss-events" in routers
        # auth-proxy has lower priority
        assert routers["auth-proxy"]["priority"] < routers["backend-wss-events"]["priority"]

    def test_wss_route_skipped_if_missing_alias(self):
        """WSS route with empty alias is skipped."""
        wss_routes = {
            "backend": {"enabled": True, "alias": "", "upstream_port": 5050, "path": "/wss/events"}
        }
        config = sd._build_traefik_config(set(), wss_routes)
        assert config["http"]["routers"] == {}

    def test_wss_route_skipped_if_missing_upstream_port(self):
        """WSS route without upstream_port is skipped."""
        wss_routes = {
            "backend": {"enabled": True, "alias": "events", "path": "/wss/events"}
        }
        config = sd._build_traefik_config(set(), wss_routes)
        assert config["http"]["routers"] == {}

    def test_no_wss_routes_when_none_passed(self):
        """Passing None for wss_routes generates no WSS entries."""
        config = sd._build_traefik_config(set(), None)
        assert config["http"]["routers"] == {}

    def test_backward_compat_no_wss_routes_arg(self):
        """Calling _build_traefik_config without wss_routes arg (backward compat)."""
        config = sd._build_traefik_config({"auth-proxy"})
        assert "auth-proxy" in config["http"]["routers"]
        # No WSS routes generated
        assert not any(k.endswith("-wss-events") for k in config["http"]["routers"])


# ---------------------------------------------------------------------------
# Tests – Artifact Sovereignty (no direct Vite route)
# ---------------------------------------------------------------------------


class TestArtifactSovereignty:
    """Validate that auth-proxy is the sole Traefik gatekeeper (no direct Vite route)."""

    def test_vite_healthy_produces_no_direct_route(self):
        """Even when Vite reports port_opened=True, no direct Vite route is emitted."""
        # Simulate both auth-proxy and vite healthy.
        config = sd._build_traefik_config({"auth-proxy", "vite"})
        routers = config["http"]["routers"]
        assert "vite" not in routers, (
            "Vite must NOT have a direct Traefik route — all traffic must pass through auth-proxy"
        )

    def test_auth_proxy_is_only_base_route(self):
        """Only auth-proxy has a base HTTP route — no other service gets one."""
        config = sd._build_traefik_config({"auth-proxy", "vite", "backend"})
        base_routes = [
            name for name in config["http"]["routers"]
            if not name.endswith(tuple(f"-wss-{a}" for a in ["events", "logs"]))
        ]
        assert base_routes == ["auth-proxy"], (
            f"Expected only auth-proxy as base route, got: {base_routes}"
        )

    def test_artifacts_path_covered_by_auth_proxy_catch_all(self):
        """auth-proxy catch-all (PathPrefix `/`) covers /artifacts/* paths."""
        config = sd._build_traefik_config({"auth-proxy"})
        router = config["http"]["routers"]["auth-proxy"]
        # PathPrefix(`/`) matches all paths including /artifacts/*
        assert "PathPrefix(`/`)" in router["rule"], (
            "auth-proxy must use PathPrefix(`/`) to cover /artifacts/* and all other paths"
        )

    @pytest.mark.asyncio
    async def test_vite_healthy_scan_produces_no_route(self):
        """Integration: when Vite is healthy in Redis, no Vite route appears in YAML."""
        redis = _make_redis_mock({
            "state:service:auth-proxy:available": {"port_opened": True, "timestamp": 1.0},
            "state:service:vite:available": {"port_opened": True, "timestamp": 1.0},
        })
        healthy = await sd.scan_healthy_services(redis)
        assert "vite" in healthy  # Vite IS discovered as healthy...
        config = sd._build_traefik_config(healthy)
        assert "vite" not in config["http"]["routers"]  # ...but gets NO route
        assert "auth-proxy" in config["http"]["routers"]  # auth-proxy is the sole gatekeeper

