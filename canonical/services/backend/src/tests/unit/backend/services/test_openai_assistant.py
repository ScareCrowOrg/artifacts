"""
Unit tests for OpenAI Assistant Service integration.

Tests the modularized OpenAI Assistant API integration including:
- Assistant creation and retrieval (assistant_manager)
- Thread creation and retrieval (thread_manager)
- Message handling (message_manager)
- Run execution and polling (run_manager)
- Complete orchestration workflow (orchestrator)

Compliance: RULESET.md Rule 3.1 (90% coverage), Rule 3.2 (Unit tests)
"""

import pytest
import httpx
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from tempfile import NamedTemporaryFile

from app.services.openai_assistant import (
    create_or_get_assistant,
    create_thread,
    get_thread,
    add_message_to_thread,
    run_assistant,
    get_run_messages,
    process_with_assistant,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_MAX_POLL_TIME
)
from .mocks.openai_mock import (
    MockHttpxAsyncClient,
    create_mock_assistant_response,
    create_mock_thread_response,
    create_mock_message_response,
    create_mock_run_response,
    create_mock_file_response
)


class TestAssistantManager:
    """Tests for assistant_manager module."""
    
    @pytest.mark.asyncio
    async def test_create_assistant_success(self):
        """Test successful assistant creation."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_post_response(
            url="/assistants",
            response_data=create_mock_assistant_response("asst_123", "Test Bot")
        )
        
        with patch('app.services.openai_assistant.assistant_manager.httpx.AsyncClient', return_value=mock_client):
            assistant_id = await create_or_get_assistant(
                name="Test Bot",
                instructions="Be helpful",
                model="gpt-4o-mini",
                api_key="test-key"
            )
        
        assert assistant_id == "asst_123"
        assert mock_client.call_count['POST'] == 1
    
    @pytest.mark.asyncio
    async def test_create_assistant_with_tools(self):
        """Test assistant creation with tools."""
        mock_client = MockHttpxAsyncClient()
        mock_response = create_mock_assistant_response("asst_456")
        mock_response['tools'] = [{"type": "file_search"}]
        mock_client.setup_post_response(
            url="/assistants",
            response_data=mock_response
        )
        
        with patch('app.services.openai_assistant.assistant_manager.httpx.AsyncClient', return_value=mock_client):
            assistant_id = await create_or_get_assistant(
                name="Tool Bot",
                instructions="Use tools",
                tools=[{"type": "file_search"}],
                api_key="test-key"
            )
        
        assert assistant_id == "asst_456"
    
    @pytest.mark.asyncio
    async def test_create_assistant_no_api_key(self):
        """Test error when API key is not configured."""
        with patch('app.services.openai_assistant.assistant_manager.OPENAI_API_KEY', None):
            with pytest.raises(ValueError) as exc_info:
                await create_or_get_assistant(
                    name="Test",
                    instructions="Test"
                )
            
            assert "OpenAI API Key não configurada" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_assistant_with_global_api_key(self):
        """Test assistant creation using global API key."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_post_response(
            url="/assistants",
            response_data=create_mock_assistant_response("asst_789")
        )
        
        with patch('app.services.openai_assistant.assistant_manager.httpx.AsyncClient', return_value=mock_client):
            with patch('app.services.openai_assistant.assistant_manager.OPENAI_API_KEY', "global-key"):
                assistant_id = await create_or_get_assistant(
                    name="Global",
                    instructions="Test"
                )
        
        assert assistant_id == "asst_789"
    
    @pytest.mark.asyncio
    async def test_create_assistant_invalid_response(self):
        """Test error handling when API returns invalid response."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_post_response(
            url="/assistants",
            response_data={"error": "Invalid"}
        )
        
        with patch('app.services.openai_assistant.assistant_manager.httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(ValueError) as exc_info:
                await create_or_get_assistant(
                    name="Test",
                    instructions="Test",
                    api_key="test-key"
                )
            
            assert "Invalid response from OpenAI Assistants API" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_assistant_http_error(self):
        """Test error handling for HTTP errors."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_post_response(
            url="/assistants",
            response_data={},
            status_code=500
        )
        
        with patch('app.services.openai_assistant.assistant_manager.httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await create_or_get_assistant(
                    name="Test",
                    instructions="Test",
                    api_key="test-key"
                )
    
    @pytest.mark.asyncio
    async def test_create_assistant_timeout(self):
        """Test timeout handling during assistant creation."""
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.post.side_effect = httpx.TimeoutException("Timeout")
        
        with patch('app.services.openai_assistant.assistant_manager.httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(httpx.TimeoutException):
                await create_or_get_assistant(
                    name="Test",
                    instructions="Test",
                    api_key="test-key"
                )


class TestThreadManager:
    """Tests for thread_manager module."""
    
    @pytest.mark.asyncio
    async def test_create_thread_success(self):
        """Test successful thread creation."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_post_response(
            url="/threads",
            response_data=create_mock_thread_response("thread_123")
        )
        
        with patch('app.services.openai_assistant.thread_manager.httpx.AsyncClient', return_value=mock_client):
            thread_id = await create_thread(api_key="test-key")
        
        assert thread_id == "thread_123"
        assert mock_client.call_count['POST'] == 1
    
    @pytest.mark.asyncio
    async def test_create_thread_with_global_api_key(self):
        """Test thread creation using global API key."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_post_response(
            url="/threads",
            response_data=create_mock_thread_response("thread_456")
        )
        
        with patch('app.services.openai_assistant.thread_manager.httpx.AsyncClient', return_value=mock_client):
            with patch('app.services.openai_assistant.thread_manager.OPENAI_API_KEY', "global-key"):
                thread_id = await create_thread()
        
        assert thread_id == "thread_456"
    
    @pytest.mark.asyncio
    async def test_create_thread_no_api_key(self):
        """Test error when API key is not configured."""
        with patch('app.services.openai_assistant.thread_manager.OPENAI_API_KEY', None):
            with pytest.raises(ValueError) as exc_info:
                await create_thread()
            
            assert "OpenAI API Key não configurada" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_thread_invalid_response(self):
        """Test error handling when API returns invalid response."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_post_response(
            url="/threads",
            response_data={"error": "Invalid"}
        )
        
        with patch('app.services.openai_assistant.thread_manager.httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(ValueError) as exc_info:
                await create_thread(api_key="test-key")
            
            assert "Invalid response from OpenAI Threads API" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_thread_http_error(self):
        """Test error handling for HTTP errors."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_post_response(
            url="/threads",
            response_data={},
            status_code=500
        )
        
        with patch('app.services.openai_assistant.thread_manager.httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await create_thread(api_key="test-key")
    
    @pytest.mark.asyncio
    async def test_get_thread_success(self):
        """Test successful thread retrieval."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_get_response(
            url="/threads/thread_123",
            response_data=create_mock_thread_response("thread_123")
        )
        
        with patch('app.services.openai_assistant.thread_manager.httpx.AsyncClient', return_value=mock_client):
            thread = await get_thread(
                thread_id="thread_123",
                api_key="test-key"
            )
        
        assert thread['id'] == "thread_123"
        assert mock_client.call_count['GET'] == 1
    
    @pytest.mark.asyncio
    async def test_get_thread_no_api_key(self):
        """Test error when API key is not configured."""
        with patch('app.services.openai_assistant.thread_manager.OPENAI_API_KEY', None):
            with pytest.raises(ValueError) as exc_info:
                await get_thread(thread_id="thread_123")
            
            assert "OpenAI API Key não configurada" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_thread_http_error(self):
        """Test error handling for HTTP errors."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_get_response(
            url="/threads/thread_123",
            response_data={},
            status_code=404
        )
        
        with patch('app.services.openai_assistant.thread_manager.httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await get_thread(
                    thread_id="thread_123",
                    api_key="test-key"
                )


