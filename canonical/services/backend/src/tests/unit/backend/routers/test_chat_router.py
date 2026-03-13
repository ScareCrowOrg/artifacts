"""
Unit tests for chat_router.py

Tests cover:
- POST /chat/processar - Process chat intent with LangChain/LangGraph orchestration

Test scenarios:
- Direct conversation mode (no classification)
- Orchestrator mode (with classification)
- Different LLM providers (ollama, gemini, openai)
- RAG enabled/disabled scenarios
- With/without attachments
- With/without conversation history
- Tracing enabled/disabled
- Error handling and validation

Technical naming: All functions and variables in English.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime

from app.main import app
from app.models import User, AIModel, NotebookItemType
from app.auth import get_current_user_required


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    user = Mock(spec=User)
    user.id = "test-user-123"
    user.name = "Test User"
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_ai_model():
    """Mock AI model."""
    model = Mock(spec=AIModel)
    model.id = "model-123"
    model.modelId = "mistral"
    model.name = "Mistral"
    model.provider = "ollama"
    model.active = True
    model.apiKey = None
    model.configuration = {}
    return model


@pytest.fixture
def mock_notebook_item_type():
    """Mock notebook item type."""
    item_type = Mock(spec=NotebookItemType)
    item_type.id = "type-123"
    item_type.name = "markdown"
    return item_type


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up dependency overrides."""
    yield
    app.dependency_overrides.clear()


