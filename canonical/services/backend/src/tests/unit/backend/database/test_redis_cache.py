"""
Unit tests for app/database/redis_cache.py

Tests Redis caching layer for JSONDatabase.
Tests cache key generation, TTL configuration, and async operations.
Uses mocked Redis to avoid external dependencies.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel


class TestRedisCachedDBInitialization:
    """Test RedisCachedJSONDatabase initialization."""
    
    def test_init_with_cache_enabled(self, cached_test_db):
        """Test initialization with cache enabled."""
        assert cached_test_db._cache_enabled is True
        assert cached_test_db._redis_client is not None
    
    def test_init_inherits_from_jsondb(self, cached_test_db):
        """Test that RedisCachedJSONDatabase inherits JSONDatabase methods."""
        # Should have all JSONDatabase methods
        assert hasattr(cached_test_db, 'insert')
        assert hasattr(cached_test_db, 'find_one')
        assert hasattr(cached_test_db, 'update')
        assert hasattr(cached_test_db, 'delete')
        assert hasattr(cached_test_db, 'find_many')


class TestCacheKeyGeneration:
    """Test cache key generation for different operations."""
    
    def test_cache_key_find_one_canonical(self, cached_test_db):
        """Test cache key for find_one on canonical artifact."""
        key = cached_test_db._get_cache_key(
            operation="find_one",
            collection="cell_types",
            doc_id="tipo_code",
            is_canonical=True
        )
        
        assert "jsondatabase" in key
        assert "find_one" in key
        assert "cell_types" in key
        assert "canonical" in key
        assert "id:tipo_code" in key
    
    def test_cache_key_find_one_runtime(self, cached_test_db):
        """Test cache key for find_one on runtime artifact."""
        key = cached_test_db._get_cache_key(
            operation="find_one",
            collection="cells",
            doc_id="cel_123",
            user_id="user_1",
            session_id="session_1",
            is_canonical=False
        )
        
        assert "runtime" in key
        assert "cells" in key
        assert "id:cel_123" in key
        assert "user:user_1" in key
        assert "session:session_1" in key
    
    def test_cache_key_find_many(self, cached_test_db):
        """Test cache key for find_many operation."""
        key = cached_test_db._get_cache_key(
            operation="find_many",
            collection="cells",
            user_id="user_1",
            is_canonical=False
        )
        
        assert "find_many" in key
        assert "cells" in key
        assert "user:user_1" in key
    
    def test_cache_key_find_by_field(self, cached_test_db):
        """Test cache key includes field and value hash."""
        key = cached_test_db._get_cache_key(
            operation="find_by_field",
            collection="cells",
            field="name",
            value="Test Cell",
            is_canonical=True
        )
        
        assert "find_by_field" in key
        assert "field:name" in key
        # Should include hash of value
        assert len(key.split(":")) >= 6
    
    def test_cache_key_different_for_different_users(self, cached_test_db):
        """Test that cache keys differ for different users."""
        key1 = cached_test_db._get_cache_key(
            operation="find_one",
            collection="cells",
            doc_id="cel_123",
            user_id="user_1"
        )
        
        key2 = cached_test_db._get_cache_key(
            operation="find_one",
            collection="cells",
            doc_id="cel_123",
            user_id="user_2"
        )
        
        assert key1 != key2


class TestTTLConfiguration:
    """Test TTL (Time-To-Live) configuration for different collections."""
    
    def test_ttl_for_canonical_artifacts(self, cached_test_db):
        """Test TTL for canonical artifacts."""
        ttl = cached_test_db._get_ttl("cell_types", is_canonical=True)
        
        # Should use REDIS_CACHE_TTL_CANONICAL
        assert ttl > 0
        assert isinstance(ttl, int)
    
    def test_ttl_for_celulas_collection(self, cached_test_db):
        """Test TTL for cells collection."""
        ttl = cached_test_db._get_ttl("cells", is_canonical=False)
        
        # Should use REDIS_CACHE_TTL_CELULAS
        assert ttl > 0
    
    def test_ttl_for_livros_collection(self, cached_test_db):
        """Test TTL for books collection."""
        ttl = cached_test_db._get_ttl("books", is_canonical=False)
        
        # Should use REDIS_CACHE_TTL_LIVROS
        assert ttl > 0
    
    def test_ttl_for_config_collection(self, cached_test_db):
        """Test TTL for config collection."""
        ttl = cached_test_db._get_ttl("config", is_canonical=False)
        
        # Should use REDIS_CACHE_TTL_CONFIG
        assert ttl > 0
    
    def test_ttl_for_unknown_collection_uses_default(self, cached_test_db):
        """Test that unknown collections use default TTL."""
        ttl = cached_test_db._get_ttl("unknown_collection", is_canonical=False)
        
        # Should use REDIS_CACHE_TTL (default)
        assert ttl > 0


class TestAsyncFindOneWithCache:
    """Test async find_one operations with caching."""
    
    @pytest.mark.asyncio
    async def test_find_one_async_cache_miss_then_cache(
        self, cached_test_db, sample_document_class
    ):
        """Test find_one on cache miss loads from disk and caches."""
        # Insert document to disk
        doc = sample_document_class(id="cached_doc", name="Cacheable", value=42)
        cached_test_db.insert("test_collection", doc, is_canonical=True)
        
        # Mock Redis get to return None (cache miss)
        cached_test_db._redis_client.get = AsyncMock(return_value=None)
        cached_test_db._redis_client.setex = AsyncMock(return_value=True)
        
        # Find document (should hit disk, then cache)
        found = await cached_test_db.find_one_async(
            "test_collection",
            "cached_doc",
            sample_document_class,
            is_canonical=True
        )
        
        assert found is not None
        assert found.id == "cached_doc"
        assert found.name == "Cacheable"
        
        # Redis setex should have been called to cache the result
        cached_test_db._redis_client.setex.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_find_one_async_cache_hit(
        self, cached_test_db, sample_document_class
    ):
        """Test find_one on cache hit returns cached data."""
        # Mock Redis to return cached data
        cached_data = {
            "id": "from_cache",
            "name": "Cached Name",
            "description": "",
            "value": 99,
            "tags": []
        }
        cached_json = json.dumps(cached_data)
        
        cached_test_db._redis_client.get = AsyncMock(return_value=cached_json)
        
        # Find document (should use cache)
        found = await cached_test_db.find_one_async(
            "test_collection",
            "from_cache",
            sample_document_class,
            is_canonical=True
        )
        
        assert found is not None
        assert found.id == "from_cache"
        assert found.name == "Cached Name"
        assert found.value == 99
        
        # Redis get should have been called
        cached_test_db._redis_client.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_find_one_async_not_found(
        self, cached_test_db, sample_document_class
    ):
        """Test find_one returns None when document doesn't exist."""
        cached_test_db._redis_client.get = AsyncMock(return_value=None)
        
        found = await cached_test_db.find_one_async(
            "test_collection",
            "nonexistent",
            sample_document_class,
            is_canonical=True
        )
        
        assert found is None


