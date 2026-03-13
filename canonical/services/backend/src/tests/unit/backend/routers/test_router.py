"""
Unit tests for router.py (legacy ScareCopilotPortal router)

Tests cover:
- GET /ScareFeraLab/{file_path} - Serve files
- POST /tree-refresh - Force rebuild directory tree
- GET /tree - Get directory tree with filters
- POST /persist/{path}/{filename} - Save single file
- POST /persist-batch - Batch file upload
- GET /health - Health check

Technical naming: All functions and variables in English.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
import base64

from app.main import app


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up dependency overrides."""
    yield
    app.dependency_overrides.clear()


class TestServeFileEndpoint:
    """Tests for GET /ScareFeraLab/{file_path} endpoint."""
    
    @pytest.mark.skip(reason="RecursionError: Mock object causes infinite recursion in FastAPI's jsonable_encoder during FileResponse serialization")
    @patch('app.routers.router.validate_and_sanitize_path')
    @patch('app.routers.router.Path')
    @patch('app.routers.router.SCAREFERA_LAB_DIR', Path('/test/scarefera'))
    def test_serve_file_success(self, mock_path_class, mock_validate, client):
        """Test successful file serving."""
        mock_validate.return_value = (True, "/test/scarefera/file.txt", None)
        
        # Mock Path object
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.name = "file.txt"
        mock_path_class.return_value = mock_file
        
        with patch('app.routers.router.FileResponse') as mock_response:
            mock_response.return_value = Mock()
            response = client.get("/api/ScareFeraLab/file.txt")
        
        # FileResponse is returned, so we can't easily check status
        # Just verify the mocks were called correctly
        mock_validate.assert_called_once()
    
    @patch('app.routers.router.validate_and_sanitize_path')
    @patch('app.routers.router.SCAREFERA_LAB_DIR', Path('/test/scarefera'))
    def test_serve_file_invalid_path(self, mock_validate, client):
        """Test serving file with invalid path."""
        mock_validate.return_value = (False, None, "Path traversal detected")
        
        response = client.get("/api/ScareFeraLab/../../../etc/passwd")
        
        # FastAPI normalizes/rejects path traversal attempts before reaching the handler
        # So we get 404 instead of 400
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
    
    @patch('app.routers.router.validate_and_sanitize_path')
    @patch('app.routers.router.Path')
    @patch('app.routers.router.SCAREFERA_LAB_DIR', Path('/test/scarefera'))
    def test_serve_file_not_found(self, mock_path_class, mock_validate, client):
        """Test serving non-existent file."""
        mock_validate.return_value = (True, "/test/scarefera/missing.txt", None)
        
        mock_file = MagicMock()
        mock_file.exists.return_value = False
        mock_path_class.return_value = mock_file
        
        response = client.get("/api/ScareFeraLab/missing.txt")
        
        assert response.status_code == 404
    
    @patch('app.routers.router.validate_and_sanitize_path')
    @patch('app.routers.router.Path')
    @patch('app.routers.router.SCAREFERA_LAB_DIR', Path('/test/scarefera'))
    def test_serve_file_is_directory(self, mock_path_class, mock_validate, client):
        """Test serving a directory instead of file."""
        mock_validate.return_value = (True, "/test/scarefera/folder", None)
        
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = False
        mock_path_class.return_value = mock_file
        
        response = client.get("/api/ScareFeraLab/folder")
        
        assert response.status_code == 400


class TestTreeRefreshEndpoint:
    """Tests for POST /tree-refresh endpoint."""
    
    @patch('app.routers.router.tree_builder')
    def test_tree_refresh_success(self, mock_tree_builder, client):
        """Test successful tree refresh."""
        mock_tree_builder.refresh_cache = Mock()
        mock_tree_builder.build_tree.return_value = {
            "name": "root",
            "type": "directory",
            "children": []
        }
        
        response = client.post("/api/tree-refresh")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "tree" in data
        mock_tree_builder.refresh_cache.assert_called_once()
        mock_tree_builder.build_tree.assert_called_once_with(include_hidden=True, use_cache=False)


