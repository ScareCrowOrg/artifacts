"""
Audit logging module for RBAC permissions tracking.

Provides comprehensive audit logging for security-sensitive operations
including role changes, permission denials, and administrative actions.

Technical naming follows Rule 4.3 (English for all technical identifiers).
Logs are structured for easy parsing and analysis in monitoring systems.

RELIABILITY: This module now includes enhanced persistence guarantees:
- Buffered audit log storage with periodic flush
- Graceful shutdown handler to ensure logs are persisted
- Retry mechanism for failed log persistence
"""

import logging
import os
import asyncio
import atexit
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

from .database import db
from .config import BASE_DIR
from . import alerting

# Configuration constants
FLUSH_INTERVAL_SECONDS = 5.0
BUFFER_FLUSH_THRESHOLD = 10
RETRY_COUNT = 3
RETRY_BASE_DELAY = 0.1
RETRY_BACKOFF_MULTIPLIER = 2

# Configure structured audit logger
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# Ensure logs directory exists
LOGS_DIR = BASE_DIR / "backend" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Handler for audit log file
audit_log_path = LOGS_DIR / "audit.log"
file_handler = logging.FileHandler(audit_log_path)
file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
audit_logger.addHandler(file_handler)

# Global buffer for audit logs pending persistence
_audit_log_buffer: List["AuditLog"] = []
_buffer_lock = asyncio.Lock()
_shutdown_event = asyncio.Event()
_background_task: Optional[asyncio.Task] = None


class AuditLog:
    """
    Model for audit log entry.

    Attributes:
        event_type: Type of event (permission_denied, role_assigned, etc.)
        user_id: ID of the user performing/affected by the action
        resource_type: Type of resource accessed (endpoint, user_role, etc.)
        resource_id: ID of the resource
        action: Action performed (access_attempt, assign, remove, etc.)
        details: Additional event details
        ip_address: IP address of the request
        timestamp: UTC timestamp of the event
    """

    def __init__(
        self,
        event_type: str,
        user_id: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ):
        self.event_type = event_type
        self.user_id = user_id
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.action = action
        self.details = details or {}
        self.ip_address = ip_address
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "event_type": self.event_type,
            "user_id": self.user_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "details": self.details,
            "ip_address": self.ip_address,
            "timestamp": self.timestamp,
        }


async def _persist_audit_log(log: AuditLog, retry_count: int = RETRY_COUNT) -> bool:
    """
    Persist audit log to database with retry mechanism.

    Args:
        log: AuditLog instance to persist
        retry_count: Number of retries on failure (default: RETRY_COUNT)

    Returns:
        bool: True if persistence succeeded, False otherwise
    """
    for attempt in range(retry_count):
        try:
            # For JSON database, we need to create a simple dict with an ID
            log_dict = log.to_dict()

            # Generate unique ID for the log entry
            log_id = f"{log.event_type}_{log.user_id}_{datetime.utcnow().timestamp()}"
            log_dict["id"] = log_id

            # Since db operations expect specific patterns, we'll store in a simple way
            # This will be stored in the canonical artifacts directory
            from pydantic import BaseModel

            class AuditLogModel(BaseModel):
                id: str
                event_type: str
                user_id: str
                resource_type: Optional[str] = None
                resource_id: Optional[str] = None
                action: Optional[str] = None
                details: Dict[str, Any] = {}
                ip_address: Optional[str] = None
                timestamp: str

            audit_model = AuditLogModel(**log_dict)
            # Audit logs are runtime artifacts, not canonical
            db.insert("audit_logs", audit_model, current_user=SYSTEM_USER)
            return True

        except Exception as e:
            if attempt < retry_count - 1:
                # Wait before retry with exponential backoff
                await asyncio.sleep(RETRY_BASE_DELAY * (RETRY_BACKOFF_MULTIPLIER**attempt))
                audit_logger.warning("Retrying audit log persistence (attempt %s/%s): %s", attempt + 2, retry_count, e)
            else:
                # Log persistence failures should not break the application
                audit_logger.error("Failed to persist audit log after %s attempts: %s", retry_count, e, exc_info=True)
                return False

    return False


async def _flush_audit_buffer() -> None:
    """
    Flush all pending audit logs from buffer to database.

    This function ensures all buffered logs are persisted before shutdown.
    """
    global _audit_log_buffer

    async with _buffer_lock:
        if not _audit_log_buffer:
            return

        logs_to_persist = _audit_log_buffer.copy()
        _audit_log_buffer.clear()

    # Persist all logs
    success_count = 0
    for log in logs_to_persist:
        if await _persist_audit_log(log):
            success_count += 1

    if success_count < len(logs_to_persist):
        audit_logger.warning(
            "Flushed audit buffer: %s/%s logs persisted successfully",
            success_count, len(logs_to_persist)
        )
    else:
        audit_logger.info("Flushed audit buffer: %s logs persisted", success_count)