class TestMessageManager:
    """Tests for message_manager module."""
    
    @pytest.mark.asyncio
    async def test_add_message_success(self):
        """Test successful message addition."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_post_response(
            url="/threads/thread_123/messages",
            response_data=create_mock_message_response("msg_123", "thread_123")
        )
        
        with patch('app.services.openai_assistant.message_manager.httpx.AsyncClient', return_value=mock_client):
            message_id = await add_message_to_thread(
                thread_id="thread_123",
                content="Hello",
                api_key="test-key"
            )
        
        assert message_id == "msg_123"
        assert mock_client.call_count['POST'] == 1
    
    @pytest.mark.asyncio
    async def test_add_message_with_files(self):
        """Test message addition with file attachments."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_post_response(
            url="/threads/thread_123/messages",
            response_data=create_mock_message_response("msg_456", "thread_123")
        )
        
        with patch('app.services.openai_assistant.message_manager.httpx.AsyncClient', return_value=mock_client):
            message_id = await add_message_to_thread(
                thread_id="thread_123",
                content="Analyze this",
                file_ids=["file-1", "file-2"],
                api_key="test-key"
            )
        
        assert message_id == "msg_456"
    
    @pytest.mark.asyncio
    async def test_add_message_with_role(self):
        """Test message addition with custom role."""
        mock_client = MockHttpxAsyncClient()
        mock_response = create_mock_message_response("msg_789", "thread_123", "assistant")
        mock_client.setup_post_response(
            url="/threads/thread_123/messages",
            response_data=mock_response
        )
        
        with patch('app.services.openai_assistant.message_manager.httpx.AsyncClient', return_value=mock_client):
            message_id = await add_message_to_thread(
                thread_id="thread_123",
                content="Response",
                role="assistant",
                api_key="test-key"
            )
        
        assert message_id == "msg_789"
    
    @pytest.mark.asyncio
    async def test_add_message_no_api_key(self):
        """Test error when API key is not configured."""
        with patch('app.services.openai_assistant.message_manager.OPENAI_API_KEY', None):
            with pytest.raises(ValueError) as exc_info:
                await add_message_to_thread(
                    thread_id="thread_123",
                    content="Hello"
                )
            
            assert "OpenAI API Key não configurada" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_add_message_invalid_response(self):
        """Test error handling when API returns invalid response."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_post_response(
            url="/threads/thread_123/messages",
            response_data={"error": "Invalid"}
        )
        
        with patch('app.services.openai_assistant.message_manager.httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(ValueError) as exc_info:
                await add_message_to_thread(
                    thread_id="thread_123",
                    content="Hello",
                    api_key="test-key"
                )
            
            assert "Invalid response from OpenAI Messages API" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_add_message_http_error(self):
        """Test error handling for HTTP errors."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_post_response(
            url="/threads/thread_123/messages",
            response_data={},
            status_code=500
        )
        
        with patch('app.services.openai_assistant.message_manager.httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await add_message_to_thread(
                    thread_id="thread_123",
                    content="Hello",
                    api_key="test-key"
                )
    
    @pytest.mark.asyncio
    async def test_get_run_messages_success(self):
        """Test successful message retrieval."""
        mock_client = MockHttpxAsyncClient()
        messages = [
            create_mock_message_response("msg_1", "thread_123", "user", "Hello"),
            create_mock_message_response("msg_2", "thread_123", "assistant", "Hi!")
        ]
        mock_client.setup_get_response(
            url="/threads/thread_123/messages",
            response_data={"data": messages}
        )
        
        with patch('app.services.openai_assistant.message_manager.httpx.AsyncClient', return_value=mock_client):
            result = await get_run_messages(
                thread_id="thread_123",
                api_key="test-key"
            )
        
        assert len(result) == 2
        assert result[0]['id'] == "msg_1"
        assert result[1]['id'] == "msg_2"
    
    @pytest.mark.asyncio
    async def test_get_run_messages_with_limit(self):
        """Test message retrieval with custom limit."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_get_response(
            url="/threads/thread_123/messages",
            response_data={"data": []}
        )
        
        with patch('app.services.openai_assistant.message_manager.httpx.AsyncClient', return_value=mock_client):
            result = await get_run_messages(
                thread_id="thread_123",
                limit=5,
                api_key="test-key"
            )
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_run_messages_no_api_key(self):
        """Test error when API key is not configured."""
        with patch('app.services.openai_assistant.message_manager.OPENAI_API_KEY', None):
            with pytest.raises(ValueError) as exc_info:
                await get_run_messages(thread_id="thread_123")
            
            assert "OpenAI API Key não configurada" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_run_messages_http_error(self):
        """Test error handling for HTTP errors."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_get_response(
            url="/threads/thread_123/messages",
            response_data={},
            status_code=500
        )
        
        with patch('app.services.openai_assistant.message_manager.httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await get_run_messages(
                    thread_id="thread_123",
                    api_key="test-key"
                )


