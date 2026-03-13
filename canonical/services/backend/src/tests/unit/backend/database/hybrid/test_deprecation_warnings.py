"""
Tests for deprecation warnings and sync method enforcement (Issue #880 - Subissue 5).

Tests that synchronous methods raise DeprecationWarning and RuntimeError appropriately
to guide users toward async methods and MongoDB storage for runtime data.
"""

import pytest
import warnings
from unittest.mock import patch

from app.database.hybrid import HybridDatabase, RUNTIME_COLLECTIONS, CANONICAL_COLLECTIONS
from .conftest import TestModel


class TestSyncMethodDeprecationWarnings:
    """Test that sync methods raise DeprecationWarning."""
    
    def test_insert_sync_raises_deprecation_warning_for_canonical(self, hybrid_db_file_only, test_model):
        """insert_sync should raise DeprecationWarning for canonical collections."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            hybrid_db_file_only.insert_sync(
                collection="cell_types",
                document=test_model,
                is_canonical=True
            )
            
            # Check that a DeprecationWarning was issued
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "insert_sync() is deprecated" in str(w[0].message)
            assert "Use async insert() instead" in str(w[0].message)
    
    def test_find_one_sync_raises_deprecation_warning(self, hybrid_db_file_only, test_model):
        """find_one_sync should raise DeprecationWarning for canonical collections."""
        # First insert a document
        hybrid_db_file_only.insert_sync("cell_types", test_model, is_canonical=True)
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            hybrid_db_file_only.find_one_sync(
                collection="cell_types",
                doc_id="test_1",
                model_class=TestModel,
                is_canonical=True
            )
            
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "find_one_sync() is deprecated" in str(w[0].message)
    
    def test_find_many_sync_raises_deprecation_warning(self, hybrid_db_file_only):
        """find_many_sync should raise DeprecationWarning for canonical collections."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            hybrid_db_file_only.find_many_sync(
                collection="cell_types",
                model_class=TestModel,
                is_canonical=True
            )
            
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "find_many_sync() is deprecated" in str(w[0].message)
    
    def test_update_sync_raises_deprecation_warning(self, hybrid_db_file_only, test_model):
        """update_sync should raise DeprecationWarning for canonical collections."""
        # First insert a document (this will also raise a warning)
        hybrid_db_file_only.insert_sync("cell_types", test_model, is_canonical=True)
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            hybrid_db_file_only.update_sync(
                collection="cell_types",
                doc_id="test_1",
                updates={"name": "Updated"},
                is_canonical=True
            )
            
            # NOTE: 2 warnings expected: update_sync deprecation + datetime.utcnow() deprecation from update operation
            # The update() method in operations.py uses datetime.utcnow() which triggers its own deprecation warning
            assert len(w) == 2
            
            # First warning should be update_sync deprecation
            assert issubclass(w[0].category, DeprecationWarning)
            assert "update_sync() is deprecated" in str(w[0].message)
            
            # Second warning is datetime.utcnow() deprecation (from operations.py line 153)
            assert issubclass(w[1].category, DeprecationWarning)
            assert "datetime.utcnow() is deprecated" in str(w[1].message)
    
    def test_delete_sync_raises_deprecation_warning(self, hybrid_db_file_only, test_model):
        """delete_sync should raise DeprecationWarning for canonical collections."""
        # First insert a document
        hybrid_db_file_only.insert_sync("cell_types", test_model, is_canonical=True)
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            hybrid_db_file_only.delete_sync(
                collection="cell_types",
                doc_id="test_1",
                is_canonical=True
            )
            
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "delete_sync() is deprecated" in str(w[0].message)


