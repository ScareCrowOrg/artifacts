"""
Unit tests for MongoDB migrations system.

Tests the migration framework including:
- Base migration class functionality
- Collection and index creation
- Migration tracking and idempotency
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Import migration classes
from app.database.mongodb.migrations import (
    MongoDBMigration,
    CreateRuntimeCollections,
    CreateApplicationUser,
    run_migrations
)


class TestMongoDBMigration:
    """Tests for the base MongoDBMigration class."""
    
    @pytest.mark.asyncio
    async def test_migration_initialization(self):
        """Test that migration initializes with correct version."""
        class TestMigration(MongoDBMigration):
            async def up(self, db):
                pass
        
        migration = TestMigration()
        assert migration.version == "TestMigration"
        assert migration.applied_at is None
    
    @pytest.mark.asyncio
    async def test_is_applied_not_applied(self, mock_mongo_db):
        """Test is_applied returns False for new migration."""
        class TestMigration(MongoDBMigration):
            async def up(self, db):
                pass
        
        migration = TestMigration()
        
        # Mock the migrations collection to be empty
        db_mock = AsyncMock()
        migrations_collection = AsyncMock()
        migrations_collection.find_one.return_value = None
        db_mock.__getitem__.return_value = migrations_collection
        
        result = await migration.is_applied(db_mock)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_is_applied_already_applied(self):
        """Test is_applied returns True for applied migration."""
        class TestMigration(MongoDBMigration):
            async def up(self, db):
                pass
        
        migration = TestMigration()
        
        # Mock the migrations collection to return a record
        db_mock = AsyncMock()
        migrations_collection = AsyncMock()
        migrations_collection.find_one.return_value = {
            "version": "TestMigration",
            "applied_at": datetime.utcnow()
        }
        db_mock.__getitem__.return_value = migrations_collection
        
        result = await migration.is_applied(db_mock)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_mark_applied(self):
        """Test marking a migration as applied."""
        class TestMigration(MongoDBMigration):
            async def up(self, db):
                pass
        
        migration = TestMigration()
        
        # Mock the migrations collection
        db_mock = AsyncMock()
        migrations_collection = AsyncMock()
        db_mock.__getitem__.return_value = migrations_collection
        
        await migration.mark_applied(db_mock)
        
        # Verify update_one was called
        migrations_collection.update_one.assert_called_once()
        assert migration.applied_at is not None
    
    @pytest.mark.asyncio
    async def test_down_not_implemented(self):
        """Test that down() method logs warning by default."""
        class TestMigration(MongoDBMigration):
            async def up(self, db):
                pass
        
        migration = TestMigration()
        db_mock = AsyncMock()
        
        # Should not raise an exception
        await migration.down(db_mock)


class TestCreateRuntimeCollections:
    """Tests for CreateRuntimeCollections migration."""
    
    @pytest.mark.asyncio
    async def test_creates_all_collections(self):
        """Test that all runtime collections are created."""
        migration = CreateRuntimeCollections()
        
        # Mock database
        db_mock = AsyncMock()
        db_mock.list_collection_names.return_value = []
        db_mock.create_collection = AsyncMock()
        
        # Mock collections for index creation
        for collection_name in ['cells_runtime', 'books_runtime', 'sessions_runtime',
                                'users_runtime', 'memory_runtime', 'traces_runtime']:
            collection_mock = AsyncMock()
            collection_mock.list_indexes.return_value.to_list.return_value = []
            collection_mock.create_index = AsyncMock()
            setattr(db_mock, collection_name, collection_mock)
        
        await migration.up(db_mock)
        
        # Verify create_collection was called for each collection
        assert db_mock.create_collection.call_count == 6
    
    @pytest.mark.asyncio
    async def test_skips_existing_collections(self):
        """Test that existing collections are not recreated."""
        migration = CreateRuntimeCollections()
        
        # Mock database with existing collections
        db_mock = AsyncMock()
        db_mock.list_collection_names.return_value = [
            'cells_runtime', 'books_runtime', 'sessions_runtime',
            'users_runtime', 'memory_runtime', 'traces_runtime'
        ]
        db_mock.create_collection = AsyncMock()
        
        # Mock collections for index creation
        for collection_name in ['cells_runtime', 'books_runtime', 'sessions_runtime',
                                'users_runtime', 'memory_runtime', 'traces_runtime']:
            collection_mock = AsyncMock()
            collection_mock.list_indexes.return_value.to_list.return_value = []
            collection_mock.create_index = AsyncMock()
            setattr(db_mock, collection_name, collection_mock)
        
        await migration.up(db_mock)
        
        # Verify create_collection was NOT called
        db_mock.create_collection.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_creates_indexes(self):
        """Test that indexes are created on collections."""
        migration = CreateRuntimeCollections()
        
        # Mock database
        db_mock = AsyncMock()
        db_mock.list_collection_names.return_value = []
        db_mock.create_collection = AsyncMock()
        
        # Mock cells_runtime collection
        cells_mock = AsyncMock()
        cells_mock.list_indexes.return_value.to_list.return_value = []
        cells_mock.create_index = AsyncMock()
        db_mock.cells_runtime = cells_mock
        
        # Mock other collections similarly
        for collection_name in ['books_runtime', 'sessions_runtime',
                                'users_runtime', 'memory_runtime', 'traces_runtime']:
            collection_mock = AsyncMock()
            collection_mock.list_indexes.return_value.to_list.return_value = []
            collection_mock.create_index = AsyncMock()
            setattr(db_mock, collection_name, collection_mock)
        
        await migration.up(db_mock)
        
        # Verify indexes were created on cells_runtime (5 indexes)
        assert cells_mock.create_index.call_count == 5
    
    @pytest.mark.asyncio
    async def test_idempotent_execution(self):
        """Test that migration can be run multiple times safely."""
        migration = CreateRuntimeCollections()
        
        # Mock database
        db_mock = AsyncMock()
        existing_collections = []
        
        def list_collections_side_effect():
            return existing_collections.copy()
        
        db_mock.list_collection_names = AsyncMock(side_effect=list_collections_side_effect)
        
        async def create_collection_side_effect(name):
            existing_collections.append(name)
        
        db_mock.create_collection = AsyncMock(side_effect=create_collection_side_effect)
        
        # Mock collections for index creation
        for collection_name in ['cells_runtime', 'books_runtime', 'sessions_runtime',
                                'users_runtime', 'memory_runtime', 'traces_runtime']:
            collection_mock = AsyncMock()
            collection_mock.list_indexes.return_value.to_list.return_value = []
            collection_mock.create_index = AsyncMock()
            setattr(db_mock, collection_name, collection_mock)
        
        # Run migration twice
        await migration.up(db_mock)
        first_call_count = db_mock.create_collection.call_count
        
        await migration.up(db_mock)
        second_call_count = db_mock.create_collection.call_count
        
        # Second run should not create new collections
        assert first_call_count == 6
        assert second_call_count == 6  # Same count, no additional calls


class TestCreateApplicationUser:
    """Tests for CreateApplicationUser migration."""
    
    @pytest.mark.asyncio
    async def test_creates_new_user(self):
        """Test creating a new application user."""
        migration = CreateApplicationUser()
        
        # Mock database
        db_mock = AsyncMock()
        db_mock.command = AsyncMock(side_effect=[
            {"users": []},  # usersInfo returns no users
            None  # createUser succeeds
        ])
        
        with patch.dict('os.environ', {
            'MONGODB_APP_USERNAME': 'test_user',
            'MONGODB_APP_PASSWORD': 'test_password'
        }):
            await migration.up(db_mock)
        
        # Verify createUser was called
        assert db_mock.command.call_count == 2
    
    @pytest.mark.asyncio
    async def test_updates_existing_user(self):
        """Test updating an existing user's roles."""
        migration = CreateApplicationUser()
        
        # Mock database
        db_mock = AsyncMock()
        db_mock.command = AsyncMock(side_effect=[
            {"users": [{"user": "test_user"}]},  # usersInfo returns existing user
            None  # updateUser succeeds
        ])
        
        with patch.dict('os.environ', {
            'MONGODB_APP_USERNAME': 'test_user',
            'MONGODB_APP_PASSWORD': 'test_password'
        }):
            await migration.up(db_mock)
        
        # Verify updateUser was called
        assert db_mock.command.call_count == 2
    
    @pytest.mark.asyncio
    async def test_handles_permission_error(self):
        """Test graceful handling of permission errors."""
        from pymongo.errors import PyMongoError
        
        migration = CreateApplicationUser()
        
        # Mock database that raises permission error
        db_mock = AsyncMock()
        db_mock.command = AsyncMock(side_effect=PyMongoError("not authorized"))
        
        with patch.dict('os.environ', {
            'MONGODB_APP_USERNAME': 'test_user',
            'MONGODB_APP_PASSWORD': 'test_password'
        }):
            # Should not raise exception
            await migration.up(db_mock)


