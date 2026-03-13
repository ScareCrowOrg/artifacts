"""
Permission and role models for RBAC (Role-Based Access Control).

This module defines the core models for the ScareVerse permission system:
- Permission: Granular permissions for resources and actions
- Role: Named collections of permissions
- UserRole: Association between users and roles
- RoleEnum: Enumeration of available system roles

Technical naming follows Rule 4.3 (English for all technical identifiers).
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from .base import generate_uuid

# Supported resource types
VALID_RESOURCES = ["cells", "books", "users", "system", "ai_models"]

# Supported action types
VALID_ACTIONS = [
    "create",
    "read",
    "update",
    "delete",
    "use",
    "configure",
    "manage",
    "view_logs",
]


class RoleEnum(str, Enum):
    """
    Available system roles.

    Roles are hierarchical by priority:
    - ADMIN (100): Full system access
    - USER (10): Standard user permissions
    - VIEWER (5): Read-only access
    - GUEST (1): Minimal/no permissions
    """

    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"
    GUEST = "guest"


class Permission(BaseModel):
    """
    Granular permission for a specific resource and action.

    Permissions follow the naming pattern: {resource}.{action}[_{scope}]
    Examples:
    - cells.create (any user can create their own cells)
    - cells.read_own (read own cells)
    - cells.read_any (read any user's cells)
    - cells.delete_any (admin-level permission)
    - system.configure (system configuration)
    """

    id: str = Field(
        default_factory=generate_uuid,
        description="Unique identifier for the permission",
    )
    name: str = Field(
        ...,
        description="Permission name (format: resource.action[_scope])",
        examples=["cells.create", "cells.read_own", "cells.delete_any"],
    )
    description: str = Field(
        ..., description="Human-readable description of what this permission allows"
    )
    resource: str = Field(
        ..., description="Resource type (cells, books, users, system, ai_models)"
    )
    action: str = Field(
        ...,
        description="Action type (create, read, update, delete, use, configure, manage)",
    )
    scope: Optional[str] = Field(
        None,
        description="Scope of permission (own, any, None for no scope restriction)",
    )

    @field_validator("name")
    @classmethod
    def validate_name_format(cls, v: str) -> str:
        """
        Validate permission name follows the format: resource.action[_scope].

        Args:
            v: Permission name to validate

        Returns:
            Validated permission name

        Raises:
            ValueError: If name format is invalid
        """
        parts = v.split(".")
        if len(parts) != 2:
            raise ValueError(
                f"Permission name must follow format 'resource.action[_scope]', got: {v}"
            )

        resource, action_scope = parts
        if not resource or not action_scope:
            raise ValueError(
                f"Permission name cannot have empty resource or action: {v}"
            )

        return v

    @field_validator("resource")
    @classmethod
    def validate_resource(cls, v: str) -> str:
        """
        Validate resource is one of the supported types.

        Args:
            v: Resource name to validate

        Returns:
            Validated resource name

        Raises:
            ValueError: If resource type is not supported
        """
        if v not in VALID_RESOURCES:
            raise ValueError(f"Resource must be one of {VALID_RESOURCES}, got: {v}")
        return v

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """
        Validate action is one of the supported types.

        Args:
            v: Action name to validate

        Returns:
            Validated action name

        Raises:
            ValueError: If action type is not supported
        """
        if v not in VALID_ACTIONS:
            raise ValueError(f"Action must be one of {VALID_ACTIONS}, got: {v}")
        return v


class Role(BaseModel):
    """
    Named collection of permissions.

    Roles define sets of permissions that can be assigned to users.
    Each role has a priority that determines precedence in permission resolution.
    """

    id: str = Field(
        default_factory=generate_uuid, description="Unique identifier for the role"
    )
    name: RoleEnum = Field(
        ..., description="Role name (must be one of RoleEnum values)"
    )
    description: str = Field(
        ...,
        description="Human-readable description of the role's purpose and permissions",
    )
    permissions: List[str] = Field(
        default_factory=list,
        description="List of permission names granted by this role (use ['*'] for all permissions)",
    )
    priority: int = Field(
        ...,
        description="Role priority (higher = more powerful). admin=100, user=10, viewer=5, guest=1",
    )

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: int) -> int:
        """
        Validate priority is within acceptable range.

        Args:
            v: Priority value to validate

        Returns:
            Validated priority value

        Raises:
            ValueError: If priority is negative or unreasonably high
        """
        if v < 0:
            raise ValueError("Role priority cannot be negative")
        if v > 1000:
            raise ValueError("Role priority cannot exceed 1000")
        return v

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: List[str]) -> List[str]:
        """
        Validate permissions list.

        Args:
            v: List of permission names

        Returns:
            Validated permissions list

        Raises:
            ValueError: If permissions format is invalid
        """
        if not isinstance(v, list):
            raise ValueError("Permissions must be a list")

        # Allow wildcard for admin role
        if v == ["*"]:
            return v

        # Validate each permission name format
        for perm in v:
            if not isinstance(perm, str) or "." not in perm:
                raise ValueError(
                    f"Each permission must be a string in format 'resource.action[_scope]', got: {perm}"
                )

        return v


class UserRole(BaseModel):
    """
    Association between a user and a role.

    Tracks when and by whom a role was assigned to a user.
    This model supports audit trails and role management.
    """

    id: str = Field(
        default_factory=generate_uuid,
        description="Unique identifier for this user-role association",
    )
    userId: str = Field(..., description="ID of the user to whom the role is assigned")
    roleId: str = Field(..., description="ID of the role being assigned")
    assignedBy: str = Field(
        ..., description="ID of the admin/user who assigned this role"
    )
    assignedAt: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the role was assigned",
    )

    @field_validator("userId", "roleId", "assignedBy")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """
        Validate that ID fields are not empty.

        Args:
            v: ID value to validate

        Returns:
            Validated ID value

        Raises:
            ValueError: If ID is empty
        """
        if not v or not v.strip():
            raise ValueError("ID fields cannot be empty")
        return v
