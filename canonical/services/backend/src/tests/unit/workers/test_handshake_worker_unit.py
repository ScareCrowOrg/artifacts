"""
Unit tests for HandshakeWorker.

Tests cover:
- Initialization and lifecycle
- Handshake request handling
- Session querying and filtering
- Response generation
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

from app.workers.handshake_worker import HandshakeWorker, start_handshake_worker, stop_handshake_worker
from app.models.event_bus import MessageEnvelope, EventTopic


@pytest.fixture
def mock_mongodb_uri():
    """Provide mock MongoDB URI."""
    return "mongodb://localhost:27017/test_db"


@pytest.fixture
def handshake_worker(mock_mongodb_uri):
    """Create a HandshakeWorker instance."""
    return HandshakeWorker(mongodb_uri=mock_mongodb_uri)


@pytest.fixture
def sample_handshake_request():
    """Create a sample handshake request message."""
    return MessageEnvelope(
        source="test-client",
        topic=EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
        payload={
            "client_id": "client-123",
            "user_id": "user-456",
            "last_sync_timestamp": "2024-01-01T00:00:00Z"
        },
        trace_id="trace-789"
    )


@pytest.fixture
def sample_sessions():
    """Create sample session data."""
    return [
        {
            "_id": "session-1",
            "session_id": "session-1",
            "user_id": "user-456",
            "state": "active",
            "updated_at": datetime(2024, 1, 2, 0, 0, 0),
            "data": {"key": "value1"}
        },
        {
            "_id": "session-2",
            "session_id": "session-2",
            "user_id": "user-456",
            "state": "active",
            "updated_at": datetime(2024, 1, 3, 0, 0, 0),
            "data": {"key": "value2"}
        }
    ]


class TestHandshakeWorkerInitialization:
    """Test HandshakeWorker initialization."""
    
    def test_init_with_custom_uri(self, mock_mongodb_uri):
        """Test initialization with custom MongoDB URI."""
        worker = HandshakeWorker(mongodb_uri=mock_mongodb_uri)
        
        assert worker.mongodb_uri == mock_mongodb_uri
        assert not worker._is_running
        assert worker._pubsub_service is None
        assert worker._mongo_client is None
        assert worker._db is None
    
    @patch('app.workers.handshake_worker.get_mongodb_uri')
    def test_init_without_uri_uses_config(self, mock_get_uri):
        """Test initialization without URI uses config."""
        mock_get_uri.return_value = "mongodb://config-uri:27017/db"
        
        worker = HandshakeWorker()
        
        assert worker.mongodb_uri == "mongodb://config-uri:27017/db"
        mock_get_uri.assert_called_once()


class TestHandshakeWorkerLifecycle:
    """Test worker lifecycle (start/stop)."""
    
    @pytest.mark.asyncio
    @patch('app.workers.handshake_worker.MONGODB_ENABLED', True)
    @patch('app.workers.handshake_worker.get_pubsub_service')
    @patch('app.workers.handshake_worker.AsyncIOMotorClient')
    async def test_start_success(self, mock_client_class, mock_get_pubsub, handshake_worker):
        """Test successful worker start."""
        # Setup mocks
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_get_pubsub.return_value = mock_pubsub
        
        # Start worker
        await handshake_worker.start()
        
        # Verify
        assert handshake_worker._is_running
        assert handshake_worker._mongo_client == mock_client
        assert handshake_worker._pubsub_service == mock_pubsub
        mock_pubsub.subscribe.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('app.workers.handshake_worker.MONGODB_ENABLED', False)
    async def test_start_when_mongodb_disabled(self, handshake_worker):
        """Test start when MongoDB is disabled."""
        await handshake_worker.start()
        
        # Worker should not start
        assert not handshake_worker._is_running
        assert handshake_worker._mongo_client is None
    
    @pytest.mark.asyncio
    @patch('app.workers.handshake_worker.MONGODB_ENABLED', True)
    @patch('app.workers.handshake_worker.AsyncIOMotorClient')
    async def test_start_mongodb_connection_failure(self, mock_client_class, handshake_worker):
        """Test start when MongoDB connection fails."""
        mock_client_class.side_effect = Exception("Connection failed")
        
        with pytest.raises(Exception, match="Connection failed"):
            await handshake_worker.start()
        
        assert not handshake_worker._is_running
    
    @pytest.mark.asyncio
    async def test_start_when_already_running(self, handshake_worker):
        """Test start when worker is already running."""
        handshake_worker._is_running = True
        
        await handshake_worker.start()
        
        # Should remain running without error
        assert handshake_worker._is_running
    
    @pytest.mark.asyncio
    async def test_stop_success(self, handshake_worker):
        """Test successful worker stop."""
        # Setup running worker
        handshake_worker._is_running = True
        handshake_worker._mongo_client = MagicMock()
        handshake_worker._mongo_client.close = MagicMock()
        
        mock_pubsub = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        handshake_worker._pubsub_service = mock_pubsub
        
        # Stop worker
        await handshake_worker.stop()
        
        # Verify
        assert not handshake_worker._is_running
        mock_pubsub.unsubscribe.assert_called_once()
        handshake_worker._mongo_client.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, handshake_worker):
        """Test stop when worker is not running."""
        await handshake_worker.stop()
        
        # Should complete without error
        assert not handshake_worker._is_running


class TestHandshakeRequestHandling:
    """Test handshake request processing."""
    
    @pytest.mark.asyncio
    async def test_handle_valid_handshake_request(
        self, handshake_worker, sample_handshake_request, sample_sessions
    ):
        """Test handling a valid handshake request."""
        # Setup mocks
        handshake_worker._get_updated_sessions = AsyncMock(return_value=[
            {k: v for k, v in session.items() if k != "_id"}
            for session in sample_sessions
        ])
        handshake_worker._send_handshake_response = AsyncMock()
        
        # Handle request
        await handshake_worker._handle_handshake_request(sample_handshake_request)
        
        # Verify session query called
        handshake_worker._get_updated_sessions.assert_called_once()
        call_args = handshake_worker._get_updated_sessions.call_args
        assert call_args[0][0] == "user-456"
        
        # Verify response sent
        handshake_worker._send_handshake_response.assert_called_once()
        response_payload = handshake_worker._send_handshake_response.call_args[0][1]
        assert response_payload["client_id"] == "client-123"
        assert response_payload["sync_count"] == 2
        assert len(response_payload["updated_sessions"]) == 2
    
    @pytest.mark.asyncio
    async def test_handle_request_missing_client_id(self, handshake_worker):
        """Test handling request with missing client_id."""
        request = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
            payload={
                "user_id": "user-456"
            },
            trace_id="trace-789"
        )
        
        handshake_worker._send_error_response = AsyncMock()
        
        await handshake_worker._handle_handshake_request(request)
        
        # Verify error response sent
        handshake_worker._send_error_response.assert_called_once()
        call_args = handshake_worker._send_error_response.call_args[0]
        assert call_args[1] == "MISSING_CLIENT_ID"
    
    @pytest.mark.asyncio
    async def test_handle_request_missing_user_id(self, handshake_worker):
        """Test handling request with missing user_id."""
        request = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
            payload={
                "client_id": "client-123"
            },
            trace_id="trace-789"
        )
        
        handshake_worker._send_error_response = AsyncMock()
        
        await handshake_worker._handle_handshake_request(request)
        
        # Verify error response sent
        handshake_worker._send_error_response.assert_called_once()
        call_args = handshake_worker._send_error_response.call_args[0]
        assert call_args[1] == "MISSING_USER_ID"
    
    @pytest.mark.asyncio
    async def test_handle_request_with_invalid_timestamp(
        self, handshake_worker, sample_sessions
    ):
        """Test handling request with invalid timestamp format."""
        request = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
            payload={
                "client_id": "client-123",
                "user_id": "user-456",
                "last_sync_timestamp": "invalid-timestamp"
            },
            trace_id="trace-789"
        )
        
        handshake_worker._get_updated_sessions = AsyncMock(return_value=[])
        handshake_worker._send_handshake_response = AsyncMock()
        
        # Should handle gracefully and call with None timestamp
        await handshake_worker._handle_handshake_request(request)
        
        # Verify session query called with None timestamp
        call_args = handshake_worker._get_updated_sessions.call_args[0]
        assert call_args[1] is None
    
    @pytest.mark.asyncio
    async def test_handle_request_without_timestamp(
        self, handshake_worker, sample_sessions
    ):
        """Test handling request without timestamp (full sync)."""
        request = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
            payload={
                "client_id": "client-123",
                "user_id": "user-456"
            },
            trace_id="trace-789"
        )
        
        handshake_worker._get_updated_sessions = AsyncMock(return_value=[])
        handshake_worker._send_handshake_response = AsyncMock()
        
        await handshake_worker._handle_handshake_request(request)
        
        # Verify session query called with None timestamp (full sync)
        call_args = handshake_worker._get_updated_sessions.call_args[0]
        assert call_args[1] is None
    
    @pytest.mark.asyncio
    async def test_handle_request_internal_error(self, handshake_worker):
        """Test handling when internal error occurs."""
        request = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
            payload={
                "client_id": "client-123",
                "user_id": "user-456"
            },
            trace_id="trace-789"
        )
        
        handshake_worker._get_updated_sessions = AsyncMock(
            side_effect=Exception("Database error")
        )
        handshake_worker._send_error_response = AsyncMock()
        
        await handshake_worker._handle_handshake_request(request)
        
        # Verify error response sent
        handshake_worker._send_error_response.assert_called_once()
        call_args = handshake_worker._send_error_response.call_args[0]
        assert call_args[1] == "INTERNAL_ERROR"
        assert "Database error" in call_args[2]


class TestSessionQuerying:
    """Test session querying functionality."""
    
    @pytest.mark.asyncio
    async def test_get_updated_sessions_with_timestamp(
        self, handshake_worker, sample_sessions
    ):
        """Test querying sessions updated after timestamp."""
        # Setup mock MongoDB
        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        
        # Create async iterator
        async def async_iter():
            for session in sample_sessions:
                yield session
        
        mock_cursor.__aiter__ = lambda self: async_iter()
        
        mock_collection = MagicMock()
        mock_collection.find = MagicMock(return_value=mock_cursor)
        
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        handshake_worker._db = mock_db
        
        # Query sessions
        last_sync = datetime(2024, 1, 1, 0, 0, 0)
        result = await handshake_worker._get_updated_sessions("user-456", last_sync)
        
        # Verify query
        mock_collection.find.assert_called_once()
        query = mock_collection.find.call_args[0][0]
        assert query["user_id"] == "user-456"
        assert query["state"] == {"$ne": "deleted"}
        assert query["updated_at"] == {"$gt": last_sync}
        
        # Verify result
        assert len(result) == 2
        assert all("_id" not in session for session in result)
    
    @pytest.mark.asyncio
    async def test_get_updated_sessions_without_timestamp(
        self, handshake_worker, sample_sessions
    ):
        """Test querying all sessions (full sync)."""
        # Setup mock MongoDB
        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        
        async def async_iter():
            for session in sample_sessions:
                yield session
        
        mock_cursor.__aiter__ = lambda self: async_iter()
        
        mock_collection = MagicMock()
        mock_collection.find = MagicMock(return_value=mock_cursor)
        
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        handshake_worker._db = mock_db
        
        # Query sessions without timestamp
        result = await handshake_worker._get_updated_sessions("user-456", None)
        
        # Verify query doesn't filter by updated_at
        query = mock_collection.find.call_args[0][0]
        assert "updated_at" not in query
        assert query["user_id"] == "user-456"
    
    @pytest.mark.asyncio
    async def test_get_updated_sessions_excludes_deleted(self, handshake_worker):
        """Test that deleted sessions are excluded."""
        sessions_with_deleted = [
            {
                "_id": "session-1",
                "user_id": "user-456",
                "state": "active",
                "updated_at": datetime(2024, 1, 2, 0, 0, 0)
            },
            {
                "_id": "session-2",
                "user_id": "user-456",
                "state": "deleted",
                "updated_at": datetime(2024, 1, 3, 0, 0, 0)
            }
        ]
        
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        
        async def async_iter():
            # Only yield non-deleted (MongoDB would filter)
            yield sessions_with_deleted[0]
        
        mock_cursor.__aiter__ = lambda self: async_iter()
        
        mock_collection = MagicMock()
        mock_collection.find = MagicMock(return_value=mock_cursor)
        
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        handshake_worker._db = mock_db
        
        result = await handshake_worker._get_updated_sessions("user-456", None)
        
        # Verify only active session returned
        assert len(result) == 1
        assert result[0]["state"] == "active"
    
    @pytest.mark.asyncio
    async def test_get_updated_sessions_database_error(self, handshake_worker):
        """Test handling database query error."""
        mock_collection = MagicMock()
        mock_collection.find = MagicMock(side_effect=Exception("DB connection lost"))
        
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        handshake_worker._db = mock_db
        
        with pytest.raises(Exception, match="DB connection lost"):
            await handshake_worker._get_updated_sessions("user-456", None)


class TestResponseGeneration:
    """Test response message generation."""
    
    @pytest.mark.asyncio
    async def test_send_handshake_response(self, handshake_worker, sample_handshake_request):
        """Test sending handshake response."""
        mock_pubsub = AsyncMock()
        mock_pubsub.publish = AsyncMock()
        handshake_worker._pubsub_service = mock_pubsub
        
        payload = {
            "client_id": "client-123",
            "server_timestamp": "2024-01-01T12:00:00",
            "updated_sessions": [],
            "deleted_sessions": [],
            "sync_count": 0
        }
        
        await handshake_worker._send_handshake_response(
            sample_handshake_request,
            payload
        )
        
        # Verify publish called
        mock_pubsub.publish.assert_called_once()
        
        # Verify message structure
        published_message = mock_pubsub.publish.call_args[0][0]
        assert published_message.source == "backend-handshake-worker"
        assert published_message.topic == EventTopic.SYSTEM_EVENT_HANDSHAKE_RESPONSE.value
        assert published_message.payload == payload
        assert published_message.correlation_id == sample_handshake_request.trace_id
    
    @pytest.mark.asyncio
    async def test_send_error_response(self, handshake_worker, sample_handshake_request):
        """Test sending error response."""
        mock_pubsub = AsyncMock()
        mock_pubsub.publish = AsyncMock()
        handshake_worker._pubsub_service = mock_pubsub
        
        await handshake_worker._send_error_response(
            sample_handshake_request,
            "TEST_ERROR",
            "Test error message"
        )
        
        # Verify publish called
        mock_pubsub.publish.assert_called_once()
        
        # Verify error message structure
        published_message = mock_pubsub.publish.call_args[0][0]
        assert published_message.topic == EventTopic.AGENT_RESPONSE_ERROR.value
        assert published_message.payload["error_code"] == "TEST_ERROR"
        assert published_message.payload["message"] == "Test error message"


class TestGlobalWorkerManagement:
    """Test global worker instance management."""
    
    @pytest.mark.asyncio
    @patch('app.workers.handshake_worker.HandshakeWorker')
    async def test_start_handshake_worker_creates_instance(self, mock_worker_class):
        """Test starting global worker creates instance."""
        mock_instance = AsyncMock()
        mock_instance.start = AsyncMock()
        mock_worker_class.return_value = mock_instance
        
        # Reset global worker
        import app.workers.handshake_worker
        app.workers.handshake_worker._worker = None
        
        result = await start_handshake_worker()
        
        assert result == mock_instance
        mock_instance.start.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('app.workers.handshake_worker.HandshakeWorker')
    async def test_start_handshake_worker_reuses_instance(self, mock_worker_class):
        """Test starting global worker reuses existing instance."""
        mock_instance = AsyncMock()
        mock_instance.start = AsyncMock()
        
        # Set existing global worker
        import app.workers.handshake_worker
        app.workers.handshake_worker._worker = mock_instance
        
        result = await start_handshake_worker()
        
        assert result == mock_instance
        mock_instance.start.assert_called_once()
        # Worker class should not be instantiated again
        mock_worker_class.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_stop_handshake_worker(self):
        """Test stopping global worker."""
        mock_instance = AsyncMock()
        mock_instance.stop = AsyncMock()
        
        # Set global worker
        import app.workers.handshake_worker
        app.workers.handshake_worker._worker = mock_instance
        
        await stop_handshake_worker()
        
        mock_instance.stop.assert_called_once()
        assert app.workers.handshake_worker._worker is None
    
    @pytest.mark.asyncio
    async def test_stop_handshake_worker_when_none(self):
        """Test stopping when no global worker exists."""
        import app.workers.handshake_worker
        app.workers.handshake_worker._worker = None
        
        # Should complete without error
        await stop_handshake_worker()
        
        assert app.workers.handshake_worker._worker is None
