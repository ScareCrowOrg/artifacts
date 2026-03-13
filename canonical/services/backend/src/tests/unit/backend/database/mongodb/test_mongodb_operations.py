"""
Unit tests for MongoDB CRUD operations.

Tests insert, find, update, and delete operations using mongomock
to simulate MongoDB without requiring a real database instance.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock

from app.database.mongodb.operations import MongoDBOperations


class TestMongoDBOperationsInit:
    """Test MongoDBOperations initialization."""
    
    def test_init(self):
        """Test MongoDBOperations initialization."""
        ops = MongoDBOperations()
        assert ops._db is None


class TestCollectionNaming:
    """Test collection naming conventions."""
    
    def test_get_collection_name_runtime(self):
        """Runtime collections should have _runtime suffix."""
        ops = MongoDBOperations()
        name = ops._get_collection_name("cells", is_canonical=False)
        assert name == "cells_runtime"
    
    def test_get_collection_name_canonical_ignored(self):
        """Canonical flag should not affect collection naming."""
        ops = MongoDBOperations()
        name = ops._get_collection_name("notebook_item_types", is_canonical=True)
        assert name == "notebook_item_types_runtime"
    
    def test_get_collection_name_consistency(self):
        """Collection naming should be consistent."""
        ops = MongoDBOperations()
        name1 = ops._get_collection_name("test", is_canonical=False)
        name2 = ops._get_collection_name("test", is_canonical=False)
        assert name1 == name2


class TestMongoDBInsert:
    """Test MongoDB insert operations."""
    
    @pytest.mark.asyncio
    async def test_insert_document_success(
        self, mock_mongo_db, mock_mongo_client, test_document_class, sample_test_document
    ):
        """Test successful document insertion."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        doc_id = await ops.insert(
            collection="test_docs",
            document=sample_test_document,
            user_id="user_123",
            session_id="sess_456"
        )
        
        assert doc_id == "doc_123"
        
        # Verify document was inserted with metadata (use sync client for verification)
        sync_db = mock_mongo_client['scareverse_test']
        inserted = sync_db['test_docs_runtime'].find_one({"id": "doc_123"})
        assert inserted is not None
        assert inserted['id'] == "doc_123"
        assert inserted['name'] == "Test Document"
        assert inserted['value'] == 42
        # Note: user_id and session_id are not stored in the document by the current implementation
        assert 'created_at' in inserted
        assert 'updated_at' in inserted
    
    @pytest.mark.asyncio
    async def test_insert_canonical_skipped(
        self, mock_mongo_db, mock_mongo_client, sample_test_document
    ):
        """Canonical documents should not be inserted into MongoDB."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        # Should raise ValueError when attempting to insert canonical data
        with pytest.raises(ValueError, match="Attempted to insert canonical data"):
            await ops.insert(
                collection="notebook_item_types",
                document=sample_test_document,
                is_canonical=True
            )
        
        # Verify no document was inserted (use sync client)
        sync_db = mock_mongo_client['scareverse_test']
        count = sync_db['notebook_item_types_runtime'].count_documents({})
        assert count == 0
    
    @pytest.mark.asyncio
    async def test_insert_without_id_fails(self, mock_mongo_db):
        """Document without 'id' field should fail insertion."""
        from pydantic import BaseModel
        
        class DocWithoutId(BaseModel):
            name: str
        
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        doc = DocWithoutId(name="test")
        
        # Should raise RuntimeError (wrapping ValueError) when document has no 'id' field
        with pytest.raises(RuntimeError, match="Failed to serialize"):
            await ops.insert(
                collection="test_docs",
                document=doc
            )
    
    @pytest.mark.asyncio
    async def test_insert_when_db_unavailable(self, sample_test_document):
        """Insert should raise RuntimeError when database is unavailable."""
        ops = MongoDBOperations()
        # _db is None (not initialized)
        
        with patch.object(ops, '_ensure_db', return_value=None):
            # Should raise RuntimeError when MongoDB is not available
            with pytest.raises(RuntimeError, match="MongoDB database not available"):
                await ops.insert(
                    collection="test_docs",
                    document=sample_test_document
                )


class TestMongoDBFindOne:
    """Test MongoDB find_one operations."""
    
    @pytest.mark.asyncio
    async def test_find_one_success(
        self, mock_mongo_db, test_document_class, populated_collection
    ):
        """Test successful document retrieval by ID."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        doc = await ops.find_one(
            collection="test_collection",
            doc_id="doc_1",
            model_class=test_document_class
        )
        
        assert doc is not None
        assert doc.id == "doc_1"
        assert doc.name == "Document 1"
        assert doc.value == 100
    
    @pytest.mark.asyncio
    async def test_find_one_not_found(
        self, mock_mongo_db, test_document_class
    ):
        """Test finding non-existent document returns None."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        doc = await ops.find_one(
            collection="test_collection",
            doc_id="nonexistent",
            model_class=test_document_class
        )
        
        assert doc is None
    
    @pytest.mark.asyncio
    async def test_find_one_with_user_filter(
        self, mock_mongo_db, test_document_class, populated_collection
    ):
        """Test finding document with user ID filter."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        doc = await ops.find_one(
            collection="test_collection",
            doc_id="doc_1",
            model_class=test_document_class,
            user_id="user_1"
        )
        
        assert doc is not None
        assert doc.id == "doc_1"
    
    @pytest.mark.asyncio
    async def test_find_one_wrong_user(
        self, mock_mongo_db, test_document_class, populated_collection
    ):
        """Test finding document with wrong user ID returns None."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        doc = await ops.find_one(
            collection="test_collection",
            doc_id="doc_1",
            model_class=test_document_class,
            user_id="wrong_user"
        )
        
        assert doc is None
    
    @pytest.mark.asyncio
    async def test_find_one_canonical_returns_none(
        self, mock_mongo_db, test_document_class
    ):
        """Canonical documents should not be found in MongoDB."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        doc = await ops.find_one(
            collection="notebook_item_types",
            doc_id="type_1",
            model_class=test_document_class,
            is_canonical=True
        )
        
        assert doc is None


