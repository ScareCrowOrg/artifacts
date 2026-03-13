"""
Tests for Legacy Adapter in HybridDatabase.

Tests the automatic conversion of legacy collection names ("cells", "books")
to the unified "notebook_items" collection with appropriate "kind" discriminator.
"""

import pytest
from unittest.mock import AsyncMock

from app.database.hybrid import HybridDatabase
from .conftest import TestModel, NotebookItemModel


class TestLegacyAdapterConversion:
    """Test legacy adapter collection name conversions."""

    def test_cells_collection_converts_to_notebook_items(self, hybrid_db_with_mongodb):
        """Legacy 'cells' collection should convert to 'notebook_items'."""
        collection, document, query = hybrid_db_with_mongodb._apply_legacy_adapter(
            collection="cells",
            document=None,
            query=None,
        )
        
        assert collection == "notebook_items"
        assert document is None
        assert query is None

    def test_books_collection_converts_to_notebook_items(self, hybrid_db_with_mongodb):
        """Legacy 'books' collection should convert to 'notebook_items'."""
        collection, document, query = hybrid_db_with_mongodb._apply_legacy_adapter(
            collection="books",
            document=None,
            query=None,
        )
        
        assert collection == "notebook_items"
        assert document is None
        assert query is None

    def test_other_collections_not_converted(self, hybrid_db_with_mongodb):
        """Non-legacy collections should not be converted."""
        collection, document, query = hybrid_db_with_mongodb._apply_legacy_adapter(
            collection="sessions",
            document=None,
            query=None,
        )
        
        assert collection == "sessions"
        assert document is None
        assert query is None


class TestLegacyAdapterDocumentTransformation:
    """Test legacy adapter document transformations with kind field."""

    @pytest.mark.asyncio
    async def test_cells_insert_adds_kind_field(self, hybrid_db_with_mongodb, notebook_item_model):
        """Inserting to 'cells' should add kind='cell' to document."""
        # Insert into legacy "cells" collection
        await hybrid_db_with_mongodb.insert(
            collection="cells",
            document=notebook_item_model,
            user_id="user_123",
        )
        
        # Verify MongoDB was called with notebook_items collection
        hybrid_db_with_mongodb._mongo_ops.insert.assert_called_once()
        call_args = hybrid_db_with_mongodb._mongo_ops.insert.call_args
        
        assert call_args.kwargs["collection"] == "notebook_items"
        # Check that document has kind field
        inserted_doc = call_args.kwargs["document"]
        assert hasattr(inserted_doc, "kind") and inserted_doc.kind == "cell"

    @pytest.mark.asyncio
    async def test_books_insert_adds_kind_field(self, hybrid_db_with_mongodb, notebook_item_model):
        """Inserting to 'books' should add kind='book' to document."""
        # Insert into legacy "books" collection
        await hybrid_db_with_mongodb.insert(
            collection="books",
            document=notebook_item_model,
            user_id="user_123",
        )
        
        # Verify MongoDB was called with notebook_items collection
        hybrid_db_with_mongodb._mongo_ops.insert.assert_called_once()
        call_args = hybrid_db_with_mongodb._mongo_ops.insert.call_args
        
        assert call_args.kwargs["collection"] == "notebook_items"
        # Check that document has kind field
        inserted_doc = call_args.kwargs["document"]
        assert hasattr(inserted_doc, "kind") and inserted_doc.kind == "book"


