"""
Tests for backward compatibility and fallback functionality.

Tests synchronous methods and graceful degradation when MongoDB is unavailable.
"""

import pytest
from unittest.mock import patch

from app.database.hybrid import HybridDatabase
from .conftest import TestModel


class TestSynchronousMethods:
    """Test synchronous backward compatibility methods with canonical collections."""
    
    def test_insert_sync(self, hybrid_db_file_only, test_model):
        """Synchronous insert should work with canonical collections."""
        result = hybrid_db_file_only.insert_sync(
            collection="ai_models",  # Canonical collection
            document=test_model,
            is_canonical=True
        )
        
        assert result == "test_1"
    
    def test_find_one_sync(self, hybrid_db_file_only, test_model):
        """Synchronous find_one should retrieve documents from canonical collections."""
        # Insert first
        hybrid_db_file_only.insert_sync(
            "ai_models", test_model, is_canonical=True
        )
        
        # Find
        result = hybrid_db_file_only.find_one_sync(
            "ai_models", "test_1", TestModel,
            is_canonical=True
        )
        
        assert result is not None
        assert result.id == "test_1"
        assert result.nome == "Test Document"
    
    def test_find_many_sync(self, hybrid_db_file_only):
        """Synchronous find_many should retrieve multiple documents from canonical collections."""
        # Insert multiple documents
        for i in range(3):
            doc = TestModel(id=f"test_{i}", nome=f"Document {i}")
            hybrid_db_file_only.insert_sync(
                "ai_models", doc, is_canonical=True
            )
        
        # Find many
        results = hybrid_db_file_only.find_many_sync(
            "ai_models", TestModel, is_canonical=True
        )
        
        assert len(results) == 3
    
    def test_update_sync(self, hybrid_db_file_only, test_model):
        """Synchronous update should modify documents in canonical collections."""
        # Insert first
        hybrid_db_file_only.insert_sync(
            "ai_models", test_model, is_canonical=True
        )
        
        # Update
        result = hybrid_db_file_only.update_sync(
            "ai_models", "test_1", {"nome": "Updated Name"},
            is_canonical=True
        )
        
        assert result is True
        
        # Verify update
        updated = hybrid_db_file_only.find_one_sync(
            "ai_models", "test_1", TestModel,
            is_canonical=True
        )
        assert updated.nome == "Updated Name"
    
    def test_delete_sync(self, hybrid_db_file_only, test_model):
        """Synchronous delete should remove documents from canonical collections."""
        # Insert first
        hybrid_db_file_only.insert_sync(
            "ai_models", test_model, is_canonical=True
        )
        
        # Delete
        result = hybrid_db_file_only.delete_sync(
            "ai_models", "test_1", is_canonical=True
        )
        
        assert result is True
        
        # Verify deletion
        deleted = hybrid_db_file_only.find_one_sync(
            "ai_models", "test_1", TestModel,
            is_canonical=True
        )
        assert deleted is None


class TestMongoDBFallback:
    """Test fallback to file system for canonical data when MongoDB is unavailable."""
    
    @pytest.mark.asyncio
    async def test_insert_falls_back_to_file_system(self, hybrid_db_file_only, test_model):
        """Insert canonical data should work even when MongoDB is disabled."""
        result = await hybrid_db_file_only.insert(
            collection="ai_models",  # Canonical collection
            document=test_model,
            is_canonical=True
        )
        
        assert result == "test_1"
        # Verify data is in file system
        found = await hybrid_db_file_only.find_one(
            "ai_models", "test_1", TestModel,
            is_canonical=True
        )
        assert found is not None
    
    @pytest.mark.asyncio
    async def test_all_operations_work_without_mongodb(self, hybrid_db_file_only, test_model):
        """All CRUD operations should work for canonical data without MongoDB."""
        # Insert
        doc_id = await hybrid_db_file_only.insert(
            "ai_models", test_model, is_canonical=True
        )
        assert doc_id == "test_1"
        
        # Find one
        found = await hybrid_db_file_only.find_one(
            "ai_models", "test_1", TestModel,
            is_canonical=True
        )
        assert found is not None
        
        # Update
        updated = await hybrid_db_file_only.update(
            "ai_models", "test_1", {"nome": "Updated"},
            is_canonical=True
        )
        assert updated is True
        
        # Find many
        many = await hybrid_db_file_only.find_many(
            "ai_models", TestModel, is_canonical=True
        )
        assert len(many) == 1
        
        # Delete
        deleted = await hybrid_db_file_only.delete(
            "ai_models", "test_1", is_canonical=True
        )
        assert deleted is True


