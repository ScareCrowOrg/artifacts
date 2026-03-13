"""
Unit tests for response_generator.py

Tests the response generator node which:
- Generates responses based on classified intentions
- Integrates with LLM services (Gemini, OpenAI, Ollama)
- Formats RAG context for prompts
- Handles different intention types (CONVERSAR, CRIAR, EXECUTAR, REFLETIR, DEPURAR)
- Saves conversations to memory
- Records tracing fragments

Target coverage: 90%+
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.orchestrator.langgraph.response_generator import (
    retorna_resposta,
    _gerar_resposta_conversa,
    _generate_fallback_response,
    _gerar_resposta_criar,
    _gerar_resposta_executar,
    _gerar_resposta_reflexao,
    _gerar_resposta_depuracao,
    _save_to_memory
)
from app.intention_classifier import IntentionType


class TestGenerateFallbackResponse:
    """Test fallback response generation."""
    
    def test_generate_fallback_response_basic(self):
        """Test basic fallback response without context."""
        response = _generate_fallback_response("What is ScareVerse?")
        
        assert "ScareVerse" in response
        assert "assistente" in response
        assert "Criar células" in response
    
    def test_generate_fallback_response_with_context(self):
        """Test fallback response with RAG context."""
        context = "ScareVerse is a collaborative software development system."
        response = _generate_fallback_response("Tell me about it", context)
        
        assert "Contexto dos Documentos" in response
        assert len(response) > 0


class TestGerarRespostaCriar:
    """Test cell creation response generation."""
    
    def test_criar_success(self):
        """Test successful cell creation response."""
        resultado = {
            "success": True,
            "celula_id": "cell123"
        }
        
        response = _gerar_resposta_criar(resultado)
        
        assert "criada com sucesso" in response
        assert "cell123" in response
        assert "✅" in response
    
    def test_criar_failure(self):
        """Test failed cell creation response."""
        resultado = {
            "success": False,
            "error": "Permission denied"
        }
        
        response = _gerar_resposta_criar(resultado)
        
        assert "Não foi possível" in response
        assert "Permission denied" in response
        assert "❌" in response
    
    def test_criar_none_result(self):
        """Test cell creation with None result."""
        response = _gerar_resposta_criar(None)
        
        assert "Não foi possível" in response


class TestGerarRespostaExecutar:
    """Test cell execution response generation."""
    
    def test_executar_success(self):
        """Test successful execution response."""
        resultado = {
            "success": True,
            "message": "Cell executed successfully"
        }
        
        response = _gerar_resposta_executar(resultado)
        
        assert "Cell executed successfully" in response
    
    def test_executar_failure(self):
        """Test failed execution response."""
        resultado = {
            "success": False
        }
        
        response = _gerar_resposta_executar(resultado)
        
        assert "forneça o ID" in response


class TestGerarRespostaReflexao:
    """Test reflection response generation."""
    
    def test_reflexao(self):
        """Test reflection response."""
        response = _gerar_resposta_reflexao("Review my work")
        
        assert "revisar resultados" in response
        assert "ID da célula" in response


class TestGerarRespostaDepuracao:
    """Test debugging response generation."""
    
    def test_depuracao(self):
        """Test debugging response."""
        response = _gerar_resposta_depuracao("Debug this error")
        
        assert "depurar" in response
        assert "ID da célula" in response
        assert "🔍" in response


class TestSaveToMemory:
    """Test conversation memory saving."""
    
    def test_save_to_memory_success(self, sample_state):
        """Test successful memory save."""
        sample_state["session_id"] = "session123"
        
        mock_memory = Mock()
        mock_memory.add_exchange = Mock()
        
        with patch('app.utils.conversation_memory.get_session_memory') as mock_get:
            mock_get.return_value = mock_memory
            
            _save_to_memory(sample_state, "Hello", "Hi there")
            
            mock_memory.add_exchange.assert_called_once_with("Hello", "Hi there")
    
    def test_save_to_memory_error_handling(self, sample_state):
        """Test memory save error handling."""
        sample_state["session_id"] = "session123"
        
        with patch('app.utils.conversation_memory.get_session_memory') as mock_get:
            mock_get.side_effect = Exception("Memory error")
            
            # Should not raise, just log error
            _save_to_memory(sample_state, "Hello", "Hi")


@pytest.mark.asyncio
class TestGerarRespostaConversa:
    """Test conversation response generation with LLM."""
    
    async def test_gerar_resposta_ollama(self, sample_state):
        """Test response generation with Ollama."""
        sample_state["target_llm"] = "ollama"
        sample_state["mensagem"] = "What is LangGraph?"
        
        with patch('app.ollama_service.processar_chat_com_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = "LangGraph is a framework..."
            
            response = await _gerar_resposta_conversa(sample_state, "What is LangGraph?")
            
            assert "LangGraph is a framework" in response
            mock_ollama.assert_called_once()
    
    async def test_gerar_resposta_openai(self, sample_state):
        """Test response generation with OpenAI."""
        sample_state["target_llm"] = "openai"
        sample_state["mensagem"] = "Explain testing"
        
        with patch('app.openai_service.processar_chat_com_openai', new_callable=AsyncMock) as mock_openai:
            mock_openai.return_value = "Testing is important..."
            
            response = await _gerar_resposta_conversa(sample_state, "Explain testing")
            
            assert "Testing is important" in response
            mock_openai.assert_called_once()
    
    async def test_gerar_resposta_gemini(self, sample_state):
        """Test response generation with Gemini."""
        sample_state["target_llm"] = "gemini"
        sample_state["mensagem"] = "Tell me about Python"
        
        with patch('app.gemini_service.processar_chat_com_gemini', new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = "Python is a programming language..."
            
            response = await _gerar_resposta_conversa(sample_state, "Tell me about Python")
            
            assert "Python is a programming language" in response
            mock_gemini.assert_called_once()
    
    async def test_gerar_resposta_with_rag_context(self, state_with_rag):
        """Test response generation with RAG context."""
        state_with_rag["target_llm"] = "ollama"
        formatted_context = "RAG context: ScareVerse info"
        
        with patch('app.ollama_service.processar_chat_com_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = "Based on the context..."
            
            response = await _gerar_resposta_conversa(state_with_rag, "Query", formatted_context)
            
            # Verify RAG context was included in the enriched message
            call_args = mock_ollama.call_args
            # The parameter name is "intencao" not "nova_intencao"
            assert "Contexto Relevante" in call_args[1]["intencao"]
    
    async def test_gerar_resposta_unknown_llm(self, sample_state):
        """Test response generation with unknown LLM (fallback)."""
        sample_state["target_llm"] = "unknown_llm"
        
        response = await _gerar_resposta_conversa(sample_state, "Test message")
        
        # Should return fallback response
        assert "assistente" in response
    
    async def test_gerar_resposta_llm_error(self, sample_state):
        """Test response generation when LLM fails."""
        sample_state["target_llm"] = "ollama"
        
        with patch('app.ollama_service.processar_chat_com_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.side_effect = Exception("LLM error")
            
            response = await _gerar_resposta_conversa(sample_state, "Test")
            
            # Should return fallback response
            assert "assistente" in response
    
    async def test_gerar_resposta_with_tracing(self, sample_state):
        """Test response generation with tracing enabled."""
        sample_state["target_llm"] = "ollama"
        sample_state["enable_tracing"] = True
        sample_state["trace_cell_id"] = "trace123"
        sample_state["conversation_id"] = "conv123"
        
        mock_trace_service = Mock()
        mock_trace_service.record_fragment = AsyncMock()
        
        with patch('app.ollama_service.processar_chat_com_ollama') as mock_ollama, \
             patch('app.services.conversation_trace_service.get_conversation_trace_service') as mock_get_trace:
            
            mock_ollama.return_value = "Response"
            mock_get_trace.return_value = mock_trace_service
            
            response = await _gerar_resposta_conversa(sample_state, "Query")
            
            # Verify tracing fragments were recorded
            assert mock_trace_service.record_fragment.called


@pytest.mark.asyncio
class TestRetornaResposta:
    """Test the main response generator node."""
    
    async def test_retorna_resposta_conversar(self, sample_state):
        """Test response for CONVERSAR intention."""
        sample_state["intencao"] = IntentionType.CONVERSAR.value
        sample_state["mensagem"] = "What is testing?"
        sample_state["target_llm"] = "ollama"
        
        with patch('app.ollama_service.processar_chat_com_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = "Testing validates code..."
            
            result = await retorna_resposta(sample_state)
            
            assert result["resposta"] == "Testing validates code..."
    
    async def test_retorna_resposta_criar_success(self, sample_state):
        """Test response for successful CRIAR intention."""
        sample_state["intencao"] = IntentionType.CRIAR.value
        sample_state["resultado_acao"] = {
            "success": True,
            "celula_id": "cell456"
        }
        
        result = await retorna_resposta(sample_state)
        
        assert "criada com sucesso" in result["resposta"]
        assert "cell456" in result["resposta"]
    
    async def test_retorna_resposta_executar(self, sample_state):
        """Test response for EXECUTAR intention."""
        sample_state["intencao"] = IntentionType.EXECUTAR.value
        sample_state["resultado_acao"] = {
            "success": True,
            "message": "Execution completed"
        }
        
        result = await retorna_resposta(sample_state)
        
        assert "Execution completed" in result["resposta"]
    
    async def test_retorna_resposta_refletir(self, sample_state):
        """Test response for REFLETIR intention."""
        sample_state["intencao"] = IntentionType.REFLETIR.value
        sample_state["mensagem"] = "Analyze my code"
        
        result = await retorna_resposta(sample_state)
        
        assert "revisar" in result["resposta"]
    
    async def test_retorna_resposta_depurar(self, sample_state):
        """Test response for DEPURAR intention."""
        sample_state["intencao"] = IntentionType.DEPURAR.value
        sample_state["mensagem"] = "Debug error"
        
        result = await retorna_resposta(sample_state)
        
        assert "depurar" in result["resposta"]
    
    async def test_retorna_resposta_unknown_intention(self, sample_state):
        """Test response for unknown intention."""
        sample_state["intencao"] = "UNKNOWN_INTENTION"
        sample_state["mensagem"] = "Test"
        
        result = await retorna_resposta(sample_state)
        
        assert "não reconhecida" in result["resposta"]
    
    async def test_retorna_resposta_with_rag_context(self, state_with_rag):
        """Test response generation with RAG context."""
        state_with_rag["intencao"] = IntentionType.CONVERSAR.value
        state_with_rag["target_llm"] = "ollama"
        
        with patch('app.ollama_service.processar_chat_com_ollama', new_callable=AsyncMock) as mock_ollama:
            
            mock_ollama.return_value = "Response with context"
            
            result = await retorna_resposta(state_with_rag)
            
            assert result["resposta"] == "Response with context"
            # Verify the RAG context was present
            assert len(state_with_rag["rag_context"]) > 0
    
    async def test_retorna_resposta_empty_rag_context(self, sample_state):
        """Test response with empty RAG context."""
        sample_state["intencao"] = IntentionType.CONVERSAR.value
        sample_state["rag_context"] = []
        sample_state["target_llm"] = "ollama"
        
        with patch('app.ollama_service.processar_chat_com_ollama', new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = "Response"
            
            result = await retorna_resposta(sample_state)
            
            assert result["resposta"] == "Response"
    
    async def test_retorna_resposta_save_memory(self, sample_state):
        """Test that conversation is saved to memory."""
        sample_state["intencao"] = IntentionType.CONVERSAR.value
        sample_state["use_memory"] = True
        sample_state["session_id"] = "session123"
        sample_state["target_llm"] = "ollama"
        sample_state["mensagem"] = "Hello"
        
        mock_memory = Mock()
        mock_memory.add_exchange = Mock()
        
        with patch('app.ollama_service.processar_chat_com_ollama') as mock_ollama, \
             patch('app.utils.conversation_memory.get_session_memory') as mock_get:
            
            mock_ollama.return_value = "Hi there"
            mock_get.return_value = mock_memory
            
            result = await retorna_resposta(sample_state)
            
            # Verify memory save was attempted
            mock_memory.add_exchange.assert_called_once_with("Hello", "Hi there")
    
    async def test_retorna_resposta_with_tracing_fragments(self, sample_state):
        """Test that tracing fragments are recorded."""
        sample_state["intencao"] = IntentionType.CONVERSAR.value
        sample_state["enable_tracing"] = True
        sample_state["trace_cell_id"] = "trace123"
        sample_state["conversation_id"] = "conv123"
        # Create mock document with page_content
        mock_doc = Mock()
        mock_doc.page_content = "test content"
        mock_doc.metadata = {"source": "test.pdf"}
        sample_state["rag_context"] = [mock_doc]
        sample_state["target_llm"] = "ollama"
        
        mock_trace_service = Mock()
        mock_trace_service.record_fragment = AsyncMock()
        
        with patch('app.ollama_service.processar_chat_com_ollama', new_callable=AsyncMock) as mock_ollama, \
             patch('app.services.conversation_trace_service.get_conversation_trace_service') as mock_get_trace, \
             patch('app.utils.input_processor.format_context_for_prompt') as mock_format:
            
            mock_ollama.return_value = "Response"
            mock_get_trace.return_value = mock_trace_service
            mock_format.return_value = "Formatted context"
            
            result = await retorna_resposta(sample_state)
            
            # Verify trace fragments were recorded
            assert mock_trace_service.record_fragment.called
            # Should record context_assembled, final_llm_call, and llm_response
            assert mock_trace_service.record_fragment.call_count >= 2
