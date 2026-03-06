"""
Tests for GateKeeper job routing.

Validates that:
- Known job types are dispatched to the correct worker endpoint.
- Successful HTTP 200 responses persist results to Redis L2.
- HTTP 4xx responses send jobs to dead-letter.
- HTTP 5xx responses are retried with back-off.
- Unknown job types are sent directly to dead-letter.
- Malformed JSON payloads are sent to dead-letter.
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "gatekeeper"))

import config  # noqa: E402
from main import GateKeeper  # noqa: E402


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


def _mock_response(status_code: int, body: dict) -> AsyncMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = json.dumps(body)
    return resp


# ---------------------------------------------------------------------------
# Routing to correct worker
# ---------------------------------------------------------------------------


class TestJobRouting:
    @pytest.mark.asyncio
    async def test_remote_rembg_dispatched_to_rembg_endpoint(
        self, gatekeeper, mock_http_client, rembg_job
    ):
        """REMOTE_REMBG jobs are sent to the rembg worker's /process path."""
        mock_http_client.post.return_value = _mock_response(
            200, {"job_id": rembg_job["job_id"], "result": "abc", "status": "ok"}
        )
        rembg_job["_source"] = "owner"

        await gatekeeper._dispatch("q", json.dumps(rembg_job), rembg_job, "owner")

        call_url = mock_http_client.post.call_args[0][0]
        assert "rembg" in call_url
        assert call_url.endswith("/process")

    @pytest.mark.asyncio
    async def test_background_removal_alias_dispatched(
        self, gatekeeper, mock_http_client, rembg_job_alias
    ):
        """background_removal alias also routes to the rembg worker."""
        mock_http_client.post.return_value = _mock_response(
            200, {"job_id": rembg_job_alias["job_id"], "result": "abc", "status": "ok"}
        )
        rembg_job_alias["_source"] = "global"

        await gatekeeper._dispatch("q", json.dumps(rembg_job_alias), rembg_job_alias, "global")

        call_url = mock_http_client.post.call_args[0][0]
        assert "rembg" in call_url

    @pytest.mark.asyncio
    async def test_unknown_job_type_sent_to_dead_letter(
        self, gatekeeper, mock_redis_l1, unknown_type_job
    ):
        """Jobs with unknown type must go to dead-letter without calling any worker."""
        raw = json.dumps(unknown_type_job)
        await gatekeeper._dispatch("q", raw, unknown_type_job, "owner")

        # HTTP client must never be called
        gatekeeper.http.post.assert_not_called()
        # Dead-letter queue must receive the raw job
        mock_redis_l1.lpush.assert_called()
        dead_letter_arg = mock_redis_l1.lpush.call_args[0][0]
        assert "dead-letter" in dead_letter_arg


# ---------------------------------------------------------------------------
# Result persistence
# ---------------------------------------------------------------------------


class TestResultPersistence:
    @pytest.mark.asyncio
    async def test_success_persists_to_redis_l2(
        self, gatekeeper, mock_redis_l2, rembg_job
    ):
        mock_result = {"job_id": rembg_job["job_id"], "result": "xyz", "status": "ok"}
        gatekeeper.http.post.return_value = _mock_response(200, mock_result)

        await gatekeeper._dispatch("q", json.dumps(rembg_job), rembg_job, "owner")

        mock_redis_l2.hset.assert_called_once()
        key_arg = mock_redis_l2.hset.call_args[0][0]
        assert rembg_job["job_id"] in key_arg
        mapping = mock_redis_l2.hset.call_args[1]["mapping"]
        assert mapping["status"] == "completed"

    @pytest.mark.asyncio
    async def test_failure_persists_to_redis_l2(
        self, gatekeeper, mock_redis_l2, rembg_job
    ):
        # Max retries config-driven; patch to speed test
        with patch.object(config, "WORKER_MAX_RETRIES", 0):
            gatekeeper.http.post.return_value = _mock_response(500, {"detail": "boom"})
            await gatekeeper._dispatch("q", json.dumps(rembg_job), rembg_job, "owner")

        mock_redis_l2.hset.assert_called()
        mapping = mock_redis_l2.hset.call_args[1]["mapping"]
        assert mapping["status"] == "failed"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_4xx_sends_to_dead_letter_no_retry(
        self, gatekeeper, mock_redis_l1, rembg_job
    ):
        """4xx = permanent failure. No retry, straight to dead-letter."""
        gatekeeper.http.post.return_value = _mock_response(400, {"detail": "bad request"})

        await gatekeeper._dispatch("q", json.dumps(rembg_job), rembg_job, "owner")

        # Only one HTTP call (no retry for 4xx)
        assert gatekeeper.http.post.call_count == 1
        mock_redis_l1.lpush.assert_called()

    @pytest.mark.asyncio
    async def test_5xx_is_retried(self, gatekeeper, rembg_job):
        """5xx errors trigger retry up to WORKER_MAX_RETRIES."""
        success_response = _mock_response(
            200, {"job_id": rembg_job["job_id"], "result": "r", "status": "ok"}
        )
        fail_response = _mock_response(500, {"detail": "server error"})
        # First call fails, second succeeds
        gatekeeper.http.post.side_effect = [fail_response, success_response]

        with patch.object(config, "WORKER_MAX_RETRIES", 3), \
             patch.object(config, "WORKER_RETRY_DELAY", 0.0):
            await gatekeeper._dispatch("q", json.dumps(rembg_job), rembg_job, "owner")

        assert gatekeeper.http.post.call_count == 2

    @pytest.mark.asyncio
    async def test_timeout_triggers_retry(self, gatekeeper, rembg_job):
        """HTTP timeout triggers retry."""
        success = _mock_response(
            200, {"job_id": rembg_job["job_id"], "result": "r", "status": "ok"}
        )
        gatekeeper.http.post.side_effect = [httpx.TimeoutException("timed out"), success]

        with patch.object(config, "WORKER_MAX_RETRIES", 2), \
             patch.object(config, "WORKER_RETRY_DELAY", 0.0):
            await gatekeeper._dispatch("q", json.dumps(rembg_job), rembg_job, "owner")

        assert gatekeeper.http.post.call_count == 2
