"""
Unit tests for LogCollectionWorker.

Tests cover:
- Initialization and lifecycle
- Log event handling
- Batch processing
- MongoDB operations
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime
import asyncio

from app.workers.log_collection_worker import LogCollectionWorker
from app.models.event_bus import MessageEnvelope, EventTopic


@pytest.fixture
def mock_mongodb_uri():
    """Provide mock MongoDB URI."""
    return "mongodb://localhost:27017/test_db"


@pytest.fixture
def log_worker(mock_mongodb_uri):
    """Create a LogCollectionWorker instance."""
    return LogCollectionWorker(mongodb_uri=mock_mongodb_uri, batch_interval=0.1)


@pytest.fixture
def sample_error_message():
    """Create a sample error message."""
    return MessageEnvelope(
        source="test-service",
        topic=EventTopic.SYSTEM_EVENT_ERROR.value,
        payload={
            "message": "Test error occurred",
            "error_code": "TEST_ERROR",
            "stack_trace": "Traceback...",
            "details": {
                "user_id": "user-123",
                "client_id": "client-456"
            }
        },
        trace_id="trace-789"
    )


class TestLogCollectionWorkerInitialization:
    """Test LogCollectionWorker initialization."""
    
    def test_init_with_custom_settings(self, mock_mongodb_uri):
        """Test initialization with custom settings."""
        worker = LogCollectionWorker(
            mongodb_uri=mock_mongodb_uri,
            batch_interval=5.0
        )
        
        assert worker.mongodb_uri == mock_mongodb_uri
        assert worker.batch_interval == 5.0
        assert not worker._is_running
        assert worker._pubsub_service is None
        assert worker._mongo_client is None
        assert worker._db is None
        assert worker._batch_queue == []
    
    @patch('app.workers.log_collection_worker.get_mongodb_uri')
    def test_init_without_uri_uses_config(self, mock_get_uri):
        """Test initialization without URI uses config."""
        mock_get_uri.return_value = "mongodb://config-uri:27017/db"
        
        worker = LogCollectionWorker()
        
        assert worker.mongodb_uri == "mongodb://config-uri:27017/db"


class TestLogCollectionWorkerLifecycle:
    """Test worker lifecycle (start/stop)."""
    
    @pytest.mark.asyncio
    @patch('app.workers.log_collection_worker.MONGODB_ENABLED', True)
    @patch('app.workers.log_collection_worker.get_pubsub_service')
    @patch('app.workers.log_collection_worker.AsyncIOMotorClient')
    async def test_start_success(self, mock_client_class, mock_get_pubsub, log_worker):
        """Test successful worker start."""
        # Setup mocks
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.create_index = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_client.scareverse = mock_db
        mock_client_class.return_value = mock_client
        
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_get_pubsub.return_value = mock_pubsub
        
        # Start worker
        await log_worker.start()
        
        # Verify
        assert log_worker._is_running
        assert log_worker._mongo_client == mock_client
        assert log_worker._pubsub_service == mock_pubsub
        assert log_worker._batch_task is not None
        mock_pubsub.subscribe.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('app.workers.log_collection_worker.MONGODB_ENABLED', False)
    async def test_start_when_mongodb_disabled(self, log_worker):
        """Test start when MongoDB is disabled."""
        await log_worker.start()
        
        # Worker should not start
        assert not log_worker._is_running
        assert log_worker._mongo_client is None
    
    @pytest.mark.asyncio
    async def test_start_when_already_running(self, log_worker):
        """Test start when worker is already running."""
        log_worker._is_running = True
        
        await log_worker.start()
        
        # Should remain running without error
        assert log_worker._is_running
    
    @pytest.mark.asyncio
    async def test_stop_success(self, log_worker):
        """Test successful worker stop."""
        # Setup running worker
        log_worker._is_running = True
        log_worker._mongo_client = MagicMock()
        log_worker._mongo_client.close = MagicMock()
        
        mock_pubsub = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        log_worker._pubsub_service = mock_pubsub
        
        # Mock batch task as an async task
        async def dummy_task():
            pass
        
        mock_task = asyncio.create_task(dummy_task())
        log_worker._batch_task = mock_task
        
        # Mock flush
        log_worker._flush_batch = AsyncMock()
        
        # Stop worker
        await log_worker.stop()
        
        # Verify
        assert not log_worker._is_running
        mock_pubsub.unsubscribe.assert_called_once()
        log_worker._flush_batch.assert_called_once()
        log_worker._mongo_client.close.assert_called_once()


class TestLogEventHandling:
    """Test log event handling."""
    
    @pytest.mark.asyncio
    async def test_handle_error_event(self, log_worker, sample_error_message):
        """Test handling error event."""
        await log_worker._handle_log_event(sample_error_message)
        
        # Verify log was added to batch queue
        assert len(log_worker._batch_queue) == 1
        
        log_entry = log_worker._batch_queue[0]
        assert log_entry["log_id"] == "trace-789"
        assert log_entry["level"] == "error"
        assert log_entry["source"] == "test-service"
        assert log_entry["message"] == "Test error occurred"
        assert log_entry["stack_trace"] == "Traceback..."
        assert log_entry["user_id"] == "user-123"
        assert log_entry["context"]["error_code"] == "TEST_ERROR"
    
    @pytest.mark.asyncio
    async def test_handle_event_with_minimal_payload(self, log_worker):
        """Test handling event with minimal payload."""
        minimal_message = MessageEnvelope(
            source="minimal-service",
            topic=EventTopic.SYSTEM_EVENT_ERROR.value,
            payload={},
            trace_id="minimal-trace"
        )
        
        await log_worker._handle_log_event(minimal_message)
        
        assert len(log_worker._batch_queue) == 1
        log_entry = log_worker._batch_queue[0]
        assert log_entry["message"] == "No message provided"
        assert log_entry["level"] == "error"
    
    @pytest.mark.asyncio
    async def test_handle_multiple_events(self, log_worker, sample_error_message):
        """Test handling multiple events in batch queue."""
        # Add multiple events
        await log_worker._handle_log_event(sample_error_message)
        await log_worker._handle_log_event(sample_error_message)
        await log_worker._handle_log_event(sample_error_message)
        
        # Verify all added to queue
        assert len(log_worker._batch_queue) == 3
    
    @pytest.mark.asyncio
    async def test_handle_event_error_handling(self, log_worker):
        """Test error handling during event processing."""
        # Create malformed message
        malformed_message = MagicMock()
        malformed_message.payload = None  # Will cause AttributeError
        
        # Should not raise exception
        await log_worker._handle_log_event(malformed_message)
        
        # Queue should remain empty
        assert len(log_worker._batch_queue) == 0


class TestBatchProcessing:
    """Test batch processing functionality."""
    
    @pytest.mark.asyncio
    async def test_flush_batch_with_logs(self, log_worker, sample_error_message):
        """Test flushing batch with log entries."""
        # Setup MongoDB mock
        mock_collection = MagicMock()
        mock_collection.insert_many = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        log_worker._db = mock_db
        
        # Add logs to queue
        await log_worker._handle_log_event(sample_error_message)
        await log_worker._handle_log_event(sample_error_message)
        
        # Flush batch
        await log_worker._flush_batch()
        
        # Verify queue is cleared
        assert len(log_worker._batch_queue) == 0
        
        # Verify insert was called
        mock_collection.insert_many.assert_called_once()
        inserted_logs = mock_collection.insert_many.call_args[0][0]
        assert len(inserted_logs) == 2
    
    @pytest.mark.asyncio
    async def test_flush_batch_when_empty(self, log_worker):
        """Test flushing empty batch."""
        # Setup MongoDB mock
        mock_collection = MagicMock()
        mock_collection.insert_many = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        log_worker._db = mock_db
        
        # Flush empty batch
        await log_worker._flush_batch()
        
        # Verify no insert
        mock_collection.insert_many.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_flush_batch_validation_error(self, log_worker):
        """Test flush batch handles validation errors."""
        # Setup MongoDB mock
        mock_collection = MagicMock()
        mock_collection.insert_many = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        log_worker._db = mock_db
        
        # Add invalid log (missing required fields)
        log_worker._batch_queue.append({"invalid": "log"})
        
        # Should handle validation error gracefully
        await log_worker._flush_batch()
        
        # Queue should be cleared
        assert len(log_worker._batch_queue) == 0


class TestIndexCreation:
    """Test MongoDB index creation."""
    
    @pytest.mark.asyncio
    @patch('app.workers.log_collection_worker.LOGS_INDEXES', [
        {
            "name": "timestamp_ttl",
            "keys": [("timestamp", 1)],
            "expireAfterSeconds": 2592000
        }
    ])
    async def test_create_indexes(self, log_worker):
        """Test creating MongoDB indexes."""
        # Setup mock collection
        mock_collection = MagicMock()
        mock_collection.create_index = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        log_worker._db = mock_db
        
        # Create indexes
        await log_worker._create_indexes()
        
        # Verify create_index was called
        mock_collection.create_index.assert_called_once()
        call_args = mock_collection.create_index.call_args
        assert call_args[1]["name"] == "timestamp_ttl"
        assert call_args[1]["expireAfterSeconds"] == 2592000
    
    @pytest.mark.asyncio
    async def test_create_indexes_error_handling(self, log_worker):
        """Test index creation handles errors gracefully."""
        # Setup mock that raises error
        mock_collection = MagicMock()
        mock_collection.create_index = AsyncMock(side_effect=Exception("Index error"))
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        log_worker._db = mock_db
        
        # Should not raise exception
        await log_worker._create_indexes()


class TestBatchProcessorTask:
    """Test batch processor background task."""
    
    @pytest.mark.asyncio
    async def test_batch_processor_periodic_flush(self, log_worker, sample_error_message):
        """Test batch processor flushes periodically."""
        # Setup MongoDB mock
        mock_collection = MagicMock()
        mock_collection.insert_many = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        log_worker._db = mock_db
        
        # Add log to queue
        await log_worker._handle_log_event(sample_error_message)
        
        # Start batch processor
        task = asyncio.create_task(log_worker._batch_processor())
        
        # Wait for at least one flush cycle
        await asyncio.sleep(0.15)  # batch_interval is 0.1s
        
        # Cancel task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Verify queue was flushed
        assert len(log_worker._batch_queue) == 0
    
    @pytest.mark.asyncio
    async def test_batch_processor_handles_errors(self, log_worker):
        """Test batch processor continues after errors."""
        # Mock flush to raise error
        original_flush = log_worker._flush_batch
        error_count = 0
        
        async def mock_flush():
            nonlocal error_count
            error_count += 1
            if error_count == 1:
                raise Exception("Flush error")
            await original_flush()
        
        log_worker._flush_batch = mock_flush
        
        # Start batch processor
        task = asyncio.create_task(log_worker._batch_processor())
        
        # Wait for error and recovery
        await asyncio.sleep(0.25)
        
        # Cancel task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Verify processor continued after error
        assert error_count >= 2


class TestConcurrency:
    """Test concurrent operations."""
    
    @pytest.mark.asyncio
    async def test_concurrent_event_handling(self, log_worker, sample_error_message):
        """Test handling multiple events concurrently."""
        # Handle events concurrently
        tasks = [
            log_worker._handle_log_event(sample_error_message)
            for _ in range(10)
        ]
        await asyncio.gather(*tasks)
        
        # Verify all added to queue
        assert len(log_worker._batch_queue) == 10
    
    @pytest.mark.asyncio
    async def test_flush_during_event_handling(self, log_worker, sample_error_message):
        """Test flushing while events are being added."""
        # Setup MongoDB mock
        mock_collection = MagicMock()
        mock_collection.insert_many = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        log_worker._db = mock_db
        
        # Add events and flush concurrently
        add_tasks = [
            log_worker._handle_log_event(sample_error_message)
            for _ in range(5)
        ]
        flush_task = log_worker._flush_batch()
        
        await asyncio.gather(*add_tasks, flush_task)
        
        # Should not raise any concurrency errors
        assert True
