"""
Conversational Memory Module (Consolidated)

This module provides LangChain-based conversation memory management:

**ConversationMemoryManager** (Primary, Recommended):
- Automatic summarization using ConversationSummaryBufferMemory
- Session-based memory with SessionMemoryStore
- Defaults to Ollama/Mistral for cost-efficient local summarization
- Configurable LLM injection for flexibility

**Chat History Utilities**: See chat_utils.py for stateless utility functions
(token counting, summarization triggers, prompt building) used by the orchestrator.

The LLM used for summarization can be configured (e.g., local Ollama/Mistral
models to reduce costs, or OpenAI models for cloud-based summarization).

Technical naming: All functions and variables in English.
"""

import logging
from typing import List, Dict, Any, Optional

from langchain_classic.memory import ConversationSummaryBufferMemory
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.language_models.chat_models import BaseChatModel

from ..config import OPENAI_API_KEY, OPENAI_DEFAULT_MODEL, OLLAMA_BASE_URL, OLLAMA_MODEL

# Re-export chat history utilities from chat_utils for backward compatibility
from .chat_utils import (
    count_tokens,
    update_history,
    should_summarize,
    build_summarization_prompt,
    reset_after_summarization,
    initialize_chat_history_state,
    format_context_for_prompt,
    ChatHistoryState,
    DEFAULT_SUMMARY_THRESHOLD_TURNS,
    DEFAULT_SUMMARY_THRESHOLD_TOKENS,
    DEFAULT_MAX_RECENT_HISTORY_TURNS,
    DEFAULT_TOKEN_MODEL,
)

logger = logging.getLogger(__name__)

# Default memory configuration
DEFAULT_MAX_TOKEN_LIMIT = 2000  # Maximum tokens to keep in buffer
DEFAULT_MODEL = "mistral"  # Default model for summarization (Ollama/Mistral for cost efficiency)


class ConversationMemoryManager:
    """
    Manages conversation memory with summarization.

    Uses ConversationSummaryBufferMemory to:
    - Keep recent messages in full
    - Summarize older messages to save tokens
    - Maintain conversation context efficiently
    """

    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        max_token_limit: int = DEFAULT_MAX_TOKEN_LIMIT,
        model_name: Optional[str] = None,
        memory_key: str = "history",
    ):
        """
        Initialize conversation memory manager.

        Args:
            llm: Language model instance to use for summarization (ChatOllama, ChatOpenAI, etc.).
                 If None, creates a default ChatOllama instance with model_name.
            max_token_limit: Maximum tokens to keep in buffer before summarizing
            model_name: Model name to use if llm is not provided (default: 'mistral' for Ollama).
                       Ignored if llm parameter is provided.
            memory_key: Key to use for memory in conversation

        Note:
            Prefers local LLM (Ollama/Mistral) for cost efficiency. Pass a configured
            LLM instance for full control over the model used for summarization.
        """
        # Use provided LLM or create default Ollama instance
        if llm is not None:
            self.llm = llm
            logger.info("Using provided LLM: %s", type(llm).__name__)
        else:
            # Default to local Ollama/Mistral for cost efficiency
            effective_model = model_name or DEFAULT_MODEL
            logger.info("Creating default ChatOllama with model: %s", effective_model)
            self.llm = ChatOllama(
                model=effective_model,
                base_url=OLLAMA_BASE_URL,
                temperature=0.0,  # Deterministic summarization
            )

        # Initialize memory
        self.memory = ConversationSummaryBufferMemory(
            llm=self.llm,
            max_token_limit=max_token_limit,
            memory_key=memory_key,
            return_messages=True,
        )

        logger.info(
            f"Initialized ConversationMemoryManager with " f"max_token_limit={max_token_limit}"
        )

    def add_user_message(self, message: str) -> None:
        """
        Add a user message to memory.

        Args:
            message: User's message
        """
        self.memory.chat_memory.add_user_message(message)
        logger.debug("Added user message to memory: %s...", message[:50])

    def add_ai_message(self, message: str) -> None:
        """
        Add an AI response to memory.

        Args:
            message: AI's response
        """
        self.memory.chat_memory.add_ai_message(message)
        logger.debug("Added AI message to memory: %s...", message[:50])

    def add_exchange(self, user_message: str, ai_response: str) -> None:
        """
        Add a complete user-AI exchange to memory.

        Args:
            user_message: User's message
            ai_response: AI's response
        """
        self.add_user_message(user_message)
        self.add_ai_message(ai_response)

    def get_history(self) -> List[Any]:
        """
        Get conversation history.

        Returns:
            List of messages (may include summarized content)
        """
        return self.memory.load_memory_variables({}).get("history", [])

    def get_history_as_dicts(self) -> List[Dict[str, str]]:
        """
        Get conversation history as list of dicts.

        Returns:
            List of dicts with 'role' and 'content' keys

        Example:
            >>> manager.get_history_as_dicts()
            [
                {'role': 'user', 'content': 'Hello'},
                {'role': 'assistant', 'content': 'Hi there!'},
                ...
            ]
        """
        history = self.get_history()
        result = []

        for msg in history:
            if isinstance(msg, HumanMessage):
                result.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                result.append({"role": "assistant", "content": msg.content})
            else:
                # Handle other message types
                result.append({"role": "system", "content": str(msg.content)})

        return result

    def clear_history(self) -> None:
        """Clear all conversation history."""
        self.memory.clear()
        logger.info("Cleared conversation history")

    def get_summary(self) -> Optional[str]:
        """
        Get the current summary of conversation (if any).

        Returns:
            Summary string or None if no summary exists
        """
        if hasattr(self.memory, "moving_summary_buffer"):
            return self.memory.moving_summary_buffer
        return None

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """
        Save conversation context from inputs and outputs.

        Args:
            inputs: Dict with input/question
            outputs: Dict with output/response
        """
        self.memory.save_context(inputs, outputs)


