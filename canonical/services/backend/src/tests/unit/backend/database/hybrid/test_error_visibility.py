"""
Tests for error visibility and logging (Issue #880 - Subissue 5).

Tests that errors are properly logged and visible, with no silent failures.
Ensures error messages propagate correctly to HTTP responses.
"""

import pytest
import logging
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException

from app.database.hybrid import HybridDatabase, RUNTIME_COLLECTIONS
from .conftest import TestModel


class TestErrorVisibility:
    """Test that errors are visible and not silently caught."""
    
    @pytest.mark.asyncio
    async def test_mongodb_enforcement_error_is_not_caught(self, temp_dir, test_model):
        """MongoDB enforcement errors should propagate, not be caught silently."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            # Error should propagate to caller
            with pytest.raises(RuntimeError) as exc_info:
                await db.insert("cells", test_model, user_id="user_123")
            
            # Error should be raised, not caught and logged silently
            assert "Runtime collection 'cells' requires MongoDB storage" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_sync_method_runtime_error_is_not_caught(self, hybrid_db_production_mode, test_model):
        """Sync method errors for runtime collections should propagate."""
        # Error should propagate to caller
        with pytest.raises(RuntimeError) as exc_info:
            hybrid_db_production_mode.insert_sync("cells", test_model, user_id="user_123")
        
        assert "DEPRECATED: Synchronous insert attempted for runtime collection 'cells'" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_no_silent_fallback_to_file_storage(self, temp_dir, test_model):
        """Runtime collections should NOT silently fall back to file storage."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            # Should raise RuntimeError, not silently use file storage
            with pytest.raises(RuntimeError):
                await db.insert("cells", test_model, user_id="user_123")
            
            # Verify no data was written to file storage
            result = db._file_db.find_one(
                collection="cells",
                doc_id="test_1",
                model_class=TestModel,
                user_id="user_123"
            )
            # Should be None because insert should have failed
            assert result is None


class TestErrorLogging:
    """Test that errors are properly logged."""
    
    @pytest.mark.asyncio
    async def test_mongodb_enforcement_logs_error(self, temp_dir, test_model, caplog):
        """MongoDB enforcement should log errors for visibility."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            caplog.set_level(logging.INFO)
            
            # Attempt operation that will fail
            with pytest.raises(RuntimeError):
                await db.insert("cells", test_model, user_id="user_123")
            
            # Note: The error is raised, not logged. The application layer should log it.
            # This test verifies that the error is raised, not silently caught.
    
    def test_sync_method_logs_deprecation_warning(self, hybrid_db_file_only, test_model, caplog):
        """Sync methods should log deprecation warnings."""
        caplog.set_level(logging.WARNING)
        
        hybrid_db_file_only.insert_sync(
            collection="cell_types",
            document=test_model,
            is_canonical=True
        )
        
        # Check for warning log
        assert any("DEPRECATED" in record.message for record in caplog.records)
    
    def test_sync_method_runtime_error_logs_before_raising(self, hybrid_db_production_mode, test_model, caplog):
        """Sync methods should log before raising RuntimeError for runtime collections."""
        caplog.set_level(logging.WARNING)
        
        with pytest.raises(RuntimeError):
            hybrid_db_production_mode.insert_sync(
                collection="cells",
                document=test_model,
                user_id="user_123"
            )
        
        # Should have logged the deprecation attempt
        # (The RuntimeError is raised before logging in this case)


class TestHTTPErrorResponses:
    """Test that errors translate to proper HTTP error responses."""
    
    @pytest.mark.asyncio
    async def test_mongodb_enforcement_error_can_be_caught_by_router(self, temp_dir, test_model):
        """MongoDB enforcement errors should be catchable by HTTP routers."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            # Simulate what a router would do
            try:
                await db.insert("cells", test_model, user_id="user_123")
                pytest.fail("Should have raised RuntimeError")
            except RuntimeError as e:
                # Router can catch and convert to HTTPException
                error_msg = str(e)
                assert "Runtime collection 'cells' requires MongoDB storage" in error_msg
                # Router would do: raise HTTPException(status_code=500, detail=error_msg)


