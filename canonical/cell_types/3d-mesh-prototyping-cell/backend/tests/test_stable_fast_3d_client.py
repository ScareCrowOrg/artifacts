"""
Tests for Stable Fast 3D API Client

Tests cover:
- Client initialization
- Image data decoding
- API request formatting
- Response handling (success and errors)
- Error handling for various scenarios
"""

import pytest
import base64
from unittest.mock import Mock, patch, MagicMock
import io
import sys
from pathlib import Path

# Add the backend scripts directory to path for imports
scripts_path = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_path))

from stable_fast_3d_client import StableFast3DClient, create_client


class TestClientInitialization:
    """Tests for StableFast3DClient initialization."""
    
    def test_init_with_api_key(self):
        """Test successful initialization with API key."""
        client = StableFast3DClient(api_key="test_key_123")

        assert client.api_key == "test_key_123"
        assert client.api_url == "https://api.stability.ai/v2beta/3d/stable-fast-3d"
        assert client.timeout == 60
    
    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        client = StableFast3DClient(
            api_key="test_key_123",
            api_url="https://custom.api.url",
            timeout=120
        )
        
        assert client.api_key == "test_key_123"
        assert client.api_url == "https://custom.api.url"
        assert client.timeout == 120
    
    def test_init_without_api_key(self):
        """Test initialization fails without API key."""
        with pytest.raises(ValueError, match="API key is required"):
            StableFast3DClient(api_key=None)
    
    def test_init_with_empty_api_key(self):
        """Test initialization fails with empty API key."""
        with pytest.raises(ValueError, match="API key is required"):
            StableFast3DClient(api_key="")


class TestImageDataDecoding:
    """Tests for image data decoding functionality."""
    
    def test_decode_data_url(self):
        """Test decoding base64 data URL."""
        client = StableFast3DClient(api_key="test_key")
        
        # Create a simple test image (1x1 red pixel PNG)
        test_image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        data_url = f"data:image/png;base64,{test_image_base64}"
        
        result = client._decode_image_data(data_url)
        
        assert isinstance(result, bytes)
        assert len(result) > 0
    
    def test_decode_raw_base64(self):
        """Test decoding raw base64 string."""
        client = StableFast3DClient(api_key="test_key")
        
        test_image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        
        result = client._decode_image_data(test_image_base64)
        
        assert isinstance(result, bytes)
        assert len(result) > 0
    
    def test_decode_empty_image_data(self):
        """Test decoding fails with empty image data."""
        client = StableFast3DClient(api_key="test_key")
        
        with pytest.raises(ValueError, match="Image data is empty"):
            client._decode_image_data("")
    
    def test_decode_invalid_data_url(self):
        """Test decoding fails with invalid data URL."""
        client = StableFast3DClient(api_key="test_key")
        
        with pytest.raises(ValueError, match="Invalid data URL format"):
            client._decode_image_data("data:image/png;base64")
    
    def test_decode_invalid_base64(self):
        """Test decoding fails with invalid base64."""
        client = StableFast3DClient(api_key="test_key")
        
        with pytest.raises(ValueError, match="Failed to decode base64"):
            client._decode_image_data("not-valid-base64!@#$%")


