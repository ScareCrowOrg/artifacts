"""
Tests for cache synchronization utilities.

Tests cache invalidation patterns and synchronization between
file system and MongoDB.
"""

import pytest
from unittest.mock import AsyncMock, patch
import json

from app.database.hybrid.cache_sync import CacheSynchronizer, get_synchronizer


class TestCacheInvalidation:
    """Test cache invalidation on MongoDB writes."""
    
    @pytest.mark.asyncio
    async def test_invalidate_on_mongodb_write(self, mock_redis_client):
        """Should invalidate cache entries after MongoDB write."""
        with patch('app.database.hybrid.cache_sync.get_redis_client', return_value=mock_redis_client):
            synchronizer = CacheSynchronizer()
            
            await synchronizer.invalidate_on_mongodb_write(
                collection="cells",
                doc_id="cel_123",
                user_id="user_123",
                session_id="sess_456"
            )
            
            # Verify scan was called to find cache keys
            assert mock_redis_client.scan.called
    
    @pytest.mark.asyncio
    async def test_invalidate_with_user_scope(self, mock_redis_client):
        """Should build user-scoped cache invalidation patterns."""
        # Mock scan to return some keys
        mock_redis_client.scan = AsyncMock(return_value=(0, ["key1", "key2"]))
        
        with patch('app.database.hybrid.cache_sync.get_redis_client', return_value=mock_redis_client):
            synchronizer = CacheSynchronizer()
            
            await synchronizer.invalidate_on_mongodb_write(
                collection="cells",
                user_id="user_123"
            )
            
            # Verify delete was called with found keys
            mock_redis_client.delete.assert_called_with("key1", "key2")
    
    @pytest.mark.asyncio
    async def test_invalidate_when_redis_unavailable(self):
        """Should handle Redis unavailability gracefully."""
        with patch('app.database.hybrid.cache_sync.get_redis_client', return_value=None):
            synchronizer = CacheSynchronizer()
            
            # Should not raise error
            await synchronizer.invalidate_on_mongodb_write(
                collection="cells",
                doc_id="cel_123"
            )
    
    @pytest.mark.asyncio
    async def test_invalidate_collection(self, mock_redis_client):
        """Should invalidate all cache entries for a collection."""
        with patch('app.database.hybrid.cache_sync.get_redis_client', return_value=mock_redis_client):
            synchronizer = CacheSynchronizer()
            
            await synchronizer.invalidate_collection(
                collection="cells",
                user_id="user_123"
            )
            
            # Should call scan for collection pattern
            assert mock_redis_client.scan.called


class TestCacheWarming:
    """Test cache warming from MongoDB reads."""
    
    @pytest.mark.asyncio
    async def test_warm_cache_from_mongodb(self, mock_redis_client):
        """Should warm cache with MongoDB data."""
        data = {"id": "cel_123", "name": "Test Cell", "type": "code"}
        
        with patch('app.database.hybrid.cache_sync.get_redis_client', return_value=mock_redis_client):
            synchronizer = CacheSynchronizer()
            
            await synchronizer.warm_cache_from_mongodb(
                collection="cells",
                doc_id="cel_123",
                data=data,
                user_id="user_123",
                session_id="sess_456",
                ttl=1800
            )
            
            # Verify setex was called with correct parameters
            mock_redis_client.setex.assert_called_once()
            call_args = mock_redis_client.setex.call_args[0]
            
            # Check TTL
            assert call_args[1] == 1800
            
            # Check data is JSON serialized
            cached_data = json.loads(call_args[2])
            assert cached_data == data
    
    @pytest.mark.asyncio
    async def test_warm_cache_builds_correct_key(self, mock_redis_client):
        """Should build correct cache key for warming."""
        data = {"id": "cel_123"}
        
        with patch('app.database.hybrid.cache_sync.get_redis_client', return_value=mock_redis_client):
            synchronizer = CacheSynchronizer()
            
            await synchronizer.warm_cache_from_mongodb(
                collection="cells",
                doc_id="cel_123",
                data=data,
                user_id="user_123",
                session_id="sess_456",
                ttl=3600
            )
            
            # Verify cache key structure
            cache_key = mock_redis_client.setex.call_args[0][0]
            assert "jsondatabase" in cache_key
            assert "find_one" in cache_key
            assert "cells" in cache_key
            assert "runtime" in cache_key
            assert "user_123" in cache_key
            assert "cel_123" in cache_key
    
    @pytest.mark.asyncio
    async def test_warm_cache_when_redis_unavailable(self):
        """Should handle Redis unavailability gracefully."""
        with patch('app.database.hybrid.cache_sync.get_redis_client', return_value=None):
            synchronizer = CacheSynchronizer()
            
            # Should not raise error
            await synchronizer.warm_cache_from_mongodb(
                collection="cells",
                doc_id="cel_123",
                data={"id": "cel_123"}
            )


