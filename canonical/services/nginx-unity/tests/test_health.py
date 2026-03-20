"""
Unit tests for the Nginx Unity health sidecar endpoints.

Validates:
- GET /health returns 200 with {"status": "healthy"}.
- GET /health/detailed returns 200 with upstream status dict.
- /health/detailed probes all configured upstreams.
- /health/detailed marks individual upstreams as "up" or "down".
- /health/detailed handles HTTP client not initialized (returns "down").
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

# ── Path setup ────────────────────────────────────────────────────────────────
_service_dir = Path(__file__).resolve().parents[1]
_artifacts_dir = _service_dir.parents[3]
for _p in [str(_service_dir), str(_artifacts_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200(self, app_client):
        response = app_client.get("/health")
        assert response.status_code == 200

    def test_health_returns_healthy_status(self, app_client):
        response = app_client.get("/health")
        assert response.json() == {"status": "healthy"}


class TestHealthDetailedEndpoint:
    """Tests for GET /health/detailed."""

    def test_detailed_returns_200(self, app_client):
        response = app_client.get("/health/detailed")
        assert response.status_code == 200

    def test_detailed_has_status_field(self, app_client):
        data = app_client.get("/health/detailed").json()
        assert data["status"] == "healthy"

    def test_detailed_has_upstreams_field(self, app_client):
        data = app_client.get("/health/detailed").json()
        assert "upstreams" in data

    def test_detailed_reports_all_configured_upstreams(self, app_client):
        import config
        data = app_client.get("/health/detailed").json()
        upstreams = data["upstreams"]
        for key in config.UPSTREAMS:
            assert key in upstreams

    def test_upstream_marked_up_on_successful_probe(self, app_client):
        """Upstreams report 'up' when the HTTP client returns a response."""
        import main

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        # Override the client that lifespan created
        main._http_client = mock_client

        data = app_client.get("/health/detailed").json()

        for upstream_status in data["upstreams"].values():
            assert upstream_status == "up"

    def test_upstream_marked_down_on_connection_error(self, app_client):
        """Upstreams report 'down' when the HTTP client raises ConnectError."""
        import main

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        main._http_client = mock_client

        data = app_client.get("/health/detailed").json()

        for upstream_status in data["upstreams"].values():
            assert upstream_status == "down"

    def test_upstream_marked_down_when_client_is_none(self, app_client):
        """Upstreams report 'down' when _http_client is None."""
        import main

        main._http_client = None

        data = app_client.get("/health/detailed").json()

        for upstream_status in data["upstreams"].values():
            assert upstream_status == "down"

    def test_partial_upstream_failure(self, app_client):
        """One upstream fails; others succeed."""
        import main

        async def fake_get(url):
            if "centralhub" in url:
                raise httpx.ConnectError("refused")
            return MagicMock(status_code=200)

        mock_client = AsyncMock()
        mock_client.get = fake_get
        main._http_client = mock_client

        data = app_client.get("/health/detailed").json()
        upstreams = data["upstreams"]

        assert upstreams["centralhub"] == "down"
        for name, status in upstreams.items():
            if name != "centralhub":
                assert status == "up", f"Expected {name} to be 'up', got '{status}'"
