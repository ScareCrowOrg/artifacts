"""
Unit tests for trace export utilities.

Tests cover:
- JSON export functionality
- Trace stage summarization
- Stage data extraction
- Trace comparison
- Error handling

Technical naming: All test functions in English.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock

from app.utils.trace_export import (
    export_trace_to_json,
    summarize_trace_stages,
    extract_stage_data,
    compare_traces
)
from app.models.content import Cell
from app.models.base import CellStatus


@pytest.fixture
def mock_trace_cell():
    """Create a mock trace cell with fragments."""
    trace = Mock(spec=Cell)
    trace.id = "trace_123"
    trace.assignee_id = "user_456"
    trace.notebook_item_type_id = "conversation-trace-item"
    trace.source_book_id = "book-conversation-traces-v1"
    trace.origemLivroId = "book-conversation-traces-v1"  # Match expected attribute name
    trace.status = CellStatus.PENDING
    trace.estado = CellStatus.PENDING  # Match expected attribute name
    trace.createdAt = datetime(2025, 11, 18, 10, 0, 0)
    
    trace.initial_data = {
        "conversation_id": "conv_abc123",
        "session_id": "sess_789",
        "tracing_enabled": True,
        "user_message": "How do I create a cell?",
        "target_llm": "openai",
        "created_at": "2025-11-18T10:00:00.000000"
    }
    
    trace.fragments = [
        {
            "timestamp": "2025-11-18T10:00:01.000000",
            "conversation_id": "conv_abc123",
            "stage": "initial_prompt",
            "data": {"user_message": "How do I create a cell?"}
        },
        {
            "timestamp": "2025-11-18T10:00:02.500000",
            "conversation_id": "conv_abc123",
            "stage": "rag_retrieval",
            "data": {"chunks_retrieved": 5, "query": "create cell"}
        },
        {
            "timestamp": "2025-11-18T10:00:03.000000",
            "conversation_id": "conv_abc123",
            "stage": "llm_response",
            "data": {"response": "To create a cell..."}
        }
    ]
    
    return trace


class TestExportTraceToJson:
    """Test suite for export_trace_to_json function."""
    
    def test_export_trace_pretty_print(self, mock_trace_cell):
        """Test JSON export with pretty printing."""
        json_str = export_trace_to_json(mock_trace_cell, pretty=True)
        
        # Parse JSON to verify it's valid
        data = json.loads(json_str)
        
        # Verify basic structure
        assert data["trace_id"] == "trace_123"
        assert data["conversation_id"] == "conv_abc123"
        assert data["session_id"] == "sess_789"
        assert data["user_message"] == "How do I create a cell?"
        assert data["target_llm"] == "openai"
        assert data["fragments_count"] == 3
        assert len(data["fragments"]) == 3
        
        # Verify pretty printing (should have newlines and indentation)
        assert "\n" in json_str
        assert "  " in json_str  # Indentation
    
    def test_export_trace_compact(self, mock_trace_cell):
        """Test JSON export without pretty printing."""
        json_str = export_trace_to_json(mock_trace_cell, pretty=False)
        
        # Parse JSON to verify it's valid
        data = json.loads(json_str)
        
        # Verify data is complete
        assert data["trace_id"] == "trace_123"
        assert data["fragments_count"] == 3
        
        # Verify compact format (minimal whitespace)
        # Pretty format would have many newlines, compact should have very few
        newline_count = json_str.count("\n")
        assert newline_count == 0  # Compact should have no newlines
    
    def test_export_trace_with_metadata(self, mock_trace_cell):
        """Test JSON export with metadata included."""
        json_str = export_trace_to_json(mock_trace_cell, include_metadata=True)
        data = json.loads(json_str)
        
        # Verify metadata is present
        assert "metadata" in data
        assert data["metadata"]["assignee_id"] == "user_456"
        assert data["metadata"]["notebook_item_type_id"] == "conversation-trace-item"
        assert data["metadata"]["origem_livro_id"] == "book-conversation-traces-v1"
        assert data["metadata"]["estado"] == CellStatus.PENDING
    
    def test_export_trace_without_metadata(self, mock_trace_cell):
        """Test JSON export with metadata excluded."""
        json_str = export_trace_to_json(mock_trace_cell, include_metadata=False)
        data = json.loads(json_str)
        
        # Verify metadata is not present
        assert "metadata" not in data
        
        # But basic data should still be present
        assert data["trace_id"] == "trace_123"
        assert data["conversation_id"] == "conv_abc123"
    
    def test_export_trace_fragments_preserved(self, mock_trace_cell):
        """Test that fragment data is fully preserved in export."""
        json_str = export_trace_to_json(mock_trace_cell)
        data = json.loads(json_str)
        
        # Verify fragments are complete
        fragments = data["fragments"]
        assert len(fragments) == 3
        
        # Check first fragment
        assert fragments[0]["stage"] == "initial_prompt"
        assert fragments[0]["data"]["user_message"] == "How do I create a cell?"
        
        # Check second fragment
        assert fragments[1]["stage"] == "rag_retrieval"
        assert fragments[1]["data"]["chunks_retrieved"] == 5
        
        # Check third fragment
        assert fragments[2]["stage"] == "llm_response"
        assert "response" in fragments[2]["data"]
    
    def test_export_trace_handles_datetime(self, mock_trace_cell):
        """Test that datetime objects are converted to ISO format."""
        json_str = export_trace_to_json(mock_trace_cell)
        data = json.loads(json_str)
        
        # Verify created_at is a string in ISO format
        assert isinstance(data["created_at"], str)
        assert "2025-11-18" in data["created_at"]
    
    def test_export_trace_empty_fragments(self):
        """Test export of trace with no fragments."""
        trace = Mock(spec=Cell)
        trace.id = "trace_empty"
        trace.assignee_id = "user_123"
        trace.notebook_item_type_id = "conversation-trace-item"
        trace.createdAt = datetime.utcnow()
        trace.initial_data = {
            "conversation_id": "conv_empty",
            "session_id": None,
            "user_message": "Test"
        }
        trace.fragments = []
        
        json_str = export_trace_to_json(trace)
        data = json.loads(json_str)
        
        assert data["fragments_count"] == 0
        assert data["fragments"] == []
    
    def test_export_trace_handles_missing_fields(self):
        """Test export handles traces with missing optional fields."""
        trace = Mock(spec=Cell)
        trace.id = "trace_minimal"
        trace.assignee_id = "user_123"
        trace.notebook_item_type_id = "conversation-trace-item"
        trace.createdAt = "2025-11-18T10:00:00"  # String instead of datetime
        trace.initial_data = {
            "conversation_id": "conv_minimal"
            # Missing session_id, user_message, target_llm
        }
        trace.fragments = []
        
        json_str = export_trace_to_json(trace, include_metadata=False)
        data = json.loads(json_str)
        
        # Should not raise error, should handle None values
        assert data["trace_id"] == "trace_minimal"
        assert data["session_id"] is None
        assert data["user_message"] is None
        assert data["target_llm"] is None
    
    def test_export_trace_error_handling(self):
        """Test error handling for invalid trace data."""
        invalid_trace = Mock()
        # Missing required attributes
        del invalid_trace.id
        
        with pytest.raises(ValueError) as exc_info:
            export_trace_to_json(invalid_trace)
        
        assert "Failed to export trace" in str(exc_info.value)


class TestSummarizeTraceStages:
    """Test suite for summarize_trace_stages function."""
    
    def test_summarize_stages_basic(self, mock_trace_cell):
        """Test basic stage summarization."""
        summary = summarize_trace_stages(mock_trace_cell)
        
        assert summary["conversation_id"] == "conv_abc123"
        assert summary["total_fragments"] == 3
        assert summary["stage_count"] == 3
        assert set(summary["stages_captured"]) == {
            "initial_prompt", "rag_retrieval", "llm_response"
        }
    
    def test_summarize_stages_details(self, mock_trace_cell):
        """Test stage detail information."""
        summary = summarize_trace_stages(mock_trace_cell)
        
        stage_details = summary["stage_details"]
        
        # Check initial_prompt stage
        assert "initial_prompt" in stage_details
        assert stage_details["initial_prompt"]["count"] == 1
        assert stage_details["initial_prompt"]["first_timestamp"] == "2025-11-18T10:00:01.000000"
        assert stage_details["initial_prompt"]["last_timestamp"] == "2025-11-18T10:00:01.000000"
        
        # Check rag_retrieval stage
        assert "rag_retrieval" in stage_details
        assert stage_details["rag_retrieval"]["count"] == 1
    
    def test_summarize_stages_duration_calculation(self, mock_trace_cell):
        """Test duration calculation from timestamps."""
        summary = summarize_trace_stages(mock_trace_cell)
        
        # Duration should be from first to last timestamp
        # First: 10:00:01.000, Last: 10:00:03.000 = 2000ms
        assert summary["duration_ms"] == 2000
        assert summary["first_timestamp"] is not None
        assert summary["last_timestamp"] is not None
    
    def test_summarize_stages_duplicate_stages(self):
        """Test summarization with duplicate stage names."""
        trace = Mock(spec=Cell)
        trace.id = "trace_dup"
        trace.initial_data = {"conversation_id": "conv_dup"}
        trace.fragments = [
            {
                "timestamp": "2025-11-18T10:00:01.000000",
                "stage": "rag_retrieval",
                "data": {"attempt": 1}
            },
            {
                "timestamp": "2025-11-18T10:00:02.000000",
                "stage": "rag_retrieval",
                "data": {"attempt": 2}
            },
            {
                "timestamp": "2025-11-18T10:00:03.000000",
                "stage": "rag_retrieval",
                "data": {"attempt": 3}
            }
        ]
        
        summary = summarize_trace_stages(trace)
        
        assert summary["total_fragments"] == 3
        assert summary["stage_count"] == 1  # Only one unique stage
        assert summary["stages_captured"] == ["rag_retrieval"]
        
        # Count should be 3 for the single stage
        assert summary["stage_details"]["rag_retrieval"]["count"] == 3
        assert summary["stage_details"]["rag_retrieval"]["first_timestamp"] == "2025-11-18T10:00:01.000000"
        assert summary["stage_details"]["rag_retrieval"]["last_timestamp"] == "2025-11-18T10:00:03.000000"
    
    def test_summarize_stages_empty_fragments(self):
        """Test summarization with no fragments."""
        trace = Mock(spec=Cell)
        trace.id = "trace_empty"
        trace.initial_data = {"conversation_id": "conv_empty"}
        trace.fragments = []
        
        summary = summarize_trace_stages(trace)
        
        assert summary["total_fragments"] == 0
        assert summary["stage_count"] == 0
        assert summary["stages_captured"] == []
        assert summary["duration_ms"] is None
    
    def test_summarize_stages_missing_timestamps(self):
        """Test summarization with missing timestamps."""
        trace = Mock(spec=Cell)
        trace.id = "trace_no_ts"
        trace.initial_data = {"conversation_id": "conv_no_ts"}
        trace.fragments = [
            {
                # No timestamp field
                "stage": "test_stage",
                "data": {}
            }
        ]
        
        summary = summarize_trace_stages(trace)
        
        # Should handle missing timestamps gracefully
        assert summary["total_fragments"] == 1
        assert summary["duration_ms"] is None
    
    def test_summarize_stages_invalid_timestamps(self):
        """Test summarization with invalid timestamp format."""
        trace = Mock(spec=Cell)
        trace.id = "trace_bad_ts"
        trace.initial_data = {"conversation_id": "conv_bad_ts"}
        trace.fragments = [
            {
                "timestamp": "not-a-valid-timestamp",
                "stage": "test_stage",
                "data": {}
            }
        ]
        
        summary = summarize_trace_stages(trace)
        
        # Should handle invalid timestamps gracefully
        assert summary["total_fragments"] == 1
        assert summary["duration_ms"] is None


class TestExtractStageData:
    """Test suite for extract_stage_data function."""
    
    def test_extract_stage_data_single_match(self, mock_trace_cell):
        """Test extracting data for a stage that appears once."""
        stage_data = extract_stage_data(mock_trace_cell, "rag_retrieval")
        
        assert len(stage_data) == 1
        assert stage_data[0]["timestamp"] == "2025-11-18T10:00:02.500000"
        assert stage_data[0]["conversation_id"] == "conv_abc123"
        assert stage_data[0]["data"]["chunks_retrieved"] == 5
        assert stage_data[0]["data"]["query"] == "create cell"
    
    def test_extract_stage_data_multiple_matches(self):
        """Test extracting data for a stage that appears multiple times."""
        trace = Mock(spec=Cell)
        trace.fragments = [
            {
                "timestamp": "2025-11-18T10:00:01.000000",
                "conversation_id": "conv_test",
                "stage": "rag_retrieval",
                "data": {"attempt": 1, "chunks": 3}
            },
            {
                "timestamp": "2025-11-18T10:00:02.000000",
                "conversation_id": "conv_test",
                "stage": "query_expansion",
                "data": {"expanded": "query"}
            },
            {
                "timestamp": "2025-11-18T10:00:03.000000",
                "conversation_id": "conv_test",
                "stage": "rag_retrieval",
                "data": {"attempt": 2, "chunks": 5}
            }
        ]
        
        stage_data = extract_stage_data(trace, "rag_retrieval")
        
        assert len(stage_data) == 2
        assert stage_data[0]["data"]["attempt"] == 1
        assert stage_data[0]["data"]["chunks"] == 3
        assert stage_data[1]["data"]["attempt"] == 2
        assert stage_data[1]["data"]["chunks"] == 5
    
    def test_extract_stage_data_no_match(self, mock_trace_cell):
        """Test extracting data for a stage that doesn't exist."""
        stage_data = extract_stage_data(mock_trace_cell, "nonexistent_stage")
        
        assert len(stage_data) == 0
        assert stage_data == []
    
    def test_extract_stage_data_empty_fragments(self):
        """Test extraction from trace with no fragments."""
        trace = Mock(spec=Cell)
        trace.fragments = []
        
        stage_data = extract_stage_data(trace, "any_stage")
        
        assert len(stage_data) == 0