class TestLegacyAdapterQueryTransformation:
    """Test legacy adapter query transformations with kind filter."""

    @pytest.mark.asyncio
    async def test_cells_find_adds_kind_filter(self, hybrid_db_with_mongodb):
        """Finding in 'cells' should add kind='cell' filter."""
        # Mock find to return empty list
        hybrid_db_with_mongodb._mongo_ops.find = AsyncMock(return_value=[])
        
        # Find in legacy "cells" collection
        await hybrid_db_with_mongodb.find(
            collection="cells",
            query={"status": "active"},
            user_id="user_123",
        )
        
        # Verify MongoDB was called with kind filter
        hybrid_db_with_mongodb._mongo_ops.find.assert_called_once()
        call_args = hybrid_db_with_mongodb._mongo_ops.find.call_args
        
        assert call_args.kwargs["collection"] == "notebook_items"
        assert call_args.kwargs["query"]["kind"] == "cell"
        assert call_args.kwargs["query"]["status"] == "active"

    @pytest.mark.asyncio
    async def test_books_find_adds_kind_filter(self, hybrid_db_with_mongodb):
        """Finding in 'books' should add kind='book' filter."""
        # Mock find to return empty list
        hybrid_db_with_mongodb._mongo_ops.find = AsyncMock(return_value=[])
        
        # Find in legacy "books" collection
        await hybrid_db_with_mongodb.find(
            collection="books",
            query={"status": "active"},
            user_id="user_123",
        )
        
        # Verify MongoDB was called with kind filter
        hybrid_db_with_mongodb._mongo_ops.find.assert_called_once()
        call_args = hybrid_db_with_mongodb._mongo_ops.find.call_args
        
        assert call_args.kwargs["collection"] == "notebook_items"
        assert call_args.kwargs["query"]["kind"] == "book"
        assert call_args.kwargs["query"]["status"] == "active"

    @pytest.mark.asyncio
    async def test_find_by_fields_adds_kind_filter(self, hybrid_db_with_mongodb):
        """find_by_fields on 'cells' should add kind filter."""
        # Mock find_by_fields to return None
        hybrid_db_with_mongodb._mongo_ops.find_by_fields = AsyncMock(return_value=None)
        
        # Find in legacy "cells" collection
        await hybrid_db_with_mongodb.find_by_fields(
            collection="cells",
            fields={"status": "active", "assignee_id": "user_123"},
            user_id="user_123",
        )
        
        # Verify MongoDB was called with kind filter
        hybrid_db_with_mongodb._mongo_ops.find_by_fields.assert_called_once()
        call_args = hybrid_db_with_mongodb._mongo_ops.find_by_fields.call_args
        
        assert call_args.kwargs["collection"] == "notebook_items"
        assert call_args.kwargs["fields"]["kind"] == "cell"
        assert call_args.kwargs["fields"]["status"] == "active"

    @pytest.mark.asyncio
    async def test_find_by_field_adds_kind_filter(self, hybrid_db_with_mongodb):
        """find_by_field on 'cells' should add kind filter by using find_by_fields."""
        # Mock find_by_fields to return None
        hybrid_db_with_mongodb._mongo_ops.find_by_fields = AsyncMock(return_value=None)
        
        # Find by single field in legacy "cells" collection
        await hybrid_db_with_mongodb.find_by_field(
            collection="cells",
            field="status",
            value="active",
            user_id="user_123",
        )
        
        # Verify MongoDB find_by_fields was called with kind filter
        hybrid_db_with_mongodb._mongo_ops.find_by_fields.assert_called_once()
        call_args = hybrid_db_with_mongodb._mongo_ops.find_by_fields.call_args
        
        assert call_args.kwargs["collection"] == "notebook_items"
        assert call_args.kwargs["fields"]["kind"] == "cell"
        assert call_args.kwargs["fields"]["status"] == "active"


class TestLegacyAdapterCRUDOperations:
    """Test legacy adapter integration with all CRUD operations."""

    @pytest.mark.asyncio
    async def test_find_one_with_legacy_collection(self, hybrid_db_with_mongodb, test_model):
        """find_one should work with legacy collection names."""
        # Mock find_one to return test model
        hybrid_db_with_mongodb._mongo_ops.find_one = AsyncMock(return_value=test_model)
        
        result = await hybrid_db_with_mongodb.find_one(
            collection="cells",
            doc_id="test_1",
            user_id="user_123",
        )
        
        # Verify correct collection was used
        hybrid_db_with_mongodb._mongo_ops.find_one.assert_called_once()
        call_args = hybrid_db_with_mongodb._mongo_ops.find_one.call_args
        assert call_args.kwargs["collection"] == "notebook_items"

    @pytest.mark.asyncio
    async def test_find_many_with_legacy_collection(self, hybrid_db_with_mongodb):
        """find_many should work with legacy collection names."""
        # Mock find_many to return empty list
        hybrid_db_with_mongodb._mongo_ops.find_many = AsyncMock(return_value=[])
        
        result = await hybrid_db_with_mongodb.find_many(
            collection="books",
            user_id="user_123",
        )
        
        # Verify correct collection was used
        hybrid_db_with_mongodb._mongo_ops.find_many.assert_called_once()
        call_args = hybrid_db_with_mongodb._mongo_ops.find_many.call_args
        assert call_args.kwargs["collection"] == "notebook_items"

    @pytest.mark.asyncio
    async def test_update_with_legacy_collection(self, hybrid_db_with_mongodb):
        """update should work with legacy collection names."""
        # Mock update to return True
        hybrid_db_with_mongodb._mongo_ops.update = AsyncMock(return_value=True)
        
        result = await hybrid_db_with_mongodb.update(
            collection="cells",
            doc_id="test_1",
            updates={"status": "completed"},
            user_id="user_123",
        )
        
        # Verify correct collection was used
        hybrid_db_with_mongodb._mongo_ops.update.assert_called_once()
        call_args = hybrid_db_with_mongodb._mongo_ops.update.call_args
        assert call_args.kwargs["collection"] == "notebook_items"

    @pytest.mark.asyncio
    async def test_delete_with_legacy_collection(self, hybrid_db_with_mongodb):
        """delete should work with legacy collection names."""
        # Mock delete to return True
        hybrid_db_with_mongodb._mongo_ops.delete = AsyncMock(return_value=True)
        
        result = await hybrid_db_with_mongodb.delete(
            collection="books",
            doc_id="test_1",
            user_id="user_123",
        )
        
        # Verify correct collection was used
        hybrid_db_with_mongodb._mongo_ops.delete.assert_called_once()
        call_args = hybrid_db_with_mongodb._mongo_ops.delete.call_args
        assert call_args.kwargs["collection"] == "notebook_items"


