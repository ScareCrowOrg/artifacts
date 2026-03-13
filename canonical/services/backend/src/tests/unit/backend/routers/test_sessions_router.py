"""
DEPRECATED: These tests are for the old ScareRunner sessions router.
Session management has been migrated to CentralHub.

See: centralhub/tests/routers/test_sessions_router.py for the new tests.

Tests previously covered:
- POST /sessions/create - Create session (NOW IN CENTRALHUB)
- GET /sessions/user/{user_id} - List user sessions (NOW IN CENTRALHUB)
- POST /sessions/{session_id}/close - Close session (NOW IN CENTRALHUB)

Phase: Session Centralization Epic
Migration Date: 2026-02-28

Technical naming: All functions and variables in English.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from app.main import app
from app.models import User, Session
from app.auth import get_current_user_required


@pytest.fixture
def client():
    """Test client."""
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
    """Clean up dependency overrides."""
    yield
    app.dependency_overrides.clear()


class TestCriarSession:
    """Tests for POST /sessions/create endpoint."""
    
    @patch('app.routers.sessions_router.create_access_token')
    @patch('app.routers.sessions_router.db')
    def test_criar_sessao_success(self, mock_db, mock_create_token, client):
        """Test successful session creation."""
        # Create a real User object (not mock) so it can serialize
        from app.models import User as RealUser
        real_usuario = RealUser(
            id="user-123",
            name="Test User",
            email="test@example.com",
            galaxy="TestGalaxy"
        )
        # Make find_one return an awaitable
        mock_db.find_one = AsyncMock(return_value=real_usuario)
        
        # Mock token creation
        mock_create_token.return_value = "test-jwt-token"
        
        # Mock insert as async
        mock_db.insert = AsyncMock(return_value="session-id")
        
        response = client.post(
            "/api/sessions/create",
            json={"user_id": "user-123"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "session" in data
        assert "token" in data
        assert "user" in data
        assert data["token"] == "test-jwt-token"
        assert data["user"]["id"] == "user-123"
    
    @patch('app.routers.sessions_router.db')
    def test_criar_sessao_user_not_found(self, mock_db, client):
        """Test 404 when user not found."""
        mock_db.find_one = AsyncMock(return_value=None)
        
        response = client.post(
            "/api/sessions/create",
            json={"user_id": "nonexistent"}
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    @patch('app.routers.sessions_router.db')
    def test_criar_sessao_database_error(self, mock_db, client):
        """Test error handling."""
        mock_db.find_one = AsyncMock(side_effect=Exception("DB error"))
        
        response = client.post(
            "/api/sessions/create",
            json={"user_id": "user-123"}
        )
        
        assert response.status_code == 500
        assert "Error creating session" in response.json()["detail"]


class TestListarSessoesUser:
    """Tests for GET /sessions/user/{usuario_id} endpoint."""
    
    @patch('app.routers.sessions_router.db')
    def test_listar_sessoes_success(self, mock_db, client, mock_user):
        """Test successful session listing."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Mock sessions
        mock_session1 = Mock(spec=Session)
        mock_session1.id = "session-1"
        mock_session1.user_id = "user-123"
        mock_session1.model_dump.return_value = {"id": "session-1", "user_id": "user-123"}
        
        mock_session2 = Mock(spec=Session)
        mock_session2.id = "session-2"
        mock_session2.user_id = "user-123"
        mock_session2.model_dump.return_value = {"id": "session-2", "user_id": "user-123"}
        
        mock_session3 = Mock(spec=Session)
        mock_session3.id = "session-3"
        mock_session3.user_id = "other-user"
        mock_session3.model_dump.return_value = {"id": "session-3", "user_id": "other-user"}
        
        mock_db.find_many = AsyncMock(return_value=[mock_session1, mock_session2, mock_session3])
        
        response = client.get("/api/sessions/user/user-123")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2  # Only user-123's sessions
        assert all(s["user_id"] == "user-123" for s in data)
    
    @patch('app.routers.sessions_router.db')
    def test_listar_sessoes_empty(self, mock_db, client, mock_user):
        """Test empty session list."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[])
        
        response = client.get("/api/sessions/user/user-123")
        
        assert response.status_code == 200
        assert len(response.json()) == 0
    
    @patch('app.routers.sessions_router.db')
    def test_listar_sessoes_database_error(self, mock_db, client, mock_user):
        """Test error handling."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(side_effect=Exception("DB error"))
        
        response = client.get("/api/sessions/user/user-123")
        
        assert response.status_code == 500
        assert "Error listing sessions" in response.json()["detail"]


class TestFecharSession:
    """Tests for POST /sessions/{sessao_id}/fechar endpoint."""
    
    @patch('app.routers.sessions_router.db')
    def test_fechar_sessao_success(self, mock_db, client, mock_user):
        """Test successful session closure."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Mock session exists
        mock_session = Mock(spec=Session)
        mock_session.id = "session-123"
        mock_db.find_one = AsyncMock(return_value=mock_session)
        
        # Mock update success
        mock_db.update = AsyncMock(return_value=True)
        
        response = client.post("/api/sessions/session-123/close")
        
        assert response.status_code == 200
        data = response.json()
        assert data["sessionId"] == "session-123"
        assert "closed successfully" in data["message"]
    
    @patch('app.routers.sessions_router.db')
    def test_fechar_sessao_not_found(self, mock_db, client, mock_user):
        """Test 404 when session not found."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(return_value=None)
        
        response = client.post("/api/sessions/nonexistent/close")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    @patch('app.routers.sessions_router.db')
    def test_fechar_sessao_update_failure(self, mock_db, client, mock_user):
        """Test error when update fails."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_session = Mock(spec=Session)
        mock_db.find_one = AsyncMock(return_value=mock_session)
        mock_db.update = AsyncMock(return_value=False)  # Update failed
        
        response = client.post("/api/sessions/session-123/close")
        
        assert response.status_code == 500
        assert "Failed to close" in response.json()["detail"]
    
    @patch('app.routers.sessions_router.db')
    def test_fechar_sessao_database_error(self, mock_db, client, mock_user):
        """Test error handling."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(side_effect=Exception("DB error"))
        
        response = client.post("/api/sessions/session-123/close")
        
        assert response.status_code == 500
        assert "Error closing" in response.json()["detail"]
