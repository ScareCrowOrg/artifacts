"""
Tests for content-explorer-cell backend.

Tests the composition of ContentTypeManagerCell and ContentManagerCell.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Import the module to test
import sys
from pathlib import Path
backend_path = Path(__file__).resolve().parents[7] / "backend"
sys.path.insert(0, str(backend_path))

# Import the main module
scripts_path = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(scripts_path))

from main import execute_cell, handle_list


@pytest.fixture
def mock_content_type():
    """Mock ContentType object."""
    mock_ct = MagicMock()
    mock_ct.id = "image-png"
    mock_ct.name = "PNG Image"
    mock_ct.description = "PNG image files"
    mock_ct.mime_type = "image/png"
    mock_ct.version = "1.0.0"
    mock_ct.max_size_bytes = 10485760
    mock_ct.allowed_extensions = [".png"]
    mock_ct.render_hints = {"preview": "image"}
    return mock_ct


@pytest.fixture
def mock_content():
    """Mock Content object."""
    mock_c = MagicMock()
    mock_c.id = "content-123"
    mock_c.content_type_id = "image-png"
    mock_c.filename = "test.png"
    mock_c.size_bytes = 1024
    mock_c.created_at = datetime(2024, 1, 1, 12, 0, 0)
    mock_c.fragments = {}
    mock_c.data_ref = "r2://test.png"
    mock_c.tags = ["test"]
    mock_c.version = 1
    mock_c.is_latest = True
    mock_c.assignee_id = "user-123"
    mock_c.origin_cell_id = None
    return mock_c


@pytest.mark.asyncio
async def test_execute_cell_list_action(mock_content_type):
    """Test execute_cell with list action."""
    with patch("main.ContentTypeLoader") as mock_loader_class, \
         patch("main.ContentManager") as mock_manager_class:
        
        # Setup mocks
        mock_loader = MagicMock()
        mock_loader.list_content_types.return_value = [mock_content_type]
        mock_loader_class.return_value = mock_loader
        
        mock_manager = MagicMock()
        mock_manager.query_contents.return_value = []
        mock_manager_class.return_value = mock_manager
        
        # Execute
        result = await execute_cell({"action": "list"})
        
        # Assert
        assert result["success"] is True
        assert "output" in result
        assert "types" in result["output"]
        assert result["output"]["types"]["total"] == 1
        assert result["output"]["types"]["types"][0]["id"] == "image-png"


@pytest.mark.asyncio
async def test_execute_cell_unknown_action():
    """Test execute_cell with unknown action."""
    result = await execute_cell({"action": "invalid"})
    
    assert result["success"] is False
    assert "error" in result
    assert "Unknown action" in result["error"]


@pytest.mark.asyncio
async def test_handle_list_types_only(mock_content_type):
    """Test handle_list without selected_type_id (types only)."""
    with patch("main.ContentTypeLoader") as mock_loader_class:
        # Setup mock
        mock_loader = MagicMock()
        mock_loader.list_content_types.return_value = [mock_content_type]
        mock_loader_class.return_value = mock_loader
        
        # Execute
        result = await handle_list({})
        
        # Assert
        assert result["success"] is True
        assert result["output"]["types"]["total"] == 1
        assert result["output"]["assets"] is None
        assert result["output"]["selected_type_id"] is None


@pytest.mark.asyncio
async def test_handle_list_with_selected_type(mock_content_type, mock_content):
    """Test handle_list with selected_type_id (types + assets)."""
    with patch("main.ContentTypeLoader") as mock_loader_class, \
         patch("main.ContentManager") as mock_manager_class:
        
        # Setup mocks
        mock_loader = MagicMock()
        mock_loader.list_content_types.return_value = [mock_content_type]
        mock_loader_class.return_value = mock_loader
        
        mock_manager = MagicMock()
        mock_manager.query_contents.return_value = [mock_content]
        mock_manager_class.return_value = mock_manager
        
        # Execute
        result = await handle_list({
            "selected_type_id": "image-png",
            "limit": 10,
            "offset": 0,
            "filters": {
                "assignee_id": "user-123"
            }
        })
        
        # Assert
        assert result["success"] is True
        assert result["output"]["selected_type_id"] == "image-png"
        assert result["output"]["assets"] is not None
        assert result["output"]["assets"]["total"] == 1
        assert result["output"]["assets"]["items"][0]["id"] == "content-123"
        
        # Verify ContentManager was called with correct filters
        mock_manager.query_contents.assert_called_once()


@pytest.mark.asyncio
async def test_handle_list_invalid_limit(mock_content_type):
    """Test handle_list with invalid limit."""
    with patch("main.ContentTypeLoader") as mock_loader_class:
        mock_loader = MagicMock()
        mock_loader.list_content_types.return_value = [mock_content_type]
        mock_loader_class.return_value = mock_loader
        
        result = await handle_list({
            "selected_type_id": "image-png",
            "limit": 200
        })
        
        assert result["success"] is False
        assert "Invalid limit" in result["error"]


@pytest.mark.asyncio
async def test_handle_list_invalid_offset(mock_content_type):
    """Test handle_list with invalid offset."""
    with patch("main.ContentTypeLoader") as mock_loader_class:
        mock_loader = MagicMock()
        mock_loader.list_content_types.return_value = [mock_content_type]
        mock_loader_class.return_value = mock_loader
        
        result = await handle_list({
            "selected_type_id": "image-png",
            "offset": -1
        })
        
        assert result["success"] is False
        assert "Invalid offset" in result["error"]


@pytest.mark.asyncio
async def test_handle_list_exception():
    """Test handle_list handles exceptions gracefully."""
    with patch("main.ContentTypeLoader") as mock_loader_class:
        mock_loader_class.side_effect = Exception("Test error")
        
        result = await handle_list({})
        
        assert result["success"] is False
        assert "error" in result
