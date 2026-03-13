"""
Personal Access Token (PAT) and Platform Node models.

Models for service-to-service authentication and distributed node management.

Security Model:
- PAT tokens are JWT signed with Ed25519 private key (asymmetric cryptography).
- JWT is NEVER stored in the database — only metadata (jti, token_prefix, etc.).
- Validation is fully cryptographic: jwt.decode(token, public_key, algorithms=["EdDSA"]).
- Revocation tracked via jti blocklist (is_active=False).
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from .base import generate_uuid

# Available PAT scopes for service-to-service communication
AVAILABLE_SCOPES: List[str] = [
    "redis.read",
    "redis.write",
    "jobs.read",
    "jobs.dispatch",
    "jobs.cancel",
    "nodes.register",
    "nodes.heartbeat",
]


class PersonalAccessToken(BaseModel):
    """
    Personal Access Token (PAT) record.

    Stores only metadata — the JWT is never persisted.
    Revocation is performed by setting is_active=False and recording revoked_at.
    """

    id: str = Field(default_factory=generate_uuid, description="Unique PAT UUID")
    user_id: str = Field(..., description="Owner user UUID")
    name: str = Field(..., description="Human-readable token name (e.g. 'runner-prod')")
    token_prefix: str = Field(
        ...,
        description="First 8 characters of the raw JWT for UI display (identification only)",
    )
    jwt_jti: str = Field(
        ...,
        description="JWT 'jti' claim — unique token ID used for revocation tracking",
    )
    scopes: List[str] = Field(
        default_factory=list,
        description="List of granted scopes (e.g. ['redis.read', 'jobs.dispatch'])",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    expires_at: datetime = Field(
        ...,
        description="Expiration timestamp — matches JWT 'exp' claim",
    )
    last_used_at: Optional[datetime] = Field(
        None, description="Timestamp of last successful use (updated on every valid use)"
    )
    is_active: bool = Field(
        default=True, description="False when token is revoked"
    )
    revoked_at: Optional[datetime] = Field(
        None, description="Revocation timestamp (audit trail)"
    )
    environment: str = Field(
        default="development",
        description="Deployment environment: 'production', 'staging', or 'development'",
    )

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: List[str]) -> List[str]:
        """Validate that all provided scopes are recognised."""
        invalid = [s for s in value if s not in AVAILABLE_SCOPES]
        if invalid:
            raise ValueError(
                f"Unknown scopes: {invalid}. Available: {AVAILABLE_SCOPES}"
            )
        return value

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        allowed = {"production", "staging", "development"}
        if value not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return value


# ---------------------------------------------------------------------------
# Request / Response models for PAT endpoints
# ---------------------------------------------------------------------------


class CreatePATRequest(BaseModel):
    """Request body for POST /api/tokens."""

    name: str = Field(
        ..., min_length=1, max_length=128, description="Token name (e.g. 'runner-prod')"
    )
    scopes: List[str] = Field(
        default_factory=list, description="List of scopes to grant"
    )
    expires_in_days: int = Field(
        default=90, ge=1, le=365, description="Token validity in days (1–365)"
    )
    environment: str = Field(
        default="development",
        description="Deployment environment: 'production', 'staging', or 'development'",
    )

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: List[str]) -> List[str]:
        invalid = [s for s in value if s not in AVAILABLE_SCOPES]
        if invalid:
            raise ValueError(
                f"Unknown scopes: {invalid}. Available: {AVAILABLE_SCOPES}"
            )
        return value

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        allowed = {"production", "staging", "development"}
        if value not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return value


class CreatePATResponse(BaseModel):
    """
    Response for POST /api/tokens.

    ⚠️ WARNING: 'token' is shown ONCE only. Advise the user to copy it immediately.
    """

    token: str = Field(
        ...,
        description=(
            "Full PAT token (sv_pat_<jwt>). "
            "Shown ONCE — copy now, you won't see it again."
        ),
    )
    token_prefix: str = Field(..., description="First 8 chars of raw JWT (for UI)")
    pat_id: str = Field(..., description="PAT record UUID")
    expires_at: datetime = Field(..., description="Expiration timestamp")
    message: str = Field(
        default="Copy now. You won't see it again.",
        description="Security reminder",
    )


class PATSummary(BaseModel):
    """PAT metadata returned in list/get endpoints (no plaintext token)."""

    id: str
    name: str
    token_prefix: str
    scopes: List[str]
    created_at: datetime
    expires_at: datetime
    last_used_at: Optional[datetime]
    is_active: bool
    revoked_at: Optional[datetime]
    environment: str


# ---------------------------------------------------------------------------
# Platform Node models
# ---------------------------------------------------------------------------


def _validate_node_nickname(value: str) -> str:
    """Validate node_nickname: a-z, 0-9, hyphens only, max 64 chars."""
    if not re.match(r"^[a-z0-9-]+$", value):
        raise ValueError(
            "node_nickname must contain only lowercase letters, digits, and hyphens"
        )
    if len(value) > 64:
        raise ValueError("node_nickname must be at most 64 characters")
    return value


class PlatformNode(BaseModel):
    """
    Registered platform node (Runner, Worker, Launcher, GateKeeper, etc.).

    Constraint: UNIQUE(user_id, node_nickname) — prevents duplicate nicknames per user,
    but two different users may share the same nickname.
    """

    id: str = Field(default_factory=generate_uuid, description="Unique node UUID")
    user_id: str = Field(..., description="Owner user UUID")
    node_nickname: str = Field(
        ...,
        description=(
            "Short identifier for this node (e.g. 'gpu-workstation'). "
            "Unique per user. Regex: ^[a-z0-9-]+$, max 64 chars."
        ),
    )
    node_type: str = Field(
        ...,
        description="Node type: 'runner', 'worker', 'launcher', or 'edge_node'",
    )
    endpoint_url: str = Field(
        default="",
        description="HTTPS endpoint where this node is reachable",
    )
    platform_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Platform metadata: hostname, os, python_version, gpu_count, etc.",
    )
    registered_at: datetime = Field(
        default_factory=datetime.utcnow, description="Node registration timestamp"
    )
    last_heartbeat: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of the last received heartbeat",
    )
    is_active: bool = Field(
        default=True, description="False when the node has been deregistered"
    )

    @field_validator("node_nickname")
    @classmethod
    def validate_node_nickname(cls, value: str) -> str:
        return _validate_node_nickname(value)

    @field_validator("node_type")
    @classmethod
    def validate_node_type(cls, value: str) -> str:
        allowed = {"runner", "worker", "launcher", "edge_node"}
        if value not in allowed:
            raise ValueError(f"node_type must be one of {allowed}")
        return value


# ---------------------------------------------------------------------------
# Request / Response models for node endpoints
# ---------------------------------------------------------------------------


class RegisterNodeRequest(BaseModel):
    """Request body for POST /api/nodes."""

    node_nickname: str = Field(
        ...,
        description="Unique nickname for this node within the user's account",
    )
    node_type: str = Field(
        ...,
        description="Node type: 'runner', 'worker', 'launcher', or 'edge_node'",
    )
    endpoint_url: str = Field(
        default="", description="HTTPS endpoint for this node"
    )
    platform_info: Dict[str, Any] = Field(
        default_factory=dict, description="Platform metadata"
    )

    @field_validator("node_nickname")
    @classmethod
    def validate_node_nickname(cls, value: str) -> str:
        return _validate_node_nickname(value)

    @field_validator("node_type")
    @classmethod
    def validate_node_type(cls, value: str) -> str:
        allowed = {"runner", "worker", "launcher", "edge_node"}
        if value not in allowed:
            raise ValueError(f"node_type must be one of {allowed}")
        return value


class NodeSummary(BaseModel):
    """Node metadata returned in list/get endpoints."""

    id: str
    node_nickname: str
    node_type: str
    endpoint_url: str
    platform_info: Dict[str, Any]
    registered_at: datetime
    last_heartbeat: datetime
    is_active: bool
