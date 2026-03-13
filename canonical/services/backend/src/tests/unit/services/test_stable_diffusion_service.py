"""
Unit tests for StableDiffusionService.

Tests cover:
- Image generation with valid responses
- Response validation (dict vs string)
- Error handling for malformed responses
- Health check functionality
"""

import json
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.stable_diffusion_service import (
    StableDiffusionService,
    get_stable_diffusion_service
)


@pytest.fixture
def sd_service():
    """Create a StableDiffusionService instance for testing."""
    return StableDiffusionService()


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


class TestStableDiffusionServiceImageGeneration:
    """Test image generation functionality."""

    @pytest.mark.asyncio
    async def test_generate_image_success_with_dict_info(self, sd_service):
        """Test successful image generation with info as dict."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "images": ["base64_encoded_image_data"],
            "info": {
                "seed": 12345,
                "model": "sd_xl_base_1.0"
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await sd_service.generate_image(
                prompt="test prompt",
                width=512,
                height=512
            )

        assert result["success"] is True
        assert "image_base64" in result
        assert result["image_base64"] == "base64_encoded_image_data"
        assert result["metadata"]["seed"] == 12345

    @pytest.mark.asyncio
    async def test_generate_image_success_with_string_info(self, sd_service):
        """Test successful image generation with info as JSON string."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "images": ["base64_encoded_image_data"],
            "info": json.dumps({"seed": 67890, "model": "sd_xl_base_1.0"})
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await sd_service.generate_image(
                prompt="test prompt",
                seed=999
            )

        assert result["success"] is True
        assert result["metadata"]["seed"] == 67890

    @pytest.mark.asyncio
    async def test_generate_image_invalid_response_type(self, sd_service):
        """Test handling of invalid response type (string instead of dict)."""
        mock_response = MagicMock()
        mock_response.json.return_value = "invalid string response"
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await sd_service.generate_image(prompt="test prompt")

        assert result["success"] is False
        assert "Invalid API response format" in result["error"]
        assert "expected JSON object, got str" in result["error"]

    @pytest.mark.asyncio
    async def test_generate_image_no_images_in_response(self, sd_service):
        """Test handling of response with no images."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "images": [],
            "info": {"seed": 12345}
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await sd_service.generate_image(prompt="test prompt")

        assert result["success"] is False
        assert result["error"] == "No images generated"

    @pytest.mark.asyncio
    async def test_generate_image_missing_info_field(self, sd_service):
        """Test generation with missing info field (uses default seed)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "images": ["base64_encoded_image_data"]
            # No 'info' field
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await sd_service.generate_image(
                prompt="test prompt",
                seed=999
            )

        assert result["success"] is True
        assert result["metadata"]["seed"] == 999  # Should use input seed

    @pytest.mark.asyncio
    async def test_generate_image_malformed_json_in_info_string(self, sd_service):
        """Test handling of malformed JSON in info string field."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "images": ["base64_encoded_image_data"],
            "info": "invalid json string {{"
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await sd_service.generate_image(
                prompt="test prompt",
                seed=777
            )

        assert result["success"] is True
        assert result["metadata"]["seed"] == 777  # Should fallback to input seed


class TestStableDiffusionServiceErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_generate_image_timeout(self, sd_service):
        """Test handling of API timeout."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = httpx.TimeoutException("Timeout")
            mock_client_class.return_value = mock_client

            result = await sd_service.generate_image(prompt="test prompt")

        assert result["success"] is False
        assert "timeout" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_generate_image_http_error(self, sd_service):
        """Test handling of HTTP errors."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = httpx.HTTPError("HTTP Error")
            mock_client_class.return_value = mock_client

            result = await sd_service.generate_image(prompt="test prompt")

        assert result["success"] is False
        assert "API error" in result["error"]

    @pytest.mark.asyncio
    async def test_generate_image_unexpected_exception(self, sd_service):
        """Test handling of unexpected exceptions."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = Exception("Unexpected error")
            mock_client_class.return_value = mock_client

            result = await sd_service.generate_image(prompt="test prompt")

        assert result["success"] is False
        assert "Generation failed" in result["error"]


class TestStableDiffusionServiceHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_check_health_success(self, sd_service):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"model_name": "sd_xl_base_1.0"},
            {"model_name": "sd_v1_5"}
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await sd_service.check_health()

        assert result["success"] is True
        assert result["available"] is True
        assert result["models_count"] == 2

    @pytest.mark.asyncio
    async def test_check_health_failure(self, sd_service):
        """Test health check when API is unavailable."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            mock_client_class.return_value = mock_client

            result = await sd_service.check_health()

        assert result["success"] is False
        assert result["available"] is False
        assert "error" in result


class TestStableDiffusionServiceSingleton:
    """Test singleton pattern."""

    def test_get_stable_diffusion_service_singleton(self):
        """Test that get_stable_diffusion_service returns singleton."""
        service1 = get_stable_diffusion_service()
        service2 = get_stable_diffusion_service()

        assert service1 is service2
        assert isinstance(service1, StableDiffusionService)
