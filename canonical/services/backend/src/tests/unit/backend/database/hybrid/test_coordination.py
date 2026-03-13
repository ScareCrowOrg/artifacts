"""
Tests for Redis coordination patterns.

Tests distributed locking, pub/sub patterns, and atomic operations.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from app.database.hybrid.coordination import RedisCoordinator, get_coordinator


class TestDistributedLocking:
    """Test Redis distributed locking functionality."""
    
    @pytest.mark.asyncio
    async def test_distributed_lock_acquired_and_released(self, mock_redis_client):
        """Distributed lock should be acquired and released properly."""
        with patch('app.database.hybrid.coordination.get_redis_client', return_value=mock_redis_client):
            coordinator = RedisCoordinator()
            
            async with coordinator.distributed_lock("test_lock"):
                pass
            
            # Verify lock was created with correct key
            mock_redis_client.lock.assert_called_once()
            lock_name = mock_redis_client.lock.call_args[1]['name']
            assert lock_name == "lock:test_lock"
            
            # Verify lock was acquired and released
            mock_lock = mock_redis_client.lock.return_value
            mock_lock.acquire.assert_called_once()
            mock_lock.release.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_distributed_lock_with_timeout(self, mock_redis_client):
        """Distributed lock should respect timeout parameter."""
        with patch('app.database.hybrid.coordination.get_redis_client', return_value=mock_redis_client):
            coordinator = RedisCoordinator()
            
            async with coordinator.distributed_lock("test_lock", timeout=5):
                pass
            
            # Verify timeout was passed
            call_kwargs = mock_redis_client.lock.call_args[1]
            assert call_kwargs['timeout'] == 5
    
    @pytest.mark.asyncio
    async def test_distributed_lock_when_redis_unavailable(self):
        """Lock should proceed without error when Redis is unavailable."""
        with patch('app.database.hybrid.coordination.get_redis_client', return_value=None):
            coordinator = RedisCoordinator()
            
            # Should not raise error
            async with coordinator.distributed_lock("test_lock"):
                pass
    
    @pytest.mark.asyncio
    async def test_distributed_lock_acquisition_failure(self, mock_redis_client):
        """Should raise TimeoutError when lock cannot be acquired."""
        mock_lock = mock_redis_client.lock.return_value
        mock_lock.acquire = AsyncMock(return_value=False)
        
        with patch('app.database.hybrid.coordination.get_redis_client', return_value=mock_redis_client):
            coordinator = RedisCoordinator()
            
            with pytest.raises(TimeoutError):
                async with coordinator.distributed_lock("test_lock"):
                    pass


class TestCacheInvalidationPubSub:
    """Test cache invalidation pub/sub patterns."""
    
    @pytest.mark.asyncio
    async def test_publish_cache_invalidation(self, mock_redis_client):
        """Cache invalidation events should be published to Redis."""
        with patch('app.database.hybrid.coordination.get_redis_client', return_value=mock_redis_client):
            coordinator = RedisCoordinator()
            
            await coordinator.publish_cache_invalidation(
                collection="cells",
                operation="update",
                doc_id="cel_123",
                user_id="user_123"
            )
            
            # Verify publish was called
            mock_redis_client.publish.assert_called_once()
            channel, message = mock_redis_client.publish.call_args[0]
            
            assert channel == "hybrid_db:cache_invalidation"
            assert "cells" in str(message)
            assert "update" in str(message)
    
    @pytest.mark.asyncio
    async def test_publish_when_redis_unavailable(self):
        """Publishing should not raise error when Redis is unavailable."""
        with patch('app.database.hybrid.coordination.get_redis_client', return_value=None):
            coordinator = RedisCoordinator()
            
            # Should not raise error
            await coordinator.publish_cache_invalidation(
                collection="cells",
                operation="insert"
            )
    
    @pytest.mark.asyncio
    async def test_subscribe_cache_invalidation(self, mock_redis_client):
        """Should be able to subscribe to cache invalidation events."""
        # Mock pubsub
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.listen = AsyncMock(return_value=iter([]))
        mock_redis_client.pubsub = MagicMock(return_value=mock_pubsub)
        
        with patch('app.database.hybrid.coordination.get_redis_client', return_value=mock_redis_client):
            coordinator = RedisCoordinator()
            
            async def callback(data):
                pass
            
            # Start subscription (will exit immediately due to empty iterator)
            await coordinator.subscribe_cache_invalidation(callback)
            
            # Verify subscription
            mock_pubsub.subscribe.assert_called_once_with("hybrid_db:cache_invalidation")


class TestAtomicOperations:
    """Test atomic write operations with cache synchronization."""
    
    @pytest.mark.asyncio
    async def test_atomic_write_with_cache_sync(self, mock_redis_client):
        """Atomic write should acquire lock and publish invalidation."""
        with patch('app.database.hybrid.coordination.get_redis_client', return_value=mock_redis_client):
            coordinator = RedisCoordinator()
            
            # Mock write operation
            async def write_op():
                return "success"
            
            result = await coordinator.atomic_write_with_cache_sync(
                write_operation=write_op,
                collection="cells",
                doc_id="cel_123",
                user_id="user_123"
            )
            
            # Verify result
            assert result == "success"
            
            # Verify lock was acquired
            mock_redis_client.lock.assert_called_once()
            
            # Verify cache invalidation was published
            mock_redis_client.publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_atomic_write_executes_operation_in_lock(self, mock_redis_client):
        """Write operation should execute while lock is held."""
        execution_order = []
        
        mock_lock = mock_redis_client.lock.return_value
        
        async def track_acquire():
            execution_order.append("lock_acquired")
            return True
        
        async def track_release():
            execution_order.append("lock_released")
        
        mock_lock.acquire = AsyncMock(side_effect=track_acquire)
        mock_lock.release = AsyncMock(side_effect=track_release)
        
        with patch('app.database.hybrid.coordination.get_redis_client', return_value=mock_redis_client):
            coordinator = RedisCoordinator()
            
            async def write_op():
                execution_order.append("write_executed")
                return True
            
            await coordinator.atomic_write_with_cache_sync(
                write_operation=write_op,
                collection="cells",
                doc_id="cel_123"
            )
            
            # Verify execution order
            assert execution_order == ["lock_acquired", "write_executed", "lock_released"]


class TestCoordinatorGlobals:
    """Test global coordinator instance management."""
    
    def test_get_coordinator_returns_singleton(self):
        """get_coordinator should return the same instance."""
        coordinator1 = get_coordinator()
        coordinator2 = get_coordinator()
        
        assert coordinator1 is coordinator2
    
    @pytest.mark.asyncio
    async def test_coordinator_close(self, mock_redis_client):
        """Coordinator should close pubsub connections."""
        mock_pubsub = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        
        coordinator = RedisCoordinator()
        coordinator._pubsub = mock_pubsub
        
        await coordinator.close()
        
        mock_pubsub.unsubscribe.assert_called_once()
        mock_pubsub.close.assert_called_once()
