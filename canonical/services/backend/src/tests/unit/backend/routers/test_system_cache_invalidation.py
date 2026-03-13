"""
Unit tests for cache invalidation endpoint in system_router.py

Tests the POST /system/cache/invalidate endpoint including:
- Admin authorization
- Redis cache invalidation
- Audit logging
- Error handling
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from app.main import app
from app.models import User


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up dependency overrides."""
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user():
    """Create mock admin user."""
    return User(
        id="admin-123",
        email="admin@test.com",
        name="Admin User",
        roles=["admin"]
    )


@pytest.fixture
def regular_user():
    """Create mock regular user."""
    return User(
        id="user-123",
        email="user@test.com",
        name="Regular User",
        roles=["user"]
    )


class TestCacheInvalidationEndpoint:
    """Test cache invalidation endpoint."""
    
    @patch('app.routers.system_router.invalidate_all_cache')
    @patch('app.routers.system_router.log_audit_event')
    def test_invalidate_cache_success(
        self,
        mock_audit,
        mock_invalidate,
        admin_user,
        client
    ):
        """Test successful cache invalidation by admin."""
        # Override the require_admin dependency directly
        from app.permissions import require_admin
        
        async def mock_admin_dep():
            return admin_user
        
        app.dependency_overrides[require_admin] = mock_admin_dep
        
        # Mock invalidate_all_cache
        mock_invalidate.return_value = {
            "success": True,
            "message": "Cache invalidated successfully. 100 keys deleted.",
            "keys_deleted": 100
        }
        
        response = client.post("/api/cache/invalidate")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["keys_deleted"] == 100
        
        # Verify audit log was called
        assert mock_audit.called
    
    @patch('app.routers.system_router.invalidate_all_cache')
    @patch('app.routers.system_router.log_audit_event')
    def test_invalidate_cache_redis_unavailable(
        self,
        mock_audit,
        mock_invalidate,
        admin_user,
        client
    ):
        """Test cache invalidation when Redis is unavailable."""
        from app.permissions import require_admin
        
        async def mock_admin_dep():
            return admin_user
        
        app.dependency_overrides[require_admin] = mock_admin_dep
        
        mock_invalidate.return_value = {
            "success": False,
            "message": "Redis is not available",
            "keys_deleted": 0
        }
        
        response = client.post("/api/cache/invalidate")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["keys_deleted"] == 0
    
    @patch('app.routers.system_router.invalidate_all_cache')
    @patch('app.routers.system_router.log_audit_event')
    def test_invalidate_cache_error_handling(
        self,
        mock_audit,
        mock_invalidate,
        admin_user,
        client
    ):
        """Test error handling in cache invalidation."""
        from app.permissions import require_admin
        
        async def mock_admin_dep():
            return admin_user
        
        app.dependency_overrides[require_admin] = mock_admin_dep
        
        mock_invalidate.side_effect = Exception("Redis connection error")
        
        response = client.post("/api/cache/invalidate")
        
        assert response.status_code == 500
        assert "Redis connection error" in response.json()["detail"]
    
    def test_invalidate_cache_requires_admin(self, regular_user, client):
        """Test that cache invalidation requires admin role."""
        from fastapi import HTTPException, status
        from app.permissions import require_admin
        
        # Mock require_admin to raise 403 for non-admin
        def mock_admin_dep():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin required"
            )
        
        app.dependency_overrides[require_admin] = mock_admin_dep
        
        response = client.post("/api/cache/invalidate")
        
        assert response.status_code == 403


class TestInvalidateAllCacheFunction:
    """Test the invalidate_all_cache function in redis_client.py"""
    
    @pytest.mark.asyncio
    async def test_invalidate_all_cache_success(self):
        """Test successful cache invalidation."""
        from app.core.redis_client import invalidate_all_cache
        
        # Mock Redis client
        mock_redis = AsyncMock()
        mock_redis.dbsize.return_value = 150
        mock_redis.flushdb = AsyncMock()
        
        with patch('app.core.redis_client.get_redis_client') as mock_get_redis:
            mock_get_redis.return_value = mock_redis
            
            result = await invalidate_all_cache()
            
            assert result["success"] is True
            assert result["keys_deleted"] == 150
            assert "150 keys deleted" in result["message"]
            
            # Verify Redis operations were called
            mock_redis.dbsize.assert_called_once()
            mock_redis.flushdb.assert_called_once_with(asynchronous=True)
    
    @pytest.mark.asyncio
    async def test_invalidate_all_cache_redis_disabled(self):
        """Test cache invalidation when Redis is disabled."""
        from app.core.redis_client import invalidate_all_cache
        
        with patch('app.core.redis_client.get_redis_client') as mock_get_redis:
            mock_get_redis.return_value = None
            
            result = await invalidate_all_cache()
            
            assert result["success"] is False
            assert result["keys_deleted"] == 0
            assert "not available" in result["message"]
    
    @pytest.mark.asyncio
    async def test_invalidate_all_cache_error(self):
        """Test error handling in cache invalidation."""
        from app.core.redis_client import invalidate_all_cache
        
        mock_redis = AsyncMock()
        mock_redis.dbsize.side_effect = Exception("Connection lost")
        
        with patch('app.core.redis_client.get_redis_client') as mock_get_redis:
            mock_get_redis.return_value = mock_redis
            
            with pytest.raises(Exception) as exc_info:
                await invalidate_all_cache()
            
            assert "Failed to invalidate cache" in str(exc_info.value)
            assert "Connection lost" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_invalidate_all_cache_zero_keys(self):
        """Test cache invalidation when cache is already empty."""
        from app.core.redis_client import invalidate_all_cache
        
        mock_redis = AsyncMock()
        mock_redis.dbsize.return_value = 0
        mock_redis.flushdb = AsyncMock()
        
        with patch('app.core.redis_client.get_redis_client') as mock_get_redis:
            mock_get_redis.return_value = mock_redis
            
            result = await invalidate_all_cache()
            
            assert result["success"] is True
            assert result["keys_deleted"] == 0
            assert "0 keys deleted" in result["message"]

