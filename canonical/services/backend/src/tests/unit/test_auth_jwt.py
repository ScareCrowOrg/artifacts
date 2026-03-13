"""
Unit tests for JWT enhancement with roles, permissions, and jti.

Tests the enhanced JWT token creation with:
- jti (JWT ID) for token revocation
- roles array for user roles
- permissions array for user permissions
- backward compatibility with old tokens
"""

import pytest
import os
from datetime import datetime, timedelta
from jose import jwt

# Set test environment variable before importing
os.environ["ENCRYPTION_KEY"] = "test-secret-key-for-testing-minimum-32-characters-long"

from app.auth import create_access_token, verify_token, ALGORITHM
from app.models import User

# Use test secret key for all tests
TEST_SECRET_KEY = os.environ["ENCRYPTION_KEY"]


class TestJWTEnhancement:
    """Tests for enhanced JWT token with roles, permissions, and jti."""

    def test_jwt_includes_jti(self):
        """JWT includes unique jti field."""
        user = User(id="user_1", name="Test User", email="test@example.com", roles=[], permissions=[])
        token = create_access_token(user)

        payload = jwt.decode(token, TEST_SECRET_KEY, algorithms=[ALGORITHM])
        assert "jti" in payload, "JWT should include jti field"
        assert isinstance(payload["jti"], str), "jti should be a string"
        assert len(payload["jti"]) > 0, "jti should not be empty"

    def test_jwt_jti_is_unique(self):
        """Each JWT has unique jti."""
        user = User(id="user_1", name="Test User", email="test@example.com", roles=[], permissions=[])
        token1 = create_access_token(user)
        token2 = create_access_token(user)

        payload1 = jwt.decode(token1, TEST_SECRET_KEY, algorithms=[ALGORITHM])
        payload2 = jwt.decode(token2, TEST_SECRET_KEY, algorithms=[ALGORITHM])

        assert payload1["jti"] != payload2["jti"], "Each JWT should have unique jti"

    def test_jwt_includes_roles(self):
        """JWT includes user roles."""
        user = User(
            id="user_1",
            name="Test User",
            email="test@example.com",
            roles=["editor", "admin"],
            permissions=[],
        )
        token = create_access_token(user)

        payload = jwt.decode(token, TEST_SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["roles"] == ["editor", "admin"], "JWT should include user roles"

    def test_jwt_includes_permissions(self):
        """JWT includes user permissions."""
        user = User(
            id="user_1",
            name="Test User",
            email="test@example.com",
            roles=[],
            permissions=["cells.read", "cells.write"],
        )
        token = create_access_token(user)

        payload = jwt.decode(token, TEST_SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["permissions"] == [
            "cells.read",
            "cells.write",
        ], "JWT should include user permissions"

    def test_jwt_expiration(self):
        """JWT expires in expected time."""
        user = User(id="user_1", name="Test User", email="test@example.com", roles=[], permissions=[])
        before = datetime.utcnow()
        token = create_access_token(user, expires_delta=timedelta(minutes=30))
        after = datetime.utcnow()

        payload = jwt.decode(token, TEST_SECRET_KEY, algorithms=[ALGORITHM])
        exp_time = datetime.fromtimestamp(payload["exp"])

        # Should be ~30 minutes from now
        expected_min = before + timedelta(minutes=29)
        expected_max = after + timedelta(minutes=31)
        assert expected_min <= exp_time <= expected_max, "JWT expiration should be around 30 minutes"

    def test_jwt_backward_compatible(self):
        """Old JWT validation still works (dict-based API)."""
        # Create old-style JWT (without jti, roles, perms)
        old_payload = {
            "sub": "user_1",
            "session_id": "session_123",
        }
        old_token = create_access_token(old_payload, expires_delta=timedelta(minutes=30))

        # Decode should succeed
        decoded = jwt.decode(old_token, TEST_SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["sub"] == "user_1", "Old token should decode successfully"
        assert decoded.get("session_id") == "session_123", "Old token should preserve session_id"
        assert "exp" in decoded, "Old token should have expiration"
        assert "iat" in decoded, "Old token should have issued-at time"
        assert decoded.get("type") == "access", "Old token should have type field"

    def test_jwt_includes_session_id(self):
        """JWT includes session_id when provided."""
        user = User(id="user_1", name="Test User", email="test@example.com", roles=[], permissions=[])
        user.session_id = "session_123"  # Add session_id attribute

        token = create_access_token(user)

        payload = jwt.decode(token, TEST_SECRET_KEY, algorithms=[ALGORITHM])
        assert payload.get("session_id") == "session_123", "JWT should include session_id"

    def test_jwt_includes_type_field(self):
        """JWT includes type field set to 'access'."""
        user = User(id="user_1", name="Test User", email="test@example.com", roles=[], permissions=[])
        token = create_access_token(user)

        payload = jwt.decode(token, TEST_SECRET_KEY, algorithms=[ALGORITHM])
        assert payload.get("type") == "access", "JWT should have type='access'"

    def test_jwt_includes_iat_field(self):
        """JWT includes issued-at timestamp."""
        user = User(id="user_1", name="Test User", email="test@example.com", roles=[], permissions=[])
        before = datetime.utcnow()
        token = create_access_token(user)
        after = datetime.utcnow()

        payload = jwt.decode(token, TEST_SECRET_KEY, algorithms=[ALGORITHM])
        assert "iat" in payload, "JWT should include iat field"

        iat_time = datetime.fromtimestamp(payload["iat"])
        assert before <= iat_time <= after, "iat should be within token creation time"

    def test_jwt_empty_roles_and_permissions(self):
        """JWT handles empty roles and permissions arrays."""
        user = User(id="user_1", name="Test User", email="test@example.com", roles=[], permissions=[])
        token = create_access_token(user)

        payload = jwt.decode(token, TEST_SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["roles"] == [], "Empty roles should be []"
        assert payload["permissions"] == [], "Empty permissions should be []"

    def test_jwt_none_roles_and_permissions(self):
        """JWT handles None roles and permissions (defaults to empty arrays)."""
        user = User(id="user_1", name="Test User", email="test@example.com")
        # User model defaults to roles=["user"], but we can override
        user.roles = None
        user.permissions = None

        token = create_access_token(user)

        payload = jwt.decode(token, TEST_SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["roles"] == [], "None roles should become []"
        assert payload["permissions"] == [], "None permissions should become []"

    def test_verify_token_with_enhanced_fields(self):
        """verify_token function works with enhanced JWT."""
        user = User(
            id="user_1",
            name="Test User",
            email="test@example.com",
            roles=["admin"],
            permissions=["cells.write"],
        )
        token = create_access_token(user)

        payload = verify_token(token)
        assert payload is not None, "verify_token should succeed"
        assert payload["sub"] == "user_1", "Should have correct user_id"
        assert "jti" in payload, "Should have jti"
        assert payload["roles"] == ["admin"], "Should have roles"
        assert payload["permissions"] == ["cells.write"], "Should have permissions"

    def test_jwt_size_is_reasonable(self):
        """JWT size is reasonable (< 2KB)."""
        # Create user with many roles and permissions
        user = User(
            id="user_1",
            name="Test User",
            email="test@example.com",
            roles=["admin", "editor", "viewer", "contributor", "moderator"],
            permissions=[
                "cells.read",
                "cells.write",
                "cells.delete",
                "books.read",
                "books.write",
                "books.delete",
                "users.read",
                "users.write",
            ],
        )
        token = create_access_token(user)

        # JWT should be < 2KB
        assert len(token) < 2048, f"JWT size ({len(token)} bytes) should be < 2KB"

    def test_jwt_creation_with_custom_expiration(self):
        """JWT respects custom expiration delta."""
        user = User(id="user_1", name="Test User", email="test@example.com", roles=[], permissions=[])
        custom_delta = timedelta(hours=2)

        before = datetime.utcnow()
        token = create_access_token(user, expires_delta=custom_delta)
        after = datetime.utcnow()

        payload = jwt.decode(token, TEST_SECRET_KEY, algorithms=[ALGORITHM])
        exp_time = datetime.fromtimestamp(payload["exp"])

        # Should be ~2 hours from now
        expected_min = before + timedelta(hours=1, minutes=59)
        expected_max = after + timedelta(hours=2, minutes=1)
        assert expected_min <= exp_time <= expected_max, "JWT should respect custom expiration"


class TestBackwardCompatibility:
    """Tests for backward compatibility with dict-based API."""

    def test_create_token_with_dict(self):
        """Can still create tokens with dict (old API)."""
        data = {"sub": "user_1", "session_id": "session_123"}
        token = create_access_token(data)

        assert token is not None
        assert isinstance(token, str)

        payload = jwt.decode(token, TEST_SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "user_1"

    def test_dict_token_includes_default_fields(self):
        """Dict-based tokens get default fields (jti, iat, type)."""
        data = {"sub": "user_1"}
        token = create_access_token(data)

        payload = jwt.decode(token, TEST_SECRET_KEY, algorithms=[ALGORITHM])
        assert "jti" in payload, "Dict token should have jti"
        assert "iat" in payload, "Dict token should have iat"
        assert payload.get("type") == "access", "Dict token should have type"

    def test_dict_token_jti_is_unique(self):
        """Dict-based tokens generate unique jti."""
        data = {"sub": "user_1"}
        token1 = create_access_token(data)
        token2 = create_access_token(data)

        payload1 = jwt.decode(token1, TEST_SECRET_KEY, algorithms=[ALGORITHM])
        payload2 = jwt.decode(token2, TEST_SECRET_KEY, algorithms=[ALGORITHM])

        assert payload1["jti"] != payload2["jti"], "Each dict token should have unique jti"

    def test_dict_token_preserves_custom_fields(self):
        """Dict-based tokens preserve custom fields."""
        data = {"sub": "user_1", "custom_field": "custom_value", "another": 123}
        token = create_access_token(data)

        payload = jwt.decode(token, TEST_SECRET_KEY, algorithms=[ALGORITHM])
        assert payload.get("custom_field") == "custom_value"
        assert payload.get("another") == 123
