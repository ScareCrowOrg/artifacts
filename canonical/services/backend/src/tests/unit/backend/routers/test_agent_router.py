"""
Unit tests for Agent Mode Router.

Tests the Agent Mode API endpoints, focusing on the user attribute fix
for the AttributeError: 'User' object has no attribute 'username'.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import HTTPException

from app.routers.agent_router import (
    create_session,
    process_command,
    close_session,
    get_session_status,
    list_sessions
)
from app.models import User


class TestAgentRouterUserAttributes:
    """Test that agent router properly uses User model attributes."""
    
    @pytest.mark.asyncio
    async def test_create_session_uses_email_not_username(self, mock_current_user):
        """Test that create_session uses email instead of username."""
        from app.routers.agent_router import CreateSessionRequest
        
        # Create a real User object to ensure it matches the actual model
        current_user = User(
            id="test-user-123",
            name="Test User",
            email="test@example.com"
        )
        
        # Mock the controller
        mock_controller = Mock()
        mock_controller.create_session = AsyncMock(return_value={
            "session_id": "conv_123",
            "status": "created"
        })
        
        # Create request
        request = CreateSessionRequest(
            conversation_id="conv_123",
            files=["test.py"],
            model="ollama/qwen2.5-coder:7b"
        )
        
        # Call the endpoint - should not raise AttributeError
        response = await create_session(
            request=request,
            controller=mock_controller,
            current_user=current_user
        )
        
        # Verify it works and returns expected response
        assert response["session_id"] == "conv_123"
        assert response["status"] == "created"
        
        # Verify the controller was called
        mock_controller.create_session.assert_called_once_with(
            conversation_id="conv_123",
            files=["test.py"],
            model="ollama/qwen2.5-coder:7b"
        )
    
    @pytest.mark.asyncio
    async def test_create_session_logs_user_email(self, mock_current_user, caplog):
        """Test that create_session logs user email instead of username."""
        from app.routers.agent_router import CreateSessionRequest
        import logging
        
        # Enable logging for the test
        caplog.set_level(logging.INFO)
        
        # Create a real User object
        current_user = User(
            id="test-user-123",
            name="Test User",
            email="test@example.com"
        )
        
        # Mock the controller
        mock_controller = Mock()
        mock_controller.create_session = AsyncMock(return_value={
            "session_id": "conv_123",
            "status": "created"
        })
        
        # Create request
        request = CreateSessionRequest(
            conversation_id="conv_123",
            files=[],
            model="ollama/qwen2.5-coder:7b"
        )
        
        # Call the endpoint
        await create_session(
            request=request,
            controller=mock_controller,
            current_user=current_user
        )
        
        # Check that logs contain email but not username
        log_messages = [record.message for record in caplog.records]
        
        # Should contain email in logs
        assert any("test@example.com" in msg for msg in log_messages)
        
        # Should NOT contain "username" attribute access
        assert not any("username" in msg and "test" in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_process_command_uses_email_not_username(self):
        """Test that process_command uses email instead of username."""
        from app.routers.agent_router import ChatRequest
        
        # Create a real User object
        current_user = User(
            id="test-user-123",
            name="Test User",
            email="test@example.com"
        )
        
        # Mock the controller with async generator
        async def mock_generator():
            yield {"type": "log", "content": "Processing..."}
            yield {"type": "status", "status": "completed"}
        
        mock_controller = Mock()
        mock_controller.process_command = Mock(return_value=mock_generator())
        
        # Create request
        request = ChatRequest(
            conversation_id="conv_123",
            command="Add docstrings"
        )
        
        # Call the endpoint - should not raise AttributeError
        response = await process_command(
            request=request,
            controller=mock_controller,
            current_user=current_user
        )
        
        # Verify StreamingResponse is returned
        from fastapi.responses import StreamingResponse
        assert isinstance(response, StreamingResponse)
    
    @pytest.mark.asyncio
    async def test_close_session_uses_email_not_username(self, caplog):
        """Test that close_session uses email instead of username."""
        import logging
        
        # Enable logging
        caplog.set_level(logging.INFO)
        
        # Create a real User object
        current_user = User(
            id="test-user-123",
            name="Test User",
            email="test@example.com"
        )
        
        # Mock the controller
        mock_controller = Mock()
        mock_controller.close_session = AsyncMock(return_value={
            "session_id": "conv_123",
            "status": "closed"
        })
        
        # Call the endpoint
        response = await close_session(
            conversation_id="conv_123",
            controller=mock_controller,
            current_user=current_user
        )
        
        # Verify response
        assert response["session_id"] == "conv_123"
        assert response["status"] == "closed"
        
        # Check logs contain email
        log_messages = [record.message for record in caplog.records]
        assert any("test@example.com" in msg for msg in log_messages)
    
    @pytest.mark.asyncio
    async def test_create_session_handles_attribute_error(self):
        """Test that create_session handles AttributeError gracefully."""
        from app.routers.agent_router import CreateSessionRequest
        
        # Create a real User object
        current_user = User(
            id="test-user-123",
            name="Test User",
            email="test@example.com"
        )
        
        # Mock the controller to raise an error
        mock_controller = Mock()
        mock_controller.create_session = AsyncMock(
            side_effect=Exception("Session creation failed")
        )
        
        # Create request
        request = CreateSessionRequest(
            conversation_id="conv_123",
            files=[],
            model="ollama/qwen2.5-coder:7b"
        )
        
        # Call should raise HTTPException, not AttributeError
        with pytest.raises(HTTPException) as exc_info:
            await create_session(
                request=request,
                controller=mock_controller,
                current_user=current_user
            )
        
        # Verify it's a 500 error with proper message
        assert exc_info.value.status_code == 500
        assert "Failed to create session" in exc_info.value.detail