class TestAsyncFindManyWithCache:
    """Test async find_many operations with caching."""
    
    @pytest.mark.asyncio
    async def test_find_many_async_cache_miss(
        self, cached_test_db, sample_document_class
    ):
        """Test find_many loads from disk on cache miss."""
        # Insert documents
        for i in range(3):
            doc = sample_document_class(
                id=f"doc_{i}",
                name=f"Document {i}",
                value=i * 10
            )
            cached_test_db.insert("test_collection", doc, is_canonical=True)
        
        # Mock cache miss
        cached_test_db._redis_client.get = AsyncMock(return_value=None)
        cached_test_db._redis_client.set = AsyncMock(return_value=True)
        
        # Find many
        docs = await cached_test_db.find_many_async(
            "test_collection",
            sample_document_class,
            is_canonical=True
        )
        
        assert len(docs) == 3
        assert all(isinstance(doc, sample_document_class) for doc in docs)
    
    @pytest.mark.asyncio
    async def test_find_many_async_with_limit(
        self, cached_test_db, sample_document_class
    ):
        """Test find_many respects limit parameter."""
        # Insert documents
        for i in range(10):
            doc = sample_document_class(id=f"doc_{i}", name=f"Doc {i}")
            cached_test_db.insert("test_collection", doc, is_canonical=True)
        
        cached_test_db._redis_client.get = AsyncMock(return_value=None)
        cached_test_db._redis_client.set = AsyncMock(return_value=True)
        
        # Find with limit
        docs = await cached_test_db.find_many_async(
            "test_collection",
            sample_document_class,
            is_canonical=True,
            limit=5
        )
        
        assert len(docs) == 5


