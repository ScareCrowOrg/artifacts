"""
Unit tests for ConversationTraceService.

Tests cover:
- Service initialization
- Conversation ID generation
- Trace cell creation
- Fragment recording
- Global enable/disable flag behavior
- Error handling

Technical naming: All test functions in English.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.services.conversation_trace_service import (
    ConversationTraceService,
    get_conversation_trace_service
)
from app.models.content import Cell


class TestConversationTraceServiceInit:
    """Test suite for service initialization."""
    
    def test_service_init_default_values(self):
        """Test that service initializes with correct default values."""
        service = ConversationTraceService()
        
        assert service.trace_book_id == "book-conversation-traces-v1"
        assert service.trace_type_id == "conversation-trace-item"
        assert isinstance(service._tracing_enabled, bool)
    
    @patch('app.services.conversation_trace_service.ENABLE_CONVERSATION_TRACING', True)
    def test_service_init_tracing_enabled(self):
        """Test service initialization when tracing is enabled."""
        service = ConversationTraceService()
        
        assert service.is_tracing_enabled() is True
    
    @patch('app.services.conversation_trace_service.ENABLE_CONVERSATION_TRACING', False)
    def test_service_init_tracing_disabled(self):
        """Test service initialization when tracing is disabled."""
        service = ConversationTraceService()
        
        assert service.is_tracing_enabled() is False


class TestConversationIDGeneration:
    """Test suite for conversation ID generation."""
    
    def test_generate_conversation_id_without_session(self):
        """Test conversation ID generation without session ID."""
        service = ConversationTraceService()
        
        conv_id = service.generate_conversation_id()
        
        assert conv_id.startswith("conv_")
        assert len(conv_id) > 5  # "conv_" + uuid
    
    def test_generate_conversation_id_with_session(self):
        """Test conversation ID generation with session ID."""
        service = ConversationTraceService()
        session_id = "sess_12345"
        
        conv_id = service.generate_conversation_id(session_id=session_id)
        
        assert conv_id.startswith("conv_")
        assert session_id in conv_id
        # Format is "conv_{session_id}_{short_uuid}"
        # Since session_id itself contains underscores, we can't rely on split count
        # Just verify the parts are present
        assert conv_id.count("_") >= 2
    
    def test_generate_conversation_id_uniqueness(self):
        """Test that generated conversation IDs are unique."""
        service = ConversationTraceService()
        
        conv_id_1 = service.generate_conversation_id()
        conv_id_2 = service.generate_conversation_id()
        
        assert conv_id_1 != conv_id_2
    
    def test_generate_conversation_id_with_session_uniqueness(self):
        """Test that IDs with same session are unique due to random suffix."""
        service = ConversationTraceService()
        session_id = "sess_12345"
        
        conv_id_1 = service.generate_conversation_id(session_id=session_id)
        conv_id_2 = service.generate_conversation_id(session_id=session_id)
        
        assert conv_id_1 != conv_id_2
        assert session_id in conv_id_1
        assert session_id in conv_id_2


class TestCreateTraceCell:
    """Test suite for trace cell creation."""
    
    @pytest.mark.asyncio
    @patch('app.services.conversation_trace_service.ENABLE_CONVERSATION_TRACING', True)
    @patch('app.services.conversation_trace_service.db')
    async def test_create_trace_cell_when_enabled(self, mock_db):
        """Test trace cell creation when tracing is enabled."""
        service = ConversationTraceService()
        mock_db.insert = Mock(return_value="cell_123")
        
        trace_cell = await service.create_trace_cell(
            conversation_id="conv_abc123",
            assignee_id="user_456",
            session_id="sess_789",
            user_message="Test message",
            target_llm="openai"
        )
        
        assert trace_cell is not None
        assert isinstance(trace_cell, Cell)
        assert trace_cell.assignee_id == "user_456"
        assert trace_cell.notebook_item_type_id == "conversation-trace-item"
        assert trace_cell.source_book_id == "book-conversation-traces-v1"
        assert trace_cell.initial_data["conversation_id"] == "conv_abc123"
        assert trace_cell.initial_data["session_id"] == "sess_789"
        assert trace_cell.initial_data["user_message"] == "Test message"
        assert trace_cell.initial_data["target_llm"] == "openai"
        assert trace_cell.initial_data["tracing_enabled"] is True
        assert trace_cell.fragments == []
        assert trace_cell.status == "pending"  # CellStatus.PENDING value
        
        # Verify db.insert was called
        mock_db.insert.assert_called_once()
        call_args = mock_db.insert.call_args
        assert call_args[0][0] == "cells"
        assert isinstance(call_args[0][1], Cell)
        assert call_args[1]["is_canonical"] is False
    
    @pytest.mark.asyncio
    @patch('app.services.conversation_trace_service.ENABLE_CONVERSATION_TRACING', False)
    @patch('app.services.conversation_trace_service.db')
    async def test_create_trace_cell_when_disabled(self, mock_db):
        """Test that trace cell is not created when tracing is disabled."""
        service = ConversationTraceService()
        
        trace_cell = await service.create_trace_cell(
            conversation_id="conv_abc123",
            assignee_id="user_456"
        )
        
        assert trace_cell is None
        mock_db.insert.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('app.services.conversation_trace_service.ENABLE_CONVERSATION_TRACING', True)
    @patch('app.services.conversation_trace_service.db')
    async def test_create_trace_cell_minimal_params(self, mock_db):
        """Test trace cell creation with only required parameters."""
        service = ConversationTraceService()
        mock_db.insert = Mock(return_value="cell_123")
        
        trace_cell = await service.create_trace_cell(
            conversation_id="conv_abc123",
            assignee_id="user_456"
        )
        
        assert trace_cell is not None
        assert trace_cell.initial_data["conversation_id"] == "conv_abc123"
        assert trace_cell.initial_data["session_id"] is None
        assert trace_cell.initial_data["user_message"] is None
        assert trace_cell.initial_data["target_llm"] is None
    
    @pytest.mark.asyncio
    @patch('app.services.conversation_trace_service.ENABLE_CONVERSATION_TRACING', True)
    @patch('app.services.conversation_trace_service.db')
    async def test_create_trace_cell_database_error(self, mock_db):
        """Test error handling when database insert fails."""
        service = ConversationTraceService()
        mock_db.insert = Mock(side_effect=Exception("Database error"))
        
        trace_cell = await service.create_trace_cell(
            conversation_id="conv_abc123",
            assignee_id="user_456"
        )
        
        assert trace_cell is None


class TestRecordFragment:
    """Test suite for fragment recording."""
    
    @pytest.mark.asyncio
    @patch('app.services.conversation_trace_service.ENABLE_CONVERSATION_TRACING', True)
    @patch('app.services.conversation_trace_service.db')
    async def test_record_fragment_success(self, mock_db):
        """Test successful fragment recording."""
        service = ConversationTraceService()
        
        # Create mock trace cell with existing fragments
        mock_trace_cell = Mock(spec=Cell)
        mock_trace_cell.id = "cell_123"
        mock_trace_cell.fragments = [
            {"timestamp": "2025-01-01T00:00:00", "stage": "initial_prompt", "data": {}}
        ]
        
        mock_db.find_one = Mock(return_value=mock_trace_cell)
        mock_db.update = Mock(return_value=True)
        
        stage_data = {
            "query": "test query",
            "chunks_retrieved": 5,
            "collections_used": ["scareverse_docs"]
        }
        
        success = await service.record_fragment(
            trace_cell_id="cell_123",
            stage="rag_retrieval",
            data=stage_data,
            conversation_id="conv_abc123"
        )
        
        assert success is True
        
        # Verify db.find_one was called correctly
        mock_db.find_one.assert_called_once_with(
            "cells", "cell_123", Cell, is_canonical=False
        )
        
        # Verify db.update was called with updated fragments
        mock_db.update.assert_called_once()
        update_call = mock_db.update.call_args
        assert update_call[0][0] == "cells"
        assert update_call[0][1] == "cell_123"
        
        # Check that new fragment was added
        updated_fragments = update_call[0][2]["fragments"]
        assert len(updated_fragments) == 2  # Original + new fragment
        
        # Verify new fragment structure
        new_fragment = updated_fragments[-1]
        assert "timestamp" in new_fragment
        assert new_fragment["conversation_id"] == "conv_abc123"
        assert new_fragment["stage"] == "rag_retrieval"
        assert new_fragment["data"] == stage_data
    
    @pytest.mark.asyncio
    @patch('app.services.conversation_trace_service.ENABLE_CONVERSATION_TRACING', False)
    @patch('app.services.conversation_trace_service.db')
    async def test_record_fragment_when_disabled(self, mock_db):
        """Test that fragment is not recorded when tracing is disabled."""
        service = ConversationTraceService()
        
        success = await service.record_fragment(
            trace_cell_id="cell_123",
            stage="rag_retrieval",
            data={"test": "data"},
            conversation_id="conv_abc123"
        )
        
        assert success is False
        mock_db.find_one.assert_not_called()
        mock_db.update.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('app.services.conversation_trace_service.ENABLE_CONVERSATION_TRACING', True)
    @patch('app.services.conversation_trace_service.db')
    async def test_record_fragment_cell_not_found(self, mock_db):
        """Test fragment recording when trace cell does not exist."""
        service = ConversationTraceService()
        mock_db.find_one = Mock(return_value=None)
        
        success = await service.record_fragment(
            trace_cell_id="nonexistent_cell",
            stage="rag_retrieval",
            data={"test": "data"},
            conversation_id="conv_abc123"
        )
        
        assert success is False
        mock_db.update.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('app.services.conversation_trace_service.ENABLE_CONVERSATION_TRACING', True)
    @patch('app.services.conversation_trace_service.db')
    async def test_record_fragment_database_error(self, mock_db):
        """Test error handling when database operations fail."""
        service = ConversationTraceService()
        mock_db.find_one = Mock(side_effect=Exception("Database error"))
        
        success = await service.record_fragment(
            trace_cell_id="cell_123",
            stage="rag_retrieval",
            data={"test": "data"},
            conversation_id="conv_abc123"
        )
        
        assert success is False
    
    @pytest.mark.asyncio
    @patch('app.services.conversation_trace_service.ENABLE_CONVERSATION_TRACING', True)
    @patch('app.services.conversation_trace_service.db')
    async def test_record_fragment_empty_data(self, mock_db):
        """Test fragment recording with empty data dict."""
        service = ConversationTraceService()
        
        mock_trace_cell = Mock(spec=Cell)
        mock_trace_cell.id = "cell_123"
        mock_trace_cell.fragments = []
        
        mock_db.find_one = Mock(return_value=mock_trace_cell)
        mock_db.update = Mock(return_value=True)
        
        success = await service.record_fragment(
            trace_cell_id="cell_123",
            stage="test_stage",
            data={},
            conversation_id="conv_abc123"
        )
        
        assert success is True
        
        # Verify fragment was added even with empty data
        update_call = mock_db.update.call_args
        updated_fragments = update_call[0][2]["fragments"]
        assert len(updated_fragments) == 1
        assert updated_fragments[0]["data"] == {}
    
    @pytest.mark.asyncio
    @patch('app.services.conversation_trace_service.ENABLE_CONVERSATION_TRACING', True)
    @patch('app.services.conversation_trace_service.db')
    async def test_record_fragment_complex_data(self, mock_db):
        """Test fragment recording with complex nested data structures."""
        service = ConversationTraceService()
        
        mock_trace_cell = Mock(spec=Cell)
        mock_trace_cell.id = "cell_123"
        mock_trace_cell.fragments = []
        
        mock_db.find_one = Mock(return_value=mock_trace_cell)
        mock_db.update = Mock(return_value=True)
        
        complex_data = {
            "query": "complex test",
            "chunks": [
                {"content": "chunk 1", "score": 0.95, "metadata": {"source": "doc1"}},
                {"content": "chunk 2", "score": 0.87, "metadata": {"source": "doc2"}}
            ],
            "processing_time_ms": 250,
            "collections": ["col1", "col2"]
        }
        
        success = await service.record_fragment(
            trace_cell_id="cell_123",
            stage="rag_retrieval",
            data=complex_data,
            conversation_id="conv_abc123"
        )
        
        assert success is True
        
        # Verify complex data was preserved
        update_call = mock_db.update.call_args
        updated_fragments = update_call[0][2]["fragments"]
        assert updated_fragments[0]["data"] == complex_data


class TestGetConversationTraceService:
    """Test suite for singleton service retrieval."""
    
    def test_get_conversation_trace_service_singleton(self):
        """Test that get_conversation_trace_service returns singleton instance."""
        service1 = get_conversation_trace_service()
        service2 = get_conversation_trace_service()
        
        assert service1 is service2
        assert isinstance(service1, ConversationTraceService)
    
    @patch('app.services.conversation_trace_service._trace_service', None)
    def test_get_conversation_trace_service_creates_instance(self):
        """Test that singleton is created on first call."""
        service = get_conversation_trace_service()
        
        assert service is not None
        assert isinstance(service, ConversationTraceService)


class TestIsTracingEnabled:
    """Test suite for tracing enabled checks."""
    
    @patch('app.services.conversation_trace_service.ENABLE_CONVERSATION_TRACING', True)
    def test_is_tracing_enabled_returns_true(self):
        """Test is_tracing_enabled returns True when config is enabled."""
        service = ConversationTraceService()
        
        assert service.is_tracing_enabled() is True
    
    @patch('app.services.conversation_trace_service.ENABLE_CONVERSATION_TRACING', False)
    def test_is_tracing_enabled_returns_false(self):
        """Test is_tracing_enabled returns False when config is disabled."""
        service = ConversationTraceService()
        
        assert service.is_tracing_enabled() is False
