"""
Unit tests for RBAC permissions module.

Tests permission validation, caching, and authorization decorators.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock
from fastapi import HTTPException

from app.permissions import (
    get_user_permissions,
    has_permission,
    require_admin,
    check_resource_ownership,
    invalidate_user_cache,
    _get_cache_key,
    _is_cache_valid,
    _get_cached_permissions,
    _cache_permissions,
    _permissions_cache,
    _CACHE_TTL
)
from app.models.users import User
from app.models.permissions import Role, RoleEnum
from app.database import JSONDatabase


# Test fixtures
@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database."""
    db = JSONDatabase(base_path=tmp_path / "test_db", is_test_env=True)
    yield db
    db.cleanup_test_data()


@pytest.fixture
def admin_user():
    """Create an admin user for testing."""
    return User(
        id="admin-1",
        name="Admin User",
        email="admin@test.com",
        roles=["admin"]
    )


@pytest.fixture
def regular_user():
    """Create a regular user for testing."""
    return User(
        id="user-1",
        name="Regular User",
        email="user@test.com",
        roles=["user"]
    )


@pytest.fixture
def viewer_user():
    """Create a viewer user for testing."""
    return User(
        id="viewer-1",
        name="Viewer User",
        email="viewer@test.com",
        roles=["viewer"]
    )


@pytest.fixture
def multi_role_user():
    """Create a user with multiple roles."""
    return User(
        id="multi-1",
        name="Multi Role User",
        email="multi@test.com",
        roles=["user", "viewer"]
    )


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request object."""
    request = MagicMock()
    request.client.host = "127.0.0.1"
    request.url.path = "/test/endpoint"
    return request


@pytest.fixture
def setup_roles(test_db):
    """Set up role definitions in the database."""
    # Admin role
    admin_role = Role(
        name=RoleEnum.ADMIN,
        description="Administrator with full access",
        permissions=["*"],
        priority=100
    )
    test_db.insert("roles", admin_role, is_canonical=True)
    
    # User role
    user_role = Role(
        name=RoleEnum.USER,
        description="Standard user with basic permissions",
        permissions=[
            "cells.create",
            "cells.read_own",
            "cells.update_own",
            "cells.delete_own",
            "books.create",
            "books.read_own"
        ],
        priority=10
    )
    test_db.insert("roles", user_role, is_canonical=True)
    
    # Viewer role
    viewer_role = Role(
        name=RoleEnum.VIEWER,
        description="Read-only access",
        permissions=[
            "cells.read_own",
            "books.read_own"
        ],
        priority=5
    )
    test_db.insert("roles", viewer_role, is_canonical=True)
    
    # Create a mock database that wraps test_db with AsyncMock for async methods
    # HybridDatabase has async methods, but test_db (JSONDatabase) has sync methods
    # We need to mock find_by_field as AsyncMock to match HybridDatabase behavior
    mock_db = MagicMock()
    
    # Create async version of find_by_field that delegates to test_db's sync method
    async def async_find_by_field(collection, field, value, model_class, is_canonical=False):
        return test_db.find_by_field(collection, field, value, model_class, is_canonical=is_canonical)
    
    mock_db.find_by_field = AsyncMock(side_effect=async_find_by_field)
    
    return mock_db


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear permissions cache before each test."""
    global _permissions_cache
    _permissions_cache.clear()
    yield
    _permissions_cache.clear()


