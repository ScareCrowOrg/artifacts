"""
Unit tests for alerting module.

Tests Slack webhook integration and alert triggers.
"""

import pytest
from unittest.mock import patch, MagicMock
import requests

from app.alerting import (
    send_alert,
    alert_admin_role_assigned,
    alert_high_permission_denials,
    alert_role_removed
)


class TestSendAlert:
    """Tests for send_alert function."""
    
    @patch('app.alerting.SLACK_WEBHOOK', 'https://hooks.slack.com/test')
    @patch('app.alerting.requests.post')
    def test_send_alert_success(self, mock_post):
        """Test successful alert sending."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        result = send_alert(
            title="Test Alert",
            message="Test message",
            severity="warning"
        )
        
        assert result is True
        assert mock_post.called
        
        # Check payload structure
        call_args = mock_post.call_args
        assert call_args[0][0] == 'https://hooks.slack.com/test'
        payload = call_args[1]['json']
        assert 'attachments' in payload
        assert payload['attachments'][0]['title'] == "Test Alert"
        assert payload['attachments'][0]['text'] == "Test message"
        assert payload['attachments'][0]['color'] == "#ff9900"  # warning color
    
    @patch.dict('os.environ', {}, clear=True)
    def test_send_alert_no_webhook_configured(self):
        """Test that alert is skipped when webhook is not configured."""
        result = send_alert(
            title="Test Alert",
            message="Test message"
        )
        
        assert result is False
    
    @patch('app.alerting.SLACK_WEBHOOK', 'https://hooks.slack.com/test')
    @patch('app.alerting.requests.post')
    def test_send_alert_with_info_severity(self, mock_post):
        """Test alert with info severity."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        send_alert(
            title="Info Alert",
            message="Info message",
            severity="info"
        )
        
        payload = mock_post.call_args[1]['json']
        assert payload['attachments'][0]['color'] == "#36a64f"  # info/green color
    
    @patch('app.alerting.SLACK_WEBHOOK', 'https://hooks.slack.com/test')
    @patch('app.alerting.requests.post')
    def test_send_alert_with_error_severity(self, mock_post):
        """Test alert with error severity."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        send_alert(
            title="Error Alert",
            message="Error message",
            severity="error"
        )
        
        payload = mock_post.call_args[1]['json']
        assert payload['attachments'][0]['color'] == "#ff0000"  # error/red color
    
    @patch.dict('os.environ', {'SLACK_WEBHOOK_URL': 'https://hooks.slack.com/test'})
    @patch('app.alerting.requests.post')
    def test_send_alert_request_failure(self, mock_post):
        """Test handling of request failure."""
        mock_post.side_effect = requests.exceptions.RequestException("Connection error")
        
        result = send_alert(
            title="Test Alert",
            message="Test message"
        )
        
        assert result is False
    
    @patch.dict('os.environ', {'SLACK_WEBHOOK_URL': 'https://hooks.slack.com/test'})
    @patch('app.alerting.requests.post')
    def test_send_alert_timeout(self, mock_post):
        """Test handling of timeout."""
        mock_post.side_effect = requests.exceptions.Timeout("Timeout")
        
        result = send_alert(
            title="Test Alert",
            message="Test message"
        )
        
        assert result is False


class TestAlertAdminRoleAssigned:
    """Tests for admin role assignment alert."""
    
    @patch('app.alerting.send_alert')
    def test_alert_admin_role_assigned(self, mock_send_alert):
        """Test alert when admin role is assigned."""
        alert_admin_role_assigned(
            admin_id="admin-1",
            user_id="user-123",
            ip_address="192.168.1.1"
        )
        
        assert mock_send_alert.called
        
        # Check arguments
        call_args = mock_send_alert.call_args
        title = call_args[0][0]
        message = call_args[0][1]
        severity = call_args[1]['severity']
        
        assert "Admin Role Assigned" in title
        assert "user-123" in message
        assert "admin-1" in message
        assert "192.168.1.1" in message
        assert severity == "warning"
    
    @patch('app.alerting.send_alert')
    def test_alert_admin_role_assigned_no_ip(self, mock_send_alert):
        """Test alert when admin role is assigned without IP address."""
        alert_admin_role_assigned(
            admin_id="admin-1",
            user_id="user-123"
        )
        
        assert mock_send_alert.called
        
        # Check message contains "unknown" for IP
        message = mock_send_alert.call_args[0][1]
        assert "unknown" in message.lower()


class TestAlertHighPermissionDenials:
    """Tests for high permission denial rate alert."""
    
    @patch('app.alerting.send_alert')
    def test_alert_high_permission_denials(self, mock_send_alert):
        """Test alert for high permission denial rate."""
        alert_high_permission_denials(count=150, time_window_minutes=5)
        
        assert mock_send_alert.called
        
        # Check arguments
        call_args = mock_send_alert.call_args
        title = call_args[0][0]
        message = call_args[0][1]
        severity = call_args[1]['severity']
        
        assert "High Rate of Permission Denials" in title
        assert "150" in message
        assert "5 minutes" in message
        assert severity == "error"


class TestAlertRoleRemoved:
    """Tests for role removal alert."""
    
    @patch('app.alerting.send_alert')
    def test_alert_admin_role_removed(self, mock_send_alert):
        """Test alert when admin role is removed."""
        alert_role_removed(
            admin_id="admin-1",
            user_id="user-123",
            role_name="admin",
            ip_address="192.168.1.1"
        )
        
        assert mock_send_alert.called
        
        # Check arguments
        call_args = mock_send_alert.call_args
        title = call_args[0][0]
        message = call_args[0][1]
        
        assert "Admin Role Removed" in title
        assert "user-123" in message
        assert "admin-1" in message
        assert "192.168.1.1" in message
    
    @patch('app.alerting.send_alert')
    def test_alert_security_admin_role_removed(self, mock_send_alert):
        """Test alert when security_admin role is removed."""
        alert_role_removed(
            admin_id="admin-1",
            user_id="user-123",
            role_name="security_admin",
            ip_address="192.168.1.1"
        )
        
        assert mock_send_alert.called
        
        # Check arguments
        title = mock_send_alert.call_args[0][0]
        assert "Security_admin Role Removed" in title
    
    @patch('app.alerting.send_alert')
    def test_no_alert_for_non_critical_role_removal(self, mock_send_alert):
        """Test that non-critical role removals don't trigger alerts."""
        alert_role_removed(
            admin_id="admin-1",
            user_id="user-123",
            role_name="viewer",
            ip_address="192.168.1.1"
        )
        
        # Should NOT send alert for non-critical roles
        assert not mock_send_alert.called
    
    @patch('app.alerting.send_alert')
    def test_no_alert_for_user_role_removal(self, mock_send_alert):
        """Test that user role removal doesn't trigger alert."""
        alert_role_removed(
            admin_id="admin-1",
            user_id="user-123",
            role_name="user",
            ip_address="192.168.1.1"
        )
        
        # Should NOT send alert for non-critical roles
        assert not mock_send_alert.called
