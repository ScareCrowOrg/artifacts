"""
Unit tests for BaseService – Redis heartbeat registration.

Validates:
- heartbeat() sets the correct Redis key with the correct TTL.
- heartbeat() stores a JSON value with port_opened and timestamp fields.
- heartbeat() loops (calls set multiple times).
- heartbeat() handles Redis connection failure gracefully (logs, retries).
- heartbeat() handles Redis command error gracefully (logs, continues).
- heartbeat() exits cleanly when redis-py is not installed (ImportError).
- Redis key format: state:service:{name}:available.
- Default TTL is 3× heartbeat_interval.
- Custom redis config and heartbeat_interval / key_ttl are respected.
- _check_port_health() returns True/False/None based on port availability.
- service_port parameter and WORKER_PORT env var are respected.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup: ensure shared/ is importable without a package install
# ---------------------------------------------------------------------------

_shared_dir = Path(__file__).resolve().parents[1]
if str(_shared_dir) not in sys.path:
    sys.path.insert(0, str(_shared_dir))

from services.base_service import BaseService  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(
    name: str = "test-service",
    heartbeat_interval: int = 1,
    key_ttl: int = 3,
    **kwargs: Any,
) -> BaseService:
    """Create a BaseService configured for fast unit-test iteration."""
    return BaseService(
        service_name=name,
        heartbeat_interval=heartbeat_interval,
        key_ttl=key_ttl,
        **kwargs,
    )


async def _run_heartbeat_iterations(service: BaseService, mock_redis: Any, iterations: int) -> None:
    """
    Run *iterations* loops of the heartbeat by patching asyncio.sleep so that
    after the Nth call it cancels the task.
    """
    call_count = 0

    async def fake_sleep(_delay: float) -> None:
        nonlocal call_count
        call_count += 1
        if call_count >= iterations:
            raise asyncio.CancelledError

    with patch("services.base_service.asyncio.sleep", side_effect=fake_sleep):
        with patch("redis.asyncio.Redis", return_value=mock_redis):
            try:
                await service.heartbeat()
            except asyncio.CancelledError:
                pass


# ---------------------------------------------------------------------------
# Tests – normal behaviour
# ---------------------------------------------------------------------------


class TestBaseServiceHeartbeat:
    @pytest.mark.asyncio
    async def test_sets_correct_key_with_ttl(self):
        """heartbeat() sets state:service:{name}:available with correct TTL."""
        mock_redis = AsyncMock()
        service = _make_service("ollama")

        await _run_heartbeat_iterations(service, mock_redis, iterations=1)

        assert mock_redis.set.call_count == 1
        args, kwargs = mock_redis.set.call_args
        assert args[0] == "state:service:ollama:available"
        assert kwargs["ex"] == 3

    @pytest.mark.asyncio
    async def test_value_is_json_with_port_opened(self):
        """heartbeat() stores JSON value with port_opened and timestamp fields."""
        mock_redis = AsyncMock()
        service = _make_service("ollama")

        await _run_heartbeat_iterations(service, mock_redis, iterations=1)

        args, _ = mock_redis.set.call_args
        value = json.loads(args[1])
        assert "port_opened" in value
        assert "timestamp" in value
        assert isinstance(value["timestamp"], float)

    @pytest.mark.asyncio
    async def test_port_opened_null_when_no_port_configured(self):
        """port_opened is null when service_port is not configured."""
        mock_redis = AsyncMock()
        service = _make_service("ollama")  # no service_port

        await _run_heartbeat_iterations(service, mock_redis, iterations=1)

        args, _ = mock_redis.set.call_args
        value = json.loads(args[1])
        assert value["port_opened"] is None

    @pytest.mark.asyncio
    async def test_uses_correct_ttl(self):
        """heartbeat() uses key_ttl for the Redis TTL."""
        mock_redis = AsyncMock()
        service = _make_service("stable-diffusion", heartbeat_interval=2, key_ttl=6)

        await _run_heartbeat_iterations(service, mock_redis, iterations=1)

        _, call_kwargs = mock_redis.set.call_args
        assert call_kwargs["ex"] == 6

    @pytest.mark.asyncio
    async def test_default_ttl_is_three_times_interval(self):
        """When key_ttl is not supplied, it defaults to heartbeat_interval * 3."""
        service = BaseService("my-svc", heartbeat_interval=10)
        assert service._key_ttl == 30

    @pytest.mark.asyncio
    async def test_loops_multiple_times(self):
        """heartbeat() calls set on every iteration."""
        mock_redis = AsyncMock()
        service = _make_service("ollama")

        await _run_heartbeat_iterations(service, mock_redis, iterations=3)

        assert mock_redis.set.call_count == 3

    @pytest.mark.asyncio
    async def test_key_format(self):
        """Key must be state:service:{name}:available."""
        mock_redis = AsyncMock()
        service = _make_service("instantmesh")

        await _run_heartbeat_iterations(service, mock_redis, iterations=1)

        args, _ = mock_redis.set.call_args
        assert args[0] == "state:service:instantmesh:available"

    @pytest.mark.asyncio
    async def test_port_opened_true_when_health_check_succeeds(self):
        """port_opened is True when HTTP /health returns 200."""
        mock_redis = AsyncMock()
        service = _make_service("backend", service_port=5050)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.base_service.asyncio.sleep", side_effect=asyncio.CancelledError):
            with patch("redis.asyncio.Redis", return_value=mock_redis):
                with patch("httpx.AsyncClient", return_value=mock_client):
                    try:
                        await service.heartbeat()
                    except asyncio.CancelledError:
                        pass

        args, _ = mock_redis.set.call_args
        value = json.loads(args[1])
        assert value["port_opened"] is True

    @pytest.mark.asyncio
    async def test_port_opened_false_when_health_check_fails(self):
        """port_opened is False when HTTP /health fails or times out."""
        mock_redis = AsyncMock()
        service = _make_service("backend", service_port=5050)

        with patch("services.base_service.asyncio.sleep", side_effect=asyncio.CancelledError):
            with patch("redis.asyncio.Redis", return_value=mock_redis):
                with patch("httpx.AsyncClient") as mock_client_cls:
                    mock_client_cls.return_value.__aenter__ = AsyncMock(
                        side_effect=Exception("Connection refused")
                    )
                    try:
                        await service.heartbeat()
                    except asyncio.CancelledError:
                        pass

        args, _ = mock_redis.set.call_args
        value = json.loads(args[1])
        assert value["port_opened"] is False


# ---------------------------------------------------------------------------
# Tests – port health check
# ---------------------------------------------------------------------------


class TestCheckPortHealth:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_port(self):
        """_check_port_health() returns None when service_port is not set."""
        service = BaseService("svc")
        result = await service._check_port_health()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_true_on_200(self):
        """_check_port_health() returns True when /health responds 200."""
        service = BaseService("svc", service_port=5050)
        mock_response = MagicMock(status_code=200)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service._check_port_health()

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_non_200(self):
        """_check_port_health() returns False when /health responds non-200."""
        service = BaseService("svc", service_port=5050)
        mock_response = MagicMock(status_code=503)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service._check_port_health()

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_connection_error(self):
        """_check_port_health() returns False when port is not reachable."""
        service = BaseService("svc", service_port=5050)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("Connection refused")
            )
            result = await service._check_port_health()

        assert result is False

    @pytest.mark.asyncio
    async def test_does_not_raise_on_timeout(self):
        """_check_port_health() swallows timeout exceptions and returns False."""
        service = BaseService("svc", service_port=5050)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("Timeout")
            )
            result = await service._check_port_health()  # must not raise

        assert result is False


# ---------------------------------------------------------------------------
# Tests – error handling
# ---------------------------------------------------------------------------


class TestBaseServiceErrorHandling:
    @pytest.mark.asyncio
    async def test_redis_connection_error_logs_and_continues(self):
        """Redis ConnectionError: logs warning, client reset to None, loop continues."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(side_effect=ConnectionError("Redis down"))

        service = _make_service("ollama")
        mock_logger = MagicMock()
        service._logger = mock_logger

        await _run_heartbeat_iterations(service, mock_redis, iterations=2)

        assert mock_logger.warning.call_count >= 1
        warning_msg = mock_logger.warning.call_args_list[0][0][0]
        assert "Heartbeat failed" in warning_msg

    @pytest.mark.asyncio
    async def test_redis_command_error_does_not_stop_loop(self):
        """Redis command error: loop continues and retries on next iteration."""
        call_count = 0
        mock_redis = AsyncMock()

        async def set_side_effect(*args: Any, **kwargs: Any) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("SET command failed")

        mock_redis.set = AsyncMock(side_effect=set_side_effect)
        service = _make_service("ollama")

        await _run_heartbeat_iterations(service, mock_redis, iterations=2)

        # Second iteration should succeed
        assert mock_redis.set.call_count == 2

    @pytest.mark.asyncio
    async def test_redis_import_error_exits_gracefully(self):
        """When redis-py is not installed, heartbeat() logs and returns without looping."""
        service = _make_service("ollama")
        mock_logger = MagicMock()
        service._logger = mock_logger

        with patch.dict(sys.modules, {"redis": None, "redis.asyncio": None}):
            await service.heartbeat()

        mock_logger.warning.assert_called_once()
        assert "redis-py not installed" in mock_logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    async def test_reconnects_after_failure(self):
        """After a connection failure the client is reset and reconnected next iteration."""
        mock_redis_calls = []
        first_client = AsyncMock()
        second_client = AsyncMock()
        first_client.set = AsyncMock(side_effect=ConnectionError("timeout"))

        clients = iter([first_client, second_client])

        def make_client(**_kwargs: Any) -> AsyncMock:
            c = next(clients)
            mock_redis_calls.append(c)
            return c

        service = _make_service("ollama")

        async def fake_sleep(_delay: float) -> None:
            if len(mock_redis_calls) >= 2:
                raise asyncio.CancelledError

        with patch("services.base_service.asyncio.sleep", side_effect=fake_sleep):
            with patch("redis.asyncio.Redis", side_effect=make_client):
                try:
                    await service.heartbeat()
                except asyncio.CancelledError:
                    pass

        # Both clients were created (first failed, second is fresh reconnect)
        assert len(mock_redis_calls) == 2
        second_client.set.assert_called_once()


