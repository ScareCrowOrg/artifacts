"""
Unit tests for MongoDB find operations.

Tests find_many, find_by_field, and find_by_fields operations
using mongomock to simulate MongoDB queries.
"""

import pytest
from app.database.mongodb.operations import MongoDBOperations


class TestMongoDBFindMany:
    """Test find_many operation for querying multiple documents."""
    
    @pytest.mark.asyncio
    async def test_find_many_all_documents(
        self, mock_mongo_db, test_document_class, populated_collection
    ):
        """Test finding all documents in a collection."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        docs = await ops.find_many(
            collection="test_collection",
            model_class=test_document_class
        )
        
        assert len(docs) == 3
        assert all(isinstance(doc, test_document_class) for doc in docs)
        doc_ids = [doc.id for doc in docs]
        assert "doc_1" in doc_ids
        assert "doc_2" in doc_ids
        assert "doc_3" in doc_ids
    
    @pytest.mark.asyncio
    async def test_find_many_with_user_filter(
        self, mock_mongo_db, test_document_class, populated_collection
    ):
        """Test finding documents filtered by user ID."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        docs = await ops.find_many(
            collection="test_collection",
            model_class=test_document_class,
            user_id="user_1"
        )
        
        assert len(docs) == 2
        assert all(doc.id in ["doc_1", "doc_2"] for doc in docs)
    
    @pytest.mark.asyncio
    async def test_find_many_with_limit(
        self, mock_mongo_db, test_document_class, populated_collection
    ):
        """Test finding documents with result limit."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        docs = await ops.find_many(
            collection="test_collection",
            model_class=test_document_class,
            limit=2
        )
        
        assert len(docs) == 2
    
    @pytest.mark.asyncio
    async def test_find_many_empty_collection(
        self, mock_mongo_db, test_document_class
    ):
        """Test finding documents in empty collection returns empty list."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        docs = await ops.find_many(
            collection="empty_collection",
            model_class=test_document_class
        )
        
        assert docs == []
    
    @pytest.mark.asyncio
    async def test_find_many_canonical_returns_empty(
        self, mock_mongo_db, test_document_class
    ):
        """Canonical collections should return empty list from MongoDB."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        docs = await ops.find_many(
            collection="notebook_item_types",
            model_class=test_document_class,
            is_canonical=True
        )
        
        assert docs == []
    
    @pytest.mark.asyncio
    async def test_find_many_handles_deserialization_errors(
        self, mock_mongo_db, mock_mongo_client, test_document_class
    ):
        """find_many should skip documents that fail deserialization."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        # Insert documents with invalid data (use sync client)
        sync_db = mock_mongo_client['scareverse_test']
        collection = sync_db['test_docs_runtime']
        collection.insert_many([
            {"id": "doc_1", "name": "Valid", "value": 100},
            {"id": "doc_2", "name": "Invalid"},  # Missing required 'value'
            {"id": "doc_3", "name": "Also Valid", "value": 300}
        ])
        
        docs = await ops.find_many(
            collection="test_docs",
            model_class=test_document_class
        )
        
        # Should return only valid documents
        assert len(docs) == 2
        assert all(doc.id in ["doc_1", "doc_3"] for doc in docs)


