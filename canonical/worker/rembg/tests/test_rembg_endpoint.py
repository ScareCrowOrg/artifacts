"""
Tests for the Rembg atomic worker FastAPI endpoint.
"""

import base64
import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import main as rembg_main
from ..main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_1x1_png_b64() -> str:
    """Return a 1×1 white PNG encoded as base64."""
    img = Image.new("RGB", (1, 1), color=(255, 255, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _make_mock_rembg_service():
    """Return a mock RembgService that returns a minimal RGBA PNG."""
    img = Image.new("RGBA", (1, 1), color=(255, 255, 255, 0))
    buf = BytesIO()
    img.save(buf, format="PNG")
    result_b64 = base64.b64encode(buf.getvalue()).decode()

    svc = MagicMock()
    svc.remove_background_base64.return_value = result_b64
    return svc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the module-level singleton between tests."""
    rembg_main._rembg_service = None
    yield
    rembg_main._rembg_service = None


@pytest.fixture
def client():
    return TestClient(rembg_main.app)


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_body(self, client):
        resp = client.get("/health")
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "rembg"


# ---------------------------------------------------------------------------
# /process – happy path
# ---------------------------------------------------------------------------


class TestProcessEndpointSuccess:
    def test_process_returns_200(self, client):
        mock_svc = _make_mock_rembg_service()
        rembg_main._rembg_service = mock_svc

        payload = {
            "job_id": "job-001",
            "image_data": _make_1x1_png_b64(),
        }
        resp = client.post("/process", json=payload)
        assert resp.status_code == 200

    def test_process_response_schema(self, client):
        mock_svc = _make_mock_rembg_service()
        rembg_main._rembg_service = mock_svc

        payload = {
            "job_id": "job-002",
            "image_data": _make_1x1_png_b64(),
        }
        body = client.post("/process", json=payload).json()
        assert body["job_id"] == "job-002"
        assert body["status"] == "ok"
        assert isinstance(body["result"], str) and len(body["result"]) > 0

    def test_process_passes_job_id_to_service(self, client):
        mock_svc = _make_mock_rembg_service()
        rembg_main._rembg_service = mock_svc

        payload = {
            "job_id": "job-003",
            "image_data": _make_1x1_png_b64(),
            "alpha_matting": False,
        }
        client.post("/process", json=payload)

        call_kwargs = mock_svc.remove_background_base64.call_args[1]
        assert call_kwargs.get("job_id") == "job-003"
        assert call_kwargs.get("alpha_matting") is False

    def test_process_default_alpha_matting_is_true(self, client):
        mock_svc = _make_mock_rembg_service()
        rembg_main._rembg_service = mock_svc

        payload = {"job_id": "job-004", "image_data": _make_1x1_png_b64()}
        client.post("/process", json=payload)

        call_kwargs = mock_svc.remove_background_base64.call_args[1]
        assert call_kwargs.get("alpha_matting") is True


# ---------------------------------------------------------------------------
# /process – error handling
# ---------------------------------------------------------------------------


class TestProcessEndpointErrors:
    def test_service_error_returns_500(self, client):
        from rembg_service import RembgServiceError

        mock_svc = MagicMock()
        mock_svc.remove_background_base64.side_effect = RembgServiceError("model failed")
        rembg_main._rembg_service = mock_svc

        payload = {"job_id": "job-err-001", "image_data": _make_1x1_png_b64()}
        resp = client.post("/process", json=payload)
        assert resp.status_code == 500

    def test_unexpected_error_returns_500(self, client):
        mock_svc = MagicMock()
        mock_svc.remove_background_base64.side_effect = RuntimeError("unexpected")
        rembg_main._rembg_service = mock_svc

        payload = {"job_id": "job-err-002", "image_data": _make_1x1_png_b64()}
        resp = client.post("/process", json=payload)
        assert resp.status_code == 500

    def test_missing_image_data_returns_422(self, client):
        """FastAPI validation error when required field is missing."""
        resp = client.post("/process", json={"job_id": "job-err-003"})
        assert resp.status_code == 422

    def test_missing_job_id_returns_422(self, client):
        resp = client.post("/process", json={"image_data": _make_1x1_png_b64()})
        assert resp.status_code == 422
