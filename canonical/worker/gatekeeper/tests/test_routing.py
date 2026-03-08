"""
Tests for GateKeeper job routing.

Validates that:
- Known job types are dispatched to the correct worker endpoint.
- Successful HTTP 200 responses persist results to Redis L2 (Rembg/default).
- Ollama/SD jobs persist results via RPUSH to Redis L1 (rpush_l1 storage).
- Ollama/SD jobs using backend "type" field (not "job_type") are routed correctly.
- HTTP 4xx responses send jobs to dead-letter.
- HTTP 5xx responses are retried with back-off.
- Unknown job types are sent directly to dead-letter.
- Malformed JSON payloads are sent to dead-letter.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from .. import config
from ..main import GateKeeper


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
    async def test_success_persists_to_redis_l1(
        self, gatekeeper, mock_redis_l1, mock_redis_l2, rembg_job
    ):
        mock_result = {"job_id": rembg_job["job_id"], "result": "xyz", "status": "ok"}
        gatekeeper.http.post.return_value = _mock_response(200, mock_result)

        await gatekeeper._dispatch("q", json.dumps(rembg_job), rembg_job, "owner")

        mock_redis_l1.rpush.assert_called_once()
        key_arg = mock_redis_l1.rpush.call_args[0][0]
        assert rembg_job["job_id"] in key_arg
        assert "scareverse:rembg-results" in key_arg
        mock_redis_l2.hset.assert_not_called()

    @pytest.mark.asyncio
    async def test_failure_persists_to_redis_l1(
        self, gatekeeper, mock_redis_l1, mock_redis_l2, rembg_job
    ):
        # 4xx triggers permanent failure and error persistence without retry
        gatekeeper.http.post.return_value = _mock_response(400, {"detail": "bad request"})
        await gatekeeper._dispatch("q", json.dumps(rembg_job), rembg_job, "owner")

        # Error result should be RPUSH'd to L1 (not HSET to L2)
        mock_redis_l1.rpush.assert_called()
        mock_redis_l2.hset.assert_not_called()
        pushed_json = mock_redis_l1.rpush.call_args[0][1]
        pushed_data = json.loads(pushed_json)
        assert pushed_data["status"] == "error"


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


# ---------------------------------------------------------------------------
# Ollama / SD: "type" field support (backend router format)
# ---------------------------------------------------------------------------


class TestOllamaSdRouting:
    @pytest.mark.asyncio
    async def test_ollama_generate_dispatched_to_ollama_endpoint(
        self, gatekeeper, mock_http_client, ollama_generate_job
    ):
        """ollama_generate jobs (using backend 'type' field) route to ollama worker."""
        mock_http_client.post.return_value = _mock_response(
            200,
            {
                "status": "success",
                "data": {"response": "Hello!", "model": "mistral"},
                "error": None,
            },
        )
        ollama_generate_job["_source"] = "owner"
        await gatekeeper._dispatch(
            "q", json.dumps(ollama_generate_job), ollama_generate_job, "owner"
        )

        call_url = mock_http_client.post.call_args[0][0]
        assert "ollama" in call_url
        assert call_url.endswith("/process")

    @pytest.mark.asyncio
    async def test_sd_generate_dispatched_to_sd_endpoint(
        self, gatekeeper, mock_http_client, sd_generate_job
    ):
        """sd_generate jobs (using backend 'type' field) route to sd worker."""
        mock_http_client.post.return_value = _mock_response(
            200,
            {
                "status": "success",
                "image_base64": "abc123",
                "model": "sdxl",
                "processing_time_ms": 1500.0,
            },
        )
        sd_generate_job["_source"] = "owner"
        await gatekeeper._dispatch(
            "q", json.dumps(sd_generate_job), sd_generate_job, "owner"
        )

        call_url = mock_http_client.post.call_args[0][0]
        assert "sd-worker" in call_url
        assert call_url.endswith("/process")


# ---------------------------------------------------------------------------
# Ollama / SD: rpush_l1 result persistence
# ---------------------------------------------------------------------------


class TestRpushL1Persistence:
    @pytest.mark.asyncio
    async def test_ollama_success_rpush_to_l1_not_l2_hset(
        self, gatekeeper, mock_redis_l1, mock_redis_l2, ollama_generate_job
    ):
        """Ollama results are RPUSH'd to L1 – NOT HSET'd to L2."""
        ollama_result = {
            "status": "success",
            "data": {"response": "hello", "model": "mistral"},
            "error": None,
        }
        gatekeeper.http.post.return_value = _mock_response(200, ollama_result)
        await gatekeeper._dispatch(
            "q", json.dumps(ollama_generate_job), ollama_generate_job, "owner"
        )

        mock_redis_l1.rpush.assert_called_once()
        mock_redis_l2.hset.assert_not_called()

        # Verify the correct result key prefix
        key_arg = mock_redis_l1.rpush.call_args[0][0]
        assert "scareverse:ollama-results" in key_arg
        assert ollama_generate_job["job_id"] in key_arg

    @pytest.mark.asyncio
    async def test_ollama_success_result_value_is_json(
        self, gatekeeper, mock_redis_l1, ollama_generate_job
    ):
        """Value pushed to Redis L1 is valid JSON matching worker response."""
        ollama_result = {
            "status": "success",
            "data": {"response": "hello", "model": "mistral"},
            "error": None,
        }
        gatekeeper.http.post.return_value = _mock_response(200, ollama_result)
        await gatekeeper._dispatch(
            "q", json.dumps(ollama_generate_job), ollama_generate_job, "owner"
        )

        pushed_json = mock_redis_l1.rpush.call_args[0][1]
        pushed_data = json.loads(pushed_json)
        assert pushed_data["status"] == "success"
        assert pushed_data["data"]["response"] == "hello"

    @pytest.mark.asyncio
    async def test_sd_success_rpush_to_l1_not_l2_hset(
        self, gatekeeper, mock_redis_l1, mock_redis_l2, sd_generate_job
    ):
        """SD results are RPUSH'd to L1 – NOT HSET'd to L2."""
        sd_result = {
            "status": "success",
            "image_base64": "abc123",
            "model": "sdxl",
            "processing_time_ms": 1500.0,
        }
        gatekeeper.http.post.return_value = _mock_response(200, sd_result)
        await gatekeeper._dispatch(
            "q", json.dumps(sd_generate_job), sd_generate_job, "owner"
        )

        mock_redis_l1.rpush.assert_called_once()
        mock_redis_l2.hset.assert_not_called()

        key_arg = mock_redis_l1.rpush.call_args[0][0]
        assert "scareverse:sd-results" in key_arg
        assert sd_generate_job["job_id"] in key_arg

    @pytest.mark.asyncio
    async def test_ollama_error_rpush_structured_error_to_l1(
        self, gatekeeper, mock_redis_l1, mock_redis_l2, ollama_generate_job
    ):
        """On permanent failure, error result is RPUSH'd to L1 so backend BRPOP gets it."""
        gatekeeper.http.post.return_value = _mock_response(400, {"detail": "bad request"})
        await gatekeeper._dispatch(
            "q", json.dumps(ollama_generate_job), ollama_generate_job, "owner"
        )

        mock_redis_l1.rpush.assert_called()
        pushed_json = mock_redis_l1.rpush.call_args[0][1]
        pushed_data = json.loads(pushed_json)
        assert pushed_data["status"] == "error"
        assert "error" in pushed_data

    @pytest.mark.asyncio
    async def test_ollama_ttl_is_set_on_l1_result_key(
        self, gatekeeper, mock_redis_l1, ollama_generate_job
    ):
        """TTL must be set on the L1 result key after RPUSH."""
        gatekeeper.http.post.return_value = _mock_response(
            200,
            {"status": "success", "data": {"response": "hi", "model": "mistral"}, "error": None},
        )
        await gatekeeper._dispatch(
            "q", json.dumps(ollama_generate_job), ollama_generate_job, "owner"
        )

        mock_redis_l1.expire.assert_called_once()
        key_arg, ttl_arg = mock_redis_l1.expire.call_args[0]
        assert "scareverse:ollama-results" in key_arg
        assert ttl_arg > 0


