"""
Tests for MongoDB enforcement policy (Issue #880 - Subissue 5).

Tests that runtime collections MUST use MongoDB and cannot fall back to disk storage.
This ensures data integrity by preventing silent failures and mixed storage states.
"""

import pytest
from unittest.mock import patch

from app.database.hybrid import HybridDatabase, RUNTIME_COLLECTIONS
from .conftest import TestModel


class TestMongoDBEnforcementForRuntimeCollections:
    """Test that runtime collections enforce MongoDB-only storage IN PRODUCTION (not in tests)."""
    
    @pytest.mark.asyncio
    async def test_runtime_collection_requires_mongodb_for_insert(self, temp_dir, test_model):
        """Runtime collections should raise RuntimeError when MongoDB is disabled in PRODUCTION (insert)."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            # NOTE: is_test_env=False to simulate production environment
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            # Attempt to insert into runtime collection without MongoDB
            with pytest.raises(RuntimeError) as exc_info:
                await db.insert(
                    collection="cells",
                    document=test_model,
                    user_id="user_123",
                    session_id="sess_456"
                )
            
            # Verify error message is clear and actionable
            error_msg = str(exc_info.value)
            # After legacy adapter conversion, "cells" becomes "notebook_items"
            assert "Runtime collection 'notebook_items' requires MongoDB storage" in error_msg
            assert "MongoDB is not enabled" in error_msg
            assert "MUST NOT be stored on disk" in error_msg
            assert "Please enable MongoDB" in error_msg
    
    @pytest.mark.asyncio
    async def test_runtime_collection_requires_mongodb_for_find_one(self, temp_dir):
        """Runtime collections should raise RuntimeError when MongoDB is disabled in PRODUCTION (find_one)."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            # NOTE: is_test_env=False to simulate production environment
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            with pytest.raises(RuntimeError) as exc_info:
                await db.find_one(
                    collection="books",
                    doc_id="book_123",
                    model_class=TestModel,
                    user_id="user_123"
                )
            
            error_msg = str(exc_info.value)
            # After legacy adapter conversion, "books" becomes "notebook_items"
            assert "Runtime collection 'notebook_items' requires MongoDB storage" in error_msg
    
    @pytest.mark.asyncio
    async def test_runtime_collection_requires_mongodb_for_update(self, temp_dir):
        """Runtime collections should raise RuntimeError when MongoDB is disabled in PRODUCTION (update)."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            # NOTE: is_test_env=False to simulate production environment
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            with pytest.raises(RuntimeError) as exc_info:
                await db.update(
                    collection="sessions",
                    doc_id="session_123",
                    updates={"status": "active"},
                    user_id="user_123"
                )
            
            error_msg = str(exc_info.value)
            assert "Runtime collection 'sessions' requires MongoDB storage" in error_msg
    
    @pytest.mark.asyncio
    async def test_runtime_collection_requires_mongodb_for_delete(self, temp_dir):
        """Runtime collections should raise RuntimeError when MongoDB is disabled in PRODUCTION (delete)."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            # NOTE: is_test_env=False to simulate production environment
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            with pytest.raises(RuntimeError) as exc_info:
                await db.delete(
                    collection="users",
                    doc_id="user_123",
                    user_id="user_123"
                )
            
            error_msg = str(exc_info.value)
            assert "Runtime collection 'users' requires MongoDB storage" in error_msg
    
    @pytest.mark.asyncio
    async def test_runtime_collection_requires_mongodb_for_find_many(self, temp_dir):
        """Runtime collections should raise RuntimeError when MongoDB is disabled in PRODUCTION (find_many)."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            # NOTE: is_test_env=False to simulate production environment
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            with pytest.raises(RuntimeError) as exc_info:
                await db.find_many(
                    collection="memory",
                    model_class=TestModel,
                    user_id="user_123"
                )
            
            error_msg = str(exc_info.value)
            assert "Runtime collection 'memory' requires MongoDB storage" in error_msg
    
    @pytest.mark.parametrize("collection", RUNTIME_COLLECTIONS)
    @pytest.mark.asyncio
    async def test_all_runtime_collections_enforce_mongodb(self, temp_dir, test_model, collection):
        """All runtime collections should enforce MongoDB requirement IN PRODUCTION."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            # NOTE: is_test_env=False to simulate production environment
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            # Test insert for each runtime collection
            with pytest.raises(RuntimeError) as exc_info:
                await db.insert(
                    collection=collection,
                    document=test_model,
                    user_id="user_123",
                    session_id="sess_456"
                )
            
            error_msg = str(exc_info.value)
            assert f"Runtime collection '{collection}' requires MongoDB storage" in error_msg
            assert "MONGODB_ENABLED=False" in error_msg or "MongoDB is not enabled" in error_msg