class TestGenerateMesh:
    """Tests for mesh generation functionality."""
    
    @patch('stable_fast_3d_client.httpx.Client')
    def test_generate_mesh_success(self, mock_client_class):
        """Test successful mesh generation."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"GLB_BINARY_DATA_HERE"
        
        mock_client_instance = Mock()
        mock_client_instance.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client_instance
        
        # Create client and generate mesh
        client = StableFast3DClient(api_key="test_key_123")
        
        test_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        
        result = client.generate_mesh(
            image_data=test_image,
            texture_resolution=1024,
            foreground_ratio=0.85
        )
        
        # Verify result
        assert result["success"] is True
        assert result["mesh_data"] is not None
        assert result["mesh_data"].startswith("data:model/gltf-binary;base64,")
        assert result["metadata"] is not None
        assert result["metadata"]["modelType"] == "stable_fast_3d"
        assert result["error"] is None
        
        # Verify API was called correctly
        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args
        assert call_args[0][0] == "https://api.stability.ai/v2beta/3d/stable-fast-3d"
        assert "authorization" in call_args[1]["headers"]
        assert call_args[1]["headers"]["authorization"] == "Bearer test_key_123"
    
    @patch('stable_fast_3d_client.httpx.Client')
    def test_generate_mesh_with_custom_params(self, mock_client_class):
        """Test mesh generation with custom parameters."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"GLB_BINARY_DATA"
        
        mock_client_instance = Mock()
        mock_client_instance.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client_instance
        
        client = StableFast3DClient(api_key="test_key")
        test_image = "data:image/png;base64,iVBORw0KGgo="
        
        result = client.generate_mesh(
            image_data=test_image,
            texture_resolution=2048,
            foreground_ratio=0.9
        )
        
        assert result["success"] is True
        
        # Verify parameters were passed
        call_args = mock_client_instance.post.call_args
        assert call_args[1]["data"]["texture_resolution"] == "2048"
        assert call_args[1]["data"]["foreground_ratio"] == "0.9"
    
    def test_generate_mesh_invalid_image(self):
        """Test mesh generation with invalid image data."""
        client = StableFast3DClient(api_key="test_key")
        
        # Use actually invalid base64 that will fail decoding
        result = client.generate_mesh(
            image_data="data:image/png;base64,!!!INVALID_BASE64!!!",
            texture_resolution=1024,
            foreground_ratio=0.85
        )
        
        assert result["success"] is False
        assert "Invalid input" in result["error"] or "Failed to decode" in result["error"]
        assert result["mesh_data"] is None
    
    @patch('stable_fast_3d_client.httpx.Client')
    def test_generate_mesh_api_error_401(self, mock_client_class):
        """Test mesh generation with authentication error."""
        # Setup mock for 401 error
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Invalid API key"}
        mock_response.text = "Unauthorized"
        
        mock_client_instance = Mock()
        mock_client_instance.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client_instance
        
        client = StableFast3DClient(api_key="invalid_key")
        test_image = "data:image/png;base64,iVBORw0KGgo="
        
        result = client.generate_mesh(image_data=test_image)
        
        assert result["success"] is False
        assert "Authentication failed" in result["error"]
        assert result["metadata"]["error_code"] == 401
    
    @patch('stable_fast_3d_client.httpx.Client')
    def test_generate_mesh_api_error_429(self, mock_client_class):
        """Test mesh generation with rate limit error."""
        # Setup mock for 429 error
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": "Rate limit exceeded"}
        mock_response.text = "Too Many Requests"
        
        mock_client_instance = Mock()
        mock_client_instance.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client_instance
        
        client = StableFast3DClient(api_key="test_key")
        test_image = "data:image/png;base64,iVBORw0KGgo="
        
        result = client.generate_mesh(image_data=test_image)
        
        assert result["success"] is False
        assert "Rate limit exceeded" in result["error"]
    
    @patch('stable_fast_3d_client.httpx.Client')
    def test_generate_mesh_api_error_500(self, mock_client_class):
        """Test mesh generation with server error."""
        # Setup mock for 500 error
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.side_effect = Exception("Not JSON")
        mock_response.text = "Internal Server Error"
        
        mock_client_instance = Mock()
        mock_client_instance.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client_instance
        
        client = StableFast3DClient(api_key="test_key")
        test_image = "data:image/png;base64,iVBORw0KGgo="
        
        result = client.generate_mesh(image_data=test_image)
        
        assert result["success"] is False
        assert "service error" in result["error"]
    
    @patch('stable_fast_3d_client.httpx.Client')
    def test_generate_mesh_timeout(self, mock_client_class):
        """Test mesh generation with timeout."""
        # Setup mock to raise timeout
        mock_client_instance = Mock()
        mock_client_instance.post.side_effect = __import__('httpx').TimeoutException("Request timeout")
        mock_client_class.return_value.__enter__.return_value = mock_client_instance
        
        client = StableFast3DClient(api_key="test_key", timeout=10)
        test_image = "data:image/png;base64,iVBORw0KGgo="
        
        result = client.generate_mesh(image_data=test_image)
        
        assert result["success"] is False
        assert "timeout" in result["error"].lower()
    
    @patch('stable_fast_3d_client.httpx.Client')
    def test_generate_mesh_network_error(self, mock_client_class):
        """Test mesh generation with network error."""
        # Setup mock to raise network error
        mock_client_instance = Mock()
        mock_client_instance.post.side_effect = __import__('httpx').HTTPError("Connection failed")
        mock_client_class.return_value.__enter__.return_value = mock_client_instance
        
        client = StableFast3DClient(api_key="test_key")
        test_image = "data:image/png;base64,iVBORw0KGgo="
        
        result = client.generate_mesh(image_data=test_image)
        
        assert result["success"] is False
        assert "Network error" in result["error"]


