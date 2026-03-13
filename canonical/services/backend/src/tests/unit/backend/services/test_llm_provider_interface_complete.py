"""
Additional unit tests for LLM Provider Interface to complete coverage.

Tests additional edge cases and verify_availability method variants.

Technical naming: All functions and variables in English.
"""

import pytest
from unittest.mock import AsyncMock, Mock
from app.services.llm_provider_interface import BaseLLMProvider, LLMProviderError


class TestLLMProviderErrorEdgeCases:
    """Additional tests for LLMProviderError exception."""
    
    def test_error_attributes(self):
        """Test that error has provider attribute."""
        error = LLMProviderError("Test error", provider="test_provider")
        assert error.provider == "test_provider"
    
    def test_error_without_provider_attribute(self):
        """Test error without provider has None attribute."""
        error = LLMProviderError("Test error")
        assert error.provider is None
    
    def test_error_str_representation(self):
        """Test string representation of error."""
        error = LLMProviderError("Connection failed", provider="ollama")
        error_str = str(error)
        assert "[ollama]" in error_str
        assert "Connection failed" in error_str
    
    def test_error_inheritance(self):
        """Test that LLMProviderError is an Exception."""
        error = LLMProviderError("Test")
        assert isinstance(error, Exception)
    
    def test_error_can_be_raised_and_caught(self):
        """Test that error can be raised and caught."""
        with pytest.raises(LLMProviderError) as exc_info:
            raise LLMProviderError("Test error", provider="test")
        
        assert "Test error" in str(exc_info.value)
        assert exc_info.value.provider == "test"


class TestBaseLLMProviderVerifyAvailability:
    """Tests for verify_availability method variants."""
    
    @pytest.mark.asyncio
    async def test_verify_availability_custom_implementation(self):
        """Test custom verify_availability implementation."""
        class CustomProvider(BaseLLMProvider):
            @property
            def provider_name(self):
                return "custom"
            
            @property
            def model_name(self):
                return "custom-model"
            
            async def process_chat(self, **kwargs):
                return {"response": "test"}
            
            async def verify_availability(self) -> bool:
                # Custom implementation that checks actual service
                return True
        
        provider = CustomProvider()
        is_available = await provider.verify_availability()
        
        assert is_available is True
    
    @pytest.mark.asyncio
    async def test_verify_availability_returns_false(self):
        """Test verify_availability that returns False."""
        class UnavailableProvider(BaseLLMProvider):
            @property
            def provider_name(self):
                return "unavailable"
            
            @property
            def model_name(self):
                return "model"
            
            async def process_chat(self, **kwargs):
                return {"response": "test"}
            
            async def verify_availability(self) -> bool:
                return False
        
        provider = UnavailableProvider()
        is_available = await provider.verify_availability()
        
        assert is_available is False
    
    @pytest.mark.asyncio
    async def test_verify_availability_with_error(self):
        """Test verify_availability that raises error."""
        class ErrorProvider(BaseLLMProvider):
            @property
            def provider_name(self):
                return "error"
            
            @property
            def model_name(self):
                return "model"
            
            async def process_chat(self, **kwargs):
                return {"response": "test"}
            
            async def verify_availability(self) -> bool:
                raise LLMProviderError("Service unavailable", provider="error")
        
        provider = ErrorProvider()
        
        with pytest.raises(LLMProviderError):
            await provider.verify_availability()