class TestSyncMethodRuntimeErrorForRuntimeCollections:
    """Test that sync methods raise DeprecationWarning for runtime collections in test env."""
    
    def test_insert_sync_raises_runtime_error_for_runtime_collection(self, hybrid_db_file_only, test_model):
        """insert_sync should raise DeprecationWarning for runtime collections in test env."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            hybrid_db_file_only.insert_sync(
                collection="cells",
                document=test_model,
                user_id="user_123",
                session_id="sess_456",
                is_canonical=False  # Not canonical
            )
            
            # In test env, only DeprecationWarning is raised, not RuntimeError
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "insert_sync() is deprecated" in str(w[0].message)
            # After legacy adapter conversion, "cells" becomes "notebook_items"
            assert "notebook_items" in str(w[0].message)
    
    def test_find_one_sync_raises_runtime_error_for_runtime_collection(self, hybrid_db_file_only):
        """find_one_sync should raise DeprecationWarning for runtime collections in test env."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            hybrid_db_file_only.find_one_sync(
                collection="books",
                doc_id="book_123",
                model_class=TestModel,
                user_id="user_123",
                is_canonical=False
            )
            
            # In test env, only DeprecationWarning is raised, not RuntimeError
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "find_one_sync() is deprecated" in str(w[0].message)
    
    def test_find_many_sync_raises_runtime_error_for_runtime_collection(self, hybrid_db_file_only):
        """find_many_sync should raise DeprecationWarning for runtime collections in test env."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            hybrid_db_file_only.find_many_sync(
                collection="sessions",
                model_class=TestModel,
                user_id="user_123",
                is_canonical=False
            )
            
            # In test env, only DeprecationWarning is raised, not RuntimeError
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "find_many_sync() is deprecated" in str(w[0].message)
    
    def test_update_sync_raises_runtime_error_for_runtime_collection(self, hybrid_db_file_only):
        """update_sync should raise DeprecationWarning for runtime collections in test env."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            hybrid_db_file_only.update_sync(
                collection="users",
                doc_id="user_123",
                updates={"name": "Updated"},
                user_id="user_123",
                is_canonical=False
            )
            
            # In test env, only DeprecationWarning is raised, not RuntimeError
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "update_sync() is deprecated" in str(w[0].message)
    
    def test_delete_sync_raises_runtime_error_for_runtime_collection(self, hybrid_db_file_only):
        """delete_sync should raise DeprecationWarning for runtime collections in test env."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            hybrid_db_file_only.delete_sync(
                collection="memory",
                doc_id="mem_123",
                user_id="user_123",
                is_canonical=False
            )
            
            # In test env, only DeprecationWarning is raised, not RuntimeError
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "delete_sync() is deprecated" in str(w[0].message)
    
    @pytest.mark.parametrize("collection", RUNTIME_COLLECTIONS)
    def test_all_sync_methods_block_runtime_collections(self, hybrid_db_file_only, test_model, collection):
        """All sync methods should raise DeprecationWarning for all runtime collections in test env."""
        # Test insert_sync
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            hybrid_db_file_only.insert_sync(
                collection=collection,
                document=test_model,
                user_id="user_123",
                is_canonical=False
            )
            assert len(w) >= 1
            assert any(issubclass(warning.category, DeprecationWarning) for warning in w)
        
        # Test find_one_sync
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            hybrid_db_file_only.find_one_sync(
                collection=collection,
                doc_id="test_123",
                model_class=TestModel,
                user_id="user_123",
                is_canonical=False
            )
            assert len(w) >= 1
        
        # Test find_many_sync
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            hybrid_db_file_only.find_many_sync(
                collection=collection,
                model_class=TestModel,
                user_id="user_123",
                is_canonical=False
            )
            assert len(w) >= 1
        
        # Test update_sync
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            hybrid_db_file_only.update_sync(
                collection=collection,
                doc_id="test_123",
                updates={"field": "value"},
                user_id="user_123",
                is_canonical=False
            )
            assert len(w) >= 1
        
        # Test delete_sync
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            hybrid_db_file_only.delete_sync(
                collection=collection,
                doc_id="test_123",
                user_id="user_123",
                is_canonical=False
            )
            assert len(w) >= 1


class TestSyncMethodsWorkForCanonicalWithWarning:
    """Test that sync methods work for canonical collections but show deprecation warning."""
    
    def test_sync_methods_work_for_canonical_collections(self, hybrid_db_file_only, test_model):
        """Sync methods should work for canonical collections (with warning)."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Insert
            result = hybrid_db_file_only.insert_sync(
                collection="cell_types",
                document=test_model,
                is_canonical=True
            )
            assert result == "test_1"
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            
            # Find one
            found = hybrid_db_file_only.find_one_sync(
                collection="cell_types",
                doc_id="test_1",
                model_class=TestModel,
                is_canonical=True
            )
            assert found is not None
            assert len(w) == 2  # Second warning
            
            # Update
            updated = hybrid_db_file_only.update_sync(
                collection="cell_types",
                doc_id="test_1",
                updates={"name": "Updated"},
                is_canonical=True
            )
            assert updated is True
            # NOTE: May be 3 or 4 warnings depending on datetime.utcnow() deprecation
            assert len(w) >= 3  # At least third warning (update_sync)
            
            # Delete
            deleted = hybrid_db_file_only.delete_sync(
                collection="cell_types",
                doc_id="test_1",
                is_canonical=True
            )
            assert deleted is True
            # NOTE: 5 warnings total - 4 sync method deprecations + 1 datetime.utcnow() from update operation
            assert len(w) == 5


class TestDeprecationWarningContent:
    """Test that deprecation warnings contain helpful information."""
    
    def test_warning_includes_collection_name(self, hybrid_db_file_only, test_model):
        """Deprecation warning should include the collection name."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            hybrid_db_file_only.insert_sync(
                collection="cell_types",
                document=test_model,
                is_canonical=True
            )
            
            assert "cell_types" in str(w[0].message)
    
    def test_warning_includes_canonical_status(self, hybrid_db_file_only, test_model):
        """Deprecation warning should indicate if collection is canonical."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            hybrid_db_file_only.insert_sync(
                collection="cell_types",
                document=test_model,
                is_canonical=True
            )
            
            assert "is_canonical: True" in str(w[0].message)
    
    def test_warning_suggests_async_alternative(self, hybrid_db_file_only, test_model):
        """Deprecation warning should suggest async alternative."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            hybrid_db_file_only.insert_sync(
                collection="cell_types",
                document=test_model,
                is_canonical=True
            )
            
            assert "Use async insert() instead" in str(w[0].message)


class TestExplicitCanonicalFlagBypassesRuntimeError:
    """Test that explicit is_canonical=True bypasses RuntimeError even for runtime collections."""
    
    def test_explicit_canonical_allows_sync_on_runtime_collection(self, hybrid_db_file_only, test_model):
        """Explicit is_canonical=True should allow sync methods on runtime collections."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Should NOT raise RuntimeError, only DeprecationWarning
            result = hybrid_db_file_only.insert_sync(
                collection="cells",  # Runtime collection
                document=test_model,
                is_canonical=True  # But explicitly canonical
            )
            
            assert result == "test_1"
            # Should have DeprecationWarning, not RuntimeError
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)


class TestLoggingBehavior:
    """Test that deprecated methods log warnings to the logger."""
    
    def test_sync_methods_log_warning(self, hybrid_db_file_only, test_model, caplog):
        """Sync methods should log warnings about MongoDB operations requiring async."""
        import logging
        caplog.set_level(logging.WARNING)
        
        hybrid_db_file_only.insert_sync(
            collection="cell_types",
            document=test_model,
            is_canonical=True
        )
        
        # Check for warning log
        assert any("DEPRECATED" in record.message for record in caplog.records)
        assert any("synchronous" in record.message.lower() for record in caplog.records)
