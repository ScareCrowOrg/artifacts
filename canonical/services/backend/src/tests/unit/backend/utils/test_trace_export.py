"""
Unit tests for app/utils/trace_export.py

Tests export_trace_to_json, summarize_trace_stages, extract_stage_data,
and compare_traces functions for conversation trace analysis.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, MagicMock


# Skip all tests if langchain_community is not available
try:
    from app.utils import trace_export
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not LANGCHAIN_AVAILABLE,
    reason="langchain_community not available"
)


class TestExportTraceToJson:
    """Test export_trace_to_json function."""
    
    def test_export_basic_trace(self):
        """Test exporting basic trace to JSON."""
        from app.utils.trace_export import export_trace_to_json
        
        # Create mock trace cell with spec to prevent auto-creation of attributes
        trace_cell = Mock(spec=['id', 'initial_data', 'fragments', 'dataCriacao', 'assignee_id', 'notebook_item_type_id'])
        trace_cell.id = "trace_123"
        trace_cell.initial_data = {
            "conversation_id": "conv_456",
            "session_id": "session_789",
            "user_message": "Hello, AI!",
            "target_llm": "gpt-4",
            "tracing_enabled": True
        }
        trace_cell.fragments = [
            {"stage": "input", "data": {"message": "Hello"}, "timestamp": "2024-01-01T00:00:00Z"}
        ]
        trace_cell.dataCriacao = datetime(2024, 1, 1, 0, 0, 0)
        trace_cell.assignee_id = "user_1"
        trace_cell.notebook_item_type_id = "type_1"
        
        result = export_trace_to_json(trace_cell, pretty=False)
        
        assert isinstance(result, str)
        data = json.loads(result)
        assert data["trace_id"] == "trace_123"
        assert data["conversation_id"] == "conv_456"
        assert data["user_message"] == "Hello, AI!"
        assert data["fragments_count"] == 1
    
    def test_export_with_pretty_format(self):
        """Test exporting with pretty formatting."""
        from app.utils.trace_export import export_trace_to_json
        
        trace_cell = Mock(spec=['id', 'initial_data', 'fragments', 'dataCriacao', 'assignee_id', 'notebook_item_type_id'])
        trace_cell.id = "trace_123"
        trace_cell.initial_data = {"conversation_id": "conv_456"}
        trace_cell.fragments = []
        trace_cell.dataCriacao = datetime.now()
        trace_cell.assignee_id = "user_1"
        trace_cell.notebook_item_type_id = "type_1"
        
        result = export_trace_to_json(trace_cell, pretty=True)
        
        # Pretty format should have indentation
        assert "\n" in result
        assert "  " in result
    
    def test_export_without_metadata(self):
        """Test exporting without metadata."""
        from app.utils.trace_export import export_trace_to_json
        
        trace_cell = Mock(spec=['id', 'initial_data', 'fragments', 'dataCriacao'])
        trace_cell.id = "trace_123"
        trace_cell.initial_data = {"conversation_id": "conv_456"}
        trace_cell.fragments = []
        trace_cell.dataCriacao = datetime.now()
        
        result = export_trace_to_json(trace_cell, include_metadata=False)
        
        data = json.loads(result)
        assert "metadata" not in data
    
    def test_export_with_string_timestamp(self):
        """Test handling of string timestamps."""
        from app.utils.trace_export import export_trace_to_json
        
        trace_cell = Mock(spec=['id', 'initial_data', 'fragments', 'assignee_id', 'notebook_item_type_id'])
        trace_cell.id = "trace_123"
        trace_cell.initial_data = {"conversation_id": "conv_456", "created_at": "2024-01-01"}
        trace_cell.fragments = []
        trace_cell.assignee_id = "user_1"
        trace_cell.notebook_item_type_id = "type_1"
        # No dataCriacao attribute
        
        result = export_trace_to_json(trace_cell)
        
        data = json.loads(result)
        assert data["created_at"] == "2024-01-01"
    
    def test_export_error_handling(self):
        """Test error handling during export."""
        from app.utils.trace_export import export_trace_to_json
        
        # Create trace cell that will raise exception
        trace_cell = Mock()
        trace_cell.id = Mock()
        trace_cell.id.side_effect = Exception("Test error")
        
        with pytest.raises(ValueError, match="Failed to export trace"):
            export_trace_to_json(trace_cell)


class TestSummarizeTraceStages:
    """Test summarize_trace_stages function."""
    
    def test_summarize_basic_stages(self):
        """Test summarizing trace with basic stages."""
        from app.utils.trace_export import summarize_trace_stages
        
        trace_cell = Mock()
        trace_cell.initial_data = {"conversation_id": "conv_123"}
        trace_cell.fragments = [
            {"stage": "input", "timestamp": "2024-01-01T00:00:00Z", "data": {}},
            {"stage": "processing", "timestamp": "2024-01-01T00:00:01Z", "data": {}},
            {"stage": "output", "timestamp": "2024-01-01T00:00:02Z", "data": {}}
        ]
        
        result = summarize_trace_stages(trace_cell)
        
        assert result["total_fragments"] == 3
        assert result["stage_count"] == 3
        assert set(result["stages_captured"]) == {"input", "processing", "output"}
        assert result["conversation_id"] == "conv_123"
    
    def test_summarize_with_duration_calculation(self):
        """Test duration calculation from timestamps."""
        from app.utils.trace_export import summarize_trace_stages
        
        trace_cell = Mock()
        trace_cell.initial_data = {"conversation_id": "conv_123"}
        trace_cell.fragments = [
            {"stage": "input", "timestamp": "2024-01-01T00:00:00+00:00", "data": {}},
            {"stage": "output", "timestamp": "2024-01-01T00:00:05+00:00", "data": {}}
        ]
        
        result = summarize_trace_stages(trace_cell)
        
        assert result["duration_ms"] == 5000  # 5 seconds
        assert result["first_timestamp"] is not None
        assert result["last_timestamp"] is not None
    
    def test_summarize_multiple_same_stage(self):
        """Test handling of multiple fragments for same stage."""
        from app.utils.trace_export import summarize_trace_stages
        
        trace_cell = Mock()
        trace_cell.initial_data = {"conversation_id": "conv_123"}
        trace_cell.fragments = [
            {"stage": "retrieval", "timestamp": "2024-01-01T00:00:00Z", "data": {}},
            {"stage": "retrieval", "timestamp": "2024-01-01T00:00:01Z", "data": {}},
            {"stage": "retrieval", "timestamp": "2024-01-01T00:00:02Z", "data": {}}
        ]
        
        result = summarize_trace_stages(trace_cell)
        
        assert result["total_fragments"] == 3
        assert result["stage_count"] == 1
        assert result["stage_details"]["retrieval"]["count"] == 3
    
    def test_summarize_invalid_timestamps(self):
        """Test handling of invalid timestamps."""
        from app.utils.trace_export import summarize_trace_stages
        
        trace_cell = Mock()
        trace_cell.initial_data = {"conversation_id": "conv_123"}
        trace_cell.fragments = [
            {"stage": "input", "timestamp": "invalid", "data": {}},
            {"stage": "output", "timestamp": None, "data": {}}
        ]
        
        result = summarize_trace_stages(trace_cell)
        
        # Should not crash, duration should be None
        assert result["duration_ms"] is None
        assert result["total_fragments"] == 2
    
    def test_summarize_empty_fragments(self):
        """Test summarizing trace with no fragments."""
        from app.utils.trace_export import summarize_trace_stages
        
        trace_cell = Mock()
        trace_cell.initial_data = {"conversation_id": "conv_123"}
        trace_cell.fragments = []
        
        result = summarize_trace_stages(trace_cell)
        
        assert result["total_fragments"] == 0
        assert result["stage_count"] == 0
        assert result["stages_captured"] == []
    
    def test_summarize_error_handling(self):
        """Test error handling during summarization."""
        from app.utils.trace_export import summarize_trace_stages
        
        trace_cell = Mock()
        trace_cell.fragments = Mock()
        trace_cell.fragments.__iter__ = Mock(side_effect=Exception("Test error"))
        
        with pytest.raises(ValueError, match="Failed to summarize trace"):
            summarize_trace_stages(trace_cell)


class TestExtractStageData:
    """Test extract_stage_data function."""
    
    def test_extract_specific_stage(self):
        """Test extracting data for a specific stage."""
        from app.utils.trace_export import extract_stage_data
        
        trace_cell = Mock()
        trace_cell.fragments = [
            {"stage": "input", "timestamp": "2024-01-01T00:00:00Z", "conversation_id": "conv_1", "data": {"msg": "hello"}},
            {"stage": "rag_retrieval", "timestamp": "2024-01-01T00:00:01Z", "conversation_id": "conv_1", "data": {"chunks": 5}},
            {"stage": "output", "timestamp": "2024-01-01T00:00:02Z", "conversation_id": "conv_1", "data": {"response": "hi"}}
        ]
        
        result = extract_stage_data(trace_cell, "rag_retrieval")
        
        assert len(result) == 1
        assert result[0]["conversation_id"] == "conv_1"
        assert result[0]["data"]["chunks"] == 5
    
    def test_extract_multiple_fragments_same_stage(self):
        """Test extracting multiple fragments for same stage."""
        from app.utils.trace_export import extract_stage_data
        
        trace_cell = Mock()
        trace_cell.fragments = [
            {"stage": "retrieval", "timestamp": "2024-01-01T00:00:00Z", "conversation_id": "conv_1", "data": {"chunks": 3}},
            {"stage": "retrieval", "timestamp": "2024-01-01T00:00:01Z", "conversation_id": "conv_1", "data": {"chunks": 5}},
        ]
        
        result = extract_stage_data(trace_cell, "retrieval")
        
        assert len(result) == 2
        assert result[0]["data"]["chunks"] == 3
        assert result[1]["data"]["chunks"] == 5
    
    def test_extract_non_existent_stage(self):
        """Test extracting data for non-existent stage."""
        from app.utils.trace_export import extract_stage_data
        
        trace_cell = Mock()
        trace_cell.fragments = [
            {"stage": "input", "timestamp": "2024-01-01T00:00:00Z", "conversation_id": "conv_1", "data": {}}
        ]
        
        result = extract_stage_data(trace_cell, "non_existent")
        
        assert result == []
    
    def test_extract_error_handling(self):
        """Test error handling during extraction."""
        from app.utils.trace_export import extract_stage_data
        
        trace_cell = Mock()
        trace_cell.fragments = Mock()
        trace_cell.fragments.__iter__ = Mock(side_effect=Exception("Test error"))
        
        result = extract_stage_data(trace_cell, "any_stage")
        
        # Should return empty list on error
        assert result == []


class TestCompareTraces:
    """Test compare_traces function."""
    
    def test_compare_identical_stages(self):
        """Test comparing traces with identical stages."""
        from app.utils.trace_export import compare_traces
        
        trace1 = Mock()
        trace1.id = "trace_1"
        trace1.initial_data = {"conversation_id": "conv_1"}
        trace1.fragments = [
            {"stage": "input", "timestamp": "2024-01-01T00:00:00+00:00"},
            {"stage": "output", "timestamp": "2024-01-01T00:00:01+00:00"}
        ]
        
        trace2 = Mock()
        trace2.id = "trace_2"
        trace2.initial_data = {"conversation_id": "conv_2"}
        trace2.fragments = [
            {"stage": "input", "timestamp": "2024-01-01T00:00:00+00:00"},
            {"stage": "output", "timestamp": "2024-01-01T00:00:01+00:00"}
        ]
        
        result = compare_traces(trace1, trace2)
        
        assert set(result["common_stages"]) == {"input", "output"}
        assert result["unique_to_trace_1"] == []
        assert result["unique_to_trace_2"] == []
        assert result["fragment_count_diff"] == 0
    
    def test_compare_different_stages(self):
        """Test comparing traces with different stages."""
        from app.utils.trace_export import compare_traces
        
        trace1 = Mock()
        trace1.id = "trace_1"
        trace1.initial_data = {"conversation_id": "conv_1"}
        trace1.fragments = [
            {"stage": "input", "timestamp": "2024-01-01T00:00:00Z"},
            {"stage": "rag_retrieval", "timestamp": "2024-01-01T00:00:01Z"}
        ]
        
        trace2 = Mock()
        trace2.id = "trace_2"
        trace2.initial_data = {"conversation_id": "conv_2"}
        trace2.fragments = [
            {"stage": "input", "timestamp": "2024-01-01T00:00:00Z"},
            {"stage": "direct_response", "timestamp": "2024-01-01T00:00:01Z"}
        ]
        
        result = compare_traces(trace1, trace2)
        
        assert "input" in result["common_stages"]
        assert "rag_retrieval" in result["unique_to_trace_1"]
        assert "direct_response" in result["unique_to_trace_2"]
    
    def test_compare_different_fragment_counts(self):
        """Test comparing traces with different fragment counts."""
        from app.utils.trace_export import compare_traces
        
        trace1 = Mock()
        trace1.id = "trace_1"
        trace1.initial_data = {"conversation_id": "conv_1"}
        trace1.fragments = [
            {"stage": "input", "timestamp": "2024-01-01T00:00:00Z"},
            {"stage": "processing", "timestamp": "2024-01-01T00:00:01Z"},
            {"stage": "output", "timestamp": "2024-01-01T00:00:02Z"}
        ]
        
        trace2 = Mock()
        trace2.id = "trace_2"
        trace2.initial_data = {"conversation_id": "conv_2"}
        trace2.fragments = [
            {"stage": "input", "timestamp": "2024-01-01T00:00:00Z"}
        ]
        
        result = compare_traces(trace1, trace2)
        
        assert result["trace_1_fragments"] == 3
        assert result["trace_2_fragments"] == 1
        assert result["fragment_count_diff"] == 2
    
    def test_compare_with_duration_diff(self):
        """Test comparing traces with duration difference."""
        from app.utils.trace_export import compare_traces
        
        trace1 = Mock()
        trace1.id = "trace_1"
        trace1.initial_data = {"conversation_id": "conv_1"}
        trace1.fragments = [
            {"stage": "input", "timestamp": "2024-01-01T00:00:00+00:00"},
            {"stage": "output", "timestamp": "2024-01-01T00:00:05+00:00"}
        ]
        
        trace2 = Mock()
        trace2.id = "trace_2"
        trace2.initial_data = {"conversation_id": "conv_2"}
        trace2.fragments = [
            {"stage": "input", "timestamp": "2024-01-01T00:00:00+00:00"},
            {"stage": "output", "timestamp": "2024-01-01T00:00:02+00:00"}
        ]
        
        result = compare_traces(trace1, trace2)
        
        # trace1: 5000ms, trace2: 2000ms, diff: 3000ms
        assert result["duration_diff_ms"] == 3000
    
    def test_compare_error_handling(self):
        """Test error handling during comparison."""
        from app.utils.trace_export import compare_traces
        
        trace1 = Mock()
        trace1.fragments = Mock()
        trace1.fragments.__iter__ = Mock(side_effect=Exception("Test error"))
        
        trace2 = Mock()
        trace2.initial_data = {"conversation_id": "conv_2"}
        trace2.fragments = []
        
        with pytest.raises(ValueError, match="Failed to compare traces"):
            compare_traces(trace1, trace2)
