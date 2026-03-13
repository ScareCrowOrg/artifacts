"""
Unit tests for conversation tracing flag propagation.

Tests validate that the enable_tracing flag is properly:
1. Accepted in the chat request model
2. Propagated to the orchestrator
3. Included in the orchestrator state

Coverage: ProcessChatIntentRequest model, orchestrator state initialization
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestTracingFlagModel:
    """Test enable_tracing field in ProcessChatIntentRequest."""
    
    def test_enable_tracing_field_exists(self):
        """Test that enable_tracing field exists in request model."""
        from app.models.chat import ProcessChatIntentRequest
        
        # Create request with enable_tracing=True
        request = ProcessChatIntentRequest(
            purpose="Test message",
            assignee_id="user123",
            enable_tracing=True
        )
        
        assert hasattr(request, 'enable_tracing'), "enable_tracing field should exist"
        assert request.enable_tracing is True
    
    def test_enable_tracing_defaults_to_false(self):
        """Test that enable_tracing defaults to False when not provided."""
        from app.models.chat import ProcessChatIntentRequest
        
        # Create request without enable_tracing
        request = ProcessChatIntentRequest(
            purpose="Test message",
            assignee_id="user123"
        )
        
        assert request.enable_tracing is False, "enable_tracing should default to False"
    
    def test_enable_tracing_with_rag(self):
        """Test enable_tracing works alongside RAG settings."""
        from app.models.chat import ProcessChatIntentRequest
        
        request = ProcessChatIntentRequest(
            purpose="Test message with RAG",
            assignee_id="user123",
            use_rag=True,
            selected_collections=["test_collection"],
            enable_tracing=True
        )
        
        assert request.enable_tracing is True
        assert request.use_rag is True
        assert request.selected_collections == ["test_collection"]


class TestTracingFlagOrchestratorState:
    """Test enable_tracing in orchestrator state."""
    
    def test_orchestrator_state_has_tracing_fields(self):
        """Test that OrchestratorState TypedDict includes tracing fields."""
        from app.orchestrator.langgraph.langgraph_state import OrchestratorState
        
        # Check if the TypedDict has the required fields
        annotations = OrchestratorState.__annotations__
        
        assert 'enable_tracing' in annotations, "enable_tracing should be in OrchestratorState"
        assert 'conversation_id' in annotations, "conversation_id should be in OrchestratorState"
        assert 'trace_cell_id' in annotations, "trace_cell_id should be in OrchestratorState"
    
    @pytest.mark.asyncio
    async def test_orchestrator_process_accepts_enable_tracing(self):
        """Test that orchestrator.process() accepts enable_tracing parameter."""
        from app.orchestrator.langgraph import ChatOrchestrator
        
        orchestrator = ChatOrchestrator()
        
        # Mock the graph execution
        with patch.object(orchestrator.graph, 'ainvoke', new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.return_value = {
                "resposta_final": "Test response",
                "intencao": "conversar",
                "celula_criada": None,
                "acao_realizada": False
            }
            
            # Call process with enable_tracing=True
            result = await orchestrator.process(
                mensagem="Test message",
                responsavel_id="user123",
                modelo="mistral",
                enable_tracing=True
            )
            
            # Verify ainvoke was called
            mock_ainvoke.assert_called_once()
            
            # Get the state passed to ainvoke
            call_args = mock_ainvoke.call_args
            state = call_args[0][0]
            
            # Verify enable_tracing is in the state
            assert state["enable_tracing"] is True, "enable_tracing should be True in state"
            assert state["conversation_id"] is None, "conversation_id should be None initially"
            assert state["trace_cell_id"] is None, "trace_cell_id should be None initially"
    
    @pytest.mark.asyncio
    async def test_orchestrator_process_with_tracing_false(self):
        """Test orchestrator.process() with enable_tracing=False."""
        from app.orchestrator.langgraph import ChatOrchestrator
        
        orchestrator = ChatOrchestrator()
        
        with patch.object(orchestrator.graph, 'ainvoke', new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.return_value = {
                "resposta_final": "Test response",
                "intencao": "conversar",
                "celula_criada": None,
                "acao_realizada": False
            }
            
            # Call process with enable_tracing=False (explicit)
            result = await orchestrator.process(
                mensagem="Test message",
                responsavel_id="user123",
                modelo="mistral",
                enable_tracing=False
            )
            
            # Get the state passed to ainvoke
            call_args = mock_ainvoke.call_args
            state = call_args[0][0]
            
            # Verify enable_tracing is False in the state
            assert state["enable_tracing"] is False, "enable_tracing should be False in state"
    
    @pytest.mark.asyncio
    async def test_orchestrator_process_tracing_default(self):
        """Test orchestrator.process() with enable_tracing default value."""
        from app.orchestrator.langgraph import ChatOrchestrator
        
        orchestrator = ChatOrchestrator()
        
        with patch.object(orchestrator.graph, 'ainvoke', new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.return_value = {
                "resposta_final": "Test response",
                "intencao": "conversar",
                "celula_criada": None,
                "acao_realizada": False
            }
            
            # Call process without enable_tracing (should default to False)
            result = await orchestrator.process(
                mensagem="Test message",
                responsavel_id="user123",
                modelo="mistral"
            )
            
            # Get the state passed to ainvoke
            call_args = mock_ainvoke.call_args
            state = call_args[0][0]
            
            # Verify enable_tracing defaults to False
            assert state["enable_tracing"] is False, "enable_tracing should default to False"


class TestTracingFlagIntegration:
    """Integration tests for tracing flag through the full chain."""
    
    @pytest.mark.asyncio
    async def test_tracing_flag_full_chain(self):
        """Test enable_tracing propagates from request to orchestrator to state."""
        from app.models.chat import ProcessChatIntentRequest
        from app.orchestrator.langgraph import ChatOrchestrator
        
        # Create request with enable_tracing=True
        request = ProcessChatIntentRequest(
            purpose="Test tracing propagation",
            assignee_id="user123",
            enable_tracing=True
        )
        
        # Verify request has enable_tracing=True
        assert request.enable_tracing is True
        
        # Create orchestrator and mock graph
        orchestrator = ChatOrchestrator()
        
        with patch.object(orchestrator.graph, 'ainvoke', new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.return_value = {
                "resposta_final": "Test response",
                "intencao": "conversar",
                "celula_criada": None,
                "acao_realizada": False
            }
            
            # Call orchestrator.process with the flag
            result = await orchestrator.process(
                mensagem=request.purpose,
                responsavel_id=request.assignee_id,
                modelo="mistral",
                enable_tracing=request.enable_tracing
            )
            
            # Verify the flag was passed to the state
            call_args = mock_ainvoke.call_args
            state = call_args[0][0]
            
            assert state["enable_tracing"] is True, "enable_tracing should propagate to orchestrator state"
