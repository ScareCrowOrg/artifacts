"""
Integration tests for search endpoints (grep and find).

Tests the /api/search/grep and /api/search/find endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path


@pytest.fixture
def client():
    """Create test client with mocked authentication."""
    from app.main import app
    from app.auth import get_current_user_required
    from app.models import User
    
    # Mock authenticated user
    def override_get_current_user():
        return User(
            id="test-user-123",
            email="test@example.com",
            name="Test User",
            assignee_id="test-assignee"
        )
    
    app.dependency_overrides[get_current_user_required] = override_get_current_user
    return TestClient(app)


class TestGrepEndpoint:
    """Tests for /api/search/grep endpoint."""
    
    def test_grep_basic_search(self, client):
        """Test basic grep search."""
        response = client.get(
            "/api/search/grep",
            params={
                "pattern": "def",
                "path": "backend/app/routers",
                "file_pattern": "*.py"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "matches" in data
        assert "count" in data
        assert "pattern" in data
        assert data["pattern"] == "def"
    
    def test_grep_case_sensitive(self, client):
        """Test case sensitive search."""
        response = client.get(
            "/api/search/grep",
            params={
                "pattern": "FastAPI",
                "path": "backend/app",
                "case_sensitive": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_grep_max_results(self, client):
        """Test max results limit."""
        response = client.get(
            "/api/search/grep",
            params={
                "pattern": "import",
                "path": "backend/app",
                "max_results": 5
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert len(data["matches"]) <= 5
    
    def test_grep_no_results(self, client):
        """Test search with no results."""
        response = client.get(
            "/api/search/grep",
            params={
                "pattern": "xyzzy_nonexistent_pattern_12345",
                "path": "backend/app"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["count"] == 0
        assert len(data["matches"]) == 0
    
    def test_grep_missing_pattern(self, client):
        """Test grep without pattern parameter."""
        response = client.get(
            "/api/search/grep",
            params={"path": "backend/app"}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_grep_invalid_path(self, client):
        """Test grep with invalid path (path traversal attempt)."""
        response = client.get(
            "/api/search/grep",
            params={
                "pattern": "test",
                "path": "../../../etc/passwd"  # Path traversal attempt
            }
        )
        
        # Endpoint safely handles invalid paths by returning empty results
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["count"] == 0  # No matches in invalid/nonexistent path


class TestFindEndpoint:
    """Tests for /api/search/find endpoint."""
    
    def test_find_basic_search(self, client):
        """Test basic find search."""
        response = client.get(
            "/api/search/find",
            params={
                "pattern": "*.py",
                "path": "backend/app/routers"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "matches" in data
        assert "count" in data
        assert "pattern" in data
        assert data["pattern"] == "*.py"
        assert data["count"] > 0  # Should find at least some .py files
    
    def test_find_recursive_search(self, client):
        """Test recursive find search."""
        response = client.get(
            "/api/search/find",
            params={
                "pattern": "*.md",
                "path": "docs",
                "recursive": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_find_non_recursive(self, client):
        """Test non-recursive find search."""
        response = client.get(
            "/api/search/find",
            params={
                "pattern": "*.py",
                "path": "backend/app",
                "recursive": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        # Non-recursive should find fewer or equal results
    
    def test_find_no_results(self, client):
        """Test find with no results."""
        response = client.get(
            "/api/search/find",
            params={
                "pattern": "*.xyzzy_nonexistent",
                "path": "backend/app"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["count"] == 0
        assert len(data["matches"]) == 0
    
    def test_find_missing_pattern(self, client):
        """Test find without pattern parameter (uses default '*')."""
        response = client.get(
            "/api/search/find",
            params={"path": "backend/app"}
        )
        
        # Endpoint uses default pattern, should succeed
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["count"] > 0  # Should find files with default pattern
    
    def test_find_nonexistent_path(self, client):
        """Test find with nonexistent path."""
        response = client.get(
            "/api/search/find",
            params={
                "pattern": "*.py",
                "path": "nonexistent_directory_12345"
            }
        )
        
        # Endpoint safely handles nonexistent paths by returning empty results
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["count"] == 0  # No files in nonexistent path
    
    def test_find_invalid_path(self, client):
        """Test find with invalid path (path traversal attempt)."""
        response = client.get(
            "/api/search/find",
            params={
                "pattern": "*",
                "path": "../../../etc"  # Path traversal attempt
            }
        )
        
        # Endpoint safely handles invalid paths by returning empty results
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["count"] == 0  # No files in invalid/secured path


class TestSearchResultsFormat:
    """Tests for search results format and structure."""
    
    def test_grep_result_structure(self, client):
        """Test grep result structure."""
        response = client.get(
            "/api/search/grep",
            params={
                "pattern": "router",
                "path": "backend/app/routers",
                "file_pattern": "search_router.py"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level structure
        assert "status" in data
        assert "pattern" in data
        assert "matches" in data
        assert "count" in data
        assert "truncated" in data
        
        # Check match structure (if any matches)
        if data["count"] > 0:
            match = data["matches"][0]
            assert "file" in match
            assert "line" in match
            assert "content" in match
            assert isinstance(match["line"], int)
    
    def test_find_result_structure(self, client):
        """Test find result structure."""
        response = client.get(
            "/api/search/find",
            params={
                "pattern": "search_router.py",
                "path": "backend/app/routers"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level structure
        assert "status" in data
        assert "pattern" in data
        assert "search_path" in data
        assert "matches" in data
        assert "count" in data
        
        # Check match structure (if any matches)
        if data["count"] > 0:
            match = data["matches"][0]
            assert "path" in match
            assert "name" in match
            assert "type" in match
            # Files should have size, directories may not
            if match["type"] == "file":
                assert "size" in match