class TestConsistencyChecking:
    """Test consistency checking between storage backends."""
    
    @pytest.mark.asyncio
    async def test_check_consistency_returns_status(self):
        """Should return consistency status structure."""
        synchronizer = CacheSynchronizer()
        
        result = await synchronizer.check_consistency(
            collection="cells",
            doc_id="cel_123",
            user_id="user_123"
        )
        
        # Verify result structure
        assert "collection" in result
        assert "doc_id" in result
        assert "exists_in_files" in result
        assert "exists_in_mongodb" in result
        assert "cached_in_redis" in result
        assert "consistent" in result
        assert "discrepancies" in result
        
        # Verify values
        assert result["collection"] == "cells"
        assert result["doc_id"] == "cel_123"


class TestSynchronizerGlobals:
    """Test global synchronizer instance management."""
    
    def test_get_synchronizer_returns_singleton(self):
        """get_synchronizer should return the same instance."""
        synchronizer1 = get_synchronizer()
        synchronizer2 = get_synchronizer()
        
        assert synchronizer1 is synchronizer2


class TestCacheKeyPatterns:
    """Test cache key pattern generation for invalidation."""
    
    @pytest.mark.asyncio
    async def test_invalidation_pattern_with_doc_id(self, mock_redis_client):
        """Should create doc-specific invalidation pattern."""
        mock_redis_client.scan = AsyncMock(return_value=(0, []))
        
        with patch('app.database.hybrid.cache_sync.get_redis_client', return_value=mock_redis_client):
            synchronizer = CacheSynchronizer()
            
            await synchronizer.invalidate_on_mongodb_write(
                collection="cells",
                doc_id="cel_123",
                user_id="user_123",
                session_id="sess_456"
            )
            
            # Check that scan was called with appropriate patterns
            calls = mock_redis_client.scan.call_args_list
            assert len(calls) > 0
            
            # At least one pattern should include the doc_id
            patterns = [call[1]['match'] for call in calls]
            doc_pattern_found = any("cel_123" in pattern for pattern in patterns)
            assert doc_pattern_found
    
    @pytest.mark.asyncio
    async def test_invalidation_pattern_without_doc_id(self, mock_redis_client):
        """Should create collection-wide invalidation pattern."""
        mock_redis_client.scan = AsyncMock(return_value=(0, []))
        
        with patch('app.database.hybrid.cache_sync.get_redis_client', return_value=mock_redis_client):
            synchronizer = CacheSynchronizer()
            
            await synchronizer.invalidate_on_mongodb_write(
                collection="cells",
                user_id="user_123"
            )
            
            # Should scan for user-specific pattern
            calls = mock_redis_client.scan.call_args_list
            assert len(calls) > 0
            
            patterns = [call[1]['match'] for call in calls]
            user_pattern_found = any("user_123" in pattern for pattern in patterns)
            assert user_pattern_found
    
    @pytest.mark.asyncio
    async def test_multiple_scan_iterations(self, mock_redis_client):
        """Should handle multiple scan iterations for large key sets."""
        # Mock scan to return cursor > 0 on first call, then 0
        mock_redis_client.scan = AsyncMock(side_effect=[
            (1, ["key1", "key2"]),  # First iteration
            (0, ["key3"])  # Final iteration
        ])
        
        with patch('app.database.hybrid.cache_sync.get_redis_client', return_value=mock_redis_client):
            synchronizer = CacheSynchronizer()
            
            await synchronizer.invalidate_on_mongodb_write(
                collection="cells",
                user_id="user_123"
            )
            
            # Verify scan was called twice (until cursor = 0)
            assert mock_redis_client.scan.call_count >= 2
            
            # Verify all keys were deleted
            delete_calls = mock_redis_client.delete.call_args_list
            assert len(delete_calls) >= 1