# Cache management tests
class TestCacheManagement:
    """Test permission caching functionality."""
    
    def test_get_cache_key(self):
        """Cache key should be properly formatted."""
        user_id = "user-123"
        cache_key = _get_cache_key(user_id)
        assert cache_key == "user_permissions:user-123"
    
    def test_cache_permissions(self):
        """Should store permissions in cache with timestamp."""
        user_id = "user-1"
        permissions = ["cells.create", "cells.read_own"]
        
        _cache_permissions(user_id, permissions)
        
        cache_key = _get_cache_key(user_id)
        assert cache_key in _permissions_cache
        assert _permissions_cache[cache_key]["permissions"] == permissions
        assert "timestamp" in _permissions_cache[cache_key]
    
    def test_get_cached_permissions_hit(self):
        """Should return cached permissions if valid."""
        user_id = "user-1"
        permissions = ["cells.create"]
        
        _cache_permissions(user_id, permissions)
        cached = _get_cached_permissions(user_id)
        
        assert cached == permissions
    
    def test_get_cached_permissions_miss(self):
        """Should return None if cache doesn't exist."""
        cached = _get_cached_permissions("nonexistent-user")
        assert cached is None
    
    def test_is_cache_valid_fresh(self):
        """Fresh cache should be valid."""
        user_id = "user-1"
        _cache_permissions(user_id, ["test.permission"])
        
        cache_key = _get_cache_key(user_id)
        assert _is_cache_valid(cache_key) is True
    
    def test_is_cache_valid_expired(self):
        """Expired cache should be invalid."""
        import time
        user_id = "user-1"
        cache_key = _get_cache_key(user_id)
        
        # Manually create expired cache entry
        _permissions_cache[cache_key] = {
            "permissions": ["test.permission"],
            "timestamp": time.time() - (_CACHE_TTL + 10)  # Expired
        }
        
        assert _is_cache_valid(cache_key) is False
    
    def test_invalidate_user_cache(self):
        """Should remove user from cache."""
        user_id = "user-1"
        _cache_permissions(user_id, ["test.permission"])
        
        cache_key = _get_cache_key(user_id)
        assert cache_key in _permissions_cache
        
        invalidate_user_cache(user_id)
        assert cache_key not in _permissions_cache
    
    def test_invalidate_nonexistent_cache(self):
        """Should not raise error when invalidating nonexistent cache."""
        invalidate_user_cache("nonexistent-user")  # Should not raise


# Permission loading tests
class TestGetUserPermissions:
    """Test user permission loading."""
    
    async def test_admin_has_wildcard(self, admin_user, setup_roles, monkeypatch):
        """Admin should receive wildcard permission."""
        # Mock db to use test_db
        monkeypatch.setattr('app.permissions.db', setup_roles)
        
        permissions = await get_user_permissions(admin_user)
        assert permissions == ["*"]
    
    async def test_user_permissions_loaded(self, regular_user, setup_roles, monkeypatch):
        """Regular user should receive role-specific permissions."""
        monkeypatch.setattr('app.permissions.db', setup_roles)
        
        permissions = await get_user_permissions(regular_user)
        
        assert "cells.create" in permissions
        assert "cells.read_own" in permissions
        assert "cells.update_own" in permissions
        assert "cells.delete_own" in permissions
        assert "books.create" in permissions
    
    async def test_viewer_permissions_limited(self, viewer_user, setup_roles, monkeypatch):
        """Viewer should have only read permissions."""
        monkeypatch.setattr('app.permissions.db', setup_roles)
        
        permissions = await get_user_permissions(viewer_user)
        
        assert "cells.read_own" in permissions
        assert "books.read_own" in permissions
        assert "cells.create" not in permissions
        assert "cells.delete_own" not in permissions
    
    async def test_multi_role_permissions_merged(self, multi_role_user, setup_roles, monkeypatch):
        """User with multiple roles should have merged permissions."""
        monkeypatch.setattr('app.permissions.db', setup_roles)
        
        permissions = await get_user_permissions(multi_role_user)
        
        # Should have all user permissions
        assert "cells.create" in permissions
        assert "cells.update_own" in permissions
        
        # No duplicates from viewer role
        assert permissions.count("cells.read_own") == 1
    
    async def test_permissions_cached_on_second_call(self, regular_user, setup_roles, monkeypatch):
        """Second call should use cache."""
        monkeypatch.setattr('app.permissions.db', setup_roles)
        
        # First call
        permissions1 = await get_user_permissions(regular_user)
        
        # Second call should use cache
        permissions2 = await get_user_permissions(regular_user)
        
        assert permissions1 == permissions2
        
        # Verify cache was used
        cache_key = _get_cache_key(regular_user.id)
        assert cache_key in _permissions_cache
    
    async def test_nonexistent_role_logged(self, regular_user, setup_roles, monkeypatch, caplog):
        """Should log warning for nonexistent role."""
        monkeypatch.setattr('app.permissions.db', setup_roles)
        
        # Add nonexistent role
        regular_user.roles.append("nonexistent_role")
        
        with caplog.at_level("WARNING"):
            permissions = await get_user_permissions(regular_user)
        
        # Should still return user role permissions
        assert "cells.create" in permissions
        
        # Should log warning
        assert "not found in database" in caplog.text


