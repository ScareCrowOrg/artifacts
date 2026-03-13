"""
Integration Tests for Enhanced Search Endpoints - Issue #1433

Tests regex and wildcard support in /api/search/grep and /api/search/find endpoints.
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


class TestGrepEndpointRegex:
    """Tests for regex support in /api/search/grep endpoint."""
    
    def test_grep_regex_or_operator(self, client):
        """Test grep with regex OR operator (|)."""
        response = client.get(
            "/api/search/grep",
            params={
                "pattern": "FastAPI|APIRouter",  # Regex OR
                "path": "backend/app/routers",
                "file_pattern": "*.py"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["count"] > 0
        # Should find matches for either FastAPI or APIRouter
    
    def test_grep_regex_anchor_start(self, client):
        """Test grep with regex start anchor (^)."""
        response = client.get(
            "/api/search/grep",
            params={
                "pattern": "^import",  # Lines starting with "import"
                "path": "backend/app",
                "file_pattern": "*.py",
                "max_results": 10
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        # All matches should have content starting with "import"
        for match in data["matches"]:
            assert match["content"].strip().startswith("import")
    
    def test_grep_regex_character_class(self, client):
        """Test grep with regex character class."""
        response = client.get(
            "/api/search/grep",
            params={
                "pattern": "def [a-z_]+\\(",  # Function definitions
                "path": "backend/app/mcp/tools",
                "file_pattern": "*.py"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        # Should find function definitions
    
    def test_grep_regex_word_boundary(self, client):
        """Test grep with word boundary metacharacter."""
        response = client.get(
            "/api/search/grep",
            params={
                "pattern": "\\bclass\\b",  # Word "class" with boundaries
                "path": "backend/app",
                "file_pattern": "*.py",
                "max_results": 10
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_grep_invalid_regex(self, client):
        """Test grep with invalid regex pattern."""
        response = client.get(
            "/api/search/grep",
            params={
                "pattern": "[invalid",  # Unclosed bracket
                "path": "backend/app"
            }
        )
        
        # Should return 400 error with validation message
        assert response.status_code == 400
        data = response.json()
        assert "Invalid regex pattern" in data["detail"]
    
    def test_grep_simple_string_still_works(self, client):
        """Test that simple string patterns still work (backward compatibility)."""
        response = client.get(
            "/api/search/grep",
            params={
                "pattern": "logger",  # Simple string (no regex)
                "path": "backend/app/routers",
                "file_pattern": "*.py"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["pattern"] == "logger"


class TestGrepEndpointWildcards:
    """Tests for path wildcard support in /api/search/grep endpoint."""
    
    def test_grep_path_wildcard_star(self, client):
        """Test grep with * wildcard in path."""
        response = client.get(
            "/api/search/grep",
            params={
                "pattern": "import",
                "path": "backend/app/*/",  # Wildcard for subdirectories
                "file_pattern": "*.py",
                "max_results": 50
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        # Should find matches in multiple subdirectories of backend/app
    
    def test_grep_path_wildcard_doublestar(self, client):
        """Test grep with ** recursive wildcard in path."""
        response = client.get(
            "/api/search/grep",
            params={
                "pattern": "async def",
                "path": "**/routers",  # Any routers directory
                "file_pattern": "*.py",
                "max_results": 20
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_grep_path_wildcard_no_matches(self, client):
        """Test grep with wildcard path that matches no directories."""
        response = client.get(
            "/api/search/grep",
            params={
                "pattern": "test",
                "path": "nonexistent_*_dir"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["count"] == 0
    
    def test_grep_path_wildcard_security(self, client):
        """Test that path traversal with wildcards is blocked."""
        response = client.get(
            "/api/search/grep",
            params={
                "pattern": "test",
                "path": "../../*"  # Path traversal attempt
            }
        )
        
        # Should return 400 (security validation)
        assert response.status_code == 400


class TestGrepEndpointCombined:
    """Tests for combined regex + wildcard functionality in grep."""
    
    def test_grep_regex_and_wildcard_combined(self, client):
        """Test grep with both regex pattern and wildcard path."""
        response = client.get(
            "/api/search/grep",
            params={
                "pattern": "^class\\s+\\w+",  # Regex: class definitions
                "path": "backend/app/*",  # Wildcard path
                "file_pattern": "*.py",
                "max_results": 20
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        # Should find class definitions in multiple directories


class TestFindEndpointWildcards:
    """Tests for path wildcard support in /api/search/find endpoint."""
    
    def test_find_path_wildcard_star(self, client):
        """Test find with * wildcard in path."""
        response = client.get(
            "/api/search/find",
            params={
                "pattern": "*.py",
                "path": "backend/app/*"  # Wildcard for subdirectories
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        # Should find .py files in multiple subdirectories
        assert data["count"] > 0
    
    def test_find_path_wildcard_doublestar(self, client):
        """Test find with ** recursive wildcard in path."""
        response = client.get(
            "/api/search/find",
            params={
                "pattern": "*.md",
                "path": "**/issues"  # Any issues directory
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_find_path_wildcard_nested(self, client):
        """Test find with nested wildcard pattern."""
        response = client.get(
            "/api/search/find",
            params={
                "pattern": "*.py",
                "path": "backend/*/tools"  # Nested wildcard
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_find_path_wildcard_no_matches(self, client):
        """Test find with wildcard path that matches no directories."""
        response = client.get(
            "/api/search/find",
            params={
                "pattern": "*.py",
                "path": "nonexistent_*_dir"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["count"] == 0
    
    def test_find_path_wildcard_security(self, client):
        """Test that path traversal with wildcards is blocked."""
        response = client.get(
            "/api/search/find",
            params={
                "pattern": "*",
                "path": "../../*"  # Path traversal attempt
            }
        )
        
        # Should return 400 (security validation)
        assert response.status_code == 400
    
    def test_find_pattern_and_path_wildcards(self, client):
        """Test find with wildcards in both pattern and path."""
        response = client.get(
            "/api/search/find",
            params={
                "pattern": "test_*.py",  # Pattern with wildcard
                "path": "backend/*/tests"  # Path with wildcard
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestSearchEndpointsResultStructure:
    """Tests for result structure with enhanced features."""
    
    def test_grep_result_structure_with_regex(self, client):
        """Test grep result structure when using regex."""
        response = client.get(
            "/api/search/grep",
            params={
                "pattern": "import|from",
                "path": "backend/app/routers",
                "file_pattern": "search_router.py",
                "max_results": 5
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure is maintained
        assert "status" in data
        assert "pattern" in data
        assert "matches" in data
        assert "count" in data
        assert "truncated" in data
        
        # Pattern should be preserved as-is
        assert data["pattern"] == "import|from"
        
        # Match structure should be unchanged
        if data["count"] > 0:
            match = data["matches"][0]
            assert "file" in match
            assert "line" in match
            assert "content" in match
    
    def test_find_result_structure_with_wildcards(self, client):
        """Test find result structure when using path wildcards."""
        response = client.get(
            "/api/search/find",
            params={
                "pattern": "*.py",
                "path": "backend/app/*"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check structure is maintained
        assert "status" in data
        assert "pattern" in data
        assert "search_path" in data
        assert "matches" in data
        assert "count" in data
        
        # Path should be preserved as-is
        assert data["search_path"] == "backend/app/*"
        
        # Match structure should be unchanged
        if data["count"] > 0:
            match = data["matches"][0]
            assert "path" in match
            assert "name" in match
            assert "type" in match