class TestRunMigrations:
    """Tests for the run_migrations orchestration function."""
    
    @pytest.mark.asyncio
    @patch('app.database.mongodb.migrations.get_mongodb_client')
    @patch('app.database.mongodb.migrations.get_mongodb_database')
    async def test_skip_when_mongodb_disabled(self, mock_get_db, mock_get_client):
        """Test migrations are skipped when MongoDB is disabled."""
        with patch('app.database.mongodb.migrations.MONGODB_ENABLED', False):
            result = await run_migrations()
        
        assert result["status"] == "skipped"
        assert result["reason"] == "MongoDB is disabled"
        assert result["applied"] == 0
    
    @pytest.mark.asyncio
    @patch('app.database.mongodb.migrations.get_mongodb_client')
    @patch('app.database.mongodb.migrations.get_mongodb_database')
    async def test_successful_migration_run(self, mock_get_db, mock_get_client):
        """Test successful execution of all migrations."""
        # Mock database
        db_mock = AsyncMock()
        db_mock.list_collection_names.return_value = []
        db_mock.create_collection = AsyncMock()
        
        # Mock migrations collection
        migrations_collection = AsyncMock()
        migrations_collection.find_one.return_value = None  # No migrations applied
        migrations_collection.update_one = AsyncMock()
        db_mock.__getitem__.return_value = migrations_collection
        
        # Mock collection methods for CreateRuntimeCollections
        for collection_name in ['cells_runtime', 'books_runtime', 'sessions_runtime',
                                'users_runtime', 'memory_runtime', 'traces_runtime']:
            collection_mock = AsyncMock()
            collection_mock.list_indexes.return_value.to_list.return_value = []
            collection_mock.create_index = AsyncMock()
            setattr(db_mock, collection_name, collection_mock)
        
        # Mock database command for CreateApplicationUser
        db_mock.command = AsyncMock(side_effect=[
            {"users": []},  # usersInfo
            None  # createUser
        ])
        
        mock_get_db.return_value = db_mock
        mock_get_client.return_value = AsyncMock()
        
        with patch('app.database.mongodb.migrations.MONGODB_ENABLED', True):
            result = await run_migrations()
        
        assert result["status"] == "success"
        assert result["applied"] == 2
        assert result["skipped"] == 0
        assert result["failed"] == 0
    
    @pytest.mark.asyncio
    @patch('app.database.mongodb.migrations.get_mongodb_client')
    @patch('app.database.mongodb.migrations.get_mongodb_database')
    async def test_skip_applied_migrations(self, mock_get_db, mock_get_client):
        """Test that already applied migrations are skipped."""
        # Mock database
        db_mock = AsyncMock()
        db_mock.list_collection_names.return_value = []
        
        # Mock migrations collection - migrations already applied
        migrations_collection = AsyncMock()
        migrations_collection.find_one.return_value = {
            "version": "CreateRuntimeCollections",
            "applied_at": datetime.utcnow()
        }
        db_mock.__getitem__.return_value = migrations_collection
        
        mock_get_db.return_value = db_mock
        mock_get_client.return_value = AsyncMock()
        
        with patch('app.database.mongodb.migrations.MONGODB_ENABLED', True):
            result = await run_migrations()
        
        assert result["skipped"] == 2
        assert result["applied"] == 0
    
    @pytest.mark.asyncio
    @patch('app.database.mongodb.migrations.get_mongodb_client')
    async def test_handles_client_unavailable(self, mock_get_client):
        """Test handling when MongoDB client is unavailable."""
        mock_get_client.return_value = None
        
        with patch('app.database.mongodb.migrations.MONGODB_ENABLED', True):
            result = await run_migrations()
        
        assert result["status"] == "error"
        assert result["reason"] == "MongoDB client unavailable"
