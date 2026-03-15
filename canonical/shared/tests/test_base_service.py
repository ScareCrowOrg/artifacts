"""
Unit tests for BaseService – Redis heartbeat registration.

Validates:
- heartbeat() sets the correct Redis key with the correct TTL.
- heartbeat() loops (calls set multiple times).
- heartbeat() handles Redis connection failure gracefully (logs, retries).
- heartbeat() handles Redis command error gracefully (logs, continues).
- heartbeat() exits cleanly when redis-py is not installed (ImportError).
- Redis key format: state:service:{name}:available.
- Default TTL is 3× heartbeat_interval.
- Custom redis config and heartbeat_interval / key_ttl are respected.
"""

import asyncio
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
    async def test_sets_correct_key_and_value(self):
        """heartbeat() sets state:service:{name}:available = '1'."""
        mock_redis = AsyncMock()
        service = _make_service("ollama")

        await _run_heartbeat_iterations(service, mock_redis, iterations=1)

        mock_redis.set.assert_called_once_with(
            "state:service:ollama:available", "1", ex=3
        )

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
    async def test_value_is_one(self):
        """Value stored in Redis must be '1'."""
        mock_redis = AsyncMock()
        service = _make_service("stable-diffusion")

        await _run_heartbeat_iterations(service, mock_redis, iterations=1)

        args, _ = mock_redis.set.call_args
        assert args[1] == "1"


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