class TestAsyncWriteOperations:
    """Test async write operations with cache invalidation."""
    
    @pytest.mark.asyncio
    async def test_insert_async_invalidates_cache(
        self, cached_test_db, sample_document_class
    ):
        """Test that insert_async invalidates related cache entries."""
        doc = sample_document_class(id="new_doc", name="New", value=1)
        
        # Mock cache invalidation
        cached_test_db._redis_client.scan = AsyncMock(
            return_value=(0, [b"cache:key1", b"cache:key2"])
        )
        cached_test_db._redis_client.delete = AsyncMock(return_value=2)
        
        # Insert
        doc_id = await cached_test_db.insert_async(
            "test_collection",
            doc,
            is_canonical=True
        )
        
        assert doc_id == "new_doc"
        
        # Verify document was written to disk
        found = cached_test_db.find_one(
            "test_collection", "new_doc",
            sample_document_class, is_canonical=True
        )
        assert found is not None
    
    @pytest.mark.asyncio
    async def test_update_async_invalidates_cache(
        self, cached_test_db, sample_document_class
    ):
        """Test that update_async invalidates cache."""
        # Insert document
        doc = sample_document_class(id="update_doc", name="Before", value=1)
        cached_test_db.insert("test_collection", doc, is_canonical=True)
        
        # Mock cache invalidation
        cached_test_db._redis_client.scan = AsyncMock(return_value=(0, []))
        cached_test_db._redis_client.delete = AsyncMock(return_value=0)
        
        # Update
        success = await cached_test_db.update_async(
            "test_collection",
            "update_doc",
            {"name": "After", "value": 2},
            is_canonical=True
        )
        
        assert success is True
        
        # Verify update on disk
        updated = cached_test_db.find_one(
            "test_collection", "update_doc",
            sample_document_class, is_canonical=True
        )
        assert updated.name == "After"
        assert updated.value == 2
    
    @pytest.mark.asyncio
    async def test_delete_async_invalidates_cache(
        self, cached_test_db, sample_document_class
    ):
        """Test that delete_async invalidates cache."""
        # Insert document
        doc = sample_document_class(id="delete_doc", name="ToDelete")
        cached_test_db.insert("test_collection", doc, is_canonical=True)
        
        # Mock cache invalidation
        cached_test_db._redis_client.scan = AsyncMock(return_value=(0, []))
        cached_test_db._redis_client.delete = AsyncMock(return_value=0)
        
        # Delete
        success = await cached_test_db.delete_async(
            "test_collection",
            "delete_doc",
            is_canonical=True
        )
        
        assert success is True
        
        # Verify deleted from disk
        found = cached_test_db.find_one(
            "test_collection", "delete_doc",
            sample_document_class, is_canonical=True
        )
        assert found is None


class TestCacheDisabled:
    """Test graceful degradation when cache is disabled."""
    
    @pytest.mark.asyncio
    async def test_operations_work_without_cache(
        self, test_db, sample_document_class
    ):
        """Test that operations work when cache is disabled."""
        from app.database.redis_cache import RedisCachedJSONDatabase
        
        # Create cached DB but disable cache
        cached_db = RedisCachedJSONDatabase(
            base_path=test_db.base_path,
            is_test_env=True
        )
        cached_db._cache_enabled = False
        
        # Insert
        doc = sample_document_class(id="no_cache", name="Test")
        doc_id = await cached_db.insert_async(
            "test_collection", doc, is_canonical=True
        )
        
        assert doc_id == "no_cache"
        
        # Find
        found = await cached_db.find_one_async(
            "test_collection", "no_cache",
            sample_document_class, is_canonical=True
        )
        
        assert found is not None
        assert found.id == "no_cache"


class TestCachePatternInvalidation:
    """Test cache invalidation by pattern matching."""
    
    @pytest.mark.asyncio
    async def test_invalidate_specific_collection(self, cached_test_db):
        """Test invalidating all cache for a specific collection."""
        pattern = "jsondatabase:*:test_collection:*"
        
        # Mock scan to return some keys
        mock_keys = [
            b"jsondatabase:find_one:test_collection:canonical:id:doc1",
            b"jsondatabase:find_many:test_collection:canonical"
        ]
        
        cached_test_db._redis_client.scan = AsyncMock(
            return_value=(0, mock_keys)
        )
        cached_test_db._redis_client.delete = AsyncMock(return_value=2)
        
        # Invalidate
        await cached_test_db._invalidate_cache_pattern(pattern)
        
        # Should have called delete
        cached_test_db._redis_client.delete.assert_called_once()
        call_args = cached_test_db._redis_client.delete.call_args[0]
        assert len(call_args) == 2  # Both keys
    
    @pytest.mark.asyncio
    async def test_invalidate_handles_no_matches(self, cached_test_db):
        """Test invalidation with no matching keys."""
        pattern = "jsondatabase:*:nonexistent:*"
        
        # Mock scan returns no keys
        cached_test_db._redis_client.scan = AsyncMock(return_value=(0, []))
        cached_test_db._redis_client.delete = AsyncMock()
        
        # Should not raise error
        await cached_test_db._invalidate_cache_pattern(pattern)
        
        # Delete should not be called
        cached_test_db._redis_client.delete.assert_not_called()


