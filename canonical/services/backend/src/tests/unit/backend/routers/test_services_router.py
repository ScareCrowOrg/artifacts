"""
Unit tests for services_router.py

Tests cover:
- GET /services/status - Get status of all services
- GET /services/config - Get service configurations
- POST /services/config - Update service configurations
- POST /services/config/test - Test connectivity
- GET /services/{service_id}/logs - Get service logs
- POST /services/{service_id}/start - Start service
- POST /services/{service_id}/stop - Stop service
- POST /services/{service_id}/restart - Restart service

Technical naming: All functions and variables in English.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
import socket as socket_module

from app.main import app
from app.models import User
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


class TestServicesStatusEndpoint:
    """Tests for GET /services/status endpoint."""
    
    @patch('app.routers.services_router.get_service_process')
    @patch('app.routers.services_router.get_process_info')
    @patch('app.routers.services_router.time')
    def test_get_status_all_running(self, mock_time, mock_get_info, mock_get_proc, client, mock_user):
        """Test getting status when all services are running."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Mock time
        mock_time.strftime.return_value = "2024-01-01T00:00:00Z"
        mock_time.gmtime.return_value = None
        
        # Mock running process
        mock_proc = Mock()
        mock_get_proc.return_value = mock_proc
        mock_get_info.return_value = {
            "pid": 12345,
            "uptime": 3600.0,
            "memory_mb": 150.5,
            "cpu_percent": 2.5
        }
        
        response = client.get("/api/services/status")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # At least one service should be running
        running_services = [s for s in data if s["status"] == "running"]
        assert len(running_services) > 0
        # Check fields
        for service in running_services:
            assert "id" in service
            assert "name" in service
            assert "status" in service
            assert service["pid"] == 12345
    
    @patch('app.routers.services_router.get_service_process')
    @patch('app.routers.services_router.time')
    def test_get_status_all_stopped(self, mock_time, mock_get_proc, client, mock_user):
        """Test getting status when all services are stopped."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_time.strftime.return_value = "2024-01-01T00:00:00Z"
        mock_time.gmtime.return_value = None
        mock_get_proc.return_value = None
        
        response = client.get("/api/services/status")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # All services should be stopped
        stopped_services = [s for s in data if s["status"] == "stopped"]
        assert len(stopped_services) == len(data)


class TestServicesConfigEndpoint:
    """Tests for GET /services/config endpoint."""
    
    @patch('app.routers.services_router.time')
    def test_get_config_success(self, mock_time, client, mock_user):
        """Test successful config retrieval."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_time.strftime.return_value = "2024-01-01T00:00:00Z"
        mock_time.gmtime.return_value = None
        
        response = client.get("/api/services/config")
        
        assert response.status_code == 200
        data = response.json()
        assert "services" in data
        assert "version" in data
        assert "last_updated" in data
        assert isinstance(data["services"], list)
        assert len(data["services"]) > 0
        
        # Check service structure
        for service in data["services"]:
            assert "id" in service
            assert "name" in service
            assert "endpoint" in service
            assert "port" in service
            assert "enabled" in service


