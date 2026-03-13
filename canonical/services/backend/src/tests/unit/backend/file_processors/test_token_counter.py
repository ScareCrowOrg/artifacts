"""
Unit tests for app/file_processors/token_counter.py

Tests token counting functions for OpenAI API with tiktoken library
and fallback approximate counting.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestCountTokens:
    """Test count_tokens function."""
    
    def test_count_tokens_basic(self):
        """Test basic token counting."""
        from app.file_processors.token_counter import count_tokens
        
        # Test with actual tiktoken (it's installed)
        result = count_tokens("Hello, world!")
        
        # Should return a positive number
        assert result > 0
        assert isinstance(result, int)
    
    def test_count_tokens_unknown_model_fallback(self):
        """Test fallback to cl100k_base for unknown model."""
        from app.file_processors.token_counter import count_tokens
        
        # Use a model name that doesn't exist
        result = count_tokens("Test text", model="unknown-model-xyz-2024")
        
        # Should still return a valid count using fallback encoding
        assert result > 0
        assert isinstance(result, int)
    
    def test_count_tokens_tiktoken_import_error(self):
        """Test fallback when tiktoken is not available."""
        from app.file_processors.token_counter import count_tokens
        
        # Patch the import to raise ImportError
        with patch('builtins.__import__', side_effect=ImportError("tiktoken not installed")):
            text = "This is a test string with specific length"
            result = count_tokens(text)
            
            # Should use approximate counting (chars/4)
            expected = len(text) // 4
            assert result == expected
    
    def test_count_tokens_general_exception(self):
        """Test fallback on general exception during encoding."""
        from app.file_processors.token_counter import count_tokens
        import tiktoken
        
        # Save original function
        original_encoding_for_model = tiktoken.encoding_for_model
        
        try:
            # Replace with a function that raises an exception
            def mock_encoding(*args, **kwargs):
                raise Exception("Network error")
            
            tiktoken.encoding_for_model = mock_encoding
            
            text = "Test text for exception handling"
            result = count_tokens(text)
            
            # Should fallback to approximate
            expected = len(text) // 4
            assert result == expected
        finally:
            # Restore original function
            tiktoken.encoding_for_model = original_encoding_for_model
    
    def test_count_tokens_different_models(self):
        """Test token counting with different models."""
        from app.file_processors.token_counter import count_tokens
        
        text = "This is a test"
        result1 = count_tokens(text, model="gpt-3.5-turbo")
        result2 = count_tokens(text, model="gpt-4")
        
        # Both should return valid results
        assert result1 > 0
        assert result2 > 0
    
    def test_count_tokens_empty_string(self):
        """Test counting tokens in empty string."""
        from app.file_processors.token_counter import count_tokens
        
        result = count_tokens("")
        
        assert result == 0
    
    def test_count_tokens_long_text(self):
        """Test counting tokens in long text."""
        from app.file_processors.token_counter import count_tokens
        
        long_text = "word " * 1000
        result = count_tokens(long_text)
        
        # Should be roughly 1000 tokens (one per word plus spaces)
        assert result > 900
        assert result < 1500
    
    def test_count_tokens_special_characters(self):
        """Test counting tokens with special characters."""
        from app.file_processors.token_counter import count_tokens
        
        text = "Hello! How are you? I'm fine, thanks."
        result = count_tokens(text)
        
        assert result > 0
    
    def test_count_tokens_code(self):
        """Test counting tokens in code."""
        from app.file_processors.token_counter import count_tokens
        
        code = """
def hello():
    print("Hello, world!")
