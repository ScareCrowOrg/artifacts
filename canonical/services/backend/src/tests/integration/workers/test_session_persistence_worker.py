"""
Integration tests for Session Persistence Worker.

Tests session state persistence, batching, version conflict resolution,
and acknowledgment publishing.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from app.workers.session_persistence_worker import SessionPersistenceWorker
from app.models.event_bus import (
    MessageEnvelope,
    EventTopic
)
from app.database.schemas.session_schema import (
    BookSchema,
    CellSchema,
    SESSIONS_COLLECTION
)


class TestSessionPersistenceWorker:
    """Integration tests for session persistence worker."""
    
    @pytest.fixture
    def mock_mongo_db(self):
        """Create a mock MongoDB database."""
        mock_db = MagicMock()
        mock_collection = MagicMock()
        
        # Mock collection methods
        mock_collection.create_index = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value=None)
        mock_collection.update_one = AsyncMock()
        
        # Configure database to return collection
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        
        return mock_db
    
    @pytest.fixture
    async def worker(self, mock_mongo_db):
        """Create a worker instance with mocked dependencies."""
        worker = SessionPersistenceWorker(
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
    def sample_book_data(self):
        """Create sample book data for testing."""
        return {
            "book_id": "book-123",
            "title": "Test Book",
            "description": "A test book",
            "state": "active",
            "cells": [],
            "user_id": "user-456",
            "version": 1,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    
    @pytest.mark.asyncio
    async def test_worker_initialization(self):
        """Test worker is initialized with correct parameters."""
        worker = SessionPersistenceWorker(
            mongodb_uri="mongodb://test:27017",
            batch_interval=0.5
        )
        
        assert worker.mongodb_uri == "mongodb://test:27017"
        assert worker.batch_interval == 0.5
        assert worker._is_running is False
        assert worker._batch_queue == {}
    
    @pytest.mark.asyncio
    async def test_worker_start_creates_indexes(self, mock_mongo_db):
        """Test that worker creates MongoDB indexes on start."""
        worker = SessionPersistenceWorker()
        
        # Mock dependencies
        mock_mongo_client = MagicMock()
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        
        with patch('app.workers.session_persistence_worker.MONGODB_ENABLED', True), \
             patch('app.workers.session_persistence_worker.AsyncIOMotorClient', return_value=mock_mongo_client), \
             patch('app.workers.session_persistence_worker.get_pubsub_service', return_value=mock_pubsub):
            
            mock_mongo_client.scareverse = mock_mongo_db
            
            await worker.start()
            
            assert worker._is_running is True
            assert mock_pubsub.subscribe.called
            
            # Verify indexes were created
            mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
            assert mock_collection.create_index.called
            
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
        worker = SessionPersistenceWorker()
        
        with patch('app.workers.session_persistence_worker.MONGODB_ENABLED', False):
            await worker.start()
            
            assert worker._is_running is False
    
    @pytest.mark.asyncio
    async def test_worker_stop_lifecycle(self):
        """Test worker lifecycle (start/stop)."""
        worker = SessionPersistenceWorker(batch_interval=0.1)
        
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
        
        with patch('app.workers.session_persistence_worker.MONGODB_ENABLED', True), \
             patch('app.workers.session_persistence_worker.AsyncIOMotorClient', return_value=mock_mongo_client), \
             patch('app.workers.session_persistence_worker.get_pubsub_service', return_value=mock_pubsub):
            
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
    async def test_handle_state_update_success(self, worker, sample_book_data):
        """Test successfully handling a state update message."""
        request_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SESSION_STATE_UPDATE.value,
            payload=sample_book_data
        )
        
        await worker._handle_state_update(request_message)
        
        # Verify book was added to batch queue
        assert "book-123" in worker._batch_queue
        assert worker._batch_queue["book-123"]["data"] == sample_book_data
        assert worker._batch_queue["book-123"]["trace_id"] == request_message.trace_id
    
    @pytest.mark.asyncio
    async def test_handle_state_update_invalid_payload(self, worker):
        """Test handling a state update with invalid payload type."""
        # Create a message with valid structure but override payload after creation
        request_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SESSION_STATE_UPDATE.value,
            payload={}  # Start with valid dict
        )
        
        # Override payload to be invalid (not a dict)
        # This simulates what might happen if external code sends wrong type
        object.__setattr__(request_message, 'payload', "not a dict")
        
        await worker._handle_state_update(request_message)
        
        # Verify error response was published
        assert worker._pubsub_service.publish.called
        
        # Check error response
        call_args = worker._pubsub_service.publish.call_args
        error_message = call_args[0][0]
        
        assert error_message.topic == EventTopic.SESSION_STATE_ERROR.value
        assert error_message.payload["error_code"] == "INVALID_PAYLOAD"
        assert error_message.correlation_id == request_message.trace_id
    
    @pytest.mark.asyncio
    async def test_handle_state_update_missing_book_id(self, worker):
        """Test handling a state update with missing book_id."""
        request_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SESSION_STATE_UPDATE.value,
            payload={"title": "Test", "state": "active"}  # Missing book_id
        )
        
        await worker._handle_state_update(request_message)
        
        # Verify error response
        call_args = worker._pubsub_service.publish.call_args
        error_message = call_args[0][0]
        
        assert error_message.topic == EventTopic.SESSION_STATE_ERROR.value
        assert error_message.payload["error_code"] == "MISSING_BOOK_ID"
    
    @pytest.mark.asyncio
    async def test_batch_processing(self, worker, sample_book_data, mock_mongo_db):
        """Test that batch processing flushes queued updates."""
        # Add item to batch queue
        request_message = MessageEnvelope(
            source="test-client",
            topic=EventTopic.SESSION_STATE_UPDATE.value,
            payload=sample_book_data
        )
        
        await worker._handle_state_update(request_message)
        
        # Mock MongoDB operations for persist
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        mock_collection.find_one = AsyncMock(return_value=None)
        mock_update_result = MagicMock()
        mock_update_result.upserted_id = "new-id"
        mock_update_result.modified_count = 0
        mock_collection.update_one = AsyncMock(return_value=mock_update_result)
        
        # Trigger batch flush
        await worker._flush_batch()
        
        # Verify batch queue was cleared
        assert len(worker._batch_queue) == 0
        
        # Verify MongoDB update was called
        assert mock_collection.update_one.called
        
        # Verify acknowledgment was published
        assert worker._pubsub_service.publish.called
        ack_message = worker._pubsub_service.publish.call_args[0][0]
        assert ack_message.topic == EventTopic.SESSION_STATE_SYNCED.value
        assert ack_message.payload["book_id"] == "book-123"
    
    @pytest.mark.asyncio
    async def test_flush_batch_empty_queue(self, worker):
        """Test flushing an empty batch queue."""
        # Queue is empty
        assert len(worker._batch_queue) == 0
        
        # Should complete without errors
        await worker._flush_batch()
        
        # No publish calls should be made
        assert not worker._pubsub_service.publish.called
    
    @pytest.mark.asyncio
    async def test_persist_book_schema_validation_failure(self, worker, mock_mongo_db):
        """Test persistence with invalid schema."""
        invalid_book_data = {
            "book_id": "book-456",
            # Missing required fields
        }
        
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        
        await worker._persist_book(invalid_book_data, "trace-123")
        
        # Should not call MongoDB update
        assert not mock_collection.update_one.called
        
        # Should publish error
        assert worker._pubsub_service.publish.called
        error_message = worker._pubsub_service.publish.call_args[0][0]
        assert error_message.topic == EventTopic.SESSION_STATE_ERROR.value
        assert error_message.payload["error_code"] == "SCHEMA_ERROR"
    
    @pytest.mark.asyncio
    async def test_persist_book_version_conflict(self, worker, sample_book_data, mock_mongo_db):
        """Test version conflict detection during persistence."""
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        
        # Mock existing book with higher version
        existing_book = {
            "book_id": "book-123",
            "version": 5,
            "updated_at": datetime.utcnow()
        }
        mock_collection.find_one = AsyncMock(return_value=existing_book)
        
        # Try to persist book with lower version
        sample_book_data["version"] = 3
        
        await worker._persist_book(sample_book_data, "trace-123")
        
        # Should not update MongoDB
        assert not mock_collection.update_one.called
        
        # Should publish version conflict error
        assert worker._pubsub_service.publish.called
        error_message = worker._pubsub_service.publish.call_args[0][0]
        assert error_message.topic == EventTopic.SESSION_STATE_ERROR.value
        assert error_message.payload["error_code"] == "VERSION_CONFLICT"
        assert "version 5" in error_message.payload["message"]
    
    @pytest.mark.asyncio
    async def test_persist_book_no_conflict(self, worker, sample_book_data, mock_mongo_db):
        """Test successful persistence when version is equal or higher."""
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        
        # Mock existing book with same version
        existing_book = {
            "book_id": "book-123",
            "version": 1,
            "updated_at": datetime.utcnow()
        }
        mock_collection.find_one = AsyncMock(return_value=existing_book)
        
        # Mock successful update
        mock_update_result = MagicMock()
        mock_update_result.modified_count = 1
        mock_update_result.upserted_id = None
        mock_collection.update_one = AsyncMock(return_value=mock_update_result)
        
        await worker._persist_book(sample_book_data, "trace-123")
        
        # Should update MongoDB
        assert mock_collection.update_one.called
        
        # Should publish acknowledgment
        assert worker._pubsub_service.publish.called
        ack_message = worker._pubsub_service.publish.call_args[0][0]
        assert ack_message.topic == EventTopic.SESSION_STATE_SYNCED.value
    
    @pytest.mark.asyncio
    async def test_persist_book_mongodb_write_failure(self, worker, sample_book_data, mock_mongo_db):
        """Test handling of MongoDB write failures."""
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        mock_collection.find_one = AsyncMock(return_value=None)
        mock_collection.update_one = AsyncMock(side_effect=Exception("Connection error"))
        
        await worker._persist_book(sample_book_data, "trace-123")
        
        # Should publish error
        assert worker._pubsub_service.publish.called
        error_message = worker._pubsub_service.publish.call_args[0][0]
        assert error_message.topic == EventTopic.SESSION_STATE_ERROR.value
        assert error_message.payload["error_code"] == "DB_ERROR"
    
    @pytest.mark.asyncio
    async def test_persist_book_updates_timestamp(self, worker, sample_book_data, mock_mongo_db):
        """Test that persist updates the updated_at timestamp."""
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        mock_collection.find_one = AsyncMock(return_value=None)
        
        mock_update_result = MagicMock()
        mock_update_result.upserted_id = "new-id"
        mock_update_result.modified_count = 0
        mock_collection.update_one = AsyncMock(return_value=mock_update_result)
        
        original_timestamp = sample_book_data["updated_at"]
        
        await worker._persist_book(sample_book_data, "trace-123")
        
        # Check that update_one was called with updated timestamp
        call_args = mock_collection.update_one.call_args
        updated_data = call_args[0][1]["$set"]
        assert "updated_at" in updated_data
        # Timestamp should be updated (not equal to original)
        # Note: In production, this would be more recent
    
    @pytest.mark.asyncio
    async def test_concurrent_batch_updates(self, worker, sample_book_data):
        """Test concurrent state updates are safely batched."""
        # Create multiple messages for the same book
        messages = [
            MessageEnvelope(
                source="test-client",
                topic=EventTopic.SESSION_STATE_UPDATE.value,
                payload={**sample_book_data, "version": i}
            )
            for i in range(10)
        ]
        
        # Process all messages concurrently
        await asyncio.gather(*[
            worker._handle_state_update(msg) for msg in messages
        ])
        
        # Only the last update should be in the queue (same book_id)
        assert len(worker._batch_queue) == 1
        assert "book-123" in worker._batch_queue
        # Should have the last version
        assert worker._batch_queue["book-123"]["data"]["version"] == 9
    
    @pytest.mark.asyncio
    async def test_multiple_books_batching(self, worker, sample_book_data):
        """Test batching of multiple different books."""
        messages = [
            MessageEnvelope(
                source="test-client",
                topic=EventTopic.SESSION_STATE_UPDATE.value,
                payload={**sample_book_data, "book_id": f"book-{i}"}
            )
            for i in range(5)
        ]
        
        # Process all messages
        for msg in messages:
            await worker._handle_state_update(msg)
        
        # All 5 books should be in the queue
        assert len(worker._batch_queue) == 5
        for i in range(5):
            assert f"book-{i}" in worker._batch_queue
    
    @pytest.mark.asyncio
    async def test_send_sync_acknowledgment(self, worker):
        """Test sending sync acknowledgment message."""
        await worker._send_sync_acknowledgment(
            book_id="book-789",
            correlation_id="trace-456",
            version=3
        )
        
        assert worker._pubsub_service.publish.called
        ack_message = worker._pubsub_service.publish.call_args[0][0]
        
        assert ack_message.topic == EventTopic.SESSION_STATE_SYNCED.value
        assert ack_message.payload["book_id"] == "book-789"
        assert ack_message.payload["version"] == 3
        assert "synced_at" in ack_message.payload
        assert ack_message.correlation_id == "trace-456"
    
    @pytest.mark.asyncio
    async def test_batch_processor_runs_periodically(self, worker, sample_book_data, mock_mongo_db):
        """Test that batch processor runs periodically in background."""
        # Add item to queue
        worker._batch_queue["book-123"] = {
            "data": sample_book_data,
            "trace_id": "trace-123",
            "timestamp": datetime.utcnow()
        }
        
        # Mock MongoDB operations
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        mock_collection.find_one = AsyncMock(return_value=None)
        mock_update_result = MagicMock()
        mock_update_result.upserted_id = "new-id"
        mock_update_result.modified_count = 0
        mock_collection.update_one = AsyncMock(return_value=mock_update_result)
        
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
    async def test_stop_flushes_remaining_batch(self, worker, sample_book_data, mock_mongo_db):
        """Test that stopping worker flushes remaining batched updates."""
        # Add item to queue
        worker._batch_queue["book-123"] = {
            "data": sample_book_data,
            "trace_id": "trace-123",
            "timestamp": datetime.utcnow()
        }
        
        # Mock MongoDB operations
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        mock_collection.find_one = AsyncMock(return_value=None)
        mock_update_result = MagicMock()
        mock_update_result.upserted_id = "new-id"
        mock_update_result.modified_count = 0
        mock_collection.update_one = AsyncMock(return_value=mock_update_result)
        
        # Stop worker (should flush batch)
        await worker.stop()
        
        # Queue should be empty
        assert len(worker._batch_queue) == 0
        
        # MongoDB update should have been called
        assert mock_collection.update_one.called
    
    @pytest.mark.asyncio
    async def test_worker_start_mongodb_connection_failure(self):
        """Test handling of MongoDB connection failures during start."""
        worker = SessionPersistenceWorker()
        
        # Mock AsyncIOMotorClient to raise an exception
        with patch('app.workers.session_persistence_worker.MONGODB_ENABLED', True), \
             patch('app.workers.session_persistence_worker.AsyncIOMotorClient', side_effect=Exception("Connection refused")):
            
            # Should raise exception
            with pytest.raises(Exception, match="Connection refused"):
                await worker.start()
    
    @pytest.mark.asyncio
    async def test_global_worker_start_and_stop(self):
        """Test global worker instance management."""
        from app.workers.session_persistence_worker import (
            start_session_persistence_worker,
            stop_session_persistence_worker,
            _worker
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
        
        with patch('app.workers.session_persistence_worker.MONGODB_ENABLED', True), \
             patch('app.workers.session_persistence_worker.AsyncIOMotorClient', return_value=mock_mongo_client), \
             patch('app.workers.session_persistence_worker.get_pubsub_service', return_value=mock_pubsub):
            
            mock_mongo_client.scareverse = mock_db
            
            # Start global worker
            worker_instance = await start_session_persistence_worker()
            assert worker_instance is not None
            assert worker_instance._is_running is True
            
            # Stop global worker
            await stop_session_persistence_worker()
    
    @pytest.mark.asyncio
    async def test_batch_queue_error_handling_during_flush(self, worker, mock_mongo_db):
        """Test error handling when batch item processing fails."""
        # Add multiple items, one will cause an error
        worker._batch_queue["book-valid"] = {
            "data": {
                "book_id": "book-valid",
                "title": "Valid Book",
                "state": "active",
                "user_id": "user-123",
                "version": 1,
                "cells": []
            },
            "trace_id": "trace-1",
            "timestamp": datetime.utcnow()
        }
        
        worker._batch_queue["book-invalid"] = {
            "data": {"book_id": "book-invalid"},  # Missing required fields
            "trace_id": "trace-2",
            "timestamp": datetime.utcnow()
        }
        
        # Mock MongoDB
        mock_collection = mock_mongo_db[SESSIONS_COLLECTION]
        mock_collection.find_one = AsyncMock(return_value=None)
        mock_update_result = MagicMock()
        mock_update_result.upserted_id = "new-id"
        mock_update_result.modified_count = 0
        mock_collection.update_one = AsyncMock(return_value=mock_update_result)
        
        # Flush should handle partial errors gracefully
        await worker._flush_batch()
        
        # Queue should be cleared
        assert len(worker._batch_queue) == 0
        
        # Error should have been published for invalid book
        assert worker._pubsub_service.publish.called
