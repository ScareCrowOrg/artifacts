"""
Unit tests for function_calling.py

Tests the function calling processor which:
- Processes messages with OpenAI function calling
- Enables LLM to request document content on-demand
- Builds messages for OpenAI API
- Executes tool calls for document access

Target coverage: 90%+
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.orchestrator.langgraph.function_calling import (
    process_with_function_calling,
    _build_messages
)


class TestBuildMessages:
    """Test message building for OpenAI API."""
    
    def test_build_messages_basic(self):
        """Test basic message building without history."""
        messages = _build_messages([], "What is LangGraph?")
        
        assert len(messages) == 2  # System + user message
        assert messages[0]["role"] == "system"
        assert "ScareVerse" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "What is LangGraph?"
    
    def test_build_messages_with_history(self):
        """Test message building with conversation history."""
        historico = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]
        
        messages = _build_messages(historico, "How are you?")
        
        assert len(messages) == 4  # System + 2 history + user
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "Hi there"
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "How are you?"
    
    def test_build_messages_system_prompt(self):
        """Test that system prompt includes tool guidance."""
        messages = _build_messages([], "Test")
        
        system_prompt = messages[0]["content"]
        assert "read_local_document" in system_prompt
        assert "AgenteLab" in system_prompt
        assert "ScareVerse" in system_prompt
        assert "grep" in system_prompt
        assert "find" in system_prompt
    
    def test_build_messages_role_mapping(self):
        """Test that history roles are mapped correctly."""
        historico = [
            {"role": "user", "content": "Q1"},
            {"role": "agent", "content": "A1"},  # Should map to assistant
            {"role": "assistant", "content": "A2"}
        ]
        
        messages = _build_messages(historico, "Q2")
        
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"
        assert messages[3]["role"] == "assistant"


@pytest.mark.asyncio
class TestProcessWithFunctionCalling:
    """Test function calling processing."""
    
    async def test_process_with_function_calling_success(self):
        """Test successful function calling processing."""
        with patch('app.openai_service.processar_com_function_calling', new_callable=AsyncMock) as mock_fc, \
             patch('app.document_tools.get_read_document_tool_definition') as mock_tool, \
             patch('app.document_tools.execute_tool_call') as mock_exec:
            
            mock_tool.return_value = {"name": "read_local_document", "description": "Read a document"}
            mock_fc.return_value = {
                "response": "Here is the information from the document...",
                "tool_calls_made": [
                    {"tool": "read_local_document", "arguments": {"path": "docs/README.md"}}
                ]
            }
            
            response = await process_with_function_calling(
                mensagem="Show me the README",
                historico=[],
                modelo="gpt-4"
            )
            
            assert response == "Here is the information from the document..."
            mock_fc.assert_called_once()
    
    async def test_process_with_function_calling_no_tool_calls(self):
        """Test function calling without tool calls."""
        with patch('app.openai_service.processar_com_function_calling', new_callable=AsyncMock) as mock_fc, \
             patch('app.document_tools.get_read_document_tool_definition') as mock_tool, \
             patch('app.document_tools.execute_tool_call') as mock_exec:
            
            mock_tool.return_value = {"name": "read_local_document"}
            mock_fc.return_value = {
                "response": "I can help with that",
                "tool_calls_made": []
            }
            
            response = await process_with_function_calling(
                mensagem="What is testing?",
                historico=[],
                modelo="gpt-4"
            )
            
            assert response == "I can help with that"
    
    async def test_process_with_function_calling_multiple_calls(self):
        """Test function calling with multiple tool calls."""
        with patch('app.openai_service.processar_com_function_calling', new_callable=AsyncMock) as mock_fc, \
             patch('app.document_tools.get_read_document_tool_definition') as mock_tool, \
             patch('app.document_tools.execute_tool_call') as mock_exec:
            
            mock_tool.return_value = {"name": "read_local_document"}
            mock_fc.return_value = {
                "response": "Combined information from both files",
                "tool_calls_made": [
                    {"tool": "read_local_document", "arguments": {"path": "file1.md"}},
                    {"tool": "read_local_document", "arguments": {"path": "file2.md"}}
                ]
            }
            
            response = await process_with_function_calling(
                mensagem="Compare file1 and file2",
                historico=[],
                modelo="gpt-4"
            )
            
            assert "Combined information" in response
    
    async def test_process_with_function_calling_error(self):
        """Test function calling error handling."""
        with patch('app.openai_service.processar_com_function_calling', new_callable=AsyncMock) as mock_fc, \
             patch('app.document_tools.get_read_document_tool_definition') as mock_tool:
            
            mock_tool.return_value = {"name": "read_local_document"}
            mock_fc.side_effect = Exception("OpenAI API error")
            
            response = await process_with_function_calling(
                mensagem="Test",
                historico=[],
                modelo="gpt-4"
            )
            
            assert "error" in response
            assert "OpenAI API error" in response
    
    async def test_process_with_function_calling_with_history(self):
        """Test function calling with conversation history."""
        historico = [
            {"role": "user", "content": "What files exist?"},
            {"role": "assistant", "content": "There are several files..."}
        ]
        
        with patch('app.openai_service.processar_com_function_calling', new_callable=AsyncMock) as mock_fc, \
             patch('app.document_tools.get_read_document_tool_definition') as mock_tool, \
             patch('app.document_tools.execute_tool_call') as mock_exec:
            
            mock_tool.return_value = {"name": "read_local_document"}
            mock_fc.return_value = {
                "response": "Response based on history",
                "tool_calls_made": []
            }
            
            response = await process_with_function_calling(
                mensagem="Show me the first one",
                historico=historico,
                modelo="gpt-4"
            )
            
            # Verify history was passed to function calling
            call_args = mock_fc.call_args
            messages = call_args[1]["messages"]
            assert len(messages) >= 3  # System + history + current
    
    async def test_process_with_function_calling_tools_passed(self):
        """Test that tools are correctly passed to function calling."""
        with patch('app.openai_service.processar_com_function_calling', new_callable=AsyncMock) as mock_fc, \
             patch('app.document_tools.get_read_document_tool_definition') as mock_tool, \
             patch('app.document_tools.execute_tool_call') as mock_exec:
            
            mock_tool_def = {"name": "read_local_document", "description": "Reads a document"}
            mock_tool.return_value = mock_tool_def
            mock_fc.return_value = {
                "response": "Success",
                "tool_calls_made": []
            }
            
            response = await process_with_function_calling(
                mensagem="Test",
                historico=[],
                modelo="gpt-4",
                enable_runtime_tools=False  # Disable runtime tools for this test
            )
            
            # Verify tools were passed correctly
            call_args = mock_fc.call_args
            tools = call_args[1]["tools"]
            assert len(tools) == 1  # Only read_local_document without runtime tools
            assert tools[0] == mock_tool_def
            # Verify tool_executor was passed
            assert call_args[1]["tool_executor"] is not None
    
    async def test_process_with_function_calling_parameters(self):
        """Test that function calling is invoked with correct parameters."""
        with patch('app.openai_service.processar_com_function_calling', new_callable=AsyncMock) as mock_fc, \
             patch('app.document_tools.get_read_document_tool_definition') as mock_tool, \
             patch('app.document_tools.execute_tool_call') as mock_exec:
            
            mock_tool.return_value = {"name": "read_local_document"}
            mock_fc.return_value = {
                "response": "Test response",
                "tool_calls_made": []
            }
            
            await process_with_function_calling(
                mensagem="Test",
                historico=[],
                modelo="gpt-4"
            )
            
            # Verify parameters
            call_args = mock_fc.call_args
            assert call_args[1]["model_id"] == "gpt-4"
            assert call_args[1]["temperature"] == 0.7
            assert call_args[1]["max_tokens"] == 4096
            assert call_args[1]["max_iterations"] == 5
