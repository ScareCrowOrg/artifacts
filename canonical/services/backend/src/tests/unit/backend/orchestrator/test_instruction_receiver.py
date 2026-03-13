"""
Unit tests for instruction_receiver.py

Tests the instruction receiver node which:
- Initializes state fields
- Loads conversation memory
- Processes attached files
- Retrieves RAG context
- Initializes conversation tracing

Target coverage: 90%+
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from app.orchestrator.langgraph.instruction_receiver import (
    recebe_instrucao,
    _initialize_state_fields,
    _load_conversation_memory,
    _retrieve_rag_context
)
from app.orchestrator.langgraph.langgraph_state import OrchestratorState


class TestInitializeStateFields:
    """Test state field initialization."""
    
    def test_initialize_basic_fields(self, sample_state):
        """Test that basic fields are initialized with defaults."""
        # Remove some fields to test initialization
        minimal_state = {
            "mensagem": "test",
            "historico": [],
            "responsavel_id": "user123",
            "model": "ollama"
        }
        
        result = _initialize_state_fields(minimal_state)
        
        assert result["acao_realizada"] is False
        assert result["resultado_acao"] is None
        assert result["celula_criada"] is None
        assert result["document_paths"] is None
        assert result["enable_function_calling"] is False
        assert result["attached_files"] is None
        assert result["attached_files_metadata"] is None
        assert result["rag_context"] is None
        assert result["use_rag"] is False
        assert result["session_id"] is None
        assert result["use_memory"] is False
    
    def test_initialize_chat_history_fields(self):
        """Test chat history management fields initialization."""
        state = {"mensagem": "test"}
        
        result = _initialize_state_fields(state)
        
        assert result["current_chat_summary"] is None
        assert result["recent_chat_history"] == []
        assert result["turns_since_last_summary"] == 0
        assert "summary_threshold_turns" in result
        assert "summary_threshold_tokens" in result
    
    def test_initialize_tracing_fields(self):
        """Test conversation tracing fields initialization."""
        state = {"mensagem": "test"}
        
        result = _initialize_state_fields(state)
        
        assert result["enable_tracing"] is False
        assert result["conversation_id"] is None
        assert result["trace_cell_id"] is None
    
    def test_preserve_existing_fields(self, sample_state):
        """Test that existing fields are not overwritten."""
        sample_state["acao_realizada"] = True
        sample_state["use_rag"] = True
        sample_state["session_id"] = "existing_session"
        
        result = _initialize_state_fields(sample_state)
        
        assert result["acao_realizada"] is True
        assert result["use_rag"] is True
        assert result["session_id"] == "existing_session"


class TestLoadConversationMemory:
    """Test conversation memory loading."""
    
    def test_load_memory_success(self, sample_state):
        """Test successful memory loading."""
        sample_state["use_memory"] = True
        sample_state["session_id"] = "session123"
        
        mock_memory = Mock()
        mock_memory.get_history_as_dicts = Mock(return_value=[
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"}
        ])
        
        with patch('app.utils.conversation_memory.get_session_memory') as mock_get:
            mock_get.return_value = mock_memory
            
            result = _load_conversation_memory(sample_state)
            
            assert len(result["historico"]) == 2
            assert result["historico"][0]["content"] == "Previous message"
            mock_get.assert_called_once_with("session123")
    
    def test_load_memory_no_session_id(self, sample_state):
        """Test memory loading when session_id is None."""
        sample_state["use_memory"] = True
        sample_state["session_id"] = None
        
        # Should not crash, just return state unchanged
        result = _load_conversation_memory(sample_state)
        
        assert result == sample_state
    
    def test_load_memory_with_existing_history(self, sample_state):
        """Test that existing history is preserved."""
        sample_state["use_memory"] = True
        sample_state["session_id"] = "session123"
        sample_state["historico"] = [{"role": "user", "content": "Existing"}]
        
        mock_memory = Mock()
        mock_memory.get_history_as_dicts = Mock(return_value=[
            {"role": "user", "content": "Loaded"}
        ])
        
        with patch('app.utils.conversation_memory.get_session_memory') as mock_get:
            mock_get.return_value = mock_memory
            
            result = _load_conversation_memory(sample_state)
            
            # Existing history should be preserved
            assert result["historico"][0]["content"] == "Existing"
    
    def test_load_memory_error_handling(self, sample_state):
        """Test error handling in memory loading."""
        sample_state["use_memory"] = True
        sample_state["session_id"] = "session123"
        
        with patch('app.utils.conversation_memory.get_session_memory') as mock_get:
            mock_get.side_effect = Exception("Memory error")
            
            # Should not raise, just continue
            result = _load_conversation_memory(sample_state)
            
            assert result is not None


class TestRetrieveRagContext:
    """Test RAG context retrieval."""
    
    @pytest.mark.asyncio
    async def test_retrieve_rag_context_success(self, sample_state, mock_rag_service):
        """Test successful RAG context retrieval."""
        sample_state["mensagem"] = "What is LangGraph?"
        sample_state["use_rag"] = True
        
        mock_rag_service.retrieve_context = Mock(return_value=[
            {"content": "LangGraph info", "metadata": {"source": "doc.pdf"}}
        ])
        
        with patch('app.utils.input_processor.extract_file_references') as mock_extract, \
             patch('app.utils.input_processor.remove_file_references') as mock_remove:
            
            mock_extract.return_value = []
            mock_remove.return_value = "What is LangGraph?"
            
            result = await _retrieve_rag_context(sample_state, mock_rag_service)
            
            assert result["rag_context"] is not None
            assert len(result["rag_context"]) > 0
    
    @pytest.mark.asyncio
    async def test_retrieve_rag_context_with_file_references(self, sample_state, mock_rag_service):
        """Test RAG context retrieval with file references in message."""
        sample_state["mensagem"] = "Show me #docs/README.md"
        sample_state["use_rag"] = True
        
        with patch('app.utils.input_processor.extract_file_references') as mock_extract, \
             patch('app.utils.input_processor.process_file_references') as mock_process, \
             patch('app.utils.input_processor.remove_file_references') as mock_remove:
            
            mock_extract.return_value = ["docs/README.md"]
            mock_process.return_value = [{"content": "README content", "metadata": {"path": "docs/README.md"}}]
            mock_remove.return_value = "Show me"
            mock_rag_service.retrieve_context = Mock(return_value=[])
            
            result = await _retrieve_rag_context(sample_state, mock_rag_service)
            
            assert result["rag_context"] is not None
    
    def test_retrieve_rag_context_error_handling(self, sample_state):
        """Test error handling in RAG context retrieval."""
        sample_state["mensagem"] = "Test query"
        
        mock_rag = Mock()
        mock_rag.retrieve_context = Mock(side_effect=Exception("RAG error"))
        
        with patch('app.utils.input_processor.extract_file_references') as mock_extract:
            mock_extract.return_value = []
            
            # Should not raise, just set empty context
            result = _retrieve_rag_context(sample_state, mock_rag)
            
            assert result is not None


@pytest.mark.asyncio
class TestRecebeInstrucao:
    """Test the main recebe_instrucao node function."""
    
    async def test_recebe_instrucao_basic(self, sample_state):
        """Test basic instruction reception without RAG or memory."""
        sample_state["use_rag"] = False
        sample_state["use_memory"] = False
        sample_state["attached_files"] = None
        sample_state["enable_tracing"] = False
        
        result = await recebe_instrucao(sample_state, rag_service=None)
        
        assert result is not None
        assert result["mensagem"] == sample_state["mensagem"]
        assert "acao_realizada" in result
        assert "resultado_acao" in result
    
    async def test_recebe_instrucao_with_rag(self, sample_state, mock_rag_service):
        """Test instruction reception with RAG enabled."""
        sample_state["use_rag"] = True
        sample_state["mensagem"] = "What is ScareVerse?"
        
        mock_rag_service.retrieve_context = Mock(return_value=[
            {"content": "ScareVerse info", "metadata": {"source": "docs.pdf"}}
        ])
        
        with patch('app.utils.input_processor.extract_file_references') as mock_extract, \
             patch('app.utils.input_processor.remove_file_references') as mock_remove:
            
            mock_extract.return_value = []
            mock_remove.return_value = "What is ScareVerse?"
            
            result = await recebe_instrucao(sample_state, rag_service=mock_rag_service)
            
            assert result["use_rag"] is True
            # RAG context should be set
            assert result.get("rag_context") is not None
    
    async def test_recebe_instrucao_with_memory(self, sample_state):
        """Test instruction reception with memory enabled."""
        sample_state["use_memory"] = True
        sample_state["session_id"] = "session123"
        
        mock_memory = Mock()
        mock_memory.get_history_as_dicts = Mock(return_value=[
            {"role": "user", "content": "Previous message"}
        ])
        
        with patch('app.utils.conversation_memory.get_session_memory') as mock_get:
            mock_get.return_value = mock_memory
            
            result = await recebe_instrucao(sample_state, rag_service=None)
            
            assert result["use_memory"] is True
            assert len(result["historico"]) > 0
    
    async def test_recebe_instrucao_with_attached_files(self, state_with_files):
        """Test instruction reception with attached files."""
        with patch('app.orchestrator.langgraph.file_processor.process_attached_files') as mock_process:
            mock_process.return_value = state_with_files
            
            result = await recebe_instrucao(state_with_files, rag_service=None)
            
            assert result is not None
            assert result["attached_files"] is not None
    
    async def test_recebe_instrucao_with_tracing(self, sample_state):
        """Test instruction reception with tracing enabled."""
        sample_state["enable_tracing"] = True
        sample_state["responsavel_id"] = "user123"
        
        mock_trace_service = Mock()
        mock_trace_service.is_tracing_enabled = Mock(return_value=True)
        mock_trace_service.generate_conversation_id = Mock(return_value="conv123")
        
        mock_trace_cell = Mock()
        mock_trace_cell.id = "trace_cell_123"
        mock_trace_service.create_trace_cell = AsyncMock(return_value=mock_trace_cell)
        mock_trace_service.record_fragment = AsyncMock()
        
        with patch('app.services.conversation_trace_service.get_conversation_trace_service') as mock_get:
            mock_get.return_value = mock_trace_service
            
            result = await recebe_instrucao(sample_state, rag_service=None)
            
            assert result["enable_tracing"] is True
            assert result.get("conversation_id") is not None
    
    async def test_recebe_instrucao_rag_disabled_warning(self, sample_state):
        """Test that RAG is skipped when use_rag is False."""
        sample_state["use_rag"] = False
        
        result = await recebe_instrucao(sample_state, rag_service=None)
        
        # RAG context should remain None when RAG is disabled
        assert result.get("rag_context") is None
    
    async def test_recebe_instrucao_rag_service_none_warning(self, sample_state):
        """Test warning when RAG is enabled but service is None."""
        sample_state["use_rag"] = True
        
        result = await recebe_instrucao(sample_state, rag_service=None)
        
        # Should handle gracefully even without RAG service
        assert result is not None
    
    async def test_recebe_instrucao_all_features(self, sample_state, mock_rag_service):
        """Test instruction reception with all features enabled."""
        sample_state["use_rag"] = True
        sample_state["use_memory"] = True
        sample_state["session_id"] = "session123"
        sample_state["enable_tracing"] = True
        sample_state["attached_files"] = [{"path": "/tmp/test.txt", "type": "text/plain"}]
        
        mock_memory = Mock()
        mock_memory.get_history_as_dicts = Mock(return_value=[])
        
        mock_trace_service = Mock()
        mock_trace_service.is_tracing_enabled = Mock(return_value=True)
        mock_trace_service.generate_conversation_id = Mock(return_value="conv123")
        mock_trace_cell = Mock()
        mock_trace_cell.id = "trace123"
        mock_trace_service.create_trace_cell = AsyncMock(return_value=mock_trace_cell)
        mock_trace_service.record_fragment = AsyncMock()
        
        with patch('app.utils.conversation_memory.get_session_memory') as mock_get_mem, \
             patch('app.services.conversation_trace_service.get_conversation_trace_service') as mock_get_trace, \
             patch('app.orchestrator.langgraph.file_processor.process_attached_files') as mock_process, \
             patch('app.utils.input_processor.extract_file_references') as mock_extract, \
             patch('app.utils.input_processor.remove_file_references') as mock_remove:
            
            mock_get_mem.return_value = mock_memory
            mock_get_trace.return_value = mock_trace_service
            mock_process.return_value = sample_state
            mock_extract.return_value = []
            mock_remove.return_value = sample_state["mensagem"]
            mock_rag_service.retrieve_context = Mock(return_value=[])
            
            result = await recebe_instrucao(sample_state, rag_service=mock_rag_service)
            
            assert result is not None
            assert result["use_rag"] is True
            assert result["use_memory"] is True
            assert result["enable_tracing"] is True
