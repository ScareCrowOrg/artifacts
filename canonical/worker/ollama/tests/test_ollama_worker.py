"""
Tests for the Ollama HTTP worker.

Validates the stateless HTTP pattern: GateKeeper calls POST /process,
worker calls Ollama API, returns structured result.
"""

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
        assert body["service"] == "ollama-worker"


# ---------------------------------------------------------------------------
# POST /process – generate jobs
# ---------------------------------------------------------------------------


class TestProcessGenerate:
    def _patch_client(self, response_data: dict) -> MagicMock:
        """Return a patched _http_client that returns response_data on POST."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = response_data
        mock_resp.raise_for_status = MagicMock()
        mock_http = AsyncMock()
        mock_http.post.return_value = mock_resp
        return mock_http

    def test_returns_success_result(self, generate_job, ollama_generate_response):
        mock_http = self._patch_client(ollama_generate_response)
        with patch.object(ollama_main, "_http_client", mock_http):
            client = TestClient(ollama_main.app)
            resp = client.post("/process", json=generate_job)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["data"]["response"] == ollama_generate_response["response"]
        assert body["data"]["model"] == ollama_generate_response["model"]
        assert body["error"] is None

    def test_calls_ollama_generate_endpoint(self, generate_job, ollama_generate_response):
        mock_http = self._patch_client(ollama_generate_response)
        with patch.object(ollama_main, "_http_client", mock_http):
            TestClient(ollama_main.app).post("/process", json=generate_job)

        url = mock_http.post.call_args[0][0]
        assert url == f"{config.OLLAMA_HOST}/api/generate"

    def test_forwards_model_and_prompt(self, generate_job, ollama_generate_response):
        mock_http = self._patch_client(ollama_generate_response)
        with patch.object(ollama_main, "_http_client", mock_http):
            TestClient(ollama_main.app).post("/process", json=generate_job)

        body = mock_http.post.call_args[1]["json"]
        assert body["model"] == generate_job["payload"]["model"]
        assert body["prompt"] == generate_job["payload"]["prompt"]
        assert body["stream"] is False

    def test_accepts_job_type_field(self, generate_job_gk_format, ollama_generate_response):
        """Worker must accept jobs using GateKeeper-native 'job_type' field too."""
        mock_http = self._patch_client(ollama_generate_response)
        with patch.object(ollama_main, "_http_client", mock_http):
            resp = TestClient(ollama_main.app).post("/process", json=generate_job_gk_format)

        assert resp.status_code == 200
        assert resp.json()["status"] == "success"


# ---------------------------------------------------------------------------
# POST /process – chat jobs
# ---------------------------------------------------------------------------


class TestProcessChat:
    def _patch_client(self, response_data: dict) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.json.return_value = response_data
        mock_resp.raise_for_status = MagicMock()
        mock_http = AsyncMock()
        mock_http.post.return_value = mock_resp
        return mock_http

    def test_returns_success_result(self, chat_job, ollama_chat_response):
        mock_http = self._patch_client(ollama_chat_response)
        with patch.object(ollama_main, "_http_client", mock_http):
            resp = TestClient(ollama_main.app).post("/process", json=chat_job)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["data"]["message"] == ollama_chat_response["message"]
        assert body["data"]["model"] == ollama_chat_response["model"]

    def test_calls_ollama_chat_endpoint(self, chat_job, ollama_chat_response):
        mock_http = self._patch_client(ollama_chat_response)
        with patch.object(ollama_main, "_http_client", mock_http):
            TestClient(ollama_main.app).post("/process", json=chat_job)

        url = mock_http.post.call_args[0][0]
        assert url == f"{config.OLLAMA_HOST}/api/chat"


# ---------------------------------------------------------------------------
# POST /process – error handling
# ---------------------------------------------------------------------------


class TestProcessErrors:
    def test_unknown_job_type_returns_400(self, unknown_type_job):
        client = TestClient(ollama_main.app)
        resp = client.post("/process", json=unknown_type_job)
        assert resp.status_code == 400
        assert "Unknown job type" in resp.json()["detail"]

    def test_ollama_http_error_returns_502(self, generate_job):
        mock_http = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_http.post.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_resp
        )
        with patch.object(ollama_main, "_http_client", mock_http):
            resp = TestClient(ollama_main.app).post("/process", json=generate_job)

        assert resp.status_code == 502

    def test_ollama_timeout_returns_504(self, generate_job):
        mock_http = AsyncMock()
        mock_http.post.side_effect = httpx.TimeoutException("timed out")
        with patch.object(ollama_main, "_http_client", mock_http):
            resp = TestClient(ollama_main.app).post("/process", json=generate_job)

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

    def test_generate_result_has_nested_data(self, generate_job, ollama_generate_response):
        """Backend reads result_data.get("data", {}).get("response")."""
        mock_http = self._patch_client(ollama_generate_response)
        with patch.object(ollama_main, "_http_client", mock_http):
            resp = TestClient(ollama_main.app).post("/process", json=generate_job)

        body = resp.json()
        assert "data" in body
        assert "response" in body["data"]
        assert "model" in body["data"]
        assert "status" in body

    def test_chat_result_has_nested_data(self, chat_job, ollama_chat_response):
        """Backend reads result_data.get("data", {}).get("message", {}).get("content")."""
        mock_http = self._patch_client(ollama_chat_response)
        with patch.object(ollama_main, "_http_client", mock_http):
            resp = TestClient(ollama_main.app).post("/process", json=chat_job)

        body = resp.json()
        assert "data" in body
        assert "message" in body["data"]
        assert "model" in body["data"]
