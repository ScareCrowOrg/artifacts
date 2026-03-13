"""
Integration tests for Log Collection Worker.

Tests log event handling, batching, MongoDB persistence,
and TTL index creation.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from app.workers.log_collection_worker import LogCollectionWorker
from app.models.event_bus import (
    MessageEnvelope,
    EventTopic
)
from app.database.schemas.session_schema import LOGS_COLLECTION
from app.database.schemas.log_schema import LOGS_INDEXES


class TestLogCollectionWorker:
    """Integration tests for log collection worker."""
    
    @pytest.fixture
    def mock_mongo_db(self):
        """Create a mock MongoDB database."""
        mock_db = MagicMock()
        mock_collection = MagicMock()
        
        # Mock collection methods
        mock_collection.create_index = AsyncMock()
        mock_collection.insert_many = AsyncMock()
        
        # Configure database to return collection
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        
        return mock_db
    
    @pytest.fixture
    async def worker(self, mock_mongo_db):
        """Create a worker instance with mocked dependencies."""
        worker = LogCollectionWorker(
            mongodb_uri="mongodb://localhost:27017",
            batch_interval=0.1  # Short interval for testing
        )
        
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
    def sample_error_event(self):
        """Create a sample error event."""
        return MessageEnvelope(
            source="test-service",
            topic=EventTopic.SYSTEM_EVENT_ERROR.value,
            payload={
                "message": "Test error occurred",
                "error_code": "TEST_ERROR",
                "stack_trace": "Line 1\nLine 2\nLine 3",
                "details": {
                    "user_id": "user-123",
                    "client_id": "client-456",
                    "additional_info": "Some context"
                }
            }
        )
    
    @pytest.mark.asyncio
    async def test_worker_initialization(self):
        """Test worker is initialized with correct parameters."""
        worker = LogCollectionWorker(
            mongodb_uri="mongodb://test:27017",
            batch_interval=1.5
        )
        
        assert worker.mongodb_uri == "mongodb://test:27017"
        assert worker.batch_interval == 1.5
        assert worker._is_running is False
        assert worker._batch_queue == []
    
    @pytest.mark.asyncio
    async def test_worker_start_creates_indexes(self, mock_mongo_db):
        """Test that worker creates MongoDB indexes on start including TTL."""
        worker = LogCollectionWorker()
        
        # Mock dependencies
        mock_mongo_client = MagicMock()
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        
        with patch('app.workers.log_collection_worker.MONGODB_ENABLED', True), \
             patch('app.workers.log_collection_worker.AsyncIOMotorClient', return_value=mock_mongo_client), \
             patch('app.workers.log_collection_worker.get_pubsub_service', return_value=mock_pubsub):
            
            mock_mongo_client.scareverse = mock_mongo_db
            
            await worker.start()
            
            assert worker._is_running is True
            assert mock_pubsub.subscribe.called
            
            # Verify indexes were created
            mock_collection = mock_mongo_db[LOGS_COLLECTION]
            assert mock_collection.create_index.called
            
            # Verify TTL index was created
            call_count = mock_collection.create_index.call_count
            assert call_count == len(LOGS_INDEXES)
            
            await worker.stop()
    
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
        worker = LogCollectionWorker()
        
        with patch('app.workers.log_collection_worker.MONGODB_ENABLED', False):
            await worker.start()
            
            assert worker._is_running is False
    
    @pytest.mark.asyncio
    async def test_worker_stop_lifecycle(self):
        """Test worker lifecycle (start/stop)."""
        worker = LogCollectionWorker(batch_interval=0.1)
        
        # Mock dependencies
        mock_mongo_client = MagicMock()
        mock_mongo_client.close = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.create_index = AsyncMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        
        with patch('app.workers.log_collection_worker.MONGODB_ENABLED', True), \
             patch('app.workers.log_collection_worker.AsyncIOMotorClient', return_value=mock_mongo_client), \
             patch('app.workers.log_collection_worker.get_pubsub_service', return_value=mock_pubsub):
            
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
    async def test_handle_log_event_success(self, worker, sample_error_event):
        """Test successfully handling a log event."""
        await worker._handle_log_event(sample_error_event)
        
        # Verify log entry was added to batch queue
        assert len(worker._batch_queue) == 1
        
        log_entry = worker._batch_queue[0]
        assert log_entry["log_id"] == sample_error_event.trace_id
        assert log_entry["level"] == "error"
        assert log_entry["source"] == "test-service"
        assert log_entry["message"] == "Test error occurred"
        assert log_entry["stack_trace"] == "Line 1\nLine 2\nLine 3"
        assert log_entry["user_id"] == "user-123"
        assert log_entry["client_id"] == "client-456"
        assert log_entry["context"]["error_code"] == "TEST_ERROR"
    
    @pytest.mark.asyncio
    async def test_handle_log_event_minimal_payload(self, worker):
        """Test handling log event with minimal payload."""
        minimal_event = MessageEnvelope(
            source="minimal-service",
            topic=EventTopic.SYSTEM_EVENT_ERROR.value,
            payload={}  # Empty payload
        )
        
        await worker._handle_log_event(minimal_event)
        
        # Should still create log entry with defaults
        assert len(worker._batch_queue) == 1
        
        log_entry = worker._batch_queue[0]
        assert log_entry["message"] == "No message provided"
        assert log_entry["level"] == "error"
        assert log_entry["stack_trace"] is None
        assert log_entry["user_id"] is None
    
    @pytest.mark.asyncio
    async def test_handle_log_event_with_details(self, worker):
        """Test that details are included in context."""
        event_with_details = MessageEnvelope(
            source="detail-service",
            topic=EventTopic.SYSTEM_EVENT_ERROR.value,
            payload={
                "message": "Error with details",
                "details": {
                    "request_id": "req-789",
                    "endpoint": "/api/test",
                    "status_code": 500
                }
            }
        )
        
        await worker._handle_log_event(event_with_details)
        
        log_entry = worker._batch_queue[0]
        assert log_entry["context"]["request_id"] == "req-789"
        assert log_entry["context"]["endpoint"] == "/api/test"
        assert log_entry["context"]["status_code"] == 500
    
    @pytest.mark.asyncio
    async def test_batch_processing(self, worker, sample_error_event, mock_mongo_db):
        """Test that batch processing flushes queued log entries."""
        # Add log events to queue
        await worker._handle_log_event(sample_error_event)
        await worker._handle_log_event(sample_error_event)
        
        assert len(worker._batch_queue) == 2
        
        # Mock MongoDB operations
        mock_collection = mock_mongo_db[LOGS_COLLECTION]
        mock_insert_result = MagicMock()
        mock_insert_result.inserted_ids = ["id1", "id2"]
        mock_collection.insert_many = AsyncMock(return_value=mock_insert_result)
        
        # Trigger batch flush
        await worker._flush_batch()
        
        # Verify batch queue was cleared
        assert len(worker._batch_queue) == 0
        
        # Verify MongoDB insert_many was called
        assert mock_collection.insert_many.called
        
        # Verify correct number of logs were inserted
        call_args = mock_collection.insert_many.call_args
        logs_to_insert = call_args[0][0]
        assert len(logs_to_insert) == 2
    
    @pytest.mark.asyncio
    async def test_flush_batch_empty_queue(self, worker):
        """Test flushing an empty batch queue."""
        # Queue is empty
        assert len(worker._batch_queue) == 0
        
        # Should complete without errors
        await worker._flush_batch()
        
        # MongoDB should not be called
        mock_collection = worker._db[LOGS_COLLECTION]
        assert not mock_collection.insert_many.called
    
    @pytest.mark.asyncio
    async def test_flush_batch_validation_error(self, worker, mock_mongo_db):
        """Test handling schema validation errors during flush."""
        # Add invalid log entry to queue
        worker._batch_queue.append({
            # Missing required fields
            "incomplete": "data"
        })
        
        mock_collection = mock_mongo_db[LOGS_COLLECTION]
        mock_collection.insert_many = AsyncMock()
        
        # Should not raise exception, but log validation error
        await worker._flush_batch()
        
        # Queue should be cleared even with validation errors
        assert len(worker._batch_queue) == 0
        
        # insert_many should not be called (no valid logs)
        assert not mock_collection.insert_many.called
    
    @pytest.mark.asyncio
    async def test_flush_batch_partial_validation(self, worker, sample_error_event, mock_mongo_db):
        """Test that valid logs are inserted even if some fail validation."""
        # Add one valid and one invalid log
        await worker._handle_log_event(sample_error_event)
        worker._batch_queue.append({"invalid": "log"})
        
        mock_collection = mock_mongo_db[LOGS_COLLECTION]
        mock_insert_result = MagicMock()
        mock_insert_result.inserted_ids = ["id1"]
        mock_collection.insert_many = AsyncMock(return_value=mock_insert_result)
        
        await worker._flush_batch()
        
        # insert_many should be called with only valid log
        assert mock_collection.insert_many.called
        call_args = mock_collection.insert_many.call_args
        logs_to_insert = call_args[0][0]
        assert len(logs_to_insert) == 1
    
    @pytest.mark.asyncio
    async def test_flush_batch_mongodb_error(self, worker, sample_error_event, mock_mongo_db):
        """Test handling MongoDB insert errors."""
        await worker._handle_log_event(sample_error_event)
        
        mock_collection = mock_mongo_db[LOGS_COLLECTION]
        mock_collection.insert_many = AsyncMock(side_effect=Exception("Connection error"))
        
        # Should not raise exception, but log error
        await worker._flush_batch()
        
        # Queue should still be cleared
        assert len(worker._batch_queue) == 0
    
    @pytest.mark.asyncio
    async def test_concurrent_log_events(self, worker, sample_error_event):
        """Test concurrent log events are safely batched."""
        # Create multiple log events
        events = [
            MessageEnvelope(
                source=f"service-{i}",
                topic=EventTopic.SYSTEM_EVENT_ERROR.value,
                payload={"message": f"Error {i}"}
            )
            for i in range(10)
        ]
        
        # Process all events concurrently
        await asyncio.gather(*[
            worker._handle_log_event(event) for event in events
        ])
        
        # All events should be in the queue
        assert len(worker._batch_queue) == 10
    
    @pytest.mark.asyncio
    async def test_batch_processor_runs_periodically(self, worker, sample_error_event, mock_mongo_db):
        """Test that batch processor runs periodically in background."""
        # Add log event to queue
        await worker._handle_log_event(sample_error_event)
        
        assert len(worker._batch_queue) == 1
        
        # Mock MongoDB operations
        mock_collection = mock_mongo_db[LOGS_COLLECTION]
        mock_insert_result = MagicMock()
        mock_insert_result.inserted_ids = ["id1"]
        mock_collection.insert_many = AsyncMock(return_value=mock_insert_result)
        
        # Start batch processor
        worker._batch_task = asyncio.create_task(worker._batch_processor())
        
        # Wait for batch interval + some margin
        await asyncio.sleep(0.2)
        
        # Stop batch processor
        worker._batch_task.cancel()
        try:
            await worker._batch_task
        except asyncio.CancelledError:
            pass
        
        # Queue should have been flushed
        assert len(worker._batch_queue) == 0
    
    @pytest.mark.asyncio
    async def test_stop_flushes_remaining_batch(self, worker, sample_error_event, mock_mongo_db):
        """Test that stopping worker flushes remaining batched logs."""
        # Add log events to queue
        await worker._handle_log_event(sample_error_event)
        await worker._handle_log_event(sample_error_event)
        
        assert len(worker._batch_queue) == 2
        
        # Mock MongoDB operations
        mock_collection = mock_mongo_db[LOGS_COLLECTION]
        mock_insert_result = MagicMock()
        mock_insert_result.inserted_ids = ["id1", "id2"]
        mock_collection.insert_many = AsyncMock(return_value=mock_insert_result)
        
        # Stop worker (should flush batch)
        await worker.stop()
        
        # Queue should be empty
        assert len(worker._batch_queue) == 0
        
        # MongoDB insert should have been called
        assert mock_collection.insert_many.called
    
    @pytest.mark.asyncio
    async def test_log_entry_includes_timestamp(self, worker, sample_error_event):
        """Test that log entries include timestamp from message."""
        await worker._handle_log_event(sample_error_event)
        
        log_entry = worker._batch_queue[0]
        assert log_entry["timestamp"] == sample_error_event.timestamp
    
    @pytest.mark.asyncio
    async def test_log_entry_includes_correlation_id(self, worker):
        """Test that correlation_id is included in context."""
        event_with_correlation = MessageEnvelope(
            source="test-service",
            topic=EventTopic.SYSTEM_EVENT_ERROR.value,
            payload={"message": "Correlated error"},
            correlation_id="original-trace-123"
        )
        
        await worker._handle_log_event(event_with_correlation)
        
        log_entry = worker._batch_queue[0]
        assert log_entry["context"]["correlation_id"] == "original-trace-123"
    
    @pytest.mark.asyncio
    async def test_log_level_defaults_to_error(self, worker):
        """Test that log level defaults to 'error' for error topic."""
        error_event = MessageEnvelope(
            source="test-service",
            topic=EventTopic.SYSTEM_EVENT_ERROR.value,
            payload={"message": "Error message"}
        )
        
        await worker._handle_log_event(error_event)
        
        log_entry = worker._batch_queue[0]
        assert log_entry["level"] == "error"
    
    @pytest.mark.asyncio
    async def test_handle_log_event_exception_handling(self, worker):
        """Test that exceptions in log handling don't crash worker."""
        # Create event that will cause an exception during processing
        # (e.g., if payload processing fails)
        problematic_event = MessageEnvelope(
            source="test-service",
            topic=EventTopic.SYSTEM_EVENT_ERROR.value,
            payload={"message": "Test"}
        )
        
        # Mock to raise exception
        with patch.object(worker, '_batch_queue', side_effect=Exception("Test exception")):
            # Should not raise exception
            await worker._handle_log_event(problematic_event)
    
    @pytest.mark.asyncio
    async def test_ttl_index_configuration(self, mock_mongo_db):
        """Test that TTL index is configured for 30-day retention."""
        worker = LogCollectionWorker()
        
        # Mock dependencies
        mock_mongo_client = MagicMock()
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        
        with patch('app.workers.log_collection_worker.MONGODB_ENABLED', True), \
             patch('app.workers.log_collection_worker.AsyncIOMotorClient', return_value=mock_mongo_client), \
             patch('app.workers.log_collection_worker.get_pubsub_service', return_value=mock_pubsub):
            
            mock_mongo_client.scareverse = mock_mongo_db
            
            await worker.start()
            
            # Verify TTL index was created
            mock_collection = mock_mongo_db[LOGS_COLLECTION]
            
            # Check if any call included TTL configuration
            ttl_configured = False
            for call in mock_collection.create_index.call_args_list:
                kwargs = call[1]
                if "expireAfterSeconds" in kwargs:
                    assert kwargs["expireAfterSeconds"] == 2592000  # 30 days in seconds
                    ttl_configured = True
                    break
            
            assert ttl_configured, "TTL index should be configured"
            
            await worker.stop()
    
    @pytest.mark.asyncio
    async def test_multiple_log_levels_supported(self, worker):
        """Test that worker can handle different log levels."""
        # Currently only error is supported, but structure allows for extension
        error_event = MessageEnvelope(
            source="test-service",
            topic=EventTopic.SYSTEM_EVENT_ERROR.value,
            payload={"message": "Error message"}
        )
        
        await worker._handle_log_event(error_event)
        
        log_entry = worker._batch_queue[0]
        assert log_entry["level"] == "error"
        
        # Future: Add tests for warning, info, debug when those topics are added
    
    @pytest.mark.asyncio
    async def test_batch_size_handling(self, worker, mock_mongo_db):
        """Test handling of large batches."""
        # Add many log events
        for i in range(100):
            event = MessageEnvelope(
                source=f"service-{i}",
                topic=EventTopic.SYSTEM_EVENT_ERROR.value,
                payload={"message": f"Error {i}"}
            )
            await worker._handle_log_event(event)
        
        assert len(worker._batch_queue) == 100
        
        # Mock MongoDB operations
        mock_collection = mock_mongo_db[LOGS_COLLECTION]
        mock_insert_result = MagicMock()
        mock_insert_result.inserted_ids = [f"id{i}" for i in range(100)]
        mock_collection.insert_many = AsyncMock(return_value=mock_insert_result)
        
        # Flush should handle all logs
        await worker._flush_batch()
        
        assert len(worker._batch_queue) == 0
        assert mock_collection.insert_many.called
    
    @pytest.mark.asyncio
    async def test_log_context_merges_details(self, worker):
        """Test that context merges error_code, correlation_id, and details."""
        event = MessageEnvelope(
            source="test-service",
            topic=EventTopic.SYSTEM_EVENT_ERROR.value,
            payload={
                "message": "Test error",
                "error_code": "ERR_001",
                "details": {
                    "key1": "value1",
                    "key2": "value2"
                }
            },
            correlation_id="corr-123"
        )
        
        await worker._handle_log_event(event)
        
        log_entry = worker._batch_queue[0]
        context = log_entry["context"]
        
        # Context should include error_code, correlation_id, and all details
        assert context["error_code"] == "ERR_001"
        assert context["correlation_id"] == "corr-123"
        assert context["key1"] == "value1"
        assert context["key2"] == "value2"
    
    @pytest.mark.asyncio
    async def test_worker_start_mongodb_connection_failure(self):
        """Test handling of MongoDB connection failures during start."""
        worker = LogCollectionWorker()
        
        # Mock AsyncIOMotorClient to raise an exception
        with patch('app.workers.log_collection_worker.MONGODB_ENABLED', True), \
             patch('app.workers.log_collection_worker.AsyncIOMotorClient', side_effect=Exception("Connection refused")):
            
            # Should raise exception
            with pytest.raises(Exception, match="Connection refused"):
                await worker.start()
    
    @pytest.mark.asyncio
    async def test_global_worker_start_and_stop(self):
        """Test global worker instance management."""
        from app.workers.log_collection_worker import (
            start_log_collection_worker,
            stop_log_collection_worker
        )
        
        # Mock dependencies
        mock_mongo_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.create_index = AsyncMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        
        with patch('app.workers.log_collection_worker.MONGODB_ENABLED', True), \
             patch('app.workers.log_collection_worker.AsyncIOMotorClient', return_value=mock_mongo_client), \
             patch('app.workers.log_collection_worker.get_pubsub_service', return_value=mock_pubsub):
            
            mock_mongo_client.scareverse = mock_db
            
            # Start global worker
            worker_instance = await start_log_collection_worker()
            assert worker_instance is not None
            assert worker_instance._is_running is True
            
            # Stop global worker
            await stop_log_collection_worker()
    
    @pytest.mark.asyncio
    async def test_batch_processor_exception_handling(self, worker, mock_mongo_db):
        """Test that batch processor handles exceptions gracefully."""
        # Add log event
        event = MessageEnvelope(
            source="test-service",
            topic=EventTopic.SYSTEM_EVENT_ERROR.value,
            payload={"message": "Test error"}
        )
        await worker._handle_log_event(event)
        
        # Mock MongoDB to raise exception during flush
        mock_collection = mock_mongo_db[LOGS_COLLECTION]
        mock_collection.insert_many = AsyncMock(side_effect=Exception("DB Error"))
        
        # Should not raise exception, just log it
        await worker._flush_batch()
        
        # Queue should be cleared even with error
        assert len(worker._batch_queue) == 0
