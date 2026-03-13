"""
User-related models.

Models for user authentication, registration, and profile management.
"""

import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from .base import generate_uuid

# Reserved nicknames that cannot be used by users.
# These are blocked to prevent conflicts with:
# - System-level API routes (/api, /health)
# - Special built-in identities (system, root, admin)
# - Ambiguous self-reference tokens (me, self, anonymous)
# - Null/empty-like values that may confuse routing logic
_RESERVED_NICKNAMES = frozenset(
    ["admin", "system", "root", "api", "health", "me", "self", "anonymous", "null"]
)


def _validate_nickname(value: Optional[str]) -> Optional[str]:
    """Validate user_nickname: a-z, 0-9, hyphens only, max 64 chars, not reserved."""
    if value is None:
        return value
    if not re.match(r"^[a-z0-9-]+$", value):
        raise ValueError(
            "user_nickname must contain only lowercase letters, digits, and hyphens"
        )
    if len(value) > 64:
        raise ValueError("user_nickname must be at most 64 characters")
    if value in _RESERVED_NICKNAMES:
        raise ValueError(f"'{value}' is a reserved nickname")
    return value


class Mascot(BaseModel):
    """User's AI mascot/agent."""

    name: str = Field(default="ScaryBot", description="Mascot name")
    type: str = Field(default="AI", description="Mascot type")


class GlobalPreferences(BaseModel):
    """User's global application preferences (i18n + theme)."""

    language: str = Field(
        default="en",
        description="User's preferred language (e.g. 'en', 'pt', 'es')",
    )
    theme: str = Field(
        default="light",
        description="User's preferred theme ('light' or 'dark')",
    )

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, value: str) -> str:
        """Validate theme is either 'light' or 'dark'."""
        if value not in ("light", "dark"):
            raise ValueError("theme must be 'light' or 'dark'")
        return value


class User(BaseModel):
    """User/player model."""

    id: str = Field(default_factory=generate_uuid, description="Unique user UUID")
    name: str = Field(..., description="Player name")
    email: str = Field(..., description="User email")
    googleId: Optional[str] = Field(None, description="Google ID for OAuth2")
    hashedPassword: Optional[str] = Field(
        None, description="Hashed password (bcrypt) for alternative authentication"
    )
    registeredAt: datetime = Field(
        default_factory=datetime.utcnow, description="Registration date"
    )
    galaxy: str = Field(default="DefaultGalaxy", description="User galaxy")
    level: int = Field(default=1, ge=1, description="Player level")
    mascot: Mascot = Field(default_factory=Mascot, description="User mascot")
    roles: List[str] = Field(
        default=["user"], description="List of role names assigned to the user (RBAC)"
    )
    permissions: List[str] = Field(
        default=[], description="Direct permissions assigned to the user (RBAC)"
    )
    globalPreferences: GlobalPreferences = Field(
        default_factory=GlobalPreferences,
        description="User's global application preferences (language, theme)",
    )
    user_nickname: Optional[str] = Field(
        None,
        description=(
            "Global network identity nickname (e.g. 'flavio'). "
            "Used for flavio.scareverse.net routing. "
            "Validation: a-z, 0-9, hyphen only; unique per system; max 64 chars."
        ),
    )

    @field_validator("user_nickname")
    @classmethod
    def validate_user_nickname(cls, value: Optional[str]) -> Optional[str]:
        """Validate user_nickname format and reserved words."""
        return _validate_nickname(value)

    def has_role(self, role: str) -> bool:
        """
        Check if user has specific role.

        Args:
            role: Role name to check (e.g., "admin", "editor")

        Returns:
            True if user has the role, False otherwise

        Example:
            if user.has_role("admin"):
                # User is admin
                pass
        """
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        """
        Check if user has specific permission.

        Note: This only checks direct permissions. For complete permission
        resolution (including roles), use RBACValidator._get_user_permissions().

        Args:
            permission: Permission string to check (e.g., "cells.read")

        Returns:
            True if user has the direct permission, False otherwise

        Example:
            if user.has_permission("cells.write"):
                # User can write cells
                pass
        """
        return permission in self.permissions


class RegisterUserRequest(BaseModel):
    """Request to register new user."""

    name: str = Field(..., description="Player name")
    email: str = Field(..., description="User email")


class UpdateUserProfileRequest(BaseModel):
    """Request to update user profile fields."""

    name: Optional[str] = Field(None, description="Updated player name")
    email: Optional[str] = Field(None, description="Updated email address")
    galaxy: Optional[str] = Field(None, description="Updated galaxy")
    mascot: Optional[Mascot] = Field(None, description="Updated mascot settings")
    user_nickname: Optional[str] = Field(
        None, description="Updated global network identity nickname"
    )

    @field_validator("user_nickname")
    @classmethod
    def validate_user_nickname(cls, value: Optional[str]) -> Optional[str]:
        """Validate user_nickname format and reserved words."""
        return _validate_nickname(value)


