"""
Unit tests for LLM Provider Interface and Factory

Tests the base interface contract and factory pattern implementation.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.llm_provider_interface import BaseLLMProvider, LLMProviderError
from app.services.llm_provider_factory import LLMProviderFactory
from app.services.providers import OllamaProvider, GeminiProvider, OpenAIProvider


class TestBaseLLMProvider:
    """Tests for BaseLLMProvider abstract interface."""
    
    def test_cannot_instantiate_abstract_class(self):
        """Test that BaseLLMProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseLLMProvider()
    
    def test_must_implement_provider_name(self):
        """Test that concrete class must implement provider_name property."""
        class IncompleteProvider(BaseLLMProvider):
            @property
            def model_name(self):
                return "test"
            
            async def process_chat(self, **kwargs):
                return {}
        
        with pytest.raises(TypeError):
            IncompleteProvider()
    
    def test_must_implement_model_name(self):
        """Test that concrete class must implement model_name property."""
        class IncompleteProvider(BaseLLMProvider):
            @property
            def provider_name(self):
                return "test"
            
            async def process_chat(self, **kwargs):
                return {}
        
        with pytest.raises(TypeError):
            IncompleteProvider()
    
    def test_must_implement_process_chat(self):
        """Test that concrete class must implement process_chat method."""
        class IncompleteProvider(BaseLLMProvider):
            @property
            def provider_name(self):
                return "test"
            
            @property
            def model_name(self):
                return "test"
        
        with pytest.raises(TypeError):
            IncompleteProvider()
    
    @pytest.mark.asyncio
    async def test_verify_availability_default_implementation(self):
        """Test default verify_availability returns True."""
        class MinimalProvider(BaseLLMProvider):
            @property
            def provider_name(self):
                return "test"
            
            @property
            def model_name(self):
                return "test-model"
            
            async def process_chat(self, **kwargs):
                return {"response": "test"}
        
        provider = MinimalProvider()
        assert await provider.verify_availability() is True


class TestLLMProviderError:
    """Tests for LLMProviderError exception."""
    
    def test_error_with_provider(self):
        """Test error message includes provider name."""
        error = LLMProviderError("Test error", provider="ollama")
        assert "[ollama]" in str(error)
        assert "Test error" in str(error)
    
    def test_error_without_provider(self):
        """Test error message without provider name."""
        error = LLMProviderError("Test error")
        assert "Test error" in str(error)
        assert "[" not in str(error)


class TestLLMProviderFactory:
    """Tests for LLMProviderFactory."""
    
    def setup_method(self):
        """Clear factory cache before each test."""
        LLMProviderFactory.clear_cache()
    
    def test_get_ollama_provider(self):
        """Test getting Ollama provider."""
        provider = LLMProviderFactory.get_provider("ollama")
        assert isinstance(provider, OllamaProvider)
        assert provider.provider_name == "ollama"
    
    def test_get_gemini_provider(self):
        """Test getting Gemini provider."""
        provider = LLMProviderFactory.get_provider("gemini")
        assert isinstance(provider, GeminiProvider)
        assert provider.provider_name == "gemini"
    
    def test_get_openai_provider(self):
        """Test getting OpenAI provider."""
        provider = LLMProviderFactory.get_provider("openai")
        assert isinstance(provider, OpenAIProvider)
        assert provider.provider_name == "openai"
    
    def test_provider_name_case_insensitive(self):
        """Test that provider names are case-insensitive."""
        provider1 = LLMProviderFactory.get_provider("OLLAMA")
        provider2 = LLMProviderFactory.get_provider("ollama")
        provider3 = LLMProviderFactory.get_provider("Ollama")
        
        # All should return same singleton instance
        assert provider1 is provider2
        assert provider2 is provider3
    
    def test_unknown_provider_raises_error(self):
        """Test that unknown provider name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            LLMProviderFactory.get_provider("unknown")
        
        assert "Unknown provider" in str(exc_info.value)
        assert "ollama" in str(exc_info.value).lower()
    
    def test_singleton_pattern(self):
        """Test that factory returns same instance for same provider."""
        provider1 = LLMProviderFactory.get_provider("ollama")
        provider2 = LLMProviderFactory.get_provider("ollama")
        
        assert provider1 is provider2
    
    def test_custom_config_creates_new_instance(self):
        """Test that custom config creates new instance instead of singleton."""
        provider1 = LLMProviderFactory.get_provider("ollama")
        provider2 = LLMProviderFactory.get_provider("ollama", model_id="llama2")
        provider3 = LLMProviderFactory.get_provider("ollama", api_key="test")
        
        # Custom configs should create different instances
        assert provider1 is not provider2
        assert provider1 is not provider3
        assert provider2 is not provider3
    
    def test_custom_model_id(self):
        """Test creating provider with custom model_id."""
        provider = LLMProviderFactory.get_provider("ollama", model_id="llama2")
        assert provider.model_name == "llama2"
    
    def test_list_providers(self):
        """Test listing available providers."""
        providers = LLMProviderFactory.list_providers()
        assert "ollama" in providers
        assert "gemini" in providers
        assert "openai" in providers
    
    def test_clear_cache(self):
        """Test clearing provider cache."""
        provider1 = LLMProviderFactory.get_provider("ollama")
        LLMProviderFactory.clear_cache()
        provider2 = LLMProviderFactory.get_provider("ollama")
        
        # After cache clear, should get different instance
        assert provider1 is not provider2
    
    def test_register_custom_provider(self):
        """Test registering a custom provider."""
        class CustomProvider(BaseLLMProvider):
            @property
            def provider_name(self):
                return "custom"
            
            @property
            def model_name(self):
                return "custom-model"
            
            async def process_chat(self, **kwargs):
                return {"response": "custom"}
        
        LLMProviderFactory.register_provider("custom", CustomProvider)
        
        assert "custom" in LLMProviderFactory.list_providers()
        
        provider = LLMProviderFactory.get_provider("custom")
        assert isinstance(provider, CustomProvider)
    
    def test_register_non_provider_class_raises_error(self):
        """Test that registering non-BaseLLMProvider class raises TypeError."""
        class NotAProvider:
            pass
        
        with pytest.raises(TypeError) as exc_info:
            LLMProviderFactory.register_provider("invalid", NotAProvider)
        
        assert "BaseLLMProvider" in str(exc_info.value)


class TestProviderInstantiation:
    """Tests for provider instantiation and configuration."""
    
    def test_ollama_provider_default_config(self):
        """Test OllamaProvider uses default config."""
        provider = OllamaProvider()
        assert provider.provider_name == "ollama"
        assert provider.model_name  # Should have a model name from config
    
    def test_ollama_provider_custom_model(self):
        """Test OllamaProvider with custom model."""
        provider = OllamaProvider(model_id="llama2")
        assert provider.model_name == "llama2"
    
    def test_gemini_provider_default_config(self):
        """Test GeminiProvider uses default config."""
        provider = GeminiProvider()
        assert provider.provider_name == "gemini"
        assert provider.model_name  # Should have a model name from config
    
    def test_gemini_provider_custom_model(self):
        """Test GeminiProvider with custom model."""
        provider = GeminiProvider(model_id="gemini-pro")
        assert provider.model_name == "gemini-pro"
    
    def test_openai_provider_default_config(self):
        """Test OpenAIProvider uses default config."""
        provider = OpenAIProvider()
        assert provider.provider_name == "openai"
        assert provider.model_name  # Should have a model name from config
    
    def test_openai_provider_custom_model(self):
        """Test OpenAIProvider with custom model."""
        provider = OpenAIProvider(model_id="gpt-4")
        assert provider.model_name == "gpt-4"
