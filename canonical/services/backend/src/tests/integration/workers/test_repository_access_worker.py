"""
Integration tests for Repository Access Worker.

Tests file access request handling, path validation, and error handling.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from app.workers.repository_access_worker import RepositoryAccessWorker
from app.models.event_bus import (
    MessageEnvelope,
    EventTopic,
    FileAccessRequest,
    FileAccessResponse,
    ErrorResponse
)


class TestRepositoryAccessWorker:
    """Integration tests for repository access worker."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            
            # Create test files
            (temp_path / "test_file.txt").write_text("Hello, World!", encoding="utf-8")
            (temp_path / "subdir").mkdir()
            (temp_path / "subdir" / "nested_file.txt").write_text("Nested content", encoding="utf-8")
            
            yield temp_path
    
    @pytest.fixture
    async def worker(self, temp_dir):
        """Create a worker instance with mocked pub/sub."""
        worker = RepositoryAccessWorker(base_dir=temp_dir)
        
        # Mock the pub/sub service
        worker._pubsub_service = AsyncMock()
        worker._pubsub_service.subscribe = AsyncMock()
        worker._pubsub_service.unsubscribe = AsyncMock()
        worker._pubsub_service.publish = AsyncMock()
        worker._is_running = True
        
        return worker
    
    @pytest.mark.asyncio
    async def test_resolve_path_simple(self, worker, temp_dir):
        """Test resolving a simple file path."""
        resolved = worker._resolve_path("test_file.txt")
        
        assert resolved is not None
        assert resolved == temp_dir / "test_file.txt"
    
    @pytest.mark.asyncio
    async def test_resolve_path_nested(self, worker, temp_dir):
        """Test resolving a nested file path."""
        resolved = worker._resolve_path("subdir/nested_file.txt")
        
        assert resolved is not None
        assert resolved == temp_dir / "subdir" / "nested_file.txt"
    
    @pytest.mark.asyncio
    async def test_resolve_path_blocks_directory_traversal(self, worker):
        """Test that directory traversal attempts are blocked."""
        resolved = worker._resolve_path("../../etc/passwd")
        
        assert resolved is None
    
    @pytest.mark.asyncio
    async def test_resolve_path_handles_absolute_paths(self, worker, temp_dir):
        """Test that absolute paths are converted to relative (leading slash stripped)."""
        resolved = worker._resolve_path("/test_file.txt")
        
        # Leading slash should be stripped, making it relative to BASE_DIR
        assert resolved is not None
        assert resolved == temp_dir / "test_file.txt"
    
    @pytest.mark.asyncio
    async def test_handle_file_access_success(self, worker, temp_dir):
        """Test successfully handling a file access request."""
        request_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.AGENT_REQUEST_FILE_ACCESS.value,
            payload={
                "path": "test_file.txt",
                "encoding": "utf-8"
            }
        )
        
        await worker._handle_file_access_request(request_message)
        
        # Verify a response was published
        assert worker._pubsub_service.publish.called
        
        # Check the response
        call_args = worker._pubsub_service.publish.call_args
        response_message = call_args[0][0]
        
        assert response_message.topic == EventTopic.AGENT_RESPONSE_FILE_DATA.value
        assert response_message.correlation_id == request_message.trace_id
        assert response_message.payload["path"] == "test_file.txt"
        assert response_message.payload["content"] == "Hello, World!"
        assert response_message.payload["size"] == 13
    
    @pytest.mark.asyncio
    async def test_handle_file_access_nested_file(self, worker, temp_dir):
        """Test accessing a nested file."""
        request_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.AGENT_REQUEST_FILE_ACCESS.value,
            payload={
                "path": "subdir/nested_file.txt",
                "encoding": "utf-8"
            }
        )
        
        await worker._handle_file_access_request(request_message)
        
        # Verify response
        call_args = worker._pubsub_service.publish.call_args
        response_message = call_args[0][0]
        
        assert response_message.topic == EventTopic.AGENT_RESPONSE_FILE_DATA.value
        assert response_message.payload["content"] == "Nested content"
    
    @pytest.mark.asyncio
    async def test_handle_file_not_found(self, worker):
        """Test handling a request for a non-existent file."""
        request_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.AGENT_REQUEST_FILE_ACCESS.value,
            payload={
                "path": "nonexistent_file.txt",
                "encoding": "utf-8"
            }
        )
        
        await worker._handle_file_access_request(request_message)
        
        # Verify error response
        call_args = worker._pubsub_service.publish.call_args
        response_message = call_args[0][0]
        
        assert response_message.topic == EventTopic.AGENT_RESPONSE_ERROR.value
        assert response_message.payload["error_code"] == "FILE_NOT_FOUND"
    
    @pytest.mark.asyncio
    async def test_handle_directory_access(self, worker, temp_dir):
        """Test that accessing a directory returns an error."""
        request_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.AGENT_REQUEST_FILE_ACCESS.value,
            payload={
                "path": "subdir",
                "encoding": "utf-8"
            }
        )
        
        await worker._handle_file_access_request(request_message)
        
        # Verify error response
        call_args = worker._pubsub_service.publish.call_args
        response_message = call_args[0][0]
        
        assert response_message.topic == EventTopic.AGENT_RESPONSE_ERROR.value
        assert response_message.payload["error_code"] == "NOT_A_FILE"
    
    @pytest.mark.asyncio
    async def test_handle_invalid_path(self, worker):
        """Test handling an invalid/unsafe path."""
        request_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.AGENT_REQUEST_FILE_ACCESS.value,
            payload={
                "path": "../../etc/passwd",
                "encoding": "utf-8"
            }
        )
        
        await worker._handle_file_access_request(request_message)
        
        # Verify error response
        call_args = worker._pubsub_service.publish.call_args
        response_message = call_args[0][0]
        
        assert response_message.topic == EventTopic.AGENT_RESPONSE_ERROR.value
        assert response_message.payload["error_code"] == "INVALID_PATH"
    
    @pytest.mark.asyncio
    async def test_worker_start_and_stop(self):
        """Test worker lifecycle (start/stop)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            worker = RepositoryAccessWorker(base_dir=Path(tmpdir))
            
            # Mock pub/sub service
            mock_pubsub = AsyncMock()
            mock_pubsub.subscribe = AsyncMock()
            mock_pubsub.unsubscribe = AsyncMock()
            
            with patch('app.workers.repository_access_worker.get_pubsub_service', return_value=mock_pubsub):
                await worker.start()
                assert worker._is_running is True
                assert mock_pubsub.subscribe.called
                
                await worker.stop()
                assert worker._is_running is False
                assert mock_pubsub.unsubscribe.called
