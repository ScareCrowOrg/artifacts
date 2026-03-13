"""
Unit tests for traces_router.py

Tests cover all endpoints with proper FastAPI dependency mocking:
- GET /traces/conversation/{conversation_id}
- GET /traces/recent

Technical naming: All functions and variables in English.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.main import app
from app.models import User
from app.models.content import Cell
from app.auth import get_current_user_required


# Test client setup
@pytest.fixture
def client():
    """Test client for making requests."""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    user = Mock(spec=User)
    user.id = "test-user-123"
    user.name = "Test User"
    user.email = "test@example.com"
    return user


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


class TestGetTraceByConversationId:
    """Tests for GET /traces/conversation/{conversation_id}."""
    
    @patch('app.routers.traces_router.db')
    def test_get_trace_success(self, mock_db, client, mock_user):
        """Test successful trace retrieval."""
        # Override authentication
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Create mock trace cell
        mock_trace = Mock(spec=Cell)
        mock_trace.id = "trace-123"
        mock_trace.assignee_id = "test-user-123"
        mock_trace.notebook_item_type_id = "conversation-trace-item"
        mock_trace.initial_data = {
            "conversation_id": "conv-123",
            "session_id": "sess-456",
            "user_message": "Test message",
            "target_llm": "gpt-3.5-turbo"
        }
        mock_trace.fragments = [{"stage": "test"}]
        mock_trace.createdAt = datetime(2025, 11, 18, 10, 0, 0)
        mock_trace.created_at = datetime(2025, 11, 18, 10, 0, 0)
        mock_trace.created_at = datetime(2025, 11, 18, 10, 0, 0)
        mock_trace.dataCriacao = datetime(2025, 11, 18, 10, 0, 0)
        
        mock_db.find_many = AsyncMock(return_value=[mock_trace])
        
        # Make request (with API prefix)
        response = client.get("/api/traces/conversation/conv-123")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["trace_id"] == "trace-123"
        assert data["conversation_id"] == "conv-123"
        assert data["fragments_count"] == 1
    
    @patch('app.routers.traces_router.db')
    def test_get_trace_not_found(self, mock_db, client, mock_user):
        """Test 404 when trace not found."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_db.find_many = AsyncMock(return_value=[])
        
        response = client.get("/api/traces/conversation/nonexistent")
        
        assert response.status_code == 404
        assert "No trace found" in response.json()["detail"]
    
    @patch('app.routers.traces_router.db')
    def test_get_trace_unauthorized(self, mock_db, client, mock_user):
        """Test 403 when accessing another user's trace."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Trace owned by different user
        mock_trace = Mock(spec=Cell)
        mock_trace.id = "trace-123"
        mock_trace.assignee_id = "other-user-456"  # Different user
        mock_trace.notebook_item_type_id = "conversation-trace-item"
        mock_trace.initial_data = {"conversation_id": "conv-123"}
        
        mock_db.find_many = AsyncMock(return_value=[mock_trace])
        
        response = client.get("/api/traces/conversation/conv-123")
        
        assert response.status_code == 403
        assert "Not authorized" in response.json()["detail"]
    
    @patch('app.routers.traces_router.db')
    def test_get_trace_database_error(self, mock_db, client, mock_user):
        """Test 500 on database error."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_db.find_many = AsyncMock(side_effect=Exception("DB error"))
        
        response = client.get("/api/traces/conversation/conv-123")
        
        assert response.status_code == 500
        assert "Error retrieving trace data" in response.json()["detail"]


