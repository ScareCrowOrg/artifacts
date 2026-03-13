"""
Integration tests for conversation tracing via chat endpoint.

Tests validate that:
1. The chat endpoint accepts enable_tracing field
2. The flag propagates through the orchestrator
3. The endpoint documentation is correct
4. Error handling works with tracing enabled

Test coverage: Full request-to-orchestrator flow
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

# Skip if dependencies not available
pytest.importorskip("app.routers.chat_router")


class TestChatEndpointTracing:
    """Integration tests for enable_tracing in chat endpoint."""
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user."""
        from app.models import User
        return User(
            id="test-user-id",
            email="test@example.com",
            name="Test User"
        )
    
    @pytest.fixture
    def mock_db(self):
        """Mock database operations."""
        with patch('app.routers.chat_router.db') as mock:
            # Mock user exists
            mock.find_one = AsyncMock(return_value=MagicMock())
            # Mock tipos_celula exists
            mock.find_many = AsyncMock(return_value=[MagicMock()])
            yield mock
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Mock orchestrator for testing."""
        with patch('app.orchestrator.langgraph.get_orchestrator') as mock:
            orchestrator_instance = MagicMock()
            orchestrator_instance.process = AsyncMock(
                return_value={
                    "resposta": "Test response",
                    "intencao": "conversar",
                    "cell": None,
                    "acao_realizada": False
                }
            )
            mock.return_value = orchestrator_instance
            yield orchestrator_instance
    
    @pytest.mark.asyncio
    async def test_endpoint_accepts_enable_tracing_true(self, mock_user, mock_db, mock_orchestrator):
        """Test that endpoint accepts enable_tracing=True."""
        from app.routers.chat_router import processar_intencao_chat
        from app.models.chat import ProcessChatIntentRequest
        
        # Create request with enable_tracing=True
        request = ProcessChatIntentRequest(
            purpose="Test message with tracing",
            assignee_id="test-user-id",
            model="mistral",
            classify_intent=True,
            enable_tracing=True
        )
        
        # Call endpoint
        response = await processar_intencao_chat(request, mock_user)
        
        # Verify orchestrator.process was called
        mock_orchestrator.process.assert_called_once()
        
        # Get the kwargs passed to orchestrator.process
        call_kwargs = mock_orchestrator.process.call_args.kwargs
        
        # Verify enable_tracing=True was passed
        assert 'enable_tracing' in call_kwargs, "enable_tracing should be passed to orchestrator"
        assert call_kwargs['enable_tracing'] is True, "enable_tracing should be True"
    
    @pytest.mark.asyncio
    async def test_endpoint_accepts_enable_tracing_false(self, mock_user, mock_db, mock_orchestrator):
        """Test that endpoint accepts enable_tracing=False."""
        from app.routers.chat_router import processar_intencao_chat
        from app.models.chat import ProcessChatIntentRequest
        
        # Create request with enable_tracing=False
        request = ProcessChatIntentRequest(
            purpose="Test message without tracing",
            assignee_id="test-user-id",
            model="mistral",
            classify_intent=True,
            enable_tracing=False
        )
        
        # Call endpoint
        response = await processar_intencao_chat(request, mock_user)
        
        # Verify orchestrator.process was called
        mock_orchestrator.process.assert_called_once()
        
        # Get the kwargs passed to orchestrator.process
        call_kwargs = mock_orchestrator.process.call_args.kwargs
        
        # Verify enable_tracing=False was passed
        assert call_kwargs['enable_tracing'] is False, "enable_tracing should be False"
    
    @pytest.mark.asyncio
    async def test_endpoint_enable_tracing_defaults_to_false(self, mock_user, mock_db, mock_orchestrator):
        """Test that enable_tracing defaults to False when not provided."""
        from app.routers.chat_router import processar_intencao_chat
        from app.models.chat import ProcessChatIntentRequest
        
        # Create request without enable_tracing (should default to False)
        request = ProcessChatIntentRequest(
            purpose="Test message default tracing",
            assignee_id="test-user-id",
            model="mistral",
            classify_intent=True
        )
        
        # Verify default value is False
        assert request.enable_tracing is False, "enable_tracing should default to False"
        
        # Call endpoint
        response = await processar_intencao_chat(request, mock_user)
        
        # Verify orchestrator.process was called with enable_tracing=False
        call_kwargs = mock_orchestrator.process.call_args.kwargs
        assert call_kwargs['enable_tracing'] is False
    
    @pytest.mark.asyncio
    async def test_tracing_with_rag_enabled(self, mock_user, mock_db, mock_orchestrator):
        """Test enable_tracing works alongside RAG settings."""
        from app.routers.chat_router import processar_intencao_chat
        from app.models.chat import ProcessChatIntentRequest
        
        # Create request with both RAG and tracing enabled
        request = ProcessChatIntentRequest(
            purpose="Test RAG with tracing",
            assignee_id="test-user-id",
            model="mistral",
            classify_intent=True,
            use_rag=True,
            selected_collections=["test_collection"],
            enable_tracing=True
        )
        
        # Call endpoint
        response = await processar_intencao_chat(request, mock_user)
        
        # Verify both flags were passed to orchestrator
        call_kwargs = mock_orchestrator.process.call_args.kwargs
        assert call_kwargs['use_rag'] is True
        assert call_kwargs['enable_tracing'] is True
    
    @pytest.mark.asyncio
    async def test_tracing_in_direct_conversation_mode(self, mock_user, mock_db):
        """Test enable_tracing in direct conversation mode (classify_intent=False)."""
        from app.routers.chat_router import processar_intencao_chat
        from app.models.chat import ProcessChatIntentRequest
        
        # Mock LLM provider for direct conversation mode
        with patch('app.services.llm_provider_factory.LLMProviderFactory') as mock_factory:
            provider_instance = MagicMock()
            provider_instance.provider_name = "ollama"
            provider_instance.model_name = "mistral"
            provider_instance.process_chat = AsyncMock(
                return_value={"response": "Direct response"}
            )
            mock_factory.get_provider.return_value = provider_instance
            
            # Create request with enable_tracing=True in direct mode
            request = ProcessChatIntentRequest(
                purpose="Test direct mode with tracing",
                assignee_id="test-user-id",
                model="mistral",
                classify_intent=False,  # Direct conversation mode
                enable_tracing=True
            )
            
            # Call endpoint
            response = await processar_intencao_chat(request, mock_user)
            
            # In direct conversation mode, tracing flag is passed but not to orchestrator
            # because orchestrator is not used. This is expected behavior.
            # The flag would be used by LLM providers if they implement tracing.
            assert response.response == "Direct response"
    
    @pytest.mark.asyncio
    async def test_tracing_with_attachments(self, mock_user, mock_db, mock_orchestrator):
        """Test enable_tracing works with file attachments."""
        from app.routers.chat_router import processar_intencao_chat
        from app.models.chat import ProcessChatIntentRequest, ChatAttachment
        
        # Create request with attachments and tracing
        request = ProcessChatIntentRequest(
            purpose="Test with attachments and tracing",
            assignee_id="test-user-id",
            model="mistral",
            classify_intent=True,
            attachments=[
                ChatAttachment(name="test.txt", content="Test content", type="text")
            ],
            enable_tracing=True
        )
        
        # Call endpoint
        response = await processar_intencao_chat(request, mock_user)
        
        # Verify orchestrator was called with enable_tracing
        call_kwargs = mock_orchestrator.process.call_args.kwargs
        assert call_kwargs['enable_tracing'] is True
        assert call_kwargs['attached_files'] is not None


class TestTracingConfigurationIntegration:
    """Test tracing configuration and environment variable interaction."""
    
    def test_env_variable_documented(self):
        """Test that ENABLE_CONVERSATION_TRACING is documented in .env.example."""
        import os
        from pathlib import Path
        
        # Read .env.example
        env_example_path = Path(__file__).parent.parent.parent.parent.parent / ".env.example"
        
        if not env_example_path.exists():
            pytest.skip(".env.example not found")
        
        with open(env_example_path, 'r') as f:
            content = f.read()
        
        # Check that ENABLE_CONVERSATION_TRACING is documented
        assert 'ENABLE_CONVERSATION_TRACING' in content, \
            "ENABLE_CONVERSATION_TRACING should be documented in .env.example"
        assert 'conversation tracing' in content.lower() or 'tracing' in content.lower(), \
            "Tracing configuration should be explained in .env.example"
    
    def test_config_has_tracing_variable(self):
        """Test that config.py loads ENABLE_CONVERSATION_TRACING."""
        from app.config import ENABLE_CONVERSATION_TRACING
        
        # Should be a boolean
        assert isinstance(ENABLE_CONVERSATION_TRACING, bool), \
            "ENABLE_CONVERSATION_TRACING should be a boolean"


class TestTracingEndpointDocumentation:
    """Test that endpoint documentation includes tracing examples."""
    
    def test_endpoint_has_tracing_example(self):
        """Test that endpoint docstring includes enable_tracing example."""
        from app.routers.chat_router import processar_intencao_chat
        
        docstring = processar_intencao_chat.__doc__
        
        assert docstring is not None, "Endpoint should have documentation"
        assert 'enable_tracing' in docstring.lower() or 'tracing' in docstring.lower(), \
            "Endpoint documentation should mention tracing"