class SessionMemoryStore:
    """
    Store for managing multiple conversation sessions.

    Each session (user/conversation) has its own memory manager.
    """

    def __init__(self):
        """Initialize session memory store."""
        self._sessions: Dict[str, ConversationMemoryManager] = {}
        logger.info("Initialized SessionMemoryStore")

    def get_or_create_session(
        self,
        session_id: str,
        llm: Optional[BaseChatModel] = None,
        max_token_limit: int = DEFAULT_MAX_TOKEN_LIMIT,
        model_name: Optional[str] = None,
    ) -> ConversationMemoryManager:
        """
        Get existing session memory or create new one.

        Args:
            session_id: Unique session identifier
            llm: Optional LLM instance for summarization (ChatOllama, ChatOpenAI, etc.)
            max_token_limit: Max tokens for memory buffer
            model_name: Model name if llm not provided (default: 'mistral')

        Returns:
            ConversationMemoryManager for the session
        """
        if session_id not in self._sessions:
            logger.info("Creating new memory session: %s", session_id)
            self._sessions[session_id] = ConversationMemoryManager(
                llm=llm, max_token_limit=max_token_limit, model_name=model_name
            )

        return self._sessions[session_id]

    def get_session(self, session_id: str) -> Optional[ConversationMemoryManager]:
        """
        Get existing session memory.

        Args:
            session_id: Session identifier

        Returns:
            ConversationMemoryManager or None if session doesn't exist
        """
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and its memory.

        Args:
            session_id: Session identifier

        Returns:
            True if session was deleted, False if it didn't exist
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("Deleted memory session: %s", session_id)
            return True
        return False

    def clear_all_sessions(self) -> None:
        """Clear all sessions."""
        self._sessions.clear()
        logger.info("Cleared all memory sessions")

    def get_active_session_count(self) -> int:
        """
        Get count of active sessions.

        Returns:
            Number of active sessions
        """
        return len(self._sessions)


# Global session store instance
_session_store: Optional[SessionMemoryStore] = None


def get_session_store() -> SessionMemoryStore:
    """
    Get or create the global session memory store.

    Returns:
        SessionMemoryStore instance
    """
    global _session_store
    if _session_store is None:
        _session_store = SessionMemoryStore()
    return _session_store


def get_session_memory(
    session_id: str,
    llm: Optional[BaseChatModel] = None,
    max_token_limit: int = DEFAULT_MAX_TOKEN_LIMIT,
    model_name: Optional[str] = None,
) -> ConversationMemoryManager:
    """
    Convenience function to get session memory.

    Args:
        session_id: Session identifier
        llm: Optional LLM instance for summarization
        max_token_limit: Max tokens for memory buffer
        model_name: Model name if llm not provided (default: 'mistral' for Ollama)

    Returns:
        ConversationMemoryManager for the session

    Example:
        >>> # Using default local Ollama/Mistral
        >>> memory = get_session_memory("user_123")
        >>> memory.add_exchange("Hello", "Hi there!")
        >>>
        >>> # Using custom LLM
        >>> from langchain_community.chat_models import ChatOllama
        >>> custom_llm = ChatOllama(model="mistral", base_url="http://localhost:11434")
        >>> memory = get_session_memory("user_456", llm=custom_llm)
    """
    store = get_session_store()
    return store.get_or_create_session(session_id, llm, max_token_limit, model_name)
