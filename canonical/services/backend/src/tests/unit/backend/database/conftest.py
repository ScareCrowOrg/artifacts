"""
Shared fixtures for database persistence tests.

Provides test database instances, mock data, and utilities for testing
the JSONDatabase and RedisCachedJSONDatabase classes.
"""

import pytest
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock
import os

from app.database.connection import JSONDatabase
from app.database.redis_cache import RedisCachedJSONDatabase


@pytest.fixture
def test_db() -> Generator[JSONDatabase, None, None]:
    """
    Create a temporary test database instance.
    
    Provides a clean JSONDatabase with isolated temporary storage
    that is automatically cleaned up after the test.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        db = JSONDatabase(base_path=Path(temp_dir), is_test_env=True)
        yield db
        # Cleanup is handled by tempfile.TemporaryDirectory


@pytest.fixture
def test_db_with_data(test_db: JSONDatabase) -> JSONDatabase:
    """
    Create a test database pre-populated with sample data.
    
    Useful for testing query and update operations without
    needing to insert data in each test.
    """
    from pydantic import BaseModel
    
    # Simple test model
    class TestDocument(BaseModel):
        id: str
        name: str
        value: int
    
    # Insert sample documents
    test_db.insert("test_collection", 
                   TestDocument(id="doc1", name="Document 1", value=100),
                   is_canonical=True)
    test_db.insert("test_collection",
                   TestDocument(id="doc2", name="Document 2", value=200),
                   is_canonical=True)
    test_db.insert("test_collection",
                   TestDocument(id="doc3", name="Document 3", value=300),
                   user_id="user1", session_id="session1")
    
    return test_db


@pytest.fixture
def mock_redis_client():
    """
    Create a mock Redis client for testing RedisCachedJSONDatabase.
    
    Returns an AsyncMock that simulates Redis operations without
    requiring a real Redis instance.
    """
    mock = AsyncMock()
    
    # Mock get method to return None (cache miss)
    mock.get = AsyncMock(return_value=None)
    
    # Mock set method
    mock.set = AsyncMock(return_value=True)
    
    # Mock setex method (set with expiration)
    mock.setex = AsyncMock(return_value=True)
    
    # Mock delete method
    mock.delete = AsyncMock(return_value=1)
    
    # Mock keys method (for pattern matching)
    mock.keys = AsyncMock(return_value=[])
    
    # Mock scan method (for pattern matching with cursor)
    mock.scan = AsyncMock(return_value=(0, []))
    
    # Mock ping method
    mock.ping = AsyncMock(return_value=True)
    
    return mock


@pytest.fixture
def cached_test_db(test_db: JSONDatabase, mock_redis_client):
    """
    Create a cached test database with mocked Redis.
    
    Provides a RedisCachedJSONDatabase for testing cache operations
    without requiring a real Redis instance.
    """
    cached_db = RedisCachedJSONDatabase(
        base_path=test_db.base_path,
        is_test_env=True
    )
    cached_db._redis_client = mock_redis_client
    cached_db._cache_enabled = True
    
    return cached_db


@pytest.fixture
def sample_document_class():
    """
    Provide a sample Pydantic model for testing.
    
    Returns a simple document class that can be used
    for insert, find, update, and delete operations.
    """
    from pydantic import BaseModel, Field
    
    class SampleDocument(BaseModel):
        id: str
        name: str
        description: str = ""
        value: int = 0
        tags: list[str] = Field(default_factory=list)
    
    return SampleDocument


@pytest.fixture
def sample_celula_class():
    """
    Provide a Cell-like model for realistic testing.
    
    Mimics the actual Cell model structure for more
    realistic persistence tests.
    """
    from pydantic import BaseModel, Field
    from typing import Optional
    
    class TestCell(BaseModel):
        id: str
        nome: str
        tipo: str
        conteudo: str = ""
        ordem: int = 0
        metadata: dict = Field(default_factory=dict)
    
    return TestCell


@pytest.fixture
def sample_modelo_ia_class():
    """
    Provide a ModeloIA-like model for encryption testing.
    
    Includes sensitive fields (apiKey) to test encryption/decryption.
    """
    from pydantic import BaseModel
    from typing import Optional
    
    class TestAIModel(BaseModel):
        id: str
        nome: str
        provider: str
        apiKey: Optional[str] = None
        configuracoes: dict = {}
    
    return TestAIModel


@pytest.fixture
def encryption_key():
    """
    Provide a test encryption key.
    
    Sets and cleans up ENCRYPTION_KEY environment variable
    for encryption tests. Also reloads config and crypto modules
    to pick up the new key.
    """
    # Generate a valid Fernet key for testing
    from cryptography.fernet import Fernet
    import importlib
    key = Fernet.generate_key().decode()
    
    old_key = os.environ.get("ENCRYPTION_KEY")
    os.environ["ENCRYPTION_KEY"] = key
    
    # Reload modules to pick up the new key (order matters!)
    import app.config
    import app.crypto_utils
    import app.database.encryption
    importlib.reload(app.config)
    importlib.reload(app.crypto_utils)
    importlib.reload(app.database.encryption)
    
    yield key
    
    # Cleanup
    if old_key:
        os.environ["ENCRYPTION_KEY"] = old_key
    else:
        os.environ.pop("ENCRYPTION_KEY", None)
    
    # Reload again to restore original state
    importlib.reload(app.config)
    importlib.reload(app.crypto_utils)
    importlib.reload(app.database.encryption)


@pytest.fixture
def no_encryption_key():
    """
    Ensure ENCRYPTION_KEY is not set for testing graceful degradation.
    
    Temporarily removes encryption key to test scenarios where
    encryption is not configured.
    """
    old_key = os.environ.get("ENCRYPTION_KEY")
    os.environ.pop("ENCRYPTION_KEY", None)
    
    yield
    
    # Restore
    if old_key:
        os.environ["ENCRYPTION_KEY"] = old_key