class TestRunManager:
    """Tests for run_manager module."""
    
    @pytest.mark.asyncio
    async def test_run_assistant_success(self):
        """Test successful run execution and completion."""
        mock_client = MockHttpxAsyncClient()
        # Initial run creation
        mock_client.setup_post_response(
            url="/threads/thread_123/runs",
            response_data=create_mock_run_response("run_123", "thread_123", "asst_123", "in_progress")
        )
        # Run status check (completed)
        mock_client.setup_get_response(
            url="/threads/thread_123/runs/run_123",
            response_data=create_mock_run_response("run_123", "thread_123", "asst_123", "completed")
        )
        
        with patch('app.services.openai_assistant.run_manager.httpx.AsyncClient', return_value=mock_client):
            run_result = await run_assistant(
                thread_id="thread_123",
                assistant_id="asst_123",
                api_key="test-key"
            )
        
        assert run_result['status'] == "completed"
        assert run_result['id'] == "run_123"
    
    @pytest.mark.asyncio
    async def test_run_assistant_failed_status(self):
        """Test run with failed status."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_post_response(
            url="/threads/thread_123/runs",
            response_data=create_mock_run_response("run_456", "thread_123", "asst_123", "in_progress")
        )
        mock_client.setup_get_response(
            url="/threads/thread_123/runs/run_456",
            response_data=create_mock_run_response("run_456", "thread_123", "asst_123", "failed")
        )
        
        with patch('app.services.openai_assistant.run_manager.httpx.AsyncClient', return_value=mock_client):
            run_result = await run_assistant(
                thread_id="thread_123",
                assistant_id="asst_123",
                api_key="test-key"
            )
        
        assert run_result['status'] == "failed"
    
    @pytest.mark.asyncio
    async def test_run_assistant_cancelled_status(self):
        """Test run with cancelled status."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_post_response(
            url="/threads/thread_123/runs",
            response_data=create_mock_run_response("run_789", "thread_123", "asst_123", "in_progress")
        )
        mock_client.setup_get_response(
            url="/threads/thread_123/runs/run_789",
            response_data=create_mock_run_response("run_789", "thread_123", "asst_123", "cancelled")
        )
        
        with patch('app.services.openai_assistant.run_manager.httpx.AsyncClient', return_value=mock_client):
            run_result = await run_assistant(
                thread_id="thread_123",
                assistant_id="asst_123",
                api_key="test-key"
            )
        
        assert run_result['status'] == "cancelled"
    
    @pytest.mark.asyncio
    async def test_run_assistant_no_api_key(self):
        """Test error when API key is not configured."""
        with patch('app.services.openai_assistant.run_manager.OPENAI_API_KEY', None):
            with pytest.raises(ValueError) as exc_info:
                await run_assistant(
                    thread_id="thread_123",
                    assistant_id="asst_123"
                )
            
            assert "OpenAI API Key não configurada" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_run_assistant_invalid_response(self):
        """Test error handling when API returns invalid response."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_post_response(
            url="/threads/thread_123/runs",
            response_data={"error": "Invalid"}
        )
        
        with patch('app.services.openai_assistant.run_manager.httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(ValueError) as exc_info:
                await run_assistant(
                    thread_id="thread_123",
                    assistant_id="asst_123",
                    api_key="test-key"
                )
            
            assert "Invalid response from OpenAI Runs API" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_run_assistant_http_error(self):
        """Test error handling for HTTP errors."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_post_response(
            url="/threads/thread_123/runs",
            response_data={},
            status_code=500
        )
        
        with patch('app.services.openai_assistant.run_manager.httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await run_assistant(
                    thread_id="thread_123",
                    assistant_id="asst_123",
                    api_key="test-key"
                )