# ---------------------------------------------------------------------------
# Tests – configuration
# ---------------------------------------------------------------------------


class TestBaseServiceConfiguration:
    def test_custom_redis_host_port(self):
        """Custom redis_host / redis_port are stored correctly."""
        service = BaseService("svc", redis_host="my-redis", redis_port=6399)
        assert service._redis_host == "my-redis"
        assert service._redis_port == 6399

    def test_custom_redis_db(self):
        """Custom redis_db is stored correctly."""
        service = BaseService("svc", redis_db=2)
        assert service._redis_db == 2

    def test_no_password_when_empty_string(self):
        """Passing redis_password='' stores None (no auth)."""
        service = BaseService("svc", redis_password="")
        assert service._redis_password is None

    def test_explicit_password(self):
        """Explicit non-empty password is stored as-is."""
        service = BaseService("svc", redis_password="secret")
        assert service._redis_password == "secret"

    def test_availability_key_format(self):
        """_availability_key follows state:service:{name}:available pattern."""
        service = BaseService("my-service")
        assert service._availability_key == "state:service:my-service:available"

    def test_custom_heartbeat_interval(self):
        """Custom heartbeat_interval is stored correctly."""
        service = BaseService("svc", heartbeat_interval=30)
        assert service._heartbeat_interval == 30
        assert service._key_ttl == 90  # 3×30

    def test_custom_key_ttl_overrides_default(self):
        """Explicit key_ttl overrides the 3× default."""
        service = BaseService("svc", heartbeat_interval=60, key_ttl=200)
        assert service._key_ttl == 200

    def test_custom_logger(self):
        """Custom logger is used instead of module logger."""
        import logging

        custom_logger = logging.getLogger("custom")
        service = BaseService("svc", logger=custom_logger)
        assert service._logger is custom_logger

    def test_service_port_explicit(self):
        """Explicit service_port is stored correctly."""
        service = BaseService("backend", service_port=5050)
        assert service._service_port == 5050

    def test_service_port_none_by_default(self):
        """When service_port is not set and WORKER_PORT is not in env, _service_port is None."""
        import os
        os.environ.pop("WORKER_PORT", None)
        service = BaseService("svc")
        assert service._service_port is None

    def test_service_port_from_worker_port_env(self, monkeypatch):
        """WORKER_PORT env var is used when service_port is not explicitly provided."""
        monkeypatch.setenv("WORKER_PORT", "5052")
        service = BaseService("vite")
        assert service._service_port == 5052


