"""
Unit tests for ngrok_router.py

Tests cover:
- POST /share/start - Start ngrok tunnel and share files
- POST /share/add - Add files to active share
- POST /share/remove - Remove files from active share
- POST /share/stop - Stop ngrok tunnel
- GET /share/status - Get current share status

Technical naming: All functions and variables in English.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

from app.main import app
from app.models import User
from app.auth import get_current_user_required


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Mock authenticated user with admin role."""
    user = Mock(spec=User)
    user.id = "test-user-123"
    user.name = "Test User"
    user.email = "test@example.com"
    user.roles = ["admin"]  # Admin role required for ngrok operations
    return user


@pytest.fixture(autouse=True)
def mock_auth(mock_user):
    """Automatically mock authentication for all tests."""
    app.dependency_overrides[get_current_user_required] = lambda: mock_user
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def temp_base_path():
    """Create a temporary base path for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file
        test_file = os.path.join(tmpdir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test content")
        yield tmpdir


@pytest.fixture(autouse=True)
def reset_ngrok_state():
    """Reset ngrok state before each test."""
    from app.routers.ngrok.state import clear_shared_files, set_ngrok_active, set_ngrok_url, set_temp_dir
    
    yield
    
    # Cleanup after test
    clear_shared_files()
    set_ngrok_active(False)
    set_ngrok_url(None)
    set_temp_dir(None)


class TestShareStart:
    """Tests for POST /share/start endpoint."""
    
    @patch('app.routers.ngrok_router.start_ngrok_tunnel')
    @patch('app.routers.ngrok_router.start_http_server')
    @patch('app.routers.ngrok_router.copy_file_to_share')
    @patch('app.routers.ngrok_router.validate_and_sanitize_path')
    @patch('app.routers.ngrok_router.get_temp_share_dir')
    @patch('app.routers.ngrok_router.SCAREFERA_LAB_DIR')
    def test_start_share_success(
        self, mock_scarefera_dir, mock_temp_dir, mock_validate,
        mock_copy, mock_http_server, mock_ngrok_tunnel, client
    ):
        """Test starting file share successfully."""
        # Setup mocks
        mock_scarefera_dir.parent.parent = "/fake/base"
        mock_temp_dir.return_value = "/tmp/share"
        mock_validate.return_value = (True, "/fake/base/test.txt", None)
        mock_copy.return_value = (True, None)
        mock_http_server.return_value = (True, None)
        mock_ngrok_tunnel.return_value = (True, "https://abc123.ngrok.io", None)
        
        response = client.post("/api/share/start", json={"files": ["test.txt"]})
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["url"] == "https://abc123.ngrok.io"
        assert "test.txt" in data["shared_files"]
    
    @patch('app.routers.ngrok_router.get_ngrok_state')
    def test_start_share_already_active(self, mock_get_state, client):
        """Test starting share when already active."""
        mock_get_state.return_value = {
            "active": True,
            "url": "https://existing.ngrok.io",
            "shared_files": []
        }
        
        response = client.post("/api/share/start", json={"files": ["test.txt"]})
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "already active" in data["message"]
        assert data["url"] == "https://existing.ngrok.io"
    
    def test_start_share_no_files(self, client):
        """Test starting share with no files specified."""
        response = client.post("/api/share/start", json={"files": []})
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "No files specified" in data["message"]
    
    @patch('app.routers.ngrok_router.validate_and_sanitize_path')
    @patch('app.routers.ngrok_router.get_temp_share_dir')
    @patch('app.routers.ngrok_router.SCAREFERA_LAB_DIR')
    @patch('app.routers.ngrok_router.cleanup_share')
    def test_start_share_invalid_path(
        self, mock_cleanup, mock_scarefera_dir, mock_temp_dir,
        mock_validate, client
    ):
        """Test starting share with invalid file path."""
        mock_scarefera_dir.parent.parent = "/fake/base"
        mock_temp_dir.return_value = "/tmp/share"
        mock_validate.return_value = (False, None, "Path outside base directory")
        
        response = client.post("/api/share/start", json={"files": ["../../../etc/passwd"]})
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "No valid files to share" in data["message"]
        assert "errors" in data
        
        # Cleanup should be called
        mock_cleanup.assert_called_once()
    
    @patch('app.routers.ngrok_router.start_http_server')
    @patch('app.routers.ngrok_router.copy_file_to_share')
    @patch('app.routers.ngrok_router.validate_and_sanitize_path')
    @patch('app.routers.ngrok_router.get_temp_share_dir')
    @patch('app.routers.ngrok_router.SCAREFERA_LAB_DIR')
    @patch('app.routers.ngrok_router.cleanup_share')
    def test_start_share_http_server_failure(
        self, mock_cleanup, mock_scarefera_dir, mock_temp_dir,
        mock_validate, mock_copy, mock_http_server, client
    ):
        """Test HTTP server start failure."""
        mock_scarefera_dir.parent.parent = "/fake/base"
        mock_temp_dir.return_value = "/tmp/share"
        mock_validate.return_value = (True, "/fake/base/test.txt", None)
        mock_copy.return_value = (True, None)
        mock_http_server.return_value = (False, "Port already in use")
        
        response = client.post("/api/share/start", json={"files": ["test.txt"]})
        
        assert response.status_code == 500
        data = response.json()
        assert data["status"] == "error"
        assert "Failed to start HTTP server" in data["message"]
        
        mock_cleanup.assert_called_once()
    
    @patch('app.routers.ngrok_router.start_ngrok_tunnel')
    @patch('app.routers.ngrok_router.start_http_server')
    @patch('app.routers.ngrok_router.copy_file_to_share')
    @patch('app.routers.ngrok_router.validate_and_sanitize_path')
    @patch('app.routers.ngrok_router.get_temp_share_dir')
    @patch('app.routers.ngrok_router.SCAREFERA_LAB_DIR')
    @patch('app.routers.ngrok_router.cleanup_share')
    def test_start_share_ngrok_failure(
        self, mock_cleanup, mock_scarefera_dir, mock_temp_dir,
        mock_validate, mock_copy, mock_http_server, mock_ngrok_tunnel, client
    ):
        """Test ngrok tunnel start failure."""
        mock_scarefera_dir.parent.parent = "/fake/base"
        mock_temp_dir.return_value = "/tmp/share"
        mock_validate.return_value = (True, "/fake/base/test.txt", None)
        mock_copy.return_value = (True, None)
        mock_http_server.return_value = (True, None)
        mock_ngrok_tunnel.return_value = (False, None, "Ngrok not installed")
        
        response = client.post("/api/share/start", json={"files": ["test.txt"]})
        
        assert response.status_code == 500
        data = response.json()
        assert data["status"] == "error"
        assert "Failed to start ngrok tunnel" in data["message"]
        
        mock_cleanup.assert_called_once()


class TestShareAdd:
    """Tests for POST /share/add endpoint."""
    
    @patch('app.routers.ngrok_router.copy_file_to_share')
    @patch('app.routers.ngrok_router.validate_and_sanitize_path')
    @patch('app.routers.ngrok_router.get_ngrok_state')
    @patch('app.routers.ngrok_router.SCAREFERA_LAB_DIR')
    def test_add_files_success(
        self, mock_scarefera_dir, mock_get_state, mock_validate,
        mock_copy, client
    ):
        """Test adding files to active share."""
        mock_scarefera_dir.parent.parent = "/fake/base"
        mock_get_state.return_value = {
            "active": True,
            "url": "https://abc123.ngrok.io",
            "shared_files": ["file1.txt"]
        }
        mock_validate.return_value = (True, "/fake/base/file2.txt", None)
        mock_copy.return_value = (True, None)
        
        response = client.post("/api/share/add", json={"files": ["file2.txt"]})
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "file2.txt" in data["added"]
    
    @patch('app.routers.ngrok_router.get_ngrok_state')
    def test_add_files_no_active_share(self, mock_get_state, client):
        """Test adding files when no share is active."""
        mock_get_state.return_value = {
            "active": False,
            "url": None,
            "shared_files": []
        }
        
        response = client.post("/api/share/add", json={"files": ["test.txt"]})
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "No active share" in data["message"]
    
    @patch('app.routers.ngrok_router.get_ngrok_state')
    def test_add_files_empty_list(self, mock_get_state, client):
        """Test adding empty file list."""
        mock_get_state.return_value = {
            "active": True,
            "url": "https://abc123.ngrok.io",
            "shared_files": []
        }
        
        response = client.post("/api/share/add", json={"files": []})
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "No files specified" in data["message"]
    
    @patch('app.routers.ngrok_router.get_ngrok_state')
    @patch('app.routers.ngrok_router.SCAREFERA_LAB_DIR')
    def test_add_files_already_shared(self, mock_scarefera_dir, mock_get_state, client):
        """Test adding files that are already shared."""
        mock_scarefera_dir.parent.parent = "/fake/base"
        mock_get_state.return_value = {
            "active": True,
            "url": "https://abc123.ngrok.io",
            "shared_files": ["test.txt"]
        }
        
        response = client.post("/api/share/add", json={"files": ["test.txt"]})
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert len(data["added"]) == 0  # Already shared, not added again


class TestShareRemove:
    """Tests for POST /share/remove endpoint."""
    
    @patch('app.routers.ngrok_router.remove_file_from_share')
    @patch('app.routers.ngrok_router.get_ngrok_state')
    @patch('app.routers.ngrok_router.SCAREFERA_LAB_DIR')
    def test_remove_files_success(
        self, mock_scarefera_dir, mock_get_state, mock_remove, client
    ):
        """Test removing files from active share."""
        mock_scarefera_dir.parent.parent = "/fake/base"
        mock_get_state.return_value = {
            "active": True,
            "url": "https://abc123.ngrok.io",
            "shared_files": ["file1.txt", "file2.txt"]
        }
        mock_remove.return_value = (True, None)
        
        response = client.post("/api/share/remove", json={"files": ["file1.txt"]})
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "file1.txt" in data["removed"]
    
    @patch('app.routers.ngrok_router.get_ngrok_state')
    def test_remove_files_no_active_share(self, mock_get_state, client):
        """Test removing files when no share is active."""
        mock_get_state.return_value = {
            "active": False,
            "url": None,
            "shared_files": []
        }
        
        response = client.post("/api/share/remove", json={"files": ["test.txt"]})
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "No active share" in data["message"]
    
    @patch('app.routers.ngrok_router.get_ngrok_state')
    def test_remove_files_empty_list(self, mock_get_state, client):
        """Test removing empty file list."""
        mock_get_state.return_value = {
            "active": True,
            "url": "https://abc123.ngrok.io",
            "shared_files": ["test.txt"]
        }
        
        response = client.post("/api/share/remove", json={"files": []})
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "No files specified" in data["message"]
    
    @patch('app.routers.ngrok_router.get_ngrok_state')
    @patch('app.routers.ngrok_router.SCAREFERA_LAB_DIR')
    def test_remove_files_not_in_share(
        self, mock_scarefera_dir, mock_get_state, client
    ):
        """Test removing files that are not in the share."""
        mock_scarefera_dir.parent.parent = "/fake/base"
        mock_get_state.return_value = {
            "active": True,
            "url": "https://abc123.ngrok.io",
            "shared_files": ["file1.txt"]
        }
        
        response = client.post("/api/share/remove", json={"files": ["nonexistent.txt"]})
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert len(data["removed"]) == 0
        assert "errors" in data


class TestShareStop:
    """Tests for POST /share/stop endpoint."""
    
    @patch('app.routers.ngrok_router.cleanup_share')
    @patch('app.routers.ngrok_router.get_ngrok_state')
    def test_stop_share_success(self, mock_get_state, mock_cleanup, client):
        """Test stopping active share."""
        mock_get_state.return_value = {
            "active": True,
            "url": "https://abc123.ngrok.io",
            "shared_files": ["test.txt"]
        }
        
        response = client.post("/api/share/stop")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "stopped successfully" in data["message"]
        
        mock_cleanup.assert_called_once()
    
    @patch('app.routers.ngrok_router.get_ngrok_state')
    def test_stop_share_no_active_share(self, mock_get_state, client):
        """Test stopping when no share is active."""
        mock_get_state.return_value = {
            "active": False,
            "url": None,
            "shared_files": []
        }
        
        response = client.post("/api/share/stop")
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "No active share" in data["message"]


class TestShareStatus:
    """Tests for GET /share/status endpoint."""
    
    @patch('app.routers.ngrok_router.get_ngrok_state')
    def test_get_status_active(self, mock_get_state, client):
        """Test getting status when share is active."""
        mock_get_state.return_value = {
            "active": True,
            "url": "https://abc123.ngrok.io",
            "shared_files": ["file1.txt", "file2.txt"]
        }
        
        response = client.get("/api/share/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["active"] is True
        assert data["url"] == "https://abc123.ngrok.io"
        assert len(data["shared_files"]) == 2
    
    @patch('app.routers.ngrok_router.get_ngrok_state')
    def test_get_status_inactive(self, mock_get_state, client):
        """Test getting status when share is inactive."""
        mock_get_state.return_value = {
            "active": False,
            "url": None,
            "shared_files": []
        }
        
        response = client.get("/api/share/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["active"] is False
        assert data["url"] is None
        assert data["shared_files"] == []
