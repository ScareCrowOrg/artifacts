"""
Integration tests for LLM Provider implementations

Tests the full chat processing flow for each provider with mocked APIs.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.providers import OllamaProvider, GeminiProvider, OpenAIProvider
from app.services.llm_provider_interface import LLMProviderError


@pytest.mark.asyncio
@patch('app.ollama_service.verificar_ollama_disponivel', new_callable=AsyncMock)
@patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock)
async def test_ollama_process_chat_basic(mock_chamar, mock_verificar):
    """Test basic Ollama chat processing without attachments or RAG."""
    mock_verificar.return_value = True
    mock_chamar.return_value = {"response": "Hello, how can I help?"}
    
    provider = OllamaProvider(model_id="mistral")
    result = await provider.process_chat(
        user_message="Hello",
        use_rag=False
    )
    
    assert result["response"] == "Hello, how can I help?"
    assert "response" in result
    mock_chamar.assert_called_once()


@pytest.mark.asyncio
@patch('app.ollama_service.verificar_ollama_disponivel', new_callable=AsyncMock)
@patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock)
async def test_ollama_with_segmented_content(mock_chamar, mock_verificar):
    """Test Ollama chat processing with segmented content."""
    mock_verificar.return_value = True
    mock_chamar.return_value = {"response": "The code defines a hello function"}
    
    provider = OllamaProvider()
    result = await provider.process_chat(
        user_message="Explain this code",
        attached_content_metadata=[{
            "type": "segmented_content",
            "content": [
                "def hello():",
                "    print('Hello World')"
            ]
        }],
        use_rag=False
    )
    
    assert result["response"] == "The code defines a hello function"
    
    # Verify segmented content is in prompt
    call_args = mock_chamar.call_args
    prompt = call_args[0][0]
    assert "def hello():" in prompt


@pytest.mark.asyncio
@patch('app.ollama_service.verificar_ollama_disponivel', new_callable=AsyncMock)
async def test_ollama_unavailable_service(mock_verificar):
    """Test that unavailable Ollama service raises LLMProviderError."""
    mock_verificar.return_value = False
    
    provider = OllamaProvider()
    
    with pytest.raises(LLMProviderError) as exc_info:
        await provider.process_chat(user_message="Hello")
    
    assert "not available" in str(exc_info.value).lower()


@pytest.mark.asyncio
@patch('app.gemini_service.chamar_gemini', new_callable=AsyncMock)
async def test_gemini_process_chat_basic(mock_chamar):
    """Test basic Gemini chat processing."""
    mock_chamar.return_value = {"response": "Hello, I'm Gemini!"}
    
    provider = GeminiProvider(api_key="test_key", model_id="gemini-pro")
    result = await provider.process_chat(
        user_message="Hello",
        use_rag=False
    )
    
    assert result["response"] == "Hello, I'm Gemini!"
    assert "response" in result
    mock_chamar.assert_called_once()


@pytest.mark.asyncio
@patch('app.gemini_service.chamar_gemini', new_callable=AsyncMock)
async def test_gemini_with_file_uris(mock_chamar):
    """Test Gemini chat processing with file URIs."""
    mock_chamar.return_value = {"response": "The file contains..."}
    
    provider = GeminiProvider(api_key="test_key")
    result = await provider.process_chat(
        user_message="Analyze this file",
        attached_content_metadata=[{
            "type": "file_id",
            "id": "file_abc123"
        }],
        use_rag=False
    )
    
    assert result["response"] == "The file contains..."
    
    # Verify file URIs are in messages
    call_args = mock_chamar.call_args
    messages = call_args[0][0]
    
    # Find the user message with file
    has_file = any(
        m.get("role") == "user" and any(
            "fileData" in part for part in m.get("parts", [])
        )
        for m in messages
    )
    assert has_file


@pytest.mark.asyncio
async def test_gemini_no_api_key():
    """Test that missing Gemini API key raises LLMProviderError."""
    provider = GeminiProvider(api_key=None)
    
    with pytest.raises(LLMProviderError) as exc_info:
        await provider.process_chat(user_message="Hello")
    
    assert "not configured" in str(exc_info.value).lower()


@pytest.mark.asyncio
@patch('app.openai_service.chamar_openai', new_callable=AsyncMock)
async def test_openai_process_chat_basic(mock_chamar):
    """Test basic OpenAI chat processing using Chat API."""
    mock_chamar.return_value = {
        "choices": [{"message": {"content": "Hello from OpenAI!"}}]
    }
    
    provider = OpenAIProvider(
        api_key="test_key",
        model_id="gpt-4",
        use_assistants_api=False
    )
    result = await provider.process_chat(
        user_message="Hello",
        use_rag=False
    )
    
    assert result["response"] == "Hello from OpenAI!"
    assert "response" in result
    mock_chamar.assert_called_once()


@pytest.mark.asyncio
async def test_openai_no_api_key():
    """Test that missing OpenAI API key raises LLMProviderError."""
    provider = OpenAIProvider(api_key=None)
    
    with pytest.raises(LLMProviderError) as exc_info:
        await provider.process_chat(user_message="Hello")
    
    assert "not configured" in str(exc_info.value).lower()


@pytest.mark.asyncio
@patch('app.ollama_service.verificar_ollama_disponivel', new_callable=AsyncMock, return_value=True)
@patch('app.ollama_service.chamar_ollama', new_callable=AsyncMock, return_value={"response": "ok"})
@patch('app.gemini_service.chamar_gemini', new_callable=AsyncMock, return_value={"response": "ok"})
@patch('app.openai_service.chamar_openai', new_callable=AsyncMock, 
       return_value={"choices": [{"message": {"content": "ok"}}]})
async def test_all_providers_return_response_dict(mock_openai, mock_gemini, mock_ollama, mock_verify):
    """Verify all providers return dict with 'response' key."""
    message = "Test message"
    
    # Test Ollama
    ollama = OllamaProvider()
    result = await ollama.process_chat(message, use_rag=False)
    assert "response" in result
    assert isinstance(result["response"], str)
    
    # Test Gemini
    gemini = GeminiProvider(api_key="test")
    result = await gemini.process_chat(message, use_rag=False)
    assert "response" in result
    assert isinstance(result["response"], str)
    
    # Test OpenAI
    openai = OpenAIProvider(api_key="test", use_assistants_api=False)
    result = await openai.process_chat(message, use_rag=False)
    assert "response" in result
    assert isinstance(result["response"], str)


def test_all_providers_have_required_properties():
    """Verify all providers implement required properties."""
    providers = [
        OllamaProvider(),
        GeminiProvider(api_key="test"),
        OpenAIProvider(api_key="test")
    ]
    
    for provider in providers:
        assert hasattr(provider, "provider_name")
        assert hasattr(provider, "model_name")
        assert isinstance(provider.provider_name, str)
        assert isinstance(provider.model_name, str)
        assert len(provider.provider_name) > 0
        assert len(provider.model_name) > 0
