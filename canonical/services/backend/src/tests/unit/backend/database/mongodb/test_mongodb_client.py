"""
Unit tests for MongoDB client connection and management.

Tests client initialization, connection pooling, health checks,
and connection error handling without requiring a real MongoDB instance.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from pymongo.errors import ConnectionFailure

from app.database.mongodb.client import (
    get_mongodb_client,
    get_mongodb_database,
    close_mongodb_client,
    reset_mongodb_client
)


class TestMongoDBClientInitialization:
    """Test MongoDB client initialization and configuration."""
    
    @pytest.mark.asyncio
    async def test_client_disabled_when_mongodb_not_enabled(self):
        """MongoDB client should return None when MONGODB_ENABLED=False."""
        with patch('app.database.mongodb.client.MONGODB_ENABLED', False):
            reset_mongodb_client()
            client = await get_mongodb_client()
            assert client is None
    
    @pytest.mark.asyncio
    async def test_client_initialization_success(self):
        """Test successful MongoDB client initialization."""
        with patch('app.database.mongodb.client.MONGODB_ENABLED', True), \
             patch('app.database.mongodb.client.AsyncIOMotorClient') as mock_client_class:
            
            # Setup mock client
            mock_client = AsyncMock()
            mock_client.admin.command = AsyncMock(return_value={'ok': 1})
            mock_client_class.return_value = mock_client
            
            reset_mongodb_client()
            client = await get_mongodb_client()
            
            assert client is not None
            assert client == mock_client
            mock_client.admin.command.assert_called_once_with('ping')
    
    @pytest.mark.asyncio
    async def test_client_singleton_pattern(self):
        """MongoDB client should return the same instance on multiple calls."""
        with patch('app.database.mongodb.client.MONGODB_ENABLED', True), \
             patch('app.database.mongodb.client.AsyncIOMotorClient') as mock_client_class:
            
            mock_client = AsyncMock()
            mock_client.admin.command = AsyncMock(return_value={'ok': 1})
            mock_client_class.return_value = mock_client
            
            reset_mongodb_client()
            client1 = await get_mongodb_client()
            client2 = await get_mongodb_client()
            
            assert client1 is client2
            # Client should only be created once
            assert mock_client_class.call_count == 1
    
    @pytest.mark.asyncio
    async def test_client_connection_failure(self):
        """Client should handle connection failures gracefully."""
        with patch('app.database.mongodb.client.MONGODB_ENABLED', True), \
             patch('app.database.mongodb.client.AsyncIOMotorClient') as mock_client_class:
            
            # Simulate connection failure
            mock_client = AsyncMock()
            mock_client.admin.command = AsyncMock(
                side_effect=ConnectionFailure("Connection refused")
            )
            mock_client_class.return_value = mock_client
            
            reset_mongodb_client()
            client = await get_mongodb_client()
            
            assert client is None
    
    @pytest.mark.asyncio
    async def test_client_generic_error(self):
        """Client should handle generic errors during initialization."""
        with patch('app.database.mongodb.client.MONGODB_ENABLED', True), \
             patch('app.database.mongodb.client.AsyncIOMotorClient') as mock_client_class:
            
            # Simulate generic error
            mock_client_class.side_effect = Exception("Unexpected error")
            
            reset_mongodb_client()
            client = await get_mongodb_client()
            
            assert client is None


class TestMongoDBDatabase:
    """Test MongoDB database instance management."""
    
    @pytest.mark.asyncio
    async def test_get_database_success(self):
        """Test successful database instance retrieval."""
        with patch('app.database.mongodb.client.MONGODB_ENABLED', True), \
             patch('app.database.mongodb.client.AsyncIOMotorClient') as mock_client_class:
            
            mock_client = AsyncMock()
            mock_client.admin.command = AsyncMock(return_value={'ok': 1})
            mock_db = MagicMock()
            mock_client.__getitem__ = MagicMock(return_value=mock_db)
            mock_client_class.return_value = mock_client
            
            reset_mongodb_client()
            db = await get_mongodb_database()
            
            assert db is not None
            assert db == mock_db
    
    @pytest.mark.asyncio
    async def test_get_database_when_client_unavailable(self):
        """Database should return None when client is unavailable."""
        with patch('app.database.mongodb.client.MONGODB_ENABLED', False):
            reset_mongodb_client()
            db = await get_mongodb_database()
            assert db is None
    
    @pytest.mark.asyncio
    async def test_database_singleton_pattern(self):
        """Database should return the same instance on multiple calls."""
        with patch('app.database.mongodb.client.MONGODB_ENABLED', True), \
             patch('app.database.mongodb.client.AsyncIOMotorClient') as mock_client_class:
            
            mock_client = AsyncMock()
            mock_client.admin.command = AsyncMock(return_value={'ok': 1})
            mock_db = MagicMock()
            mock_client.__getitem__ = MagicMock(return_value=mock_db)
            mock_client_class.return_value = mock_client
            
            reset_mongodb_client()
            db1 = await get_mongodb_database()
            db2 = await get_mongodb_database()
            
            assert db1 is db2


class TestMongoDBClientLifecycle:
    """Test MongoDB client lifecycle management."""
    
    @pytest.mark.asyncio
    async def test_close_client(self):
        """Test closing MongoDB client connection."""
        with patch('app.database.mongodb.client.MONGODB_ENABLED', True), \
             patch('app.database.mongodb.client.AsyncIOMotorClient') as mock_client_class:
            
            mock_client = AsyncMock()
            mock_client.admin.command = AsyncMock(return_value={'ok': 1})
            mock_client.close = MagicMock()
            mock_client_class.return_value = mock_client
            
            reset_mongodb_client()
            await get_mongodb_client()
            await close_mongodb_client()
            
            mock_client.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_client_error_handling(self):
        """Client close should handle errors gracefully."""
        with patch('app.database.mongodb.client.MONGODB_ENABLED', True), \
             patch('app.database.mongodb.client.AsyncIOMotorClient') as mock_client_class:
            
            mock_client = AsyncMock()
            mock_client.admin.command = AsyncMock(return_value={'ok': 1})
            mock_client.close = MagicMock(side_effect=Exception("Close error"))
            mock_client_class.return_value = mock_client
            
            reset_mongodb_client()
            await get_mongodb_client()
            
            # Should not raise exception
            await close_mongodb_client()
    
    def test_reset_client(self):
        """Test resetting client state."""
        reset_mongodb_client()
        # After reset, global variables should be None
        # This is primarily for testing purposes
        from app.database.mongodb import client as client_module
        assert client_module._mongodb_client is None
        assert client_module._mongodb_database is None


class TestMongoDBConnectionParameters:
    """Test MongoDB connection parameters and configuration."""
    
    @pytest.mark.asyncio
    async def test_connection_parameters(self):
        """Verify MongoDB client is initialized with correct parameters."""
        with patch('app.database.mongodb.client.MONGODB_ENABLED', True), \
             patch('app.database.mongodb.client.AsyncIOMotorClient') as mock_client_class, \
             patch('app.database.mongodb.client.get_mongodb_uri', return_value='mongodb://localhost:27017'):
            
            mock_client = AsyncMock()
            mock_client.admin.command = AsyncMock(return_value={'ok': 1})
            mock_client_class.return_value = mock_client
            
            reset_mongodb_client()
            await get_mongodb_client()
            
            # Verify client was created with correct parameters
            mock_client_class.assert_called_once()
            call_args = mock_client_class.call_args
            
            assert call_args[0][0] == 'mongodb://localhost:27017'
            assert call_args[1]['serverSelectionTimeoutMS'] == 5000
            assert call_args[1]['connectTimeoutMS'] == 10000
            assert call_args[1]['maxPoolSize'] == 50
