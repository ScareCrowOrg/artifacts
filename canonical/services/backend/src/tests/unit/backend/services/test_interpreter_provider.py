"""
Unit tests for InterpreterProvider

Tests the Open Interpreter integration via aider-worker service.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.providers.interpreter_provider import InterpreterProvider
from app.services.llm_provider_interface import LLMProviderError


class TestInterpreterProviderInitialization:
    """Tests for InterpreterProvider initialization."""
    
    def test_initialization_with_defaults(self):
        """Test provider initialization with default config."""
        provider = InterpreterProvider()
        
        assert provider.provider_name == "scare-worker"
        assert provider.model_name == "open-interpreter"
        assert provider._base_url is not None
        assert provider._timeout > 0
    
    def test_initialization_with_custom_config(self):
        """Test provider initialization with custom config."""
        provider = InterpreterProvider(
            base_url="http://custom-worker:9000",
            timeout=60
        )
        
        assert provider._base_url == "http://custom-worker:9000"
        assert provider._timeout == 60
    
    def test_base_url_trailing_slash_removed(self):
        """Test that trailing slash is removed from base_url."""
        provider = InterpreterProvider(
            base_url="http://worker:8001/"
        )
        
        assert provider._base_url == "http://worker:8001"


class TestInterpreterProviderVerifyAvailability:
    """Tests for verify_availability method."""
    
    @pytest.mark.asyncio
    async def test_verify_availability_healthy(self):
        """Test verify_availability when service is healthy."""
        provider = InterpreterProvider()
        
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
        provider = InterpreterProvider()
        
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
        provider = InterpreterProvider()
        
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
        provider = InterpreterProvider()
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            
            result = await provider.verify_availability()
            
            assert result is False


class TestInterpreterProviderProcessChat:
    """Tests for process_chat method."""
    
    @pytest.mark.asyncio
    async def test_process_chat_successful_with_analysis_and_plan(self):
        """Test successful chat processing with analysis and plan."""
        provider = InterpreterProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "test-session",
            "status": "success",
            "analysis": "The project structure is well organized.",
            "plan": "1. Review code\n2. Add tests\n3. Deploy",
            "output": "Full interpreter output here",
            "metrics": {}
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            result = await provider.process_chat(
                user_message="Analyze the project",
                session_id="test-session"
            )
            
            assert "response" in result
            assert "**Analysis:**" in result["response"]
            assert "**Action Plan:**" in result["response"]
            assert "The project structure is well organized." in result["response"]
            assert "1. Review code" in result["response"]
            assert result["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_process_chat_with_conversation_history(self):
        """Test chat processing with conversation history."""
        provider = InterpreterProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "test-session",
            "status": "success",
            "analysis": "Analysis based on context",
            "plan": "Next steps",
            "output": "Output",
            "metrics": {}
        }
        
        history = [
            {"role": "user", "content": "What is the project about?"},
            {"role": "assistant", "content": "It's a ScareVerse project."}
        ]
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            result = await provider.process_chat(
                user_message="Continue analysis",
                conversation_history=history,
                session_id="test-session"
            )
            
            # Verify history was included in request
            call_kwargs = mock_post.call_args[1]
            assert "json" in call_kwargs
            assert "history" in call_kwargs["json"]
            assert len(call_kwargs["json"]["history"]) == 2
            assert result["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_process_chat_filters_system_messages(self):
        """Test that system messages are filtered from history."""
        provider = InterpreterProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "test-session",
            "status": "success",
            "analysis": "Analysis",
            "plan": "Plan",
            "output": "Output",
            "metrics": {}
        }
        
        history = [
            {"role": "system", "content": "System message"},
            {"role": "user", "content": "User message"},
            {"role": "assistant", "content": "Assistant message"}
        ]
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            await provider.process_chat(
                user_message="Test",
                conversation_history=history,
                session_id="test-session"
            )
            
            # Verify system message was filtered
            call_kwargs = mock_post.call_args[1]
            history_sent = call_kwargs["json"]["history"]
            assert len(history_sent) == 2
            assert all(msg["role"] != "system" for msg in history_sent)
    
    @pytest.mark.asyncio
    async def test_process_chat_with_system_instructions(self):
        """Test chat processing with system instructions."""
        provider = InterpreterProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "test-session",
            "status": "success",
            "analysis": "Analysis",
            "plan": "Plan",
            "output": "Output",
            "metrics": {}
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            await provider.process_chat(
                user_message="Test message",
                system_instructions="Be concise and direct",
                session_id="test-session"
            )
            
            # Verify system instructions were prepended to prompt
            call_kwargs = mock_post.call_args[1]
            prompt = call_kwargs["json"]["prompt"]
            assert "System Instructions:" in prompt
            assert "Be concise and direct" in prompt
            assert "User Request:" in prompt
    
    @pytest.mark.asyncio
    async def test_process_chat_defaults_session_id(self):
        """Test that session_id defaults to 'default-session' if not provided."""
        provider = InterpreterProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "default-session",
            "status": "success",
            "analysis": "Analysis",
            "plan": "Plan",
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
        provider = InterpreterProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "conversation-conv_123456",
            "status": "success",
            "analysis": "Analysis",
            "plan": "Plan",
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
    async def test_process_chat_no_analysis_or_plan(self):
        """Test chat processing when no analysis or plan returned."""
        provider = InterpreterProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "test-session",
            "status": "success",
            "analysis": None,
            "plan": None,
            "output": "Raw interpreter output",
            "metrics": {}
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            result = await provider.process_chat(
                user_message="Test",
                session_id="test-session"
            )
            
            # Should fall back to raw output
            assert result["response"] == "Raw interpreter output"
    
    @pytest.mark.asyncio
    async def test_process_chat_empty_response(self):
        """Test chat processing with completely empty response."""
        provider = InterpreterProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "test-session",
            "status": "success",
            "analysis": None,
            "plan": None,
            "output": "",
            "metrics": {}
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            result = await provider.process_chat(
                user_message="Test",
                session_id="test-session"
            )
            
            # Should return fallback message
            assert "no analysis or plan was generated" in result["response"].lower()


class TestInterpreterProviderErrorHandling:
    """Tests for error handling in InterpreterProvider."""
    
    @pytest.mark.asyncio
    async def test_process_chat_http_error(self):
        """Test error handling for HTTP errors."""
        provider = InterpreterProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            with pytest.raises(LLMProviderError) as exc_info:
                await provider.process_chat(
                    user_message="Test",
                    session_id="test-session"
                )
            
            assert "HTTP 500" in str(exc_info.value)
            assert exc_info.value.provider == "scare-worker"
    
    @pytest.mark.asyncio
    async def test_process_chat_timeout_error(self):
        """Test error handling for timeout."""
        provider = InterpreterProvider()
        
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
            assert exc_info.value.provider == "scare-worker"
    
    @pytest.mark.asyncio
    async def test_process_chat_connection_error(self):
        """Test error handling for connection errors."""
        provider = InterpreterProvider()
        
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
            assert exc_info.value.provider == "scare-worker"
    
    @pytest.mark.asyncio
    async def test_process_chat_generic_http_error(self):
        """Test error handling for generic HTTP errors."""
        provider = InterpreterProvider()
        
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
            assert exc_info.value.provider == "scare-worker"
    
    @pytest.mark.asyncio
    async def test_process_chat_unexpected_error(self):
        """Test error handling for unexpected errors."""
        provider = InterpreterProvider()
        
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
            assert exc_info.value.provider == "scare-worker"


class TestInterpreterProviderIntegration:
    """Integration-style tests for InterpreterProvider."""
    
    @pytest.mark.asyncio
    async def test_full_conversation_flow(self):
        """Test a full conversation flow with multiple turns."""
        provider = InterpreterProvider()
        
        # First message
        mock_response_1 = MagicMock()
        mock_response_1.status_code = 200
        mock_response_1.json.return_value = {
            "session_id": "conv-123",
            "status": "success",
            "analysis": "Initial analysis",
            "plan": "Step 1",
            "output": "Output 1",
            "metrics": {}
        }
        
        # Second message
        mock_response_2 = MagicMock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = {
            "session_id": "conv-123",
            "status": "success",
            "analysis": "Follow-up analysis",
            "plan": "Step 2",
            "output": "Output 2",
            "metrics": {}
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(side_effect=[mock_response_1, mock_response_2])
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            # First turn
            result_1 = await provider.process_chat(
                user_message="Start analysis",
                session_id="conv-123"
            )
            
            assert "Initial analysis" in result_1["response"]
            
            # Second turn with history
            history = [
                {"role": "user", "content": "Start analysis"},
                {"role": "assistant", "content": result_1["response"]}
            ]
            
            result_2 = await provider.process_chat(
                user_message="Continue",
                conversation_history=history,
                session_id="conv-123"
            )
            
            assert "Follow-up analysis" in result_2["response"]
            
            # Verify both calls used same session_id
            for call in mock_post.call_args_list:
                assert "conv-123" in call[0][0]


class TestInterpreterProviderSessionManagement:
    """Tests for session management in InterpreterProvider."""
    
    @pytest.mark.asyncio
    async def test_session_id_from_conversation_id(self):
        """Test that session_id is built from conversation_id."""
        provider = InterpreterProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "conversation-abc123",
            "status": "success",
            "analysis": "Analysis",
            "plan": "Plan",
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
        provider = InterpreterProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "default-session",
            "status": "success",
            "analysis": "Analysis",
            "plan": "Plan",
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
        provider = InterpreterProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "explicit-session",
            "status": "success",
            "analysis": "Analysis",
            "plan": "Plan",
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


class TestInterpreterProviderCustomInstructions:
    """Tests for custom instructions handling in InterpreterProvider."""
    
    @pytest.mark.asyncio
    async def test_process_chat_with_custom_instructions(self):
        """Test chat processing with custom instructions."""
        provider = InterpreterProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "test-session",
            "status": "success",
            "analysis": "Analysis",
            "plan": "Plan",
            "output": "Output",
            "metrics": {}
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            await provider.process_chat(
                user_message="Test message",
                custom_instructions="You are a code quality expert. Focus on best practices.",
                session_id="test-session"
            )
            
            # Verify custom instructions were added to payload
            call_kwargs = mock_post.call_args[1]
            assert "json" in call_kwargs
            payload = call_kwargs["json"]
            
            # Check that custom_instructions field is present
            assert "custom_instructions" in payload
            assert payload["custom_instructions"] == "You are a code quality expert. Focus on best practices."
            
            # Check that prompt was prepended with instructions
            assert "System Instructions:" in payload["prompt"]
            assert "You are a code quality expert" in payload["prompt"]
            assert "User Request:" in payload["prompt"]
    
    @pytest.mark.asyncio
    async def test_custom_instructions_take_priority_over_system_instructions(self):
        """Test that custom_instructions take priority over system_instructions."""
        provider = InterpreterProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "test-session",
            "status": "success",
            "analysis": "Analysis",
            "plan": "Plan",
            "output": "Output",
            "metrics": {}
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            await provider.process_chat(
                user_message="Test message",
                system_instructions="Generic system instruction",
                custom_instructions="Specific custom instruction",
                session_id="test-session"
            )
            
            # Verify custom instructions were used, not system instructions
            call_kwargs = mock_post.call_args[1]
            payload = call_kwargs["json"]
            
            assert "custom_instructions" in payload
            assert payload["custom_instructions"] == "Specific custom instruction"
            assert "Specific custom instruction" in payload["prompt"]
            assert "Generic system instruction" not in payload["prompt"]
    
    @pytest.mark.asyncio
    async def test_no_instructions_modification_when_none_provided(self):
        """Test that prompt is not modified when no instructions are provided."""
        provider = InterpreterProvider()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "session_id": "test-session",
            "status": "success",
            "analysis": "Analysis",
            "plan": "Plan",
            "output": "Output",
            "metrics": {}
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post
            
            await provider.process_chat(
                user_message="Test message",
                session_id="test-session"
            )
            
            # Verify prompt was not modified
            call_kwargs = mock_post.call_args[1]
            payload = call_kwargs["json"]
            
            assert payload["prompt"] == "Test message"
            assert "custom_instructions" not in payload or payload.get("custom_instructions") is None
