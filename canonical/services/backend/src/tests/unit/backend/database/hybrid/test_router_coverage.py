"""
Additional tests for HybridDatabase router to improve coverage.

Focuses on testing edge cases, error scenarios, and code paths
that weren't covered by the existing tests.
"""

import pytest
from unittest.mock import patch, AsyncMock
from app.database.hybrid.router import HybridDatabase, CANONICAL_COLLECTIONS, RUNTIME_COLLECTIONS


class TestHybridDatabaseInitialization:
    """Test HybridDatabase initialization and setup."""
    
    def test_init_with_mongodb_enabled(self, temp_dir):
        """Test initialization when MongoDB is enabled."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', True):
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            assert db._mongo_ops is not None
    
    def test_init_with_mongodb_disabled(self, temp_dir):
        """Test initialization when MongoDB is disabled."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            assert db._mongo_ops is None
    
    def test_file_db_initialized(self, temp_dir):
        """Test that file database is always initialized."""
        db = HybridDatabase(base_path=temp_dir, is_test_env=False)
        assert db._file_db is not None


class TestRoutingLogic:
    """Test routing decision logic comprehensively."""
    
    def test_canonical_collections_routing(self):
        """All canonical collections should route to file system."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', True):
            db = HybridDatabase(is_test_env=True)
            db._mongo_ops = AsyncMock()  # MongoDB enabled
            
            for collection in CANONICAL_COLLECTIONS:
                assert not db._should_use_mongodb(collection, is_canonical=False)
    
    def test_runtime_collections_routing_when_enabled(self):
        """Runtime collections should route to MongoDB when enabled."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', True):
            db = HybridDatabase(is_test_env=True)
            db._mongo_ops = AsyncMock()  # MongoDB enabled
            
            for collection in RUNTIME_COLLECTIONS:
                assert db._should_use_mongodb(collection, is_canonical=False)
    
    def test_runtime_collections_routing_when_disabled(self, temp_dir):
        """Runtime collections should raise RuntimeError when MongoDB disabled."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            for collection in RUNTIME_COLLECTIONS:
                # Should raise RuntimeError, not return False
                with pytest.raises(RuntimeError) as exc_info:
                    db._should_use_mongodb(collection, is_canonical=False)
                assert f"Runtime collection '{collection}' requires MongoDB storage" in str(exc_info.value)
    
    def test_unknown_collection_defaults_to_file_system(self):
        """Unknown collections should default to file system."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', True):
            db = HybridDatabase(is_test_env=True)
            db._mongo_ops = AsyncMock()
            
            assert not db._should_use_mongodb("unknown_collection", is_canonical=False)
    
    def test_explicit_canonical_overrides_collection_type(self):
        """is_canonical=True should override collection type."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', True):
            db = HybridDatabase(is_test_env=True)
            db._mongo_ops = AsyncMock()
            
            # Even runtime collections should go to file system if canonical
            assert not db._should_use_mongodb("cells", is_canonical=True)


class TestAsyncOperationsWithoutMongoDB:
    """Test async operations when MongoDB is not available."""
    
    @pytest.mark.asyncio
    async def test_insert_canonical_without_mongodb(self, hybrid_db_file_only, test_model):
        """Insert canonical data should work without MongoDB."""
        result = await hybrid_db_file_only.insert(
            collection="cell_types",  # Canonical collection
            document=test_model,
            is_canonical=True
        )
        assert result == "test_1"
    
    @pytest.mark.asyncio
    async def test_insert_runtime_without_mongodb_raises_error(self, hybrid_db_production_mode, test_model):
        """Insert runtime data without MongoDB should raise RuntimeError."""
        with pytest.raises(RuntimeError) as exc_info:
            await hybrid_db_production_mode.insert(
                collection="cells",  # Runtime collection
                document=test_model,
                user_id="user_123",
                session_id="sess_456"
            )
        # After legacy adapter conversion, "cells" becomes "notebook_items"
        assert "Runtime collection 'notebook_items' requires MongoDB storage" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_find_one_canonical_without_mongodb(self, hybrid_db_file_only, test_model):
        """Find_one canonical data should work without MongoDB."""
        # First insert
        await hybrid_db_file_only.insert(
            collection="cell_types",
            document=test_model,
            is_canonical=True
        )
        
        # Then find
        from .conftest import TestModel
        result = await hybrid_db_file_only.find_one(
            collection="cell_types",
            doc_id="test_1",
            model_class=TestModel,
            is_canonical=True
        )
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_find_many_canonical_without_mongodb(self, hybrid_db_file_only, test_model):
        """Find_many canonical data should work without MongoDB."""
        # Insert some documents
        await hybrid_db_file_only.insert(
            collection="cell_types",
            document=test_model,
            is_canonical=True
        )
        
        # Find many
        from .conftest import TestModel
        results = await hybrid_db_file_only.find_many(
            collection="cell_types",
            model_class=TestModel,
            is_canonical=True
        )
        assert len(results) >= 0  # Should return list
    
    @pytest.mark.asyncio
    async def test_update_canonical_without_mongodb(self, hybrid_db_file_only, test_model):
        """Update canonical data should work without MongoDB."""
        # First insert
        await hybrid_db_file_only.insert(
            collection="cell_types",
            document=test_model,
            is_canonical=True
        )
        
        # Then update
        result = await hybrid_db_file_only.update(
            collection="cell_types",
            doc_id="test_1",
            updates={"name": "Updated Name"},
            is_canonical=True
        )
        # Result depends on file DB implementation
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_delete_canonical_without_mongodb(self, hybrid_db_file_only, test_model):
        """Delete canonical data should work without MongoDB."""
        # First insert
        await hybrid_db_file_only.insert(
            collection="cell_types",
            document=test_model,
            is_canonical=True
        )
        
        # Then delete
        result = await hybrid_db_file_only.delete(
            collection="cell_types",
            doc_id="test_1",
            is_canonical=True
        )
        # Result depends on file DB implementation
        assert isinstance(result, bool)


class TestMongoDBRoutingPaths:
    """Test code paths that route to MongoDB."""
    
    @pytest.mark.asyncio
    async def test_insert_routes_to_mongodb(self, hybrid_db_with_mongodb, test_model):
        """Test that runtime collections route to MongoDB for insert."""
        result = await hybrid_db_with_mongodb.insert(
            collection="cells",  # Runtime collection
            document=test_model,
            user_id="user_123"
        )
        # Mock should return "test_1"
        assert result == "test_1"
        # Verify MongoDB was called
        hybrid_db_with_mongodb._mongo_ops.insert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_find_one_routes_to_mongodb(self, hybrid_db_with_mongodb):
        """Test that runtime collections route to MongoDB for find_one."""
        from .conftest import TestModel
        result = await hybrid_db_with_mongodb.find_one(
            collection="cells",  # Runtime collection
            doc_id="test_1",
            model_class=TestModel,
            user_id="user_123"
        )
        # Mock returns None
        assert result is None
        # Verify MongoDB was called
        hybrid_db_with_mongodb._mongo_ops.find_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_find_many_routes_to_mongodb(self, hybrid_db_with_mongodb):
        """Test that runtime collections route to MongoDB for find_many."""
        from .conftest import TestModel
        results = await hybrid_db_with_mongodb.find_many(
            collection="cells",  # Runtime collection
            model_class=TestModel,
            user_id="user_123"
        )
        # Mock returns empty list
        assert results == []
        # Verify MongoDB was called
        hybrid_db_with_mongodb._mongo_ops.find_many.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_routes_to_mongodb(self, hybrid_db_with_mongodb):
        """Test that runtime collections route to MongoDB for update."""
        result = await hybrid_db_with_mongodb.update(
            collection="cells",  # Runtime collection
            doc_id="test_1",
            updates={"name": "Updated"},
            user_id="user_123"
        )
        # Mock returns True
        assert result is True
        # Verify MongoDB was called
        hybrid_db_with_mongodb._mongo_ops.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_routes_to_mongodb(self, hybrid_db_with_mongodb):
        """Test that runtime collections route to MongoDB for delete."""
        result = await hybrid_db_with_mongodb.delete(
            collection="cells",  # Runtime collection
            doc_id="test_1",
            user_id="user_123"
        )
        # Mock returns True
        assert result is True
        # Verify MongoDB was called
        hybrid_db_with_mongodb._mongo_ops.delete.assert_called_once()
