"""
Tests for the Stable Diffusion HTTP worker.

Validates the stateless HTTP pattern: GateKeeper calls POST /process,
worker calls SD API, returns structured result.
"""

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
        assert body["service"] == "sd-worker"


# ---------------------------------------------------------------------------
# POST /process – sd_generate jobs
# ---------------------------------------------------------------------------


class TestProcessSdGenerate:
    def _patch_client(self, response_data: dict) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.json.return_value = response_data
        mock_resp.raise_for_status = MagicMock()
        mock_http = AsyncMock()
        mock_http.post.return_value = mock_resp
        return mock_http

    def test_returns_success_result(self, sd_generate_job, sd_api_success_response):
        mock_http = self._patch_client(sd_api_success_response)
        with patch.object(sd_main, "_http_client", mock_http):
            resp = TestClient(sd_main.app).post("/process", json=sd_generate_job)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["image_base64"] == sd_api_success_response["image_base64"]
        assert body["model"] == sd_api_success_response["model"]
        assert "processing_time_ms" in body
        assert isinstance(body["processing_time_ms"], float)

    def test_calls_sd_generate_endpoint(self, sd_generate_job, sd_api_success_response):
        mock_http = self._patch_client(sd_api_success_response)
        with patch.object(sd_main, "_http_client", mock_http):
            TestClient(sd_main.app).post("/process", json=sd_generate_job)

        url = mock_http.post.call_args[0][0]
        assert url == f"{config.SD_HOST}/generate"

    def test_forwards_all_generation_params(self, sd_generate_job, sd_api_success_response):
        mock_http = self._patch_client(sd_api_success_response)
        with patch.object(sd_main, "_http_client", mock_http):
            TestClient(sd_main.app).post("/process", json=sd_generate_job)

        body = mock_http.post.call_args[1]["json"]
        payload = sd_generate_job["payload"]
        assert body["prompt"] == payload["prompt"]
        assert body["model"] == payload["model"]
        assert body["negative_prompt"] == payload["negative_prompt"]
        assert body["height"] == payload["height"]
        assert body["width"] == payload["width"]
        assert body["num_inference_steps"] == payload["num_inference_steps"]
        assert body["guidance_scale"] == payload["guidance_scale"]
        assert body["seed"] == payload["seed"]

    def test_accepts_job_type_field(self, sd_generate_job_gk_format, sd_api_success_response):
        """Worker must accept jobs using GateKeeper-native 'job_type' field too."""
        mock_http = self._patch_client(sd_api_success_response)
        with patch.object(sd_main, "_http_client", mock_http):
            resp = TestClient(sd_main.app).post("/process", json=sd_generate_job_gk_format)

        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_handles_sd_api_error_response(self, sd_generate_job, sd_api_error_response):
        """SD API non-success status should surface as an error result (not HTTP 5xx)."""
        mock_http = self._patch_client(sd_api_error_response)
        with patch.object(sd_main, "_http_client", mock_http):
            resp = TestClient(sd_main.app).post("/process", json=sd_generate_job)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "error"
        assert body["image_base64"] is None
        assert "GPU out of memory" in body["error"]


# ---------------------------------------------------------------------------
# POST /process – error handling
# ---------------------------------------------------------------------------


class TestProcessErrors:
    def test_unknown_job_type_returns_400(self, unknown_type_job):
        resp = TestClient(sd_main.app).post("/process", json=unknown_type_job)
        assert resp.status_code == 400
        assert "Unknown job type" in resp.json()["detail"]

    def test_sd_http_error_returns_502(self, sd_generate_job):
        mock_http = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 507
        mock_resp.text = "Insufficient Storage"
        mock_http.post.side_effect = httpx.HTTPStatusError(
            "507", request=MagicMock(), response=mock_resp
        )
        with patch.object(sd_main, "_http_client", mock_http):
            resp = TestClient(sd_main.app).post("/process", json=sd_generate_job)

        assert resp.status_code == 502

    def test_sd_timeout_returns_504(self, sd_generate_job):
        mock_http = AsyncMock()
        mock_http.post.side_effect = httpx.TimeoutException("timed out")
        with patch.object(sd_main, "_http_client", mock_http):
            resp = TestClient(sd_main.app).post("/process", json=sd_generate_job)

        assert resp.status_code == 504


# ---------------------------------------------------------------------------
# Result format contract
# ---------------------------------------------------------------------------


class TestResultFormat:
    """Validate result format matches what backend router expects after BRPOP."""

    def _patch_client(self, response_data: dict) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.json.return_value = response_data
        mock_resp.raise_for_status = MagicMock()
        mock_http = AsyncMock()
        mock_http.post.return_value = mock_resp
        return mock_http

    def test_success_result_has_flat_structure(self, sd_generate_job, sd_api_success_response):
        """Backend reads result_data.get("image_base64"), get("model"), get("processing_time_ms")."""
        mock_http = self._patch_client(sd_api_success_response)
        with patch.object(sd_main, "_http_client", mock_http):
            resp = TestClient(sd_main.app).post("/process", json=sd_generate_job)

        body = resp.json()
        # Backend reads these at top level (flat, not nested in 'data')
        assert "image_base64" in body
        assert "model" in body
        assert "processing_time_ms" in body
        assert "status" in body
        assert "data" not in body
