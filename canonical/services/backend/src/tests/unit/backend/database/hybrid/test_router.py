"""
Tests for HybridDatabase router logic.

Tests the intelligent routing between file-based and MongoDB storage
based on collection type and configuration.
"""

import pytest
from unittest.mock import patch, AsyncMock

from app.database.hybrid import HybridDatabase, CANONICAL_COLLECTIONS, RUNTIME_COLLECTIONS
from .conftest import TestModel


class TestCollectionRouting:
    """Test collection routing logic."""
    
    @pytest.mark.asyncio
    async def test_canonical_collection_routes_to_file_system(self, hybrid_db_with_mongodb, test_model):
        """Canonical collections should always route to file system."""
        # Insert into a canonical collection
        result = await hybrid_db_with_mongodb.insert(
            collection="cell_types",
            document=test_model,
            is_canonical=True
        )
        
        assert result == "test_1"
        # MongoDB insert should not be called for canonical data
        hybrid_db_with_mongodb._mongo_ops.insert.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_runtime_collection_routes_to_mongodb_when_enabled(self, hybrid_db_with_mongodb, test_model):
        """Runtime collections should route to MongoDB when enabled."""
        # Insert into a runtime collection
        result = await hybrid_db_with_mongodb.insert(
            collection="cells",  # Runtime collection
            document=test_model,
            user_id="user_123",
            session_id="sess_456"
        )
        
        assert result == "test_1"
        # MongoDB insert should be called
        hybrid_db_with_mongodb._mongo_ops.insert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_runtime_collection_raises_error_when_mongodb_disabled(self, hybrid_db_production_mode, test_model):
        """Runtime collections should raise RuntimeError when MongoDB is disabled."""
        # Attempt to insert into a runtime collection without MongoDB
        with pytest.raises(RuntimeError) as exc_info:
            await hybrid_db_production_mode.insert(
                collection="cells",  # Legacy collection name (converted to notebook_items)
                document=test_model,
                user_id="user_123",
                session_id="sess_456"
            )
        
        # After legacy adapter conversion, "cells" becomes "notebook_items"
        assert "Runtime collection 'notebook_items' requires MongoDB storage" in str(exc_info.value)
        # No MongoDB operations should happen
        assert hybrid_db_production_mode._mongo_ops is None
    
    @pytest.mark.asyncio
    async def test_explicit_canonical_flag_forces_file_system(self, hybrid_db_with_mongodb, test_model):
        """Explicit is_canonical=True should force file system routing."""
        # Even for a runtime collection, is_canonical=True should use file system
        result = await hybrid_db_with_mongodb.insert(
            collection="cells",  # Runtime collection
            document=test_model,
            is_canonical=True  # But explicitly canonical
        )
        
        assert result == "test_1"
        hybrid_db_with_mongodb._mongo_ops.insert.assert_not_called()


class TestRouterDecisions:
    """Test _should_use_mongodb decision logic."""
    
    def test_should_use_mongodb_for_runtime_collection(self, hybrid_db_with_mongodb):
        """Runtime collections should use MongoDB when enabled."""
        for collection in RUNTIME_COLLECTIONS:
            assert hybrid_db_with_mongodb._should_use_mongodb(collection, is_canonical=False)
    
    def test_should_not_use_mongodb_for_canonical_collection(self, hybrid_db_with_mongodb):
        """Canonical collections should never use MongoDB."""
        for collection in CANONICAL_COLLECTIONS:
            assert not hybrid_db_with_mongodb._should_use_mongodb(collection, is_canonical=False)
    
    def test_should_not_use_mongodb_when_explicitly_canonical(self, hybrid_db_with_mongodb):
        """Explicitly canonical flag should prevent MongoDB use."""
        assert not hybrid_db_with_mongodb._should_use_mongodb("cells", is_canonical=True)
    
    def test_should_raise_error_when_mongodb_disabled_for_runtime(self, hybrid_db_production_mode):
        """MongoDB should raise RuntimeError when MONGODB_ENABLED=False for runtime collections."""
        with pytest.raises(RuntimeError) as exc_info:
            # Test with the unified collection name (cells/books are now legacy names converted by adapter)
            hybrid_db_production_mode._should_use_mongodb("notebook_items", is_canonical=False)
        assert "Runtime collection 'notebook_items' requires MongoDB storage" in str(exc_info.value)


