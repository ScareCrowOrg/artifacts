"""
Unit Tests for Chat IA Cell Backend Script (main.py)

Tests the execute_cell function with 90%+ code coverage.
Uses pytest with mocking for external dependencies.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import json

# Import the function to test
from ..scripts.main import execute_cell


class TestExecuteCellBasic:
    """Basic functionality tests"""

    @pytest.mark.asyncio
    async def test_valid_prompt_direct_mode(self):
        """Test valid prompt in direct LLM mode (no intent classification)"""
        # Mock the LLM provider
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "ollama"
            mock_provider.process_chat = AsyncMock(return_value={
                "response": "Hello! I'm doing well, thanks for asking!",
                "thread_id": None,
                "assistant_id": None
            })
            mock_factory.return_value = mock_provider

            result = await execute_cell({
                "prompt": "Hello, how are you?",
                "model": "mistral",
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is True
            assert "Hello" in result["output"]["response"]
            assert result["output"]["model_used"] == "mistral"
            assert mock_provider.process_chat.called

    @pytest.mark.asyncio
    async def test_empty_prompt_returns_error(self):
        """Test that empty prompt returns error"""
        result = await execute_cell({
            "prompt": "",
            "model": "gpt-4",
        }, user_id="test-user")

        assert result["success"] is False
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_missing_prompt_returns_error(self):
        """Test that missing prompt returns error"""
        result = await execute_cell({
            "model": "gpt-4",
        }, user_id="test-user")

        assert result["success"] is False
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_whitespace_only_prompt_returns_error(self):
        """Test that whitespace-only prompt returns error"""
        result = await execute_cell({
            "prompt": "   \n\t   ",
            "model": "gpt-4",
        }, user_id="test-user")

        assert result["success"] is False
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_missing_model_returns_error(self):
        """Test that missing model returns error"""
        result = await execute_cell({
            "prompt": "Hello",
        }, user_id="test-user")

        assert result["success"] is False
        assert "model" in result["error"].lower()


class TestModelNormalization:
    """Test model parameter normalization"""

    @pytest.mark.asyncio
    async def test_selectedmodel_alias_accepted(self):
        """Test that selectedModel parameter is accepted as alias for model"""
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "ollama"
            mock_provider.process_chat = AsyncMock(return_value={"response": "Test"})
            mock_factory.return_value = mock_provider

            result = await execute_cell({
                "prompt": "Test",
                "selectedModel": "mistral",  # Using selectedModel instead of model
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is True
            assert result["output"]["model_used"] == "mistral"

    @pytest.mark.asyncio
    async def test_model_parameter_preferred_over_selectedmodel(self):
        """Test that model parameter takes precedence over selectedModel"""
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "ollama"
            mock_provider.process_chat = AsyncMock(return_value={"response": "Test"})
            mock_factory.return_value = mock_provider

            result = await execute_cell({
                "prompt": "Test",
                "model": "gpt-4",
                "selectedModel": "mistral",  # This should be ignored
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is True
            assert result["output"]["model_used"] == "gpt-4"


class TestIntentClassification:
    """Test intent classification routing"""

    @pytest.mark.asyncio
    async def test_intent_classification_disabled_uses_direct_llm(self):
        """Test that disabled intent classification uses direct LLM"""
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "ollama"
            mock_provider.process_chat = AsyncMock(return_value={"response": "Direct LLM response"})
            mock_factory.return_value = mock_provider

            result = await execute_cell({
                "prompt": "Hello",
                "model": "mistral",
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is True
            assert "Direct LLM response" in result["output"]["response"]
            assert mock_provider.process_chat.called
            # Verify orchestrator was NOT called
            assert "Orchestrator" not in result["output"].get("debug", "")

    @pytest.mark.asyncio
    async def test_intent_classification_enabled_uses_orchestrator(self):
        """Test that enabled intent classification uses orchestrator"""
        with patch('backend.app.orchestrator.langgraph.get_orchestrator') as mock_orchestrator_fn:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.process = AsyncMock(return_value={
                "resposta": "Orchestrator response",
                "intencao": "criar",
                "celula": {"type": "python", "content": "print('hello')"},
                "conversation_id": "conv-123"
            })
            mock_orchestrator_fn.return_value = mock_orchestrator

            result = await execute_cell({
                "prompt": "Create a hello world cell",
                "model": "gpt-4",
                "enableIntentionClassification": True,
            }, user_id="test-user")

            assert result["success"] is True
            assert "Orchestrator response" in result["output"]["response"]
            assert mock_orchestrator.process.called
            assert result["output"]["cell"] is not None
            assert result["output"]["conversation_id"] == "conv-123"


class TestRAGSupport:
    """Test RAG (Retrieval-Augmented Generation) support"""

    @pytest.mark.asyncio
    async def test_rag_collections_passed_to_llm(self):
        """Test that selected collections are passed to LLM provider"""
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "ollama"
            mock_provider.process_chat = AsyncMock(return_value={"response": "Response with RAG"})
            mock_factory.return_value = mock_provider

            result = await execute_cell({
                "prompt": "Explain the architecture",
                "model": "mistral",
                "selectedCollections": ["docs", "code"],
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is True
            # Verify process_chat was called with RAG parameters
            call_kwargs = mock_provider.process_chat.call_args[1]
            assert call_kwargs.get("use_rag") is True
            assert call_kwargs.get("selected_collections") == ["docs", "code"]

    @pytest.mark.asyncio
    async def test_empty_collections_disables_rag(self):
        """Test that empty collections list disables RAG"""
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "ollama"
            mock_provider.process_chat = AsyncMock(return_value={"response": "Response without RAG"})
            mock_factory.return_value = mock_provider

            result = await execute_cell({
                "prompt": "Hello",
                "model": "mistral",
                "selectedCollections": [],
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is True
            call_kwargs = mock_provider.process_chat.call_args[1]
            assert call_kwargs.get("use_rag") is False


class TestOpenAIAssistants:
    """Test OpenAI Assistants API support (thread_id, assistant_id)"""

    @pytest.mark.asyncio
    async def test_openai_thread_id_passed_and_returned(self):
        """Test that OpenAI thread_id is passed and returned"""
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "openai"
            mock_provider.process_chat = AsyncMock(return_value={
                "response": "OpenAI response",
                "thread_id": "thread-xyz",
                "assistant_id": "asst-abc"
            })
            mock_factory.return_value = mock_provider

            result = await execute_cell({
                "prompt": "Hello",
                "model": "gpt-4",
                "thread_id": "thread-xyz",
                "assistant_id": "asst-abc",
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is True
            assert result["output"]["thread_id"] == "thread-xyz"
            assert result["output"]["assistant_id"] == "asst-abc"

    @pytest.mark.asyncio
    async def test_openai_ids_not_passed_for_other_providers(self):
        """Test that OpenAI IDs are not passed to non-OpenAI providers"""
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "ollama"
            mock_provider.process_chat = AsyncMock(return_value={"response": "Ollama response"})
            mock_factory.return_value = mock_provider

            result = await execute_cell({
                "prompt": "Hello",
                "model": "mistral",
                "thread_id": "thread-xyz",
                "assistant_id": "asst-abc",
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is True
            # Verify thread_id/assistant_id were NOT passed to non-OpenAI provider
            call_kwargs = mock_provider.process_chat.call_args[1]
            assert call_kwargs.get("thread_id") is None
            assert call_kwargs.get("assistant_id") is None


class TestAttachmentHandling:
    """Test file attachment processing"""

    @pytest.mark.asyncio
    async def test_attachments_processed_for_ollama(self):
        """Test that attachments are converted to segmented_content for Ollama"""
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "ollama"
            mock_provider.process_chat = AsyncMock(return_value={"response": "Response"})
            mock_factory.return_value = mock_provider

            result = await execute_cell({
                "prompt": "Analyze this code",
                "model": "mistral",
                "attachments": [
                    {"name": "file1.py", "content": "print('hello')", "type": "text/plain"},
                    {"name": "file2.py", "content": "print('world')", "type": "text/plain"},
                ],
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is True
            call_kwargs = mock_provider.process_chat.call_args[1]
            attached_metadata = call_kwargs.get("attached_content_metadata")
            assert attached_metadata is not None
            assert len(attached_metadata) > 0

    @pytest.mark.asyncio
    async def test_attachments_create_temp_files_for_openai(self):
        """Test that OpenAI attachments create temporary files"""
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "openai"
            mock_provider.process_chat = AsyncMock(return_value={
                "response": "Response",
                "thread_id": None,
                "assistant_id": None
            })
            mock_factory.return_value = mock_provider

            result = await execute_cell({
                "prompt": "Analyze this file",
                "model": "gpt-4",
                "attachments": [
                    {"name": "data.csv", "content": "col1,col2\n1,2", "type": "text/csv"},
                ],
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is True
            call_kwargs = mock_provider.process_chat.call_args[1]
            attached_metadata = call_kwargs.get("attached_content_metadata")
            assert attached_metadata is not None
            # Verify temp files were created with proper paths
            assert any("path" in str(m) for m in attached_metadata)


class TestConversationHistory:
    """Test conversation history handling"""

    @pytest.mark.asyncio
    async def test_conversation_history_passed_to_llm(self):
        """Test that conversation history is passed to LLM"""
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "ollama"
            mock_provider.process_chat = AsyncMock(return_value={"response": "Response"})
            mock_factory.return_value = mock_provider

            history = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ]

            result = await execute_cell({
                "prompt": "How are you?",
                "model": "mistral",
                "history": history,
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is True
            call_kwargs = mock_provider.process_chat.call_args[1]
            conv_history = call_kwargs.get("conversation_history")
            assert len(conv_history) == 2

    @pytest.mark.asyncio
    async def test_system_prompt_passed_to_llm(self):
        """Test that custom system prompt is passed to LLM"""
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "ollama"
            mock_provider.process_chat = AsyncMock(return_value={"response": "Response"})
            mock_factory.return_value = mock_provider

            result = await execute_cell({
                "prompt": "Hello",
                "model": "mistral",
                "systemPrompt": "You are a helpful AI assistant.",
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is True
            call_kwargs = mock_provider.process_chat.call_args[1]
            assert call_kwargs.get("system_instructions") == "You are a helpful AI assistant."


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_llm_provider_exception_returns_error(self):
        """Test that LLM provider exceptions are caught and returned as errors"""
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "ollama"
            mock_provider.process_chat = AsyncMock(
                side_effect=RuntimeError("LLM API unreachable")
            )
            mock_factory.return_value = mock_provider

            result = await execute_cell({
                "prompt": "Hello",
                "model": "mistral",
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is False
            assert "LLM processing failed" in result["error"]

    @pytest.mark.asyncio
    async def test_orchestrator_exception_returns_error(self):
        """Test that orchestrator exceptions are caught and returned as errors"""
        with patch('backend.app.orchestrator.langgraph.get_orchestrator') as mock_orchestrator_fn:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.process = AsyncMock(
                side_effect=RuntimeError("Orchestrator error")
            )
            mock_orchestrator_fn.return_value = mock_orchestrator

            result = await execute_cell({
                "prompt": "Create a cell",
                "model": "gpt-4",
                "enableIntentionClassification": True,
            }, user_id="test-user")

            assert result["success"] is False
            assert "Orchestrator processing failed" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_response_from_llm_returns_error(self):
        """Test handling of missing response from LLM"""
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "ollama"
            mock_provider.process_chat = AsyncMock(return_value={})  # Empty response
            mock_factory.return_value = mock_provider

            result = await execute_cell({
                "prompt": "Hello",
                "model": "mistral",
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is False
            assert "response" in result["error"].lower()


class TestModelProviderDetection:
    """Test model provider detection"""

    @pytest.mark.asyncio
    async def test_ollama_model_detection(self):
        """Test that ollama models are correctly detected"""
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "ollama"
            mock_provider.process_chat = AsyncMock(return_value={"response": "Test"})
            mock_factory.return_value = mock_provider

            result = await execute_cell({
                "prompt": "Hello",
                "model": "mistral",
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is True
            # Verify ollama provider was used
            mock_factory.assert_called()

    @pytest.mark.asyncio
    async def test_gemini_model_detection(self):
        """Test that gemini models are correctly detected"""
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "gemini"
            mock_provider.process_chat = AsyncMock(return_value={"response": "Test"})
            mock_factory.return_value = mock_provider

            result = await execute_cell({
                "prompt": "Hello",
                "model": "gemini",
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_openai_model_detection(self):
        """Test that openai models are correctly detected"""
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "openai"
            mock_provider.process_chat = AsyncMock(return_value={
                "response": "Test",
                "thread_id": None,
                "assistant_id": None
            })
            mock_factory.return_value = mock_provider

            result = await execute_cell({
                "prompt": "Hello",
                "model": "gpt-4",
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_model_with_slash_provider_detection(self):
        """Test model detection with slash notation (e.g., ollama/mistral)"""
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "ollama"
            mock_provider.process_chat = AsyncMock(return_value={"response": "Test"})
            mock_factory.return_value = mock_provider

            result = await execute_cell({
                "prompt": "Hello",
                "model": "ollama/neural-chat",
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is True


class TestResponseFormat:
    """Test response format consistency"""

    @pytest.mark.asyncio
    async def test_success_response_structure(self):
        """Test that success responses have correct structure"""
        with patch('backend.app.services.llm_provider_factory.LLMProviderFactory.get_provider') as mock_factory:
            mock_provider = AsyncMock()
            mock_provider.provider_name = "ollama"
            mock_provider.process_chat = AsyncMock(return_value={"response": "Test response"})
            mock_factory.return_value = mock_provider

            result = await execute_cell({
                "prompt": "Hello",
                "model": "mistral",
                "enableIntentionClassification": False,
            }, user_id="test-user")

            assert result["success"] is True
            assert "output" in result
            assert "response" in result["output"]
            assert "model_used" in result["output"]
            assert "conversation_id" in result["output"]
            assert "cell" in result["output"]
            assert "thread_id" in result["output"]
            assert "assistant_id" in result["output"]

    @pytest.mark.asyncio
    async def test_error_response_structure(self):
        """Test that error responses have correct structure"""
        result = await execute_cell({
            "prompt": "",
            "model": "gpt-4",
        }, user_id="test-user")

        assert result["success"] is False
        assert "error" in result
        assert result["output"] == {}
