"""
Tests for GateKeeper job routing.

Validates that:
- Service worker jobs (Ollama, SD) are dispatched via HTTP to correct endpoints.
- Subprocess worker jobs (Rembg) are dispatched via subprocess executor.
- Successful HTTP 200 responses persist results to Redis L1 (rpush_l1).
- Ollama/SD jobs using backend "type" field (not "job_type") are routed correctly.
- HTTP 4xx responses send jobs to dead-letter.
- HTTP 5xx responses are retried with back-off.
- Unknown job types are sent directly to dead-letter.
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
    async def test_remote_rembg_dispatched_via_subprocess(
        self, gatekeeper, mock_http_client, rembg_job
    ):
        """REMOTE_REMBG jobs are dispatched via subprocess (not HTTP) in new architecture."""
        rembg_job["_source"] = "owner"
        mock_result = {"image_base64": "abc123"}

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result
            await gatekeeper._dispatch("q", json.dumps(rembg_job), rembg_job, "owner")

        # HTTP client must NOT be called for subprocess workers
        mock_http_client.post.assert_not_called()
        mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_background_removal_alias_dispatched_via_subprocess(
        self, gatekeeper, mock_http_client, rembg_job_alias
    ):
        """background_removal alias also routes to subprocess executor."""
        rembg_job_alias["_source"] = "global"
        mock_result = {"image_base64": "abc123"}

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result
            await gatekeeper._dispatch("q", json.dumps(rembg_job_alias), rembg_job_alias, "global")

        mock_http_client.post.assert_not_called()
        mock_exec.assert_called_once()

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
# Result persistence (subprocess workers – rembg)
# ---------------------------------------------------------------------------


class TestRembgResultPersistence:
    @pytest.mark.asyncio
    async def test_rembg_success_persists_to_redis_l1(
        self, gatekeeper, mock_redis_l1, mock_redis_l2, rembg_job
    ):
        mock_result = {"image_base64": "xyz123"}

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result
            await gatekeeper._dispatch("q", json.dumps(rembg_job), rembg_job, "owner")

        mock_redis_l1.rpush.assert_called_once()
        key_arg = mock_redis_l1.rpush.call_args[0][0]
        assert rembg_job["job_id"] in key_arg
        assert "scareverse:rembg-results" in key_arg
        mock_redis_l2.hset.assert_not_called()

    @pytest.mark.asyncio
    async def test_rembg_subprocess_failure_persists_error_to_l1(
        self, gatekeeper, mock_redis_l1, mock_redis_l2, rembg_job
    ):
        """When subprocess fails, error result should be RPUSH'd to L1."""
        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = ValueError("Worker failed: rembg error")
            await gatekeeper._dispatch("q", json.dumps(rembg_job), rembg_job, "owner")

        mock_redis_l1.rpush.assert_called()
        mock_redis_l2.hset.assert_not_called()
        pushed_json = mock_redis_l1.rpush.call_args[0][1]
        pushed_data = json.loads(pushed_json)
        assert pushed_data["status"] == "error"


# ---------------------------------------------------------------------------
# Ollama / SD: "type" field support (backend router format)
# ---------------------------------------------------------------------------


class TestOllamaSdRouting:
    @pytest.mark.asyncio
    async def test_ollama_generate_dispatched_to_ollama_endpoint(
        self, gatekeeper, mock_http_client, ollama_generate_job
    ):
        """ollama_generate jobs route to ollama service via HTTP."""
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
        """sd_generate jobs route to stable diffusion service via HTTP."""
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
        assert "sd" in call_url
        assert call_url.endswith("/process")


# ---------------------------------------------------------------------------
# Error handling for service workers
# ---------------------------------------------------------------------------


class TestServiceWorkerErrorHandling:
    @pytest.mark.asyncio
    async def test_4xx_sends_to_dead_letter_no_retry(
        self, gatekeeper, mock_redis_l1, ollama_generate_job
    ):
        """4xx = permanent failure. No retry, straight to dead-letter."""
        gatekeeper.http.post.return_value = _mock_response(400, {"detail": "bad request"})

        await gatekeeper._dispatch("q", json.dumps(ollama_generate_job), ollama_generate_job, "owner")

        assert gatekeeper.http.post.call_count == 1
        mock_redis_l1.lpush.assert_called()

    @pytest.mark.asyncio
    async def test_5xx_is_retried(self, gatekeeper, ollama_generate_job):
        """5xx errors trigger retry up to WORKER_MAX_RETRIES."""
        success_response = _mock_response(
            200, {"status": "success", "data": {"response": "hi"}, "error": None}
        )
        fail_response = _mock_response(500, {"detail": "server error"})
        gatekeeper.http.post.side_effect = [fail_response, success_response]

        with patch.object(config, "WORKER_MAX_RETRIES", 3), \
             patch.object(config, "WORKER_RETRY_DELAY", 0.0):
            await gatekeeper._dispatch("q", json.dumps(ollama_generate_job), ollama_generate_job, "owner")

        assert gatekeeper.http.post.call_count == 2

    @pytest.mark.asyncio
    async def test_timeout_triggers_retry(self, gatekeeper, ollama_generate_job):
        """HTTP timeout triggers retry."""
        success = _mock_response(
            200, {"status": "success", "data": {"response": "hi"}, "error": None}
        )
        gatekeeper.http.post.side_effect = [httpx.TimeoutException("timed out"), success]

        with patch.object(config, "WORKER_MAX_RETRIES", 2), \
             patch.object(config, "WORKER_RETRY_DELAY", 0.0):
            await gatekeeper._dispatch("q", json.dumps(ollama_generate_job), ollama_generate_job, "owner")

        assert gatekeeper.http.post.call_count == 2


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

        key_arg = mock_redis_l1.rpush.call_args[0][0]
        assert "scareverse:ollama-results" in key_arg
        assert ollama_generate_job["job_id"] in key_arg

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

    @pytest.mark.asyncio
    async def test_rembg_success_rpush_to_l1_not_l2_hset(
        self, gatekeeper, mock_redis_l2, mock_redis_l1, rembg_job
    ):
        """Rembg results go to Redis L1 via RPUSH (subprocess model)."""
        mock_result = {"image_base64": "xyz123"}

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result
            await gatekeeper._dispatch("q", json.dumps(rembg_job), rembg_job, "owner")

        mock_redis_l1.rpush.assert_called_once()
        mock_redis_l2.hset.assert_not_called()

        key_arg = mock_redis_l1.rpush.call_args[0][0]
        assert "scareverse:rembg-results" in key_arg
        assert rembg_job["job_id"] in key_arg

    @pytest.mark.asyncio
    async def test_rembg_ttl_set_on_l1_result_key(
        self, gatekeeper, mock_redis_l1, rembg_job
    ):
        """TTL must be set on the L1 result key after RPUSH."""
        mock_result = {"image_base64": "xyz123"}

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_result
            await gatekeeper._dispatch("q", json.dumps(rembg_job), rembg_job, "owner")

        mock_redis_l1.expire.assert_called_once()
        key_arg, ttl_arg = mock_redis_l1.expire.call_args[0]
        assert "scareverse:rembg-results" in key_arg
        assert ttl_arg > 0