# ---------------------------------------------------------------------------
# Tests – cleanup() method
# ---------------------------------------------------------------------------


class TestBaseServiceCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_deletes_heartbeat_key(self):
        """cleanup() deletes the availability key in Redis."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=1)

        service = _make_service("ollama")

        with patch("redis.asyncio.Redis", return_value=mock_redis):
            await service.cleanup()

        mock_redis.delete.assert_called_once_with("state:service:ollama:available")

    @pytest.mark.asyncio
    async def test_cleanup_logs_success_when_key_deleted(self):
        """cleanup() logs success info when key was present and deleted."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=1)

        service = _make_service("ollama")
        mock_logger = MagicMock()
        service._logger = mock_logger

        with patch("redis.asyncio.Redis", return_value=mock_redis):
            await service.cleanup()

        mock_logger.info.assert_called()
        assert any(
            "deleted" in str(call).lower() or "cleaned" in str(call).lower()
            for call in mock_logger.info.call_args_list
        )

    @pytest.mark.asyncio
    async def test_cleanup_logs_debug_when_key_absent(self):
        """cleanup() logs debug when key was already gone (delete returns 0)."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=0)

        service = _make_service("stable-diffusion")
        mock_logger = MagicMock()
        service._logger = mock_logger

        with patch("redis.asyncio.Redis", return_value=mock_redis):
            await service.cleanup()

        mock_redis.delete.assert_called_once_with("state:service:stable-diffusion:available")
        mock_logger.info.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_handles_redis_error_gracefully(self):
        """cleanup() logs a warning and does not raise when Redis is unreachable."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(side_effect=ConnectionError("Redis down"))

        service = _make_service("ollama")
        mock_logger = MagicMock()
        service._logger = mock_logger

        with patch("redis.asyncio.Redis", return_value=mock_redis):
            await service.cleanup()  # must not raise

        mock_logger.warning.assert_called_once()
        assert "cleanup failed" in mock_logger.warning.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_cleanup_handles_missing_redis_import(self):
        """cleanup() logs a warning and returns when redis-py is not installed."""
        service = _make_service("ollama")
        mock_logger = MagicMock()
        service._logger = mock_logger

        with patch.dict(sys.modules, {"redis": None, "redis.asyncio": None}):
            await service.cleanup()  # must not raise

        mock_logger.warning.assert_called_once()
        assert "redis-py not installed" in mock_logger.warning.call_args[0][0].lower()
