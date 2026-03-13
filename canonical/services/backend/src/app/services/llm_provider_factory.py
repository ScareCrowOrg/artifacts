"""
LLM Provider Factory

Factory pattern for creating and managing LLM provider instances.
Implements singleton pattern for resource optimization.
"""

import logging
from typing import Dict, Optional

from .llm_provider_interface import BaseLLMProvider
from .providers import (
    AiderProvider,
    GeminiProvider,
    InterpreterProvider,
    OllamaProvider,
    OpenAIProvider,
)

logger = logging.getLogger(__name__)


class LLMProviderFactory:
    """
    Factory for creating and managing LLM provider instances.

    This factory implements the singleton pattern to ensure that provider
    instances are reused across requests, optimizing resource usage since
    providers have no per-request mutable state.

    Usage:
        >>> # Get a provider instance
        >>> provider = LLMProviderFactory.get_provider("ollama")
        >>> result = await provider.process_chat("Hello")
        >>>
        >>> # Get provider with custom config
        >>> provider = LLMProviderFactory.get_provider(
        ...     "openai",
        ...     model_id="gpt-4",
        ...     api_key="sk-..."
        ... )
    """

    # Singleton instances cache
    _instances: Dict[str, BaseLLMProvider] = {}

    # Mapping of provider names to their classes
    _provider_classes = {
        "ollama": OllamaProvider,
        "gemini": GeminiProvider,
        "openai": OpenAIProvider,
        "interpreter": InterpreterProvider,
        "aider": AiderProvider,
    }

    @classmethod
    def get_provider(
        cls,
        provider_name: str,
        model_id: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs,
    ) -> BaseLLMProvider:
        """
        Get or create a provider instance.

        Returns a singleton instance for the given provider configuration.
        If custom configuration (model_id, api_key) is provided, creates
        a new instance instead of using the cached singleton.

        Args:
            provider_name: Provider identifier ("ollama", "gemini", "openai")
            model_id: Optional model identifier (creates new instance)
            api_key: Optional API key (creates new instance)
            **kwargs: Additional provider-specific parameters

        Returns:
            BaseLLMProvider instance

        Raises:
            ValueError: If provider_name is not recognized

        Example:
            >>> # Get default Ollama provider (singleton)
            >>> provider = LLMProviderFactory.get_provider("ollama")
            >>>
            >>> # Get custom OpenAI provider (new instance)
            >>> provider = LLMProviderFactory.get_provider(
            ...     "openai",
            ...     model_id="gpt-4",
            ...     api_key="sk-custom"
            ... )
        """
        provider_name_lower = provider_name.lower()

        # Validate provider name
        if provider_name_lower not in cls._provider_classes:
            available = ", ".join(cls._provider_classes.keys())
            raise ValueError(
                f"Unknown provider: {provider_name}. Available providers: {available}"
            )

        # If custom config provided, create new instance (don't cache)
        if model_id or api_key or kwargs:
            logger.debug("Creating new %s provider instance with custom config", provider_name_lower)
            provider_class = cls._provider_classes[provider_name_lower]

            # Build init kwargs based on provider's __init__ signature
            init_kwargs = {}
            if model_id is not None:
                init_kwargs["model_id"] = model_id
            if api_key is not None:
                init_kwargs["api_key"] = api_key
            init_kwargs.update(kwargs)

            # Filter out None values and params not accepted by provider
            import inspect

            sig = inspect.signature(provider_class.__init__)
            valid_params = set(sig.parameters.keys()) - {"self"}
            filtered_kwargs = {
                k: v for k, v in init_kwargs.items() if k in valid_params
            }

            return provider_class(**filtered_kwargs)

        # Otherwise, return cached singleton instance
        if provider_name_lower not in cls._instances:
            logger.info("Creating singleton instance for %s", provider_name_lower)
            provider_class = cls._provider_classes[provider_name_lower]
            cls._instances[provider_name_lower] = provider_class()
        else:
            logger.debug("Returning cached instance for %s", provider_name_lower)

        return cls._instances[provider_name_lower]

    @classmethod
    def register_provider(cls, provider_name: str, provider_class: type) -> None:
        """
        Register a new provider class.

        This allows for dynamic registration of new provider implementations
        without modifying the factory code.

        Args:
            provider_name: Identifier for the provider
            provider_class: Class implementing BaseLLMProvider

        Raises:
            TypeError: If provider_class doesn't inherit from BaseLLMProvider

        Example:
            >>> class ClaudeProvider(BaseLLMProvider):
            ...     pass  # Implementation
            >>>
            >>> LLMProviderFactory.register_provider("claude", ClaudeProvider)
            >>> provider = LLMProviderFactory.get_provider("claude")
        """
        if not issubclass(provider_class, BaseLLMProvider):
            raise TypeError(
                f"Provider class must inherit from BaseLLMProvider, "
                f"got {provider_class.__name__}"
            )

        logger.info("Registering provider: %s", provider_name)
        cls._provider_classes[provider_name.lower()] = provider_class

    @classmethod
    def clear_cache(cls) -> None:
        """
        Clear all cached provider instances.

        Useful for testing or when you want to force recreation of providers.

        Example:
            >>> LLMProviderFactory.clear_cache()
        """
        logger.info("Clearing provider cache")
        cls._instances.clear()

    @classmethod
    def list_providers(cls) -> list[str]:
        """
        Get list of available provider names.

        Returns:
            List of registered provider names

        Example:
            >>> providers = LLMProviderFactory.list_providers()
            >>> assert "ollama" in providers
        """
        return list(cls._provider_classes.keys())