"""
        result = count_tokens(code)
        
        assert result > 0


class TestEstimateMessageTokens:
    """Test estimate_message_tokens function."""
    
    @patch('app.file_processors.token_counter.count_tokens')
    def test_estimate_single_message(self, mock_count):
        """Test estimating tokens for single message."""
        from app.file_processors.token_counter import estimate_message_tokens
        
        mock_count.side_effect = [10, 4]  # content: 10, role: 4
        
        messages = [{"role": "user", "content": "Hello"}]
        result = estimate_message_tokens(messages)
        
        # 4 (message overhead) + 10 (content) + 4 (role) + 3 (structure) = 21
        assert result == 21
    
    @patch('app.file_processors.token_counter.count_tokens')
    def test_estimate_multiple_messages(self, mock_count):
        """Test estimating tokens for multiple messages."""
        from app.file_processors.token_counter import estimate_message_tokens
        
        # Mock token counts for each message part
        mock_count.side_effect = [
            10, 4,  # First message: content, role
            20, 9   # Second message: content, role
        ]
        
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        result = estimate_message_tokens(messages)
        
        # 2 messages * (4 overhead) + tokens + 3 structure = 8 + 10 + 4 + 20 + 9 + 3 = 54
        assert result == 54
    
    @patch('app.file_processors.token_counter.count_tokens')
    def test_estimate_empty_messages(self, mock_count):
        """Test estimating tokens for empty message list."""
        from app.file_processors.token_counter import estimate_message_tokens
        
        messages = []
        result = estimate_message_tokens(messages)
        
        # Only structure overhead
        assert result == 3
    
    @patch('app.file_processors.token_counter.count_tokens')
    def test_estimate_message_missing_content(self, mock_count):
        """Test estimating tokens for message with missing content."""
        from app.file_processors.token_counter import estimate_message_tokens
        
        mock_count.side_effect = [0, 4]  # empty content, role
        
        messages = [{"role": "user"}]  # No content key
        result = estimate_message_tokens(messages)
        
        assert result > 0
        assert mock_count.call_count == 2


class TestCheckTokenLimit:
    """Test check_token_limit function."""
    
    @patch('app.file_processors.token_counter.count_tokens')
    def test_within_limit(self, mock_count):
        """Test text within token limit."""
        from app.file_processors.token_counter import check_token_limit
        
        mock_count.return_value = 500
        
        result = check_token_limit("test text", max_tokens=1000)
        
        assert result is True
    
    @patch('app.file_processors.token_counter.count_tokens')
    def test_exceeds_limit(self, mock_count):
        """Test text exceeding token limit."""
        from app.file_processors.token_counter import check_token_limit
        
        mock_count.return_value = 1500
        
        result = check_token_limit("test text", max_tokens=1000)
        
        assert result is False
    
    @patch('app.file_processors.token_counter.count_tokens')
    def test_exactly_at_limit(self, mock_count):
        """Test text exactly at token limit."""
        from app.file_processors.token_counter import check_token_limit
        
        mock_count.return_value = 1000
        
        result = check_token_limit("test text", max_tokens=1000)
        
        assert result is True
    
    @patch('app.file_processors.token_counter.count_tokens')
    def test_default_max_tokens(self, mock_count):
        """Test using default max tokens."""
        from app.file_processors.token_counter import check_token_limit, DEFAULT_MAX_TOKENS
        
        mock_count.return_value = 500
        
        result = check_token_limit("test text")
        
        # Should use DEFAULT_MAX_TOKENS
        mock_count.assert_called_once()
        assert result is True


class TestGetAvailableTokens:
    """Test get_available_tokens function."""
    
    @patch('app.file_processors.token_counter.estimate_message_tokens')
    def test_calculate_available_tokens(self, mock_estimate):
        """Test calculating available tokens."""
        from app.file_processors.token_counter import get_available_tokens, RESPONSE_BUFFER_TOKENS
        
        mock_estimate.return_value = 1000
        
        messages = [{"role": "user", "content": "Hello"}]
        result = get_available_tokens(messages, max_context=16000)
        
        # 16000 - 1000 - 2000 (buffer) = 13000
        expected = 16000 - 1000 - RESPONSE_BUFFER_TOKENS
        assert result == expected
    
    @patch('app.file_processors.token_counter.estimate_message_tokens')
    def test_available_tokens_with_custom_context(self, mock_estimate):
        """Test with custom context window."""
        from app.file_processors.token_counter import get_available_tokens, RESPONSE_BUFFER_TOKENS
        
        mock_estimate.return_value = 500
        
        messages = []
        result = get_available_tokens(messages, max_context=8000)
        
        expected = 8000 - 500 - RESPONSE_BUFFER_TOKENS
        assert result == expected
    
    @patch('app.file_processors.token_counter.estimate_message_tokens')
    def test_available_tokens_negative_becomes_zero(self, mock_estimate):
        """Test that negative available tokens becomes 0."""
        from app.file_processors.token_counter import get_available_tokens
        
        # Large message count that exceeds context
        mock_estimate.return_value = 20000
        
        messages = []
        result = get_available_tokens(messages, max_context=16000)
        
        # Should be 0, not negative
        assert result == 0
    
    @patch('app.file_processors.token_counter.estimate_message_tokens')
    def test_available_tokens_empty_conversation(self, mock_estimate):
        """Test with empty conversation."""
        from app.file_processors.token_counter import get_available_tokens, RESPONSE_BUFFER_TOKENS
        
        mock_estimate.return_value = 3  # Just structure overhead
        
        messages = []
        result = get_available_tokens(messages, max_context=16000)
        
        # Should have most of context available
        expected = 16000 - 3 - RESPONSE_BUFFER_TOKENS
        assert result == expected


class TestConstants:
    """Test module constants."""
    
    def test_default_constants_defined(self):
        """Test that required constants are defined."""
        from app.file_processors import token_counter
        
        assert hasattr(token_counter, 'DEFAULT_MAX_TOKENS')
        assert hasattr(token_counter, 'DEFAULT_MODEL_CONTEXT')
        assert hasattr(token_counter, 'RESPONSE_BUFFER_TOKENS')
        
        assert token_counter.DEFAULT_MAX_TOKENS > 0
        assert token_counter.DEFAULT_MODEL_CONTEXT > 0
        assert token_counter.RESPONSE_BUFFER_TOKENS > 0
    
    def test_constants_reasonable_values(self):
        """Test that constants have reasonable values."""
        from app.file_processors import token_counter
        
        # DEFAULT_MAX_TOKENS should be less than context
        assert token_counter.DEFAULT_MAX_TOKENS < token_counter.DEFAULT_MODEL_CONTEXT
        
        # Response buffer should be significant but not huge
        assert 1000 <= token_counter.RESPONSE_BUFFER_TOKENS <= 5000
