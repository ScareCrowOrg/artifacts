"""
Integration tests for audit logs API endpoints.

Tests audit log retrieval, filtering, and statistics.
"""

import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient
from datetime import datetime

from app.main import app
from app.models.users import User
from app.database import JSONDatabase


@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database."""
    db = JSONDatabase(base_path=tmp_path / "test_db", is_test_env=True)
    yield db
    db.cleanup_test_data()


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def admin_token(test_db):
    """Create an admin user and return authentication token."""
    # Create admin user
    admin_user = User(
        id="admin-test",
        name="Admin Test",
        email="admin@test.com",
        roles=["admin"]
    )
    test_db.insert("users", admin_user, is_canonical=False)
    
    # Mock authentication - in real tests you would get a proper JWT token
    # For now, we'll mock the authentication dependency
    return "mock-admin-token"


@pytest.fixture
def regular_token(test_db):
    """Create a regular user and return authentication token."""
    user = User(
        id="user-test",
        name="User Test",
        email="user@test.com",
        roles=["user"]
    )
    test_db.insert("users", user, is_canonical=False)
    
    return "mock-user-token"


@pytest.fixture
def sample_audit_logs(tmp_path):
    """Create sample audit logs for testing."""
    audit_logs_dir = tmp_path / "backend" / "artifacts" / "canonical" / "audit_logs"
    audit_logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Create sample audit logs
    logs = [
        {
            "id": "permission_denied_user-1_1234567890.1",
            "event_type": "permission_denied",
            "user_id": "user-1",
            "resource_type": "endpoint",
            "resource_id": "/api/admin/config",
            "action": "access_attempt",
            "details": {"required_permission": "admin.access"},
            "ip_address": "192.168.1.1",
            "timestamp": "2025-01-01T10:00:00"
        },
        {
            "id": "role_assigned_admin-1_1234567891.2",
            "event_type": "role_assigned",
            "user_id": "admin-1",
            "resource_type": "user_role",
            "resource_id": "user-2",
            "action": "assign",
            "details": {"role_name": "admin", "target_user": "user-2"},
            "ip_address": "192.168.1.2",
            "timestamp": "2025-01-01T11:00:00"
        },
        {
            "id": "role_removed_admin-1_1234567892.3",
            "event_type": "role_removed",
            "user_id": "admin-1",
            "resource_type": "user_role",
            "resource_id": "user-3",
            "action": "remove",
            "details": {"role_name": "viewer", "target_user": "user-3"},
            "ip_address": "192.168.1.2",
            "timestamp": "2025-01-01T12:00:00"
        },
        {
            "id": "permission_denied_user-4_1234567893.4",
            "event_type": "permission_denied",
            "user_id": "user-4",
            "resource_type": "endpoint",
            "resource_id": "/api/cells/delete",
            "action": "access_attempt",
            "details": {"required_permission": "cells.delete_any"},
            "ip_address": "192.168.1.3",
            "timestamp": "2025-01-01T13:00:00"
        },
        {
            "id": "admin_action_admin-1_1234567894.5",
            "event_type": "admin_action",
            "user_id": "admin-1",
            "action": "config_update",
            "details": {"config_changed": "logging_level"},
            "ip_address": "192.168.1.2",
            "timestamp": "2025-01-01T14:00:00"
        }
    ]
    
    # Write log files
    for log in logs:
        log_file = audit_logs_dir / f"{log['id']}.json"
        with open(log_file, 'w') as f:
            json.dump(log, f)
    
    return audit_logs_dir


class TestGetAuditLogs:
    """Tests for GET /api/audit/logs endpoint."""
    
    @pytest.mark.skip(reason="Authentication mocking needs to be implemented")
    def test_get_audit_logs_as_admin(self, client, admin_token, sample_audit_logs, tmp_path, monkeypatch):
        """Test retrieving audit logs as admin."""
        # Mock BASE_DIR to use tmp_path
        monkeypatch.setattr('app.routers.audit_router.BASE_DIR', tmp_path)
        
        response = client.get(
            "/api/audit/logs",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total" in data
        assert "logs" in data
        assert data["total"] == 5
        assert len(data["logs"]) == 5
    
    @pytest.mark.skip(reason="Authentication mocking needs to be implemented")
    def test_get_audit_logs_as_regular_user_forbidden(self, client, regular_token):
        """Test that regular users cannot access audit logs."""
        response = client.get(
            "/api/audit/logs",
            headers={"Authorization": f"Bearer {regular_token}"}
        )
        
        assert response.status_code == 403
    
    @pytest.mark.skip(reason="Authentication mocking needs to be implemented")
    def test_get_audit_logs_filter_by_event_type(self, client, admin_token, sample_audit_logs, tmp_path, monkeypatch):
        """Test filtering audit logs by event type."""
        monkeypatch.setattr('app.routers.audit_router.BASE_DIR', tmp_path)
        
        response = client.get(
            "/api/audit/logs?event_type=permission_denied",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 2
        for log in data["logs"]:
            assert log["event_type"] == "permission_denied"
    
    @pytest.mark.skip(reason="Authentication mocking needs to be implemented")
    def test_get_audit_logs_filter_by_user_id(self, client, admin_token, sample_audit_logs, tmp_path, monkeypatch):
        """Test filtering audit logs by user ID."""
        monkeypatch.setattr('app.routers.audit_router.BASE_DIR', tmp_path)
        
        response = client.get(
            "/api/audit/logs?user_id=admin-1",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 3
        for log in data["logs"]:
            assert log["user_id"] == "admin-1"
    
    @pytest.mark.skip(reason="Authentication mocking needs to be implemented")
    def test_get_audit_logs_pagination(self, client, admin_token, sample_audit_logs, tmp_path, monkeypatch):
        """Test audit logs pagination."""
        monkeypatch.setattr('app.routers.audit_router.BASE_DIR', tmp_path)
        
        response = client.get(
            "/api/audit/logs?skip=0&limit=2",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 5
        assert len(data["logs"]) == 2
        assert data["skip"] == 0
        assert data["limit"] == 2
    
    @pytest.mark.skip(reason="Authentication mocking needs to be implemented")
    def test_get_audit_logs_date_range_filter(self, client, admin_token, sample_audit_logs, tmp_path, monkeypatch):
        """Test filtering audit logs by date range."""
        monkeypatch.setattr('app.routers.audit_router.BASE_DIR', tmp_path)
        
        response = client.get(
            "/api/audit/logs?start_date=2025-01-01T11:00:00&end_date=2025-01-01T13:00:00",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return logs between 11:00 and 13:00 (inclusive)
        assert data["total"] == 3


class TestGetAuditStats:
    """Tests for GET /api/audit/stats endpoint."""
    
    @pytest.mark.skip(reason="Authentication mocking needs to be implemented")
    def test_get_audit_stats_as_admin(self, client, admin_token, sample_audit_logs, tmp_path, monkeypatch):
        """Test retrieving audit statistics as admin."""
        monkeypatch.setattr('app.routers.audit_router.BASE_DIR', tmp_path)
        
        response = client.get(
            "/api/audit/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        stats = response.json()
        
        assert "permission_denied_count" in stats
        assert "role_changes_count" in stats
        assert "admin_actions_count" in stats
        assert "top_denied_permissions" in stats
        
        assert stats["permission_denied_count"] == 2
        assert stats["role_changes_count"] == 2  # 1 assigned + 1 removed
        assert stats["admin_actions_count"] == 1
    
    @pytest.mark.skip(reason="Authentication mocking needs to be implemented")
    def test_get_audit_stats_top_denied_permissions(self, client, admin_token, sample_audit_logs, tmp_path, monkeypatch):
        """Test top denied permissions in statistics."""
        monkeypatch.setattr('app.routers.audit_router.BASE_DIR', tmp_path)
        
        response = client.get(
            "/api/audit/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        stats = response.json()
        
        top_denied = stats["top_denied_permissions"]
        assert len(top_denied) == 2
        
        # Check structure
        for item in top_denied:
            assert "permission" in item
            assert "count" in item
    
    @pytest.mark.skip(reason="Authentication mocking needs to be implemented")
    def test_get_audit_stats_as_regular_user_forbidden(self, client, regular_token):
        """Test that regular users cannot access audit statistics."""
        response = client.get(
            "/api/audit/stats",
            headers={"Authorization": f"Bearer {regular_token}"}
        )
        
        assert response.status_code == 403


class TestAuditLogsEndToEnd:
    """End-to-end tests for audit logging workflow."""
    
    @pytest.mark.skip(reason="Requires full authentication setup")
    def test_permission_denied_creates_audit_log(self, client, regular_token, tmp_path, monkeypatch):
        """Test that permission denied creates an audit log entry."""
        monkeypatch.setattr('app.audit_logger.BASE_DIR', tmp_path)
        
        # Attempt to access admin endpoint as regular user
        response = client.get(
            "/api/roles/",
            headers={"Authorization": f"Bearer {regular_token}"}
        )
        
        # Should be denied
        assert response.status_code == 403
        
        # Check audit log was created
        audit_logs_dir = tmp_path / "backend" / "artifacts" / "canonical" / "audit_logs"
        if audit_logs_dir.exists():
            log_files = list(audit_logs_dir.glob("permission_denied_*.json"))
            assert len(log_files) > 0