class TestCompareTraces:
    """Test suite for compare_traces function."""
    
    def test_compare_traces_basic(self):
        """Test basic trace comparison."""
        trace1 = Mock(spec=Cell)
        trace1.id = "trace_1"
        trace1.initial_data = {"conversation_id": "conv_1"}
        trace1.fragments = [
            {"timestamp": "2025-11-18T10:00:01.000000", "stage": "initial_prompt", "data": {}},
            {"timestamp": "2025-11-18T10:00:02.000000", "stage": "rag_retrieval", "data": {}},
            {"timestamp": "2025-11-18T10:00:03.000000", "stage": "llm_response", "data": {}}
        ]
        
        trace2 = Mock(spec=Cell)
        trace2.id = "trace_2"
        trace2.initial_data = {"conversation_id": "conv_2"}
        trace2.fragments = [
            {"timestamp": "2025-11-18T10:00:01.000000", "stage": "initial_prompt", "data": {}},
            {"timestamp": "2025-11-18T10:00:03.000000", "stage": "llm_response", "data": {}},
            {"timestamp": "2025-11-18T10:00:04.000000", "stage": "error_handling", "data": {}}
        ]
        
        comparison = compare_traces(trace1, trace2)
        
        assert comparison["trace_1_id"] == "trace_1"
        assert comparison["trace_2_id"] == "trace_2"
        assert set(comparison["common_stages"]) == {"initial_prompt", "llm_response"}
        assert comparison["unique_to_trace_1"] == ["rag_retrieval"]
        assert comparison["unique_to_trace_2"] == ["error_handling"]
        assert comparison["trace_1_fragments"] == 3
        assert comparison["trace_2_fragments"] == 3
        assert comparison["fragment_count_diff"] == 0
    
    def test_compare_traces_different_fragment_counts(self):
        """Test comparison with different fragment counts."""
        trace1 = Mock(spec=Cell)
        trace1.id = "trace_1"
        trace1.initial_data = {"conversation_id": "conv_1"}
        trace1.fragments = [
            {"timestamp": "2025-11-18T10:00:01.000000", "stage": "stage_1", "data": {}},
            {"timestamp": "2025-11-18T10:00:02.000000", "stage": "stage_2", "data": {}}
        ]
        
        trace2 = Mock(spec=Cell)
        trace2.id = "trace_2"
        trace2.initial_data = {"conversation_id": "conv_2"}
        trace2.fragments = [
            {"timestamp": "2025-11-18T10:00:01.000000", "stage": "stage_1", "data": {}},
            {"timestamp": "2025-11-18T10:00:02.000000", "stage": "stage_2", "data": {}},
            {"timestamp": "2025-11-18T10:00:03.000000", "stage": "stage_3", "data": {}},
            {"timestamp": "2025-11-18T10:00:04.000000", "stage": "stage_4", "data": {}},
            {"timestamp": "2025-11-18T10:00:05.000000", "stage": "stage_5", "data": {}}
        ]
        
        comparison = compare_traces(trace1, trace2)
        
        assert comparison["fragment_count_diff"] == -3  # trace1 has 3 fewer fragments
        assert comparison["trace_1_fragments"] == 2
        assert comparison["trace_2_fragments"] == 5
    
    def test_compare_traces_with_duration(self):
        """Test comparison includes duration difference."""
        trace1 = Mock(spec=Cell)
        trace1.id = "trace_1"
        trace1.initial_data = {"conversation_id": "conv_1"}
        trace1.fragments = [
            {"timestamp": "2025-11-18T10:00:00.000000", "stage": "start", "data": {}},
            {"timestamp": "2025-11-18T10:00:02.000000", "stage": "end", "data": {}}
        ]
        
        trace2 = Mock(spec=Cell)
        trace2.id = "trace_2"
        trace2.initial_data = {"conversation_id": "conv_2"}
        trace2.fragments = [
            {"timestamp": "2025-11-18T10:00:00.000000", "stage": "start", "data": {}},
            {"timestamp": "2025-11-18T10:00:05.000000", "stage": "end", "data": {}}
        ]
        
        comparison = compare_traces(trace1, trace2)
        
        # trace1 duration: 2000ms, trace2 duration: 5000ms, diff: -3000ms
        assert comparison["duration_diff_ms"] == -3000
    
    def test_compare_traces_no_common_stages(self):
        """Test comparison when traces have no common stages."""
        trace1 = Mock(spec=Cell)
        trace1.id = "trace_1"
        trace1.initial_data = {"conversation_id": "conv_1"}
        trace1.fragments = [
            {"timestamp": "2025-11-18T10:00:01.000000", "stage": "stage_a", "data": {}}
        ]
        
        trace2 = Mock(spec=Cell)
        trace2.id = "trace_2"
        trace2.initial_data = {"conversation_id": "conv_2"}
        trace2.fragments = [
            {"timestamp": "2025-11-18T10:00:01.000000", "stage": "stage_b", "data": {}}
        ]
        
        comparison = compare_traces(trace1, trace2)
        
        assert comparison["common_stages"] == []
        assert comparison["unique_to_trace_1"] == ["stage_a"]
        assert comparison["unique_to_trace_2"] == ["stage_b"]
