"""
Unit tests for AiderProvider

Tests the Aider code execution integration via aider-worker service.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.providers.aider_provider import AiderProvider
from app.services.llm_provider_interface import LLMProviderError


class TestAiderProviderInitialization:
    """Tests for AiderProvider initialization."""
    
    def test_initialization_with_defaults(self):
        """Test provider initialization with default config."""
        provider = AiderProvider()
        
        assert provider.provider_name == "scare-aider"
        assert provider.model_name == "aider-coder"
        assert provider._base_url is not None
        assert provider._timeout >= 10
        assert provider._timeout <= 1800
    
    def test_initialization_with_custom_config(self):
        """Test provider initialization with custom config."""
        provider = AiderProvider(
            base_url="http://custom-worker:9000",
            timeout=60
        )
        
        assert provider._base_url == "http://custom-worker:9000"
        assert provider._timeout == 60
    
    def test_base_url_trailing_slash_removed(self):
        """Test that trailing slash is removed from base_url."""
        provider = AiderProvider(
            base_url="http://worker:8001/"
        )
        
        assert provider._base_url == "http://worker:8001"
    
    def test_timeout_minimum_enforced(self):
        """Test that timeout minimum (10s) is enforced."""
        provider = AiderProvider(timeout=5)
        
        assert provider._timeout == 10
    
    def test_timeout_maximum_enforced(self):
        """Test that timeout maximum (1800s) is enforced."""
        provider = AiderProvider(timeout=2000)
        
        assert provider._timeout == 1800


class TestAiderProviderVerifyAvailability:
    """Tests for verify_availability method."""
    
    @pytest.mark.asyncio
    async def test_verify_availability_healthy(self):
        """Test verify_availability when service is healthy."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "orchestrator_initialized": True
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            result = await provider.verify_availability()
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_verify_availability_unhealthy(self):
        """Test verify_availability when service is unhealthy."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "unhealthy",
            "orchestrator_initialized": False
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            result = await provider.verify_availability()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_verify_availability_service_error(self):
        """Test verify_availability when service returns error."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 503
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            result = await provider.verify_availability()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_verify_availability_connection_error(self):
        """Test verify_availability when connection fails."""
        provider = AiderProvider()
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            
            result = await provider.verify_availability()
            
            assert result is False


