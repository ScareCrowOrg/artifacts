"""
Unit tests for MongoDB operations error handling.

Tests error scenarios and edge cases to ensure proper error handling
and logging in MongoDB operations.
"""

import pytest
from unittest.mock import patch, AsyncMock
from app.database.mongodb.operations import MongoDBOperations


class TestMongoDBErrorHandling:
    """Test error handling in MongoDB operations."""
    
    @pytest.mark.asyncio
    async def test_insert_error_handling(self, mock_mongo_db, sample_test_document):
        """Test insert operation error handling."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        # Mock insert_one to raise an exception
        with patch.object(
            mock_mongo_db._db['test_docs_runtime'],
            'insert_one',
            side_effect=Exception("Database error")
        ):
            # MongoDB operations now raise RuntimeError on failure
            with pytest.raises(RuntimeError, match="MongoDB insert failed"):
                await ops.insert(
                    collection="test_docs",
                    document=sample_test_document
                )
    
    @pytest.mark.asyncio
    async def test_find_one_error_handling(self, mock_mongo_db, test_document_class):
        """Test find_one operation error handling."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        # Mock find_one to raise an exception
        with patch.object(
            mock_mongo_db._db['test_docs_runtime'],
            'find_one',
            side_effect=Exception("Database error")
        ):
            # MongoDB operations now raise RuntimeError on failure
            with pytest.raises(RuntimeError, match="MongoDB query failed"):
                await ops.find_one(
                    collection="test_docs",
                    doc_id="doc_123",
                    model_class=test_document_class
                )
    
    @pytest.mark.asyncio
    async def test_update_error_handling(self, mock_mongo_db):
        """Test update operation error handling."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        # Mock update_one to raise an exception
        with patch.object(
            mock_mongo_db._db['test_docs_runtime'],
            'update_one',
            side_effect=Exception("Database error")
        ):
            # MongoDB operations now raise RuntimeError on failure
            with pytest.raises(RuntimeError, match="MongoDB update failed"):
                await ops.update(
                    collection="test_docs",
                    doc_id="doc_123",
                    updates={"value": 999}
                )
    
    @pytest.mark.asyncio
    async def test_delete_error_handling(self, mock_mongo_db):
        """Test delete operation error handling."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        # Mock delete_one to raise an exception
        with patch.object(
            mock_mongo_db._db['test_docs_runtime'],
            'delete_one',
            side_effect=Exception("Database error")
        ):
            # MongoDB operations now raise RuntimeError on failure
            with pytest.raises(RuntimeError, match="MongoDB delete failed"):
                await ops.delete(
                    collection="test_docs",
                    doc_id="doc_123"
                )
    
    @pytest.mark.asyncio
    async def test_find_many_error_handling(self, mock_mongo_db, test_document_class):
        """Test find_many operation error handling."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        # Mock find to raise an exception
        with patch.object(
            mock_mongo_db._db['test_docs_runtime'],
            'find',
            side_effect=Exception("Database error")
        ):
            docs = await ops.find_many(
                collection="test_docs",
                model_class=test_document_class
            )
            
            assert docs == []
    
    @pytest.mark.asyncio
    async def test_find_by_field_error_handling(self, mock_mongo_db, test_document_class):
        """Test find_by_field operation error handling."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        # Mock find_one to raise an exception
        with patch.object(
            mock_mongo_db._db['test_docs_runtime'],
            'find_one',
            side_effect=Exception("Database error")
        ):
            # MongoDB operations now raise RuntimeError on query failure
            with pytest.raises(RuntimeError, match="MongoDB query failed"):
                await ops.find_by_field(
                    collection="test_docs",
                    field="name",
                    value="test",
                    model_class=test_document_class
                )
    
    @pytest.mark.asyncio
    async def test_find_by_fields_error_handling(self, mock_mongo_db, test_document_class):
        """Test find_by_fields operation error handling."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        # Mock find_one to raise an exception
        with patch.object(
            mock_mongo_db._db['test_docs_runtime'],
            'find_one',
            side_effect=Exception("Database error")
        ):
            # MongoDB operations now raise RuntimeError on query failure
            with pytest.raises(RuntimeError, match="MongoDB query failed"):
                await ops.find_by_fields(
                    collection="test_docs",
                    fields={"name": "test"},
                    model_class=test_document_class
                )


class TestMongoDBEnsureDatabase:
    """Test _ensure_db method."""
    
    @pytest.mark.asyncio
    async def test_ensure_db_caches_database(self):
        """Test that _ensure_db caches the database instance."""
        ops = MongoDBOperations()
        assert ops._db is None
        
        # Mock get_mongodb_database
        mock_db = AsyncMock()
        with patch('app.database.mongodb.operations.get_mongodb_database', return_value=mock_db):
            db1 = await ops._ensure_db()
            db2 = await ops._ensure_db()
            
            assert db1 is mock_db
            assert db2 is mock_db
            assert db1 is db2


class TestMongoDBErrorMessages:
    """Test that error messages contain correct collection names with _runtime suffix."""
    
    @pytest.mark.asyncio
    async def test_insert_error_message_contains_runtime_suffix(self, mock_mongo_db, sample_test_document):
        """Test that insert error messages show the actual collection name with _runtime suffix."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        # Mock insert_one to raise an authentication error (like in the issue)
        with patch.object(
            mock_mongo_db._db['test_docs_runtime'],
            'insert_one',
            side_effect=Exception("Command insert requires authentication")
        ):
            with pytest.raises(RuntimeError) as exc_info:
                await ops.insert(
                    collection="test_docs",
                    document=sample_test_document
                )
            
            # Verify error message contains the actual collection name with _runtime suffix
            error_message = str(exc_info.value)
            assert error_message.startswith("MongoDB insert failed for collection 'test_docs_runtime'"), \
                f"Error message should start with correct collection name but got: {error_message}"
    
    @pytest.mark.asyncio
    async def test_find_one_error_message_contains_runtime_suffix(self, mock_mongo_db, test_document_class):
        """Test that find_one error messages show the actual collection name with _runtime suffix."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        # Mock find_one to raise an authentication error (like in the issue)
        with patch.object(
            mock_mongo_db._db['test_docs_runtime'],
            'find_one',
            side_effect=Exception("Command find requires authentication")
        ):
            with pytest.raises(RuntimeError) as exc_info:
                await ops.find_one(
                    collection="test_docs",
                    doc_id="doc_123",
                    model_class=test_document_class
                )
            
            # Verify error message contains the actual collection name with _runtime suffix
            error_message = str(exc_info.value)
            assert error_message.startswith("MongoDB query failed for collection 'test_docs_runtime'"), \
                f"Error message should start with correct collection name but got: {error_message}"
    
    @pytest.mark.asyncio
    async def test_update_error_message_contains_runtime_suffix(self, mock_mongo_db):
        """Test that update error messages show the actual collection name with _runtime suffix."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        # Mock update_one to raise an authentication error
        with patch.object(
            mock_mongo_db._db['test_docs_runtime'],
            'update_one',
            side_effect=Exception("Command update requires authentication")
        ):
            with pytest.raises(RuntimeError) as exc_info:
                await ops.update(
                    collection="test_docs",
                    doc_id="doc_123",
                    updates={"value": 999}
                )
            
            # Verify error message contains the actual collection name with _runtime suffix
            error_message = str(exc_info.value)
            assert error_message.startswith("MongoDB update failed for collection 'test_docs_runtime'"), \
                f"Error message should start with correct collection name but got: {error_message}"
    
    @pytest.mark.asyncio
    async def test_delete_error_message_contains_runtime_suffix(self, mock_mongo_db):
        """Test that delete error messages show the actual collection name with _runtime suffix."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        # Mock delete_one to raise an authentication error
        with patch.object(
            mock_mongo_db._db['test_docs_runtime'],
            'delete_one',
            side_effect=Exception("Command delete requires authentication")
        ):
            with pytest.raises(RuntimeError) as exc_info:
                await ops.delete(
                    collection="test_docs",
                    doc_id="doc_123"
                )
            
            # Verify error message contains the actual collection name with _runtime suffix
            error_message = str(exc_info.value)
            assert error_message.startswith("MongoDB delete failed for collection 'test_docs_runtime'"), \
                f"Error message should start with correct collection name but got: {error_message}"
