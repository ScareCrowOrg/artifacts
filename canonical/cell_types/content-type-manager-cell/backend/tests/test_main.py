"""
Unit tests for content-type-manager-cell backend.

Tests the 'list' action with various scenarios.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add cell scripts to path
cell_scripts_path = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(cell_scripts_path))

from main import execute_cell, handle_list


class MockContentType:
    """Mock ContentType for testing."""
    
    def __init__(self, id, name, description, mime_type, version="1.0.0", 
                 max_size_bytes=52428800, allowed_extensions=None, render_hints=None):
        self.id = id
        self.name = name
        self.description = description
        self.mime_type = mime_type
        self.version = version
        self.max_size_bytes = max_size_bytes
        self.allowed_extensions = allowed_extensions or []
        self.render_hints = render_hints or {}


@pytest.fixture
def mock_content_types():
    """Fixture providing mock content types."""
    return [
        MockContentType(
            id="image-png",
            name="PNG Image Asset",
            description="PNG raster images",
            mime_type="image/png",
            allowed_extensions=[".png"]
        ),
        MockContentType(
            id="vector-svg",
            name="SVG Vector Graphic",
            description="SVG vector graphics",
            mime_type="image/svg+xml",
            allowed_extensions=[".svg"]
        ),
        MockContentType(
            id="3d-glb",
            name="3D Model (GLB)",
            description="3D models in GLB format",
            mime_type="model/gltf-binary",
            allowed_extensions=[".glb"]
        )
    ]


class TestExecuteCell:
    """Tests for execute_cell router."""
    
    @pytest.mark.asyncio
    async def test_missing_action(self):
        """Test that missing action returns error."""
        result = await execute_cell({})
        
        assert result["success"] is False
        assert "action" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_invalid_action(self):
        """Test that invalid action returns error."""
        result = await execute_cell({"action": "invalid"})
        
        assert result["success"] is False
        assert "unknown action" in result["error"].lower()
    
    @pytest.mark.asyncio
    @patch('main.ContentTypeLoader')
    async def test_list_action_routes_correctly(self, mock_loader_class, mock_content_types):
        """Test that list action is routed correctly."""
        mock_loader = Mock()
        mock_loader.list_content_types.return_value = mock_content_types
        mock_loader_class.return_value = mock_loader
        
        result = await execute_cell({"action": "list"})
        
        assert result["success"] is True
        assert result["action"] == "list"
        assert "data" in result


class TestHandleList:
    """Tests for handle_list action."""
    
    @pytest.mark.asyncio
    @patch('main.ContentTypeLoader')
    async def test_list_all_content_types(self, mock_loader_class, mock_content_types):
        """Test listing all content types."""
        mock_loader = Mock()
        mock_loader.list_content_types.return_value = mock_content_types
        mock_loader_class.return_value = mock_loader
        
        result = await handle_list({"action": "list"})
        
        assert result["success"] is True
        assert result["action"] == "list"
        assert "data" in result
        assert "types" in result["data"]
        assert "total" in result["data"]
        assert len(result["data"]["types"]) == 3
        assert result["data"]["total"] == 3
    
    @pytest.mark.asyncio
    @patch('main.ContentTypeLoader')
    async def test_list_includes_all_metadata(self, mock_loader_class, mock_content_types):
        """Test that list returns all required metadata fields."""
        mock_loader = Mock()
        mock_loader.list_content_types.return_value = mock_content_types
        mock_loader_class.return_value = mock_loader
        
        result = await handle_list({"action": "list"})
        
        assert result["success"] is True
        types_list = result["data"]["types"]
        
        # Check first type has all fields
        first_type = types_list[0]
        assert "id" in first_type
        assert "name" in first_type
        assert "description" in first_type
        assert "mime_type" in first_type
        assert "version" in first_type
        assert "max_size_bytes" in first_type
        assert "allowed_extensions" in first_type
        assert "render_hints" in first_type
        
        # Verify values match mock
        assert first_type["id"] == "image-png"
        assert first_type["name"] == "PNG Image Asset"
        assert first_type["mime_type"] == "image/png"
    
    @pytest.mark.asyncio
    @patch('main.ContentTypeLoader')
    async def test_list_with_limit(self, mock_loader_class, mock_content_types):
        """Test listing with limit parameter."""
        mock_loader = Mock()
        mock_loader.list_content_types.return_value = mock_content_types
        mock_loader_class.return_value = mock_loader
        
        result = await handle_list({"action": "list", "limit": 2})
        
        assert result["success"] is True
        assert len(result["data"]["types"]) == 2
        assert result["data"]["total"] == 3  # Total remains 3
    
    @pytest.mark.asyncio
    @patch('main.ContentTypeLoader')
    async def test_list_with_default_limit(self, mock_loader_class, mock_content_types):
        """Test that default limit is 100."""
        mock_loader = Mock()
        mock_loader.list_content_types.return_value = mock_content_types
        mock_loader_class.return_value = mock_loader
        
        result = await handle_list({"action": "list"})
        
        assert result["success"] is True
        # All 3 types returned (less than default limit of 100)
        assert len(result["data"]["types"]) == 3
    
    @pytest.mark.asyncio
    async def test_list_with_invalid_limit_too_low(self):
        """Test that limit < 1 returns error."""
        result = await handle_list({"action": "list", "limit": 0})
        
        assert result["success"] is False
        assert "invalid limit" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_list_with_invalid_limit_too_high(self):
        """Test that limit > 100 returns error."""
        result = await handle_list({"action": "list", "limit": 101})
        
        assert result["success"] is False
        assert "invalid limit" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_list_with_invalid_limit_type(self):
        """Test that non-integer limit returns error."""
        result = await handle_list({"action": "list", "limit": "invalid"})
        
        assert result["success"] is False
        assert "invalid limit" in result["error"].lower()
    
    @pytest.mark.asyncio
    @patch('main.ContentTypeLoader')
    async def test_list_with_empty_types(self, mock_loader_class):
        """Test listing when no content types exist."""
        mock_loader = Mock()
        mock_loader.list_content_types.return_value = []
        mock_loader_class.return_value = mock_loader
        
        result = await handle_list({"action": "list"})
        
        assert result["success"] is True
        assert result["data"]["types"] == []
        assert result["data"]["total"] == 0
    
    @pytest.mark.asyncio
    @patch('main.ContentTypeLoader')
    async def test_list_handles_loader_exception(self, mock_loader_class):
        """Test that loader exceptions are handled gracefully."""
        mock_loader = Mock()
        mock_loader.list_content_types.side_effect = Exception("Loader error")
        mock_loader_class.return_value = mock_loader
        
        result = await handle_list({"action": "list"})
        
        assert result["success"] is False
        assert result["action"] == "list"
        assert "error" in result
        assert "failed to list" in result["error"].lower()
    
    @pytest.mark.asyncio
    @patch('main.ContentTypeLoader')
    async def test_list_orders_types_consistently(self, mock_loader_class, mock_content_types):
        """Test that content types are returned in consistent order."""
        mock_loader = Mock()
        mock_loader.list_content_types.return_value = mock_content_types
        mock_loader_class.return_value = mock_loader
        
        result1 = await handle_list({"action": "list"})
        result2 = await handle_list({"action": "list"})
        
        # Order should be consistent across calls
        types1 = [t["id"] for t in result1["data"]["types"]]
        types2 = [t["id"] for t in result2["data"]["types"]]
        assert types1 == types2