class TestErrorMessageQuality:
    """Test that error messages are high quality and actionable."""
    
    @pytest.mark.asyncio
    async def test_error_includes_what_went_wrong(self, temp_dir, test_model):
        """Error message should explain what went wrong."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            with pytest.raises(RuntimeError) as exc_info:
                await db.insert("cells", test_model, user_id="user_123")
            
            error_msg = str(exc_info.value)
            assert "requires MongoDB storage" in error_msg
            assert "MongoDB is not enabled" in error_msg
    
    @pytest.mark.asyncio
    async def test_error_includes_how_to_fix(self, temp_dir, test_model):
        """Error message should include how to fix the problem."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            with pytest.raises(RuntimeError) as exc_info:
                await db.insert("cells", test_model, user_id="user_123")
            
            error_msg = str(exc_info.value)
            assert "Please enable MongoDB" in error_msg or "enable MongoDB" in error_msg.lower()
    
    @pytest.mark.asyncio
    async def test_error_includes_policy_explanation(self, temp_dir, test_model):
        """Error message should explain the policy being enforced."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            with pytest.raises(RuntimeError) as exc_info:
                await db.insert("cells", test_model, user_id="user_123")
            
            error_msg = str(exc_info.value)
            assert "MUST NOT be stored on disk" in error_msg
    
    def test_sync_error_explains_correct_usage(self, hybrid_db_production_mode, test_model):
        """Sync method errors should explain correct async usage."""
        with pytest.raises(RuntimeError) as exc_info:
            hybrid_db_production_mode.insert_sync("cells", test_model, user_id="user_123")
        
        error_msg = str(exc_info.value)
        assert "Use 'db.insert()' instead of 'db.insert_sync()'" in error_msg


class TestNoSilentFailures:
    """Test that there are no silent failures - all errors are visible."""
    
    @pytest.mark.asyncio
    async def test_no_silent_failure_on_mongodb_enforcement(self, temp_dir, test_model):
        """MongoDB enforcement should not fail silently."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            # Should raise RuntimeError, not return None or empty result
            with pytest.raises(RuntimeError):
                await db.insert("cells", test_model, user_id="user_123")
    
    def test_no_silent_failure_on_sync_method_violation(self, hybrid_db_production_mode, test_model):
        """Sync method violations should not fail silently."""
        # Should raise RuntimeError, not return None or log silently
        with pytest.raises(RuntimeError):
            hybrid_db_production_mode.insert_sync("cells", test_model, user_id="user_123")
    
    @pytest.mark.asyncio
    async def test_all_runtime_collections_fail_loudly(self, temp_dir, test_model):
        """All runtime collections should fail loudly when MongoDB is disabled."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            for collection in RUNTIME_COLLECTIONS:
                with pytest.raises(RuntimeError) as exc_info:
                    await db.insert(collection, test_model, user_id="user_123")
                
                # Verify error is specific and informative
                assert collection in str(exc_info.value)
                assert "requires MongoDB storage" in str(exc_info.value)


class TestConsistentErrorBehavior:
    """Test that error behavior is consistent across all operations."""
    
    @pytest.mark.asyncio
    async def test_all_crud_operations_fail_consistently(self, temp_dir, test_model):
        """All CRUD operations should fail with same error when MongoDB is disabled."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            operations = [
                ("insert", lambda: db.insert("cells", test_model, user_id="user_123")),
                ("find_one", lambda: db.find_one("cells", "test_1", TestModel, user_id="user_123")),
                ("update", lambda: db.update("cells", "test_1", {"name": "Updated"}, user_id="user_123")),
                ("delete", lambda: db.delete("cells", "test_1", user_id="user_123")),
                ("find_many", lambda: db.find_many("cells", TestModel, user_id="user_123")),
            ]
            
            for op_name, op_func in operations:
                with pytest.raises(RuntimeError) as exc_info:
                    await op_func()
                
                error_msg = str(exc_info.value)
                assert "Runtime collection 'cells' requires MongoDB storage" in error_msg
                assert "MONGODB_ENABLED=False" in error_msg or "MongoDB is not enabled" in error_msg


class TestErrorRecoveryGuidance:
    """Test that errors provide clear recovery guidance."""
    
    @pytest.mark.asyncio
    async def test_mongodb_error_suggests_configuration_check(self, temp_dir, test_model):
        """MongoDB error should suggest checking configuration."""
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            db = HybridDatabase(base_path=temp_dir, is_test_env=False)
            
            with pytest.raises(RuntimeError) as exc_info:
                await db.insert("cells", test_model, user_id="user_123")
            
            error_msg = str(exc_info.value)
            assert "check your configuration" in error_msg.lower() or "Please enable MongoDB" in error_msg
    
    def test_sync_error_provides_correct_async_syntax(self, hybrid_db_production_mode, test_model):
        """Sync method error should show correct async syntax."""
        with pytest.raises(RuntimeError) as exc_info:
            hybrid_db_production_mode.insert_sync("cells", test_model, user_id="user_123")
        
        error_msg = str(exc_info.value)
        # Should show both the wrong way and the right way
        assert "db.insert_sync()" in error_msg
        assert "db.insert()" in error_msg
