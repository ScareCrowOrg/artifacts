"""
Pytest fixtures for HybridDatabase tests.

Provides shared test fixtures for mocking MongoDB, Redis, and file-based databases.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel, Field
from typing import Optional

from app.database.hybrid import HybridDatabase
from app.database.connection import JSONDatabase
from app.database.mongodb.operations import MongoDBOperations


class TestModel(BaseModel):
    """Test Pydantic model for database operations."""
    id: str
    nome: str
    tipo: str = "test"


class NotebookItemModel(BaseModel):
    """Test model for notebook items with kind discriminator."""
    id: str
    nome: str
    tipo: str = "test"
    kind: Optional[str] = Field(None, description="Item kind: 'cell' or 'book'")


@pytest.fixture
def test_model():
    """Create a test model instance."""
    return TestModel(id="test_1", nome="Test Document", tipo="test")


@pytest.fixture
def notebook_item_model():
    """Create a notebook item model instance (without kind initially)."""
    return NotebookItemModel(id="test_1", nome="Test Item", tipo="test")


@pytest.fixture
def temp_dir():
    """Create a temporary directory for file-based storage."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def mock_mongodb():
    """Mock MongoDB operations."""
    mock_ops = AsyncMock(spec=MongoDBOperations)
    mock_ops.insert = AsyncMock(return_value="test_1")
    mock_ops.find_one = AsyncMock(return_value=None)
    mock_ops.find_many = AsyncMock(return_value=[])
    mock_ops.update = AsyncMock(return_value=True)
    mock_ops.delete = AsyncMock(return_value=True)
    mock_ops.find_by_field = AsyncMock(return_value=None)
    mock_ops.find_by_fields = AsyncMock(return_value=None)
    return mock_ops


@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.setex = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=1)
    mock_client.scan = AsyncMock(return_value=(0, []))
    mock_client.publish = AsyncMock(return_value=1)
    mock_client.lock = MagicMock()
    
    # Mock lock context manager
    mock_lock = AsyncMock()
    mock_lock.acquire = AsyncMock(return_value=True)
    mock_lock.release = AsyncMock()
    mock_lock.__aenter__ = AsyncMock(return_value=mock_lock)
    mock_lock.__aexit__ = AsyncMock()
    mock_client.lock.return_value = mock_lock
    
    return mock_client


@pytest.fixture
async def hybrid_db_file_only(temp_dir):
    """
    Create HybridDatabase with file-based storage only (MongoDB disabled).
    Uses test environment (is_test_env=True) to allow fallback for runtime collections.
    """
    with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
        db = HybridDatabase(base_path=temp_dir, is_test_env=True)
        yield db


@pytest.fixture
async def hybrid_db_production_mode(temp_dir):
    """
    Create HybridDatabase in production mode (is_test_env=False).
    Used for testing MongoDB enforcement - RuntimeError will be raised for runtime collections.
    """
    with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
        db = HybridDatabase(base_path=temp_dir, is_test_env=False)
        yield db


@pytest.fixture
async def hybrid_db_with_mongodb(temp_dir, mock_mongodb):
    """
    Create HybridDatabase with MongoDB support (mocked).
    """
    with patch('app.database.hybrid.router.MONGODB_ENABLED', True):
        db = HybridDatabase(base_path=temp_dir, is_test_env=True)
        db._mongo_ops = mock_mongodb
        yield db


@pytest.fixture
async def hybrid_db_with_redis(temp_dir, mock_redis_client):
    """
    Create HybridDatabase with Redis caching (mocked).
    """
    with patch('app.core.redis_client.get_redis_client', return_value=mock_redis_client):
        with patch('app.database.hybrid.router.MONGODB_ENABLED', False):
            db = HybridDatabase(base_path=temp_dir, is_test_env=True)
            yield db
