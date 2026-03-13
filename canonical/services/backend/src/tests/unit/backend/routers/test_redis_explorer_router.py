"""
Unit tests for Redis Explorer Router.

Tests REST API endpoints for Redis exploration and state invalidation.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def mock_service():
    """Create a mock Redis Explorer Service."""
    service = MagicMock()
    service.get_redis_info = AsyncMock(return_value={
        "version": "7.0.0",
        "used_memory": "1.5M",
        "total_keys": 42,
        "connected_clients": 5,
        "uptime_seconds": 3600
    })
    service.scan_keys_by_prefix = AsyncMock(return_value={
        "prefix": "",
        "delimiter": ":",
        "nodes": ["aider", "ollama"],
        "keys": [],
        "total_scanned": 100
    })
    service.get_key_value = AsyncMock(return_value={
        "key": "test:key",
        "type": "string",
        "value": {"test": "data"},
        "ttl": -1,
        "size": 100
    })
    service.delete_keys_by_prefix = AsyncMock(return_value={
        "prefix": "test:",
        "keys_found": 3,
        "keys_deleted": 3,
        "dry_run": False,
        "sample_keys": ["test:1", "test:2", "test:3"]
    })
    return service


class TestRedisExplorerRouter:
    """Test suite for Redis Explorer Router."""
    
    def test_get_redis_info_success(self, test_client, mock_service, mock_current_user):
        """Test successfully getting Redis info."""
        with patch('app.routers.redis_explorer_router.get_explorer_service', return_value=mock_service):
            response = test_client.get("/api/redis-explorer/info")
            
            assert response.status_code == 200
            data = response.json()
            assert data["version"] == "7.0.0"
            assert data["total_keys"] == 42
    
    def test_get_redis_info_error(self, test_client, mock_service, mock_current_user):
        """Test error handling when getting Redis info."""
        mock_service.get_redis_info.side_effect = Exception("Connection failed")
        
        with patch('app.routers.redis_explorer_router.get_explorer_service', return_value=mock_service):
            response = test_client.get("/api/redis-explorer/info")
            
            assert response.status_code == 500
            assert "Failed to get Redis info" in response.json()["detail"]
    
    def test_scan_keys_root_level(self, test_client, mock_service, mock_current_user):
        """Test scanning keys at root level."""
        with patch('app.routers.redis_explorer_router.get_explorer_service', return_value=mock_service):
            response = test_client.post(
                "/api/redis-explorer/scan",
                json={"prefix": "", "delimiter": ":", "max_depth": 1}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "nodes" in data
            assert "keys" in data
            assert data["prefix"] == ""
    
    def test_scan_keys_with_prefix(self, test_client, mock_service, mock_current_user):
        """Test scanning keys with specific prefix."""
        mock_service.scan_keys_by_prefix.return_value = {
            "prefix": "aider:session",
            "delimiter": ":",
            "nodes": ["123", "456"],
            "keys": [],
            "total_scanned": 50
        }
        
        with patch('app.routers.redis_explorer_router.get_explorer_service', return_value=mock_service):
            response = test_client.post(
                "/api/redis-explorer/scan",
                json={"prefix": "aider:session", "delimiter": ":", "max_depth": 1}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["prefix"] == "aider:session"
            assert "123" in data["nodes"]
    
    def test_get_key_value_success(self, test_client, mock_service, mock_current_user):
        """Test successfully getting key value."""
        with patch('app.routers.redis_explorer_router.get_explorer_service', return_value=mock_service):
            response = test_client.get("/api/redis-explorer/key/test:key")
            
            assert response.status_code == 200
            data = response.json()
            assert data["key"] == "test:key"
            assert data["type"] == "string"
    
    def test_get_key_value_not_found(self, test_client, mock_service, mock_current_user):
        """Test getting non-existent key."""
        mock_service.get_key_value.side_effect = Exception("Key does not exist")
        
        with patch('app.routers.redis_explorer_router.get_explorer_service', return_value=mock_service):
            response = test_client.get("/api/redis-explorer/key/nonexistent:key")
            
            assert response.status_code == 404
    
    def test_delete_keys_dry_run(self, test_client, mock_service, mock_current_user):
        """Test dry run deletion."""
        mock_service.delete_keys_by_prefix.return_value = {
            "prefix": "test:",
            "keys_found": 5,
            "keys_deleted": 0,
            "dry_run": True,
            "sample_keys": ["test:1", "test:2"]
        }
        
        with patch('app.routers.redis_explorer_router.get_explorer_service', return_value=mock_service):
            response = test_client.post(
                "/api/redis-explorer/delete",
                json={"prefix": "test:", "dry_run": True, "confirm": False}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["dry_run"] is True
            assert data["keys_found"] == 5
            assert data["keys_deleted"] == 0
    
    def test_delete_keys_actual_with_confirmation(self, test_client, mock_service, mock_current_user):
        """Test actual deletion with confirmation."""
        with patch('app.routers.redis_explorer_router.get_explorer_service', return_value=mock_service):
            response = test_client.post(
                "/api/redis-explorer/delete",
                json={"prefix": "test:", "dry_run": False, "confirm": True}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["dry_run"] is False
            assert data["keys_deleted"] > 0
    
    def test_delete_keys_without_confirmation(self, test_client, mock_service, mock_current_user):
        """Test deletion fails without explicit confirmation."""
        with patch('app.routers.redis_explorer_router.get_explorer_service', return_value=mock_service):
            response = test_client.post(
                "/api/redis-explorer/delete",
                json={"prefix": "test:", "dry_run": False, "confirm": False}
            )
            
            assert response.status_code == 400
            assert "confirm" in response.json()["detail"].lower()
    
    def test_redis_health_check_healthy(self, test_client, mock_service):
        """Test Redis health check when Redis is available."""
        with patch('app.routers.redis_explorer_router.get_explorer_service', return_value=mock_service):
            response = test_client.get("/api/redis-explorer/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["redis_available"] is True
    
    def test_redis_health_check_unhealthy(self, test_client, mock_service):
        """Test Redis health check when Redis is unavailable."""
        mock_service.get_redis_info.side_effect = Exception("Connection refused")
        
        with patch('app.routers.redis_explorer_router.get_explorer_service', return_value=mock_service):
            response = test_client.get("/api/redis-explorer/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["redis_available"] is False
            assert "error" in data
    
    def test_scan_request_validation(self, test_client, mock_current_user):
        """Test request validation for scan endpoint."""
        # Invalid max_depth (too high)
        response = test_client.post(
            "/api/redis-explorer/scan",
            json={"prefix": "", "delimiter": ":", "max_depth": 100}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_delete_request_validation(self, test_client, mock_current_user):
        """Test request validation for delete endpoint."""
        # Empty prefix (should fail validation)
        response = test_client.post(
            "/api/redis-explorer/delete",
            json={"prefix": "", "dry_run": True, "confirm": False}
        )
        
        assert response.status_code == 422  # Validation error
