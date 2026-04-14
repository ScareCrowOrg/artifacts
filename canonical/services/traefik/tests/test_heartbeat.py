"""
Unit tests for the Traefik service heartbeat.

Validates:
- Heartbeat registers successfully with the correct service name.
- Heartbeat handles missing BaseService gracefully (import error).
- Config values are read from environment variables correctly.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_service_dir = Path(__file__).resolve().parents[1]
_artifacts_dir = _service_dir.parents[2]  # artifacts/

for _p in [str(_service_dir), str(_artifacts_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestHeartbeatRegistration:
    """Tests for Traefik heartbeat registration."""

    def test_heartbeat_registers_with_service_name(self):
        """BaseService is instantiated with 'traefik' service name."""
        mock_service = MagicMock()
        mock_service.heartbeat = AsyncMock(return_value=None)

        with patch("heartbeat.BaseService", return_value=mock_service) as mock_cls:
            import heartbeat
            heartbeat.main()
            call_args = mock_cls.call_args
            # BaseService is called positionally: BaseService("traefik", logger=...)
            assert call_args[0][0] == "traefik"

    def test_heartbeat_calls_heartbeat_method(self):
        """BaseService.heartbeat() is called during registration."""
        mock_service = MagicMock()
        mock_service.heartbeat = AsyncMock(return_value=None)

        with patch("heartbeat.BaseService", return_value=mock_service):
            import heartbeat
            heartbeat.main()
            mock_service.heartbeat.assert_called_once()

    def test_heartbeat_handles_import_error_gracefully(self):
        """main() does not raise if BaseService import fails and logs a warning."""
        import heartbeat as hb_module
        import logging

        with patch.dict(sys.modules, {"canonical.shared.services.base_service": None}):
            with patch.object(hb_module.logger, "warning") as mock_warn:
                # Should not raise
                hb_module.main()
                # Warning should have been issued about unavailable BaseService
                mock_warn.assert_called_once()
                assert "BaseService unavailable" in mock_warn.call_args[0][0]

    def test_heartbeat_handles_runtime_error_gracefully(self):
        """main() does not raise if heartbeat() raises an exception."""
        mock_service = MagicMock()
        mock_service.heartbeat = AsyncMock(side_effect=Exception("Redis connection failed"))

        with patch("heartbeat.BaseService", return_value=mock_service):
            import heartbeat
            # Should not raise
            heartbeat.main()


class TestConfig:
    """Tests for Traefik config defaults."""

    def test_worker_id_default(self):
        """WORKER_ID defaults to 'traefik'."""
        import config
        assert config.WORKER_ID == "traefik"

    def test_heartbeat_interval_default(self):
        """HEARTBEAT_INTERVAL defaults to 20."""
        import config
        assert config.HEARTBEAT_INTERVAL == 20

    def test_heartbeat_ttl_default(self):
        """HEARTBEAT_TTL defaults to 60."""
        import config
        assert config.HEARTBEAT_TTL == 60

    def test_redis_port_default(self):
        """REDIS_L1_PORT defaults to 6380."""
        import config
        assert config.REDIS_L1_PORT == 6380

    def test_worker_id_from_env(self, monkeypatch):
        """WORKER_ID is read from environment variable."""
        monkeypatch.setenv("WORKER_ID", "traefik-custom")
        import importlib
        import config
        importlib.reload(config)
        assert config.WORKER_ID == "traefik-custom"
        # Restore
        importlib.reload(config)
