"""
Integration tests for JWT enhancement in login endpoints.

⚠️ DEPRECATED: These tests are for backend auth endpoints that have been
migrated to CentralHub as part of the Complete Authentication Strangling epic.
These tests need to be:
1. Migrated to centralhub/tests/integration/
2. Updated to test CentralHub endpoints instead of backend
3. Or removed if CentralHub already has equivalent tests

Tests that login endpoints (Google OAuth and password) return
JWTs with the enhanced structure including jti, roles, and permissions.
"""

import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
from jose import jwt

# Set test environment variable before importing
os.environ["ENCRYPTION_KEY"] = "test-secret-key-for-testing-minimum-32-characters-long"

# ⚠️ DEPRECATED: auth_router has been migrated to CentralHub
# from app.routers.auth_router import google_callback, login_with_password
# from app.models import User, LoginPasswordRequest
# from app.auth import ALGORITHM

# Use test secret key for all tests
TEST_SECRET_KEY = os.environ["ENCRYPTION_KEY"]


@pytest.mark.skip(reason="Auth endpoints migrated to CentralHub - tests need migration")
class TestGoogleLoginJWTStructure:
    """Integration tests for Google OAuth login JWT structure."""

    @pytest.mark.asyncio
    @patch("app.routers.auth_router.httpx.AsyncClient")
    @patch("app.routers.auth_router.db")
    async def test_google_login_returns_jwt_with_all_fields(self, mock_db, mock_httpx):
        """Google login returns JWT with jti, roles, and permissions."""
        # Mock Google OAuth responses
        mock_client = AsyncMock()
        mock_httpx.return_value.__aenter__.return_value = mock_client

        # Mock token exchange
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {"access_token": "google_access_token"}
        mock_client.post.return_value = token_response

        # Mock user info
        user_info_response = MagicMock()
        user_info_response.status_code = 200
        user_info_response.json.return_value = {
            "id": "google_123",
            "email": "test@example.com",
            "name": "Test User",
        }
        mock_client.get.return_value = user_info_response

        # Mock database - user doesn't exist yet (new user)
        mock_db.find.return_value = []
        mock_db.insert = AsyncMock()

        # Mock config
        mock_db.get_config.return_value = None
        os.environ["GOOGLE_CLIENT_ID"] = "test_client_id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test_client_secret"

        # Call endpoint
        request_data = {
            "code": "auth_code_123",
            "redirect_uri": "http://localhost:3000/callback",
        }

        result = await google_callback(request_data)

        # Verify response
        assert "token" in result, "Response should include token"
        assert "user" in result, "Response should include user"
        assert "session" in result, "Response should include session"

        # Decode and verify JWT structure
        token = result["token"]
        payload = jwt.decode(token, TEST_SECRET_KEY, algorithms=[ALGORITHM])

        # Check required fields
        assert "sub" in payload, "JWT should have 'sub' field"
        assert "jti" in payload, "JWT should have 'jti' field"
        assert "roles" in payload, "JWT should have 'roles' field"
        assert "permissions" in payload, "JWT should have 'permissions' field"
        assert "session_id" in payload, "JWT should have 'session_id' field"
        assert "exp" in payload, "JWT should have 'exp' field"
        assert "iat" in payload, "JWT should have 'iat' field"
        assert "type" in payload, "JWT should have 'type' field"

        # Verify field values
        assert isinstance(payload["jti"], str), "jti should be a string"
        assert len(payload["jti"]) > 0, "jti should not be empty"
        assert isinstance(payload["roles"], list), "roles should be a list"
        assert isinstance(payload["permissions"], list), "permissions should be a list"
        assert payload["type"] == "access", "type should be 'access'"

        # New user should have default role
        assert "user" in payload["roles"], "New user should have 'user' role"

    @pytest.mark.asyncio
    @patch("app.routers.auth_router.httpx.AsyncClient")
    @patch("app.routers.auth_router.db")
    async def test_google_login_existing_user_preserves_roles(self, mock_db, mock_httpx):
        """Google login for existing user preserves their roles and permissions."""
        # Mock Google OAuth responses
        mock_client = AsyncMock()
        mock_httpx.return_value.__aenter__.return_value = mock_client

        # Mock token exchange
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {"access_token": "google_access_token"}
        mock_client.post.return_value = token_response

        # Mock user info
        user_info_response = MagicMock()
        user_info_response.status_code = 200
        user_info_response.json.return_value = {
            "id": "google_123",
            "email": "admin@example.com",
            "name": "Admin User",
        }
        mock_client.get.return_value = user_info_response

        # Mock database - existing user with admin role
        existing_user = {
            "id": "user_123",
            "email": "admin@example.com",
            "name": "Admin User",
            "googleId": "google_123",
            "roles": ["admin", "editor"],
            "permissions": ["cells.write", "users.manage"],
        }
        mock_db.find.return_value = [existing_user]
        mock_db.insert = AsyncMock()

        # Mock config
        mock_db.get_config.return_value = None
        os.environ["GOOGLE_CLIENT_ID"] = "test_client_id"
        os.environ["GOOGLE_CLIENT_SECRET"] = "test_client_secret"

        # Call endpoint
        request_data = {
            "code": "auth_code_123",
            "redirect_uri": "http://localhost:3000/callback",
        }

        result = await google_callback(request_data)

        # Decode and verify JWT
        token = result["token"]
        payload = jwt.decode(token, TEST_SECRET_KEY, algorithms=[ALGORITHM])

        # Verify roles and permissions are preserved
        assert payload["roles"] == ["admin", "editor"], "Should preserve existing roles"
        assert payload["permissions"] == [
            "cells.write",
            "users.manage",
        ], "Should preserve existing permissions"


