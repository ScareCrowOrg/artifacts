"""
Integration tests for refactored LLM service functions using the centralized prompt_builder.

These tests verify that the service functions correctly use the prompt_builder
and maintain backward compatibility.
"""

import pytest
from unittest.mock import AsyncMock, patch
from app.ollama_service import processar_chat_com_ollama, processar_chat_com_ollama_rag
from app.gemini_service import processar_chat_com_gemini, processar_chat_com_gemini_rag
from app.openai_service import processar_chat_com_openai, processar_chat_com_openai_rag


class TestOllamaServiceIntegration:
    """Tests for Ollama service using prompt_builder."""
    
    @pytest.mark.asyncio
    @patch('app.ollama_service.verificar_ollama_disponivel')
    @patch('app.ollama_service.chamar_ollama')
    async def test_processar_chat_com_ollama_uses_prompt_builder(
        self,
        mock_chamar: AsyncMock,
        mock_verificar: AsyncMock
    ):
        """Test that processar_chat_com_ollama uses the prompt builder correctly."""
        mock_verificar.return_value = True
        mock_chamar.return_value = {"response": "Test response"}
        
        result = await processar_chat_com_ollama(
            intencao="Hello",
            historico=[{"role": "user", "content": "Hi"}]
        )
        
        assert result == "Test response"
        mock_chamar.assert_called_once()
        
        # Verify the prompt was built with correct structure
        call_args = mock_chamar.call_args
        prompt = call_args[0][0]
        assert isinstance(prompt, str)
        assert "Hello" in prompt
        assert "IMPORTANTE:" in prompt  # History instruction
    
    @pytest.mark.asyncio
    @patch('app.ollama_service.verificar_ollama_disponivel')
    @patch('app.ollama_service.chamar_ollama')
    async def test_processar_chat_com_ollama_rag_uses_prompt_builder(
        self,
        mock_chamar: AsyncMock,
        mock_verificar: AsyncMock
    ):
        """Test that processar_chat_com_ollama_rag uses the prompt builder correctly."""
        mock_verificar.return_value = True
        mock_chamar.return_value = {"response": "RAG response"}
        
        result = await processar_chat_com_ollama_rag(
            nova_intencao="Explain",
            historico=[],
            rag_context="Context from docs",
            use_rag=False  # Disable actual RAG retrieval
        )
        
        assert result == "RAG response"
        mock_chamar.assert_called_once()
        
        # Verify RAG context is in the prompt
        call_args = mock_chamar.call_args
        prompt = call_args[0][0]
        assert "Context from docs" in prompt
        assert "### Contexto Relevante do Repositório ###" in prompt


class TestGeminiServiceIntegration:
    """Tests for Gemini service using prompt_builder."""
    
    @pytest.mark.asyncio
    @patch('app.gemini_service.chamar_gemini')
    async def test_processar_chat_com_gemini_uses_prompt_builder(
        self,
        mock_chamar: AsyncMock
    ):
        """Test that processar_chat_com_gemini uses the prompt builder correctly."""
        mock_chamar.return_value = {"response": "Gemini response"}
        
        result = await processar_chat_com_gemini(
            intencao="Hello",
            historico=[{"role": "user", "content": "Hi"}],
            api_key="test_key"
        )
        
        assert result == "Gemini response"
        mock_chamar.assert_called_once()
        
        # Verify the messages list was built correctly
        call_args = mock_chamar.call_args
        messages = call_args[0][0]
        assert isinstance(messages, list)
        
        # Should have history instruction + acknowledgment + history + current
        assert len(messages) >= 3
        
        # Find the message with IMPORTANTE instruction
        has_instruction = any(
            "IMPORTANTE:" in part.get("text", "")
            for msg in messages
            for part in msg.get("parts", [])
            if isinstance(part, dict)
        )
        assert has_instruction
    
    @pytest.mark.asyncio
    @patch('app.gemini_service.chamar_gemini')
    async def test_processar_chat_com_gemini_rag_uses_prompt_builder(
        self,
        mock_chamar: AsyncMock
    ):
        """Test that processar_chat_com_gemini_rag uses the prompt builder correctly."""
        mock_chamar.return_value = {"response": "Gemini RAG response"}
        
        result = await processar_chat_com_gemini_rag(
            nova_intencao="Explain",
            historico=[],
            api_key="test_key",
            use_rag=False  # Disable actual RAG retrieval
        )
        
        assert result == "Gemini RAG response"
        mock_chamar.assert_called_once()
        
        # Verify messages structure
        call_args = mock_chamar.call_args
        messages = call_args[0][0]
        assert isinstance(messages, list)