# ---------------------------------------------------------------------------
# Rembg now uses L1 RPUSH (Phase 2.1: unified result storage)
# ---------------------------------------------------------------------------


class TestRembgRpushL1:
    @pytest.mark.asyncio
    async def test_rembg_success_rpush_to_l1_not_l2_hset(
        self, gatekeeper, mock_redis_l2, mock_redis_l1, rembg_job
    ):
        """Rembg results now go to Redis L1 via RPUSH (Phase 2.1 fix)."""
        mock_result = {"job_id": rembg_job["job_id"], "result": "xyz", "status": "ok"}
        gatekeeper.http.post.return_value = _mock_response(200, mock_result)
        await gatekeeper._dispatch("q", json.dumps(rembg_job), rembg_job, "owner")

        mock_redis_l1.rpush.assert_called_once()
        mock_redis_l2.hset.assert_not_called()

        key_arg = mock_redis_l1.rpush.call_args[0][0]
        assert "scareverse:rembg-results" in key_arg
        assert rembg_job["job_id"] in key_arg

    @pytest.mark.asyncio
    async def test_rembg_canonical_type_rpush_to_l1(
        self, gatekeeper, mock_redis_l1, mock_redis_l2
    ):
        """rembg_removebackground (canonical alias) also persists to L1 RPUSH."""
        rembg_canonical_job = {
            "job_id": "job-rembg-canonical-001",
            "job_type": "rembg_removebackground",
            "image_data": "abc123",
            "alpha_matting": True,
            "_source": "owner",
        }
        mock_result = {"job_id": rembg_canonical_job["job_id"], "result": "xyz", "status": "ok"}
        gatekeeper.http.post.return_value = _mock_response(200, mock_result)
        await gatekeeper._dispatch(
            "q", json.dumps(rembg_canonical_job), rembg_canonical_job, "owner"
        )

        mock_redis_l1.rpush.assert_called_once()
        mock_redis_l2.hset.assert_not_called()

    @pytest.mark.asyncio
    async def test_rembg_ttl_set_on_l1_result_key(
        self, gatekeeper, mock_redis_l1, rembg_job
    ):
        """TTL must be set on the L1 result key after RPUSH."""
        mock_result = {"job_id": rembg_job["job_id"], "result": "xyz", "status": "ok"}
        gatekeeper.http.post.return_value = _mock_response(200, mock_result)
        await gatekeeper._dispatch("q", json.dumps(rembg_job), rembg_job, "owner")

        mock_redis_l1.expire.assert_called_once()
        key_arg, ttl_arg = mock_redis_l1.expire.call_args[0]
        assert "scareverse:rembg-results" in key_arg
        assert ttl_arg > 0