class TestAiderProviderProcessChat:
    """Tests for process_chat method."""
    
    @pytest.mark.asyncio
    async def test_process_chat_successful(self):
        """Test successful chat processing."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "test-session",
            "status": "success",
            "output": "Code modifications completed successfully",
            "metrics": {"files_modified": 2, "lines_changed": 15}
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            result = await provider.process_chat(
                user_message="Add type hints to functions",
                session_id="test-session"
            )
            
            assert "response" in result
            assert result["response"] == "Code modifications completed successfully"
            assert result["status"] == "success"
            assert "metrics" in result
            assert result["metrics"]["files_modified"] == 2
    
    @pytest.mark.asyncio
    async def test_process_chat_with_files(self):
        """Test chat processing with file list."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "test-session",
            "status": "success",
            "output": "Modified app/utils.py",
            "metrics": {}
        }
        
        files = ["app/utils.py", "app/models.py"]
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            result = await provider.process_chat(
                user_message="Add docstrings",
                files=files,
                session_id="test-session"
            )
            
            # Verify files were included in request
            call_kwargs = mock_post.call_args[1]
            assert "json" in call_kwargs
            assert "files" in call_kwargs["json"]
            assert call_kwargs["json"]["files"] == files
            assert result["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_process_chat_with_model_override(self):
        """Test chat processing with custom model."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "test-session",
            "status": "success",
            "output": "Output",
            "metrics": {}
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            await provider.process_chat(
                user_message="Test",
                model="gpt-4",
                session_id="test-session"
            )
            
            # Verify model was included in request
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["json"]["model"] == "gpt-4"
    
    @pytest.mark.asyncio
    async def test_process_chat_with_timeout_override(self):
        """Test chat processing with timeout override."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "test-session",
            "status": "success",
            "output": "Output",
            "metrics": {}
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            await provider.process_chat(
                user_message="Test",
                timeout=180,
                session_id="test-session"
            )
            
            # Verify timeout was included in request
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["json"]["timeout"] == 180
    
    @pytest.mark.asyncio
    async def test_process_chat_with_additional_args(self):
        """Test chat processing with additional CLI arguments."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "test-session",
            "status": "success",
            "output": "Output",
            "metrics": {}
        }
        
        additional_args = ["--yes", "--no-auto-commits"]
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            await provider.process_chat(
                user_message="Test",
                additional_args=additional_args,
                session_id="test-session"
            )
            
            # Verify additional_args were included in request
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["json"]["additional_args"] == additional_args
    
    @pytest.mark.asyncio
    async def test_process_chat_defaults_session_id(self):
        """Test that session_id defaults to 'default-session' if not provided."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "default-session",
            "status": "success",
            "output": "Output",
            "metrics": {}
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            await provider.process_chat(
                user_message="Test message"
            )
            
            # Verify URL includes default-session
            call_args = mock_post.call_args[0]
            assert "default-session" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_process_chat_conversation_id_to_session_id(self):
        """Test that conversation_id is properly converted to session_id."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "conversation-conv_123456",
            "status": "success",
            "output": "Output",
            "metrics": {}
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            await provider.process_chat(
                user_message="Test message",
                conversation_id="conv_123456"
            )
            
            # Verify URL includes conversation-prefixed session_id
            call_args = mock_post.call_args[0]
            assert "conversation-conv_123456" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_process_chat_invalid_user_message(self):
        """Test that empty user_message raises error."""
        provider = AiderProvider()
        
        with pytest.raises(LLMProviderError) as exc_info:
            await provider.process_chat(
                user_message="",
                session_id="test-session"
            )
        
        assert "non-empty string" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_process_chat_none_user_message(self):
        """Test that None user_message raises error."""
        provider = AiderProvider()
        
        with pytest.raises(LLMProviderError) as exc_info:
            await provider.process_chat(
                user_message=None,
                session_id="test-session"
            )
        
        assert "non-empty string" in str(exc_info.value)


class TestAiderProviderErrorHandling:
    """Tests for error handling in AiderProvider."""
    
    @pytest.mark.asyncio
    async def test_process_chat_http_400_error(self):
        """Test error handling for HTTP 400 (bad request)."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid request: missing required field"
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            with pytest.raises(LLMProviderError) as exc_info:
                await provider.process_chat(
                    user_message="Test",
                    session_id="test-session"
                )
            
            assert "Invalid request" in str(exc_info.value)
            assert exc_info.value.provider == "scare-aider"
    
    @pytest.mark.asyncio
    async def test_process_chat_http_503_error(self):
        """Test error handling for HTTP 503 (service unavailable)."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Orchestrator not initialized"
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            with pytest.raises(LLMProviderError) as exc_info:
                await provider.process_chat(
                    user_message="Test",
                    session_id="test-session"
                )
            
            assert "Service unavailable" in str(exc_info.value)
            assert "orchestrator not initialized" in str(exc_info.value).lower()
            assert exc_info.value.provider == "scare-aider"
    
    @pytest.mark.asyncio
    async def test_process_chat_http_504_error(self):
        """Test error handling for HTTP 504 (timeout)."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 504
        mock_response.text = "Execution timed out"
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            with pytest.raises(LLMProviderError) as exc_info:
                await provider.process_chat(
                    user_message="Test",
                    session_id="test-session"
                )
            
            assert "Execution timeout" in str(exc_info.value)
            assert exc_info.value.provider == "scare-aider"
    
    @pytest.mark.asyncio
    async def test_process_chat_http_500_error(self):
        """Test error handling for HTTP 500 (execution failed)."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Execution failed: command error"
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            with pytest.raises(LLMProviderError) as exc_info:
                await provider.process_chat(
                    user_message="Test",
                    session_id="test-session"
                )
            
            assert "Execution failed" in str(exc_info.value)
            assert exc_info.value.provider == "scare-aider"
    
    @pytest.mark.asyncio
    async def test_process_chat_timeout_error(self):
        """Test error handling for timeout."""
        provider = AiderProvider()
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("Request timeout")
            )
            
            with pytest.raises(LLMProviderError) as exc_info:
                await provider.process_chat(
                    user_message="Test",
                    session_id="test-session"
                )
            
            assert "timed out" in str(exc_info.value).lower()
            assert exc_info.value.provider == "scare-aider"
    
    @pytest.mark.asyncio
    async def test_process_chat_connection_error(self):
        """Test error handling for connection errors."""
        provider = AiderProvider()
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            
            with pytest.raises(LLMProviderError) as exc_info:
                await provider.process_chat(
                    user_message="Test",
                    session_id="test-session"
                )
            
            assert "cannot connect" in str(exc_info.value).lower()
            assert "ensure the service is running" in str(exc_info.value).lower()
            assert exc_info.value.provider == "scare-aider"
    
    @pytest.mark.asyncio
    async def test_process_chat_generic_http_error(self):
        """Test error handling for generic HTTP errors."""
        provider = AiderProvider()
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPError("Generic HTTP error")
            )
            
            with pytest.raises(LLMProviderError) as exc_info:
                await provider.process_chat(
                    user_message="Test",
                    session_id="test-session"
                )
            
            assert "http error" in str(exc_info.value).lower()
            assert exc_info.value.provider == "scare-aider"
    
    @pytest.mark.asyncio
    async def test_process_chat_unexpected_error(self):
        """Test error handling for unexpected errors."""
        provider = AiderProvider()
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("Unexpected error")
            )
            
            with pytest.raises(LLMProviderError) as exc_info:
                await provider.process_chat(
                    user_message="Test",
                    session_id="test-session"
                )
            
            assert "failed to process" in str(exc_info.value).lower()
            assert exc_info.value.provider == "scare-aider"


class TestAiderProviderSessionManagement:
    """Tests for session management in AiderProvider."""
    
    @pytest.mark.asyncio
    async def test_session_id_from_conversation_id(self):
        """Test that session_id is built from conversation_id."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "conversation-abc123",
            "status": "success",
            "output": "Output",
            "metrics": {}
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            await provider.process_chat(
                user_message="Test message",
                conversation_id="abc123"
            )
            
            # Verify URL includes conversation-based session_id
            call_args = mock_post.call_args[0]
            assert "conversation-abc123" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_session_id_fallback_when_conversation_id_none(self):
        """Test that session_id defaults to 'default-session' when conversation_id is None."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "default-session",
            "status": "success",
            "output": "Output",
            "metrics": {}
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            await provider.process_chat(
                user_message="Test message",
                conversation_id=None
            )
            
            # Verify URL includes default-session
            call_args = mock_post.call_args[0]
            assert "default-session" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_explicit_session_id_takes_priority(self):
        """Test that explicit session_id takes priority over conversation_id."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "explicit-session",
            "status": "success",
            "output": "Output",
            "metrics": {}
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            await provider.process_chat(
                user_message="Test message",
                session_id="explicit-session",
                conversation_id="abc123"
            )
            
            # Verify URL uses explicit session_id, not conversation-based
            call_args = mock_post.call_args[0]
            assert "explicit-session" in call_args[0]
            assert "conversation-abc123" not in call_args[0]


class TestAiderProviderIntegration:
    """Integration-style tests for AiderProvider."""
    
    @pytest.mark.asyncio
    async def test_full_code_modification_flow(self):
        """Test a full code modification flow."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "conv-123",
            "status": "success",
            "output": "Added type hints to 3 functions in app/utils.py",
            "metrics": {
                "files_modified": 1,
                "lines_changed": 12,
                "execution_time": 5.2
            }
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            result = await provider.process_chat(
                user_message="Add type hints to all functions",
                files=["app/utils.py"],
                session_id="conv-123"
            )
            
            assert "type hints" in result["response"].lower()
            assert result["status"] == "success"
            assert result["metrics"]["files_modified"] == 1
    
    @pytest.mark.asyncio
    async def test_timeout_enforcement_on_request(self):
        """Test that timeout bounds are enforced on per-request timeout."""
        provider = AiderProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "test-session",
            "status": "success",
            "output": "Output",
            "metrics": {}
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            # Test with timeout too low (should be adjusted to 10s)
            await provider.process_chat(
                user_message="Test",
                timeout=5,
                session_id="test-session"
            )
            
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["json"]["timeout"] == 10
            
            # Test with timeout too high (should be adjusted to 1800s)
            await provider.process_chat(
                user_message="Test",
                timeout=2500,
                session_id="test-session"
            )
            
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["json"]["timeout"] == 1800
