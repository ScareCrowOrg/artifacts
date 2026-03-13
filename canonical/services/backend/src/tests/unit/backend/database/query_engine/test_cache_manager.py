"""
Unit tests for Cache Manager.

Tests L1 Redis cache manager for query results including:
- Deterministic cache key generation
- Cache get/set operations
- TTL handling
- Cache invalidation (specific and pattern-based)
- Secondary indexing for efficient invalidation
- Cache statistics

Uses mocked Redis to avoid external dependencies.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, call

from app.database.query_engine.cache_manager import CacheManager


@pytest.fixture
def mock_redis():
    """Create a mock Redis client for testing."""
    mock = AsyncMock()
    
    # Mock get method to return None (cache miss) by default
    mock.get = AsyncMock(return_value=None)
    
    # Mock set method
    mock.set = AsyncMock(return_value=True)
    
    # Mock setex method (set with expiration)
    mock.setex = AsyncMock(return_value=True)
    
    # Mock delete method
    mock.delete = AsyncMock(return_value=1)
    
    # Mock scan method (for pattern matching)
    mock.scan = AsyncMock(return_value=(0, []))
    
    # Mock ping method
    mock.ping = AsyncMock(return_value=True)
    
    return mock


@pytest.fixture
def cache_manager(mock_redis):
    """Create a CacheManager instance with mocked Redis."""
    return CacheManager(mock_redis)


class TestCacheKeyGeneration:
    """Test cache key generation for determinism and uniqueness."""
    
    def test_generate_cache_key_deterministic(self, cache_manager):
        """Test cache key generation is deterministic."""
        key1 = cache_manager.generate_cache_key(
            "templates",
            {"status": "published"},
            "user1",
            limit=10
        )
        key2 = cache_manager.generate_cache_key(
            "templates",
            {"status": "published"},
            "user1",
            limit=10
        )
        
        assert key1 == key2
        assert key1.startswith("query:")
    
    def test_generate_cache_key_different_queries(self, cache_manager):
        """Test different queries generate different keys."""
        key1 = cache_manager.generate_cache_key(
            "templates",
            {"status": "published"},
            "user1"
        )
        key2 = cache_manager.generate_cache_key(
            "templates",
            {"status": "draft"},
            "user1"
        )
        
        assert key1 != key2
    
    def test_generate_cache_key_different_users(self, cache_manager):
        """Test different users generate different keys."""
        key1 = cache_manager.generate_cache_key(
            "templates",
            {"status": "published"},
            "user1"
        )
        key2 = cache_manager.generate_cache_key(
            "templates",
            {"status": "published"},
            "user2"
        )
        
        assert key1 != key2
    
    def test_generate_cache_key_different_collections(self, cache_manager):
        """Test different collections generate different keys."""
        key1 = cache_manager.generate_cache_key(
            "templates",
            {"status": "published"},
            "user1"
        )
        key2 = cache_manager.generate_cache_key(
            "roles",
            {"status": "published"},
            "user1"
        )
        
        assert key1 != key2
    
    def test_generate_cache_key_different_limits(self, cache_manager):
        """Test different limits generate different keys."""
        key1 = cache_manager.generate_cache_key(
            "templates",
            {"status": "published"},
            "user1",
            limit=10
        )
        key2 = cache_manager.generate_cache_key(
            "templates",
            {"status": "published"},
            "user1",
            limit=20
        )
        
        assert key1 != key2
    
    def test_generate_cache_key_with_no_limit(self, cache_manager):
        """Test key generation with no limit parameter."""
        key = cache_manager.generate_cache_key(
            "templates",
            {"status": "published"},
            "user1"
        )
        
        assert key.startswith("query:")
        assert len(key) > 10  # Should have hash
    
    def test_cache_key_determinism_with_limit(self, cache_manager):
        """Validate cache keys are unique for different limits (Bug #2 fix)."""
        key_no_limit = cache_manager.generate_cache_key(
            "templates",
            {"status": "published"},
            "user1"
        )
        key_limit_10 = cache_manager.generate_cache_key(
            "templates",
            {"status": "published"},
            "user1",
            limit=10
        )
        key_limit_0 = cache_manager.generate_cache_key(
            "templates",
            {"status": "published"},
            "user1",
            limit=0
        )
        
        # All should be different
        assert key_no_limit != key_limit_10, "No limit and limit=10 should have different keys"
        assert key_limit_10 != key_limit_0, "limit=10 and limit=0 should have different keys"
        assert key_no_limit != key_limit_0, "No limit and limit=0 should have different keys"
    
    def test_generate_cache_key_complex_query(self, cache_manager):
        """Test key generation with complex query."""
        key = cache_manager.generate_cache_key(
            "templates",
            {
                "status": "published",
                "owner": "user1",
                "tags": ["python", "api"],
                "metadata.level": "advanced"
            },
            "user1",
            limit=50
        )
        
        assert key.startswith("query:")
        # Should be deterministic with nested structures
        key2 = cache_manager.generate_cache_key(
            "templates",
            {
                "status": "published",
                "owner": "user1",
                "tags": ["python", "api"],
                "metadata.level": "advanced"
            },
            "user1",
            limit=50
        )
        assert key == key2


class TestCacheGetSet:
    """Test basic cache get and set operations."""
    
    @pytest.mark.asyncio
    async def test_cache_set_get(self, cache_manager, mock_redis):
        """Test basic cache set and get."""
        key = "query:test123"
        data = [{"_id": "1", "name": "Test"}]
        
        await cache_manager.set(key, data)
        
        # Verify setex was called with correct parameters
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == key
        assert call_args[0][1] == 300  # default TTL
        assert json.loads(call_args[0][2]) == data
    
    @pytest.mark.asyncio
    async def test_cache_get_hit(self, cache_manager, mock_redis):
        """Test cache get on hit returns cached data."""
        key = "query:test123"
        data = [{"_id": "1", "name": "Test"}]
        
        # Mock Redis to return cached data
        mock_redis.get = AsyncMock(return_value=json.dumps(data))
        
        cached = await cache_manager.get(key)
        
        assert cached == data
        mock_redis.get.assert_called_once_with(key)
    
    @pytest.mark.asyncio
    async def test_cache_miss(self, cache_manager, mock_redis):
        """Test cache miss returns None."""
        key = "query:nonexistent"
        
        # Mock Redis to return None (cache miss)
        mock_redis.get = AsyncMock(return_value=None)
        
        cached = await cache_manager.get(key)
        
        assert cached is None
        mock_redis.get.assert_called_once_with(key)
    
    @pytest.mark.asyncio
    async def test_cache_set_with_custom_ttl(self, cache_manager, mock_redis):
        """Test cache set with custom TTL."""
        key = "query:test_ttl"
        data = [{"_id": "1"}]
        ttl = 600
        
        await cache_manager.set(key, data, ttl=ttl)
        
        # Verify custom TTL was used
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == ttl
    
    @pytest.mark.asyncio
    async def test_cache_set_with_datetime_serialization(self, cache_manager, mock_redis):
        """Test cache set handles datetime serialization."""
        from datetime import datetime
        
        key = "query:test_datetime"
        data = [{"_id": "1", "created_at": datetime(2026, 2, 24, 10, 0, 0)}]
        
        await cache_manager.set(key, data)
        
        # Should serialize without error
        mock_redis.setex.assert_called_once()
        # Datetime should be converted to string
        serialized = mock_redis.setex.call_args[0][2]
        assert "2026-02-24" in serialized


class TestCacheInvalidation:
    """Test cache invalidation operations."""
    
    @pytest.mark.asyncio
    async def test_invalidate_specific_key(self, cache_manager, mock_redis):
        """Test specific key invalidation."""
        key = "query:test_inv"
        
        await cache_manager.invalidate(key)
        
        mock_redis.delete.assert_called_once_with(key)
    
    @pytest.mark.asyncio
    async def test_invalidate_for_collection_with_user(self, cache_manager, mock_redis):
        """Test invalidating all queries for a collection and user."""
        # Mock scan to return some index keys
        index_keys = [
            "query_index:templates:user1:abc123",
            "query_index:templates:user1:def456"
        ]
        query_keys = ["query:abc123", "query:def456"]
        
        # First scan returns keys, second returns empty (cursor=0)
        mock_redis.scan = AsyncMock(return_value=(0, index_keys))
        
        # Mock get to return query keys
        mock_redis.get = AsyncMock(side_effect=query_keys)
        
        await cache_manager.invalidate_for_collection("templates", "user1")
        
        # Verify scan was called with correct pattern
        mock_redis.scan.assert_called_once()
        call_args = mock_redis.scan.call_args
        assert "query_index:templates:user1:*" in str(call_args)
        
        # Verify query keys and index keys were deleted
        assert mock_redis.delete.call_count == 2  # Once for query keys, once for index keys
    
    @pytest.mark.asyncio
    async def test_invalidate_for_collection_all_users(self, cache_manager, mock_redis):
        """Test invalidating all queries for a collection (all users)."""
        await cache_manager.invalidate_for_collection("templates")
        
        # Verify scan was called with correct pattern (no user_id)
        mock_redis.scan.assert_called_once()
        call_args = mock_redis.scan.call_args
        assert "query_index:templates:*" in str(call_args)
    
    @pytest.mark.asyncio
    async def test_invalidate_for_collection_multiple_pages(self, cache_manager, mock_redis):
        """Test invalidation with paginated scan results."""
        # First page of results
        page1_keys = ["query_index:templates:user1:abc123"]
        # Second page of results
        page2_keys = ["query_index:templates:user1:def456"]
        
        # Mock scan to return paginated results
        mock_redis.scan = AsyncMock(side_effect=[
            (1, page1_keys),  # cursor=1, has more
            (0, page2_keys),  # cursor=0, done
        ])
        
        # Mock get to return query keys
        mock_redis.get = AsyncMock(side_effect=["query:abc123", "query:def456"])
        
        await cache_manager.invalidate_for_collection("templates", "user1")
        
        # Verify scan was called twice (pagination)
        assert mock_redis.scan.call_count == 2
        
        # Verify all keys were deleted
        assert mock_redis.delete.call_count == 4  # 2 pages × (query keys + index keys)


class TestCacheWithIndex:
    """Test cache operations with secondary indexing."""
    
    @pytest.mark.asyncio
    async def test_set_with_index(self, cache_manager, mock_redis):
        """Test cache with indexing for invalidation."""
        key = cache_manager.generate_cache_key("templates", {"status": "active"}, "user1")
        data = [{"_id": "1", "name": "Template 1"}]
        
        await cache_manager.set_with_index(key, data, "templates", "user1")
        
        # Verify main cache key was set
        assert mock_redis.setex.call_count == 2  # Once for data, once for index
        
        # Verify index key was created
        # Should be query_index:templates:user1:{hash}
        calls = mock_redis.setex.call_args_list
        
        # First call should be the data
        data_call = calls[0]
        assert data_call[0][0] == key
        
        # Second call should be the index
        index_call = calls[1]
        index_key = index_call[0][0]
        assert index_key.startswith("query_index:templates:user1:")
        assert index_call[0][2] == key  # Index value should point to query key
    
    @pytest.mark.asyncio
    async def test_set_with_index_custom_ttl(self, cache_manager, mock_redis):
        """Test indexed cache with custom TTL."""
        key = cache_manager.generate_cache_key("templates", {"status": "active"}, "user1")
        data = [{"_id": "1"}]
        ttl = 600
        
        await cache_manager.set_with_index(key, data, "templates", "user1", ttl=ttl)
        
        # Data should use custom TTL, index should use custom TTL + buffer
        calls = mock_redis.setex.call_args_list
        assert calls[0][0][1] == ttl  # Data TTL
        assert calls[1][0][1] == ttl + 3600  # Index TTL (query TTL + 1 hour buffer)
    
    @pytest.mark.asyncio
    async def test_secondary_index_multiple_queries(self, cache_manager, mock_redis):
        """Validate that multiple queries DON'T overwrite index (Bug #1 verification)."""
        # Query 1
        key1 = cache_manager.generate_cache_key("templates", {"status": "published"}, "user1")
        await cache_manager.set_with_index(key1, [{"id": "1"}], "templates", "user1")
        
        # Query 2 (different query, same collection+user)
        key2 = cache_manager.generate_cache_key("templates", {"status": "draft"}, "user1")
        await cache_manager.set_with_index(key2, [{"id": "2"}], "templates", "user1")
        
        # Both should have unique keys
        assert key1 != key2
        
        # Verify both index entries were created (4 calls: 2 for data, 2 for index)
        assert mock_redis.setex.call_count == 4
        
        # Extract index keys from calls
        calls = mock_redis.setex.call_args_list
        index1_key = calls[1][0][0]  # Second call is first index
        index2_key = calls[3][0][0]  # Fourth call is second index
        
        # Index keys should be different (different hash suffixes)
        assert index1_key != index2_key
        assert "query_index:templates:user1:" in index1_key
        assert "query_index:templates:user1:" in index2_key
    
    @pytest.mark.asyncio
    async def test_index_ttl_longer_than_query(self, cache_manager, mock_redis):
        """Validate that index TTL is longer than query TTL (Bug #3 fix)."""
        key = cache_manager.generate_cache_key("templates", {"status": "active"}, "user1")
        data = [{"_id": "1"}]
        
        await cache_manager.set_with_index(key, data, "templates", "user1")
        
        # Verify setex was called twice
        calls = mock_redis.setex.call_args_list
        assert len(calls) == 2
        
        # First call: query data with default TTL
        query_ttl = calls[0][0][1]
        assert query_ttl == 300  # default_ttl
        
        # Second call: index with longer TTL
        index_ttl = calls[1][0][1]
        assert index_ttl == 300 + 3600  # default_ttl + 1 hour buffer
        assert index_ttl > query_ttl, "Index TTL must be longer than query TTL"


class TestCacheStats:
    """Test cache statistics."""
    
    @pytest.mark.asyncio
    async def test_get_cache_stats(self, cache_manager, mock_redis):
        """Test getting cache statistics."""
        # Mock scan to return some query keys
        mock_redis.scan = AsyncMock(side_effect=[
            (1, ["query:1", "query:2", "query:3"]),
            (0, ["query:4", "query:5"])
        ])
        
        stats = await cache_manager.get_cache_stats()
        
        assert stats["total_cached_queries"] == 5
        assert stats["default_ttl_seconds"] == 300
    
    @pytest.mark.asyncio
    async def test_get_cache_stats_empty(self, cache_manager, mock_redis):
        """Test cache stats when cache is empty."""
        mock_redis.scan = AsyncMock(return_value=(0, []))
        
        stats = await cache_manager.get_cache_stats()
        
        assert stats["total_cached_queries"] == 0
        assert stats["default_ttl_seconds"] == 300
    
    @pytest.mark.asyncio
    async def test_get_cache_stats_no_redis(self):
        """Test cache stats when Redis is not available."""
        cache = CacheManager(None)
        
        stats = await cache.get_cache_stats()
        
        assert stats["total_cached_queries"] == 0
        assert stats["default_ttl_seconds"] == 300


class TestCacheManagerEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_get_with_no_redis(self):
        """Test get operation when Redis is not available."""
        cache = CacheManager(None)
        
        result = await cache.get("query:test")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_set_with_no_redis(self):
        """Test set operation when Redis is not available."""
        cache = CacheManager(None)
        
        # Should not raise exception
        await cache.set("query:test", [{"_id": "1"}])
    
    @pytest.mark.asyncio
    async def test_invalidate_with_no_redis(self):
        """Test invalidate operation when Redis is not available."""
        cache = CacheManager(None)
        
        # Should not raise exception
        await cache.invalidate("query:test")
    
    @pytest.mark.asyncio
    async def test_invalidate_for_collection_with_no_redis(self):
        """Test collection invalidation when Redis is not available."""
        cache = CacheManager(None)
        
        # Should not raise exception
        await cache.invalidate_for_collection("templates", "user1")
    
    @pytest.mark.asyncio
    async def test_get_error_handling(self, cache_manager, mock_redis):
        """Test error handling in get operation."""
        mock_redis.get = AsyncMock(side_effect=Exception("Redis error"))
        
        # Should return None on error, not raise
        result = await cache_manager.get("query:test")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_set_error_handling(self, cache_manager, mock_redis):
        """Test error handling in set operation."""
        mock_redis.setex = AsyncMock(side_effect=Exception("Redis error"))
        
        # Should not raise exception
        await cache_manager.set("query:test", [{"_id": "1"}])
    
    @pytest.mark.asyncio
    async def test_invalidate_error_handling(self, cache_manager, mock_redis):
        """Test error handling in invalidate operation."""
        mock_redis.delete = AsyncMock(side_effect=Exception("Redis error"))
        
        # Should not raise exception
        await cache_manager.invalidate("query:test")
    
    @pytest.mark.asyncio
    async def test_empty_query_list(self, cache_manager, mock_redis):
        """Test caching empty query results."""
        key = "query:empty"
        data = []
        
        await cache_manager.set(key, data)
        
        # Should serialize empty list
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert json.loads(call_args[0][2]) == []
    
    @pytest.mark.asyncio
    async def test_large_query_result(self, cache_manager, mock_redis):
        """Test caching large query results."""
        key = "query:large"
        # Create a large result set
        data = [{"_id": str(i), "name": f"Item {i}", "value": i} for i in range(1000)]
        
        await cache_manager.set(key, data)
        
        # Should handle large datasets
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert len(json.loads(call_args[0][2])) == 1000


class TestCacheManagerIntegration:
    """Integration tests for complete cache workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_cache_workflow(self, cache_manager, mock_redis):
        """Test complete cache workflow: set, get, invalidate."""
        # Generate key
        key = cache_manager.generate_cache_key(
            "templates",
            {"status": "published"},
            "user1",
            limit=10
        )
        
        # Set cache with index
        data = [{"_id": "1", "name": "Template 1"}]
        await cache_manager.set_with_index(key, data, "templates", "user1")
        
        # Mock get to return cached data
        mock_redis.get = AsyncMock(return_value=json.dumps(data))
        
        # Get from cache
        cached = await cache_manager.get(key)
        assert cached == data
        
        # Invalidate
        await cache_manager.invalidate(key)
        mock_redis.delete.assert_called()
    
    @pytest.mark.asyncio
    async def test_multiple_users_different_caches(self, cache_manager):
        """Test that different users have isolated caches."""
        query = {"status": "published"}
        
        key_user1 = cache_manager.generate_cache_key("templates", query, "user1")
        key_user2 = cache_manager.generate_cache_key("templates", query, "user2")
        
        # Keys should be different
        assert key_user1 != key_user2
        
        # Hash should be different due to user_id
        hash1 = key_user1.split(":")[-1]
        hash2 = key_user2.split(":")[-1]
        assert hash1 != hash2
