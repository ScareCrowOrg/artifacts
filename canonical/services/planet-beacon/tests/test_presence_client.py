"""
Tests for presence_client.py

Tests verify:
- POST is sent to the correct CentralHub URL
- Authorization header is set correctly
- HTTP 204 response returns True
- Non-204 HTTP response returns False and logs a warning
- Network error returns False and logs a warning
- Missing PLANET_ID returns False immediately
"""

import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

# Add service root to path so imports resolve without install
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from presence_client import send_presence


class MockConfig:
    """Minimal config-like object for testing."""
    PLANET_ID = "planet-abc-123"
    PLANET_NAME = "andromeda"
    TUNNEL_FQDN = "andromeda.scareverse.net"
    CENTRALHUB_URL = "https://hub.scareverse.net"
    CENTRALHUB_SERVICE_TOKEN = "test-service-token"
    PRESENCE_TTL = 90


SAMPLE_VIEWERS = [
    {"id": "dynamic-workspace", "path": "/artifacts/canonical/viewers/dynamic-workspace"}
]


@pytest.mark.asyncio
async def test_send_presence_posts_to_correct_url():
    """POST is sent to CENTRALHUB_URL/api/v1/planets/presence."""
    mock_response = MagicMock()
    mock_response.status_code = 204

    with patch("presence_client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_response)

        await send_presence(MockConfig(), SAMPLE_VIEWERS)

        instance.post.assert_called_once()
        call_args = instance.post.call_args
        assert call_args[0][0] == "https://hub.scareverse.net/api/v1/planets/presence"


@pytest.mark.asyncio
async def test_send_presence_includes_auth_header():
    """Authorization: Bearer <token> header is sent."""
    mock_response = MagicMock()
    mock_response.status_code = 204

    with patch("presence_client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_response)

        await send_presence(MockConfig(), SAMPLE_VIEWERS)

        call_kwargs = instance.post.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer test-service-token"


@pytest.mark.asyncio
async def test_send_presence_returns_true_on_204():
    """Returns True when CentralHub responds with HTTP 204."""
    mock_response = MagicMock()
    mock_response.status_code = 204

    with patch("presence_client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_response)

        result = await send_presence(MockConfig(), SAMPLE_VIEWERS)
        assert result is True


@pytest.mark.asyncio
async def test_send_presence_returns_false_on_http_error():
    """Returns False when CentralHub responds with non-204 status."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch("presence_client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_response)

        result = await send_presence(MockConfig(), SAMPLE_VIEWERS)
        assert result is False


@pytest.mark.asyncio
async def test_send_presence_returns_false_on_request_error():
    """Returns False on network / connection error."""
    with patch("presence_client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(
            side_effect=httpx.RequestError("connection refused")
        )

        result = await send_presence(MockConfig(), SAMPLE_VIEWERS)
        assert result is False


@pytest.mark.asyncio
async def test_send_presence_returns_false_when_planet_id_missing():
    """Returns False immediately when PLANET_ID is not set."""
    cfg = MockConfig()
    cfg.PLANET_ID = ""

    result = await send_presence(cfg, SAMPLE_VIEWERS)
    assert result is False


@pytest.mark.asyncio
async def test_send_presence_returns_false_when_service_token_missing():
    """Returns False immediately when CENTRALHUB_SERVICE_TOKEN is not set."""
    cfg = MockConfig()
    cfg.CENTRALHUB_SERVICE_TOKEN = ""

    result = await send_presence(cfg, SAMPLE_VIEWERS)
    assert result is False


@pytest.mark.asyncio
async def test_send_presence_payload_contains_viewers():
    """Payload sent to CentralHub includes the viewers list."""
    mock_response = MagicMock()
    mock_response.status_code = 204

    with patch("presence_client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_response)

        await send_presence(MockConfig(), SAMPLE_VIEWERS)

        call_kwargs = instance.post.call_args[1]
        payload = call_kwargs.get("json", {})
        assert payload["planet_id"] == "planet-abc-123"
        assert payload["fqdn"] == "andromeda.scareverse.net"
        assert payload["status"] == "online"
        assert payload["viewers"] == SAMPLE_VIEWERS
