"""
Unit tests for app/file_processors/message_builder.py

Tests message building functions for constructing OpenAI message lists
with segmented file content while maintaining conversation context.
"""

import pytest
from unittest.mock import Mock, patch


class TestBuildSegmentedMessages:
    """Test build_segmented_messages function."""
    
    @patch('app.file_processors.message_builder.estimate_message_tokens')
    @patch('app.file_processors.message_builder.count_tokens')
    def test_build_single_segment(self, mock_count, mock_estimate):
        """Test building messages for single file segment."""
        from app.file_processors.message_builder import build_segmented_messages
        
        mock_estimate.return_value = 100
        mock_count.return_value = 50
        
        base_messages = [{"role": "user", "content": "Previous message"}]
        file_segments = [{
            "content": "file content",
            "tokens": 200,
            "metadata": {
                "file_name": "test.py",
                "segment_index": 0,
                "total_segments": 1
            }
        }]
        user_message = "Analyze this file"
        
        result = build_segmented_messages(base_messages, file_segments, user_message)
        
        assert len(result) == 1  # Single message group
        assert len(result[0]) == 2  # base_messages + new user message
        assert result[0][0] == base_messages[0]
        assert "Analyze this file" in result[0][1]["content"]
    
    @patch('app.file_processors.message_builder.estimate_message_tokens')
    @patch('app.file_processors.message_builder.count_tokens')
    def test_build_multiple_segments(self, mock_count, mock_estimate):
        """Test building messages for multiple segments."""
        from app.file_processors.message_builder import build_segmented_messages
        
        mock_estimate.return_value = 100
        mock_count.return_value = 50
        
        base_messages = []
        file_segments = [
            {"content": "seg1", "tokens": 5000, "metadata": {"file_name": "test.py", "segment_index": 0, "total_segments": 2}},
            {"content": "seg2", "tokens": 5000, "metadata": {"file_name": "test.py", "segment_index": 1, "total_segments": 2}}
        ]
        user_message = "Review"
        
        # With limited context, should create multiple groups
        result = build_segmented_messages(base_messages, file_segments, user_message, max_context_tokens=8000)
        
        # Each segment may be in its own group or combined
        assert len(result) >= 1
    
    @patch('app.file_processors.message_builder.estimate_message_tokens')
    @patch('app.file_processors.message_builder.count_tokens')
    def test_build_warning_limited_tokens(self, mock_count, mock_estimate):
        """Test warning when very limited tokens available."""
        from app.file_processors.message_builder import build_segmented_messages
        
        mock_estimate.return_value = 15000  # High base usage
        mock_count.return_value = 100
        
        base_messages = [{"role": "user", "content": "Long history"}] * 10
        file_segments = [{"content": "code", "tokens": 100, "metadata": {"file_name": "test.py", "segment_index": 0, "total_segments": 1}}]
        user_message = "Review"
        
        result = build_segmented_messages(base_messages, file_segments, user_message, max_context_tokens=16000)
        
        # Should still create message groups even with limited space
        assert len(result) >= 1


class TestFormatFileReference:
    """Test format_file_reference function."""
    
    def test_format_single_segment(self):
        """Test formatting reference for single segment."""
        from app.file_processors.message_builder import format_file_reference
        
        result = format_file_reference("test.py", 0, 1)
        
        assert result == "--- File: test.py ---"
    
    def test_format_multiple_segments(self):
        """Test formatting reference for multiple segments."""
        from app.file_processors.message_builder import format_file_reference
        
        result = format_file_reference("test.py", 1, 3)
        
        assert "Part 2/3" in result
        assert "test.py" in result
    
    def test_format_with_segment_name(self):
        """Test formatting reference with segment name."""
        from app.file_processors.message_builder import format_file_reference
        
        result = format_file_reference("test.py", 0, 3, "my_function")
        
        assert "Part 1/3" in result
        assert "Section: my_function" in result


class TestMergeSegmentResponses:
    """Test merge_segment_responses function."""
    
    def test_merge_single_response(self):
        """Test merging single response."""
        from app.file_processors.message_builder import merge_segment_responses
        
        responses = ["This is the analysis"]
        result = merge_segment_responses(responses)
        
        assert result == "This is the analysis"
    
    def test_merge_multiple_responses(self):
        """Test merging multiple responses."""
        from app.file_processors.message_builder import merge_segment_responses
        
        responses = ["Analysis of part 1", "Analysis of part 2"]
        result = merge_segment_responses(responses)
        
        assert "Segment 1" in result
        assert "Segment 2" in result
        assert "Analysis of part 1" in result
        assert "Analysis of part 2" in result
    
    def test_merge_empty_responses(self):
        """Test merging empty response list."""
        from app.file_processors.message_builder import merge_segment_responses
        
        result = merge_segment_responses([])
        
        assert "No responses" in result
    
    def test_merge_preserves_order(self):
        """Test that merge preserves response order."""
        from app.file_processors.message_builder import merge_segment_responses
        
        responses = ["First", "Second", "Third"]
        result = merge_segment_responses(responses)
        
        # Check order is preserved
        first_pos = result.find("First")
        second_pos = result.find("Second")
        third_pos = result.find("Third")
        
        assert first_pos < second_pos < third_pos


class TestCreateMessageListForSegments:
    """Test _create_message_list_for_segments internal function."""
    
    def test_create_with_single_segment(self):
        """Test creating message list with single segment."""
        from app.file_processors.message_builder import _create_message_list_for_segments
        
        base_messages = [{"role": "user", "content": "Hello"}]
        segments = [{
            "content": "code content",
            "metadata": {
                "file_name": "test.py",
                "segment_index": 0,
                "total_segments": 1
            }
        }]
        user_message = "Review this"
        
        result = _create_message_list_for_segments(base_messages, segments, user_message)
        
        assert len(result) == 2  # base + new message
        assert result[0] == base_messages[0]
        assert "Review this" in result[1]["content"]
        assert "test.py" in result[1]["content"]
    
    def test_create_with_multiple_segments(self):
        """Test creating message list with multiple segments."""
        from app.file_processors.message_builder import _create_message_list_for_segments
        
        base_messages = []
        segments = [
            {"content": "seg1", "metadata": {"file_name": "test.py", "segment_index": 0, "total_segments": 2, "segment_name": "func1"}},
            {"content": "seg2", "metadata": {"file_name": "test.py", "segment_index": 1, "total_segments": 2, "segment_name": "func2"}}
        ]
        user_message = "Analyze"
        
        result = _create_message_list_for_segments(base_messages, segments, user_message)
        
        assert len(result) == 1  # Just the user message with file content
        assert "Part 1/2" in result[0]["content"]
        assert "Part 2/2" in result[0]["content"]
        assert "func1" in result[0]["content"]
        assert "func2" in result[0]["content"]
