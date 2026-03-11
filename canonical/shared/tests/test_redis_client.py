"""
Unit tests for redis_client.py – capability-based job routing.

Validates:
- _check_local_gatekeeper_can_serve(): returns True when job-type is in
  serving list, False when missing, and False on errors or missing key.
- create_job(): routes service job-types to L1 when GateKeeper capable,
  falls back to L2 when incapable or registry missing.
- create_job(): subprocess job-types bypass capability check (always L1).
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import helpers: ensure shared/ is on sys.path
# ---------------------------------------------------------------------------

_shared_dir = Path(__file__).resolve().parents[1]
if str(_shared_dir) not in sys.path:
    sys.path.insert(0, str(_shared_dir))

from redis_client import (  # noqa: E402
    _check_local_gatekeeper_can_serve,
    _reset_job_type_map,
    reset_redis_client,
)


# ---------------------------------------------------------------------------
# _check_local_gatekeeper_can_serve tests
# ---------------------------------------------------------------------------


class TestCheckLocalGatekeeperCanServe:
    @pytest.mark.asyncio
    async def test_returns_true_when_job_type_in_serving_list(self):
        """Job-type present in serving_job_types → True."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(
            return_value=json.dumps(["sd_generate", "ollama_generate"])
        )

        result = await _check_local_gatekeeper_can_serve(
            mock_redis, "sd_generate", worker_id="gk-test"
        )
        assert result is True
        mock_redis.get.assert_called_once_with(
            "state:gatekeeper:gk-test:serving_job_types"
        )

    @pytest.mark.asyncio
    async def test_returns_false_when_job_type_not_in_serving_list(self):
        """Job-type absent from serving_job_types → False."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(
            return_value=json.dumps(["ollama_generate", "rembg_removebackground"])
        )

        result = await _check_local_gatekeeper_can_serve(
            mock_redis, "sd_generate", worker_id="gk-test"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_registry_key_missing(self):
        """Missing capability registry key → False (graceful fallback)."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        result = await _check_local_gatekeeper_can_serve(
            mock_redis, "sd_generate", worker_id="gk-test"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_invalid_json(self):
        """Corrupted JSON value in Redis → False (graceful fallback)."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="not-valid-json[{")

        result = await _check_local_gatekeeper_can_serve(
            mock_redis, "sd_generate", worker_id="gk-test"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_redis_error(self):
        """Redis exception during GET → False (graceful fallback)."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))

        result = await _check_local_gatekeeper_can_serve(
            mock_redis, "sd_generate", worker_id="gk-test"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_uses_default_worker_id_from_env(self):
        """Without explicit worker_id, falls back to WORKER_ID env var."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(["sd_generate"]))

        with patch("redis_client.WORKER_ID", "gk-from-env"):
            result = await _check_local_gatekeeper_can_serve(
                mock_redis, "sd_generate"
            )

        assert result is True
        mock_redis.get.assert_called_once_with(
            "state:gatekeeper:gk-from-env:serving_job_types"
        )


# ---------------------------------------------------------------------------
# create_job capability routing tests
# ---------------------------------------------------------------------------


def _make_job_type_map(execution_model: str = "service") -> Dict[str, Any]:
    """Build a minimal job-type map for testing."""
    entry = {
        "queue": "scareverse:cpu-jobs:queue",
        "dependencies": [],
        "execution_model": execution_model,
    }
    return {
        "sd_generate": {**entry, "dependencies": ["stable-diffusion"]},
        "ollama_generate": entry,
        "rembg_removebackground": {**entry, "execution_model": "subprocess"},
    }


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset redis_client module singletons between tests."""
    reset_redis_client()
    _reset_job_type_map()
    yield
    reset_redis_client()
    _reset_job_type_map()


@pytest.mark.asyncio
async def test_service_job_type_without_local_capability_goes_to_l2():
    """
    Job-type with no local GateKeeper capability should fallback to L2.

    Setup: serving_job_types = ["ollama_generate"]
    Request: create_job("sd_generate")
    Expected: Fallback to L2, return ("job_id", "l2")
    """
    from redis_client import create_job

    mock_redis = AsyncMock()

    def _side_effect(key):
        if key == "state:service:stable-diffusion:available":
            return "1"  # service IS available
        return json.dumps(["ollama_generate"])  # sd_generate NOT in serving list

    mock_redis.get = AsyncMock(side_effect=_side_effect)

    job_type_map = _make_job_type_map()

    with patch("redis_client.get_redis_client", return_value=mock_redis), \
         patch("redis_client._get_job_type_map", return_value=job_type_map), \
         patch("redis_client._enqueue_via_centralhub", new_callable=AsyncMock) as mock_l2:

        job_id, destination = await create_job(
            "sd_generate", {"prompt": "ghost"}, "user-1", job_id="job-test-1"
        )

    assert destination == "l2"
    assert job_id == "job-test-1"
    mock_l2.assert_called_once()
    mock_redis.lpush.assert_not_called()


@pytest.mark.asyncio
async def test_service_job_type_with_local_capability_goes_to_l1():
    """
    Job-type with local GateKeeper capability should enqueue to L1.

    Setup: serving_job_types = ["sd_generate"], stable-diffusion available
    Request: create_job("sd_generate")
    Expected: Enqueue to L1, return ("job_id", "l1")
    """
    from redis_client import create_job

    mock_redis = AsyncMock()

    def _side_effect(key):
        if key == "state:service:stable-diffusion:available":
            return "1"  # service IS available
        return json.dumps(["sd_generate", "ollama_generate"])  # sd_generate IS in serving list

    mock_redis.get = AsyncMock(side_effect=_side_effect)
    mock_redis.lpush = AsyncMock(return_value=1)

    job_type_map = _make_job_type_map()

    with patch("redis_client.get_redis_client", return_value=mock_redis), \
         patch("redis_client._get_job_type_map", return_value=job_type_map), \
         patch("redis_client._enqueue_via_centralhub", new_callable=AsyncMock) as mock_l2:

        job_id, destination = await create_job(
            "sd_generate", {"prompt": "ghost"}, "user-1", job_id="job-test-2"
        )

    assert destination == "l1"
    assert job_id == "job-test-2"
    mock_redis.lpush.assert_called_once()
    mock_l2.assert_not_called()


@pytest.mark.asyncio
async def test_subprocess_job_type_ignores_capability_check():
    """
    Subprocess job-types should skip the capability check (always local).

    Setup: serving_job_types does NOT include rembg_removebackground
    Request: create_job("rembg_removebackground", execution_model="subprocess")
    Expected: Enqueue to L1 anyway, return ("job_id", "l1")
    """
    from redis_client import create_job

    mock_redis = AsyncMock()
    # No service dependencies for subprocess → _all_services_available returns True
    # serving list does not include the subprocess job-type
    mock_redis.get = AsyncMock(return_value=json.dumps(["ollama_generate"]))
    mock_redis.lpush = AsyncMock(return_value=1)

    job_type_map = _make_job_type_map()

    with patch("redis_client.get_redis_client", return_value=mock_redis), \
         patch("redis_client._get_job_type_map", return_value=job_type_map), \
         patch("redis_client._enqueue_via_centralhub", new_callable=AsyncMock) as mock_l2:

        job_id, destination = await create_job(
            "rembg_removebackground",
            {"image_base64": "abc123"},
            "user-1",
            job_id="job-test-3",
        )

    assert destination == "l1"
    assert job_id == "job-test-3"
    mock_redis.lpush.assert_called_once()
    mock_l2.assert_not_called()


@pytest.mark.asyncio
async def test_missing_capability_registry_falls_back_to_l2():
    """
    If capability registry key is missing (GateKeeper just started), fallback to L2.

    Setup: state:gatekeeper:gk-1:serving_job_types = MISSING
           stable-diffusion service IS available
    Request: create_job("sd_generate")
    Expected: Fallback to L2, return ("job_id", "l2")
    """
    from redis_client import create_job

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=lambda key: (
        "1" if "state:service:stable-diffusion:available" in key
        else None  # capability key is MISSING
    ))

    job_type_map = _make_job_type_map()

    with patch("redis_client.get_redis_client", return_value=mock_redis), \
         patch("redis_client._get_job_type_map", return_value=job_type_map), \
         patch("redis_client._enqueue_via_centralhub", new_callable=AsyncMock) as mock_l2:

        job_id, destination = await create_job(
            "sd_generate", {"prompt": "ghost"}, "user-1", job_id="job-test-4"
        )

    assert destination == "l2"
    assert job_id == "job-test-4"
    mock_l2.assert_called_once()
    mock_redis.lpush.assert_not_called()


@pytest.mark.asyncio
async def test_service_unavailable_routes_to_l2_without_capability_check():
    """
    When service dependencies are unavailable, skip capability check and go to L2.
    """
    from redis_client import create_job

    mock_redis = AsyncMock()
    # stable-diffusion NOT available
    mock_redis.get = AsyncMock(return_value=None)

    job_type_map = _make_job_type_map()

    with patch("redis_client.get_redis_client", return_value=mock_redis), \
         patch("redis_client._get_job_type_map", return_value=job_type_map), \
         patch("redis_client._enqueue_via_centralhub", new_callable=AsyncMock) as mock_l2:

        job_id, destination = await create_job(
            "sd_generate", {"prompt": "ghost"}, "user-1", job_id="job-test-5"
        )

    assert destination == "l2"
    mock_l2.assert_called_once()
    mock_redis.lpush.assert_not_called()
