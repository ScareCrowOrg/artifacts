"""
Unit tests for HTTP timeout configuration and error handling.

Tests that HTTP clients properly timeout and propagate errors to applications.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
import requests

from app.config import HTTP_CONNECTION_TIMEOUT, HTTP_READ_TIMEOUT


class TestHTTPTimeoutConfiguration:
    """Tests for HTTP timeout configuration."""
    
    def test_default_timeout_values(self):
        """Test that default timeout values are reasonable."""
        assert HTTP_CONNECTION_TIMEOUT > 0
        assert HTTP_READ_TIMEOUT > 0
        # Connection timeout should be shorter than read timeout
        assert HTTP_CONNECTION_TIMEOUT <= HTTP_READ_TIMEOUT
        # Total timeout should not be excessive
        assert HTTP_CONNECTION_TIMEOUT + HTTP_READ_TIMEOUT < 60
    
    @patch.dict('os.environ', {'HTTP_CONNECTION_TIMEOUT': '5.0', 'HTTP_READ_TIMEOUT': '15.0'})
    def test_timeout_from_env_vars(self):
        """Test that timeout values can be configured via environment variables."""
        # Reimport to pick up new env vars
        from importlib import reload
        import app.config as config
        reload(config)
        
        assert config.HTTP_CONNECTION_TIMEOUT == 5.0
        assert config.HTTP_READ_TIMEOUT == 15.0


class TestAuthRouterTimeouts:
    """Tests for auth_router timeout handling."""
    
    @pytest.mark.asyncio
    @patch.dict('os.environ', {'GOOGLE_CLIENT_ID': 'test-client-id', 'GOOGLE_CLIENT_SECRET': 'test-secret'})
    @patch('app.database.db.get_config', return_value={})
    @patch('app.routers.auth_router.httpx.AsyncClient')
    async def test_google_oauth_timeout_handling(self, mock_client, mock_db_config):
        """Test that Google OAuth properly handles timeouts."""
        from app.routers.auth_router import google_callback
        
        # Mock the client to raise a timeout exception
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.post.side_effect = httpx.TimeoutException("Connection timeout")
        mock_client.return_value = mock_instance
        
        # Prepare request data
        request_data = {
            "code": "test_code",
            "redirect_uri": "http://localhost:3000/callback"
        }
        
        # Should raise HTTPException with 504 status
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await google_callback(request_data)
        
        assert exc_info.value.status_code == 504
        assert "Timeout" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    @patch.dict('os.environ', {'GOOGLE_CLIENT_ID': 'test-client-id', 'GOOGLE_CLIENT_SECRET': 'test-secret'})
    @patch('app.database.db.get_config', return_value={})
    @patch('app.routers.auth_router.httpx.AsyncClient')
    async def test_google_oauth_connection_error_handling(self, mock_client, mock_db_config):
        """Test that Google OAuth properly handles connection errors."""
        from app.routers.auth_router import google_callback
        
        # Mock the client to raise a request error
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.post.side_effect = httpx.RequestError("Connection failed")
        mock_client.return_value = mock_instance
        
        # Prepare request data
        request_data = {
            "code": "test_code",
            "redirect_uri": "http://localhost:3000/callback"
        }
        
        # Should raise HTTPException with 503 status
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await google_callback(request_data)
        
        assert exc_info.value.status_code == 503
        # Verify error detail exists (don't check specific language)
        assert len(exc_info.value.detail) > 0


class TestNgrokHelperTimeouts:
    """Tests for ngrok helper timeout handling."""
    
    @patch('requests.get')
    @patch('subprocess.Popen')
    @patch('shutil.which', return_value='/usr/bin/ngrok')
    def test_ngrok_tunnel_timeout_handling(self, mock_which, mock_popen, mock_get):
        """Test that ngrok tunnel creation properly handles timeouts."""
        from app.routers.ngrok.helpers import start_ngrok_tunnel
        
        # Mock the process
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        
        # Mock requests to raise timeout
        mock_get.side_effect = requests.exceptions.Timeout("Request timeout")
        
        # Should handle timeout and return error
        success, url, error = start_ngrok_tunnel(port=9000)
        
        assert success is False
        assert url is None
        assert "Failed to get ngrok public URL" in error
        # Process should be killed after timeout
        assert mock_process.kill.called
    
    @patch('requests.get')
    @patch('subprocess.Popen')
    @patch('shutil.which', return_value='/usr/bin/ngrok')
    def test_ngrok_tunnel_connection_error_handling(self, mock_which, mock_popen, mock_get):
        """Test that ngrok tunnel creation properly handles connection errors."""
        from app.routers.ngrok.helpers import start_ngrok_tunnel
        
        # Mock the process
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        
        # Mock requests to raise connection error
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        # Should handle connection error
        success, url, error = start_ngrok_tunnel(port=9000)
        
        assert success is False
        assert url is None
        # Verify error message exists (don't check specific language)
        assert error is not None
        assert len(error) > 0


class TestExistingServiceTimeouts:
    """Tests to verify existing services have proper timeout configuration."""
    
    def test_ollama_timeout_configured(self):
        """Test that Ollama service has timeout configured."""
        from app.config import OLLAMA_TIMEOUT
        assert OLLAMA_TIMEOUT > 0
        assert isinstance(OLLAMA_TIMEOUT, int)
    
    def test_gemini_timeout_configured(self):
        """Test that Gemini service has timeout configured."""
        from app.config import GEMINI_TIMEOUT
        assert GEMINI_TIMEOUT > 0
        assert isinstance(GEMINI_TIMEOUT, int)
    
    def test_openai_timeout_configured(self):
        """Test that OpenAI service has timeout configured."""
        from app.config import OPENAI_TIMEOUT
        assert OPENAI_TIMEOUT > 0
        assert isinstance(OPENAI_TIMEOUT, float) or isinstance(OPENAI_TIMEOUT, int)
    
    @pytest.mark.asyncio
    async def test_ollama_timeout_exception_handling(self):
        """Test that Ollama service properly handles timeout exceptions."""
        from app.ollama_service import chamar_ollama
        
        with patch('app.ollama_service.httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.post.side_effect = httpx.TimeoutException("Timeout")
            mock_client.return_value = mock_instance
            
            with pytest.raises(httpx.TimeoutException):
                await chamar_ollama("test prompt")
    
    @pytest.mark.asyncio
    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'})
    @patch('app.gemini_service.GEMINI_API_KEY', 'test-key')
    async def test_gemini_timeout_exception_handling(self):
        """Test that Gemini service properly handles timeout exceptions."""
        from app.gemini_service import chamar_gemini
        
        with patch('app.gemini_service.httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.post.side_effect = httpx.TimeoutException("Timeout")
            mock_client.return_value = mock_instance
            
            with pytest.raises(httpx.TimeoutException):
                await chamar_gemini([{"role": "user", "parts": [{"text": "test"}]}])
    
    @pytest.mark.asyncio
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    @patch('app.openai_service.api_client.OPENAI_API_KEY', 'test-key')
    async def test_openai_timeout_exception_handling(self):
        """Test that OpenAI service properly handles timeout exceptions."""
        from app.openai_service.api_client import chamar_openai
        
        with patch('app.openai_service.api_client.httpx.AsyncClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.post.side_effect = httpx.TimeoutException("Timeout")
            mock_client.return_value = mock_instance
            
            payload = {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "test"}]}
            
            with pytest.raises(RuntimeError) as exc_info:
                await chamar_openai(payload)
            
            assert "Timeout" in str(exc_info.value)


class TestAlertingTimeout:
    """Tests for alerting module timeout handling."""
    
    @patch.dict('os.environ', {'SLACK_WEBHOOK_URL': 'https://hooks.slack.com/test'})
    @patch('app.alerting.SLACK_WEBHOOK', 'https://hooks.slack.com/test')
    @patch('app.alerting.requests.post')
    def test_alerting_has_timeout(self, mock_post):
        """Test that alerting requests include timeout."""
        from app.alerting import send_alert
        
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        send_alert("Test", "Message")
        
        # Check that timeout was passed
        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        assert 'timeout' in call_kwargs
        assert call_kwargs['timeout'] == 5
    
    @patch.dict('os.environ', {'SLACK_WEBHOOK_URL': 'https://hooks.slack.com/test'})
    @patch('app.alerting.SLACK_WEBHOOK', 'https://hooks.slack.com/test')
    @patch('app.alerting.requests.post')
    def test_alerting_handles_timeout(self, mock_post):
        """Test that alerting handles timeout gracefully."""
        from app.alerting import send_alert
        
        mock_post.side_effect = requests.exceptions.RequestException("Timeout")
        
        # Should return False instead of raising exception
        result = send_alert("Test", "Message")
        
        assert result is False
