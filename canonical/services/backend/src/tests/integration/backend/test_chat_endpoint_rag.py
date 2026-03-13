"""
Integration tests for /api/chat/processar endpoint RAG behavior.

CRITICAL: These tests validate that the chat endpoint respects the requirement
that RAG is ONLY executed when collections are explicitly selected.

Test coverage:
- Endpoint with selected_collections=None (RAG disabled)
- Endpoint with selected_collections=[] (RAG disabled)
- Endpoint with explicit collections (RAG enabled)
- Verify no fallback to "all collections"
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

# These tests will be skipped if dependencies are not available
pytest.importorskip("app.routers.chat_router")


class TestChatEndpointRAGBehavior:
    """Integration tests for chat endpoint RAG collection selection."""
    
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
            # Mock user exists - must be AsyncMock for await
            mock.find_one = AsyncMock(return_value=MagicMock())
            # Mock tipos_celula exists - must be AsyncMock for await
            mock.find_many = AsyncMock(return_value=[MagicMock()])
            yield mock
    
    @pytest.fixture
    def mock_llm_provider(self):
        """Mock LLM provider factory."""
        with patch('app.services.llm_provider_factory.LLMProviderFactory') as mock:
            provider_instance = MagicMock()
            provider_instance.provider_name = "ollama"
            provider_instance.model_name = "mistral"
            provider_instance.process_chat = AsyncMock(
                return_value={"response": "Test response"}
            )
            mock.get_provider.return_value = provider_instance
            yield mock, provider_instance
    
    def test_endpoint_definition(self):
        """Test that the endpoint is properly defined."""
        from app.routers.chat_router import chat_router
        
        # Check that the endpoint exists
        routes = [route for route in chat_router.routes if hasattr(route, 'path')]
        processar_routes = [r for r in routes if '/processar' in r.path]
        
        assert len(processar_routes) > 0, "Endpoint /processar should exist"
    
    @pytest.mark.asyncio
    async def test_chat_endpoint_with_none_collections(self, mock_user, mock_db, mock_llm_provider):
        """Test that endpoint does not use RAG when selected_collections is None."""
        from app.routers.chat_router import processar_intencao_chat
        from app.models.chat import ProcessChatIntentRequest
        
        mock_factory, mock_provider = mock_llm_provider
        
        # Create request with selected_collections=None (field omitted)
        request = ProcessChatIntentRequest(
            purpose="Test message",
            assignee_id="test-user-id",
            model="mistral",
            classify_intent=False,  # Direct conversation mode
            selected_collections=None
        )
        
        # Call endpoint
        response = await processar_intencao_chat(request, mock_user)
        
        # Verify process_chat was called with use_rag=False
        mock_provider.process_chat.assert_called_once()
        call_kwargs = mock_provider.process_chat.call_args.kwargs
        
        # CRITICAL: use_rag should be False when collections are None
        assert call_kwargs['use_rag'] is False, "RAG should be disabled when collections are None"
        assert call_kwargs['selected_collections'] is None
    
    @pytest.mark.asyncio
    async def test_chat_endpoint_with_empty_collections(self, mock_user, mock_db, mock_llm_provider):
        """Test that endpoint does not use RAG when selected_collections is []."""
        from app.routers.chat_router import processar_intencao_chat
        from app.models.chat import ProcessChatIntentRequest
        
        mock_factory, mock_provider = mock_llm_provider
        
        # Create request with selected_collections=[]
        request = ProcessChatIntentRequest(
            purpose="Test message",
            assignee_id="test-user-id",
            model="mistral",
            classify_intent=False,
            selected_collections=[]
        )
        
        # Call endpoint
        response = await processar_intencao_chat(request, mock_user)
        
        # Verify process_chat was called with use_rag=False
        mock_provider.process_chat.assert_called_once()
        call_kwargs = mock_provider.process_chat.call_args.kwargs
        
        # CRITICAL: use_rag should be False when collections are empty
        assert call_kwargs['use_rag'] is False, "RAG should be disabled when collections are empty"
        assert call_kwargs['selected_collections'] == []
    
    @pytest.mark.asyncio
    async def test_chat_endpoint_with_explicit_collections(self, mock_user, mock_db, mock_llm_provider):
        """Test that endpoint uses RAG when collections are explicitly provided."""
        from app.routers.chat_router import processar_intencao_chat
        from app.models.chat import ProcessChatIntentRequest
        
        mock_factory, mock_provider = mock_llm_provider
        
        # Create request with explicit collections
        request = ProcessChatIntentRequest(
            purpose="Test message",
            assignee_id="test-user-id",
            model="mistral",
            classify_intent=False,
            selected_collections=['scareverse_docs', 'scareverse_code']
        )
        
        # Call endpoint
        response = await processar_intencao_chat(request, mock_user)
        
        # Verify process_chat was called with use_rag=True
        mock_provider.process_chat.assert_called_once()
        call_kwargs = mock_provider.process_chat.call_args.kwargs
        
        # CRITICAL: use_rag should be True when collections are provided
        assert call_kwargs['use_rag'] is True, "RAG should be enabled with explicit collections"
        assert call_kwargs['selected_collections'] == ['scareverse_docs', 'scareverse_code']
    
    @pytest.mark.asyncio
    async def test_chat_endpoint_response_format(self, mock_user, mock_db, mock_llm_provider):
        """Test that endpoint returns correct response format."""
        from app.routers.chat_router import processar_intencao_chat
        from app.models.chat import ProcessChatIntentRequest
        
        mock_factory, mock_provider = mock_llm_provider
        
        request = ProcessChatIntentRequest(
            purpose="Test message",
            assignee_id="test-user-id",
            model="mistral",
            classify_intent=False,
            selected_collections=[]
        )
        
        response = await processar_intencao_chat(request, mock_user)
        
        assert response.response == "Test response"
        assert response.cell is None  # No cell creation in direct conversation mode


class TestChatRequestModel:
    """Tests for ProcessChatIntentRequest model validation."""
    
    def test_request_model_default_collections(self):
        """Test that selected_collections defaults to empty list."""
        from app.models.chat import ProcessChatIntentRequest
        
        request = ProcessChatIntentRequest(
            purpose="Test",
            assignee_id="test-id"
        )
        
        # Default should be empty list (RAG disabled)
        assert request.selected_collections == []
        assert isinstance(request.selected_collections, list)
    
    def test_request_model_explicit_none_collections(self):
        """Test that selected_collections can be explicitly set to None."""
        from app.models.chat import ProcessChatIntentRequest
        
        request = ProcessChatIntentRequest(
            purpose="Test",
            assignee_id="test-id",
            selected_collections=None
        )
        
        # Should accept None
        assert request.selected_collections is None
    
    def test_request_model_explicit_collections(self):
        """Test that selected_collections accepts list of strings."""
        from app.models.chat import ProcessChatIntentRequest
        
        collections = ['scareverse_docs', 'scareverse_code']
        request = ProcessChatIntentRequest(
            purpose="Test",
            assignee_id="test-id",
            selected_collections=collections
        )
        
        assert request.selected_collections == collections


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