class TestOrchestrator:
    """Tests for orchestrator module (process_with_assistant)."""
    
    @pytest.mark.asyncio
    async def test_process_with_assistant_complete_flow(self):
        """Test complete assistant processing flow."""
        # Mock all the sub-functions instead of HTTP client
        with patch('app.services.openai_assistant.orchestrator.create_or_get_assistant', new_callable=AsyncMock) as mock_create_asst:
            with patch('app.services.openai_assistant.orchestrator.create_thread', new_callable=AsyncMock) as mock_create_thread:
                with patch('app.services.openai_assistant.orchestrator.add_message_to_thread', new_callable=AsyncMock) as mock_add_msg:
                    with patch('app.services.openai_assistant.orchestrator.run_assistant', new_callable=AsyncMock) as mock_run:
                        with patch('app.services.openai_assistant.orchestrator.get_run_messages', new_callable=AsyncMock) as mock_get_msgs:
                            # Setup mock return values
                            mock_create_asst.return_value = "asst_123"
                            mock_create_thread.return_value = "thread_123"
                            mock_add_msg.return_value = "msg_123"
                            mock_run.return_value = {"status": "completed"}
                            mock_get_msgs.return_value = [
                                create_mock_message_response("msg_456", "thread_123", "assistant", "Here's the answer")
                            ]
                            
                            response, thread_id, assistant_id = await process_with_assistant(
                                user_message="Test question",
                                api_key="test-key"
                            )
        
        assert response == "Here's the answer"
        assert thread_id == "thread_123"
        assert assistant_id == "asst_123"
    
    @pytest.mark.asyncio
    async def test_process_with_assistant_with_existing_thread(self):
        """Test processing with existing thread."""
        with patch('app.services.openai_assistant.orchestrator.create_or_get_assistant', new_callable=AsyncMock) as mock_create_asst:
            with patch('app.services.openai_assistant.orchestrator.add_message_to_thread', new_callable=AsyncMock) as mock_add_msg:
                with patch('app.services.openai_assistant.orchestrator.run_assistant', new_callable=AsyncMock) as mock_run:
                    with patch('app.services.openai_assistant.orchestrator.get_run_messages', new_callable=AsyncMock) as mock_get_msgs:
                        mock_create_asst.return_value = "asst_456"
                        mock_add_msg.return_value = "msg_789"
                        mock_run.return_value = {"status": "completed"}
                        mock_get_msgs.return_value = [
                            create_mock_message_response("msg_999", "thread_existing", "assistant", "Response")
                        ]
                        
                        response, thread_id, assistant_id = await process_with_assistant(
                            user_message="Test",
                            thread_id="thread_existing",
                            api_key="test-key"
                        )
        
        assert thread_id == "thread_existing"
    
    @pytest.mark.asyncio
    async def test_process_with_assistant_with_existing_assistant(self):
        """Test processing with existing assistant."""
        with patch('app.services.openai_assistant.orchestrator.create_thread', new_callable=AsyncMock) as mock_create_thread:
            with patch('app.services.openai_assistant.orchestrator.add_message_to_thread', new_callable=AsyncMock) as mock_add_msg:
                with patch('app.services.openai_assistant.orchestrator.run_assistant', new_callable=AsyncMock) as mock_run:
                    with patch('app.services.openai_assistant.orchestrator.get_run_messages', new_callable=AsyncMock) as mock_get_msgs:
                        mock_create_thread.return_value = "thread_789"
                        mock_add_msg.return_value = "msg_abc"
                        mock_run.return_value = {"status": "completed"}
                        mock_get_msgs.return_value = [
                            create_mock_message_response("msg_resp", "thread_789", "assistant", "Done")
                        ]
                        
                        response, thread_id, assistant_id = await process_with_assistant(
                            user_message="Test",
                            assistant_id="asst_existing",
                            api_key="test-key"
                        )
        
        assert assistant_id == "asst_existing"
    
    @pytest.mark.asyncio
    async def test_process_with_assistant_with_files(self):
        """Test processing with file attachments."""
        # Create temporary test file
        with NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content")
            temp_file = Path(f.name)
        
        try:
            # Patch where the function is imported from
            with patch('app.services.openai_files_api.upload_file_to_openai_api', new_callable=AsyncMock) as mock_upload:
                with patch('app.services.openai_assistant.orchestrator.create_or_get_assistant', new_callable=AsyncMock) as mock_create_asst:
                    with patch('app.services.openai_assistant.orchestrator.create_thread', new_callable=AsyncMock) as mock_create_thread:
                        with patch('app.services.openai_assistant.orchestrator.add_message_to_thread', new_callable=AsyncMock) as mock_add_msg:
                            with patch('app.services.openai_assistant.orchestrator.run_assistant', new_callable=AsyncMock) as mock_run:
                                with patch('app.services.openai_assistant.orchestrator.get_run_messages', new_callable=AsyncMock) as mock_get_msgs:
                                    mock_upload.return_value = "file-abc"
                                    mock_create_asst.return_value = "asst_file"
                                    mock_create_thread.return_value = "thread_file"
                                    mock_add_msg.return_value = "msg_file"
                                    mock_run.return_value = {"status": "completed"}
                                    mock_get_msgs.return_value = [
                                        create_mock_message_response("msg_r", "thread_file", "assistant", "File analyzed")
                                    ]
                                    
                                    response, thread_id, assistant_id = await process_with_assistant(
                                        user_message="Analyze this file",
                                        file_paths=[temp_file],
                                        api_key="test-key"
                                    )
            
            assert "File analyzed" in response
            # Verify file upload was called
            assert mock_upload.called
        finally:
            temp_file.unlink()
    
    @pytest.mark.asyncio
    async def test_process_with_assistant_no_api_key(self):
        """Test error when API key is not configured."""
        with patch('app.services.openai_assistant.orchestrator.OPENAI_API_KEY', None):
            with pytest.raises(ValueError) as exc_info:
                await process_with_assistant(user_message="Test")
            
            assert "OpenAI API Key não configurada" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_process_with_assistant_run_failed(self):
        """Test handling of failed run."""
        with patch('app.services.openai_assistant.orchestrator.create_or_get_assistant', new_callable=AsyncMock) as mock_create_asst:
            with patch('app.services.openai_assistant.orchestrator.create_thread', new_callable=AsyncMock) as mock_create_thread:
                with patch('app.services.openai_assistant.orchestrator.add_message_to_thread', new_callable=AsyncMock) as mock_add_msg:
                    with patch('app.services.openai_assistant.orchestrator.run_assistant', new_callable=AsyncMock) as mock_run:
                        mock_create_asst.return_value = "asst_fail"
                        mock_create_thread.return_value = "thread_fail"
                        mock_add_msg.return_value = "msg_fail"
                        mock_run.return_value = {
                            "status": "failed",
                            "last_error": {"message": "Something went wrong"}
                        }
                        
                        with pytest.raises(RuntimeError) as exc_info:
                            await process_with_assistant(
                                user_message="Test",
                                api_key="test-key"
                            )
        
        assert "Assistant run failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_process_with_assistant_no_response(self):
        """Test handling when no assistant response is found."""
        with patch('app.services.openai_assistant.orchestrator.create_or_get_assistant', new_callable=AsyncMock) as mock_create_asst:
            with patch('app.services.openai_assistant.orchestrator.create_thread', new_callable=AsyncMock) as mock_create_thread:
                with patch('app.services.openai_assistant.orchestrator.add_message_to_thread', new_callable=AsyncMock) as mock_add_msg:
                    with patch('app.services.openai_assistant.orchestrator.run_assistant', new_callable=AsyncMock) as mock_run:
                        with patch('app.services.openai_assistant.orchestrator.get_run_messages', new_callable=AsyncMock) as mock_get_msgs:
                            mock_create_asst.return_value = "asst_empty"
                            mock_create_thread.return_value = "thread_empty"
                            mock_add_msg.return_value = "msg_empty"
                            mock_run.return_value = {"status": "completed"}
                            mock_get_msgs.return_value = []  # No messages
                            
                            response, thread_id, assistant_id = await process_with_assistant(
                                user_message="Test",
                                api_key="test-key"
                            )
        
        assert "Não foi possível obter uma resposta" in response


class TestConstants:
    """Tests for exported constants."""
    
    def test_default_poll_interval(self):
        """Test DEFAULT_POLL_INTERVAL constant."""
        assert DEFAULT_POLL_INTERVAL == 1.0
    
    def test_default_max_poll_time(self):
        """Test DEFAULT_MAX_POLL_TIME constant."""
        assert DEFAULT_MAX_POLL_TIME == 120.0