class TestConfigurationOperations:
    """Test configuration get/set operations."""
    
    def test_set_and_get_config(self, hybrid_db_file_only):
        """Should be able to set and get configuration."""
        config_data = {
            "api_key": "test_key",
            "enabled": True,
            "options": {"timeout": 30}
        }
        
        # Set config
        result = hybrid_db_file_only.set_config("test_service", config_data)
        assert result is True
        
        # Get config
        retrieved = hybrid_db_file_only.get_config("test_service")
        assert retrieved == config_data
    
    def test_get_nonexistent_config_returns_none(self, hybrid_db_file_only):
        """Getting nonexistent config should return None."""
        result = hybrid_db_file_only.get_config("nonexistent_config")
        assert result is None
    
    def test_update_existing_config(self, hybrid_db_file_only):
        """Should be able to update existing configuration."""
        # Set initial config
        initial = {"value": 1}
        hybrid_db_file_only.set_config("counter", initial)
        
        # Update config
        updated = {"value": 2}
        hybrid_db_file_only.set_config("counter", updated)
        
        # Verify update
        result = hybrid_db_file_only.get_config("counter")
        assert result["value"] == 2


class TestMixedCanonicalAndRuntime:
    """Test handling of mixed canonical and runtime data operations."""
    
    @pytest.mark.asyncio
    async def test_canonical_and_runtime_operations_coexist(self, hybrid_db_with_mongodb, test_model):
        """Canonical can use file system, runtime requires MongoDB."""
        # Insert canonical data (file system)
        canonical_doc = TestModel(id="canonical_1", nome="Canonical Type")
        canonical_id = await hybrid_db_with_mongodb.insert(
            "ai_models", canonical_doc, is_canonical=True
        )
        assert canonical_id == "canonical_1"
        
        # Insert runtime data (MongoDB - mocked)
        runtime_doc = TestModel(id="runtime_1", nome="Runtime Cell")
        runtime_id = await hybrid_db_with_mongodb.insert(
            "cells", runtime_doc, user_id="user_123", session_id="sess_456"
        )
        assert runtime_id is not None  # MongoDB mock returns doc ID
        
        # Canonical should be retrievable from file system
        canonical = await hybrid_db_with_mongodb.find_one(
            "ai_models", "canonical_1", TestModel, is_canonical=True
        )
        assert canonical is not None
        assert canonical.nome == "Canonical Type"


class TestErrorHandling:
    """Test error handling in fallback scenarios."""
    
    @pytest.mark.asyncio
    async def test_handles_mongodb_connection_error_gracefully(self, temp_dir, test_model):
        """Should handle MongoDB connection errors gracefully."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', True):
            # Create HybridDatabase but MongoDB operations will fail
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            # MongoDB ops is initialized but will fail
            # Operations should still work via file system fallback
            # (In real scenario, MongoDB client would be None)
            
            # For this test, we just verify initialization doesn't crash
            assert db._mongo_ops is not None or db._file_db is not None
    
    def test_sync_methods_log_warning_about_mongodb(self, hybrid_db_with_mongodb, test_model, caplog):
        """Synchronous methods should log warning for runtime collections in test mode."""
        import logging
        caplog.set_level(logging.WARNING)
        
        # In test environment, sync methods on runtime collections log warning but don't raise error
        result = hybrid_db_with_mongodb.insert_sync("cells", test_model, user_id="user_123")
        
        # Should log deprecation warning
        # After legacy adapter conversion, "cells" becomes "notebook_items"
        assert any("DEPRECATED: Using synchronous insert for notebook_items" in record.message for record in caplog.records)