class TestBaseLLMProviderProcessChat:
    """Additional tests for process_chat method contract."""
    
    @pytest.mark.asyncio
    async def test_process_chat_with_all_parameters(self):
        """Test process_chat with all possible parameters."""
        class FullProvider(BaseLLMProvider):
            @property
            def provider_name(self):
                return "full"
            
            @property
            def model_name(self):
                return "full-model"
            
            async def process_chat(
                self,
                user_message: str,
                conversation_history=None,
                rag_context=None,
                attached_content_metadata=None,
                system_instructions=None,
                use_rag=True,
                selected_collections=None,
                **kwargs
            ):
                return {
                    "response": user_message,
                    "history_len": len(conversation_history or []),
                    "has_rag": rag_context is not None,
                    "has_attachments": attached_content_metadata is not None,
                    "has_system": system_instructions is not None,
                    "use_rag": use_rag,
                    "collections": selected_collections
                }
        
        provider = FullProvider()
        
        result = await provider.process_chat(
            user_message="Test",
            conversation_history=[{"role": "user", "content": "Hi"}],
            rag_context="RAG context",
            attached_content_metadata=[{"type": "file", "id": "123"}],
            system_instructions="Be helpful",
            use_rag=True,
            selected_collections=["docs"]
        )
        
        assert result["response"] == "Test"
        assert result["history_len"] == 1
        assert result["has_rag"] is True
        assert result["has_attachments"] is True
        assert result["has_system"] is True
        assert result["use_rag"] is True
        assert result["collections"] == ["docs"]
    
    @pytest.mark.asyncio
    async def test_process_chat_minimal_parameters(self):
        """Test process_chat with minimal parameters."""
        class MinimalProvider(BaseLLMProvider):
            @property
            def provider_name(self):
                return "minimal"
            
            @property
            def model_name(self):
                return "minimal-model"
            
            async def process_chat(self, user_message: str, **kwargs):
                return {"response": f"Echo: {user_message}"}
        
        provider = MinimalProvider()
        
        result = await provider.process_chat(user_message="Hello")
        
        assert result["response"] == "Echo: Hello"
    
    @pytest.mark.asyncio
    async def test_process_chat_with_custom_kwargs(self):
        """Test process_chat with additional custom kwargs."""
        class CustomKwargsProvider(BaseLLMProvider):
            @property
            def provider_name(self):
                return "custom"
            
            @property
            def model_name(self):
                return "custom-model"
            
            async def process_chat(self, user_message: str, **kwargs):
                custom_param = kwargs.get("custom_param", "default")
                return {
                    "response": user_message,
                    "custom": custom_param
                }
        
        provider = CustomKwargsProvider()
        
        result = await provider.process_chat(
            user_message="Test",
            custom_param="custom_value"
        )
        
        assert result["custom"] == "custom_value"


class TestBaseLLMProviderProperties:
    """Tests for provider_name and model_name properties."""
    
    def test_provider_name_returns_string(self):
        """Test that provider_name returns a string."""
        class StringProvider(BaseLLMProvider):
            @property
            def provider_name(self):
                return "test_provider"
            
            @property
            def model_name(self):
                return "test_model"
            
            async def process_chat(self, **kwargs):
                return {}
        
        provider = StringProvider()
        assert isinstance(provider.provider_name, str)
        assert provider.provider_name == "test_provider"
    
    def test_model_name_returns_string(self):
        """Test that model_name returns a string."""
        class ModelProvider(BaseLLMProvider):
            @property
            def provider_name(self):
                return "provider"
            
            @property
            def model_name(self):
                return "gpt-4-turbo"
            
            async def process_chat(self, **kwargs):
                return {}
        
        provider = ModelProvider()
        assert isinstance(provider.model_name, str)
        assert provider.model_name == "gpt-4-turbo"
    
    def test_properties_are_readonly(self):
        """Test that properties cannot be directly set."""
        class ReadOnlyProvider(BaseLLMProvider):
            @property
            def provider_name(self):
                return "readonly"
            
            @property
            def model_name(self):
                return "model"
            
            async def process_chat(self, **kwargs):
                return {}
        
        provider = ReadOnlyProvider()
        
        # Properties should be read-only (can't be reassigned)
        with pytest.raises(AttributeError):
            provider.provider_name = "new_value"


class TestBaseLLMProviderAbstractMethods:
    """Tests verifying abstract method enforcement."""
    
    def test_all_abstract_methods_must_be_implemented(self):
        """Test that all abstract methods must be implemented."""
        # Missing all abstract methods
        with pytest.raises(TypeError):
            class IncompleteProvider(BaseLLMProvider):
                pass
            IncompleteProvider()
    
    def test_partial_implementation_fails(self):
        """Test that partial implementation fails."""
        # Only implementing one abstract method
        with pytest.raises(TypeError):
            class PartialProvider(BaseLLMProvider):
                @property
                def provider_name(self):
                    return "partial"
            PartialProvider()
    
    def test_complete_implementation_succeeds(self):
        """Test that complete implementation succeeds."""
        class CompleteProvider(BaseLLMProvider):
            @property
            def provider_name(self):
                return "complete"
            
            @property
            def model_name(self):
                return "model"
            
            async def process_chat(self, **kwargs):
                return {"response": "ok"}
        
        # Should not raise
        provider = CompleteProvider()
        assert provider.provider_name == "complete"
