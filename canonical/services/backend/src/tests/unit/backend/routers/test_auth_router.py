"""
Unit tests for auth_router.py

Tests cover:
- GET /auth/status - Check authentication status
- POST /auth/password/register - Register password for user
- POST /auth/password/login - Login with email and password
- POST /auth/refresh - Refresh JWT token

Note: Google OAuth endpoints (GET /auth/google, POST /auth/google/callback)
have been moved to CentralHub. See centralhub/tests/routers/test_auth_router.py

Technical naming: All functions and variables in English.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from app.main import app
from app.models import User, Session
from app.auth import get_current_user_required, get_current_session


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
    user.googleId = "google-123"
    user.hashedPassword = None
    user.model_dump = Mock(return_value={
        "id": "test-user-123",
        "name": "Test User",
        "email": "test@example.com"
    })
    return user


@pytest.fixture
def mock_session():
    """Mock session."""
    session = Mock(spec=Session)
    session.id = "session-123"
    session.userId = "test-user-123"
    session.user_id = "test-user-123"
    session.active = True
    session.expires_at = datetime.utcnow() + timedelta(days=7)
    session.token = "test-token-123"
    session.model_dump = Mock(return_value={
        "id": "session-123",
        "userId": "test-user-123",
        "active": True
    })
    return session


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up dependency overrides."""
    yield
    app.dependency_overrides.clear()


@pytest.mark.skip(reason="Google OAuth endpoints moved to CentralHub - see centralhub/tests/routers/test_auth_router.py")
class TestGoogleLogin:
    """Tests for GET /auth/google endpoint (MOVED TO CENTRALHUB)."""
    
    @patch.dict('os.environ', {'GOOGLE_CLIENT_ID': 'test-client-id'})
    def test_google_login_success_with_env_var(self, client):
        """Test successful Google login with env var."""
        response = client.get("/api/auth/google?redirect_uri=http://localhost:8080/callback")
        
        assert response.status_code == 200
        data = response.json()
        assert "authUrl" in data
        assert "accounts.google.com" in data["authUrl"]
        assert "test-client-id" in data["authUrl"]
        assert "redirect_uri=http" in data["authUrl"]
    
    @patch('app.routers.auth_router.db')
    def test_google_login_success_with_db_config(self, mock_db, client):
        """Test successful Google login with DB config."""
        mock_db.get_config.return_value = {"googleClientId": "db-client-id"}
        
        response = client.get("/api/auth/google?redirect_uri=http://localhost:8080/callback")
        
        assert response.status_code == 200
        data = response.json()
        assert "authUrl" in data
        assert "db-client-id" in data["authUrl"]
    
    def test_google_login_missing_redirect_uri(self, client):
        """Test Google login without redirect_uri."""
        response = client.get("/api/auth/google")
        
        assert response.status_code == 400
        assert "redirect_uri é obrigatório" in response.json()["detail"]
    
    @patch('app.routers.auth_router.db')
    def test_google_login_not_configured(self, mock_db, client):
        """Test Google login when OAuth not configured."""
        mock_db.get_config.return_value = {}
        
        response = client.get("/api/auth/google?redirect_uri=http://localhost:8080/callback")
        
        assert response.status_code == 503
        assert "não configurado" in response.json()["detail"]
    
    @patch('app.routers.auth_router.db')
    def test_google_login_error_handling(self, mock_db, client):
        """Test error handling in Google login."""
        mock_db.get_config.side_effect = Exception("DB error")
        
        response = client.get("/api/auth/google?redirect_uri=http://localhost:8080/callback")
        
        assert response.status_code == 500
        assert "Erro ao iniciar login" in response.json()["detail"]


