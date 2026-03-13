"""
Event Bus models for distributed messaging.

Defines message envelope format and event-related data structures
for WebSocket and Redis pub/sub communication.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .base import generate_uuid


class EventTopic(str, Enum):
    """Supported event topics for the distributed event bus."""

    # Agent request topics (client → backend)
    AGENT_REQUEST_FILE_ACCESS = "agent/request/file_access"
    AGENT_REQUEST_FILE_WRITE = "agent/request/file_write"
    AGENT_REQUEST_EXEC = "agent/request/exec"

    # Agent response topics (backend → client)
    AGENT_RESPONSE_FILE_DATA = "agent/response/file_data"
    AGENT_RESPONSE_FILE_WRITTEN = "agent/response/file_written"
    AGENT_RESPONSE_EXEC_RESULT = "agent/response/exec_result"
    AGENT_RESPONSE_ERROR = "agent/response/error"

    # Session state topics
    SESSION_STATE_UPDATE = "session/state/update"
    SESSION_STATE_SYNCED = "session/state/synced"
    SESSION_STATE_ERROR = "session/state/error"

    # Repository asset topics
    REPO_ASSET_CHANGED = "repo/asset/changed"
    REPO_ASSET_DELETED = "repo/asset/deleted"

    # System event topics
    SYSTEM_EVENT_ERROR = "system/event/error"
    SYSTEM_EVENT_LOG = "system/event/log"
    SYSTEM_EVENT_HEARTBEAT = "system/event/heartbeat"
    SYSTEM_EVENT_HANDSHAKE_REQUEST = "system/event/handshake_request"
    SYSTEM_EVENT_HANDSHAKE_RESPONSE = "system/event/handshake_response"

    # Cell Factory generation topics (MVP 1)
    CELL_GENERATE_REQUEST = "cell/generate/request"
    CELL_GENERATE_PROGRESS = "cell/generate/progress"
    CELL_GENERATE_COMPLETE = "cell/generate/complete"
    CELL_GENERATE_ERROR = "cell/generate/error"

    # Cell Factory validation topics (MVP 1)
    CELL_VALIDATE_STARTED = "cell/validate/started"
    CELL_VALIDATE_ERRORS = "cell/validate/errors"
    CELL_VALIDATE_AUTO_CORRECT = "cell/validate/auto_correct"
    CELL_VALIDATE_COMPLETE = "cell/validate/complete"

    # Cell Factory promotion topics (MVP 1)
    CELL_PROMOTE_REQUEST = "cell/promote/request"
    CELL_PROMOTE_PROGRESS = "cell/promote/progress"
    CELL_PROMOTE_COMPLETE = "cell/promote/complete"
    CELL_PROMOTE_ERROR = "cell/promote/error"

    # Cell Factory transmutation topics (MVP 2 - Recursive Transmutation)
    CELL_TRANSMUTE_PLAN = "cell/transmute/plan"

    # Pipeline Monitoring topics (Sprint 3)
    MONITORING_HEALTH_UPDATE = "monitoring/health/update"
    MONITORING_METRICS_UPDATE = "monitoring/metrics/update"
    MONITORING_PREREQUISITE_UPDATE = "monitoring/prerequisite/update"
    MONITORING_ALERT_TRIGGERED = "monitoring/alert/triggered"
    MONITORING_ALERT_RESOLVED = "monitoring/alert/resolved"


class MessageEnvelope(BaseModel):
    """
    Standard message envelope for all events in the distributed event bus.

    This format ensures consistency across WebSocket and Redis pub/sub channels.
    All events must be wrapped in this envelope.
    """

    trace_id: str = Field(
        default_factory=generate_uuid,
        description="Unique identifier for tracing this message through the system",
    )

    source: str = Field(
        default="backend-service",
        description="Source of the message (e.g., 'extension-wasm-sidecar', 'backend-worker')",
        min_length=1,
        max_length=100,
    )

    topic: str = Field(
        ...,
        description="Event topic (e.g., 'agent/request/file_access')",
        min_length=1,
        max_length=100,
    )

    payload: Dict[str, Any] = Field(
        default_factory=dict, description="Event payload data"
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Message timestamp (UTC)"
    )

    correlation_id: Optional[str] = Field(
        None,
        description="ID of the original request this message relates to (for responses)",
    )

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


class FileAccessRequest(BaseModel):
    """Payload for agent/request/file_access topic."""

    path: str = Field(
        ...,
        description="Relative path to the file (from repository root)",
        min_length=1,
    )

    encoding: str = Field(default="utf-8", description="File encoding")


class FileAccessResponse(BaseModel):
    """Payload for agent/response/file_data topic."""

    path: str = Field(..., description="Path to the file")

    content: str = Field(..., description="File content")

    size: int = Field(..., description="File size in bytes")

    encoding: str = Field(default="utf-8", description="File encoding used")


class ErrorResponse(BaseModel):
    """Payload for agent/response/error topic."""

    error_code: str = Field(..., description="Error code identifier")

    message: str = Field(..., description="Human-readable error message")

    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )


class HeartbeatEvent(BaseModel):
    """Payload for system/event/heartbeat topic."""

    source: str = Field(..., description="Source identifier sending the heartbeat")

    uptime_seconds: float = Field(..., description="Uptime in seconds")

    status: str = Field(default="healthy", description="Service status")