class TestMongoDBUpdate:
    """Test MongoDB update operations."""
    
    @pytest.mark.asyncio
    async def test_update_document_success(
        self, mock_mongo_db, mock_mongo_client, populated_collection
    ):
        """Test successful document update."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        result = await ops.update(
            collection="test_collection",
            doc_id="doc_1",
            updates={"value": 999, "name": "Updated Document"}
        )
        
        assert result is True
        
        # Verify update (use sync client)
        sync_db = mock_mongo_client['scareverse_test']
        updated = sync_db['test_collection_runtime'].find_one({"id": "doc_1"})
        assert updated['value'] == 999
        assert updated['name'] == "Updated Document"
        assert 'updated_at' in updated
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_document(self, mock_mongo_db):
        """Updating non-existent document should return False."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        result = await ops.update(
            collection="test_collection",
            doc_id="nonexistent",
            updates={"value": 999}
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_update_with_user_filter(
        self, mock_mongo_db, mock_mongo_client, populated_collection
    ):
        """Test updating document with user filter."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        result = await ops.update(
            collection="test_collection",
            doc_id="doc_1",
            updates={"value": 555},
            user_id="user_1"
        )
        
        assert result is True
        
        # Verify update (use sync client)
        sync_db = mock_mongo_client['scareverse_test']
        updated = sync_db['test_collection_runtime'].find_one({"id": "doc_1"})
        assert updated['value'] == 555
    
    @pytest.mark.asyncio
    async def test_update_wrong_user(
        self, mock_mongo_db, populated_collection
    ):
        """Updating document with wrong user should return False."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        result = await ops.update(
            collection="test_collection",
            doc_id="doc_1",
            updates={"value": 555},
            user_id="wrong_user"
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_update_canonical_returns_false(self, mock_mongo_db):
        """Canonical documents cannot be updated in MongoDB."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        # Should raise ValueError when attempting to update canonical data
        with pytest.raises(ValueError, match="Attempted to update canonical data"):
            await ops.update(
                collection="notebook_item_types",
                doc_id="type_1",
                updates={"name": "New Name"},
                is_canonical=True
            )


class TestMongoDBDelete:
    """Test MongoDB delete operations."""
    
    @pytest.mark.asyncio
    async def test_delete_document_success(
        self, mock_mongo_db, mock_mongo_client, populated_collection
    ):
        """Test successful document deletion."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        result = await ops.delete(
            collection="test_collection",
            doc_id="doc_1"
        )
        
        assert result is True
        
        # Verify deletion (use sync client)
        sync_db = mock_mongo_client['scareverse_test']
        deleted = sync_db['test_collection_runtime'].find_one({"id": "doc_1"})
        assert deleted is None
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_document(self, mock_mongo_db):
        """Deleting non-existent document should return False."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        result = await ops.delete(
            collection="test_collection",
            doc_id="nonexistent"
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_with_user_filter(
        self, mock_mongo_db, populated_collection
    ):
        """Test deleting document with user filter."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        result = await ops.delete(
            collection="test_collection",
            doc_id="doc_1",
            user_id="user_1"
        )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_wrong_user(
        self, mock_mongo_db, populated_collection
    ):
        """Deleting document with wrong user should return False."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        result = await ops.delete(
            collection="test_collection",
            doc_id="doc_1",
            user_id="wrong_user"
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_canonical_returns_false(self, mock_mongo_db):
        """Canonical documents cannot be deleted from MongoDB."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        # Should raise ValueError when attempting to delete canonical data
        with pytest.raises(ValueError, match="Attempted to delete canonical data"):
            await ops.delete(
                collection="notebook_item_types",
                doc_id="type_1",
                is_canonical=True
            )