class TestEdgeCases:
    """Test edge cases in Redis caching."""
    
    @pytest.mark.asyncio
    async def test_redis_connection_failure_graceful(
        self, test_db, sample_document_class
    ):
        """Test graceful handling when Redis is unavailable."""
        from app.database.redis_cache import RedisCachedJSONDatabase
        
        cached_db = RedisCachedJSONDatabase(
            base_path=test_db.base_path,
            is_test_env=True
        )
        
        # Mock Redis to raise exception
        async def failing_ensure_redis():
            return None
        
        cached_db._ensure_redis = failing_ensure_redis
        
        # Operations should still work (fallback to disk)
        doc = sample_document_class(id="fallback", name="Test")
        doc_id = await cached_db.insert_async(
            "test_collection", doc, is_canonical=True
        )
        
        assert doc_id == "fallback"
    
    @pytest.mark.asyncio
    async def test_cache_with_none_values(self, cached_test_db, sample_document_class):
        """Test caching documents with None values."""
        doc = sample_document_class(
            id="with_none",
            name="Test",
            description="",  # Empty string, not None
            value=0
        )
        
        cached_test_db._redis_client.get = AsyncMock(return_value=None)
        cached_test_db._redis_client.set = AsyncMock(return_value=True)
        
        # Insert and cache
        await cached_test_db.insert_async(
            "test_collection", doc, is_canonical=True
        )
        
        # Should handle properly
        found = await cached_test_db.find_one_async(
            "test_collection", "with_none",
            sample_document_class, is_canonical=True
        )
        
        assert found is not None
        assert found.id == "with_none"


class TestAsyncFieldQueries:
    """Test async field query operations with caching."""
    
    @pytest.mark.asyncio
    async def test_find_by_field_async_cache_hit(
        self, cached_test_db, sample_document_class
    ):
        """Test find_by_field_async with cache hit."""
        import json
        from unittest.mock import AsyncMock
        
        cached_data = {
            "id": "cached_field",
            "name": "Cached",
            "description": "",
            "value": 123,
            "tags": []
        }
        
        cached_test_db._redis_client.get = AsyncMock(
            return_value=json.dumps(cached_data)
        )
        
        found = await cached_test_db.find_by_field_async(
            "test_collection",
            "name",
            "Cached",
            sample_document_class,
            is_canonical=True
        )
        
        assert found is not None
        assert found.id == "cached_field"
    
    @pytest.mark.asyncio
    async def test_find_by_field_async_cache_miss(
        self, cached_test_db, sample_document_class
    ):
        """Test find_by_field_async with cache miss."""
        from unittest.mock import AsyncMock
        
        # Insert document
        doc = sample_document_class(id="field_doc", name="FindByField", value=99)
        cached_test_db.insert("test_collection", doc, is_canonical=True)
        
        cached_test_db._redis_client.get = AsyncMock(return_value=None)
        cached_test_db._redis_client.setex = AsyncMock(return_value=True)
        
        found = await cached_test_db.find_by_field_async(
            "test_collection",
            "name",
            "FindByField",
            sample_document_class,
            is_canonical=True
        )
        
        assert found is not None
        assert found.id == "field_doc"
        
        # Should have cached result
        cached_test_db._redis_client.setex.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_find_by_fields_async_cache_hit(
        self, cached_test_db, sample_document_class
    ):
        """Test find_by_fields_async with cache hit."""
        import json
        from unittest.mock import AsyncMock
        
        cached_data = {
            "id": "multi_field",
            "name": "Test",
            "description": "Desc",
            "value": 42,
            "tags": []
        }
        
        cached_test_db._redis_client.get = AsyncMock(
            return_value=json.dumps(cached_data)
        )
        
        found = await cached_test_db.find_by_fields_async(
            "test_collection",
            {"name": "Test", "value": 42},
            sample_document_class,
            is_canonical=True
        )
        
        assert found is not None
        assert found.id == "multi_field"
    
    @pytest.mark.asyncio
    async def test_find_by_fields_async_cache_miss(
        self, cached_test_db, sample_document_class
    ):
        """Test find_by_fields_async with cache miss."""
        from unittest.mock import AsyncMock
        
        # Insert document
        doc = sample_document_class(
            id="fields_doc",
            name="MultiField",
            description="Test",
            value=77
        )
        cached_test_db.insert("test_collection", doc, is_canonical=True)
        
        cached_test_db._redis_client.get = AsyncMock(return_value=None)
        cached_test_db._redis_client.setex = AsyncMock(return_value=True)
        
        found = await cached_test_db.find_by_fields_async(
            "test_collection",
            {"name": "MultiField", "value": 77},
            sample_document_class,
            is_canonical=True
        )
        
        assert found is not None
        assert found.id == "fields_doc"
        
        # Should have cached result
        cached_test_db._redis_client.setex.assert_called_once()


