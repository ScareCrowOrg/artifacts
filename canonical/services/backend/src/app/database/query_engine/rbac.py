"""
RBAC (Role-Based Access Control) infrastructure for Query Engine.

This module implements a 3-tier access control system:
- Sandbox: User-specific data (owner-based access)
- Canonical: Blueprint/schema data (role-based access)
- Runtime: Operational data (permission-based access)

Features:
- Permission caching in Redis (5 min TTL)
- Role-based permission resolution
- Support for 9 public canonical collections
- Clear error messages for access denials

Usage:
    from app.database.query_engine.rbac import RBACValidator

    rbac = RBACValidator(redis_client, db_client)

    # Validate access (raises exception if denied)
    rbac.validate_access("cells", current_user)

    # Check specific tier access
    has_access = rbac.check_sandbox_access(owner_id, current_user)
"""

import json
import logging
from typing import TYPE_CHECKING, Optional, Set

from .exceptions import QueryEngineException

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from app.database.connection import JSONDatabase
    from app.models.users import User

logger = logging.getLogger(__name__)

# Public collections (always accessible) - 9 public canonical collections
# These are blueprint/schema collections that users can read but not modify
PUBLIC_COLLECTIONS = {
    "notebook_item_types",  # Cell and book type definitions
    "templates",  # Template blueprints
    "workflows",  # Workflow definitions
    "permissions",  # Permission definitions (for UI/documentation)
    "roles",  # Role definitions (for UI/documentation)
    "ai_models",  # AI model configurations
    "content_types",  # Content type schemas
    "agent_types",  # Agent type definitions
    "book_types",  # Book type definitions
}

# Note: The following collections require RBAC checks:
# - cells: User/agent specific instances
# - books: User/agent specific notebooks
# - notebook_items: User/agent specific items
# - contents: User-generated content with versioning


class PermissionError(QueryEngineException):
    """
    Exception raised when user lacks permission to access a resource.

    This is a specialized QueryEngineException for RBAC violations.

    Attributes:
        user_id: The ID of the user who was denied access
        collection: The collection they tried to access
        action: The action they tried to perform (e.g., "read", "write")
    """

    def __init__(
        self,
        message: str,
        user_id: Optional[str] = None,
        collection: Optional[str] = None,
        action: Optional[str] = None,
    ):
        """
        Initialize permission error.

        Args:
            message: Human-readable error message
            user_id: User who was denied access
            collection: Collection that was accessed
            action: Action that was attempted
        """
        details = {}
        if user_id:
            details["user_id"] = user_id
        if collection:
            details["collection"] = collection
        if action:
            details["action"] = action

        super().__init__(message, details)


