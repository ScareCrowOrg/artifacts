"""
Unit tests for proposals_router.py

Tests cover:
- POST /api/proposals/accept - Accept file proposal (create/update)
- POST /api/proposals/reject - Reject file proposal

These tests verify the file persistence functionality for Action Links.
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
import tempfile
import shutil

from app.main import app
from app.models.users import User
from app.auth import get_current_user_required


@pytest.fixture
def mock_user():
    """Mock authenticated user with admin role."""
    user = Mock(spec=User)
    user.id = "test-user-123"
    user.name = "Test User"
    user.email = "test@example.com"
    user.roles = ["admin"]  # Admin bypasses permission checks
    return user


@pytest.fixture
def client(mock_user):
    """Test client with auth override."""
    app.dependency_overrides[get_current_user_required] = lambda: mock_user
    return TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up dependency overrides."""
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def temp_base_dir():
    """Create a temporary base directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


class TestAcceptProposalEndpoint:
    """Tests for POST /api/proposals/accept endpoint."""
    
    def test_accept_create_proposal(self, client, temp_base_dir):
        """Test accepting a file creation proposal."""
        with patch('app.routers.proposals_router.BASE_DIR', temp_base_dir):
            response = client.post("/api/proposals/accept", json={
                "type": "create",
                "filePath": "test/new_file.txt",
                "content": "Hello, World!",
                "description": "Create a test file"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "created successfully" in data["message"]
            assert data["proposal_id"] is not None
            
            # Verify file was created
            created_file = temp_base_dir / "test" / "new_file.txt"
            assert created_file.exists()
            assert created_file.read_text() == "Hello, World!"
    
    def test_accept_update_proposal(self, client, temp_base_dir):
        """Test accepting a file update proposal."""
        # Create an existing file
        test_file = temp_base_dir / "existing.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("Original content")
        
        with patch('app.routers.proposals_router.BASE_DIR', temp_base_dir):
            response = client.post("/api/proposals/accept", json={
                "type": "update",
                "filePath": "existing.txt",
                "content": "Updated content",
                "originalContent": "Original content",
                "description": "Update the file"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "updated successfully" in data["message"]
            
            # Verify file was updated
            assert test_file.read_text() == "Updated content"
    
    def test_accept_create_with_nested_path(self, client, temp_base_dir):
        """Test creating a file in a nested directory that doesn't exist."""
        with patch('app.routers.proposals_router.BASE_DIR', temp_base_dir):
            response = client.post("/api/proposals/accept", json={
                "type": "create",
                "filePath": "deep/nested/path/file.txt",
                "content": "Nested file content",
                "description": "Create nested file"
            })
            
            assert response.status_code == 200
            
            # Verify directories were created
            nested_file = temp_base_dir / "deep" / "nested" / "path" / "file.txt"
            assert nested_file.exists()
            assert nested_file.read_text() == "Nested file content"
    
    def test_accept_update_nonexistent_file(self, client, temp_base_dir):
        """Test updating a file that doesn't exist."""
        with patch('app.routers.proposals_router.BASE_DIR', temp_base_dir):
            response = client.post("/api/proposals/accept", json={
                "type": "update",
                "filePath": "nonexistent.txt",
                "content": "New content",
                "originalContent": "Old content",
                "description": "Update nonexistent file"
            })
            
            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"].lower()
    
    def test_accept_missing_required_fields(self, client, temp_base_dir):
        """Test with missing required fields."""
        with patch('app.routers.proposals_router.BASE_DIR', temp_base_dir):
            # Missing content
            response = client.post("/api/proposals/accept", json={
                "type": "create",
                "filePath": "test.txt",
                "description": "Test"
            })
            
            assert response.status_code == 422  # Validation error
    
    def test_accept_update_missing_original_content(self, client, temp_base_dir):
        """Test update without originalContent."""
        with patch('app.routers.proposals_router.BASE_DIR', temp_base_dir):
            response = client.post("/api/proposals/accept", json={
                "type": "update",
                "filePath": "test.txt",
                "content": "New content",
                "description": "Update without original"
            })
            
            assert response.status_code == 400
            data = response.json()
            assert "original content is required" in data["detail"].lower()
    
    def test_accept_directory_traversal_attack(self, client, temp_base_dir):
        """Test security: prevent directory traversal attacks."""
        with patch('app.routers.proposals_router.BASE_DIR', temp_base_dir):
            response = client.post("/api/proposals/accept", json={
                "type": "create",
                "filePath": "../../../etc/passwd",
                "content": "Malicious content",
                "description": "Directory traversal attack"
            })
            
            assert response.status_code == 400
            data = response.json()
            assert "invalid file path" in data["detail"].lower()
    
    def test_accept_with_leading_slash(self, client, temp_base_dir):
        """Test that leading slashes are handled correctly."""
        with patch('app.routers.proposals_router.BASE_DIR', temp_base_dir):
            response = client.post("/api/proposals/accept", json={
                "type": "create",
                "filePath": "/test/file.txt",
                "content": "Content with leading slash",
                "description": "Test leading slash handling"
            })
            
            assert response.status_code == 200
            
            # Verify file was created in correct location
            created_file = temp_base_dir / "test" / "file.txt"
            assert created_file.exists()
            assert created_file.read_text() == "Content with leading slash"