@pytest.mark.skip(reason="Google OAuth endpoints moved to CentralHub - see centralhub/tests/routers/test_auth_router.py")
class TestGoogleCallback:
    """Tests for POST /auth/google/callback endpoint (MOVED TO CENTRALHUB)."""
    
    @patch('app.routers.auth_router.httpx.AsyncClient')
    @patch('app.routers.auth_router.db')
    @patch('app.routers.auth_router.create_access_token')
    @patch.dict('os.environ', {'GOOGLE_CLIENT_ID': 'test-id', 'GOOGLE_CLIENT_SECRET': 'test-secret'})
    async def test_google_callback_new_user(self, mock_create_token, mock_db, mock_httpx, client):
        """Test Google callback for new user."""
        # Mock HTTP client responses
        mock_client = AsyncMock()
        mock_httpx.return_value.__aenter__.return_value = mock_client
        
        # Mock token exchange
        token_response = Mock()
        token_response.status_code = 200
        token_response.json.return_value = {"access_token": "google-token"}
        mock_client.post = AsyncMock(return_value=token_response)
        
        # Mock user info
        user_response = Mock()
        user_response.status_code = 200
        user_response.json.return_value = {
            "id": "google-123",
            "email": "new@example.com",
            "name": "New User"
        }
        mock_client.get = AsyncMock(return_value=user_response)
        
        # Mock database - no existing user
        mock_db.find_by_field = AsyncMock(return_value=None)
        mock_db.insert = AsyncMock(return_value=None)
        mock_create_token.return_value = "jwt-token-123"
        
        response = client.post("/api/auth/google/callback", json={
            "code": "auth-code",
            "redirect_uri": "http://localhost:8080/callback"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert "session" in data
    
    def test_google_callback_missing_code(self, client):
        """Test callback without code."""
        response = client.post("/api/auth/google/callback", json={
            "redirect_uri": "http://localhost:8080/callback"
        })
        
        assert response.status_code == 400
        assert "obrigatórios" in response.json()["detail"]
    
    def test_google_callback_missing_redirect_uri(self, client):
        """Test callback without redirect_uri."""
        response = client.post("/api/auth/google/callback", json={
            "code": "auth-code"
        })
        
        assert response.status_code == 400
        assert "obrigatórios" in response.json()["detail"]
    
    @patch('app.routers.auth_router.db')
    def test_google_callback_not_configured(self, mock_db, client):
        """Test callback when OAuth not configured."""
        mock_db.get_config.return_value = {}
        
        response = client.post("/api/auth/google/callback", json={
            "code": "auth-code",
            "redirect_uri": "http://localhost:8080/callback"
        })
        
        assert response.status_code == 503
        assert "não configurado" in response.json()["detail"]
    
    @patch('app.routers.auth_router.httpx.AsyncClient')
    @patch.dict('os.environ', {'GOOGLE_CLIENT_ID': 'test-id', 'GOOGLE_CLIENT_SECRET': 'test-secret'})
    async def test_google_callback_token_exchange_failed(self, mock_httpx, client):
        """Test callback when token exchange fails."""
        mock_client = AsyncMock()
        mock_httpx.return_value.__aenter__.return_value = mock_client
        
        token_response = Mock()
        token_response.status_code = 400
        token_response.text = "Invalid code"
        mock_client.post = AsyncMock(return_value=token_response)
        
        response = client.post("/api/auth/google/callback", json={
            "code": "invalid-code",
            "redirect_uri": "http://localhost:8080/callback"
        })
        
        assert response.status_code == 401
        assert "Falha ao obter token" in response.json()["detail"]
    
    @patch('app.routers.auth_router.httpx.AsyncClient')
    @patch.dict('os.environ', {'GOOGLE_CLIENT_ID': 'test-id', 'GOOGLE_CLIENT_SECRET': 'test-secret'})
    async def test_google_callback_user_info_failed(self, mock_httpx, client):
        """Test callback when user info request fails."""
        mock_client = AsyncMock()
        mock_httpx.return_value.__aenter__.return_value = mock_client
        
        # Mock token exchange success
        token_response = Mock()
        token_response.status_code = 200
        token_response.json.return_value = {"access_token": "google-token"}
        mock_client.post = AsyncMock(return_value=token_response)
        
        # Mock user info failure
        user_response = Mock()
        user_response.status_code = 401
        user_response.text = "Invalid token"
        mock_client.get = AsyncMock(return_value=user_response)
        
        response = client.post("/api/auth/google/callback", json={
            "code": "auth-code",
            "redirect_uri": "http://localhost:8080/callback"
        })
        
        assert response.status_code == 401
        assert "Falha ao obter informações" in response.json()["detail"]


class TestAuthStatus:
    """Tests for GET /auth/status endpoint (now proxies to CentralHub)."""
    
    @patch('httpx.AsyncClient')
    @patch.dict('os.environ', {'CENTRALHUB_URL': 'http://localhost:5051'})
    async def test_auth_status_from_centralhub(self, mock_httpx_client, client):
        """Test auth status proxies to CentralHub."""
        # Mock CentralHub response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "authEnabled": True,
            "configured": True,
            "googleClientId": "test-client-id"
        }
        
        mock_http_client = AsyncMock()
        mock_http_client.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_httpx_client.return_value = mock_http_client
        
        response = client.get("/api/auth/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["authEnabled"] is True
        assert data["configured"] is True
    
    @patch('httpx.AsyncClient')
    @patch.dict('os.environ', {
        'CENTRALHUB_URL': 'http://localhost:5051',
        'GOOGLE_CLIENT_ID': 'fallback-client-id',
        'GOOGLE_CLIENT_SECRET': 'fallback-secret'
    })
    async def test_auth_status_fallback_to_env(self, mock_httpx_client, client):
        """Test auth status falls back to env vars when CentralHub unavailable."""
        # Mock CentralHub failure
        mock_http_client = AsyncMock()
        mock_http_client.__aenter__.return_value.get = AsyncMock(side_effect=Exception("Connection failed"))
        mock_httpx_client.return_value = mock_http_client
        
        response = client.get("/api/auth/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["authEnabled"] is True
        assert data["configured"] is True
        assert data.get("source") == "env_fallback"


class TestPasswordRegister:
    """Tests for POST /auth/password/register endpoint."""
    
    @patch('app.routers.auth_router.db')
    @patch('app.routers.auth_router.hash_password')
    def test_password_register_success(self, mock_hash, mock_db, client, mock_user):
        """Test successful password registration."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_hash.return_value = "hashed-password"
        mock_db.update = AsyncMock(return_value=True)
        
        response = client.post("/api/auth/password/register", json={
            "password": "secure-password-123"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Senha cadastrada com sucesso"
        assert data["email"] == mock_user.email
    
    def test_password_register_unauthenticated(self, client):
        """Test password register without authentication."""
        response = client.post("/api/auth/password/register", json={
            "password": "secure-password-123"
        })
        
        assert response.status_code == 401
    
    @patch('app.routers.auth_router.db')
    @patch('app.routers.auth_router.hash_password')
    def test_password_register_db_failure(self, mock_hash, mock_db, client, mock_user):
        """Test password register when DB update fails."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_hash.return_value = "hashed-password"
        mock_db.update = AsyncMock(return_value=False)
        
        response = client.post("/api/auth/password/register", json={
            "password": "secure-password-123"
        })
        
        assert response.status_code == 500
        assert "Falha ao salvar senha" in response.json()["detail"]
    
    @patch('app.routers.auth_router.db')
    @patch('app.routers.auth_router.hash_password')
    def test_password_register_error_handling(self, mock_hash, mock_db, client, mock_user):
        """Test error handling in password register."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_hash.side_effect = Exception("Hashing error")
        
        response = client.post("/api/auth/password/register", json={
            "password": "secure-password-123"
        })
        
        assert response.status_code == 500
        assert "Erro ao cadastrar senha" in response.json()["detail"]


class TestPasswordLogin:
    """Tests for POST /auth/password/login endpoint."""
    
    @patch('app.routers.auth_router.db')
    @patch('app.routers.auth_router.verify_password')
    @patch('app.routers.auth_router.create_access_token')
    def test_password_login_success(self, mock_create_token, mock_verify, mock_db, client, mock_user):
        """Test successful password login."""
        mock_user.hashedPassword = "hashed-password"
        mock_db.find_by_field = AsyncMock(return_value=mock_user)
        mock_verify.return_value = True
        mock_create_token.return_value = "jwt-token-123"
        mock_db.insert = AsyncMock(return_value=None)
        
        response = client.post("/api/auth/password/login", json={
            "email": "test@example.com",
            "password": "correct-password"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert "session" in data
    
    @patch('app.routers.auth_router.db')
    def test_password_login_user_not_found(self, mock_db, client):
        """Test password login with non-existent user."""
        mock_db.find_by_field = AsyncMock(return_value=None)
        
        response = client.post("/api/auth/password/login", json={
            "email": "nonexistent@example.com",
            "password": "any-password"
        })
        
        assert response.status_code == 401
        assert "incorretos" in response.json()["detail"]
    
    @patch('app.routers.auth_router.db')
    def test_password_login_no_password_set(self, mock_db, client, mock_user):
        """Test password login when user has no password."""
        mock_user.hashedPassword = None
        mock_db.find_by_field = AsyncMock(return_value=mock_user)
        
        response = client.post("/api/auth/password/login", json={
            "email": "test@example.com",
            "password": "any-password"
        })
        
        assert response.status_code == 401
        assert "incorretos" in response.json()["detail"]
    
    @patch('app.routers.auth_router.db')
    @patch('app.routers.auth_router.verify_password')
    def test_password_login_wrong_password(self, mock_verify, mock_db, client, mock_user):
        """Test password login with wrong password."""
        mock_user.hashedPassword = "hashed-password"
        mock_db.find_by_field = AsyncMock(return_value=mock_user)
        mock_verify.return_value = False
        
        response = client.post("/api/auth/password/login", json={
            "email": "test@example.com",
            "password": "wrong-password"
        })
        
        assert response.status_code == 401
        assert "incorretos" in response.json()["detail"]
    
    @patch('app.routers.auth_router.db')
    def test_password_login_error_handling(self, mock_db, client):
        """Test error handling in password login."""
        mock_db.find_by_field = AsyncMock(side_effect=Exception("DB error"))
        
        response = client.post("/api/auth/password/login", json={
            "email": "test@example.com",
            "password": "any-password"
        })
        
        assert response.status_code == 500
        assert "Erro no login" in response.json()["detail"]


class TestRefreshToken:
    """Tests for POST /auth/refresh endpoint."""
    
    @patch('app.routers.auth_router.db')
    @patch('app.routers.auth_router.create_access_token')
    def test_refresh_token_success(self, mock_create_token, mock_db, client, mock_user, mock_session):
        """Test successful token refresh."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        app.dependency_overrides[get_current_session] = lambda: mock_session
        
        mock_create_token.return_value = "new-jwt-token"
        mock_db.update = AsyncMock(return_value=True)
        
        response = client.post("/api/auth/refresh")
        
        assert response.status_code == 200
        data = response.json()
        assert data["token"] == "new-jwt-token"
        assert "user" in data
        assert "session" in data
    
    def test_refresh_token_unauthenticated(self, client):
        """Test token refresh without authentication."""
        response = client.post("/api/auth/refresh")
        
        assert response.status_code == 401
    
    @patch('app.routers.auth_router.db')
    def test_refresh_token_inactive_session(self, mock_db, client, mock_user, mock_session):
        """Test token refresh with inactive session."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_session.active = False
        app.dependency_overrides[get_current_session] = lambda: mock_session
        
        response = client.post("/api/auth/refresh")
        
        assert response.status_code == 401
        assert "inválida ou expirada" in response.json()["detail"]
    
    @patch('app.routers.auth_router.db')
    def test_refresh_token_expired_session(self, mock_db, client, mock_user, mock_session):
        """Test token refresh with expired session."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_session.expires_at = datetime.utcnow() - timedelta(days=1)
        app.dependency_overrides[get_current_session] = lambda: mock_session
        
        response = client.post("/api/auth/refresh")
        
        assert response.status_code == 401
        assert "expirada" in response.json()["detail"]
    
    @patch('app.routers.auth_router.db')
    @patch('app.routers.auth_router.create_access_token')
    def test_refresh_token_error_handling(self, mock_create_token, mock_db, client, mock_user, mock_session):
        """Test error handling in token refresh."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        app.dependency_overrides[get_current_session] = lambda: mock_session
        
        mock_create_token.side_effect = Exception("Token error")
        
        response = client.post("/api/auth/refresh")
        
        assert response.status_code == 500
        assert "Erro ao renovar token" in response.json()["detail"]
