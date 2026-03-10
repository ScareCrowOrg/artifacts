"""
End-to-end integration tests: job dispatch through GateKeeper to worker
subprocess and result persistence to Redis L1.

Tests the full pipeline:
  1. Job posted to Redis L1 queue (mocked BRPOP)
  2. GateKeeper._dispatch() routes to subprocess executor
  3. Subprocess executor invokes fake worker
  4. Result persisted to Redis L1 via RPUSH
  5. TTL set on result key

Requires pytest-asyncio.
"""

import json
import sys
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ..main import GateKeeper


# ---------------------------------------------------------------------------
# Minimal 1×1 PNG base64
# ---------------------------------------------------------------------------

_MINIMAL_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_http_client():
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def gatekeeper(mock_redis_l1, mock_redis_l2, mock_http_client):
    return GateKeeper(
        redis_l1=mock_redis_l1,
        redis_l2=mock_redis_l2,
        http_client=mock_http_client,
    )


# ---------------------------------------------------------------------------
# End-to-end: subprocess dispatch → Redis L1 result persistence
# ---------------------------------------------------------------------------


class TestEndToEndSubprocessDispatch:
    @pytest.mark.asyncio
    async def test_rembg_job_dispatched_and_result_persisted(
        self, gatekeeper, mock_redis_l1
    ):
        """
        Full pipeline: GateKeeper._dispatch() → subprocess executor → RPUSH result to L1.

        The subprocess executor is patched so no real process is spawned,
        but all routing, result-wrapping, and Redis persistence code runs.
        """
        job = {
            "job_id": "e2e-rembg-001",
            "job_type": "REMOTE_REMBG",
            "input_data": {"image_base64": _MINIMAL_PNG_B64},
            "_source": "owner",
        }
        expected_result = {"image_base64": "PROCESSED_RESULT_B64"}

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = expected_result
            await gatekeeper._dispatch(
                "scareverse:cpu-jobs:queue",
                json.dumps(job),
                job,
                "owner",
            )

        # 1. Subprocess executor was called
        mock_exec.assert_called_once()
        call_args = mock_exec.call_args
        assert call_args[0][0] == "REMOTE_REMBG"  # job_type
        assert call_args[0][1] == "e2e-rembg-001"  # job_id

        # 2. Result persisted to Redis L1 via RPUSH
        mock_redis_l1.rpush.assert_called_once()
        rpush_key = mock_redis_l1.rpush.call_args[0][0]
        rpush_value = mock_redis_l1.rpush.call_args[0][1]

        assert "rembg-results" in rpush_key
        assert "e2e-rembg-001" in rpush_key

        persisted = json.loads(rpush_value)
        assert persisted["image_base64"] == "PROCESSED_RESULT_B64"

        # 3. TTL set on the result key
        mock_redis_l1.expire.assert_called_once()
        ttl_key, ttl_value = mock_redis_l1.expire.call_args[0]
        assert ttl_key == rpush_key
        assert ttl_value > 0

    @pytest.mark.asyncio
    async def test_rembg_l2_not_touched_on_success(
        self, gatekeeper, mock_redis_l2
    ):
        """L2 (CentralHub) is never written for subprocess rembg workers."""
        job = {
            "job_id": "e2e-rembg-002",
            "job_type": "REMOTE_REMBG",
            "input_data": {"image_base64": _MINIMAL_PNG_B64},
            "_source": "owner",
        }

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"image_base64": "RESULT"}
            await gatekeeper._dispatch(
                "q", json.dumps(job), job, "owner"
            )

        mock_redis_l2.hset.assert_not_called()

    @pytest.mark.asyncio
    async def test_subprocess_error_persists_error_result_to_l1(
        self, gatekeeper, mock_redis_l1
    ):
        """When subprocess raises ValueError, an error payload is RPUSH'd to L1."""
        job = {
            "job_id": "e2e-rembg-003",
            "job_type": "REMOTE_REMBG",
            "input_data": {"image_base64": _MINIMAL_PNG_B64},
            "_source": "owner",
        }

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = ValueError("rembg model load failed")
            await gatekeeper._dispatch(
                "q", json.dumps(job), job, "owner"
            )

        mock_redis_l1.rpush.assert_called()
        rpush_value = mock_redis_l1.rpush.call_args[0][1]
        persisted = json.loads(rpush_value)

        assert persisted["status"] == "error"
        assert "rembg model load failed" in persisted["error"]

    @pytest.mark.asyncio
    async def test_subprocess_timeout_persists_error_and_dead_letters(
        self, gatekeeper, mock_redis_l1
    ):
        """TimeoutError from subprocess is persisted as error and job sent to dead-letter."""
        job = {
            "job_id": "e2e-rembg-timeout",
            "job_type": "REMOTE_REMBG",
            "input_data": {"image_base64": _MINIMAL_PNG_B64},
            "_source": "owner",
        }

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = TimeoutError("Worker exceeded timeout")
            await gatekeeper._dispatch(
                "q", json.dumps(job), job, "owner"
            )

        # Error result persisted to L1
        mock_redis_l1.rpush.assert_called()
        rpush_value = mock_redis_l1.rpush.call_args[0][1]
        persisted = json.loads(rpush_value)
        assert persisted["status"] == "error"

        # Job sent to dead-letter
        mock_redis_l1.lpush.assert_called()
        dl_key = mock_redis_l1.lpush.call_args[0][0]
        assert "dead-letter" in dl_key