class TestRejectProposalEndpoint:
    """Tests for POST /api/proposals/reject endpoint."""
    
    def test_reject_proposal(self, client):
        """Test rejecting a file proposal."""
        response = client.post("/api/proposals/reject", json={
            "type": "create",
            "filePath": "test.txt",
            "content": "Test content",
            "description": "Test rejection"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "rejected" in data["message"].lower()
    
    def test_reject_minimal_data(self, client):
        """Test rejecting with minimal data."""
        response = client.post("/api/proposals/reject", json={
            "type": "create",
            "filePath": "test.txt",
            "content": "x"
        })
        
        assert response.status_code == 200


class TestSnippetOperations:
    """Tests for snippet-based file updates."""
    
    def test_accept_snippet_update(self, client, temp_base_dir):
        """Test accepting a snippet update proposal."""
        # Create a file with multiple lines
        test_file = temp_base_dir / "snippet_test.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        original_content = "line 1\nline 2\nline 3\nline 4\nline 5\n"
        test_file.write_text(original_content)
        
        with patch('app.routers.proposals_router.BASE_DIR', temp_base_dir):
            response = client.post("/api/proposals/accept", json={
                "type": "update",
                "filePath": "snippet_test.py",
                "content": "modified line 2\nmodified line 3",
                "isSnippet": True,
                "startLine": 2,
                "endLine": 3,
                "description": "Update lines 2-3"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "updated successfully" in data["message"]
            
            # Verify file was updated correctly
            updated_content = test_file.read_text()
            expected = "line 1\nmodified line 2\nmodified line 3\nline 4\nline 5\n"
            assert updated_content == expected
    
    def test_accept_snippet_deletion(self, client, temp_base_dir):
        """Test accepting a snippet deletion proposal (empty content)."""
        # Create a file with multiple lines
        test_file = temp_base_dir / "snippet_delete.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        original_content = "line 1\nline 2\nline 3\nline 4\nline 5\n"
        test_file.write_text(original_content)
        
        with patch('app.routers.proposals_router.BASE_DIR', temp_base_dir):
            response = client.post("/api/proposals/accept", json={
                "type": "update",
                "filePath": "snippet_delete.py",
                "content": "",  # Empty content = deletion
                "isSnippet": True,
                "startLine": 2,
                "endLine": 4,
                "description": "Delete lines 2-4"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "updated" in data["message"]
            
            # Verify lines were deleted
            updated_content = test_file.read_text()
            expected = "line 1\nline 5\n"
            assert updated_content == expected
    
    def test_accept_snippet_deletion_single_line(self, client, temp_base_dir):
        """Test deleting a single line."""
        test_file = temp_base_dir / "single_delete.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        original_content = "line 1\nline 2\nline 3\n"
        test_file.write_text(original_content)
        
        with patch('app.routers.proposals_router.BASE_DIR', temp_base_dir):
            response = client.post("/api/proposals/accept", json={
                "type": "update",
                "filePath": "single_delete.py",
                "content": "",
                "isSnippet": True,
                "startLine": 2,
                "endLine": 2,
                "description": "Delete line 2"
            })
            
            assert response.status_code == 200
            
            # Verify single line was deleted
            updated_content = test_file.read_text()
            expected = "line 1\nline 3\n"
            assert updated_content == expected
    
    def test_accept_snippet_deletion_last_lines(self, client, temp_base_dir):
        """Test deleting the last lines of a file."""
        test_file = temp_base_dir / "delete_last.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        original_content = "line 1\nline 2\nline 3\nline 4\n"
        test_file.write_text(original_content)
        
        with patch('app.routers.proposals_router.BASE_DIR', temp_base_dir):
            response = client.post("/api/proposals/accept", json={
                "type": "update",
                "filePath": "delete_last.py",
                "content": "",
                "isSnippet": True,
                "startLine": 3,
                "endLine": 4,
                "description": "Delete last two lines"
            })
            
            assert response.status_code == 200
            
            # Verify last lines were deleted
            updated_content = test_file.read_text()
            expected = "line 1\nline 2\n"
            assert updated_content == expected
    
    def test_accept_snippet_missing_line_numbers(self, client, temp_base_dir):
        """Test snippet update without required line numbers."""
        test_file = temp_base_dir / "test.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("line 1\nline 2\n")
        
        with patch('app.routers.proposals_router.BASE_DIR', temp_base_dir):
            response = client.post("/api/proposals/accept", json={
                "type": "update",
                "filePath": "test.py",
                "content": "new content",
                "isSnippet": True,
                "description": "Missing line numbers"
            })
            
            assert response.status_code == 400
            data = response.json()
            assert "startLine and endLine are required" in data["detail"]
    
    def test_accept_snippet_invalid_line_range(self, client, temp_base_dir):
        """Test snippet with startLine > endLine."""
        test_file = temp_base_dir / "test.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("line 1\nline 2\nline 3\n")
        
        with patch('app.routers.proposals_router.BASE_DIR', temp_base_dir):
            response = client.post("/api/proposals/accept", json={
                "type": "update",
                "filePath": "test.py",
                "content": "content",
                "isSnippet": True,
                "startLine": 3,
                "endLine": 1,
                "description": "Invalid range"
            })
            
            assert response.status_code == 400
            data = response.json()
            assert "startLine must be <= endLine" in data["detail"]
    
    def test_accept_snippet_line_exceeds_file_length(self, client, temp_base_dir):
        """Test snippet with line numbers beyond file length."""
        test_file = temp_base_dir / "short.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("line 1\nline 2\n")
        
        with patch('app.routers.proposals_router.BASE_DIR', temp_base_dir):
            response = client.post("/api/proposals/accept", json={
                "type": "update",
                "filePath": "short.py",
                "content": "content",
                "isSnippet": True,
                "startLine": 1,
                "endLine": 10,
                "description": "Line exceeds length"
            })
            
            assert response.status_code == 400
            data = response.json()
            assert "exceeds file length" in data["detail"]