class TestUpdateServicesConfigEndpoint:
    """Tests for POST /services/config endpoint."""
    
    def test_update_config_success(self, client, mock_user):
        """Test successful config update."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        response = client.post("/api/services/config", json={
            "services": [
                {
                    "id": "backend",
                    "name": "Backend API",
                    "endpoint": "http://localhost:5051/api",
                    "port": 5051,
                    "enabled": True,
                    "auto_start": False
                }
            ]
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "services_updated" in data
    
    def test_update_config_invalid_service(self, client, mock_user):
        """Test config update with invalid service ID."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        response = client.post("/api/services/config", json={
            "services": [
                {
                    "id": "nonexistent_service",
                    "name": "Fake Service",
                    "endpoint": "http://localhost:9999",
                    "port": 9999,
                    "enabled": True
                }
            ]
        })
        
        assert response.status_code == 400
        data = response.json()
        assert "Unknown service" in data["detail"]
    
    def test_update_config_invalid_port(self, client, mock_user):
        """Test config update with invalid port."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        response = client.post("/api/services/config", json={
            "services": [
                {
                    "id": "backend",
                    "name": "Backend API",
                    "endpoint": "http://localhost:99999",
                    "port": 99999,  # Invalid port
                    "enabled": True
                }
            ]
        })
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid port" in data["detail"]


class TestConnectivityTestEndpoint:
    """Tests for POST /services/config/test endpoint."""
    
    def test_connectivity_test_success(self, client, mock_user):
        """Test successful connectivity test."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        with patch('socket.socket') as mock_socket_class:
            # Mock successful connection
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0
            mock_sock.close.return_value = None
            mock_sock.settimeout.return_value = None
            mock_socket_class.return_value = mock_sock
            
            response = client.post("/api/services/config/test", json={
                "endpoint": "http://localhost:5051",
                "port": 5051,
                "timeout": 5
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Successfully connected" in data["message"]
    
    def test_connectivity_test_failure(self, client, mock_user):
        """Test failed connectivity test."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        with patch('socket.socket') as mock_socket_class:
            # Mock failed connection
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 1  # Connection refused
            mock_sock.close.return_value = None
            mock_sock.settimeout.return_value = None
            mock_socket_class.return_value = mock_sock
            
            response = client.post("/api/services/config/test", json={
                "endpoint": "http://localhost:9999",
                "port": 9999,
                "timeout": 5
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Failed to connect" in data["message"]
    
    def test_connectivity_test_timeout(self, client, mock_user):
        """Test connectivity test timeout."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        with patch('socket.socket') as mock_socket_class:
            # Mock timeout
            mock_sock = MagicMock()
            mock_sock.connect_ex.side_effect = socket_module.timeout()
            mock_sock.close.return_value = None
            mock_sock.settimeout.return_value = None
            mock_socket_class.return_value = mock_sock
            
            response = client.post("/api/services/config/test", json={
                "endpoint": "http://localhost:5051",
                "port": 5051,
                "timeout": 1
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "timeout" in data["message"].lower()


class TestServiceLogsEndpoint:
    """Tests for GET /services/{service_id}/logs endpoint."""
    
    @patch('app.routers.services_router.BASE_DIR', Path('/test/base'))
    @patch('builtins.open', new_callable=mock_open, read_data="Log line 1\nLog line 2\nLog line 3\n")
    def test_get_logs_success(self, mock_file, client, mock_user):
        """Test successful log retrieval."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        with patch.object(Path, 'exists', return_value=True):
            response = client.get("/api/services/backend/logs?lines=50")
        
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "service_id" in data
        assert data["service_id"] == "backend"
        assert isinstance(data["logs"], list)
    
    def test_get_logs_service_not_found(self, client, mock_user):
        """Test logs for non-existent service."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        response = client.get("/api/services/nonexistent/logs")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    @patch('app.routers.services_router.BASE_DIR', Path('/test/base'))
    def test_get_logs_no_log_file(self, client, mock_user):
        """Test logs when log file doesn't exist."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        with patch.object(Path, 'exists', return_value=False):
            response = client.get("/api/services/backend/logs")
        
        assert response.status_code == 200
        data = response.json()
        assert data["logs"] == []
        assert "No logs available" in data["message"]


class TestStartServiceEndpoint:
    """Tests for POST /services/{service_id}/start endpoint."""
    
    @patch('app.routers.services_router.get_service_process')
    def test_start_service_already_running(self, mock_get_proc, client, mock_user):
        """Test starting a service that's already running."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Mock running process
        mock_proc = Mock()
        mock_get_proc.return_value = mock_proc
        
        response = client.post("/api/services/backend/start")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "already running" in data["message"].lower()
    
    @patch('app.routers.services_router.get_service_process')
    def test_start_service_not_implemented(self, mock_get_proc, client, mock_user):
        """Test starting service (not fully implemented)."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Mock stopped process
        mock_get_proc.return_value = None
        
        response = client.post("/api/services/backend/start")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not fully implemented" in data["message"].lower()
    
    def test_start_service_invalid_id(self, client, mock_user):
        """Test starting non-existent service."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        response = client.post("/api/services/nonexistent/start")
        
        assert response.status_code == 404


class TestStopServiceEndpoint:
    """Tests for POST /services/{service_id}/stop endpoint."""
    
    @patch('app.routers.services_router.get_service_process')
    def test_stop_service_not_running(self, mock_get_proc, client, mock_user):
        """Test stopping a service that's not running."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Mock no process
        mock_get_proc.return_value = None
        
        response = client.post("/api/services/backend/stop")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not running" in data["message"].lower()
    
    @patch('app.routers.services_router.get_service_process')
    def test_stop_service_not_implemented(self, mock_get_proc, client, mock_user):
        """Test stopping service (not fully implemented)."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Mock running process
        mock_proc = Mock()
        mock_get_proc.return_value = mock_proc
        
        response = client.post("/api/services/backend/stop")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not fully implemented" in data["message"].lower()


class TestRestartServiceEndpoint:
    """Tests for POST /services/{service_id}/restart endpoint."""
    
    def test_restart_service_not_implemented(self, client, mock_user):
        """Test restarting service (not fully implemented)."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        response = client.post("/api/services/backend/restart")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not fully implemented" in data["message"].lower()
    
    def test_restart_service_invalid_id(self, client, mock_user):
        """Test restarting non-existent service."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        response = client.post("/api/services/nonexistent/restart")
        
        assert response.status_code == 404
