"""
Unit tests for GateKeeper service availability mechanism.

Validates:
- _probe_http_health(): returns True on 2xx, False on 4xx/5xx/timeout/empty URL.
- _check_service_availability(): sets/deletes the correct Redis keys based on
  HTTP probe results (state:service:{name}:available).
- Subprocess workers (no deps) are always marked available without probing.
- Deduplication: the same service dependency is only probed once per cycle.
- Loop resilience: exceptions are caught so the loop continues.
"""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ..main import GateKeeper


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis_l1() -> AsyncMock:
    client = AsyncMock()
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    return client


@pytest.fixture
def mock_redis_l2() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_http_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def gatekeeper(mock_redis_l1, mock_redis_l2, mock_http_client) -> GateKeeper:
    return GateKeeper(mock_redis_l1, mock_redis_l2, mock_http_client)


# ---------------------------------------------------------------------------
# _probe_http_health tests
# ---------------------------------------------------------------------------


class TestProbeHttpHealth:
    @pytest.mark.asyncio
    async def test_empty_url_returns_false(self, gatekeeper):
        """Empty URL → returns False without making any HTTP request."""
        result = await gatekeeper._probe_http_health("")
        assert result is False

    @pytest.mark.asyncio
    async def test_200_response_returns_true(self, gatekeeper):
        """HTTP 200 → returns True."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        gatekeeper.http.get = AsyncMock(return_value=mock_response)

        result = await gatekeeper._probe_http_health("http://service:9090/health")
        assert result is True

    @pytest.mark.asyncio
    async def test_201_response_returns_true(self, gatekeeper):
        """HTTP 201 → returns True (< 400)."""
        mock_response = MagicMock()
        mock_response.status_code = 201

        gatekeeper.http.get = AsyncMock(return_value=mock_response)

        result = await gatekeeper._probe_http_health("http://service:9090/health")
        assert result is True

    @pytest.mark.asyncio
    async def test_400_response_returns_false(self, gatekeeper):
        """HTTP 400 → returns False."""
        mock_response = MagicMock()
        mock_response.status_code = 400

        gatekeeper.http.get = AsyncMock(return_value=mock_response)

        result = await gatekeeper._probe_http_health("http://service:9090/health")
        assert result is False

    @pytest.mark.asyncio
    async def test_500_response_returns_false(self, gatekeeper):
        """HTTP 500 → returns False."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        gatekeeper.http.get = AsyncMock(return_value=mock_response)

        result = await gatekeeper._probe_http_health("http://service:9090/health")
        assert result is False

    @pytest.mark.asyncio
    async def test_connection_error_returns_false(self, gatekeeper):
        """Connection error → returns False."""
        gatekeeper.http.get = AsyncMock(
            side_effect=Exception("Connection refused")
        )

        result = await gatekeeper._probe_http_health("http://service:9090/health")
        assert result is False

    @pytest.mark.asyncio
    async def test_timeout_returns_false(self, gatekeeper):
        """Timeout → returns False."""
        import httpx

        gatekeeper.http.get = AsyncMock(
            side_effect=httpx.TimeoutException("timed out")
        )

        result = await gatekeeper._probe_http_health("http://service:9090/health")
        assert result is False


# ---------------------------------------------------------------------------
# _check_service_availability tests
# ---------------------------------------------------------------------------


