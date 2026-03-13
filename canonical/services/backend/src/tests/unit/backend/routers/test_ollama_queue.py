"""
Unit tests for ollama_proxy router.

Tests cover:
- POST /api/generate - Generate text via Ollama-compatible endpoint
- POST /api/chat - Chat via Ollama-compatible endpoint
- GET /api/status/{job_id} - Get job status

Technical naming: All functions and variables in English.
"""

import pytest
import json
import time
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.config.redis_keys import get_ollama_result_key


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_client = MagicMock()
    redis_client.ping.return_value = True
    return redis_client


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up dependency overrides."""
    yield
    app.dependency_overrides.clear()


class TestOllamaProxyGenerate:
    """Tests for POST /api/generate endpoint."""
    
    @patch('app.routers.ollama_proxy.get_redis_client')
    @patch('app.routers.ollama_proxy.asyncio.wait_for')
    def test_generate_success(self, mock_wait_for, mock_get_redis, client, mock_redis):
        """Test successful text generation via Ollama-compatible endpoint."""
        # Setup mocks
        mock_get_redis.return_value = mock_redis
        
        # Mock job enqueue (rpush)
        mock_redis.rpush.return_value = 1
        
        # Mock BRPOP result (simulated worker response)
        job_id = "test-job-123"
        result_key = get_ollama_result_key(job_id)
        
        # Mock asyncio.wait_for to return the result directly
        mock_wait_for.return_value = (
            result_key,
            json.dumps({
                "status": "success",
                "data": {
                    "response": "This is a test response from Ollama.",
                    "model": "mistral",
                    "done": True
                }
            })
        )
        
        # Make request
        response = client.post(
            "/api/generate",
            json={
                "prompt": "What is AI?",
                "model": "mistral"
            }
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "response" in data
        assert data["model"] == "mistral"
        
        # Verify Redis calls
        mock_redis.rpush.assert_called_once()
        mock_redis.delete.assert_not_called()  # No error cleanup
    
    @patch('app.routers.ollama_proxy.get_redis_client')
    @patch('app.routers.ollama_proxy.asyncio.wait_for')
    def test_generate_timeout(self, mock_wait_for, mock_get_redis, client, mock_redis):
        """Test timeout handling for generate endpoint."""
        # Setup mocks
        mock_get_redis.return_value = mock_redis
        mock_redis.rpush.return_value = 1
        
        # Mock timeout by raising asyncio.TimeoutError
        mock_wait_for.side_effect = asyncio.TimeoutError()
        
        # Make request
        response = client.post(
            "/api/generate",
            json={
                "prompt": "What is AI?",
                "model": "mistral"
            }
        )
        
        # Assertions
        assert response.status_code == 504  # Gateway Timeout
        assert "timeout" in response.json()["detail"].lower()
        
        # Verify cleanup
        mock_redis.delete.assert_called_once()
    
    @patch('app.routers.ollama_proxy.get_redis_client')
    @patch('app.routers.ollama_proxy.asyncio.wait_for')
    def test_generate_worker_error(self, mock_wait_for, mock_get_redis, client, mock_redis):
        """Test error handling when worker fails."""
        # Setup mocks
        mock_get_redis.return_value = mock_redis
        mock_redis.rpush.return_value = 1
        
        # Mock worker error response
        job_id = "test-job-error"
        result_key = get_ollama_result_key(job_id)
        
        # Mock asyncio.wait_for to return error result
        mock_wait_for.return_value = (
            result_key,
            json.dumps({
                "status": "error",
                "error": "GPU unavailable after retries"
            })
        )
        
        # Make request
        response = client.post(
            "/api/generate",
            json={
                "prompt": "What is AI?",
                "model": "mistral"
            }
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "error" in data
        assert "GPU unavailable" in data["error"]


class TestOllamaProxyChat:
    """Tests for POST /api/chat endpoint."""
    
    @patch('app.routers.ollama_proxy.get_redis_client')
    @patch('app.routers.ollama_proxy.asyncio.wait_for')
    def test_chat_success(self, mock_wait_for, mock_get_redis, client, mock_redis):
        """Test successful chat via Ollama-compatible endpoint."""
        # Setup mocks
        mock_get_redis.return_value = mock_redis
        mock_redis.rpush.return_value = 1
        
        # Mock BRPOP result
        job_id = "test-chat-job"
        result_key = get_ollama_result_key(job_id)
        
        # Mock asyncio.wait_for to return the result directly
        mock_wait_for.return_value = (
            result_key,
            json.dumps({
                "status": "success",
                "data": {
                    "message": {
                        "role": "assistant",
                        "content": "Hello! How can I help you?"
                    },
                    "model": "mistral",
                    "done": True
                }
            })
        )
        
        # Make request
        response = client.post(
            "/api/chat",
            json={
                "messages": [
                    {"role": "user", "content": "Hello"}
                ],
                "model": "mistral"
            }
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "response" in data
        assert "Hello! How can I help you?" in data["response"]


class TestOllamaProxyStatus:
    """Tests for GET /api/status/{job_id} endpoint."""
    
    @patch('app.routers.ollama_proxy.get_redis_client')
    def test_status_found(self, mock_get_redis, client, mock_redis):
        """Test status retrieval for existing job."""
        # Setup mocks
        mock_get_redis.return_value = mock_redis
        
        # Mock Redis get result
        job_id = "test-status-job"
        mock_redis.get.return_value = json.dumps({
            "status": "success",
            "data": {
                "response": "Test response",
                "model": "mistral"
            }
        })
        
        # Make request
        response = client.get(f"/api/status/{job_id}")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "success"
    
    @patch('app.routers.ollama_proxy.get_redis_client')
    def test_status_not_found(self, mock_get_redis, client, mock_redis):
        """Test status retrieval for non-existent job."""
        # Setup mocks
        mock_get_redis.return_value = mock_redis
        mock_redis.get.return_value = None
        
        # Make request
        job_id = "non-existent-job"
        response = client.get(f"/api/status/{job_id}")
        
        # Assertions
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestRedisConnection:
    """Tests for Redis connection handling."""
    
    @patch('app.routers.ollama_proxy.redis.from_url')
    def test_redis_connection_success(self, mock_from_url):
        """Test successful Redis connection."""
        from app.routers.ollama_proxy import get_redis_client
        
        # Reset global client
        import app.routers.ollama_proxy as module
        module._redis_client = None
        
        # Mock Redis client
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_from_url.return_value = mock_client
        
        # Get client
        client = get_redis_client()
        
        # Assertions
        assert client is not None
        mock_client.ping.assert_called_once()
    
    @patch('app.routers.ollama_proxy.redis.from_url')
    def test_redis_connection_failure(self, mock_from_url):
        """Test Redis connection failure."""
        from app.routers.ollama_proxy import get_redis_client
        
        # Reset global client
        import app.routers.ollama_proxy as module
        module._redis_client = None
        
        # Mock connection failure
        mock_from_url.side_effect = Exception("Connection refused")
        
        # Attempt to get client
        with pytest.raises(ConnectionError):
            get_redis_client()


class TestRequestValidation:
    """Tests for request validation."""
    
    def test_generate_empty_prompt(self, client):
        """Test validation for empty prompt."""
        response = client.post(
            "/api/generate",
            json={
                "prompt": "",
                "model": "mistral"
            }
        )
        
        # Pydantic validation should fail
        assert response.status_code == 422
    
    def test_chat_empty_messages(self, client):
        """Test validation for empty messages."""
        response = client.post(
            "/api/chat",
            json={
                "messages": [],
                "model": "mistral"
            }
        )
        
        # Pydantic validation should fail
        assert response.status_code == 422
    
    def test_generate_missing_prompt(self, client):
        """Test validation for missing prompt."""
        response = client.post(
            "/api/generate",
            json={
                "model": "mistral"
            }
        )
        
        # Pydantic validation should fail
        assert response.status_code == 422
    
    def test_generate_invalid_model(self, client):
        """Test validation for invalid model name."""
        response = client.post(
            "/api/generate",
            json={
                "prompt": "Test prompt",
                "model": "invalid-model-name"
            }
        )
        
        # Pydantic validation should fail
        assert response.status_code == 422
        assert "not available" in response.json()["detail"][0]["msg"].lower()
    
    def test_chat_invalid_model(self, client):
        """Test validation for invalid model in chat."""
        response = client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "gpt-4"  # Not an Ollama model
            }
        )
        
        # Pydantic validation should fail
        assert response.status_code == 422
        assert "not available" in response.json()["detail"][0]["msg"].lower()
