"""
LLM Provider Interface - Abstract Base Class for all LLM providers.

This module defines the unified interface that all LLM providers must implement,
enabling polymorphic dispatch and eliminating conditional logic in the router.

Key Features:
- Abstract `process_chat` method for unified chat processing
- Provider identification via properties
- Support for attached_content_metadata handling
- Integration with centralized prompt_builder
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    """
    Abstract Base Class for all LLM providers.

    All concrete LLM provider implementations must inherit from this class
    and implement all abstract methods. This ensures a consistent interface
    across different LLM services (Ollama, Gemini, OpenAI, etc.).

    The provider handles:
    - Chat processing with conversation history
    - RAG context integration
    - Attached content metadata processing (specific to each provider)
    - System instructions

    Example:
        >>> class MyProvider(BaseLLMProvider):
        ...     @property
        ...     def provider_name(self) -> str:
        ...         return "my_provider"
        ...
        ...     @property
        ...     def model_name(self) -> str:
        ...         return "my_model_v1"
        ...
        ...     async def process_chat(self, user_message, conversation_history, **kwargs):
        ...         # Implementation here
        ...         return {"response": "Hello"}
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Return the name of the provider.

        Returns:
            Provider identifier (e.g., "ollama", "gemini", "openai")

        Example:
            >>> provider = OllamaProvider()
            >>> assert provider.provider_name == "ollama"
        """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """
        Return the name/ID of the model being used.

        Returns:
            Model identifier (e.g., "mistral", "gemini-2.5-flash", "gpt-4")

        Example:
            >>> provider = OpenAIProvider(model_id="gpt-4")
            >>> assert provider.model_name == "gpt-4"
        """

    @abstractmethod
    async def process_chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        rag_context: Optional[str] = None,
        attached_content_metadata: Optional[List[Dict[str, Any]]] = None,
        system_instructions: Optional[str] = None,
        use_rag: bool = True,
        selected_collections: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Process a chat message and return a response.

        This is the main interface method that all providers must implement.
        Each provider is responsible for:
        1. Parsing attached_content_metadata specific to its format
        2. Building prompts using the centralized prompt_builder
        3. Calling the provider's API
        4. Returning a standardized response

        Args:
            user_message: Current user message/intent
            conversation_history: Previous conversation turns
                                Format: [{'role': 'user'/'assistant', 'content': str}]
            rag_context: Pre-retrieved RAG context (optional, if not provided and
                        use_rag=True, provider should retrieve it)
            attached_content_metadata: List of metadata about attached content
                                      Format varies by provider:
                                      - Ollama: {"type": "segmented_content",
                                                "content": ["segment1", "segment2"]}
                                      - OpenAI/Gemini: {"type": "file_id",
                                                       "id": "file_abc123"}
            system_instructions: System-level instructions/prompt (optional)
            use_rag: Whether to use RAG for context retrieval (default: True)
            selected_collections: Optional list of RAG collections to search
                                (e.g., ['scareverse_docs', 'scareverse_code'])
            **kwargs: Additional provider-specific parameters

        Returns:
            Dict containing:
                - response: str - The LLM's response text
                - Additional provider-specific data (e.g., thread_id for OpenAI)

        Raises:
            LLMProviderError: Generic error for provider-related issues
            ConnectionError: If provider service is unavailable
            ValueError: If required parameters are missing or invalid

        Example:
            >>> provider = OllamaProvider()
            >>> result = await provider.process_chat(
            ...     user_message="Explain this code",
            ...     attached_content_metadata=[{
            ...         "type": "segmented_content",
            ...         "content": ["def hello(): print('hi')"]
            ...     }],
            ...     use_rag=True
            ... )
            >>> assert "response" in result
        """

    async def verify_availability(self) -> bool:
        """
        Check if the provider service is available.

        This is an optional method that providers can override to implement
        health checks. Default implementation returns True.

        Returns:
            True if provider is available, False otherwise

        Example:
            >>> provider = OllamaProvider()
            >>> is_available = await provider.verify_availability()
        """
        logger.warning(
            f"{self.provider_name}: verify_availability not implemented, "
            "assuming available"
        )
        return True


class LLMProviderError(Exception):
    """
    Generic exception for LLM provider errors.

    This exception should be raised by providers when encountering errors,
    allowing the router to handle errors uniformly without knowing provider
    implementation details.

    Example:
        >>> raise LLMProviderError("Failed to process chat", provider="ollama")
    """

    def __init__(self, message: str, provider: Optional[str] = None):
        self.provider = provider
        super().__init__(f"[{provider}] {message}" if provider else message)