class TestMongoDBFindByField:
    """Test find_by_field operation for finding document by specific field."""
    
    @pytest.mark.asyncio
    async def test_find_by_field_success(
        self, mock_mongo_db, test_document_class, populated_collection
    ):
        """Test finding document by field value."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        doc = await ops.find_by_field(
            collection="test_collection",
            field="value",
            value=200,
            model_class=test_document_class
        )
        
        assert doc is not None
        assert doc.id == "doc_2"
        assert doc.value == 200
    
    @pytest.mark.asyncio
    async def test_find_by_field_not_found(
        self, mock_mongo_db, test_document_class
    ):
        """Test finding document with non-matching field value."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        doc = await ops.find_by_field(
            collection="test_collection",
            field="value",
            value=999,
            model_class=test_document_class
        )
        
        assert doc is None
    
    @pytest.mark.asyncio
    async def test_find_by_field_string_value(
        self, mock_mongo_db, test_document_class, populated_collection
    ):
        """Test finding document by string field value."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        doc = await ops.find_by_field(
            collection="test_collection",
            field="name",
            value="Document 3",
            model_class=test_document_class
        )
        
        assert doc is not None
        assert doc.id == "doc_3"
        assert doc.name == "Document 3"
    
    @pytest.mark.asyncio
    async def test_find_by_field_returns_first_match(
        self, mock_mongo_db, mock_mongo_client, test_document_class
    ):
        """find_by_field should return first matching document."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        # Insert multiple documents with same field value (use sync client)
        sync_db = mock_mongo_client['scareverse_test']
        collection = sync_db['test_docs_runtime']
        collection.insert_many([
            {"id": "doc_1", "name": "Same Name", "value": 100},
            {"id": "doc_2", "name": "Same Name", "value": 200}
        ])
        
        doc = await ops.find_by_field(
            collection="test_docs",
            field="name",
            value="Same Name",
            model_class=test_document_class
        )
        
        assert doc is not None
        # Should return one of the matching documents
        assert doc.name == "Same Name"
    
    @pytest.mark.asyncio
    async def test_find_by_field_canonical_returns_none(
        self, mock_mongo_db, test_document_class
    ):
        """Canonical collections should return None from MongoDB."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        doc = await ops.find_by_field(
            collection="notebook_item_types",
            field="name",
            value="Type 1",
            model_class=test_document_class,
            is_canonical=True
        )
        
        assert doc is None


class TestMongoDBFindByFields:
    """Test find_by_fields operation for finding document by multiple fields."""
    
    @pytest.mark.asyncio
    async def test_find_by_fields_success(
        self, mock_mongo_db, test_document_class, populated_collection
    ):
        """Test finding document by multiple field values."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        doc = await ops.find_by_fields(
            collection="test_collection",
            fields={"name": "Document 2", "value": 200},
            model_class=test_document_class
        )
        
        assert doc is not None
        assert doc.id == "doc_2"
        assert doc.name == "Document 2"
        assert doc.value == 200
    
    @pytest.mark.asyncio
    async def test_find_by_fields_not_found(
        self, mock_mongo_db, test_document_class, populated_collection
    ):
        """Test finding document with non-matching field values."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        doc = await ops.find_by_fields(
            collection="test_collection",
            fields={"name": "Document 2", "value": 999},  # Value doesn't match
            model_class=test_document_class
        )
        
        assert doc is None
    
    @pytest.mark.asyncio
    async def test_find_by_fields_single_field(
        self, mock_mongo_db, test_document_class, populated_collection
    ):
        """Test finding document with single field in dict."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        doc = await ops.find_by_fields(
            collection="test_collection",
            fields={"id": "doc_3"},
            model_class=test_document_class
        )
        
        assert doc is not None
        assert doc.id == "doc_3"
    
    @pytest.mark.asyncio
    async def test_find_by_fields_with_metadata(
        self, mock_mongo_db, test_document_class, populated_collection
    ):
        """Test finding document by metadata fields."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        doc = await ops.find_by_fields(
            collection="test_collection",
            fields={"user_id": "user_1", "session_id": "session_1"},
            model_class=test_document_class
        )
        
        assert doc is not None
        # Should return one of the documents with matching metadata
        assert doc.id in ["doc_1", "doc_2"]
    
    @pytest.mark.asyncio
    async def test_find_by_fields_empty_dict(
        self, mock_mongo_db, test_document_class, populated_collection
    ):
        """Test finding document with empty fields dict returns first document."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        doc = await ops.find_by_fields(
            collection="test_collection",
            fields={},
            model_class=test_document_class
        )
        
        # Empty query should match all documents, return first one
        assert doc is not None
    
    @pytest.mark.asyncio
    async def test_find_by_fields_canonical_returns_none(
        self, mock_mongo_db, test_document_class
    ):
        """Canonical collections should return None from MongoDB."""
        ops = MongoDBOperations()
        ops._db = mock_mongo_db
        
        doc = await ops.find_by_fields(
            collection="notebook_item_types",
            fields={"name": "Type 1"},
            model_class=test_document_class,
            is_canonical=True
        )
        
        assert doc is None


class TestMongoDBFindOperationsEdgeCases:
    """Test edge cases and error handling for find operations."""
    
    @pytest.mark.asyncio
    async def test_find_operations_when_db_unavailable(
        self, test_document_class
    ):
        """All find operations should handle unavailable database gracefully."""
        ops = MongoDBOperations()
        # _db is None
        
        from unittest.mock import patch
        with patch.object(ops, '_ensure_db', return_value=None):
            # find_one should raise RuntimeError when DB unavailable
            with pytest.raises(RuntimeError, match="MongoDB database not available"):
                await ops.find_one(
                    collection="test",
                    doc_id="123",
                    model_class=test_document_class
                )
            
            # find_many should raise RuntimeError when DB unavailable
            with pytest.raises(RuntimeError, match="MongoDB database not available"):
                await ops.find_many(
                    collection="test",
                    model_class=test_document_class
                )
            
            # find_by_field
            doc = await ops.find_by_field(
                collection="test",
                field="name",
                value="test",
                model_class=test_document_class
            )
            assert doc is None
            
            # find_by_fields
            doc = await ops.find_by_fields(
                collection="test",
                fields={"name": "test"},
                model_class=test_document_class
            )
            assert doc is None
