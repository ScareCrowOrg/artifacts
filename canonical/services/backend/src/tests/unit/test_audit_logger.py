"""
Unit tests for audit logging module.

Tests audit log creation, persistence, and structured logging.
"""

import pytest
import os
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

from app.audit_logger import (
    AuditLog,
    log_permission_denied,
    log_role_assigned,
    log_role_removed,
    log_admin_action,
    log_audit_event,
    _persist_audit_log,
    _flush_audit_buffer,
    _schedule_persist_audit_log,
    _reset_audit_buffer_for_testing
)


# Test fixtures
@pytest.fixture
def temp_logs_dir(tmp_path):
    """Create a temporary logs directory."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    return logs_dir


@pytest.fixture
def temp_artifacts_dir(tmp_path):
    """Create a temporary artifacts directory."""
    artifacts_dir = tmp_path / "artifacts" / "runtime" / "audit_logs"
    artifacts_dir.mkdir(parents=True)
    return artifacts_dir


class TestAuditLog:
    """Tests for AuditLog class."""
    
    def test_audit_log_creation(self):
        """Test creating an AuditLog instance."""
        log = AuditLog(
            event_type="permission_denied",
            user_id="user-123",
            resource_type="endpoint",
            resource_id="/api/admin",
            action="access_attempt",
            details={"required_permission": "admin.access"},
            ip_address="192.168.1.1"
        )
        
        assert log.event_type == "permission_denied"
        assert log.user_id == "user-123"
        assert log.resource_type == "endpoint"
        assert log.resource_id == "/api/admin"
        assert log.action == "access_attempt"
        assert log.details == {"required_permission": "admin.access"}
        assert log.ip_address == "192.168.1.1"
        assert log.timestamp is not None
    
    def test_audit_log_to_dict(self):
        """Test converting AuditLog to dictionary."""
        log = AuditLog(
            event_type="role_assigned",
            user_id="admin-1",
            resource_type="user_role",
            resource_id="user-123",
            action="assign",
            details={"role_name": "admin"},
            ip_address="192.168.1.1"
        )
        
        log_dict = log.to_dict()
        
        assert log_dict["event_type"] == "role_assigned"
        assert log_dict["user_id"] == "admin-1"
        assert log_dict["resource_type"] == "user_role"
        assert log_dict["resource_id"] == "user-123"
        assert log_dict["action"] == "assign"
        assert log_dict["details"]["role_name"] == "admin"
        assert log_dict["ip_address"] == "192.168.1.1"
        assert "timestamp" in log_dict
    
    def test_audit_log_optional_fields(self):
        """Test AuditLog with minimal fields."""
        log = AuditLog(
            event_type="admin_action",
            user_id="admin-1"
        )
        
        assert log.event_type == "admin_action"
        assert log.user_id == "admin-1"
        assert log.resource_type is None
        assert log.resource_id is None
        assert log.action is None
        assert log.details == {}
        assert log.ip_address is None


class TestPermissionDeniedLogging:
    """Tests for permission denied logging."""
    
    @patch('app.audit_logger._schedule_persist_audit_log_sync')
    @patch('app.audit_logger.audit_logger')
    def test_log_permission_denied(self, mock_logger, mock_schedule):
        """Test logging permission denied event."""
        log_permission_denied(
            user_id="user-123",
            required_permission="cells.delete",
            endpoint="/api/cells/123",
            ip_address="192.168.1.1"
        )
        
        # Check schedule was called
        assert mock_schedule.called
        
        # Check logger was called with warning level
        assert mock_logger.warning.called
        call_args = mock_logger.warning.call_args[0][0]
        assert "PERMISSION_DENIED" in call_args
        assert "user=user-123" in call_args
        assert "permission=cells.delete" in call_args
        assert "endpoint=/api/cells/123" in call_args
    
    @patch('app.audit_logger._schedule_persist_audit_log_sync')
    def test_log_permission_denied_persistence(self, mock_schedule):
        """Test that permission denied logs are scheduled for persistence correctly."""
        log_permission_denied(
            user_id="user-123",
            required_permission="admin.access",
            endpoint="/api/admin/config",
            ip_address="10.0.0.1"
        )
        
        # Verify schedule was called
        assert mock_schedule.called
        
        # Get the call arguments
        call_args = mock_schedule.call_args
        audit_log = call_args[0][0]
        
        assert audit_log.event_type == "permission_denied"
        assert audit_log.user_id == "user-123"
        assert audit_log.resource_type == "endpoint"
        assert audit_log.resource_id == "/api/admin/config"
        assert audit_log.details["required_permission"] == "admin.access"
        assert audit_log.ip_address == "10.0.0.1"


class TestRoleAssignmentLogging:
    """Tests for role assignment logging."""
    
    @patch('app.audit_logger.alerting')
    @patch('app.audit_logger._schedule_persist_audit_log_sync')
    @patch('app.audit_logger.audit_logger')
    def test_log_role_assigned(self, mock_logger, mock_schedule, mock_alerting):
        """Test logging role assignment event."""
        log_role_assigned(
            admin_id="admin-1",
            user_id="user-123",
            role_name="user",
            ip_address="192.168.1.1"
        )
        
        # Check schedule was called
        assert mock_schedule.called
        
        # Check logger was called with info level
        assert mock_logger.info.called
        call_args = mock_logger.info.call_args[0][0]
        assert "ROLE_ASSIGNED" in call_args
        assert "admin=admin-1" in call_args
        assert "user=user-123" in call_args
        assert "role=user" in call_args
    
    @patch('app.audit_logger.alerting')
    @patch('app.audit_logger._schedule_persist_audit_log_sync')
    def test_log_admin_role_assigned_triggers_alert(self, mock_schedule, mock_alerting):
        """Test that assigning admin role triggers an alert."""
        log_role_assigned(
            admin_id="admin-1",
            user_id="user-123",
            role_name="admin",
            ip_address="192.168.1.1"
        )
        
        # Check alert was triggered
        assert mock_alerting.alert_admin_role_assigned.called
        call_args = mock_alerting.alert_admin_role_assigned.call_args[0]
        assert call_args[0] == "admin-1"
        assert call_args[1] == "user-123"
    
    @patch('app.audit_logger.alerting')
    @patch('app.audit_logger._schedule_persist_audit_log_sync')
    def test_log_regular_role_assigned_no_alert(self, mock_schedule, mock_alerting):
        """Test that assigning non-admin role does not trigger alert."""
        log_role_assigned(
            admin_id="admin-1",
            user_id="user-123",
            role_name="viewer",
            ip_address="192.168.1.1"
        )
        
        # Check alert was NOT triggered
        assert not mock_alerting.alert_admin_role_assigned.called


class TestRoleRemovalLogging:
    """Tests for role removal logging."""
    
    @patch('app.audit_logger.alerting')
    @patch('app.audit_logger._schedule_persist_audit_log_sync')
    @patch('app.audit_logger.audit_logger')
    def test_log_role_removed(self, mock_logger, mock_schedule, mock_alerting):
        """Test logging role removal event."""
        log_role_removed(
            admin_id="admin-1",
            user_id="user-123",
            role_name="user",
            ip_address="192.168.1.1"
        )
        
        # Check schedule was called
        assert mock_schedule.called
        
        # Check logger was called with warning level
        assert mock_logger.warning.called
        call_args = mock_logger.warning.call_args[0][0]
        assert "ROLE_REMOVED" in call_args
        assert "admin=admin-1" in call_args
        assert "user=user-123" in call_args
        assert "role=user" in call_args
        
        # Check alert was called
        assert mock_alerting.alert_role_removed.called


class TestAdminActionLogging:
    """Tests for admin action logging."""
    
    @patch('app.audit_logger._schedule_persist_audit_log_sync')
    @patch('app.audit_logger.audit_logger')
    def test_log_admin_action(self, mock_logger, mock_schedule):
        """Test logging generic admin action."""
        details = {
            "config_changed": "logging_level",
            "old_value": "INFO",
            "new_value": "DEBUG"
        }
        
        log_admin_action(
            admin_id="admin-1",
            action="config_update",
            details=details,
            ip_address="192.168.1.1"
        )
        
        # Check schedule was called
        assert mock_schedule.called
        
        # Check logger was called with info level
        assert mock_logger.info.called
        call_args = mock_logger.info.call_args[0][0]
        assert "ADMIN_ACTION" in call_args
        assert "admin=admin-1" in call_args
        assert "action=config_update" in call_args


class TestAuditEventLogging:
    """Tests for generic audit event logging."""
    
    @patch('app.audit_logger._schedule_persist_audit_log_sync')
    @patch('app.audit_logger.audit_logger')
    def test_log_audit_event_full_parameters(self, mock_logger, mock_schedule):
        """Test logging audit event with all parameters."""
        details = {
            "keys_deleted": 42,
            "success": True
        }
        
        log_audit_event(
            user_id="user-123",
            action="cache.invalidate_all",
            resource_type="system",
            resource_id="redis_cache",
            details=details,
            ip_address="192.168.1.1"
        )
        
        # Check schedule was called
        assert mock_schedule.called
        
        # Check logger was called with info level
        assert mock_logger.info.called
        call_args = mock_logger.info.call_args[0][0]
        assert "AUDIT_EVENT" in call_args
        assert "user=user-123" in call_args
        assert "action=cache.invalidate_all" in call_args
        assert "resource=system/redis_cache" in call_args
    
    @patch('app.audit_logger._schedule_persist_audit_log_sync')
    def test_log_audit_event_persistence(self, mock_schedule):
        """Test that audit events are scheduled for persistence correctly."""
        log_audit_event(
            user_id="admin-1",
            action="cache.invalidate_all",
            resource_type="system",
            resource_id="redis_cache",
            details={"keys_deleted": 10},
            ip_address="10.0.0.1"
        )
        
        # Verify schedule was called
        assert mock_schedule.called
        
        # Get the call arguments
        call_args = mock_schedule.call_args
        audit_log = call_args[0][0]
        
        assert audit_log.event_type == "audit_event"
        assert audit_log.user_id == "admin-1"
        assert audit_log.resource_type == "system"
        assert audit_log.resource_id == "redis_cache"
        assert audit_log.action == "cache.invalidate_all"
        assert audit_log.details["keys_deleted"] == 10
        assert audit_log.ip_address == "10.0.0.1"
    
    @patch('app.audit_logger._schedule_persist_audit_log_sync')
    @patch('app.audit_logger.audit_logger')
    def test_log_audit_event_minimal_parameters(self, mock_logger, mock_schedule):
        """Test logging audit event with minimal required parameters."""
        log_audit_event(
            user_id="user-456",
            action="data.export",
            resource_type="data",
            resource_id="dataset-123"
        )
        
        # Check schedule was called
        assert mock_schedule.called
        
        # Get the scheduled audit log
        call_args = mock_schedule.call_args
        audit_log = call_args[0][0]
        
        assert audit_log.user_id == "user-456"
        assert audit_log.action == "data.export"
        assert audit_log.resource_type == "data"
        assert audit_log.resource_id == "dataset-123"
        assert audit_log.details == {}
        assert audit_log.ip_address is None


class TestPersistAuditLog:
    """Tests for audit log persistence."""
    
    @pytest.mark.asyncio
    async def test_persist_audit_log_success(self):
        """Test successful audit log persistence."""
        from unittest.mock import AsyncMock, patch
        
        log = AuditLog(
            event_type="permission_denied",
            user_id="user-123",
            resource_type="endpoint",
            resource_id="/api/test"
        )
        
        with patch('app.audit_logger.db') as mock_db:
            mock_db.insert = AsyncMock()
            result = await _persist_audit_log(log)
            
            # Check db.insert was called
            assert mock_db.insert.called
            
            # Check arguments
            call_args = mock_db.insert.call_args
            collection = call_args[0][0]
            assert collection == "audit_logs"
            assert result is True
    
    @pytest.mark.asyncio
    async def test_persist_audit_log_retry_on_failure(self):
        """Test that persistence retries on failure."""
        from unittest.mock import Mock, patch
        from app.audit_logger import RETRY_COUNT
        
        log = AuditLog(
            event_type="permission_denied",
            user_id="user-123"
        )
        
        with patch('app.audit_logger.db') as mock_db:
            with patch('app.audit_logger.audit_logger') as mock_logger:
                # Make db.insert fail twice then succeed (use Mock not AsyncMock since db.insert is sync)
                mock_db.insert = Mock(side_effect=[Exception("DB error"), Exception("DB error"), None])
                
                result = await _persist_audit_log(log, retry_count=RETRY_COUNT)
                
                # Check that it retried and eventually succeeded
                assert mock_db.insert.call_count == RETRY_COUNT
                assert result is True
                
                # Check warning was logged for retries
                assert mock_logger.warning.called
    
    @pytest.mark.asyncio
    async def test_persist_audit_log_failure_after_retries(self):
        """Test that persistence returns False after all retries fail."""
        from unittest.mock import Mock, patch
        from app.audit_logger import RETRY_COUNT
        
        log = AuditLog(
            event_type="permission_denied",
            user_id="user-123"
        )
        
        with patch('app.audit_logger.db') as mock_db:
            with patch('app.audit_logger.audit_logger') as mock_logger:
                # Make db.insert always fail (use Mock not AsyncMock since db.insert is sync)
                mock_db.insert = Mock(side_effect=Exception("Database error"))
                
                result = await _persist_audit_log(log, retry_count=RETRY_COUNT)
                
                # Check that it tried all retries
                assert mock_db.insert.call_count == RETRY_COUNT
                assert result is False
                
                # Check error was logged
                assert mock_logger.error.called


class TestAuditBuffering:
    """Tests for audit log buffering and flushing."""
    
    def setup_method(self):
        """Reset buffer before each test."""
        _reset_audit_buffer_for_testing()
    
    def teardown_method(self):
        """Clean up buffer after each test."""
        _reset_audit_buffer_for_testing()
    
    @pytest.mark.asyncio
    async def test_flush_audit_buffer(self):
        """Test flushing audit log buffer."""
        from unittest.mock import AsyncMock, patch
        import app.audit_logger as audit_logger_module
        
        # Create test logs
        log1 = AuditLog(event_type="test1", user_id="user1")
        log2 = AuditLog(event_type="test2", user_id="user2")
        
        # Add to buffer
        audit_logger_module._audit_log_buffer = [log1, log2]
        
        with patch('app.audit_logger._persist_audit_log', new_callable=AsyncMock) as mock_persist:
            mock_persist.return_value = True
            
            await _flush_audit_buffer()
            
            # Check all logs were persisted
            assert mock_persist.call_count == 2
            
            # Check buffer was cleared
            assert len(audit_logger_module._audit_log_buffer) == 0
    
    @pytest.mark.asyncio
    async def test_schedule_persist_audit_log_adds_to_buffer(self):
        """Test that scheduling log persistence adds to buffer."""
        import app.audit_logger as audit_logger_module
        
        # Ensure buffer is empty
        _reset_audit_buffer_for_testing()
        
        log = AuditLog(event_type="test", user_id="user1")
        
        await _schedule_persist_audit_log(log)
        
        # Check log was added to buffer
        assert len(audit_logger_module._audit_log_buffer) == 1
        assert audit_logger_module._audit_log_buffer[0].event_type == "test"
    
    @pytest.mark.asyncio
    async def test_buffer_auto_flush_on_size(self):
        """Test that buffer auto-flushes when reaching threshold."""
        from unittest.mock import AsyncMock, patch
        from app.audit_logger import BUFFER_FLUSH_THRESHOLD
        
        # Ensure buffer is empty
        _reset_audit_buffer_for_testing()
        
        with patch('app.audit_logger._flush_audit_buffer', new_callable=AsyncMock) as mock_flush:
            # Add logs to reach threshold
            for i in range(BUFFER_FLUSH_THRESHOLD):
                log = AuditLog(event_type=f"test{i}", user_id=f"user{i}")
                await _schedule_persist_audit_log(log)
            
            # Check flush was called
            assert mock_flush.called