# Permission validation tests
class TestHasPermission:
    """Test has_permission decorator."""
    
    @pytest.mark.asyncio
    async def test_admin_bypass(self, admin_user, setup_roles, mock_request, monkeypatch):
        """Admin should bypass permission checks."""
        monkeypatch.setattr('app.permissions.db', setup_roles)
        monkeypatch.setattr('app.permissions.get_current_user_required', lambda: admin_user)
        
        # Create permission checker for any permission
        checker = has_permission(["nonexistent.permission"])
        
        # Should not raise for admin
        result = await checker(mock_request, admin_user)
        assert result == admin_user
    
    @pytest.mark.asyncio
    async def test_user_with_permission_allowed(self, regular_user, setup_roles, mock_request, monkeypatch):
        """User with required permission should be allowed."""
        monkeypatch.setattr('app.permissions.db', setup_roles)
        
        checker = has_permission(["cells.create"])
        result = await checker(mock_request, regular_user)
        
        assert result == regular_user
    
    @pytest.mark.asyncio
    async def test_user_without_permission_denied(self, regular_user, setup_roles, mock_request, monkeypatch):
        """User without required permission should be denied."""
        monkeypatch.setattr('app.permissions.db', setup_roles)
        
        checker = has_permission(["cells.delete_any"])
        
        with pytest.raises(HTTPException) as exc:
            await checker(mock_request, regular_user)
        
        assert exc.value.status_code == 403
        assert exc.value.detail["error"] == "insufficient_permissions"
        assert "cells.delete_any" in exc.value.detail["missing"]
    
    @pytest.mark.asyncio
    async def test_require_all_permissions(self, regular_user, setup_roles, mock_request, monkeypatch):
        """require_all=True should require all permissions."""
        monkeypatch.setattr('app.permissions.db', setup_roles)
        
        # User has cells.create but not cells.delete_any
        checker = has_permission(
            ["cells.create", "cells.delete_any"],
            require_all=True
        )
        
        with pytest.raises(HTTPException) as exc:
            await checker(mock_request, regular_user)
        
        assert exc.value.status_code == 403
        assert "cells.delete_any" in exc.value.detail["missing"]
    
    @pytest.mark.asyncio
    async def test_require_any_permission(self, regular_user, setup_roles, mock_request, monkeypatch):
        """require_all=False should accept any one permission."""
        monkeypatch.setattr('app.permissions.db', setup_roles)
        
        # User has cells.create but not cells.delete_any
        checker = has_permission(
            ["cells.create", "cells.delete_any"],
            require_all=False
        )
        
        result = await checker(mock_request, regular_user)
        assert result == regular_user
    
    @pytest.mark.asyncio
    async def test_require_any_all_missing(self, viewer_user, setup_roles, mock_request, monkeypatch):
        """require_all=False should deny if no permissions match."""
        monkeypatch.setattr('app.permissions.db', setup_roles)
        
        # Viewer doesn't have any of these
        checker = has_permission(
            ["cells.create", "cells.delete_own"],
            require_all=False
        )
        
        with pytest.raises(HTTPException) as exc:
            await checker(mock_request, viewer_user)
        
        assert exc.value.status_code == 403
        assert "required_any" in exc.value.detail


# Admin requirement tests
class TestRequireAdmin:
    """Test require_admin helper."""
    
    @pytest.mark.asyncio
    async def test_admin_allowed(self, admin_user):
        """Admin user should be allowed."""
        result = await require_admin(admin_user)
        assert result == admin_user
    
    @pytest.mark.asyncio
    async def test_non_admin_denied(self, regular_user):
        """Non-admin user should be denied."""
        with pytest.raises(HTTPException) as exc:
            await require_admin(regular_user)
        
        assert exc.value.status_code == 403
        assert exc.value.detail["error"] == "admin_required"
    
    @pytest.mark.asyncio
    async def test_viewer_denied(self, viewer_user):
        """Viewer should be denied."""
        with pytest.raises(HTTPException) as exc:
            await require_admin(viewer_user)
        
        assert exc.value.status_code == 403


