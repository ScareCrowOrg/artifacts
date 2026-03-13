"""
MongoDB schema definitions for log collection.

Defines the structure of log entries stored in MongoDB
for centralized logging and error tracking.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class LogEntrySchema(BaseModel):
    """Schema for a log entry."""

    log_id: str = Field(..., description="Unique log identifier")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Log timestamp (UTC)"
    )
    level: str = Field(..., description="Log level (error, warning, info, debug)")
    source: str = Field(
        ...,
        description="Source of the log (e.g., 'extension-wasm-sidecar', 'backend-worker')",
    )
    message: str = Field(..., description="Log message")
    stack_trace: Optional[str] = Field(None, description="Stack trace for errors")
    user_id: Optional[str] = Field(None, description="User ID associated with the log")
    client_id: Optional[str] = Field(
        None, description="Client ID associated with the log"
    )
    context: Optional[Dict[str, Any]] = Field(
        None, description="Additional context data"
    )

    class Config:
        """Pydantic config."""

        json_encoders = {datetime: lambda v: v.isoformat()}


# Indexes for logs collection
LOGS_INDEXES = [
    {"keys": [("timestamp", -1)], "name": "timestamp_idx", "background": True},
    {
        "keys": [("level", 1), ("timestamp", -1)],
        "name": "level_timestamp_idx",
        "background": True,
    },
    {
        "keys": [("user_id", 1), ("timestamp", -1)],
        "name": "user_timestamp_idx",
        "background": True,
    },
    {
        "keys": [("source", 1), ("timestamp", -1)],
        "name": "source_timestamp_idx",
        "background": True,
    },
    {
        "keys": [("timestamp", 1)],
        "name": "timestamp_ttl_idx",
        "background": True,
        "expireAfterSeconds": 2592000,  # 30 days
    },
]
