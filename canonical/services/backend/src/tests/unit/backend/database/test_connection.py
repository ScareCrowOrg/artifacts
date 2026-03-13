"""
Unit tests for app/database/connection.py

Tests JSONDatabase initialization, path management, and directory operations.
Ensures proper handling of runtime vs canonical artifacts, test mode, and cleanup.
"""

import pytest
import tempfile
from pathlib import Path
import os

from app.database.connection import JSONDatabase, get_db_instance


class TestJSONDatabaseInitialization:
    """Test database initialization and configuration."""
    
    def test_init_with_default_path_test_mode(self):
        """Test initialization in test mode creates temporary directory."""
        db = JSONDatabase(is_test_env=True)
        
        assert db.base_path.exists()
        assert db.runtime_path.exists()
        assert db.canonical_path.exists()
        assert db.is_test_env is True
        
        # Cleanup
        db.cleanup_test_data()
    
    def test_init_with_explicit_path(self):
        """Test initialization with explicit base path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir) / "custom_artifacts"
            db = JSONDatabase(base_path=base_path, is_test_env=True)
            
            assert db.base_path == base_path
            assert db.base_path.exists()
            assert db.runtime_path == base_path / "runtime"
            assert db.canonical_path == base_path / "canonical"
    
    def test_init_creates_required_directories(self):
        """Test that initialization creates all required directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db = JSONDatabase(base_path=Path(temp_dir), is_test_env=True)
            
            # Check runtime directories
            assert (db.runtime_path / "cells").exists()
            assert (db.runtime_path / "books").exists()
            assert (db.runtime_path / "memory").exists()
            assert (db.runtime_path / "users").exists()
            assert (db.runtime_path / "sessions").exists()
            
            # Check canonical directories (from CANONICAL_COLLECTIONS)
            assert (db.canonical_path / "cells").exists()
            assert (db.canonical_path / "books").exists()
            assert (db.canonical_path / "templates").exists()
            assert (db.canonical_path / "notebook_item_types").exists()
            assert (db.canonical_path / "ai_models").exists()
            assert (db.canonical_path / "workflows").exists()
            assert (db.canonical_path / "agent_types").exists()
            assert (db.canonical_path / "permissions").exists()
            assert (db.canonical_path / "roles").exists()
            
            # Check config directory
            assert (db.base_path / "config").exists()
    
    def test_init_test_mode_flag(self):
        """Test is_test_env flag is properly set."""
        db_test = JSONDatabase(is_test_env=True)
        assert db_test.is_test_env is True
        db_test.cleanup_test_data()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            db_runtime = JSONDatabase(base_path=Path(temp_dir), is_test_env=False)
            assert db_runtime.is_test_env is False


class TestPathManagement:
    """Test path resolution and document location methods."""
    
    def test_get_collection_path_canonical(self, test_db):
        """Test collection path for canonical artifacts."""
        path = test_db._get_collection_path("cells", is_canonical=True)
        
        assert path == test_db.canonical_path / "cells"
        assert path.exists()
    
    def test_get_collection_path_runtime(self, test_db):
        """Test collection path for runtime artifacts."""
        path = test_db._get_collection_path("cells", is_canonical=False)
        
        assert path == test_db.runtime_path / "cells"
        assert path.exists()
    
    def test_get_document_path_canonical(self, test_db):
        """Test document path for canonical artifact."""
        doc_path = test_db._get_document_path(
            "cell_types", 
            "tipo_code",
            is_canonical=True
        )
        
        expected = test_db.canonical_path / "cell_types" / "tipo_code.json"
        assert doc_path == expected
    
    def test_get_document_path_runtime_with_user_session(self, test_db):
        """Test document path for runtime artifact with user and session."""
        doc_path = test_db._get_document_path(
            "cells",
            "cel_123",
            user_id="user_1",
            session_id="session_1",
            is_canonical=False
        )
        
        expected = (
            test_db.runtime_path / "cells" / "user_1" / "session_1" / "cel_123.json"
        )
        assert doc_path == expected
        # Should create parent directories
        assert doc_path.parent.exists()
    
    def test_get_document_path_runtime_without_user_session(self, test_db):
        """Test document path for runtime artifact without user/session."""
        doc_path = test_db._get_document_path(
            "cells",
            "cel_456",
            is_canonical=False
        )
        
        expected = test_db.runtime_path / "cells" / "cel_456.json"
        assert doc_path == expected
    
    def test_get_document_path_creates_directories(self, test_db):
        """Test that getting document path creates necessary directories."""
        doc_path = test_db._get_document_path(
            "cells",
            "cel_789",
            user_id="user_2",
            session_id="session_2",
            is_canonical=False
        )
        
        # Parent directories should exist
        assert doc_path.parent.exists()
        assert (test_db.runtime_path / "cells" / "user_2").exists()
        assert (test_db.runtime_path / "cells" / "user_2" / "session_2").exists()