# ---------------------------------------------------------------------------
# End-to-end: service worker dispatch (Ollama / SD)
# ---------------------------------------------------------------------------


class TestEndToEndServiceWorkerDispatch:
    @pytest.mark.asyncio
    async def test_ollama_job_dispatched_to_http_and_persisted(
        self, gatekeeper, mock_redis_l1
    ):
        """Ollama jobs go via HTTP and result is RPUSH'd to L1."""
        job = {
            "job_id": "e2e-ollama-001",
            "type": "ollama_generate",
            "payload": {"prompt": "Hello", "model": "mistral", "stream": False, "options": {}},
            "created_at": 0.0,
            "attempts": 0,
            "_source": "owner",
        }
        http_result = {
            "status": "success",
            "data": {"response": "Hi there!", "model": "mistral"},
            "error": None,
        }

        gatekeeper.http.post.return_value = _mock_response(200, http_result)

        await gatekeeper._dispatch("q", json.dumps(job), job, "owner")

        # HTTP endpoint was called
        gatekeeper.http.post.assert_called_once()
        call_url = gatekeeper.http.post.call_args[0][0]
        assert "ollama" in call_url

        # Result persisted to L1
        mock_redis_l1.rpush.assert_called_once()
        rpush_key = mock_redis_l1.rpush.call_args[0][0]
        assert "ollama-results" in rpush_key
        assert "e2e-ollama-001" in rpush_key


# ---------------------------------------------------------------------------
# Unknown job type handling
# ---------------------------------------------------------------------------


class TestUnknownJobTypePipeline:
    @pytest.mark.asyncio
    async def test_unknown_type_sent_to_dead_letter_no_worker_called(
        self, gatekeeper, mock_redis_l1, mock_http_client
    ):
        """Unknown job types go straight to dead-letter, no executor called."""
        job = {
            "job_id": "e2e-unknown-001",
            "job_type": "TOTALLY_UNKNOWN_TYPE",
            "input_data": {},
            "_source": "owner",
        }

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            await gatekeeper._dispatch("q", json.dumps(job), job, "owner")

            mock_exec.assert_not_called()

        mock_http_client.post.assert_not_called()

        mock_redis_l1.lpush.assert_called()
        dl_key = mock_redis_l1.lpush.call_args[0][0]
        assert "dead-letter" in dl_key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(status_code: int, body: dict) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = json.dumps(body)
    return resp