class TestCheckServiceAvailability:
    @pytest.mark.asyncio
    async def test_subprocess_no_deps_always_sets_key(self, gatekeeper, mock_redis_l1):
        """Subprocess workers with no dependencies always set their availability key."""
        import config as config_module

        job_types_config: Dict[str, Any] = {
            "rembg_removebackground": {
                "execution_model": "subprocess",
                "dependencies": [],
                "endpoint": "",
                "health_path": "/health",
            }
        }

        async def fake_sleep(_delay):
            raise asyncio.CancelledError

        with patch.object(config_module, "JOB_TYPES_CONFIG", job_types_config), \
             patch.object(config_module, "VENV_HEALTH_CHECK_INTERVAL", 60), \
             patch("asyncio.sleep", side_effect=fake_sleep):
            try:
                await gatekeeper._check_service_availability()
            except asyncio.CancelledError:
                pass

        mock_redis_l1.set.assert_called_once_with(
            "state:service:rembg_removebackground:available", "1", ex=120
        )

    @pytest.mark.asyncio
    async def test_service_no_deps_sets_key(self, gatekeeper, mock_redis_l1):
        """Service workers with empty dependencies also get the key set directly."""
        import config as config_module

        job_types_config: Dict[str, Any] = {
            "instantmesh": {
                "execution_model": "service",
                "dependencies": [],
                "endpoint": "http://instantmesh:8000",
                "health_path": "/health",
            }
        }

        async def fake_sleep(_delay):
            raise asyncio.CancelledError

        with patch.object(config_module, "JOB_TYPES_CONFIG", job_types_config), \
             patch.object(config_module, "VENV_HEALTH_CHECK_INTERVAL", 60), \
             patch("asyncio.sleep", side_effect=fake_sleep):
            try:
                await gatekeeper._check_service_availability()
            except asyncio.CancelledError:
                pass

        mock_redis_l1.set.assert_called_once_with(
            "state:service:instantmesh:available", "1", ex=120
        )

    @pytest.mark.asyncio
    async def test_healthy_service_sets_key(self, gatekeeper, mock_redis_l1):
        """Service with healthy HTTP probe → sets state:service:{dep}:available."""
        import config as config_module

        job_types_config: Dict[str, Any] = {
            "sd_generate": {
                "execution_model": "service",
                "dependencies": ["stable-diffusion"],
                "endpoint": "http://scareverse-sd-service:9090",
                "health_path": "/health",
            }
        }

        async def fake_sleep(_delay):
            raise asyncio.CancelledError

        with patch.object(config_module, "JOB_TYPES_CONFIG", job_types_config), \
             patch.object(config_module, "VENV_HEALTH_CHECK_INTERVAL", 60), \
             patch.object(gatekeeper, "_probe_http_health", new=AsyncMock(return_value=True)), \
             patch("asyncio.sleep", side_effect=fake_sleep):
            try:
                await gatekeeper._check_service_availability()
            except asyncio.CancelledError:
                pass

        mock_redis_l1.set.assert_called_once_with(
            "state:service:stable-diffusion:available", "1", ex=120
        )
        mock_redis_l1.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_unhealthy_service_deletes_key(self, gatekeeper, mock_redis_l1):
        """Service with failing HTTP probe → deletes state:service:{dep}:available."""
        import config as config_module

        job_types_config: Dict[str, Any] = {
            "sd_generate": {
                "execution_model": "service",
                "dependencies": ["stable-diffusion"],
                "endpoint": "http://scareverse-sd-service:9090",
                "health_path": "/health",
            }
        }

        async def fake_sleep(_delay):
            raise asyncio.CancelledError

        with patch.object(config_module, "JOB_TYPES_CONFIG", job_types_config), \
             patch.object(config_module, "VENV_HEALTH_CHECK_INTERVAL", 60), \
             patch.object(gatekeeper, "_probe_http_health", new=AsyncMock(return_value=False)), \
             patch("asyncio.sleep", side_effect=fake_sleep):
            try:
                await gatekeeper._check_service_availability()
            except asyncio.CancelledError:
                pass

        mock_redis_l1.delete.assert_called_once_with(
            "state:service:stable-diffusion:available"
        )
        mock_redis_l1.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_shared_dependency_probed_once(self, gatekeeper, mock_redis_l1):
        """Two job-types sharing the same dependency probe it only once."""
        import config as config_module

        job_types_config: Dict[str, Any] = {
            "ollama_generate": {
                "execution_model": "service",
                "dependencies": ["ollama"],
                "endpoint": "http://scareverse-ollama-service:11434",
                "health_path": "/api/version",
            },
            "ollama_chat": {
                "execution_model": "service",
                "dependencies": ["ollama"],
                "endpoint": "http://scareverse-ollama-service:11434",
                "health_path": "/api/version",
            },
        }

        probe_mock = AsyncMock(return_value=True)

        async def fake_sleep(_delay):
            raise asyncio.CancelledError

        with patch.object(config_module, "JOB_TYPES_CONFIG", job_types_config), \
             patch.object(config_module, "VENV_HEALTH_CHECK_INTERVAL", 60), \
             patch.object(gatekeeper, "_probe_http_health", new=probe_mock), \
             patch("asyncio.sleep", side_effect=fake_sleep):
            try:
                await gatekeeper._check_service_availability()
            except asyncio.CancelledError:
                pass

        # Probe called only once despite two job types sharing "ollama"
        probe_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_exception_in_loop_is_recovered(self, gatekeeper, mock_redis_l1):
        """Exception inside the loop body is caught and the loop continues."""
        import config as config_module

        call_count = 0

        async def fake_sleep(_delay):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError

        job_types_config: Dict[str, Any] = {
            "sd_generate": {
                "execution_model": "service",
                "dependencies": ["stable-diffusion"],
                "endpoint": "http://scareverse-sd-service:9090",
                "health_path": "/health",
            }
        }

        call_num = 0

        async def probe_side_effect(url: str) -> bool:
            nonlocal call_num
            call_num += 1
            if call_num == 1:
                raise RuntimeError("Redis error")
            return True

        with patch.object(config_module, "JOB_TYPES_CONFIG", job_types_config), \
             patch.object(config_module, "VENV_HEALTH_CHECK_INTERVAL", 60), \
             patch.object(gatekeeper, "_probe_http_health", side_effect=probe_side_effect), \
             patch("asyncio.sleep", side_effect=fake_sleep):
            try:
                await gatekeeper._check_service_availability()
            except asyncio.CancelledError:
                pass

        # Loop ran twice: first iteration raised, second set the key
        assert call_count == 2
        mock_redis_l1.set.assert_called_once_with(
            "state:service:stable-diffusion:available", "1", ex=120
        )

    @pytest.mark.asyncio
    async def test_health_url_uses_health_path(self, gatekeeper, mock_redis_l1):
        """Health probe URL is constructed from endpoint + health_path."""
        import config as config_module

        job_types_config: Dict[str, Any] = {
            "ollama_generate": {
                "execution_model": "service",
                "dependencies": ["ollama"],
                "endpoint": "http://scareverse-ollama-service:11434",
                "health_path": "/api/version",
            }
        }

        probe_mock = AsyncMock(return_value=True)

        async def fake_sleep(_delay):
            raise asyncio.CancelledError

        with patch.object(config_module, "JOB_TYPES_CONFIG", job_types_config), \
             patch.object(config_module, "VENV_HEALTH_CHECK_INTERVAL", 60), \
             patch.object(gatekeeper, "_probe_http_health", new=probe_mock), \
             patch("asyncio.sleep", side_effect=fake_sleep):
            try:
                await gatekeeper._check_service_availability()
            except asyncio.CancelledError:
                pass

        probe_mock.assert_called_once_with(
            "http://scareverse-ollama-service:11434/api/version"
        )
