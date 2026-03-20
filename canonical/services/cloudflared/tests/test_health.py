"""
Unit tests for the Cloudflared health sidecar endpoints.

Validates:
- GET /health returns 200 with {"status": "healthy"}.
- GET /health/detailed returns 200 with tunnel metadata.
- /health/detailed reflects tunnel token presence.
- /health/detailed reflects ingress rule count.
- /health/detailed reports process status correctly.
"""

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


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_client(mock_base_service):
    """Return a TestClient with mocked BaseService."""
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200(self, app_client):
        response = app_client.get("/health")
        assert response.status_code == 200

    def test_health_returns_healthy_status(self, app_client):
        response = app_client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"


class TestHealthDetailedEndpoint:
    """Tests for GET /health/detailed."""

    def test_detailed_returns_200(self, app_client):
        response = app_client.get("/health/detailed")
        assert response.status_code == 200

    def test_detailed_has_required_fields(self, app_client):
        data = app_client.get("/health/detailed").json()
        assert "status" in data
        assert "tunnel" in data
        tunnel = data["tunnel"]
        assert "name" in tunnel
        assert "process_running" in tunnel
        assert "token_configured" in tunnel
        assert "ingress_rules_count" in tunnel

    def test_detailed_status_is_healthy(self, app_client):
        data = app_client.get("/health/detailed").json()
        assert data["status"] == "healthy"

    def test_token_configured_false_when_empty(self, mock_base_service):
        with patch("config.TUNNEL_TOKEN", ""):
            from fastapi.testclient import TestClient
            from main import app

            with TestClient(app) as client:
                data = client.get("/health/detailed").json()
                assert data["tunnel"]["token_configured"] is False

    def test_token_configured_true_when_set(self, mock_base_service):
        with patch("config.TUNNEL_TOKEN", "dummy-token"):
            from fastapi.testclient import TestClient
            from main import app

            with TestClient(app) as client:
                data = client.get("/health/detailed").json()
                assert data["tunnel"]["token_configured"] is True

    def test_ingress_rules_count_zero(self, mock_base_service):
        with patch("config.INGRESS_RULES", []):
            from fastapi.testclient import TestClient
            from main import app

            with TestClient(app) as client:
                data = client.get("/health/detailed").json()
                assert data["tunnel"]["ingress_rules_count"] == 0

    def test_ingress_rules_count_reflects_config(self, mock_base_service):
        rules = [
            {"hostname": "api.example.com", "service": "http://backend:5051"},
            {"service": "http_status:404"},
        ]
        with patch("config.INGRESS_RULES", rules):
            from fastapi.testclient import TestClient
            from main import app

            with TestClient(app) as client:
                data = client.get("/health/detailed").json()
                assert data["tunnel"]["ingress_rules_count"] == 2

    def test_tunnel_name_from_config(self, mock_base_service):
        with patch("config.TUNNEL_NAME", "my-tunnel"):
            from fastapi.testclient import TestClient
            from main import app

            with TestClient(app) as client:
                data = client.get("/health/detailed").json()
                assert data["tunnel"]["name"] == "my-tunnel"

    def test_process_running_when_pgrep_returns_zero(self, app_client):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("main.subprocess.run", return_value=mock_result):
            data = app_client.get("/health/detailed").json()
            assert data["tunnel"]["process_running"] is True

    def test_process_not_running_when_pgrep_returns_nonzero(self, app_client):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("main.subprocess.run", return_value=mock_result):
            data = app_client.get("/health/detailed").json()
            assert data["tunnel"]["process_running"] is False

    def test_process_check_handles_file_not_found(self, app_client):
        with patch("main.subprocess.run", side_effect=FileNotFoundError):
            data = app_client.get("/health/detailed").json()
            assert data["tunnel"]["process_running"] is False
