"""
Tests for Nginx Unit configuration file (unit.conf.json).

Validates:
- unit.conf.json exists alongside the Dockerfile.
- unit.conf.json is valid JSON.
- Initial config has an empty routes list (no vite/backend upstreams).
- Initial config has a listener on port 80.
- Initial config has an empty upstreams dict (routes registered dynamically).
"""

import json
import sys
from pathlib import Path

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_service_dir = Path(__file__).resolve().parents[1]
_artifacts_dir = _service_dir.parents[3]
for _p in [str(_service_dir), str(_artifacts_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

_unit_conf_path = _service_dir / "unit.conf.json"


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestUnitConfJson:
    """Validate the Nginx Unit initial configuration file."""

    def test_unit_conf_exists(self):
        """unit.conf.json must exist for the container to load it."""
        assert _unit_conf_path.exists(), "unit.conf.json not found in nginx-unity service directory"

    def test_unit_conf_is_valid_json(self):
        """unit.conf.json must be parseable JSON."""
        content = _unit_conf_path.read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert isinstance(parsed, dict)

    def test_unit_conf_has_listeners(self):
        """Nginx Unit requires a 'listeners' section."""
        config = json.loads(_unit_conf_path.read_text(encoding="utf-8"))
        assert "listeners" in config

    def test_unit_conf_has_port_80_listener(self):
        """Listener must be on port 80 (or *:80) for HTTP traffic."""
        config = json.loads(_unit_conf_path.read_text(encoding="utf-8"))
        listeners = config["listeners"]
        has_port_80 = any("80" in key for key in listeners)
        assert has_port_80, f"No port 80 listener found in: {list(listeners.keys())}"

    def test_unit_conf_routes_is_empty_list(self):
        """Routes must start empty – vite/backend registered dynamically."""
        config = json.loads(_unit_conf_path.read_text(encoding="utf-8"))
        assert "routes" in config
        assert config["routes"] == [], "Initial routes must be empty (dynamic registration)"

    def test_unit_conf_upstreams_is_empty(self):
        """Upstreams must start empty – registered dynamically after heartbeat."""
        config = json.loads(_unit_conf_path.read_text(encoding="utf-8"))
        assert "upstreams" in config
        assert config["upstreams"] == {}, "Initial upstreams must be empty (dynamic registration)"

    def test_unit_conf_no_vite_upstream(self):
        """No vite upstream at startup – causes Phase 7 validation failures."""
        config = json.loads(_unit_conf_path.read_text(encoding="utf-8"))
        upstreams = config.get("upstreams", {})
        assert "vite" not in upstreams, "vite upstream must not be in initial config"

    def test_unit_conf_no_backend_upstream(self):
        """No backend upstream at startup – causes Phase 7 validation failures."""
        config = json.loads(_unit_conf_path.read_text(encoding="utf-8"))
        upstreams = config.get("upstreams", {})
        assert "backend" not in upstreams, "backend upstream must not be in initial config"