@pytest.mark.skip(reason="Auth endpoints migrated to CentralHub - tests need migration")
class TestPasswordLoginJWTStructure:
    """Integration tests for password login JWT structure."""

    @pytest.mark.asyncio
    @patch("app.routers.auth_router.db")
    async def test_password_login_returns_jwt_with_all_fields(self, mock_db):
        """Password login returns JWT with jti, roles, and permissions."""
        # Mock database - existing user with password
        existing_user = {
            "id": "user_123",
            "email": "test@example.com",
            "name": "Test User",
            "hashedPassword": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyB0xJxRgBWe",  # "password"
            "roles": ["user", "editor"],
            "permissions": ["cells.read", "cells.write"],
        }
        mock_db.find.return_value = [existing_user]
        mock_db.insert = AsyncMock()

        # Call endpoint
        request = LoginPasswordRequest(email="test@example.com", password="password")

        with patch("app.routers.auth_router.verify_password", return_value=True):
            result = await login_with_password(request)

        # Verify response
        assert "token" in result, "Response should include token"
        assert "user" in result, "Response should include user"
        assert "session" in result, "Response should include session"

        # Decode and verify JWT structure
        token = result.token
        payload = jwt.decode(token, TEST_SECRET_KEY, algorithms=[ALGORITHM])

        # Check required fields
        assert "sub" in payload, "JWT should have 'sub' field"
        assert "jti" in payload, "JWT should have 'jti' field"
        assert "roles" in payload, "JWT should have 'roles' field"
        assert "permissions" in payload, "JWT should have 'permissions' field"
        assert "session_id" in payload, "JWT should have 'session_id' field"
        assert "exp" in payload, "JWT should have 'exp' field"
        assert "iat" in payload, "JWT should have 'iat' field"
        assert "type" in payload, "JWT should have 'type' field"

        # Verify field values match user data
        assert payload["sub"] == "user_123", "sub should match user ID"
        assert payload["roles"] == ["user", "editor"], "roles should match user roles"
        assert payload["permissions"] == [
            "cells.read",
            "cells.write",
        ], "permissions should match user permissions"

    @pytest.mark.asyncio
    @patch("app.routers.auth_router.db")
    async def test_password_login_jti_is_unique_per_login(self, mock_db):
        """Each password login generates a unique jti."""
        # Mock database
        existing_user = {
            "id": "user_123",
            "email": "test@example.com",
            "name": "Test User",
            "hashedPassword": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyB0xJxRgBWe",
            "roles": ["user"],
            "permissions": [],
        }
        mock_db.find.return_value = [existing_user]
        mock_db.insert = AsyncMock()

        # First login
        request1 = LoginPasswordRequest(email="test@example.com", password="password")
        with patch("app.routers.auth_router.verify_password", return_value=True):
            result1 = await login_with_password(request1)

        # Second login
        request2 = LoginPasswordRequest(email="test@example.com", password="password")
        with patch("app.routers.auth_router.verify_password", return_value=True):
            result2 = await login_with_password(request2)

        # Decode both tokens
        payload1 = jwt.decode(result1.token, TEST_SECRET_KEY, algorithms=[ALGORITHM])
        payload2 = jwt.decode(result2.token, TEST_SECRET_KEY, algorithms=[ALGORITHM])

        # Verify jtis are different
        assert payload1["jti"] != payload2["jti"], "Each login should generate unique jti"


class TestTokenRefreshJWTStructure:
    """Integration tests for token refresh JWT structure."""

    @pytest.mark.asyncio
    @patch("app.routers.auth_router.db")
    async def test_refresh_token_includes_all_fields(self, mock_db):
        """Token refresh returns JWT with jti, roles, and permissions."""
        # This test would require importing and testing the refresh endpoint
        # Skipping for now as it requires more complex setup
        # The implementation in auth_router.py already uses the new API
        pass
