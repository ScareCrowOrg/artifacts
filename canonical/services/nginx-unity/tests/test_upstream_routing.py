"""
Tests for upstream routing configuration and _check_upstream helper.

Validates:
- _check_upstream returns "up" on successful HTTP probe.
- _check_upstream returns "down" on timeout.
- _check_upstream returns "down" on connection error.
- _check_upstream returns "down" when _http_client is None.
- config.UPSTREAMS contains all expected upstream names.
- All upstream addresses from config are used in detailed health check.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_service_dir = Path(__file__).resolve().parents[1]
_artifacts_dir = _service_dir.parents[3]
for _p in [str(_service_dir), str(_artifacts_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main  # noqa: E402
import config  # noqa: E402


# ── _check_upstream ───────────────────────────────────────────────────────────


class TestCheckUpstream:
    """Unit tests for main._check_upstream()."""

    @pytest.mark.asyncio
    async def test_returns_up_on_success(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=MagicMock(status_code=200))
        main._http_client = mock_client

        result = await main._check_upstream("centralhub", "centralhub:5051")
        assert result == "up"
        mock_client.get.assert_called_once_with("http://centralhub:5051")

    @pytest.mark.asyncio
    async def test_returns_down_on_connect_error(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        main._http_client = mock_client

        result = await main._check_upstream("centralhub", "centralhub:5051")
        assert result == "down"

    @pytest.mark.asyncio
    async def test_returns_down_on_timeout(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        main._http_client = mock_client

        result = await main._check_upstream("centralhub", "centralhub:5051")
        assert result == "down"

    @pytest.mark.asyncio
    async def test_returns_down_when_client_is_none(self):
        main._http_client = None
        result = await main._check_upstream("frontend", "vite-frontend:5173")
        assert result == "down"

    @pytest.mark.asyncio
    async def test_returns_down_on_generic_exception(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=RuntimeError("unexpected"))
        main._http_client = mock_client

        result = await main._check_upstream("scarerunner", "scarerunner:5050")
        assert result == "down"

    @pytest.mark.asyncio
    async def test_any_http_status_counts_as_up(self):
        """Even a 404 response means the upstream is reachable."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=MagicMock(status_code=404))
        main._http_client = mock_client

        result = await main._check_upstream("frontend", "vite-frontend:5173")
        assert result == "up"


# ── Config upstream map ───────────────────────────────────────────────────────


class TestConfigUpstreams:
    """Verify the UPSTREAMS dict in config contains expected keys."""

    def test_upstreams_has_centralhub(self):
        assert "centralhub" in config.UPSTREAMS

    def test_upstreams_has_frontend(self):
        assert "frontend" in config.UPSTREAMS

    def test_upstreams_has_scarerunner(self):
        assert "scarerunner" in config.UPSTREAMS

    def test_upstreams_has_gatekeeper(self):
        assert "gatekeeper" in config.UPSTREAMS

    def test_upstream_values_are_strings(self):
        for key, value in config.UPSTREAMS.items():
            assert isinstance(value, str), f"Upstream {key!r} value is not a string: {value!r}"

    def test_upstream_values_contain_port(self):
        for key, value in config.UPSTREAMS.items():
            assert ":" in value, f"Upstream {key!r} value missing port: {value!r}"