class TestGetRecentTraces:
    """Tests for GET /traces/recent."""
    
    @patch('app.routers.traces_router.db')
    def test_get_recent_success(self, mock_db, client, mock_user):
        """Test successful retrieval of recent traces."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Create mock traces
        traces = []
        for i in range(5):
            mock_trace = Mock(spec=Cell)
            mock_trace.id = f"trace-{i}"
            mock_trace.assignee_id = "test-user-123"
            mock_trace.notebook_item_type_id = "conversation-trace-item"
            mock_trace.initial_data = {
                "conversation_id": f"conv-{i}",
                "user_message": f"Message {i}"
            }
            mock_trace.fragments = []
            mock_trace.createdAt = datetime(2025, 11, 18, 10, i, 0)
            mock_trace.created_at = datetime(2025, 11, 18, 10, i, 0)
            mock_trace.dataCriacao = datetime(2025, 11, 18, 10, i, 0)
            mock_trace.dataCriacao = datetime(2025, 11, 18, 10, i, 0)
            traces.append(mock_trace)
        
        mock_db.find_many = AsyncMock(return_value=traces)
        
        response = client.get("/api/traces/recent")
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 5
        assert len(data["traces"]) == 5
        # Most recent first
        assert data["traces"][0]["conversation_id"] == "conv-4"
    
    @patch('app.routers.traces_router.db')
    def test_get_recent_with_pagination(self, mock_db, client, mock_user):
        """Test pagination works correctly."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Create 15 traces
        traces = []
        for i in range(15):
            mock_trace = Mock(spec=Cell)
            mock_trace.id = f"trace-{i}"
            mock_trace.assignee_id = "test-user-123"
            mock_trace.notebook_item_type_id = "conversation-trace-item"
            mock_trace.initial_data = {"conversation_id": f"conv-{i}"}
            mock_trace.fragments = []
            mock_trace.createdAt = datetime(2025, 11, 18, 10, i, 0)
            mock_trace.created_at = datetime(2025, 11, 18, 10, i, 0)
            mock_trace.dataCriacao = datetime(2025, 11, 18, 10, i, 0)
            traces.append(mock_trace)
        
        mock_db.find_many = AsyncMock(return_value=traces)
        
        response = client.get("/api/traces/recent?limit=5&offset=5")
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 15  # Total
        assert data["limit"] == 5
        assert data["offset"] == 5
        assert len(data["traces"]) == 5
    
    @patch('app.routers.traces_router.db')
    def test_get_recent_filters_other_users(self, mock_db, client, mock_user):
        """Test only returns current user's traces."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Mix of users
        traces = []
        for i in range(10):
            mock_trace = Mock(spec=Cell)
            mock_trace.id = f"trace-{i}"
            mock_trace.assignee_id = "test-user-123" if i < 5 else "other-user"
            mock_trace.notebook_item_type_id = "conversation-trace-item"
            mock_trace.initial_data = {"conversation_id": f"conv-{i}"}
            mock_trace.fragments = []
            mock_trace.createdAt = datetime(2025, 11, 18, 10, i, 0)
            mock_trace.created_at = datetime(2025, 11, 18, 10, i, 0)
            mock_trace.dataCriacao = datetime(2025, 11, 18, 10, i, 0)
            traces.append(mock_trace)
        
        mock_db.find_many = AsyncMock(return_value=traces)
        
        response = client.get("/api/traces/recent")
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 5  # Only current user's
    
    @patch('app.routers.traces_router.db')
    def test_get_recent_empty(self, mock_db, client, mock_user):
        """Test empty result."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_db.find_many = AsyncMock(return_value=[])
        
        response = client.get("/api/traces/recent")
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert len(data["traces"]) == 0
    
    @patch('app.routers.traces_router.db')
    def test_get_recent_truncates_long_messages(self, mock_db, client, mock_user):
        """Test long messages are truncated."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_trace = Mock(spec=Cell)
        mock_trace.id = "trace-1"
        mock_trace.assignee_id = "test-user-123"
        mock_trace.notebook_item_type_id = "conversation-trace-item"
        mock_trace.initial_data = {
            "conversation_id": "conv-1",
            "user_message": "A" * 150  # Long message
        }
        mock_trace.fragments = []
        mock_trace.createdAt = datetime(2025, 11, 18, 10, 0, 0)
        mock_trace.created_at = datetime(2025, 11, 18, 10, 0, 0)
        mock_trace.dataCriacao = datetime(2025, 11, 18, 10, 0, 0)
        
        mock_db.find_many = AsyncMock(return_value=[mock_trace])
        
        response = client.get("/api/traces/recent")
        
        assert response.status_code == 200
        user_msg = response.json()["traces"][0]["user_message"]
        assert len(user_msg) <= 103
        assert user_msg.endswith("...")
    
    def test_get_recent_limit_validation(self, client, mock_user):
        """Test limit parameter validation."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Test exceeding max limit
        response = client.get("/api/traces/recent?limit=200")
        assert response.status_code == 422
    
    @patch('app.routers.traces_router.db')
    def test_get_recent_database_error(self, mock_db, client, mock_user):
        """Test database error handling."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_db.find_many = AsyncMock(side_effect=Exception("DB error"))
        
        response = client.get("/api/traces/recent")
        
        assert response.status_code == 500
        assert "Error retrieving recent traces" in response.json()["detail"]