class TestMongoDBEnforcementErrorMessages:
    """Test that error messages are clear and actionable IN PRODUCTION."""
    
    @pytest.mark.asyncio
    async def test_error_message_includes_collection_name(self, temp_dir, test_model):
        """Error message should include the specific collection name IN PRODUCTION."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            # NOTE: is_test_env=False to simulate production environment
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            with pytest.raises(RuntimeError) as exc_info:
                await db.insert("traces", test_model, user_id="user_123")
            
            assert "traces" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_error_message_includes_mongodb_status(self, temp_dir, test_model):
        """Error message should include MongoDB enabled status IN PRODUCTION."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            # NOTE: is_test_env=False to simulate production environment
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            with pytest.raises(RuntimeError) as exc_info:
                await db.insert("cells", test_model, user_id="user_123")
            
            error_msg = str(exc_info.value)
            assert "MONGODB_ENABLED=False" in error_msg or "MongoDB is not enabled" in error_msg
    
    @pytest.mark.asyncio
    async def test_error_message_provides_solution(self, temp_dir, test_model):
        """Error message should suggest how to fix the problem IN PRODUCTION."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            # NOTE: is_test_env=False to simulate production environment
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            with pytest.raises(RuntimeError) as exc_info:
                await db.insert("cells", test_model, user_id="user_123")
            
            error_msg = str(exc_info.value)
            assert "enable MongoDB" in error_msg.lower() or "Please enable MongoDB" in error_msg
    
    @pytest.mark.asyncio
    async def test_error_message_explains_policy(self, temp_dir, test_model):
        """Error message should explain the MongoDB-only policy IN PRODUCTION."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            # NOTE: is_test_env=False to simulate production environment
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            with pytest.raises(RuntimeError) as exc_info:
                await db.insert("cells", test_model, user_id="user_123")
            
            error_msg = str(exc_info.value)
            assert "MUST NOT be stored on disk" in error_msg


class TestCanonicalCollectionsStillWorkWithoutMongoDB:
    """Test that canonical collections work fine without MongoDB."""
    
    @pytest.mark.asyncio
    async def test_canonical_collection_works_without_mongodb(self, temp_dir, test_model):
        """Canonical collections should work without MongoDB."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            db = HybridDatabase(base_path=temp_dir, is_test_env=True)
            
            # Should NOT raise RuntimeError
            result = await db.insert(
                collection="cell_types",
                document=test_model,
                is_canonical=True
            )
            
            assert result == "test_1"
    
    @pytest.mark.asyncio
    async def test_explicit_canonical_flag_bypasses_mongodb_requirement(self, temp_dir, test_model):
        """Explicit is_canonical=True should bypass MongoDB requirement."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            db = HybridDatabase(base_path=temp_dir, is_test_env=True)
            
            # Even for runtime collection, is_canonical=True should work
            result = await db.insert(
                collection="cells",
                document=test_model,
                is_canonical=True  # Explicitly canonical
            )
            
            assert result == "test_1"


class TestMongoDBEnforcementWithMongoDBEnabled:
    """Test that operations work correctly when MongoDB is enabled."""
    
    @pytest.mark.asyncio
    async def test_runtime_collection_uses_mongodb_when_enabled(self, hybrid_db_with_mongodb, test_model):
        """Runtime collections should use MongoDB when it's enabled."""
        # Should NOT raise RuntimeError
        result = await hybrid_db_with_mongodb.insert(
            collection="cells",
            document=test_model,
            user_id="user_123",
            session_id="sess_456"
        )
        
        assert result == "test_1"
        # Verify MongoDB was called
        hybrid_db_with_mongodb._mongo_ops.insert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_all_crud_operations_work_with_mongodb(self, hybrid_db_with_mongodb, test_model):
        """All CRUD operations should work when MongoDB is enabled."""
        # Insert
        await hybrid_db_with_mongodb.insert("cells", test_model, user_id="user_123")
        assert hybrid_db_with_mongodb._mongo_ops.insert.called
        
        # Find one
        hybrid_db_with_mongodb._mongo_ops.find_one.reset_mock()
        await hybrid_db_with_mongodb.find_one("cells", "test_1", TestModel, user_id="user_123")
        assert hybrid_db_with_mongodb._mongo_ops.find_one.called
        
        # Update
        hybrid_db_with_mongodb._mongo_ops.update.reset_mock()
        await hybrid_db_with_mongodb.update("cells", "test_1", {"name": "Updated"}, user_id="user_123")
        assert hybrid_db_with_mongodb._mongo_ops.update.called
        
        # Delete
        hybrid_db_with_mongodb._mongo_ops.delete.reset_mock()
        await hybrid_db_with_mongodb.delete("cells", "test_1", user_id="user_123")
        assert hybrid_db_with_mongodb._mongo_ops.delete.called
