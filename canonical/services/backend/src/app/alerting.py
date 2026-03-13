"""
Alerting module for security-critical events.

Provides integration with Slack webhooks for real-time alerting
on security-sensitive operations and anomalous behavior.

Technical naming follows Rule 4.3 (English for all technical identifiers).
"""

import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Slack webhook URL from environment
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL")


def send_alert(title: str, message: str, severity: str = "warning") -> bool:
    """
    Send alert to Slack webhook.

    Args:
        title: Alert title
        message: Alert message body
        severity: Alert severity level (info, warning, error)

    Returns:
        True if alert was sent successfully, False otherwise
    """
    if not SLACK_WEBHOOK:
        logger.debug("SLACK_WEBHOOK_URL not configured, skipping alert")
        return False

    # Map severity to color
    color_map = {
        "info": "#36a64f",  # Green
        "warning": "#ff9900",  # Orange
        "error": "#ff0000",  # Red
    }
    color = color_map.get(severity, "#cccccc")

    # Build Slack attachment payload
    payload = {
        "attachments": [
            {"color": color, "title": title, "text": message, "ts": int(time.time())}
        ]
    }

    try:
        response = requests.post(
            SLACK_WEBHOOK, json=payload, timeout=5
        )  # 5 second timeout
        response.raise_for_status()

        logger.info("Alert sent successfully: %s", title)
        return True

    except requests.exceptions.RequestException as e:
        logger.error("Failed to send alert to Slack: %s", e)
        return False


def alert_admin_role_assigned(
    admin_id: str, user_id: str, ip_address: Optional[str] = None
) -> None:
    """
    Alert when admin role is assigned to a user.

    This is a critical security event that should always be monitored.

    Args:
        admin_id: ID of the admin who assigned the role
        user_id: ID of the user who received admin role
        ip_address: IP address of the request
    """
    title = "⚠️ Admin Role Assigned"
    message = (
        f"User `{user_id}` was assigned **admin** role by `{admin_id}`.\n"
        f"IP Address: {ip_address or 'unknown'}\n"
        f"Time: <t:{int(time.time())}:F>"
    )

    send_alert(title, message, severity="warning")


def alert_high_permission_denials(count: int, time_window_minutes: int = 5) -> None:
    """
    Alert when there are too many permission denials in a short time.

    This may indicate an attack or misconfiguration.

    Args:
        count: Number of permission denials
        time_window_minutes: Time window in minutes
    """
    title = "🚨 High Rate of Permission Denials"
    message = (
        f"Detected **{count}** permission denials (403 Forbidden) "
        f"in the last {time_window_minutes} minutes.\n"
        f"This may indicate an attack or misconfiguration."
    )

    send_alert(title, message, severity="error")


def alert_role_removed(
    admin_id: str, user_id: str, role_name: str, ip_address: Optional[str] = None
) -> None:
    """
    Alert when a critical role is removed from a user.

    Args:
        admin_id: ID of the admin who removed the role
        user_id: ID of the user who lost the role
        role_name: Name of the role that was removed
        ip_address: IP address of the request
    """
    # Only alert for critical roles
    critical_roles = ["admin", "security_admin"]

    if role_name not in critical_roles:
        return

    title = f"⚠️ {role_name.capitalize()} Role Removed"
    message = (
        f"User `{user_id}` lost **{role_name}** role (removed by `{admin_id}`).\n"
        f"IP Address: {ip_address or 'unknown'}\n"
        f"Time: <t:{int(time.time())}:F>"
    )

    send_alert(title, message, severity="warning")
