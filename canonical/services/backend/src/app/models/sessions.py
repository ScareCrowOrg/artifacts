"""
Session models for user session management.

Models for session creation, tracking, and token management.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .base import generate_uuid


class Session(BaseModel):
    """User session model."""

    id: str = Field(default_factory=generate_uuid, description="Session UUID")
    user_id: str = Field(..., description="User UUID")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")
    active: bool = Field(default=True, description="Whether the session is active")
    token: Optional[str] = Field(None, description="Session JWT token")


class CreateSessionRequest(BaseModel):
    """Request to create a new session."""

    user_id: str = Field(..., description="User UUID")


class CreateSessionResponse(BaseModel):
    """Session creation response."""

    session: Session = Field(..., description="Created session data")
    token: str = Field(..., description="Session JWT token")
