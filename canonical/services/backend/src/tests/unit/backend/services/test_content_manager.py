"""
Unit tests for ContentManager and ContentTypeLoader services.

Tests ContentType loading, schema validation, and content persistence.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.services.content_manager import ContentTypeLoader, ContentManager
from app.models.content_types import (
    ContentType,
    Content,
    CreateContentRequest,
    UpdateContentMetadataRequest,
    StoragePolicy
)


class TestContentTypeLoader:
    """Tests for ContentTypeLoader."""
    
    @pytest.fixture
    def temp_content_types_dir(self, tmp_path):
        """Create temporary content_types directory with test files."""
        content_types_dir = tmp_path / "content_types"
        content_types_dir.mkdir()
        
        # Create test ContentType
        test_type = {
            "id": "test-type",
            "name": "Test Type",
            "mime_type": "text/plain",
            "version": "1.0.0",
            "expected_fragments": {
                "key1": {"type": "string"},
                "key2": {"type": "integer"}
            },
            "storage_policy": "local"
        }
        
        type_file = content_types_dir / "test-type.json"
        with open(type_file, 'w') as f:
            json.dump(test_type, f)
        
        return content_types_dir
    
    def test_load_content_type(self, temp_content_types_dir):
        """Test loading a ContentType from file."""
        loader = ContentTypeLoader(str(temp_content_types_dir))
        content_type = loader.load_content_type("test-type")
        
        assert content_type is not None
        assert content_type.id == "test-type"
        assert content_type.name == "Test Type"
        assert content_type.mime_type == "text/plain"
    
    def test_load_nonexistent_type(self, temp_content_types_dir):
        """Test loading a non-existent ContentType."""
        loader = ContentTypeLoader(str(temp_content_types_dir))
        content_type = loader.load_content_type("nonexistent")
        
        assert content_type is None
    
    def test_cache_content_type(self, temp_content_types_dir):
        """Test that ContentTypes are cached."""
        loader = ContentTypeLoader(str(temp_content_types_dir))
        
        # First load
        ct1 = loader.load_content_type("test-type")
        
        # Second load should hit cache
        ct2 = loader.load_content_type("test-type")
        
        assert ct1 is ct2  # Same instance from cache
    
    def test_list_content_types(self, temp_content_types_dir):
        """Test listing all ContentTypes."""
        loader = ContentTypeLoader(str(temp_content_types_dir))
        content_types = loader.list_content_types()
        
        assert len(content_types) == 1
        assert content_types[0].id == "test-type"
    
    def test_reload_cache(self, temp_content_types_dir):
        """Test cache reload."""
        loader = ContentTypeLoader(str(temp_content_types_dir))
        
        # Load and cache
        loader.load_content_type("test-type")
        assert len(loader._cache) == 1
        
        # Clear cache
        loader.reload_cache()
        assert len(loader._cache) == 0
    
    def test_invalid_json(self, tmp_path):
        """Test handling of invalid JSON file."""
        content_types_dir = tmp_path / "content_types"
        content_types_dir.mkdir()
        
        # Create invalid JSON file
        bad_file = content_types_dir / "bad-type.json"
        bad_file.write_text("{ invalid json }")
        
        loader = ContentTypeLoader(str(content_types_dir))
        
        with pytest.raises(ValueError, match="Invalid ContentType definition"):
            loader.load_content_type("bad-type")


class TestContentManager:
    """Tests for ContentManager."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database for testing."""
        with patch('app.services.content_manager.db') as mock:
            yield mock
    
    @pytest.fixture
    def mock_loader(self):
        """Mock ContentTypeLoader."""
        loader = Mock(spec=ContentTypeLoader)
        
        # Create mock ContentType
        mock_ct = ContentType(
            id="test-type",
            name="Test Type",
            mime_type="text/plain",
            expected_fragments={
                "key1": {"type": "string"},
                "key2": {"type": "integer"}
            }
        )
        
        loader.load_content_type.return_value = mock_ct
        return loader
    
    def test_validate_fragments_success(self, mock_loader):
        """Test successful fragment validation."""
        manager = ContentManager(mock_loader)
        content_type = mock_loader.load_content_type("test-type")
        
        fragments = {"key1": "value", "key2": 42}
        
        # Should not raise
        assert manager.validate_content_fragments(content_type, fragments) is True
    
    def test_validate_fragments_missing_required(self, mock_loader):
        """Test validation fails with missing required fields."""
        manager = ContentManager(mock_loader)
        content_type = mock_loader.load_content_type("test-type")
        
        fragments = {"key1": "value"}  # Missing key2
        
        with pytest.raises(ValueError, match="Missing required fragment"):
            manager.validate_content_fragments(content_type, fragments)
    
    def test_validate_fragments_wrong_type(self, mock_loader):
        """Test validation fails with wrong type."""
        manager = ContentManager(mock_loader)
        content_type = mock_loader.load_content_type("test-type")
        
        fragments = {"key1": "value", "key2": "not-an-integer"}
        
        with pytest.raises(ValueError, match="wrong type"):
            manager.validate_content_fragments(content_type, fragments)
    
    def test_create_content_success(self, mock_loader, mock_db):
        """Test successful content creation."""
        manager = ContentManager(mock_loader)
        
        request = CreateContentRequest(
            content_type_id="test-type",
            assignee_id="user-123",
            data_ref="file:///test.dat",
            fragments={"key1": "value", "key2": 42}
        )
        
        content = manager.create_content(request)
        
        assert content.content_type_id == "test-type"
        assert content.assignee_id == "user-123"
        assert content.version == 1
        assert content.is_latest is True
        
        # Verify DB insert was called
        mock_db.insert.assert_called_once()
        assert mock_db.insert.call_args[0][0] == "contents"
    
    def test_create_content_type_not_found(self, mock_loader, mock_db):
        """Test content creation fails if ContentType not found."""
        mock_loader.load_content_type.return_value = None
        manager = ContentManager(mock_loader)
        
        request = CreateContentRequest(
            content_type_id="nonexistent",
            assignee_id="user-123",
            data_ref="file:///test.dat"
        )
        
        with pytest.raises(ValueError, match="ContentType not found"):
            manager.create_content(request)
    
    def test_create_content_invalid_fragments(self, mock_loader, mock_db):
        """Test content creation fails with invalid fragments."""
        manager = ContentManager(mock_loader)
        
        request = CreateContentRequest(
            content_type_id="test-type",
            assignee_id="user-123",
            data_ref="file:///test.dat",
            fragments={"key1": "value"}  # Missing key2
        )
        
        with pytest.raises(ValueError, match="Missing required fragment"):
            manager.create_content(request)
    
    def test_get_content(self, mock_loader, mock_db):
        """Test retrieving content by ID."""
        manager = ContentManager(mock_loader)
        
        mock_db.find_one.return_value = {
            "id": "content-123",
            "content_type_id": "test-type",
            "assignee_id": "user-123",
            "data_ref": "file:///test.dat",
            "version": 1,
            "is_latest": True,
            "fragments": {},
            "tags": [],
            "metadata": {},
            "created_at": "2024-01-01T00:00:00"
        }
        
        content = manager.get_content("content-123")
        
        assert content is not None
        assert content.id == "content-123"
        
        mock_db.find_one.assert_called_once_with("contents", {"id": "content-123"})
    
    def test_get_content_not_found(self, mock_loader, mock_db):
        """Test retrieving non-existent content."""
        manager = ContentManager(mock_loader)
        mock_db.find_one.return_value = None
        
        content = manager.get_content("nonexistent")
        
        assert content is None
    
    def test_create_new_version(self, mock_loader, mock_db):
        """Test creating a new version of content."""
        manager = ContentManager(mock_loader)
        
        # Mock existing content
        existing = Content(
            id="content-123",
            content_type_id="test-type",
            assignee_id="user-123",
            data_ref="file:///test.dat",
            version=1,
            is_latest=True,
            fragments={"key1": "old", "key2": 1}
        )
        
        with patch.object(manager, 'get_content', return_value=existing):
            request = UpdateContentMetadataRequest(
                fragments={"key1": "new", "key2": 2}
            )
            
            new_version = manager.create_new_version("content-123", request)
            
            assert new_version.version == 2
            assert new_version.is_latest is True
            assert new_version.previous_version_id == "content-123"
            assert new_version.fragments["key1"] == "new"
            
            # Verify old version marked as not latest
            mock_db.update.assert_called_once()
            update_call = mock_db.update.call_args
            assert update_call[0][0] == "contents"
            assert update_call[0][1] == {"id": "content-123"}
            assert update_call[0][2] == {"$set": {"is_latest": False}}
    
    def test_query_contents(self, mock_loader, mock_db):
        """Test querying contents with filters."""
        from app.models.content_types import ContentQueryFilters
        
        manager = ContentManager(mock_loader)
        
        mock_db.find.return_value = [
            {
                "id": "content-1",
                "content_type_id": "test-type",
                "assignee_id": "user-123",
                "data_ref": "file:///test1.dat",
                "version": 1,
                "is_latest": True,
                "fragments": {},
                "tags": [],
                "metadata": {},
                "created_at": "2024-01-01T00:00:00"
            }
        ]
        
        filters = ContentQueryFilters(
            content_type_id="test-type",
            assignee_id="user-123"
        )
        
        results = manager.query_contents(filters)
        
        assert len(results) == 1
        assert results[0].id == "content-1"
        
        # Verify query was built correctly
        mock_db.find.assert_called_once()
        query = mock_db.find.call_args[0][1]
        assert query["content_type_id"] == "test-type"
        assert query["assignee_id"] == "user-123"