class TestCleanupOperations:
    """Test database cleanup and data removal."""
    
    def test_cleanup_test_data_in_test_mode(self):
        """Test cleanup removes temporary directory in test mode."""
        db = JSONDatabase(is_test_env=True)
        base_path = db.base_path
        
        # Create some test data
        (base_path / "test_file.txt").write_text("test")
        
        assert base_path.exists()
        
        # Cleanup
        db.cleanup_test_data()
        
        # Directory should be cleaned (but may be recreated by cleanup method)
        # Check that the temp directory no longer contains our test file
        if base_path.exists():
            assert not (base_path / "test_file.txt").exists()
    
    def test_cleanup_explicit_test_path(self):
        """Test cleanup with explicitly provided test path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir) / "test_db"
            db = JSONDatabase(base_path=test_path, is_test_env=True)
            
            # Create test file
            test_file = test_path / "runtime" / "test.txt"
            test_file.write_text("test content")
            
            assert test_file.exists()
            
            # Cleanup
            db.cleanup_test_data()
            
            # Path should be cleaned and recreated
            assert test_path.exists()
            assert not test_file.exists()
    
    def test_cleanup_non_test_mode_no_action(self):
        """Test cleanup does nothing in non-test mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db = JSONDatabase(base_path=Path(temp_dir), is_test_env=False)
            
            test_file = db.base_path / "important.txt"
            test_file.write_text("important data")
            
            # Should not remove anything
            db.cleanup_test_data()
            
            # File should still exist
            assert test_file.exists()


class TestGetDBInstance:
    """Test global database instance management."""
    
    def test_get_db_instance_runtime_mode(self):
        """Test get_db_instance in runtime mode."""
        # Save original value
        original_test_env = os.environ.get("TEST_ENV")
        
        try:
            # Set to runtime mode
            os.environ.pop("TEST_ENV", None)
            
            # Should return a HybridDatabase instance (current implementation)
            db = get_db_instance()
            assert db is not None
            # HybridDatabase is now the default database router
            from app.database.hybrid import HybridDatabase
            assert isinstance(db, HybridDatabase)
            
        finally:
            # Restore original
            if original_test_env:
                os.environ["TEST_ENV"] = original_test_env
    
    def test_get_db_instance_test_mode_requires_fixture(self):
        """Test get_db_instance in test mode requires proper setup."""
        # Save original value
        original_test_env = os.environ.get("TEST_ENV")
        
        try:
            # Set to test mode
            os.environ["TEST_ENV"] = "true"
            
            # Import to reset the global db variable
            from app.database import connection
            connection.db = None
            
            # Should raise error if db not set
            with pytest.raises(RuntimeError, match="JSONDatabase not initialized"):
                get_db_instance()
            
        finally:
            # Restore
            if original_test_env:
                os.environ["TEST_ENV"] = original_test_env
            else:
                os.environ.pop("TEST_ENV", None)


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_multiple_instances_independent(self):
        """Test that multiple database instances are independent."""
        db1 = JSONDatabase(is_test_env=True)
        db2 = JSONDatabase(is_test_env=True)
        
        assert db1.base_path != db2.base_path
        assert db1.base_path.exists()
        assert db2.base_path.exists()
        
        # Cleanup both
        db1.cleanup_test_data()
        db2.cleanup_test_data()
    
    def test_init_with_nonexistent_path_creates_it(self):
        """Test initialization with non-existent path creates directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_path = Path(temp_dir) / "deeply" / "nested" / "path"
            assert not new_path.exists()
            
            db = JSONDatabase(base_path=new_path, is_test_env=True)
            
            assert new_path.exists()
            assert db.base_path == new_path
    
    def test_collection_path_with_special_characters(self, test_db):
        """Test collection paths handle normal collection names."""
        # Test with underscores (common in collection names)
        path = test_db._get_collection_path("cell_types", is_canonical=True)
        assert "cell_types" in str(path)
        
        path2 = test_db._get_collection_path("ai_models", is_canonical=True)
        assert "ai_models" in str(path2)
    
    def test_insert_permission_error_handling(self, test_db, sample_document_class):
        """Test that PermissionError in insert is properly raised."""
        import os
        from unittest.mock import patch, mock_open
        
        doc = sample_document_class(id="perm_test", name="Test")
        
        # Mock open to raise PermissionError
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            with pytest.raises(PermissionError):
                test_db.insert("test_collection", doc, is_canonical=True)