async def _background_flush_task() -> None:
    """
    Background task that periodically flushes the audit log buffer.

    Runs every FLUSH_INTERVAL_SECONDS or until shutdown is triggered.
    """
    while not _shutdown_event.is_set():
        try:
            # Wait for FLUSH_INTERVAL_SECONDS or until shutdown
            await asyncio.wait_for(_shutdown_event.wait(), timeout=FLUSH_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            # Timeout is expected - flush the buffer
            await _flush_audit_buffer()
        except Exception as e:
            audit_logger.error("Error in background flush task: %s", e, exc_info=True)

    # Final flush on shutdown
    await _flush_audit_buffer()
    audit_logger.info("Background audit flush task terminated")


def start_audit_logger_background_task() -> None:
    """
    Start the background task for periodic audit log flushing.

    This should be called during application startup.
    """
    global _background_task

    try:
        loop = asyncio.get_event_loop()
        _background_task = loop.create_task(_background_flush_task())
        audit_logger.info("Started background audit log flush task")
    except Exception as e:
        audit_logger.error("Failed to start background audit flush task: %s", e, exc_info=True)


def stop_audit_logger_background_task() -> None:
    """
    Stop the background task and flush remaining logs.

    This should be called during application shutdown.
    """
    global _background_task

    _shutdown_event.set()

    if _background_task and not _background_task.done():
        try:
            # Wait for the task to complete gracefully
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, the task will complete on its own
                audit_logger.info("Signaled background audit flush task to stop")
            else:
                # If loop is not running, wait for task completion
                loop.run_until_complete(_background_task)
                audit_logger.info("Stopped background audit flush task")
        except Exception as e:
            audit_logger.error("Error stopping background audit flush task: %s", e, exc_info=True)


def _safe_shutdown_handler() -> None:
    """
    Safe shutdown handler that ensures audit logs are flushed.

    Wrapped in try-except to prevent exceptions from blocking application exit.
    """
    try:
        if not _shutdown_event.is_set():
            stop_audit_logger_background_task()
    except Exception as e:
        # Log but don't prevent shutdown
        try:
            audit_logger.error("Error in shutdown handler: %s", e, exc_info=True)
        except:
            # If even logging fails, silently continue shutdown
            pass


def _reset_audit_buffer_for_testing() -> None:
    """
    Reset audit buffer state for testing purposes.

    WARNING: This is for testing only. Do not use in production code.
    """
    global _audit_log_buffer
    _audit_log_buffer = []


# Register shutdown handler
atexit.register(_safe_shutdown_handler)


async def _schedule_persist_audit_log(log: AuditLog) -> None:
    """
    Schedule async persistence of audit log using buffered approach.

    This adds the log to a buffer that is periodically flushed to ensure
    persistence even in case of unexpected shutdown.

    Args:
        log: AuditLog instance to persist
    """
    global _audit_log_buffer

    async with _buffer_lock:
        _audit_log_buffer.append(log)

    # If buffer is getting large, flush immediately
    if len(_audit_log_buffer) >= BUFFER_FLUSH_THRESHOLD:
        await _flush_audit_buffer()


def _schedule_persist_audit_log_sync(log: AuditLog) -> None:
    """
    Synchronous wrapper to schedule audit log persistence.

    This helper function allows synchronous callers to trigger async
    audit log persistence without blocking.

    Args:
        log: AuditLog instance to persist
    """
    try:
        # Try to get the current event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If event loop is running, create a task
            asyncio.create_task(_schedule_persist_audit_log(log))
        else:
            # If no event loop is running, run until complete
            loop.run_until_complete(_schedule_persist_audit_log(log))
    except RuntimeError:
        # No event loop available, create a new one
        asyncio.run(_schedule_persist_audit_log(log))
    except Exception as e:
        # If scheduling fails, log locally but don't fail
        audit_logger.error("Failed to schedule audit log persistence: %s", e, exc_info=True)


def log_permission_denied(
    user_id: str, required_permission: str, endpoint: str, ip_address: Optional[str] = None
) -> None:
    """
    Log access denied event.

    Called when a user attempts to access a resource without sufficient permissions.

    Args:
        user_id: ID of the user who was denied access
        required_permission: Permission(s) that were required
        endpoint: Endpoint that was accessed
        ip_address: IP address of the request
    """
    log = AuditLog(
        event_type="permission_denied",
        user_id=user_id,
        resource_type="endpoint",
        resource_id=endpoint,
        action="access_attempt",
        details={"required_permission": required_permission, "reason": "insufficient_permissions"},
        ip_address=ip_address,
    )

    # Persist to database using buffered approach
    _schedule_persist_audit_log_sync(log)

    # Structured log for parsing
    audit_logger.warning(
        "PERMISSION_DENIED | user=%s | permission=%s | endpoint=%s | ip=%s",
        user_id, required_permission, endpoint, ip_address
    )


def log_role_assigned(
    admin_id: str, user_id: str, role_name: str, ip_address: Optional[str] = None
) -> None:
    """
    Log role assignment event.

    Called when an admin assigns a role to a user.

    Args:
        admin_id: ID of the admin who assigned the role
        user_id: ID of the user who received the role
        role_name: Name of the role that was assigned
        ip_address: IP address of the request
    """
    log = AuditLog(
        event_type="role_assigned",
        user_id=admin_id,
        resource_type="user_role",
        resource_id=user_id,
        action="assign",
        details={"role_name": role_name, "target_user": user_id},
        ip_address=ip_address,
    )

    # Persist to database using buffered approach
    _schedule_persist_audit_log_sync(log)

    # Structured log
    audit_logger.info("ROLE_ASSIGNED | admin=%s | user=%s | role=%s | ip=%s", admin_id, user_id, role_name, ip_address)

    # Alert if admin role was assigned
    if role_name == "admin":
        alerting.alert_admin_role_assigned(admin_id, user_id, ip_address)


def log_role_removed(
    admin_id: str, user_id: str, role_name: str, ip_address: Optional[str] = None
) -> None:
    """
    Log role removal event.

    Called when an admin removes a role from a user.

    Args:
        admin_id: ID of the admin who removed the role
        user_id: ID of the user who lost the role
        role_name: Name of the role that was removed
        ip_address: IP address of the request
    """
    log = AuditLog(
        event_type="role_removed",
        user_id=admin_id,
        resource_type="user_role",
        resource_id=user_id,
        action="remove",
        details={"role_name": role_name, "target_user": user_id},
        ip_address=ip_address,
    )

    # Persist to database using buffered approach
    _schedule_persist_audit_log_sync(log)

    # Structured log (warning level as this is a security-sensitive action)
    audit_logger.warning(
        "ROLE_REMOVED | admin=%s | user=%s | role=%s | ip=%s",
        admin_id, user_id, role_name, ip_address
    )

    # Alert for critical role removals
    alerting.alert_role_removed(admin_id, user_id, role_name, ip_address)


def log_admin_action(
    admin_id: str, action: str, details: Dict[str, Any], ip_address: Optional[str] = None
) -> None:
    """
    Log generic administrative action.

    Called for security-sensitive administrative operations.

    Args:
        admin_id: ID of the admin who performed the action
        action: Description of the action performed
        details: Additional details about the action
        ip_address: IP address of the request
    """
    log = AuditLog(
        event_type="admin_action",
        user_id=admin_id,
        action=action,
        details=details,
        ip_address=ip_address,
    )

    # Persist to database using buffered approach
    _schedule_persist_audit_log_sync(log)

    # Structured log
    audit_logger.info("ADMIN_ACTION | admin=%s | action=%s | details=%s | ip=%s", admin_id, action, details, ip_address)


def log_audit_event(
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    event_type: Optional[str] = None,
) -> None:
    """
    Log a generic audit event.

    This is a generic audit logging function that can be used for any type of event
    that doesn't fit into the more specific logging functions (log_permission_denied,
    log_role_assigned, etc.).

    Args:
        user_id: ID of the user performing the action
        action: Action being performed (e.g., "cache.invalidate_all", "data.export")
        resource_type: Type of resource (e.g., "system", "user", "data")
        resource_id: Identifier of the specific resource
        details: Additional event details
        ip_address: IP address of the request
        event_type: Type of event (defaults to "audit_event" if not specified)
    """
    log = AuditLog(
        event_type=event_type or "audit_event",
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        details=details or {},
        ip_address=ip_address,
    )

    # Persist to database using buffered approach
    _schedule_persist_audit_log_sync(log)

    # Structured log
    audit_logger.info(
        "AUDIT_EVENT | user=%s | action=%s | resource=%s/%s | ip=%s",
        user_id, action, resource_type, resource_id, ip_address
    )
