"""
Unit tests for the Nginx Unity heartbeat sidecar.

Validates:
- Sidecar starts heartbeat on application startup.
- Sidecar cleans up heartbeat on application shutdown.
- BaseService is instantiated with correct config values.
- App initializes without HTTP health endpoints.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ── Path setup ────────────────────────────────────────────────────────────────
_service_dir = Path(__file__).resolve().parents[1]
_artifacts_dir = _service_dir.parents[2]  # artifacts/
for _p in [str(_service_dir), str(_artifacts_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestSidecarLifecycle:
    """Tests for heartbeat sidecar startup and shutdown."""

    def test_heartbeat_started_on_startup(self, mock_base_service):
        """BaseService.heartbeat() is called during app lifespan startup."""
        from main import app

        with TestClient(app, raise_server_exceptions=True):
            mock_base_service.heartbeat.assert_called_once()

    def test_cleanup_called_on_shutdown(self, mock_base_service):
        """BaseService.cleanup() is called during app lifespan shutdown."""
        from main import app

        with TestClient(app, raise_server_exceptions=True):
            pass  # context exit triggers shutdown

        mock_base_service.cleanup.assert_called_once()

    def test_base_service_instantiated_with_worker_id(self, mock_base_service):
        """BaseService is created with WORKER_ID from config."""
        import config
        from main import app

        with patch("main.BaseService", return_value=mock_base_service) as mock_cls:
            with TestClient(app, raise_server_exceptions=True):
                call_kwargs = mock_cls.call_args[1]
                assert call_kwargs["service_name"] == config.WORKER_ID

    def test_no_health_endpoint(self, mock_base_service):
        """GET /health is not registered (health is Redis-driven, not HTTP)."""
        from main import app

        with TestClient(app, raise_server_exceptions=True) as client:
            response = client.get("/health")
            assert response.status_code == 404

    def test_no_health_detailed_endpoint(self, mock_base_service):
        """GET /health/detailed is not registered (upstreams are dynamic)."""
        from main import app

        with TestClient(app, raise_server_exceptions=True) as client:
            response = client.get("/health/detailed")
            assert response.status_code == 404
