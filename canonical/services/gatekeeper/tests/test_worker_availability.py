"""
Unit tests for GateKeeper worker availability mechanism.

Validates:
- _check_docker_health(): returns True when all containers are healthy,
  False when any container is unhealthy/missing/errored.
- _check_worker_availability(): sets/deletes Redis keys correctly based on
  dependency health status.
- Graceful handling of missing docker-py, Docker daemon errors, and
  ImportError.
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
# _check_docker_health tests
# ---------------------------------------------------------------------------


class TestCheckDockerHealth:
    @pytest.mark.asyncio
    async def test_all_healthy_returns_true(self, gatekeeper):
        """All containers healthy → returns True."""
        mock_container = MagicMock()
        mock_container.attrs = {"State": {"Health": {"Status": "healthy"}}}

        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container

        mock_docker = MagicMock()
        mock_docker.from_env.return_value = mock_client

        with patch.dict("sys.modules", {"docker": mock_docker}):
            result = await gatekeeper._check_docker_health(["container-a", "container-b"])

        assert result is True

    @pytest.mark.asyncio
    async def test_unhealthy_container_returns_false(self, gatekeeper):
        """Container with 'unhealthy' status → returns False."""
        mock_container = MagicMock()
        mock_container.attrs = {"State": {"Health": {"Status": "unhealthy"}}}

        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container

        mock_docker = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_docker.errors = MagicMock()
        mock_docker.errors.NotFound = Exception

        with patch.dict("sys.modules", {"docker": mock_docker}):
            result = await gatekeeper._check_docker_health(["container-a"])

        assert result is False

    @pytest.mark.asyncio
    async def test_starting_container_returns_false(self, gatekeeper):
        """Container with 'starting' status → returns False."""
        mock_container = MagicMock()
        mock_container.attrs = {"State": {"Health": {"Status": "starting"}}}

        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container

        mock_docker = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_docker.errors = MagicMock()
        mock_docker.errors.NotFound = Exception

        with patch.dict("sys.modules", {"docker": mock_docker}):
            result = await gatekeeper._check_docker_health(["container-a"])

        assert result is False

    @pytest.mark.asyncio
    async def test_container_not_found_returns_false(self, gatekeeper):
        """Container not found (NotFound exception) → returns False."""

        class NotFound(Exception):
            pass

        mock_client = MagicMock()
        mock_client.containers.get.side_effect = NotFound("not found")

        mock_docker = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_docker.errors = MagicMock()
        mock_docker.errors.NotFound = NotFound

        with patch.dict("sys.modules", {"docker": mock_docker}):
            result = await gatekeeper._check_docker_health(["missing-container"])

        assert result is False

    @pytest.mark.asyncio
    async def test_import_error_assumes_healthy(self, gatekeeper):
        """docker-py not installed → assumes healthy (returns True)."""
        import sys

        original = sys.modules.pop("docker", None)
        try:
            result = await gatekeeper._check_docker_health(["some-container"])
        finally:
            if original is not None:
                sys.modules["docker"] = original

        assert result is True

    @pytest.mark.asyncio
    async def test_docker_daemon_error_returns_false(self, gatekeeper):
        """Unexpected Docker daemon error → returns False."""
        mock_docker = MagicMock()
        mock_docker.from_env.side_effect = Exception("Cannot connect to Docker daemon")

        with patch.dict("sys.modules", {"docker": mock_docker}):
            result = await gatekeeper._check_docker_health(["container-a"])

        assert result is False

    @pytest.mark.asyncio
    async def test_empty_list_returns_true(self, gatekeeper):
        """Empty container list → no checks needed, returns True."""
        mock_docker = MagicMock()
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client

        with patch.dict("sys.modules", {"docker": mock_docker}):
            result = await gatekeeper._check_docker_health([])

        assert result is True
        mock_client.containers.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_second_container_unhealthy_returns_false(self, gatekeeper):
        """First container healthy, second unhealthy → returns False."""

        class NotFound(Exception):
            pass

        healthy_container = MagicMock()
        healthy_container.attrs = {"State": {"Health": {"Status": "healthy"}}}

        unhealthy_container = MagicMock()
        unhealthy_container.attrs = {"State": {"Health": {"Status": "unhealthy"}}}

        mock_client = MagicMock()
        mock_client.containers.get.side_effect = [healthy_container, unhealthy_container]

        mock_docker = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_docker.errors = MagicMock()
        mock_docker.errors.NotFound = NotFound

        with patch.dict("sys.modules", {"docker": mock_docker}):
            result = await gatekeeper._check_docker_health(["healthy-c", "unhealthy-c"])

        assert result is False


# ---------------------------------------------------------------------------
# _check_worker_availability tests
# ---------------------------------------------------------------------------


class TestCheckWorkerAvailability:
    @pytest.mark.asyncio
    async def test_sets_key_for_no_dependency_job_types(self, gatekeeper, mock_redis_l1):
        """Job-types without dependencies always set the availability key."""
        import config as config_module

        job_types_config: Dict[str, Any] = {
            "rembg_removebackground": {
                "dependencies": [],
            }
        }

        async def fake_sleep(_delay):
            raise asyncio.CancelledError

        with patch.object(config_module, "JOB_TYPES_CONFIG", job_types_config), \
             patch.object(config_module, "VENV_HEALTH_CHECK_INTERVAL", 60), \
             patch("asyncio.sleep", side_effect=fake_sleep):
            try:
                await gatekeeper._check_worker_availability()
            except asyncio.CancelledError:
                pass

        mock_redis_l1.set.assert_called_once_with(
            "state:worker:rembg_removebackground:available", "1", ex=120
        )

    @pytest.mark.asyncio
    async def test_sets_key_when_dependencies_healthy(self, gatekeeper, mock_redis_l1):
        """Job-types with healthy dependencies get availability key set."""
        import config as config_module

        job_types_config: Dict[str, Any] = {
            "sd_generate": {
                "dependencies": ["stable-diffusion"],
            }
        }

        async def fake_sleep(_delay):
            raise asyncio.CancelledError

        with patch.object(config_module, "JOB_TYPES_CONFIG", job_types_config), \
             patch.object(config_module, "VENV_HEALTH_CHECK_INTERVAL", 60), \
             patch.object(
                 gatekeeper, "_check_docker_health", new=AsyncMock(return_value=True)
             ), \
             patch("asyncio.sleep", side_effect=fake_sleep):
            try:
                await gatekeeper._check_worker_availability()
            except asyncio.CancelledError:
                pass

        mock_redis_l1.set.assert_called_once_with(
            "state:worker:sd_generate:available", "1", ex=120
        )

    @pytest.mark.asyncio
    async def test_deletes_key_when_dependencies_unhealthy(
        self, gatekeeper, mock_redis_l1
    ):
        """Job-types with unhealthy dependencies get availability key deleted."""
        import config as config_module

        job_types_config: Dict[str, Any] = {
            "sd_generate": {
                "dependencies": ["stable-diffusion"],
            }
        }

        async def fake_sleep(_delay):
            raise asyncio.CancelledError

        with patch.object(config_module, "JOB_TYPES_CONFIG", job_types_config), \
             patch.object(config_module, "VENV_HEALTH_CHECK_INTERVAL", 60), \
             patch.object(
                 gatekeeper, "_check_docker_health", new=AsyncMock(return_value=False)
             ), \
             patch("asyncio.sleep", side_effect=fake_sleep):
            try:
                await gatekeeper._check_worker_availability()
            except asyncio.CancelledError:
                pass

        mock_redis_l1.delete.assert_called_once_with(
            "state:worker:sd_generate:available"
        )
        mock_redis_l1.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_exception_does_not_crash_loop(self, gatekeeper, mock_redis_l1):
        """Exception inside loop is caught; loop continues to next iteration."""
        import config as config_module

        call_count = 0

        async def fake_sleep(_delay):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError

        with patch.object(
            config_module,
            "JOB_TYPES_CONFIG",
            {"sd_generate": {"dependencies": ["sd"]}},
        ), patch.object(config_module, "VENV_HEALTH_CHECK_INTERVAL", 60), patch.object(
            gatekeeper,
            "_check_docker_health",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ), patch(
            "asyncio.sleep", side_effect=fake_sleep
        ):
            try:
                await gatekeeper._check_worker_availability()
            except asyncio.CancelledError:
                pass

        # Loop ran and slept at least once after recovering from exception
        assert call_count >= 1



# ---------------------------------------------------------------------------
# _check_docker_health tests
# ---------------------------------------------------------------------------


class TestCheckDockerHealth:
    @pytest.mark.asyncio
    async def test_all_healthy_returns_true(self, gatekeeper):
        """All containers healthy → returns True."""
        mock_container = MagicMock()
        mock_container.attrs = {"State": {"Health": {"Status": "healthy"}}}

        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container

        mock_docker = MagicMock()
        mock_docker.from_env.return_value = mock_client

        with patch.dict("sys.modules", {"docker": mock_docker}):
            result = await gatekeeper._check_docker_health(["container-a", "container-b"])

        assert result is True

    @pytest.mark.asyncio
    async def test_unhealthy_container_returns_false(self, gatekeeper):
        """Container with 'unhealthy' status → returns False."""
        mock_container = MagicMock()
        mock_container.attrs = {"State": {"Health": {"Status": "unhealthy"}}}

        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container

        mock_docker = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_docker.errors = MagicMock()
        mock_docker.errors.NotFound = Exception

        with patch.dict("sys.modules", {"docker": mock_docker}):
            result = await gatekeeper._check_docker_health(["container-a"])

        assert result is False

    @pytest.mark.asyncio
    async def test_starting_container_returns_false(self, gatekeeper):
        """Container with 'starting' status → returns False."""
        mock_container = MagicMock()
        mock_container.attrs = {"State": {"Health": {"Status": "starting"}}}

        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container

        mock_docker = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_docker.errors = MagicMock()
        mock_docker.errors.NotFound = Exception

        with patch.dict("sys.modules", {"docker": mock_docker}):
            result = await gatekeeper._check_docker_health(["container-a"])

        assert result is False

    @pytest.mark.asyncio
    async def test_container_not_found_returns_false(self, gatekeeper):
        """Container not found (NotFound exception) → returns False."""

        class NotFound(Exception):
            pass

        mock_client = MagicMock()
        mock_client.containers.get.side_effect = NotFound("not found")

        mock_docker = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_docker.errors = MagicMock()
        mock_docker.errors.NotFound = NotFound

        with patch.dict("sys.modules", {"docker": mock_docker}):
            result = await gatekeeper._check_docker_health(["missing-container"])

        assert result is False

    @pytest.mark.asyncio
    async def test_import_error_assumes_healthy(self, gatekeeper):
        """docker-py not installed → assumes healthy (returns True)."""
        import sys

        original = sys.modules.pop("docker", None)
        try:
            result = await gatekeeper._check_docker_health(["some-container"])
        finally:
            if original is not None:
                sys.modules["docker"] = original

        assert result is True

    @pytest.mark.asyncio
    async def test_docker_daemon_error_returns_false(self, gatekeeper):
        """Unexpected Docker daemon error → returns False."""
        mock_docker = MagicMock()
        mock_docker.from_env.side_effect = Exception("Cannot connect to Docker daemon")

        with patch.dict("sys.modules", {"docker": mock_docker}):
            result = await gatekeeper._check_docker_health(["container-a"])

        assert result is False

    @pytest.mark.asyncio
    async def test_empty_list_returns_true(self, gatekeeper):
        """Empty container list → no checks needed, returns True."""
        mock_docker = MagicMock()
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client

        with patch.dict("sys.modules", {"docker": mock_docker}):
            result = await gatekeeper._check_docker_health([])

        assert result is True
        mock_client.containers.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_second_container_unhealthy_returns_false(self, gatekeeper):
        """First container healthy, second unhealthy → returns False."""

        class NotFound(Exception):
            pass

        healthy_container = MagicMock()
        healthy_container.attrs = {"State": {"Health": {"Status": "healthy"}}}

        unhealthy_container = MagicMock()
        unhealthy_container.attrs = {"State": {"Health": {"Status": "unhealthy"}}}

        mock_client = MagicMock()
        mock_client.containers.get.side_effect = [healthy_container, unhealthy_container]

        mock_docker = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_docker.errors = MagicMock()
        mock_docker.errors.NotFound = NotFound

        with patch.dict("sys.modules", {"docker": mock_docker}):
            result = await gatekeeper._check_docker_health(["healthy-c", "unhealthy-c"])

        assert result is False


# ---------------------------------------------------------------------------
# _check_worker_availability tests
# ---------------------------------------------------------------------------


class TestCheckWorkerAvailability:
    @pytest.mark.asyncio
    async def test_sets_key_for_no_dependency_job_types(self, gatekeeper, mock_redis_l1):
        """Job-types without dependencies always set the availability key."""
        job_types_config: Dict[str, Any] = {
            "rembg_removebackground": {
                "dependencies": [],
            }
        }

        _shutdown_calls = 0

        async def run_once():
            nonlocal _shutdown_calls
            # Patch sleep to raise after first iteration
            original_sleep = asyncio.sleep

            async def fake_sleep(_delay):
                raise asyncio.CancelledError

            with patch("main.config") as mock_cfg:
                mock_cfg.JOB_TYPES_CONFIG = job_types_config
                mock_cfg.VENV_HEALTH_CHECK_INTERVAL = 60
                with patch("asyncio.sleep", side_effect=fake_sleep):
                    try:
                        await gatekeeper._check_worker_availability()
                    except asyncio.CancelledError:
                        pass

        await run_once()

        mock_redis_l1.set.assert_called_once_with(
            "state:worker:rembg_removebackground:available", "1", ex=120
        )

    @pytest.mark.asyncio
    async def test_sets_key_when_dependencies_healthy(self, gatekeeper, mock_redis_l1):
        """Job-types with healthy dependencies get availability key set."""
        job_types_config: Dict[str, Any] = {
            "sd_generate": {
                "dependencies": ["stable-diffusion"],
            }
        }

        async def fake_sleep(_delay):
            raise asyncio.CancelledError

        with patch("main.config") as mock_cfg:
            mock_cfg.JOB_TYPES_CONFIG = job_types_config
            mock_cfg.VENV_HEALTH_CHECK_INTERVAL = 60
            with patch.object(
                gatekeeper, "_check_docker_health", new=AsyncMock(return_value=True)
            ):
                with patch("asyncio.sleep", side_effect=fake_sleep):
                    try:
                        await gatekeeper._check_worker_availability()
                    except asyncio.CancelledError:
                        pass

        mock_redis_l1.set.assert_called_once_with(
            "state:worker:sd_generate:available", "1", ex=120
        )

    @pytest.mark.asyncio
    async def test_deletes_key_when_dependencies_unhealthy(
        self, gatekeeper, mock_redis_l1
    ):
        """Job-types with unhealthy dependencies get availability key deleted."""
        job_types_config: Dict[str, Any] = {
            "sd_generate": {
                "dependencies": ["stable-diffusion"],
            }
        }

        async def fake_sleep(_delay):
            raise asyncio.CancelledError

        with patch("main.config") as mock_cfg:
            mock_cfg.JOB_TYPES_CONFIG = job_types_config
            mock_cfg.VENV_HEALTH_CHECK_INTERVAL = 60
            with patch.object(
                gatekeeper, "_check_docker_health", new=AsyncMock(return_value=False)
            ):
                with patch("asyncio.sleep", side_effect=fake_sleep):
                    try:
                        await gatekeeper._check_worker_availability()
                    except asyncio.CancelledError:
                        pass

        mock_redis_l1.delete.assert_called_once_with(
            "state:worker:sd_generate:available"
        )
        mock_redis_l1.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_exception_does_not_crash_loop(self, gatekeeper, mock_redis_l1):
        """Exception inside loop is caught; loop continues to next iteration."""
        call_count = 0

        async def fake_sleep(_delay):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError

        with patch("main.config") as mock_cfg:
            mock_cfg.JOB_TYPES_CONFIG = {"sd_generate": {"dependencies": ["sd"]}}
            mock_cfg.VENV_HEALTH_CHECK_INTERVAL = 60
            with patch.object(
                gatekeeper,
                "_check_docker_health",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ):
                with patch("asyncio.sleep", side_effect=fake_sleep):
                    try:
                        await gatekeeper._check_worker_availability()
                    except asyncio.CancelledError:
                        pass

        # Loop ran and slept at least once after recovering from exception
        assert call_count >= 1