class TestOpenAIServiceIntegration:
    """Tests for OpenAI service using prompt_builder."""
    
    @pytest.mark.asyncio
    @patch('app.openai_service.chat_processor.chamar_openai')
    async def test_processar_chat_com_openai_uses_prompt_builder(
        self,
        mock_chamar: AsyncMock
    ):
        """Test that processar_chat_com_openai uses the prompt builder correctly."""
        mock_chamar.return_value = {
            "choices": [{"message": {"content": "OpenAI response"}}]
        }
        
        result = await processar_chat_com_openai(
            nova_intencao="Hello",
            historico=[{"role": "user", "content": "Hi"}],
            api_key="test_key"
        )
        
        assert result == "OpenAI response"
        mock_chamar.assert_called_once()
        
        # Verify the payload structure
        call_args = mock_chamar.call_args
        payload = call_args[1]["payload"]
        messages = payload["messages"]
        
        assert isinstance(messages, list)
        # Should have system (with history instruction) + history + current
        assert len(messages) >= 3
        
        # First message should be system with IMPORTANTE instruction
        system_msg = next((m for m in messages if m["role"] == "system"), None)
        assert system_msg is not None
        assert "IMPORTANTE:" in system_msg["content"]
    
    @pytest.mark.asyncio
    @patch('app.openai_service.rag_integration.chamar_openai')
    async def test_processar_chat_com_openai_rag_uses_prompt_builder(
        self,
        mock_chamar: AsyncMock
    ):
        """Test that processar_chat_com_openai_rag uses the prompt builder correctly."""
        mock_chamar.return_value = {
            "choices": [{"message": {"content": "OpenAI RAG response"}}]
        }
        
        result = await processar_chat_com_openai_rag(
            nova_intencao="Explain",
            historico=[],
            api_key="test_key",
            use_rag=False  # Disable actual RAG retrieval
        )
        
        assert result == "OpenAI RAG response"
        mock_chamar.assert_called_once()
        
        # Verify payload structure
        call_args = mock_chamar.call_args
        payload = call_args[1]["payload"]
        messages = payload["messages"]
        
        assert isinstance(messages, list)


class TestPromptConsistency:
    """Tests to verify consistent prompt structure across all providers."""
    
    @pytest.mark.asyncio
    @patch('app.ollama_service.verificar_ollama_disponivel', return_value=True)
    @patch('app.ollama_service.chamar_ollama', return_value={"response": "ok"})
    @patch('app.gemini_service.chamar_gemini', return_value={"response": "ok"})
    @patch('app.openai_service.chat_processor.chamar_openai', return_value={"choices": [{"message": {"content": "ok"}}]})
    async def test_all_providers_include_history_instruction(
        self,
        mock_openai: AsyncMock,
        mock_gemini: AsyncMock,
        mock_ollama: AsyncMock,
        mock_verify: AsyncMock
    ):
        """Verify all providers include the IMPORTANTE history instruction."""
        history = [{"role": "user", "content": "Previous message"}]
        
        # Test Ollama
        await processar_chat_com_ollama(intencao="Test", historico=history)
        ollama_prompt = mock_ollama.call_args[0][0]
        assert "IMPORTANTE:" in ollama_prompt
        
        # Test Gemini
        await processar_chat_com_gemini(intencao="Test", historico=history, api_key="key")
        gemini_messages = mock_gemini.call_args[0][0]
        has_instruction = any(
            "IMPORTANTE:" in part.get("text", "")
            for msg in gemini_messages
            for part in msg.get("parts", [])
            if isinstance(part, dict)
        )
        assert has_instruction
        
        # Test OpenAI
        await processar_chat_com_openai(nova_intencao="Test", historico=history, api_key="key")
        openai_payload = mock_openai.call_args[1]["payload"]
        system_msg = next((m for m in openai_payload["messages"] if m["role"] == "system"), None)
        assert system_msg is not None
        assert "IMPORTANTE:" in system_msg["content"]