class TestLegacyAdapterIsolation:
    """Test that kind filter prevents data leakage between cells and books."""

    @pytest.mark.asyncio
    async def test_cells_query_filters_out_books(self, hybrid_db_with_mongodb, notebook_item_model):
        """Querying 'cells' should only return documents with kind='cell'."""
        # Mock find to return a cell item
        notebook_item_model.kind = "cell"
        
        hybrid_db_with_mongodb._mongo_ops.find = AsyncMock(return_value=[notebook_item_model])
        
        # Find in cells collection
        results = await hybrid_db_with_mongodb.find(
            collection="cells",
            query={},
            user_id="user_123",
        )
        
        # Verify query included kind filter
        call_args = hybrid_db_with_mongodb._mongo_ops.find.call_args
        assert call_args.kwargs["query"]["kind"] == "cell"

    @pytest.mark.asyncio
    async def test_books_query_filters_out_cells(self, hybrid_db_with_mongodb, notebook_item_model):
        """Querying 'books' should only return documents with kind='book'."""
        # Mock find to return a book item
        notebook_item_model.kind = "book"
        
        hybrid_db_with_mongodb._mongo_ops.find = AsyncMock(return_value=[notebook_item_model])
        
        # Find in books collection
        results = await hybrid_db_with_mongodb.find(
            collection="books",
            query={},
            user_id="user_123",
        )
        
        # Verify query included kind filter
        call_args = hybrid_db_with_mongodb._mongo_ops.find.call_args
        assert call_args.kwargs["query"]["kind"] == "book"


class TestLegacyAdapterBackwardCompatibility:
    """Test backward compatibility - no changes needed to existing code."""

    @pytest.mark.asyncio
    async def test_existing_cells_code_works_unchanged(self, hybrid_db_with_mongodb, test_model):
        """Existing code using 'cells' collection should work without changes."""
        # Simulate existing code pattern
        cell_id = await hybrid_db_with_mongodb.insert(
            collection="cells",  # Legacy collection name
            document=test_model,
            user_id="user_123",
        )
        
        # Should successfully insert without errors
        assert cell_id == "test_1"
        hybrid_db_with_mongodb._mongo_ops.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_existing_books_code_works_unchanged(self, hybrid_db_with_mongodb, test_model):
        """Existing code using 'books' collection should work without changes."""
        # Simulate existing code pattern
        book_id = await hybrid_db_with_mongodb.insert(
            collection="books",  # Legacy collection name
            document=test_model,
            user_id="user_123",
        )
        
        # Should successfully insert without errors
        assert book_id == "test_1"
        hybrid_db_with_mongodb._mongo_ops.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_code_using_notebook_items_works(self, hybrid_db_with_mongodb, notebook_item_model):
        """New code can directly use 'notebook_items' collection."""
        # New code pattern - set kind explicitly
        notebook_item_model.kind = "cell"
        item_id = await hybrid_db_with_mongodb.insert(
            collection="notebook_items",  # Direct use of unified collection
            document=notebook_item_model,
            user_id="user_123",
        )
        
        # Should work without adapter interference
        assert item_id == "test_1"
        hybrid_db_with_mongodb._mongo_ops.insert.assert_called_once()
        call_args = hybrid_db_with_mongodb._mongo_ops.insert.call_args
        assert call_args.kwargs["collection"] == "notebook_items"
