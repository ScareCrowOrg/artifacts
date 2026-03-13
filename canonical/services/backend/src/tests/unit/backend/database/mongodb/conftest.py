"""
Shared fixtures for MongoDB tests using mongomock.

Provides mocked MongoDB instances, test models, and utilities for testing
the MongoDB operations module without requiring a real MongoDB instance.
"""

import pytest
import mongomock
from typing import Generator
from pydantic import BaseModel, Field
from unittest.mock import AsyncMock, MagicMock


class AsyncMongomockCollection:
    """Wrapper to make mongomock collection async-compatible."""
    
    def __init__(self, sync_collection):
        self._collection = sync_collection
    
    async def insert_one(self, document):
        """Async wrapper for insert_one."""
        result = self._collection.insert_one(document)
        return result
    
    async def find_one(self, query):
        """Async wrapper for find_one."""
        return self._collection.find_one(query)
    
    async def update_one(self, query, update):
        """Async wrapper for update_one."""
        return self._collection.update_one(query, update)
    
    async def delete_one(self, query):
        """Async wrapper for delete_one."""
        return self._collection.delete_one(query)
    
    def find(self, query):
        """Return async cursor wrapper."""
        cursor = self._collection.find(query)
        return AsyncMongomockCursor(cursor)
    
    async def count_documents(self, query):
        """Async wrapper for count_documents."""
        return self._collection.count_documents(query)


class AsyncMongomockCursor:
    """Async iterator wrapper for mongomock cursor."""
    
    def __init__(self, sync_cursor):
        self._cursor = sync_cursor
        self._items = list(sync_cursor)
        self._index = 0
    
    def limit(self, count):
        """Limit results."""
        self._items = self._items[:count]
        return self
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return item


class AsyncMongomockDatabase:
    """Wrapper to make mongomock database async-compatible."""
    
    def __init__(self, sync_db):
        self._db = sync_db
    
    def __getitem__(self, name):
        """Get collection by name."""
        return AsyncMongomockCollection(self._db[name])


@pytest.fixture
def mock_mongo_client() -> Generator[mongomock.MongoClient, None, None]:
    """
    Create a mongomock client wrapped as Motor async client.
    
    Returns:
        Mocked async MongoDB client for testing
    """
    # Use mongomock to create an in-memory MongoDB
    client = mongomock.MongoClient()
    yield client
    client.close()


@pytest.fixture
def mock_mongo_db(mock_mongo_client) -> AsyncMongomockDatabase:
    """
    Get a test database from the mock client.
    
    Returns:
        Async-wrapped mocked MongoDB database instance
    """
    sync_db = mock_mongo_client['scareverse_test']
    return AsyncMongomockDatabase(sync_db)


@pytest.fixture
def test_document_class():
    """
    Simple test document model for basic CRUD operations.
    
    Returns:
        Pydantic model class for testing
    """
    class TestDocument(BaseModel):
        id: str
        name: str
        value: int
        description: str = ""
        
    return TestDocument


@pytest.fixture
def test_cell_class():
    """
    Cell-like model for realistic testing.
    
    Returns:
        Pydantic model class mimicking Cell structure
    """
    class TestCell(BaseModel):
        id: str
        nome: str
        tipo: str
        conteudo: str = ""
        ordem: int = 0
        metadata: dict = Field(default_factory=dict)
    
    return TestCelula


@pytest.fixture
def sample_test_document(test_document_class):
    """
    Sample test document instance.
    
    Returns:
        Test document instance
    """
    return test_document_class(
        id="doc_123",
        name="Test Document",
        value=42,
        description="A test document for testing"
    )


@pytest.fixture
def sample_celula(test_celula_class):
    """
    Sample cell instance for testing.
    
    Returns:
        Test cell instance
    """
    return test_celula_class(
        id="cel_456",
        name="Test Cell",
        type="code",
        content="print('hello world')",
        ordem=1,
        metadata={"tags": ["test", "example"]}
    )


@pytest.fixture
def populated_collection(mock_mongo_client, test_document_class):
    """
    MongoDB collection pre-populated with test documents.
    
    Returns:
        Collection name and inserted document IDs
    """
    # Use sync collection for setup
    sync_db = mock_mongo_client['scareverse_test']
    collection = sync_db['test_collection_runtime']
    
    # Insert multiple test documents
    docs = [
        {
            "id": "doc_1",
            "name": "Document 1",
            "value": 100,
            "description": "First document",
            "user_id": "user_1",
            "session_id": "session_1"
        },
        {
            "id": "doc_2",
            "name": "Document 2",
            "value": 200,
            "description": "Second document",
            "user_id": "user_1",
            "session_id": "session_1"
        },
        {
            "id": "doc_3",
            "name": "Document 3",
            "value": 300,
            "description": "Third document",
            "user_id": "user_2",
            "session_id": "session_2"
        }
    ]
    
    collection.insert_many(docs)
    
    return {
        'collection_name': 'test_collection',
        'doc_ids': ["doc_1", "doc_2", "doc_3"]
    }
