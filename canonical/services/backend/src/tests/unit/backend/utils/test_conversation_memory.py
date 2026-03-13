"""
Unit tests for app/utils/conversation_memory.py

Tests ConversationMemoryManager, SessionMemoryStore, and utility functions.
Ensures comprehensive coverage of conversation memory management with
automatic summarization and session handling.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch


# Skip all tests if langchain modules are not available
try:
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    # Create mock classes for type checking
    HumanMessage = AIMessage = SystemMessage = Mock

pytestmark = pytest.mark.skipif(
    not LANGCHAIN_AVAILABLE,
    reason="langchain modules not available"
)


class TestConversationMemoryManager:
    """Test ConversationMemoryManager class."""
    
    @patch('app.utils.conversation_memory.ConversationSummaryBufferMemory')
    @patch('app.utils.conversation_memory.ChatOllama')
    def test_init_with_default_llm(self, mock_ollama, mock_memory):
        """Test initialization with default Ollama LLM."""
        from app.utils.conversation_memory import ConversationMemoryManager
        
        mock_ollama_instance = Mock()
        mock_ollama.return_value = mock_ollama_instance
        
        manager = ConversationMemoryManager()
        
        # Verify ChatOllama was created with correct params
        mock_ollama.assert_called_once_with(
            model="mistral",
            base_url=mock_ollama.call_args[1]['base_url'],
            temperature=0.0
        )
        
        # Verify memory was initialized
        mock_memory.assert_called_once()
        assert mock_memory.call_args[1]['llm'] == mock_ollama_instance
        assert mock_memory.call_args[1]['max_token_limit'] == 2000
        assert mock_memory.call_args[1]['return_messages'] is True
    
    @patch('app.utils.conversation_memory.ConversationSummaryBufferMemory')
    def test_init_with_custom_llm(self, mock_memory):
        """Test initialization with custom LLM instance."""
        from app.utils.conversation_memory import ConversationMemoryManager
        
        custom_llm = Mock()
        manager = ConversationMemoryManager(llm=custom_llm, max_token_limit=5000)
        
        # Verify provided LLM was used
        mock_memory.assert_called_once()
        assert mock_memory.call_args[1]['llm'] == custom_llm
        assert mock_memory.call_args[1]['max_token_limit'] == 5000
    
    @patch('app.utils.conversation_memory.ConversationSummaryBufferMemory')
    @patch('app.utils.conversation_memory.ChatOllama')
    def test_init_with_custom_model_name(self, mock_ollama, mock_memory):
        """Test initialization with custom model name."""
        from app.utils.conversation_memory import ConversationMemoryManager
        
        manager = ConversationMemoryManager(model_name="llama2")
        
        # Verify ChatOllama was created with custom model
        assert mock_ollama.call_args[1]['model'] == "llama2"
    
    @patch('app.utils.conversation_memory.ConversationSummaryBufferMemory')
    @patch('app.utils.conversation_memory.ChatOllama')
    def test_add_user_message(self, mock_ollama, mock_memory):
        """Test adding user message to memory."""
        from app.utils.conversation_memory import ConversationMemoryManager
        
        mock_chat_memory = Mock()
        mock_memory.return_value.chat_memory = mock_chat_memory
        
        manager = ConversationMemoryManager()
        manager.add_user_message("Hello, AI!")
        
        mock_chat_memory.add_user_message.assert_called_once_with("Hello, AI!")
    
    @patch('app.utils.conversation_memory.ConversationSummaryBufferMemory')
    @patch('app.utils.conversation_memory.ChatOllama')
    def test_add_ai_message(self, mock_ollama, mock_memory):
        """Test adding AI message to memory."""
        from app.utils.conversation_memory import ConversationMemoryManager
        
        mock_chat_memory = Mock()
        mock_memory.return_value.chat_memory = mock_chat_memory
        
        manager = ConversationMemoryManager()
        manager.add_ai_message("Hi there!")
        
        mock_chat_memory.add_ai_message.assert_called_once_with("Hi there!")
    
    @patch('app.utils.conversation_memory.ConversationSummaryBufferMemory')
    @patch('app.utils.conversation_memory.ChatOllama')
    def test_add_exchange(self, mock_ollama, mock_memory):
        """Test adding complete user-AI exchange."""
        from app.utils.conversation_memory import ConversationMemoryManager
        
        mock_chat_memory = Mock()
        mock_memory.return_value.chat_memory = mock_chat_memory
        
        manager = ConversationMemoryManager()
        manager.add_exchange("User message", "AI response")
        
        # Verify both messages were added
        assert mock_chat_memory.add_user_message.call_count == 1
        assert mock_chat_memory.add_ai_message.call_count == 1
        mock_chat_memory.add_user_message.assert_called_with("User message")
        mock_chat_memory.add_ai_message.assert_called_with("AI response")
    
    @patch('app.utils.conversation_memory.ConversationSummaryBufferMemory')
    @patch('app.utils.conversation_memory.ChatOllama')
    def test_get_history(self, mock_ollama, mock_memory):
        """Test retrieving conversation history."""
        from app.utils.conversation_memory import ConversationMemoryManager
        
        mock_history = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!")
        ]
        mock_memory.return_value.load_memory_variables.return_value = {
            "history": mock_history
        }
        
        manager = ConversationMemoryManager()
        history = manager.get_history()
        
        assert history == mock_history
        mock_memory.return_value.load_memory_variables.assert_called_once_with({})
    
    @patch('app.utils.conversation_memory.ConversationSummaryBufferMemory')
    @patch('app.utils.conversation_memory.ChatOllama')
    def test_get_history_empty(self, mock_ollama, mock_memory):
        """Test retrieving empty history."""
        from app.utils.conversation_memory import ConversationMemoryManager
        
        mock_memory.return_value.load_memory_variables.return_value = {}
        
        manager = ConversationMemoryManager()
        history = manager.get_history()
        
        assert history == []
    
    @patch('app.utils.conversation_memory.ConversationSummaryBufferMemory')
    @patch('app.utils.conversation_memory.ChatOllama')
    def test_get_history_as_dicts(self, mock_ollama, mock_memory):
        """Test getting history as list of dicts."""
        from app.utils.conversation_memory import ConversationMemoryManager
        
        mock_history = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
            SystemMessage(content="System message")
        ]
        mock_memory.return_value.load_memory_variables.return_value = {
            "history": mock_history
        }
        
        manager = ConversationMemoryManager()
        result = manager.get_history_as_dicts()
        
        assert len(result) == 3
        assert result[0] == {"role": "user", "content": "Hello"}
        assert result[1] == {"role": "assistant", "content": "Hi there!"}
        assert result[2] == {"role": "system", "content": "System message"}
    
    @patch('app.utils.conversation_memory.ConversationSummaryBufferMemory')
    @patch('app.utils.conversation_memory.ChatOllama')
    def test_get_history_as_dicts_empty(self, mock_ollama, mock_memory):
        """Test getting empty history as dicts."""
        from app.utils.conversation_memory import ConversationMemoryManager
        
        mock_memory.return_value.load_memory_variables.return_value = {"history": []}
        
        manager = ConversationMemoryManager()
        result = manager.get_history_as_dicts()
        
        assert result == []
    
    @patch('app.utils.conversation_memory.ConversationSummaryBufferMemory')
    @patch('app.utils.conversation_memory.ChatOllama')
    def test_clear_history(self, mock_ollama, mock_memory):
        """Test clearing conversation history."""
        from app.utils.conversation_memory import ConversationMemoryManager
        
        manager = ConversationMemoryManager()
        manager.clear_history()
        
        mock_memory.return_value.clear.assert_called_once()
    
    @patch('app.utils.conversation_memory.ConversationSummaryBufferMemory')
    @patch('app.utils.conversation_memory.ChatOllama')
    def test_get_summary_with_summary(self, mock_ollama, mock_memory):
        """Test getting summary when summary exists."""
        from app.utils.conversation_memory import ConversationMemoryManager
        
        mock_memory.return_value.moving_summary_buffer = "This is a summary of the conversation."
        
        manager = ConversationMemoryManager()
        summary = manager.get_summary()
        
        assert summary == "This is a summary of the conversation."
    
    @patch('app.utils.conversation_memory.ConversationSummaryBufferMemory')
    @patch('app.utils.conversation_memory.ChatOllama')
    def test_get_summary_no_summary(self, mock_ollama, mock_memory):
        """Test getting summary when no summary exists."""
        from app.utils.conversation_memory import ConversationMemoryManager
        
        # Mock memory without moving_summary_buffer attribute
        delattr(mock_memory.return_value, 'moving_summary_buffer') if hasattr(
            mock_memory.return_value, 'moving_summary_buffer'
        ) else None
        
        manager = ConversationMemoryManager()
        summary = manager.get_summary()
        
        assert summary is None
    
    @patch('app.utils.conversation_memory.ConversationSummaryBufferMemory')
    @patch('app.utils.conversation_memory.ChatOllama')
    def test_save_context(self, mock_ollama, mock_memory):
        """Test saving context from inputs and outputs."""
        from app.utils.conversation_memory import ConversationMemoryManager
        
        manager = ConversationMemoryManager()
        inputs = {"input": "What is AI?"}
        outputs = {"output": "AI stands for Artificial Intelligence."}
        
        manager.save_context(inputs, outputs)
        
        mock_memory.return_value.save_context.assert_called_once_with(inputs, outputs)


class TestSessionMemoryStore:
    """Test SessionMemoryStore class."""
    
    @patch('app.utils.conversation_memory.ConversationMemoryManager')
    def test_init(self, mock_manager):
        """Test SessionMemoryStore initialization."""
        from app.utils.conversation_memory import SessionMemoryStore
        
        store = SessionMemoryStore()
        
        assert hasattr(store, '_sessions')
        assert isinstance(store._sessions, dict)
        assert len(store._sessions) == 0
    
    @patch('app.utils.conversation_memory.ConversationMemoryManager')
    def test_get_or_create_session_new(self, mock_manager):
        """Test creating a new session."""
        from app.utils.conversation_memory import SessionMemoryStore
        
        store = SessionMemoryStore()
        session = store.get_or_create_session("user_123")
        
        mock_manager.assert_called_once()
        assert "user_123" in store._sessions
    
    @patch('app.utils.conversation_memory.ConversationMemoryManager')
    def test_get_or_create_session_existing(self, mock_manager):
        """Test retrieving existing session."""
        from app.utils.conversation_memory import SessionMemoryStore
        
        store = SessionMemoryStore()
        
        # Create first session
        session1 = store.get_or_create_session("user_123")
        
        # Get same session again
        session2 = store.get_or_create_session("user_123")
        
        # Should only create manager once
        assert mock_manager.call_count == 1
        assert session1 == session2
    
    @patch('app.utils.conversation_memory.ConversationMemoryManager')
    def test_get_or_create_session_with_custom_params(self, mock_manager):
        """Test creating session with custom parameters."""
        from app.utils.conversation_memory import SessionMemoryStore
        
        store = SessionMemoryStore()
        custom_llm = Mock()
        
        session = store.get_or_create_session(
            "user_123",
            llm=custom_llm,
            max_token_limit=5000,
            model_name="custom_model"
        )
        
        mock_manager.assert_called_once_with(
            llm=custom_llm,
            max_token_limit=5000,
            model_name="custom_model"
        )
    
    @patch('app.utils.conversation_memory.ConversationMemoryManager')
    def test_get_session_exists(self, mock_manager):
        """Test getting existing session."""
        from app.utils.conversation_memory import SessionMemoryStore
        
        store = SessionMemoryStore()
        created_session = store.get_or_create_session("user_123")
        retrieved_session = store.get_session("user_123")
        
        assert retrieved_session == created_session
    
    @patch('app.utils.conversation_memory.ConversationMemoryManager')
    def test_get_session_not_exists(self, mock_manager):
        """Test getting non-existent session."""
        from app.utils.conversation_memory import SessionMemoryStore
        
        store = SessionMemoryStore()
        session = store.get_session("non_existent")
        
        assert session is None
    
    @patch('app.utils.conversation_memory.ConversationMemoryManager')
    def test_delete_session_exists(self, mock_manager):
        """Test deleting existing session."""
        from app.utils.conversation_memory import SessionMemoryStore
        
        store = SessionMemoryStore()
        store.get_or_create_session("user_123")
        
        result = store.delete_session("user_123")
        
        assert result is True
        assert "user_123" not in store._sessions
    
    @patch('app.utils.conversation_memory.ConversationMemoryManager')
    def test_delete_session_not_exists(self, mock_manager):
        """Test deleting non-existent session."""
        from app.utils.conversation_memory import SessionMemoryStore
        
        store = SessionMemoryStore()
        result = store.delete_session("non_existent")
        
        assert result is False
    
    @patch('app.utils.conversation_memory.ConversationMemoryManager')
    def test_clear_all_sessions(self, mock_manager):
        """Test clearing all sessions."""
        from app.utils.conversation_memory import SessionMemoryStore
        
        store = SessionMemoryStore()
        store.get_or_create_session("user_1")
        store.get_or_create_session("user_2")
        store.get_or_create_session("user_3")
        
        assert len(store._sessions) == 3
        
        store.clear_all_sessions()
        
        assert len(store._sessions) == 0
    
    @patch('app.utils.conversation_memory.ConversationMemoryManager')
    def test_get_active_session_count(self, mock_manager):
        """Test getting active session count."""
        from app.utils.conversation_memory import SessionMemoryStore
        
        store = SessionMemoryStore()
        
        assert store.get_active_session_count() == 0
        
        store.get_or_create_session("user_1")
        assert store.get_active_session_count() == 1
        
        store.get_or_create_session("user_2")
        assert store.get_active_session_count() == 2
        
        store.delete_session("user_1")
        assert store.get_active_session_count() == 1


class TestUtilityFunctions:
    """Test module-level utility functions."""
    
    @patch('app.utils.conversation_memory.SessionMemoryStore')
    def test_get_session_store_creates_global(self, mock_store_class):
        """Test get_session_store creates global instance."""
        from app.utils.conversation_memory import get_session_store
        
        # Reset global variable
        import app.utils.conversation_memory as cm
        cm._session_store = None
        
        store = get_session_store()
        
        mock_store_class.assert_called_once()
    
    @patch('app.utils.conversation_memory.SessionMemoryStore')
    def test_get_session_store_reuses_global(self, mock_store_class):
        """Test get_session_store reuses global instance."""
        from app.utils.conversation_memory import get_session_store
        
        # Reset and create first instance
        import app.utils.conversation_memory as cm
        cm._session_store = None
        
        store1 = get_session_store()
        store2 = get_session_store()
        
        # Should only create once
        assert mock_store_class.call_count == 1
    
    @patch('app.utils.conversation_memory.get_session_store')
    def test_get_session_memory(self, mock_get_store):
        """Test get_session_memory convenience function."""
        from app.utils.conversation_memory import get_session_memory
        
        mock_store = Mock()
        mock_memory = Mock()
        mock_store.get_or_create_session.return_value = mock_memory
        mock_get_store.return_value = mock_store
        
        custom_llm = Mock()
        memory = get_session_memory(
            "user_123",
            llm=custom_llm,
            max_token_limit=5000,
            model_name="custom_model"
        )
        
        mock_store.get_or_create_session.assert_called_once_with(
            "user_123",
            custom_llm,
            5000,
            "custom_model"
        )
        assert memory == mock_memory
    
    @patch('app.utils.conversation_memory.get_session_store')
    def test_get_session_memory_default_params(self, mock_get_store):
        """Test get_session_memory with default parameters."""
        from app.utils.conversation_memory import get_session_memory, DEFAULT_MAX_TOKEN_LIMIT
        
        mock_store = Mock()
        mock_get_store.return_value = mock_store
        
        memory = get_session_memory("user_456")
        
        mock_store.get_or_create_session.assert_called_once_with(
            "user_456",
            None,
            DEFAULT_MAX_TOKEN_LIMIT,
            None
        )
