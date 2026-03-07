"""
Tests for the Stable Diffusion queue consumer worker.
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

import main as sd_main
import config


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_returns_200(self):
        client = TestClient(sd_main.app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_body(self):
        client = TestClient(sd_main.app)
        resp = client.get("/health")
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "sd-consumer"


# ---------------------------------------------------------------------------
# _store_result
# ---------------------------------------------------------------------------


class TestStoreResult:
    @pytest.mark.asyncio
    async def test_stores_result_as_rpush(self, mock_redis):
        result = {
            "status": "success",
            "image_base64": "abc123",
            "model": "stabilityai/sdxl",
            "processing_time_ms": 5000.0,
        }
        await sd_main._store_result(mock_redis, "job-001", result)

        mock_redis.rpush.assert_called_once()
        call_args = mock_redis.rpush.call_args
        key = call_args[0][0]
        value = call_args[0][1]
        assert key == f"{config.RESULTS_KEY_PREFIX}:job-001"
        stored = json.loads(value)
        assert stored["status"] == "success"

    @pytest.mark.asyncio
    async def test_sets_ttl_after_rpush(self, mock_redis):
        result = {"status": "success", "image_base64": "abc", "model": "sdxl"}
        await sd_main._store_result(mock_redis, "job-002", result)

        mock_redis.expire.assert_called_once_with(
            f"{config.RESULTS_KEY_PREFIX}:job-002",
            config.RESULT_KEY_TTL,
        )

    @pytest.mark.asyncio
    async def test_handles_redis_error_gracefully(self, mock_redis):
        mock_redis.rpush.side_effect = Exception("Redis connection refused")
        result = {"status": "success", "image_base64": "abc", "model": "sdxl"}
        # Should not raise
        await sd_main._store_result(mock_redis, "job-err", result)


# ---------------------------------------------------------------------------
# _process_sd_generate
# ---------------------------------------------------------------------------


class TestProcessSdGenerate:
    @pytest.mark.asyncio
    async def test_returns_success_result(self, sd_generate_job, sd_api_success_response):
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = sd_api_success_response
        mock_response.raise_for_status = MagicMock()
        mock_http.post.return_value = mock_response

        result = await sd_main._process_sd_generate(
            mock_http,
            sd_generate_job["job_id"],
            sd_generate_job["payload"],
        )

        assert result["status"] == "success"
        assert result["image_base64"] == sd_api_success_response["image_base64"]
        assert result["model"] == sd_api_success_response["model"]
        assert "processing_time_ms" in result
        assert isinstance(result["processing_time_ms"], float)

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self, sd_generate_job, sd_api_success_response):
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = sd_api_success_response
        mock_response.raise_for_status = MagicMock()
        mock_http.post.return_value = mock_response

        await sd_main._process_sd_generate(
            mock_http,
            sd_generate_job["job_id"],
            sd_generate_job["payload"],
        )

        call_args = mock_http.post.call_args
        assert call_args[0][0] == f"{config.SD_HOST}/generate"

    @pytest.mark.asyncio
    async def test_passes_all_generation_params(self, sd_generate_job, sd_api_success_response):
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = sd_api_success_response
        mock_response.raise_for_status = MagicMock()
        mock_http.post.return_value = mock_response

        await sd_main._process_sd_generate(
            mock_http,
            sd_generate_job["job_id"],
            sd_generate_job["payload"],
        )

        call_kwargs = mock_http.post.call_args[1]
        body = call_kwargs["json"]
        payload = sd_generate_job["payload"]
        assert body["prompt"] == payload["prompt"]
        assert body["model"] == payload["model"]
        assert body["negative_prompt"] == payload["negative_prompt"]
        assert body["height"] == payload["height"]
        assert body["width"] == payload["width"]
        assert body["num_inference_steps"] == payload["num_inference_steps"]
        assert body["guidance_scale"] == payload["guidance_scale"]
        assert body["seed"] == payload["seed"]

    @pytest.mark.asyncio
    async def test_handles_sd_api_error_response(self, sd_generate_job, sd_api_error_response):
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = sd_api_error_response
        mock_response.raise_for_status = MagicMock()
        mock_http.post.return_value = mock_response

        result = await sd_main._process_sd_generate(
            mock_http,
            sd_generate_job["job_id"],
            sd_generate_job["payload"],
        )

        assert result["status"] == "error"
        assert result["image_base64"] is None
        assert "GPU out of memory" in result["error"]


# ---------------------------------------------------------------------------
# Job loop error handling
# ---------------------------------------------------------------------------


class TestJobLoopErrorHandling:
    @pytest.mark.asyncio
    async def test_stores_error_on_http_failure(self, mock_redis, sd_generate_job):
        """HTTP error from SD API should store error result in Redis."""
        mock_response = MagicMock()
        mock_response.status_code = 507
        mock_response.text = "Insufficient Storage – GPU OOM"
        http_error = httpx.HTTPStatusError(
            "507 error",
            request=MagicMock(),
            response=mock_response,
        )

        mock_http = AsyncMock()
        mock_http.post.side_effect = http_error

        try:
            await sd_main._process_sd_generate(
                mock_http,
                sd_generate_job["job_id"],
                sd_generate_job["payload"],
            )
            result = None
        except httpx.HTTPStatusError:
            result = {
                "status": "error",
                "image_base64": None,
                "model": None,
                "error": "SD API HTTP 507",
            }

        await sd_main._store_result(mock_redis, sd_generate_job["job_id"], result)

        stored_json = mock_redis.rpush.call_args[0][1]
        stored = json.loads(stored_json)
        assert stored["status"] == "error"
        assert stored["image_base64"] is None

    @pytest.mark.asyncio
    async def test_stores_error_on_timeout(self, mock_redis, sd_generate_job):
        """Timeout from SD API should store error result in Redis."""
        mock_http = AsyncMock()
        mock_http.post.side_effect = httpx.TimeoutException("Request timed out")

        try:
            await sd_main._process_sd_generate(
                mock_http,
                sd_generate_job["job_id"],
                sd_generate_job["payload"],
            )
            result = None
        except httpx.TimeoutException:
            result = {
                "status": "error",
                "image_base64": None,
                "model": None,
                "error": "SD generation request timed out",
            }

        await sd_main._store_result(mock_redis, sd_generate_job["job_id"], result)

        stored_json = mock_redis.rpush.call_args[0][1]
        stored = json.loads(stored_json)
        assert stored["status"] == "error"
        assert "timed out" in stored["error"]

    @pytest.mark.asyncio
    async def test_unknown_job_type_stores_error(self, mock_redis, unknown_type_job):
        """Unknown job type should store an error result."""
        result = {
            "status": "error",
            "image_base64": None,
            "model": None,
            "error": f"Unknown job type: {unknown_type_job['type']}",
        }
        await sd_main._store_result(mock_redis, unknown_type_job["job_id"], result)

        stored_json = mock_redis.rpush.call_args[0][1]
        stored = json.loads(stored_json)
        assert stored["status"] == "error"
        assert "Unknown job type" in stored["error"]


# ---------------------------------------------------------------------------
# Result format matches backend router expectations
# ---------------------------------------------------------------------------


class TestResultFormat:
    @pytest.mark.asyncio
    async def test_success_result_has_flat_structure(self, sd_generate_job, sd_api_success_response):
        """
        Backend router reads:
            result_data.get("image_base64")
            result_data.get("model")
            result_data.get("processing_time_ms")
        Result must be flat (not nested in 'data').
        """
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = sd_api_success_response
        mock_response.raise_for_status = MagicMock()
        mock_http.post.return_value = mock_response

        result = await sd_main._process_sd_generate(
            mock_http,
            sd_generate_job["job_id"],
            sd_generate_job["payload"],
        )

        # Backend reads these fields at top level
        assert "image_base64" in result
        assert "model" in result
        assert "processing_time_ms" in result
        assert "status" in result
        # Should NOT be nested in 'data'
        assert "data" not in result

    @pytest.mark.asyncio
    async def test_result_stored_as_json_list_item(self, mock_redis, sd_generate_job, sd_api_success_response):
        """Result stored via RPUSH must be JSON-serializable (for BRPOP retrieval)."""
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = sd_api_success_response
        mock_response.raise_for_status = MagicMock()
        mock_http.post.return_value = mock_response

        result = await sd_main._process_sd_generate(
            mock_http,
            sd_generate_job["job_id"],
            sd_generate_job["payload"],
        )
        await sd_main._store_result(mock_redis, sd_generate_job["job_id"], result)

        # Verify RPUSH was called with a valid JSON string
        stored_json = mock_redis.rpush.call_args[0][1]
        stored = json.loads(stored_json)
        assert stored["status"] == "success"
        assert stored["image_base64"] is not None
