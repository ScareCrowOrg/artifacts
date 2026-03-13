"""
Unit tests for history_manager.py

Tests the chat history management node which:
- Updates recent chat history with latest exchange
- Checks if summarization threshold is reached
- Invokes LLM to generate summary when needed
- Resets counters after summarization

Target coverage: 90%+
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.orchestrator.langgraph.history_manager import (
    manage_chat_history,
    _generate_summary
)


class TestGenerateSummary:
    """Test summary generation with Ollama."""
    
    def test_generate_summary_success(self):
        """Test successful summary generation."""
        with patch('app.ollama_service.processar_chat_com_ollama', new_callable=AsyncMock) as mock_ollama, \
             patch('asyncio.get_event_loop') as mock_loop:
            
            # Create a mock event loop
            mock_event_loop = Mock()
            mock_loop.return_value = mock_event_loop
            mock_event_loop.run_until_complete.return_value = "Summary of the conversation..."
            
            summary = _generate_summary("Summarize this conversation...")
            
            assert summary == "Summary of the conversation..."
    
    def test_generate_summary_error(self):
        """Test summary generation error handling."""
        with patch('app.ollama_service.processar_chat_com_ollama', new_callable=AsyncMock) as mock_ollama, \
             patch('asyncio.get_event_loop') as mock_loop:
            
            mock_event_loop = Mock()
            mock_loop.return_value = mock_event_loop
            mock_event_loop.run_until_complete.side_effect = Exception("Ollama error")
            
            summary = _generate_summary("Test prompt")
            
            assert summary is None


class TestManageChatHistory:
    """Test chat history management node."""
    
    def test_manage_history_no_summarization(self, state_with_history):
        """Test history management without triggering summarization."""
        state_with_history["resposta_final"] = "This is my response"
        state_with_history["turns_since_last_summary"] = 2
        state_with_history["summary_threshold_turns"] = 10
        
        with patch('app.utils.conversation_memory.update_history') as mock_update, \
             patch('app.utils.conversation_memory.should_summarize') as mock_should:
            
            mock_update.return_value = state_with_history
            mock_should.return_value = False
            
            result = manage_chat_history(state_with_history)
            
            assert result is not None
            mock_update.assert_called_once()
            mock_should.assert_called_once()
    
    def test_manage_history_with_summarization(self, state_with_history):
        """Test history management triggering summarization."""
        state_with_history["resposta_final"] = "Response"
        state_with_history["turns_since_last_summary"] = 10
        state_with_history["summary_threshold_turns"] = 5
        state_with_history["recent_chat_history"] = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"}
        ]
        
        with patch('app.utils.conversation_memory.update_history') as mock_update, \
             patch('app.utils.conversation_memory.should_summarize') as mock_should, \
             patch('app.utils.conversation_memory.build_summarization_prompt') as mock_build, \
             patch('app.utils.conversation_memory.reset_after_summarization') as mock_reset, \
             patch('app.orchestrator.langgraph.history_manager._generate_summary') as mock_gen:
            
            mock_update.return_value = state_with_history
            mock_should.return_value = True
            mock_build.return_value = "Summarize: ..."
            mock_gen.return_value = "New summary of the conversation"
            mock_reset.return_value = state_with_history
            
            result = manage_chat_history(state_with_history)
            
            assert result["current_chat_summary"] == "New summary of the conversation"
            mock_gen.assert_called_once()
            mock_reset.assert_called_once()
    
    def test_manage_history_summarization_failed(self, state_with_history):
        """Test history management when summarization fails."""
        state_with_history["resposta_final"] = "Response"
        state_with_history["turns_since_last_summary"] = 10
        
        with patch('app.utils.conversation_memory.update_history') as mock_update, \
             patch('app.utils.conversation_memory.should_summarize') as mock_should, \
             patch('app.utils.conversation_memory.build_summarization_prompt') as mock_build, \
             patch('app.orchestrator.langgraph.history_manager._generate_summary') as mock_gen:
            
            mock_update.return_value = state_with_history
            mock_should.return_value = True
            mock_build.return_value = "Summarize: ..."
            mock_gen.return_value = None  # Summarization failed
            
            result = manage_chat_history(state_with_history)
            
            # Should continue without error
            assert result is not None
    
    def test_manage_history_summarization_error(self, state_with_history):
        """Test history management with summarization error."""
        state_with_history["resposta_final"] = "Response"
        
        with patch('app.utils.conversation_memory.update_history') as mock_update, \
             patch('app.utils.conversation_memory.should_summarize') as mock_should, \
             patch('app.utils.conversation_memory.build_summarization_prompt') as mock_build:
            
            mock_update.return_value = state_with_history
            mock_should.return_value = True
            mock_build.side_effect = Exception("Build error")
            
            # Should not raise, just continue
            result = manage_chat_history(state_with_history)
            
            assert result is not None
    
    def test_manage_history_basic_state(self, sample_state):
        """Test history management with minimal state."""
        sample_state["mensagem"] = "Hello"
        sample_state["resposta_final"] = "Hi there"
        sample_state["turns_since_last_summary"] = 0
        
        with patch('app.utils.conversation_memory.update_history') as mock_update, \
             patch('app.utils.conversation_memory.should_summarize') as mock_should:
            
            mock_update.return_value = sample_state
            mock_should.return_value = False
            
            result = manage_chat_history(sample_state)
            
            assert result is not None
            # Verify update_history was called with correct params
            call_args = mock_update.call_args
            assert call_args[1]["user_msg"] == "Hello"
            assert call_args[1]["agent_response"] == "Hi there"
            assert call_args[1]["max_recent_turns"] == 5
    
    def test_manage_history_with_existing_summary(self, state_with_history):
        """Test history management with existing summary."""
        state_with_history["resposta_final"] = "Response"
        state_with_history["current_chat_summary"] = "Previous summary..."
        state_with_history["turns_since_last_summary"] = 10
        
        with patch('app.utils.conversation_memory.update_history') as mock_update, \
             patch('app.utils.conversation_memory.should_summarize') as mock_should, \
             patch('app.utils.conversation_memory.build_summarization_prompt') as mock_build, \
             patch('app.utils.conversation_memory.reset_after_summarization') as mock_reset, \
             patch('app.orchestrator.langgraph.history_manager._generate_summary') as mock_gen:
            
            mock_update.return_value = state_with_history
            mock_should.return_value = True
            mock_build.return_value = "Update summary: ..."
            mock_gen.return_value = "Updated summary"
            mock_reset.return_value = state_with_history
            
            result = manage_chat_history(state_with_history)
            
            # Verify build_summarization_prompt was called with current summary
            call_args = mock_build.call_args
            assert call_args[1]["current_summary"] == "Previous summary..."
    
    def test_manage_history_token_threshold(self, state_with_history):
        """Test that token threshold is passed to should_summarize."""
        state_with_history["resposta_final"] = "Response"
        state_with_history["summary_threshold_turns"] = 10
        state_with_history["summary_threshold_tokens"] = 3000
        
        with patch('app.utils.conversation_memory.update_history') as mock_update, \
             patch('app.utils.conversation_memory.should_summarize') as mock_should:
            
            mock_update.return_value = state_with_history
            mock_should.return_value = False
            
            result = manage_chat_history(state_with_history)
            
            # Verify should_summarize was called with thresholds
            call_args = mock_should.call_args
            assert call_args[0][1] == 10  # threshold_turns
            assert call_args[0][2] == 3000  # threshold_tokens
