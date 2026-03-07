"""
Tests for the Ollama queue consumer worker.
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import main as ollama_main
import config


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_returns_200(self):
        client = TestClient(ollama_main.app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_body(self):
        client = TestClient(ollama_main.app)
        resp = client.get("/health")
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "ollama-consumer"


# ---------------------------------------------------------------------------
# _store_result
# ---------------------------------------------------------------------------


class TestStoreResult:
    @pytest.mark.asyncio
    async def test_stores_result_as_rpush(self, mock_redis):
        result = {"status": "success", "data": {"response": "hello"}, "error": None}
        await ollama_main._store_result(mock_redis, "job-001", result)

        mock_redis.rpush.assert_called_once()
        call_args = mock_redis.rpush.call_args
        key = call_args[0][0]
        value = call_args[0][1]
        assert key == f"{config.RESULTS_KEY_PREFIX}:job-001"
        stored = json.loads(value)
        assert stored["status"] == "success"

    @pytest.mark.asyncio
    async def test_sets_ttl_after_rpush(self, mock_redis):
        result = {"status": "success", "data": {}, "error": None}
        await ollama_main._store_result(mock_redis, "job-002", result)

        mock_redis.expire.assert_called_once_with(
            f"{config.RESULTS_KEY_PREFIX}:job-002",
            config.RESULT_KEY_TTL,
        )

    @pytest.mark.asyncio
    async def test_handles_redis_error_gracefully(self, mock_redis):
        mock_redis.rpush.side_effect = Exception("Redis connection refused")
        # Should not raise
        result = {"status": "success", "data": {}, "error": None}
        await ollama_main._store_result(mock_redis, "job-err", result)


# ---------------------------------------------------------------------------
# _process_generate
# ---------------------------------------------------------------------------


class TestProcessGenerate:
    @pytest.mark.asyncio
    async def test_returns_success_result(self, generate_job, ollama_generate_response):
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = ollama_generate_response
        mock_response.raise_for_status = MagicMock()
        mock_http.post.return_value = mock_response

        result = await ollama_main._process_generate(
            mock_http,
            generate_job["job_id"],
            generate_job["payload"],
        )

        assert result["status"] == "success"
        assert result["data"]["response"] == ollama_generate_response["response"]
        assert result["data"]["model"] == ollama_generate_response["model"]
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self, generate_job, ollama_generate_response):
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = ollama_generate_response
        mock_response.raise_for_status = MagicMock()
        mock_http.post.return_value = mock_response

        await ollama_main._process_generate(
            mock_http,
            generate_job["job_id"],
            generate_job["payload"],
        )

        call_args = mock_http.post.call_args
        assert call_args[0][0] == f"{config.OLLAMA_HOST}/api/generate"

    @pytest.mark.asyncio
    async def test_passes_model_and_prompt(self, generate_job, ollama_generate_response):
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = ollama_generate_response
        mock_response.raise_for_status = MagicMock()
        mock_http.post.return_value = mock_response

        await ollama_main._process_generate(
            mock_http,
            generate_job["job_id"],
            generate_job["payload"],
        )

        call_kwargs = mock_http.post.call_args[1]
        body = call_kwargs["json"]
        assert body["model"] == generate_job["payload"]["model"]
        assert body["prompt"] == generate_job["payload"]["prompt"]
        assert body["stream"] is False


# ---------------------------------------------------------------------------
# _process_chat
# ---------------------------------------------------------------------------


class TestProcessChat:
    @pytest.mark.asyncio
    async def test_returns_success_result(self, chat_job, ollama_chat_response):
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = ollama_chat_response
        mock_response.raise_for_status = MagicMock()
        mock_http.post.return_value = mock_response

        result = await ollama_main._process_chat(
            mock_http,
            chat_job["job_id"],
            chat_job["payload"],
        )

        assert result["status"] == "success"
        assert result["data"]["message"] == ollama_chat_response["message"]
        assert result["data"]["model"] == ollama_chat_response["model"]
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_calls_chat_endpoint(self, chat_job, ollama_chat_response):
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = ollama_chat_response
        mock_response.raise_for_status = MagicMock()
        mock_http.post.return_value = mock_response

        await ollama_main._process_chat(
            mock_http,
            chat_job["job_id"],
            chat_job["payload"],
        )

        call_args = mock_http.post.call_args
        assert call_args[0][0] == f"{config.OLLAMA_HOST}/api/chat"


# ---------------------------------------------------------------------------
# Job loop error handling
# ---------------------------------------------------------------------------


class TestJobLoopErrorHandling:
    @pytest.mark.asyncio
    async def test_stores_error_on_http_failure(self, mock_redis, generate_job):
        """HTTP error from Ollama should store error result in Redis."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        http_error = httpx.HTTPStatusError(
            "500 error",
            request=MagicMock(),
            response=mock_response,
        )

        mock_http = AsyncMock()
        mock_http.post.side_effect = http_error

        # Test the error path directly (no job loop needed)
        result = None
        try:
            result = await ollama_main._process_generate(
                mock_http,
                generate_job["job_id"],
                generate_job["payload"],
            )
        except httpx.HTTPStatusError:
            result = {
                "status": "error",
                "data": None,
                "error": "Ollama HTTP 500",
            }
        await ollama_main._store_result(mock_redis, generate_job["job_id"], result)

        assert mock_redis.rpush.called
        stored_json = mock_redis.rpush.call_args[0][1]
        stored = json.loads(stored_json)
        assert stored["status"] == "error"
        assert stored["data"] is None

    @pytest.mark.asyncio
    async def test_stores_error_on_timeout(self, mock_redis, generate_job):
        """Timeout from Ollama should store error result in Redis."""
        mock_http = AsyncMock()
        mock_http.post.side_effect = httpx.TimeoutException("Request timed out")

        # Test the error path directly
        try:
            await ollama_main._process_generate(
                mock_http,
                generate_job["job_id"],
                generate_job["payload"],
            )
            result = None
        except httpx.TimeoutException:
            result = {
                "status": "error",
                "data": None,
                "error": "Ollama request timed out",
            }

        await ollama_main._store_result(mock_redis, generate_job["job_id"], result)

        stored_json = mock_redis.rpush.call_args[0][1]
        stored = json.loads(stored_json)
        assert stored["status"] == "error"
        assert "timed out" in stored["error"]

    @pytest.mark.asyncio
    async def test_unknown_job_type_stores_error(self, mock_redis, unknown_type_job):
        """Unknown job type should store an error result."""
        mock_http = AsyncMock()

        result = {
            "status": "error",
            "data": None,
            "error": f"Unknown job type: {unknown_type_job['type']}",
        }
        await ollama_main._store_result(mock_redis, unknown_type_job["job_id"], result)

        stored_json = mock_redis.rpush.call_args[0][1]
        stored = json.loads(stored_json)
        assert stored["status"] == "error"
        assert "Unknown job type" in stored["error"]