# Resource ownership tests
class TestCheckResourceOwnership:
    """Test resource ownership validation."""
    
    async def test_owner_allowed(self, regular_user, setup_roles, monkeypatch):
        """Owner should have access to their resource."""
        monkeypatch.setattr('app.permissions.db', setup_roles)
        
        result = await check_resource_ownership(
            resource_user_id=regular_user.id,
            current_user=regular_user,
            admin_permission="cells.delete_any"
        )
        
        assert result is True
    
    async def test_admin_allowed_any_resource(self, admin_user, regular_user, setup_roles, monkeypatch):
        """Admin should access any resource."""
        monkeypatch.setattr('app.permissions.db', setup_roles)
        
        result = await check_resource_ownership(
            resource_user_id=regular_user.id,
            current_user=admin_user,
            admin_permission="cells.delete_any"
        )
        
        assert result is True
    
    async def test_non_owner_without_permission_denied(self, regular_user, viewer_user, setup_roles, monkeypatch):
        """Non-owner without admin permission should be denied."""
        monkeypatch.setattr('app.permissions.db', setup_roles)
        
        with pytest.raises(HTTPException) as exc:
            await check_resource_ownership(
                resource_user_id=viewer_user.id,
                current_user=regular_user,
                admin_permission="cells.delete_any"
            )
        
        assert exc.value.status_code == 403
        assert exc.value.detail["error"] == "resource_forbidden"
    
    async def test_non_owner_with_admin_permission_allowed(self, setup_roles, monkeypatch):
        """Non-owner with specific admin permission should be allowed."""
        monkeypatch.setattr('app.permissions.db', setup_roles)
        
        # Create a user with delete_any permission
        admin_user = User(
            id="admin-2",
            name="Admin User",
            email="admin2@test.com",
            roles=["admin"]
        )
        
        other_user = User(
            id="other-1",
            name="Other User",
            email="other@test.com",
            roles=["user"]
        )
        
        result = await check_resource_ownership(
            resource_user_id=other_user.id,
            current_user=admin_user,
            admin_permission="cells.delete_any"
        )
        
        assert result is True


# Integration tests
class TestPermissionsIntegration:
    """Integration tests for permission system."""
    
    @pytest.mark.asyncio
    async def test_permission_check_with_cache(self, regular_user, setup_roles, mock_request, monkeypatch):
        """Permission check should use cache on subsequent calls."""
        monkeypatch.setattr('app.permissions.db', setup_roles)
        
        checker = has_permission(["cells.create"])
        
        # First call - loads from database
        await checker(mock_request, regular_user)
        
        # Verify cache was populated
        cache_key = _get_cache_key(regular_user.id)
        assert cache_key in _permissions_cache
        
        # Second call - uses cache
        await checker(mock_request, regular_user)
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_reloads_permissions(self, regular_user, setup_roles, monkeypatch):
        """Invalidating cache should reload permissions."""
        monkeypatch.setattr('app.permissions.db', setup_roles)
        
        # Load permissions
        permissions1 = await get_user_permissions(regular_user)
        
        # Invalidate cache
        invalidate_user_cache(regular_user.id)
        
        # Reload permissions
        permissions2 = await get_user_permissions(regular_user)
        
        # Should be equal
        assert permissions1 == permissions2
    
    async def test_error_detail_structure(self, regular_user, setup_roles, mock_request, monkeypatch):
        """Error responses should have proper structure."""
        monkeypatch.setattr('app.permissions.db', setup_roles)
        
        checker = has_permission(["cells.delete_any"])
        
        with pytest.raises(HTTPException) as exc:
            # Use await instead of loop.run_until_complete since this is an async test
            await checker(mock_request, regular_user)
        
        # Check error structure
        detail = exc.value.detail
        assert "error" in detail
        assert "message" in detail
        assert "required" in detail
        assert "missing" in detail
        assert isinstance(detail["required"], list)
        assert isinstance(detail["missing"], list)