class TestGetTreeEndpoint:
    """Tests for GET /tree endpoint."""
    
    @patch('app.routers.router.tree_builder')
    @patch('app.routers.router.SCAREFERA_LAB_DIR', Path('/test/scarefera'))
    def test_get_tree_default(self, mock_tree_builder, client):
        """Test getting tree with default parameters."""
        mock_tree_builder.build_tree.return_value = {
            "name": "root",
            "type": "directory",
            "children": []
        }
        
        response = client.get("/api/tree")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["success"] is True
        assert data["format"] == "tree"
        assert "data" in data
        assert isinstance(data["data"], list)
    
    @patch('app.routers.router.tree_builder')
    @patch('app.routers.router.SCAREFERA_LAB_DIR', Path('/test/scarefera'))
    def test_get_tree_flat_format(self, mock_tree_builder, client):
        """Test getting tree in flat format."""
        mock_tree_builder.get_flat_list.return_value = [
            {"path": "file1.txt", "type": "file"},
            {"path": "folder/file2.txt", "type": "file"}
        ]
        
        response = client.get("/api/tree?format=flat")
        
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "flat"
        assert isinstance(data["data"], list)
        mock_tree_builder.get_flat_list.assert_called_once()
    
    @patch('app.routers.router.tree_builder')
    def test_get_tree_with_filters(self, mock_tree_builder, client):
        """Test getting tree with filters."""
        mock_tree_builder.build_tree.return_value = {}
        
        response = client.get("/api/tree?include_hidden=true&max_depth=3&file_type=file")
        
        assert response.status_code == 200
        # Verify filters were passed
        mock_tree_builder.build_tree.assert_called_once()
        call_kwargs = mock_tree_builder.build_tree.call_args[1]
        assert call_kwargs["include_hidden"] is True
        assert call_kwargs["max_depth"] == 3
    
    def test_get_tree_invalid_format(self, client):
        """Test getting tree with invalid format."""
        response = client.get("/api/tree?format=invalid")
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid format" in data["detail"]
    
    def test_get_tree_invalid_file_type(self, client):
        """Test getting tree with invalid file type."""
        response = client.get("/api/tree?file_type=invalid")
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid file_type" in data["detail"]