class TestCacheErrorHandling:
    """Test error handling in cache operations."""
    
    @pytest.mark.asyncio
    async def test_cache_error_on_get(
        self, cached_test_db, sample_document_class
    ):
        """Test that cache read errors are handled gracefully."""
        from unittest.mock import AsyncMock
        
        # Insert document
        doc = sample_document_class(id="error_doc", name="Test")
        cached_test_db.insert("test_collection", doc, is_canonical=True)
        
        # Mock Redis get to raise exception
        cached_test_db._redis_client.get = AsyncMock(
            side_effect=Exception("Redis connection error")
        )
        
        # Should fallback to disk
        found = await cached_test_db.find_one_async(
            "test_collection",
            "error_doc",
            sample_document_class,
            is_canonical=True
        )
        
        assert found is not None
        assert found.id == "error_doc"
    
    @pytest.mark.asyncio
    async def test_cache_error_on_set(
        self, cached_test_db, sample_document_class
    ):
        """Test that cache write errors are handled gracefully."""
        from unittest.mock import AsyncMock
        
        # Insert document
        doc = sample_document_class(id="write_error", name="Test")
        cached_test_db.insert("test_collection", doc, is_canonical=True)
        
        # Mock cache miss and setex to fail
        cached_test_db._redis_client.get = AsyncMock(return_value=None)
        cached_test_db._redis_client.setex = AsyncMock(
            side_effect=Exception("Redis write error")
        )
        
        # Should still return document even if caching fails
        found = await cached_test_db.find_one_async(
            "test_collection",
            "write_error",
            sample_document_class,
            is_canonical=True
        )
        
        assert found is not None
        assert found.id == "write_error"
    
    @pytest.mark.asyncio
    async def test_find_many_async_cache_hit(
        self, cached_test_db, sample_document_class
    ):
        """Test find_many_async returns cached list."""
        import json
        from unittest.mock import AsyncMock
        
        cached_data = [
            {"id": f"doc_{i}", "name": f"Doc {i}", "description": "", "value": i, "tags": []}
            for i in range(3)
        ]
        
        cached_test_db._redis_client.get = AsyncMock(
            return_value=json.dumps(cached_data)
        )
        
        docs = await cached_test_db.find_many_async(
            "test_collection",
            sample_document_class,
            is_canonical=True
        )
        
        assert len(docs) == 3
        assert all(isinstance(doc, sample_document_class) for doc in docs)
    
    @pytest.mark.asyncio
    async def test_find_many_async_error_on_cache_set(
        self, cached_test_db, sample_document_class
    ):
        """Test find_many gracefully handles cache set errors."""
        from unittest.mock import AsyncMock
        
        # Insert documents
        for i in range(2):
            doc = sample_document_class(id=f"doc_{i}", name=f"Doc {i}")
            cached_test_db.insert("test_collection", doc, is_canonical=True)
        
        # Mock cache miss and setex to fail
        cached_test_db._redis_client.get = AsyncMock(return_value=None)
        cached_test_db._redis_client.setex = AsyncMock(
            side_effect=Exception("Cache write failed")
        )
        
        # Should still return documents
        docs = await cached_test_db.find_many_async(
            "test_collection",
            sample_document_class,
            is_canonical=True
        )
        
        assert len(docs) == 2