class TestResponseHandling:
    """Tests for API response handling."""
    
    def test_handle_success_response(self):
        """Test handling of successful API response."""
        client = StableFast3DClient(api_key="test_key")
        
        # Create mock response
        mock_response = Mock()
        mock_response.content = b"GLB_BINARY_TEST_DATA"
        
        result = client._handle_success_response(mock_response)
        
        assert result["success"] is True
        assert result["mesh_data"].startswith("data:model/gltf-binary;base64,")
        assert result["metadata"]["fileSizeBytes"] == len(b"GLB_BINARY_TEST_DATA")
        assert result["metadata"]["modelType"] == "stable_fast_3d"
        assert result["error"] is None
    
    def test_handle_error_response_with_json(self):
        """Test handling of error response with JSON body."""
        client = StableFast3DClient(api_key="test_key")
        
        # Create mock error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"message": "Invalid image format"}
        
        result = client._handle_error_response(mock_response)
        
        assert result["success"] is False
        assert "Bad request" in result["error"]
        assert result["metadata"]["error_code"] == 400
        assert result["mesh_data"] is None
    
    def test_handle_error_response_without_json(self):
        """Test handling of error response without JSON body."""
        client = StableFast3DClient(api_key="test_key")
        
        # Create mock error response
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.json.side_effect = Exception("Not JSON")
        mock_response.text = "Service Unavailable"
        
        result = client._handle_error_response(mock_response)
        
        assert result["success"] is False
        assert "service error" in result["error"].lower()


class TestCreateClientFactory:
    """Tests for create_client factory function."""
    
    def test_create_client_with_api_key(self):
        """Test creating client with provided API key."""
        client = create_client(api_key="test_key_123")
        
        assert client is not None
        assert client.api_key == "test_key_123"
    
    def test_create_client_without_api_key(self):
        """Test creating client without API key returns None."""
        client = create_client(api_key=None)
        
        assert client is None
    
    def test_create_client_with_custom_params(self):
        """Test creating client with custom parameters."""
        client = create_client(
            api_key="test_key",
            api_url="https://custom.url",
            timeout=120
        )
        
        assert client is not None
        assert client.api_url == "https://custom.url"
        assert client.timeout == 120


class TestIntegration:
    """Integration tests for complete workflow."""
    
    @patch('stable_fast_3d_client.httpx.Client')
    def test_full_workflow_success(self, mock_client_class):
        """Test complete workflow from initialization to mesh generation."""
        # Setup mock
        mock_glb_data = b"MOCK_GLB_BINARY_DATA_FOR_TESTING"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = mock_glb_data
        
        mock_client_instance = Mock()
        mock_client_instance.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client_instance
        
        # Create client
        client = StableFast3DClient(
            api_key="sk-test-key-12345",
            api_url="https://api.stability.ai/v2beta/3d/stable-fast-3d",
            timeout=60
        )
        
        # Prepare test image
        test_image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00"  # PNG header
        test_image_base64 = base64.b64encode(test_image_bytes).decode('utf-8')
        test_image_data_url = f"data:image/png;base64,{test_image_base64}"
        
        # Generate mesh
        result = client.generate_mesh(
            image_data=test_image_data_url,
            texture_resolution=1024,
            foreground_ratio=0.85
        )
        
        # Verify complete result
        assert result["success"] is True
        assert result["mesh_data"] is not None
        assert result["mesh_data"].startswith("data:model/gltf-binary;base64,")
        
        # Decode and verify GLB data
        glb_base64 = result["mesh_data"].split(",")[1]
        decoded_glb = base64.b64decode(glb_base64)
        assert decoded_glb == mock_glb_data
        
        # Verify metadata
        assert result["metadata"]["fileSizeBytes"] == len(mock_glb_data)
        assert result["metadata"]["modelType"] == "stable_fast_3d"
        assert result["metadata"]["generationSource"] == "stability_ai_api"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