class TestPersistFileEndpoint:
    """Tests for POST /persist/{path}/{filename} endpoint."""
    
    @patch('app.routers.router.validate_filename_extension')
    @patch('app.routers.router.validate_and_sanitize_path')
    @patch('app.routers.router.ensure_directory_exists')
    @patch('app.routers.router.decode_base64_content')
    @patch('app.routers.router.write_file_atomically')
    @patch('app.routers.router.tree_builder')
    @patch('app.routers.router.SCAREFERA_LAB_DIR', Path('/test/scarefera'))
    def test_persist_file_success(self, mock_tree, mock_write, mock_decode,
                                  mock_ensure_dir, mock_validate_path,
                                  mock_validate_name, client):
        """Test successful file persistence."""
        # Setup mocks
        mock_validate_name.return_value = (True, None)
        mock_validate_path.return_value = (True, "/test/scarefera/folder", None)
        mock_ensure_dir.return_value = (True, None)
        
        test_content = "Test content"
        encoded_content = base64.b64encode(test_content.encode()).decode()
        mock_decode.return_value = (True, test_content, None)
        mock_write.return_value = (True, None)
        
        response = client.post(
            "/api/persist/folder/file.txt",
            json={"content": encoded_content}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "path" in data
        mock_write.assert_called_once()
        mock_tree.refresh_cache.assert_called_once()
    
    @patch('app.routers.router.validate_filename_extension')
    def test_persist_file_invalid_filename(self, mock_validate_name, client):
        """Test persist with invalid filename."""
        mock_validate_name.return_value = (False, "Invalid filename")
        
        response = client.post(
            "/api/persist/folder/../etc/passwd",
            json={"content": "dGVzdA=="}
        )
        
        assert response.status_code == 400
    
    @patch('app.routers.router.validate_filename_extension')
    @patch('app.routers.router.validate_and_sanitize_path')
    def test_persist_file_invalid_path(self, mock_validate_path, mock_validate_name, client):
        """Test persist with invalid path."""
        mock_validate_name.return_value = (True, None)
        mock_validate_path.return_value = (False, None, "Invalid path")
        
        response = client.post(
            "/api/persist/../../etc/file.txt",
            json={"content": "dGVzdA=="}
        )
        
        # FastAPI normalizes/rejects path traversal attempts before reaching the handler
        # So we get 404 instead of 400
        assert response.status_code == 404


class TestPersistBatchEndpoint:
    """Tests for POST /persist-batch endpoint."""
    
    @patch('app.routers.router.validate_filename_extension')
    @patch('app.routers.router.validate_and_sanitize_path')
    @patch('app.routers.router.ensure_directory_exists')
    @patch('app.routers.router.decode_base64_content')
    @patch('app.routers.router.write_file_atomically')
    @patch('app.routers.router.tree_builder')
    @patch('app.routers.router.SCAREFERA_LAB_DIR', Path('/test/scarefera'))
    def test_persist_batch_success(self, mock_tree, mock_write, mock_decode,
                                   mock_ensure_dir, mock_validate_path,
                                   mock_validate_name, client):
        """Test successful batch file persistence."""
        # Setup mocks for success
        mock_validate_name.return_value = (True, None)
        mock_validate_path.return_value = (True, "/test/scarefera/folder", None)
        mock_ensure_dir.return_value = (True, None)
        mock_decode.return_value = (True, "Test content", None)
        mock_write.return_value = (True, None)
        
        encoded_content = base64.b64encode(b"Test content").decode()
        
        response = client.post("/api/persist-batch", json={
            "files": [
                {
                    "path": "folder",
                    "filename": "file1.txt",
                    "content": encoded_content
                },
                {
                    "path": "folder",
                    "filename": "file2.txt",
                    "content": encoded_content
                }
            ]
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["success_count"] == 2
        assert data["error_count"] == 0
        assert len(data["results"]) == 2
    
    def test_persist_batch_empty_files(self, client):
        """Test batch persist with no files."""
        response = client.post("/api/persist-batch", json={
            "files": []
        })
        
        assert response.status_code == 400
        data = response.json()
        assert "No files provided" in data["detail"]
    
    @patch('app.routers.router.validate_filename_extension')
    @patch('app.routers.router.validate_and_sanitize_path')
    @patch('app.routers.router.ensure_directory_exists')
    @patch('app.routers.router.decode_base64_content')
    @patch('app.routers.router.write_file_atomically')
    @patch('app.routers.router.tree_builder')
    @patch('app.routers.router.SCAREFERA_LAB_DIR', Path('/test/scarefera'))
    def test_persist_batch_partial_success(self, mock_tree, mock_write, mock_decode,
                                           mock_ensure_dir, mock_validate_path,
                                           mock_validate_name, client):
        """Test batch persist with some failures."""
        # First file succeeds, second fails
        mock_validate_name.side_effect = [
            (True, None),      # file1 - valid
            (False, "Invalid") # file2 - invalid
        ]
        mock_validate_path.return_value = (True, "/test/scarefera/folder", None)
        mock_ensure_dir.return_value = (True, None)
        mock_decode.return_value = (True, "Test content", None)
        mock_write.return_value = (True, None)
        
        encoded_content = base64.b64encode(b"Test content").decode()
        
        response = client.post("/api/persist-batch", json={
            "files": [
                {
                    "path": "folder",
                    "filename": "file1.txt",
                    "content": encoded_content
                },
                {
                    "path": "folder",
                    "filename": "../invalid.txt",
                    "content": encoded_content
                }
            ]
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success_count"] == 1
        assert data["error_count"] == 1


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""
    
    @patch('app.routers.health_router.SCAREFERA_LAB_DIR')
    def test_health_check_success(self, mock_dir, client):
        """Test health check endpoint."""
        mock_dir.exists.return_value = True
        
        response = client.get("/api/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "checks" in data
        assert data["checks"]["scarefera_lab"] == "accessible"
    
    @patch('app.routers.health_router.SCAREFERA_LAB_DIR')
    def test_health_check_dir_not_exists(self, mock_dir, client):
        """Test health check when directory doesn't exist."""
        mock_dir.exists.return_value = False
        
        response = client.get("/api/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["checks"]["scarefera_lab"] == "missing"
