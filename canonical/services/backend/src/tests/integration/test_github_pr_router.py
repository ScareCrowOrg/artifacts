"""
Integration Tests for GitHub PR Router

These are integration tests that test the router endpoints by:
- Creating a FastAPI TestClient
- Mocking the GitHub PR service to avoid real API calls
- Testing request/response flow through the router
- Validating error handling and status codes

Tests include:
- PR report endpoint
- PR changes endpoint
- PR file diff endpoint
- PR new file content endpoint
- Error handling
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models import User
from app.auth import get_current_user_required


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Mock authenticated user with admin role."""
    user = Mock(spec=User)
    user.id = "test-user-123"
    user.name = "Test User"
    user.email = "test@example.com"
    user.roles = ["admin"]
    return user


@pytest.fixture(autouse=True)
def setup_auth(mock_user):
    """Automatically set up auth for all tests."""
    app.dependency_overrides[get_current_user_required] = lambda: mock_user
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_service():
    """Mock GitHub PR service"""
    with patch('app.routers.github_pr_router.get_github_pr_service') as mock:
        yield mock.return_value


class TestGitHubPRRouter:
    """Test suite for GitHub PR router endpoints"""
    
    def test_get_pr_report_success(self, client, mock_service):
        """Test successful PR report retrieval"""
        mock_service.get_pr_report.return_value = {
            "number": 123,
            "title": "Test PR",
            "body": "Test description",
            "state": "open",
            "merged": False,
            "created_at": "2025-12-25T10:00:00",
            "updated_at": "2025-12-25T12:00:00",
            "closed_at": None,
            "merged_at": None,
            "user": "testuser",
            "base_branch": "main",
            "head_branch": "feature",
            "commits_count": 5,
            "additions": 100,
            "deletions": 20,
            "changed_files": 5,
            "url": "https://github.com/test/repo/pull/123"
        }
        
        response = client.get(
            "/api/github/pr/report",
            params={"owner": "testowner", "repo": "testrepo", "pr_number": 123}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["number"] == 123
        assert data["title"] == "Test PR"
        assert data["state"] == "open"
        mock_service.get_pr_report.assert_called_once_with("testowner", "testrepo", 123)
    
    def test_get_pr_report_error(self, client, mock_service):
        """Test PR report retrieval with error"""
        mock_service.get_pr_report.side_effect = Exception("API Error")
        
        response = client.get(
            "/api/github/pr/report",
            params={"owner": "testowner", "repo": "testrepo", "pr_number": 123}
        )
        
        assert response.status_code == 500
        assert "Failed to retrieve PR report" in response.json()["detail"]
    
    def test_get_pr_report_missing_params(self, client):
        """Test PR report endpoint with missing parameters"""
        response = client.get("/api/github/pr/report")
        assert response.status_code == 422
    
    def test_get_pr_report_invalid_pr_number(self, client):
        """Test PR report with invalid PR number"""
        response = client.get(
            "/api/github/pr/report",
            params={"owner": "testowner", "repo": "testrepo", "pr_number": 0}
        )
        assert response.status_code == 422
    
    def test_get_pr_changes_success(self, client, mock_service):
        """Test successful PR changes retrieval"""
        mock_service.get_pr_changes.return_value = [
            {
                "filename": "file1.py",
                "status": "modified",
                "additions": 10,
                "deletions": 5,
                "changes": 15,
                "patch": "@@ -1,5 +1,10 @@"
            },
            {
                "filename": "file2.py",
                "status": "added",
                "additions": 20,
                "deletions": 0,
                "changes": 20
            }
        ]
        
        response = client.get(
            "/api/github/pr/changes",
            params={"owner": "testowner", "repo": "testrepo", "pr_number": 123}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["changes"]) == 2
        assert data["changes"][0]["filename"] == "file1.py"
        assert data["changes"][1]["status"] == "added"
        mock_service.get_pr_changes.assert_called_once_with("testowner", "testrepo", 123)
    
    def test_get_pr_changes_error(self, client, mock_service):
        """Test PR changes retrieval with error"""
        mock_service.get_pr_changes.side_effect = Exception("API Error")
        
        response = client.get(
            "/api/github/pr/changes",
            params={"owner": "testowner", "repo": "testrepo", "pr_number": 123}
        )
        
        assert response.status_code == 500
        assert "Failed to retrieve PR changes" in response.json()["detail"]
    
    def test_get_pr_file_diff_success(self, client, mock_service):
        """Test successful file diff retrieval"""
        mock_service.get_pr_file_diff.return_value = {
            "filename": "test_file.py",
            "status": "modified",
            "additions": 15,
            "deletions": 8,
            "changes": 23,
            "patch": "@@ -10,20 +10,27 @@"
        }
        
        response = client.get(
            "/api/github/pr/file-diff",
            params={
                "owner": "testowner",
                "repo": "testrepo",
                "pr_number": 123,
                "file_path": "test_file.py"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test_file.py"
        assert data["status"] == "modified"
        assert data["additions"] == 15
        mock_service.get_pr_file_diff.assert_called_once_with(
            "testowner", "testrepo", 123, "test_file.py"
        )
    
    def test_get_pr_file_diff_not_found(self, client, mock_service):
        """Test file diff when file not in PR"""
        mock_service.get_pr_file_diff.return_value = None
        
        response = client.get(
            "/api/github/pr/file-diff",
            params={
                "owner": "testowner",
                "repo": "testrepo",
                "pr_number": 123,
                "file_path": "missing_file.py"
            }
        )
        
        assert response.status_code == 404
        assert "not found in PR" in response.json()["detail"]
    
    def test_get_pr_file_diff_error(self, client, mock_service):
        """Test file diff retrieval with error"""
        mock_service.get_pr_file_diff.side_effect = Exception("API Error")
        
        response = client.get(
            "/api/github/pr/file-diff",
            params={
                "owner": "testowner",
                "repo": "testrepo",
                "pr_number": 123,
                "file_path": "test_file.py"
            }
        )
        
        assert response.status_code == 500
        assert "Failed to retrieve file diff" in response.json()["detail"]
    
    def test_get_pr_new_file_content_success(self, client, mock_service):
        """Test successful new file content retrieval"""
        mock_service.get_pr_new_file_content.return_value = {
            "filename": "new_file.py",
            "content": "# New file content\nprint('hello')",
            "encoding": "utf-8",
            "size": 100
        }
        
        response = client.get(
            "/api/github/pr/new-file-content",
            params={
                "owner": "testowner",
                "repo": "testrepo",
                "pr_number": 123,
                "file_path": "new_file.py"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "new_file.py"
        assert "New file content" in data["content"]
        assert data["encoding"] == "utf-8"
        mock_service.get_pr_new_file_content.assert_called_once_with(
            "testowner", "testrepo", 123, "new_file.py"
        )
    
    def test_get_pr_new_file_content_not_added(self, client, mock_service):
        """Test new file content when file wasn't added"""
        mock_service.get_pr_new_file_content.return_value = None
        
        response = client.get(
            "/api/github/pr/new-file-content",
            params={
                "owner": "testowner",
                "repo": "testrepo",
                "pr_number": 123,
                "file_path": "existing_file.py"
            }
        )
        
        assert response.status_code == 404
        assert "was not added in PR" in response.json()["detail"]
    
    def test_get_pr_new_file_content_binary(self, client, mock_service):
        """Test new file content for binary file"""
        mock_service.get_pr_new_file_content.return_value = {
            "filename": "image.png",
            "content": None,
            "encoding": "binary",
            "size": None,
            "error": "Binary file cannot be decoded as text"
        }
        
        response = client.get(
            "/api/github/pr/new-file-content",
            params={
                "owner": "testowner",
                "repo": "testrepo",
                "pr_number": 123,
                "file_path": "image.png"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "image.png"
        assert data["content"] is None
        assert data["error"] is not None
    
    def test_get_pr_new_file_content_error(self, client, mock_service):
        """Test new file content retrieval with error"""
        mock_service.get_pr_new_file_content.side_effect = Exception("API Error")
        
        response = client.get(
            "/api/github/pr/new-file-content",
            params={
                "owner": "testowner",
                "repo": "testrepo",
                "pr_number": 123,
                "file_path": "new_file.py"
            }
        )
        
        assert response.status_code == 500
        assert "Failed to retrieve new file content" in response.json()["detail"]