class TestChatProcessarDirectMode:
    """Tests for POST /chat/processar in direct conversation mode (no classification)."""
    
    @patch('app.routers.chat_router.db')
    @patch('app.services.llm_provider_factory.LLMProviderFactory')
    def test_processar_direct_mode_success(self, mock_factory, mock_db, client, mock_user,
                                          mock_ai_model, mock_notebook_item_type):
        """Test successful direct conversation processing."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Setup mocks
        mock_db.find_one = AsyncMock(return_value=mock_user)
        async def async_find_many(*args, **kwargs):
            if args[0] == "notebook_item_types":
                return [mock_notebook_item_type]
            elif args[0] == "ai_models":
                return [mock_ai_model]
            return []
        mock_db.find_many = async_find_many
        
        # Mock LLM provider
        mock_provider = Mock()
        mock_provider.provider_name = "ollama"
        mock_provider.model_name = "mistral"
        mock_provider.process_chat = AsyncMock(return_value={
            "response": "Test response from LLM"
        })
        mock_factory.get_provider.return_value = mock_provider
        
        response = client.post("/api/chat/processar", json={
            "purpose": "Hello, how are you?",
            "model": "mistral",
            "classify_intent": False,  # Direct mode
            "history": [],
            "attachments": []
        })
        
        # Debug output
        if response.status_code != 200:
            print(f"Error response: {response.status_code}")
            print(f"Error detail: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert data["response"] == "Test response from LLM"
        assert data["cell"] is None  # No cell created in direct mode
        mock_provider.process_chat.assert_called_once()
    
    @patch('app.routers.chat_router.db')
    @patch('app.services.llm_provider_factory.LLMProviderFactory')
    def test_processar_direct_mode_with_rag(self, mock_factory, mock_db, client, mock_user,
                                           mock_ai_model, mock_notebook_item_type):
        """Test direct mode with RAG enabled."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(return_value=mock_user)
        async def async_find_many(*args, **kwargs):
            if args[0] == "notebook_item_types":
                return [mock_notebook_item_type]
            elif args[0] == "ai_models":
                return [mock_ai_model]
            return []
        mock_db.find_many = async_find_many
        
        mock_provider = Mock()
        mock_provider.provider_name = "ollama"
        mock_provider.model_name = "mistral"
        mock_provider.process_chat = AsyncMock(return_value={
            "response": "RAG-enhanced response"
        })
        mock_factory.get_provider.return_value = mock_provider
        
        response = client.post("/api/chat/processar", json={
            "purpose": "What is the project architecture?",
            "model": "mistral",
            "classify_intent": False,
            "selected_collections": ["scareverse_docs"],  # RAG enabled
            "history": []
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        # Verify RAG was used
        call_kwargs = mock_provider.process_chat.call_args[1]
        assert call_kwargs["use_rag"] is True
        assert call_kwargs["selected_collections"] == ["scareverse_docs"]
    
    @patch('app.routers.chat_router.db')
    @patch('app.services.llm_provider_factory.LLMProviderFactory')
    def test_processar_direct_mode_with_attachments_ollama(self, mock_factory, mock_db, client,
                                                           mock_user, mock_ai_model, mock_notebook_item_type):
        """Test direct mode with attachments for Ollama provider."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(return_value=mock_user)
        async def async_find_many(*args, **kwargs):
            if args[0] == "notebook_item_types":
                return [mock_notebook_item_type]
            elif args[0] == "ai_models":
                return [mock_ai_model]
            return []
        mock_db.find_many = async_find_many
        
        mock_provider = Mock()
        mock_provider.provider_name = "ollama"
        mock_provider.model_name = "mistral"
        mock_provider.process_chat = AsyncMock(return_value={
            "response": "Response with attachment context"
        })
        mock_factory.get_provider.return_value = mock_provider
        
        response = client.post("/api/chat/processar", json={
            "purpose": "Analyze this code",
            "model": "mistral",
            "classify_intent": False,
            "attachments": [
                {
                    "name": "test.py",
                    "content": "def hello():\n    print('Hello')",
                    "type": "text/plain"
                }
            ]
        })
        
        assert response.status_code == 200
        # Verify attachments were passed
        call_kwargs = mock_provider.process_chat.call_args[1]
        assert "attached_content_metadata" in call_kwargs
        assert call_kwargs["attached_content_metadata"] is not None


class TestChatProcessarOrchestratorMode:
    """Tests for POST /chat/processar with orchestrator (classification enabled)."""
    
    @patch('app.routers.chat_router.db')
    @patch('app.orchestrator.langgraph.langgraph_chat_flow.get_orchestrator')
    def test_processar_orchestrator_mode_success(self, mock_get_orch, mock_db, client,
                                                 mock_user, mock_ai_model, mock_notebook_item_type):
        """Test successful processing with orchestrator."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(return_value=mock_user)
        async def async_find_many(*args, **kwargs):
            if args[0] == "notebook_item_types":
                return [mock_notebook_item_type]
            elif args[0] == "ai_models":
                return [mock_ai_model]
            return []
        mock_db.find_many = async_find_many
        
        # Mock orchestrator
        mock_orchestrator = Mock()
        mock_orchestrator.process = AsyncMock(return_value={
            "resposta": "Orchestrator response",  # orchestrator uses 'resposta' internally
            "intencao": "conversar",
            "celula": None,  # orchestrator uses 'celula' not 'cell'
            "conversation_id": "conv-123"
        })
        mock_get_orch.return_value = mock_orchestrator
        
        response = client.post("/api/chat/processar", json={
            "purpose": "Create a cell for user login system",
            "model": "mistral",
            "classify_intent": True,  # Orchestrator mode
            "history": []
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "conversation_id" in data
        mock_orchestrator.process.assert_called_once()
    
    @patch('app.routers.chat_router.db')
    @patch('app.orchestrator.langgraph.langgraph_chat_flow.get_orchestrator')
    def test_processar_orchestrator_with_tracing(self, mock_get_orch, mock_db, client,
                                                 mock_user, mock_ai_model, mock_notebook_item_type):
        """Test orchestrator mode with tracing enabled."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(return_value=mock_user)
        async def async_find_many(*args, **kwargs):
            if args[0] == "notebook_item_types":
                return [mock_notebook_item_type]
            elif args[0] == "ai_models":
                return [mock_ai_model]
            return []
        mock_db.find_many = async_find_many
        
        mock_orchestrator = Mock()
        mock_orchestrator.process = AsyncMock(return_value={
            "resposta": "Response with tracing",  # orchestrator uses 'resposta' internally
            "intencao": "conversar",
            "celula": None,  # orchestrator uses 'celula' not 'cell'
            "conversation_id": "conv-traced-123"
        })
        mock_get_orch.return_value = mock_orchestrator
        
        response = client.post("/api/chat/processar", json={
            "purpose": "Debug this RAG query",
            "model": "mistral",
            "classify_intent": True,
            "enable_tracing": True,  # Tracing enabled
            "history": []
        })
        
        assert response.status_code == 200
        # Verify tracing was enabled
        call_kwargs = mock_orchestrator.process.call_args[1]
        assert call_kwargs["enable_tracing"] is True


class TestChatProcessarProviders:
    """Tests for different LLM providers."""
    
    @patch('app.routers.chat_router.db')
    @patch('app.services.llm_provider_factory.LLMProviderFactory')
    def test_processar_gemini_provider(self, mock_factory, mock_db, client, mock_user,
                                       mock_notebook_item_type):
        """Test processing with Gemini provider."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Mock Gemini model
        mock_gemini_model = Mock(spec=AIModel)
        mock_gemini_model.modelId = "gemini-1.5-pro"
        mock_gemini_model.provider = "gemini"
        mock_gemini_model.active = True
        mock_gemini_model.apiKey = "test-key"
        mock_gemini_model.configuration = {}
        
        mock_db.find_one = AsyncMock(return_value=mock_user)
        async def async_find_many(*args, **kwargs):
            if args[0] == "notebook_item_types":
                return [mock_notebook_item_type]
            elif args[0] == "ai_models":
                return [mock_gemini_model]
            return []
        mock_db.find_many = async_find_many
        
        mock_provider = Mock()
        mock_provider.provider_name = "gemini"
        mock_provider.model_name = "gemini-1.5-pro"
        mock_provider.process_chat = AsyncMock(return_value={
            "response": "Gemini response"
        })
        mock_factory.get_provider.return_value = mock_provider
        
        response = client.post("/api/chat/processar", json={
            "purpose": "Test Gemini",
            "model": "gemini-1.5-pro",
            "classify_intent": False,
            "history": []
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
    
    @patch('app.routers.chat_router.db')
    @patch('app.services.llm_provider_factory.LLMProviderFactory')
    def test_processar_openai_provider(self, mock_factory, mock_db, client, mock_user,
                                       mock_notebook_item_type):
        """Test processing with OpenAI provider."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Mock OpenAI model
        mock_openai_model = Mock(spec=AIModel)
        mock_openai_model.modelId = "gpt-4"
        mock_openai_model.provider = "openai"
        mock_openai_model.active = True
        mock_openai_model.apiKey = "test-key"
        mock_openai_model.configuration = {}
        
        mock_db.find_one = AsyncMock(return_value=mock_user)
        async def async_find_many(*args, **kwargs):
            if args[0] == "notebook_item_types":
                return [mock_notebook_item_type]
            elif args[0] == "ai_models":
                return [mock_openai_model]
            return []
        mock_db.find_many = async_find_many
        
        mock_provider = Mock()
        mock_provider.provider_name = "openai"
        mock_provider.model_name = "gpt-4"
        mock_provider.process_chat = AsyncMock(return_value={
            "response": "OpenAI response",
            "thread_id": "thread-123",
            "assistant_id": "asst-123"
        })
        mock_factory.get_provider.return_value = mock_provider
        
        response = client.post("/api/chat/processar", json={
            "purpose": "Test OpenAI",
            "model": "gpt-4",
            "classify_intent": False,
            "thread_id": "thread-123",
            "assistant_id": "asst-123",
            "history": []
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "thread_id" in data
        assert "assistant_id" in data


class TestChatProcessarErrorHandling:
    """Tests for error handling in chat processing."""
    
    @patch('app.routers.chat_router.db')
    def test_processar_user_not_found(self, mock_db, client, mock_user, mock_notebook_item_type):
        """Test processing when user not found in database."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # User exists in auth but not in DB
        mock_db.find_one = AsyncMock(return_value=None)
        mock_db.find_many = AsyncMock(return_value=[mock_notebook_item_type])
        
        response = client.post("/api/chat/processar", json={
            "purpose": "Test",
            "model": "mistral",
            "classify_intent": False
        })
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower() or "not found" in data["detail"].lower()
    
    @patch('app.routers.chat_router.db')
    def test_processar_no_cell_types(self, mock_db, client, mock_user):
        """Test processing when no cell types available."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(return_value=mock_user)
        async def async_find_many(*args, **kwargs):
            return []  # No types or models
        mock_db.find_many = async_find_many
        
        response = client.post("/api/chat/processar", json={
            "purpose": "Test",
            "model": "mistral",
            "classify_intent": False
        })
        
        assert response.status_code == 500
        data = response.json()
        assert "tipo de célula" in data["detail"].lower() or "cell type" in data["detail"].lower() or "notebook item" in data["detail"].lower()
    
    @patch('app.routers.chat_router.db')
    def test_processar_invalid_model(self, mock_db, client, mock_user, mock_notebook_item_type):
        """Test processing with invalid model ID."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(return_value=mock_user)
        async def async_find_many(*args, **kwargs):
            if args[0] == "notebook_item_types":
                return [mock_notebook_item_type]
            elif args[0] == "ai_models":
                return []  # No models available
            return []
        mock_db.find_many = async_find_many
        
        response = client.post("/api/chat/processar", json={
            "purpose": "Test",
            "model": "nonexistent-model",
            "classify_intent": False
        })
        
        assert response.status_code == 400
        data = response.json()
        assert "model" in data["detail"].lower() or "model" in data["detail"].lower()
    
    @patch('app.routers.chat_router.db')
    def test_processar_gpt4_model_not_in_openai_models(self, mock_db, client, mock_user, mock_notebook_item_type):
        """Test processing with 'gpt-4' model which is not in OPENAI_MODELS list.
        
        This regression test ensures that using an invalid OpenAI model name
        (like 'gpt-4' which is not in the default OPENAI_MODELS list) properly
        returns a 400 error instead of silently failing.
        
        Related to: SVG generator cell 400 Bad Request fix.
        """
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Setup mocks - user exists, has cell types, but no models in DB
        async def mock_find_one(*args, **kwargs):
            return mock_user
        
        async def mock_find_many(*args, **kwargs):
            if args[0] == "notebook_item_types":
                return [mock_notebook_item_type]
            elif args[0] == "ai_models":
                return []  # No models in database, will fall back to .env config
            return []
        
        mock_db.find_one = mock_find_one
        mock_db.find_many = mock_find_many
        
        response = client.post("/api/chat/processar", json={
            "purpose": "Generate SVG visualization",
            "model": "gpt-4",  # This model is NOT in OPENAI_MODELS (only gpt-3.5-turbo, gpt-4o, gpt-4o-mini)
            "classify_intent": False
        })
        
        assert response.status_code == 400
        data = response.json()
        assert "model" in data["detail"].lower()
        assert "gpt-4" in data["detail"].lower()
        # Verify the error message lists available models
        assert "available" in data["detail"].lower() or "gpt-4o" in data["detail"].lower()


class TestChatProcessarWithHistory:
    """Tests for chat processing with conversation history."""
    
    @patch('app.routers.chat_router.db')
    @patch('app.services.llm_provider_factory.LLMProviderFactory')
    def test_processar_with_history(self, mock_factory, mock_db, client, mock_user,
                                    mock_ai_model, mock_notebook_item_type):
        """Test processing with conversation history."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(return_value=mock_user)
        async def async_find_many(*args, **kwargs):
            if args[0] == "notebook_item_types":
                return [mock_notebook_item_type]
            elif args[0] == "ai_models":
                return [mock_ai_model]
            return []
        mock_db.find_many = async_find_many
        
        mock_provider = Mock()
        mock_provider.provider_name = "ollama"
        mock_provider.model_name = "mistral"
        mock_provider.process_chat = AsyncMock(return_value={
            "response": "Context-aware response"
        })
        mock_factory.get_provider.return_value = mock_provider
        
        response = client.post("/api/chat/processar", json={
            "purpose": "What was my previous question?",
            "model": "mistral",
            "classify_intent": False,
            "history": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
                {"role": "user", "content": "What is 2+2?"},
                {"role": "assistant", "content": "The answer is 4."}
            ]
        })
        
        assert response.status_code == 200
        # Verify history was passed
        call_kwargs = mock_provider.process_chat.call_args[1]
        assert "conversation_history" in call_kwargs
        assert len(call_kwargs["conversation_history"]) == 4