class TestCRUDOperations:
    """Test CRUD operations routing."""
    
    @pytest.mark.asyncio
    async def test_insert_routes_correctly(self, hybrid_db_with_mongodb, test_model):
        """Insert operations should route to correct backend."""
        # Canonical insert
        await hybrid_db_with_mongodb.insert("cell_types", test_model, is_canonical=True)
        hybrid_db_with_mongodb._mongo_ops.insert.assert_not_called()
        
        # Runtime insert
        hybrid_db_with_mongodb._mongo_ops.insert.reset_mock()
        await hybrid_db_with_mongodb.insert("cells", test_model, user_id="user_123")
        hybrid_db_with_mongodb._mongo_ops.insert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_find_one_routes_correctly(self, hybrid_db_with_mongodb):
        """Find_one operations should route to correct backend."""
        # Canonical find_one
        await hybrid_db_with_mongodb.find_one(
            "cell_types", "test_1", TestModel, is_canonical=True
        )
        hybrid_db_with_mongodb._mongo_ops.find_one.assert_not_called()
        
        # Runtime find_one
        hybrid_db_with_mongodb._mongo_ops.find_one.reset_mock()
        await hybrid_db_with_mongodb.find_one(
            "cells", "test_1", TestModel, user_id="user_123"
        )
        hybrid_db_with_mongodb._mongo_ops.find_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_routes_correctly(self, hybrid_db_with_mongodb):
        """Update operations should route to correct backend."""
        # Canonical update
        await hybrid_db_with_mongodb.update(
            "cell_types", "test_1", {"name": "Updated"}, is_canonical=True
        )
        hybrid_db_with_mongodb._mongo_ops.update.assert_not_called()
        
        # Runtime update
        hybrid_db_with_mongodb._mongo_ops.update.reset_mock()
        await hybrid_db_with_mongodb.update(
            "cells", "test_1", {"name": "Updated"}, user_id="user_123"
        )
        hybrid_db_with_mongodb._mongo_ops.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_routes_correctly(self, hybrid_db_with_mongodb):
        """Delete operations should route to correct backend."""
        # Canonical delete
        await hybrid_db_with_mongodb.delete(
            "cell_types", "test_1", is_canonical=True
        )
        hybrid_db_with_mongodb._mongo_ops.delete.assert_not_called()
        
        # Runtime delete
        hybrid_db_with_mongodb._mongo_ops.delete.reset_mock()
        await hybrid_db_with_mongodb.delete(
            "cells", "test_1", user_id="user_123"
        )
        hybrid_db_with_mongodb._mongo_ops.delete.assert_called_once()


class TestCacheInvalidation:
    """Test cache invalidation on MongoDB writes."""
    
    @pytest.mark.asyncio
    async def test_insert_invalidates_cache(self, hybrid_db_with_mongodb, test_model):
        """Insert to MongoDB should invalidate related cache entries."""
        with patch.object(
            hybrid_db_with_mongodb._file_db,
            '_invalidate_collection_cache',
            new_callable=AsyncMock
        ) as mock_invalidate:
            await hybrid_db_with_mongodb.insert(
                "cells", test_model, user_id="user_123"
            )
            
            # Check that cache invalidation was called
            assert mock_invalidate.called
            # After legacy adapter conversion, "cells" becomes "notebook_items"
            call_str = str(mock_invalidate.call_args)
            assert "notebook_items" in call_str
    
    @pytest.mark.asyncio
    async def test_update_invalidates_cache(self, hybrid_db_with_mongodb):
        """Update to MongoDB should invalidate related cache entries."""
        with patch.object(
            hybrid_db_with_mongodb._file_db,
            '_invalidate_collection_cache',
            new_callable=AsyncMock
        ) as mock_invalidate:
            await hybrid_db_with_mongodb.update(
                "cells", "test_1", {"name": "Updated"}, user_id="user_123"
            )
            
            # Check that cache invalidation was called
            assert mock_invalidate.called
            # After legacy adapter conversion, "cells" becomes "notebook_items"
            call_str = str(mock_invalidate.call_args)
            assert "notebook_items" in call_str
    
    @pytest.mark.asyncio
    async def test_delete_invalidates_cache(self, hybrid_db_with_mongodb):
        """Delete from MongoDB should invalidate related cache entries."""
        with patch.object(
            hybrid_db_with_mongodb._file_db,
            '_invalidate_collection_cache',
            new_callable=AsyncMock
        ) as mock_invalidate:
            await hybrid_db_with_mongodb.delete(
                "cells", "test_1", user_id="user_123"
            )
            
            # Check that cache invalidation was called
            assert mock_invalidate.called
            # After legacy adapter conversion, "cells" becomes "notebook_items"
            call_str = str(mock_invalidate.call_args)
            assert "notebook_items" in call_str


class TestBackwardCompatibility:
    """Test synchronous methods for backward compatibility."""
    
    def test_insert_sync_raises_error_for_runtime_collections(self, hybrid_db_production_mode, test_model):
        """Synchronous insert should raise RuntimeError for runtime collections."""
        with pytest.raises(RuntimeError) as exc_info:
            hybrid_db_production_mode.insert_sync(
                "cells", test_model, user_id="user_123"
            )
        
        # After legacy adapter conversion, "cells" becomes "notebook_items"
        assert "DEPRECATED: Synchronous insert attempted for runtime collection 'notebook_items'" in str(exc_info.value)
    
    def test_insert_sync_works_for_canonical_collections(self, hybrid_db_production_mode, test_model):
        """Synchronous insert should work for canonical collections (with deprecation warning)."""
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            result = hybrid_db_production_mode.insert_sync(
                "cell_types", test_model, is_canonical=True
            )
            
            assert result == "test_1"
            # Should have DeprecationWarning
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
    
    def test_config_operations_work(self, hybrid_db_file_only):
        """Configuration operations should work."""
        config_data = {"key": "value", "enabled": True}
        
        # Set config
        result = hybrid_db_file_only.set_config("test_config", config_data)
        assert result is True
        
        # Get config
        retrieved = hybrid_db_file_only.get_config("test_config")
        assert retrieved == config_data