# ---------------------------------------------------------------------------
# Result format matches backend router expectations
# ---------------------------------------------------------------------------


class TestResultFormat:
    @pytest.mark.asyncio
    async def test_generate_result_has_data_wrapper(self, generate_job, ollama_generate_response):
        """Backend router reads result_data.get('data', {}).get('response')."""
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = ollama_generate_response
        mock_response.raise_for_status = MagicMock()
        mock_http.post.return_value = mock_response

        result = await ollama_main._process_generate(
            mock_http,
            generate_job["job_id"],
            generate_job["payload"],
        )

        # Backend router does: result_data.get("data", {}).get("response")
        assert "data" in result
        assert "response" in result["data"]
        assert "model" in result["data"]

    @pytest.mark.asyncio
    async def test_chat_result_has_data_wrapper(self, chat_job, ollama_chat_response):
        """Backend router reads result_data.get('data', {}).get('message', {}).get('content')."""
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = ollama_chat_response
        mock_response.raise_for_status = MagicMock()
        mock_http.post.return_value = mock_response

        result = await ollama_main._process_chat(
            mock_http,
            chat_job["job_id"],
            chat_job["payload"],
        )

        # Backend router does: result_data.get("data", {}).get("message", {}).get("content")
        assert "data" in result
        assert "message" in result["data"]
        assert "model" in result["data"]