class RBACValidator:
    """
    RBAC validation for HybridDatabase access.

    Implements 3-tier access control system:
    1. Sandbox: User-specific data (owner-based)
    2. Canonical: Blueprint/schema data (public + role-based)
    3. Runtime: Operational data (permission-based)

    Features:
    - Caches permissions in Redis (5 min TTL)
    - Resolves permissions from roles
    - Validates current_user parameter type
    - Clear error messages for access denials

    Example:
        validator = RBACValidator(redis_client, db_client)

        # Validate access (raises exception if denied)
        validator.validate_access("cells", current_user)

        # Check access without raising
        if validator.check_canonical_access("templates", current_user):
            # Access granted
            pass
    """

    def __init__(
        self,
        redis_client: Optional["Redis"],
        db_client: "JSONDatabase",
    ):
        """
        Initialize RBAC validator.

        Args:
            redis_client: Redis client for permission caching (can be None)
            db_client: Database client for role lookup
        """
        self.redis = redis_client
        self.db = db_client
        self.logger = logger

    def validate_access(
        self,
        collection: str,
        current_user: "User",
    ) -> None:
        """
        Validate user has access to collection.

        This is the main entry point for access validation. It checks:
        1. current_user is provided and correct type
        2. Public collections (always allow)
        3. Admin role (always allow)
        4. User-specific permissions

        Args:
            collection: Collection/table name to access
            current_user: User making the request

        Raises:
            TypeError: If current_user is not provided or wrong type
            PermissionError: If user lacks access to collection

        Example:
            validator.validate_access("cells", current_user)
            # Raises PermissionError if access denied
        """
        # Import User here to avoid circular import
        from app.models.users import User

        # Validate current_user parameter
        if current_user is None:
            raise TypeError(
                "current_user parameter is required for all database operations"
            )

        if not isinstance(current_user, User):
            raise TypeError(
                f"current_user must be User type, got {type(current_user).__name__}"
            )

        # Public collections - always allow
        if collection in PUBLIC_COLLECTIONS:
            self.logger.debug("Access granted to public collection '%s' for user '%s'", collection, current_user.id)
            return

        # Admin role - always allow
        if "admin" in current_user.roles:
            self.logger.debug("Access granted to '%s' for admin user '%s'", collection, current_user.id)
            return

        # Check specific permissions
        permissions = self._get_user_permissions(current_user)

        # Collection-specific permission
        if f"{collection}.read" in permissions:
            self.logger.debug(
                "Access granted to '%s' via collection permission for user '%s'",
                collection, current_user.id
            )
            return

        # Canonical read permission
        if "canonical.read" in permissions:
            self.logger.debug("Access granted to '%s' via canonical.read for user '%s'", collection, current_user.id)
            return

        # No permission found - deny access
        self.logger.warning("Access denied to '%s' for user '%s'", collection, current_user.id)
        raise PermissionError(
            f"User '{current_user.id}' lacks permission to access collection '{collection}'",
            user_id=current_user.id,
            collection=collection,
            action="read",
        )

    def check_sandbox_access(
        self,
        resource_owner_id: str,
        current_user: "User",
    ) -> bool:
        """
        Check if user can access sandbox data.

        Sandbox tier contains user-specific data. Access is granted if:
        1. User is the owner of the resource
        2. User has admin role
        3. User has sandbox.read_any permission

        Args:
            resource_owner_id: ID of the user who owns the resource
            current_user: User making the request

        Returns:
            True if access granted, False otherwise

        Example:
            if validator.check_sandbox_access("user123", current_user):
                # User can access user123's sandbox data
                pass
        """
        # Owner always has access
        if current_user.id == resource_owner_id:
            return True

        # Admin always has access
        if "admin" in current_user.roles:
            return True

        # Check explicit sandbox permission
        permissions = self._get_user_permissions(current_user)
        if "sandbox.read_any" in permissions:
            return True

        return False

    def check_canonical_access(
        self,
        collection: str,
        current_user: "User",
    ) -> bool:
        """
        Check if user can access canonical data.

        Canonical tier contains blueprint/schema data. Access is granted if:
        1. Collection is public (always accessible)
        2. User has admin role
        3. User has collection-specific or canonical.read permission

        Args:
            collection: Collection/table name
            current_user: User making the request

        Returns:
            True if access granted, False otherwise

        Example:
            if validator.check_canonical_access("templates", current_user):
                # User can access template blueprints
                pass
        """
        # Public collections always accessible
        if collection in PUBLIC_COLLECTIONS:
            return True

        # Admin always has access
        if "admin" in current_user.roles:
            return True

        # Check permissions
        permissions = self._get_user_permissions(current_user)

        return f"{collection}.read" in permissions or "canonical.read" in permissions

    def check_runtime_access(
        self,
        collection: str,
        current_user: "User",
    ) -> bool:
        """
        Check if user can access runtime/MongoDB data.

        Runtime tier contains operational data. Access is granted if:
        1. User has admin role
        2. User has collection-specific read permission

        Args:
            collection: Collection/table name
            current_user: User making the request

        Returns:
            True if access granted, False otherwise

        Example:
            if validator.check_runtime_access("notebook_items", current_user):
                # User can access notebook items
                pass
        """
        # Admin always has access
        if "admin" in current_user.roles:
            return True

        # Check collection-specific permission
        permissions = self._get_user_permissions(current_user)
        return f"{collection}.read" in permissions

    def _get_user_permissions(self, current_user: "User") -> Set[str]:
        """
        Get flattened permissions for user (cached 5 min in Redis).

        Aggregates permissions from:
        1. User's roles (resolved from roles collection)
        2. User's direct permissions

        Results are cached in Redis for 5 minutes to improve performance.

        Args:
            current_user: User to get permissions for

        Returns:
            Set of permission strings (e.g., {"cells.read", "books.write"})

        Example:
            perms = validator._get_user_permissions(current_user)
            if "cells.read" in perms:
                # User can read cells
                pass
        """
        cache_key = f"user_permissions:{current_user.id}"

        # Try cache first (5 min TTL)
        if self.redis is not None:
            try:
                cached = self.redis.get(cache_key)
                if cached:
                    self.logger.debug("Permissions cache hit for user '%s'", current_user.id)
                    return set(json.loads(cached))
            except Exception as e:
                self.logger.warning("Failed to read from Redis cache: %s. Falling back to DB.", e)

        # Build from roles + direct permissions
        permissions = set()

        # Add permissions from roles
        for role_name in current_user.roles:
            try:
                # Look up role in canonical roles collection
                # Note: Using JSONDatabase directly (not HybridDatabase)
                # to avoid RBAC loop - we're already inside RBAC validation!
                try:
                    role = self.db.find_one("roles", role_name, is_canonical=True, model_class=None)
                except TypeError:
                    # If find_one doesn't support these params, skip role lookup
                    # RBAC will default to minimal permissions
                    self.logger.warning("Could not load role '%s' - using minimal permissions", role_name)
                    continue

                if role and role.get("permissions"):
                    # Handle wildcard admin permission
                    if "*" in role["permissions"]:
                        # Admin has all permissions - return wildcard
                        permissions.add("*")
                    else:
                        permissions.update(role["permissions"])

                    self.logger.debug("Added %s permissions from role '%s'", len(role['permissions']), role_name)
            except Exception as e:
                self.logger.warning("Failed to load role '%s': %s", role_name, e)

        # Add direct permissions (if user model has permissions field)
        if hasattr(current_user, "permissions") and current_user.permissions:
            permissions.update(current_user.permissions)
            self.logger.debug("Added %s direct permissions", len(current_user.permissions))

        # Cache for 5 minutes
        if self.redis is not None:
            try:
                self.redis.setex(cache_key, 300, json.dumps(list(permissions)))
                self.logger.debug("Cached %s permissions for user '%s'", len(permissions), current_user.id)
            except Exception as e:
                self.logger.warning("Failed to write to Redis cache: %s", e)

        return permissions

    def invalidate_user_permissions(self, user_id: str) -> None:
        """
        Invalidate cached permissions for specific user.

        Call this when:
        - User's roles change
        - User's direct permissions change

        Args:
            user_id: ID of user whose cache should be invalidated

        Example:
            # After updating user roles
            validator.invalidate_user_permissions("user123")
        """
        if self.redis is None:
            return

        cache_key = f"user_permissions:{user_id}"
        try:
            self.redis.delete(cache_key)
            self.logger.info("Invalidated permission cache for user '%s'", user_id)
        except Exception as e:
            self.logger.error("Failed to invalidate cache for user '%s': %s", user_id, e)

    def invalidate_all_permissions(self) -> None:
        """
        Invalidate all cached permissions.

        Call this when:
        - Role definitions change
        - Permission system is updated
        - After bulk user updates

        This operation scans all permission cache keys and deletes them.

        Example:
            # After updating role definitions
            validator.invalidate_all_permissions()
        """
        if self.redis is None:
            return

        pattern = "user_permissions:*"
        deleted_count = 0
        cursor = 0

        try:
            while True:
                cursor, keys = self.redis.scan(cursor, match=pattern, count=100)
                if keys:
                    self.redis.delete(*keys)
                    deleted_count += len(keys)
                if cursor == 0:
                    break

            self.logger.info("Invalidated all permission caches. %s keys deleted.", deleted_count)
        except Exception as e:
            self.logger.error("Failed to invalidate all permission caches: %s", e)


__all__ = [
    "RBACValidator",
    "PermissionError",
    "PUBLIC_COLLECTIONS",
]
