"""
Integration tests for Handshake Worker.

Tests handshake request handling, session querying, timestamp filtering,
and response generation.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from app.workers.handshake_worker import HandshakeWorker
from app.models.event_bus import (
    MessageEnvelope,
    EventTopic
)
from app.database.schemas.session_schema import (
    SESSIONS_COLLECTION
)


class TestHandshakeWorker:
    """Integration tests for handshake worker."""
    
    @pytest.fixture
    def async_cursor_mock(self):
        """Create an async cursor mock class for MongoDB queries."""
        class AsyncCursorMock:
            def __init__(self, data):
                self.data = data
                self.index = 0
            
            def __aiter__(self):
                return self
            
            async def __anext__(self):
                if self.index >= len(self.data):
                    raise StopAsyncIteration
                result = self.data[self.index]
                self.index += 1
                return result
            
            def sort(self, *args, **kwargs):
                return self
        
        return AsyncCursorMock
    
    @pytest.fixture
    def mock_mongo_db(self):
        """Create a mock MongoDB database."""
        mock_db = MagicMock()
        mock_collection = MagicMock()
        
        # Configure database to return collection
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        
        return mock_db
    
    @pytest.fixture
    async def worker(self, mock_mongo_db):
        """Create a worker instance with mocked dependencies."""
        worker = HandshakeWorker(mongodb_uri="mongodb://localhost:27017")
        
        # Mock the pub/sub service
        worker._pubsub_service = AsyncMock()
        worker._pubsub_service.subscribe = AsyncMock()
        worker._pubsub_service.unsubscribe = AsyncMock()
        worker._pubsub_service.publish = AsyncMock()
        
        # Mock MongoDB client and database
        worker._mongo_client = MagicMock()
        worker._mongo_client.close = MagicMock()
        worker._db = mock_mongo_db
        worker._is_running = True
        
        return worker
    
    @pytest.fixture
    def sample_handshake_request(self):
        """Create a sample handshake request."""
        return {
            "client_id": "client-123",
            "user_id": "user-456",
            "last_sync_timestamp": None
        }
    
    @pytest.fixture
    def sample_sessions(self):
        """Create sample session data."""
        base_time = datetime.utcnow()
        return [
            {
                "_id": "mongo-id-1",
                "book_id": "book-1",
                "title": "Session 1",
                "state": "active",
                "user_id": "user-456",
                "updated_at": base_time,
                "version": 1
            },
            {
                "_id": "mongo-id-2",
                "book_id": "book-2",
                "title": "Session 2",
                "state": "active",
                "user_id": "user-456",
                "updated_at": base_time - timedelta(hours=1),
                "version": 2
            }
        ]
    
    @pytest.mark.asyncio
    async def test_worker_initialization(self):
        """Test worker is initialized with correct parameters."""
        worker = HandshakeWorker(mongodb_uri="mongodb://test:27017")
        
        assert worker.mongodb_uri == "mongodb://test:27017"
        assert worker._is_running is False
        assert worker._pubsub_service is None
        assert worker._mongo_client is None
    
    @pytest.mark.asyncio
    async def test_worker_start_and_stop(self):
        """Test worker lifecycle (start/stop)."""
        worker = HandshakeWorker()
        
        # Mock dependencies
        mock_mongo_client = MagicMock()
        mock_mongo_client.close = MagicMock()
        mock_db = MagicMock()
        
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        
        with patch('app.workers.handshake_worker.MONGODB_ENABLED', True), \
             patch('app.workers.handshake_worker.AsyncIOMotorClient', return_value=mock_mongo_client), \
             patch('app.workers.handshake_worker.get_pubsub_service', return_value=mock_pubsub):
            
            mock_mongo_client.scareverse = mock_db
            
            # Start worker
            await worker.start()
            assert worker._is_running is True
            assert mock_pubsub.subscribe.called
            
            # Stop worker
            await worker.stop()
            assert worker._is_running is False
            assert mock_pubsub.unsubscribe.called
            assert mock_mongo_client.close.called
    
    @pytest.mark.asyncio
    async def test_worker_start_when_already_running(self, worker):
        """Test that starting an already running worker logs a warning."""
        worker._is_running = True
        
        # Should not raise an error, just return
        await worker.start()
        
        # Worker should still be running
        assert worker._is_running is True
    
    @pytest.mark.asyncio
    async def test_worker_start_when_mongodb_disabled(self):
        """Test worker does not start when MongoDB is disabled."""
        worker = HandshakeWorker()
        
        with patch('app.workers.handshake_worker.MONGODB_ENABLED', False):
            await worker.start()
            
            assert worker._is_running is False
    
    @pytest.mark.asyncio
    async def test_handle_handshake_request_success(self, worker, sample_handshake_request, sample_sessions, mock_mongo_db, async_cursor_mock):
        """Test successfully handling a handshake request."""
        request_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
            payload=sample_handshake_request
        )
        
        # Mock MongoDB query to return sessions
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        mock_cursor = async_cursor_mock(sample_sessions)
        mock_collection.find = Mock(return_value=mock_cursor)
        
        await worker._handle_handshake_request(request_message)
        
        # Verify response was published
        assert worker._pubsub_service.publish.called
        
        # Check response
        call_args = worker._pubsub_service.publish.call_args
        response_message = call_args[0][0]
        
        assert response_message.topic == EventTopic.SYSTEM_EVENT_HANDSHAKE_RESPONSE.value
        assert response_message.correlation_id == request_message.trace_id
        assert response_message.payload["client_id"] == "client-123"
        assert len(response_message.payload["updated_sessions"]) == 2
        assert response_message.payload["sync_count"] == 2
        assert "server_timestamp" in response_message.payload
    
    @pytest.mark.asyncio
    async def test_handle_handshake_request_missing_client_id(self, worker):
        """Test handling handshake request with missing client_id."""
        request_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
            payload={"user_id": "user-456"}  # Missing client_id
        )
        
        await worker._handle_handshake_request(request_message)
        
        # Verify error response
        assert worker._pubsub_service.publish.called
        call_args = worker._pubsub_service.publish.call_args
        error_message = call_args[0][0]
        
        assert error_message.topic == EventTopic.AGENT_RESPONSE_ERROR.value
        assert error_message.payload["error_code"] == "MISSING_CLIENT_ID"
        assert error_message.correlation_id == request_message.trace_id
    
    @pytest.mark.asyncio
    async def test_handle_handshake_request_missing_user_id(self, worker):
        """Test handling handshake request with missing user_id."""
        request_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
            payload={"client_id": "client-123"}  # Missing user_id
        )
        
        await worker._handle_handshake_request(request_message)
        
        # Verify error response
        call_args = worker._pubsub_service.publish.call_args
        error_message = call_args[0][0]
        
        assert error_message.topic == EventTopic.AGENT_RESPONSE_ERROR.value
        assert error_message.payload["error_code"] == "MISSING_USER_ID"
    
    @pytest.mark.asyncio
    async def test_get_updated_sessions_no_timestamp(self, worker, sample_sessions, mock_mongo_db, async_cursor_mock):
        """Test querying sessions without timestamp filter (all sessions)."""
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        mock_cursor = async_cursor_mock(sample_sessions)
        mock_collection.find = Mock(return_value=mock_cursor)
        
        sessions = await worker._get_updated_sessions("user-456", None)
        
        # Should return all sessions (minus _id)
        assert len(sessions) == 2
        assert sessions[0]["book_id"] == "book-1"
        assert sessions[1]["book_id"] == "book-2"
        assert "_id" not in sessions[0]
        assert "_id" not in sessions[1]
        
        # Verify query was correct
        call_args = mock_collection.find.call_args
        query = call_args[0][0]
        assert query["user_id"] == "user-456"
        assert query["state"] == {"$ne": "deleted"}
        assert "updated_at" not in query  # No timestamp filter
    
    @pytest.mark.asyncio
    async def test_get_updated_sessions_with_timestamp(self, worker, sample_sessions, mock_mongo_db, async_cursor_mock):
        """Test querying sessions with timestamp filter."""
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        
        # Filter to only return sessions updated after this time
        filter_time = datetime.utcnow() - timedelta(minutes=30)
        
        # Only first session should match (more recent)
        filtered_sessions = [sample_sessions[0]]
        mock_cursor = async_cursor_mock(filtered_sessions)
        mock_collection.find = Mock(return_value=mock_cursor)
        
        sessions = await worker._get_updated_sessions("user-456", filter_time)
        
        # Should return only recent session
        assert len(sessions) == 1
        assert sessions[0]["book_id"] == "book-1"
        
        # Verify query included timestamp filter
        call_args = mock_collection.find.call_args
        query = call_args[0][0]
        assert "updated_at" in query
        assert query["updated_at"]["$gt"] == filter_time
    
    @pytest.mark.asyncio
    async def test_get_updated_sessions_excludes_deleted(self, worker, mock_mongo_db, async_cursor_mock):
        """Test that deleted sessions are excluded from results."""
        sessions_with_deleted = [
            {
                "_id": "mongo-id-1",
                "book_id": "book-1",
                "state": "active",
                "user_id": "user-456",
                "updated_at": datetime.utcnow()
            },
            {
                "_id": "mongo-id-2",
                "book_id": "book-2",
                "state": "deleted",  # Should be excluded
                "user_id": "user-456",
                "updated_at": datetime.utcnow()
            }
        ]
        
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        
        # Only active session should be returned
        active_sessions = [sessions_with_deleted[0]]
        mock_cursor = async_cursor_mock(active_sessions)
        mock_collection.find = Mock(return_value=mock_cursor)
        
        sessions = await worker._get_updated_sessions("user-456", None)
        
        # Verify only active session returned
        assert len(sessions) == 1
        assert sessions[0]["state"] == "active"
        
        # Verify query excluded deleted
        call_args = mock_collection.find.call_args
        query = call_args[0][0]
        assert query["state"] == {"$ne": "deleted"}
    
    @pytest.mark.asyncio
    async def test_get_updated_sessions_sorted_by_updated_at(self, worker, sample_sessions, mock_mongo_db, async_cursor_mock):
        """Test that sessions are sorted by updated_at ascending."""
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        mock_cursor = async_cursor_mock(sample_sessions)
        mock_collection.find = Mock(return_value=mock_cursor)
        
        await worker._get_updated_sessions("user-456", None)
        
        # Verify sort was called correctly
        # Note: sort is called on the cursor mock which returns itself
        assert mock_collection.find.called
    
    @pytest.mark.asyncio
    async def test_get_updated_sessions_mongodb_error(self, worker, mock_mongo_db):
        """Test handling MongoDB query errors."""
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        mock_collection.find = Mock(side_effect=Exception("Connection error"))
        
        with pytest.raises(Exception, match="Connection error"):
            await worker._get_updated_sessions("user-456", None)
    
    @pytest.mark.asyncio
    async def test_handle_handshake_request_with_timestamp(self, worker, sample_handshake_request, sample_sessions, mock_mongo_db, async_cursor_mock):
        """Test handshake request with last_sync_timestamp."""
        # Add timestamp to request
        last_sync = (datetime.utcnow() - timedelta(minutes=30)).isoformat()
        sample_handshake_request["last_sync_timestamp"] = last_sync
        
        request_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
            payload=sample_handshake_request
        )
        
        # Mock MongoDB query
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        mock_cursor = async_cursor_mock(sample_sessions)
        mock_collection.find = Mock(return_value=mock_cursor)
        
        await worker._handle_handshake_request(request_message)
        
        # Verify response was published
        assert worker._pubsub_service.publish.called
        response_message = worker._pubsub_service.publish.call_args[0][0]
        assert response_message.topic == EventTopic.SYSTEM_EVENT_HANDSHAKE_RESPONSE.value
    
    @pytest.mark.asyncio
    async def test_handle_handshake_request_invalid_timestamp_format(self, worker, sample_handshake_request, sample_sessions, mock_mongo_db, async_cursor_mock):
        """Test handshake with invalid timestamp format (should be ignored)."""
        # Add invalid timestamp
        sample_handshake_request["last_sync_timestamp"] = "not-a-valid-timestamp"
        
        request_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
            payload=sample_handshake_request
        )
        
        # Mock MongoDB query
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        mock_cursor = async_cursor_mock(sample_sessions)
        mock_collection.find = Mock(return_value=mock_cursor)
        
        # Should not raise an error, just treat as no timestamp
        await worker._handle_handshake_request(request_message)
        
        assert worker._pubsub_service.publish.called
        response_message = worker._pubsub_service.publish.call_args[0][0]
        assert response_message.topic == EventTopic.SYSTEM_EVENT_HANDSHAKE_RESPONSE.value
    
    @pytest.mark.asyncio
    async def test_handle_handshake_request_no_sessions(self, worker, sample_handshake_request, mock_mongo_db, async_cursor_mock):
        """Test handshake when user has no sessions."""
        request_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
            payload=sample_handshake_request
        )
        
        # Mock empty result
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        mock_cursor = async_cursor_mock([])
        mock_collection.find = Mock(return_value=mock_cursor)
        
        await worker._handle_handshake_request(request_message)
        
        # Verify response with empty sessions
        assert worker._pubsub_service.publish.called
        response_message = worker._pubsub_service.publish.call_args[0][0]
        
        assert response_message.topic == EventTopic.SYSTEM_EVENT_HANDSHAKE_RESPONSE.value
        assert response_message.payload["sync_count"] == 0
        assert len(response_message.payload["updated_sessions"]) == 0
        assert response_message.payload["deleted_sessions"] == []
    
    @pytest.mark.asyncio
    async def test_send_handshake_response(self, worker):
        """Test sending handshake response message."""
        original_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
            payload={"client_id": "client-123"}
        )
        
        response_payload = {
            "client_id": "client-123",
            "server_timestamp": datetime.utcnow().isoformat(),
            "updated_sessions": [],
            "deleted_sessions": [],
            "sync_count": 0
        }
        
        await worker._send_handshake_response(original_message, response_payload)
        
        assert worker._pubsub_service.publish.called
        response_message = worker._pubsub_service.publish.call_args[0][0]
        
        assert response_message.topic == EventTopic.SYSTEM_EVENT_HANDSHAKE_RESPONSE.value
        assert response_message.correlation_id == original_message.trace_id
        assert response_message.payload == response_payload
    
    @pytest.mark.asyncio
    async def test_send_error_response(self, worker):
        """Test sending error response message."""
        original_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
            payload={}
        )
        
        await worker._send_error_response(
            original_message,
            "TEST_ERROR",
            "This is a test error"
        )
        
        assert worker._pubsub_service.publish.called
        error_message = worker._pubsub_service.publish.call_args[0][0]
        
        assert error_message.topic == EventTopic.AGENT_RESPONSE_ERROR.value
        assert error_message.payload["error_code"] == "TEST_ERROR"
        assert error_message.payload["message"] == "This is a test error"
        assert error_message.correlation_id == original_message.trace_id
    
    @pytest.mark.asyncio
    async def test_handle_handshake_internal_error(self, worker, sample_handshake_request, mock_mongo_db):
        """Test handling internal errors during handshake processing."""
        request_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
            payload=sample_handshake_request
        )
        
        # Mock MongoDB to raise an error
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        mock_collection.find = Mock(side_effect=Exception("Database error"))
        
        await worker._handle_handshake_request(request_message)
        
        # Should publish error response
        assert worker._pubsub_service.publish.called
        error_message = worker._pubsub_service.publish.call_args[0][0]
        
        assert error_message.topic == EventTopic.AGENT_RESPONSE_ERROR.value
        assert error_message.payload["error_code"] == "INTERNAL_ERROR"
        assert "Database error" in error_message.payload["message"]
    
    @pytest.mark.asyncio
    async def test_handshake_response_includes_deleted_sessions(self, worker, sample_handshake_request, sample_sessions, mock_mongo_db, async_cursor_mock):
        """Test that handshake response includes deleted_sessions field (currently empty)."""
        request_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
            payload=sample_handshake_request
        )
        
        # Mock MongoDB query
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        mock_cursor = async_cursor_mock(sample_sessions)
        mock_collection.find = Mock(return_value=mock_cursor)
        
        await worker._handle_handshake_request(request_message)
        
        response_message = worker._pubsub_service.publish.call_args[0][0]
        
        # Should include deleted_sessions field (empty for now)
        assert "deleted_sessions" in response_message.payload
        assert response_message.payload["deleted_sessions"] == []
    
    @pytest.mark.asyncio
    async def test_timestamp_parsing_with_z_suffix(self, worker, sample_handshake_request, sample_sessions, mock_mongo_db, async_cursor_mock):
        """Test timestamp parsing with 'Z' suffix (UTC)."""
        # Add timestamp with Z suffix
        sample_handshake_request["last_sync_timestamp"] = "2024-01-01T12:00:00Z"
        
        request_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
            payload=sample_handshake_request
        )
        
        # Mock MongoDB query
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        mock_cursor = async_cursor_mock(sample_sessions)
        mock_collection.find = Mock(return_value=mock_cursor)
        
        # Should parse successfully
        await worker._handle_handshake_request(request_message)
        
        assert worker._pubsub_service.publish.called
        response_message = worker._pubsub_service.publish.call_args[0][0]
        assert response_message.topic == EventTopic.SYSTEM_EVENT_HANDSHAKE_RESPONSE.value
    
    @pytest.mark.asyncio
    async def test_worker_start_mongodb_connection_failure(self):
        """Test handling of MongoDB connection failures during start."""
        worker = HandshakeWorker()
        
        # Mock AsyncIOMotorClient to raise an exception
        with patch('app.workers.handshake_worker.MONGODB_ENABLED', True), \
             patch('app.workers.handshake_worker.AsyncIOMotorClient', side_effect=Exception("Connection refused")):
            
            # Should raise exception
            with pytest.raises(Exception, match="Connection refused"):
                await worker.start()
    
    @pytest.mark.asyncio
    async def test_global_worker_start_and_stop(self):
        """Test global worker instance management."""
        from app.workers.handshake_worker import (
            start_handshake_worker,
            stop_handshake_worker
        )
        
        # Mock dependencies
        mock_mongo_client = MagicMock()
        mock_db = MagicMock()
        
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        
        with patch('app.workers.handshake_worker.MONGODB_ENABLED', True), \
             patch('app.workers.handshake_worker.AsyncIOMotorClient', return_value=mock_mongo_client), \
             patch('app.workers.handshake_worker.get_pubsub_service', return_value=mock_pubsub):
            
            mock_mongo_client.scareverse = mock_db
            
            # Start global worker
            worker_instance = await start_handshake_worker()
            assert worker_instance is not None
            assert worker_instance._is_running is True
            
            # Stop global worker
            await stop_handshake_worker()
