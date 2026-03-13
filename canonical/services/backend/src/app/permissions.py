"""
Authorization and permission control (RBAC) module.

Provides decorators and helpers for validating permissions in FastAPI endpoints.
Implements role-based access control with in-memory caching for performance.

Technical naming follows Rule 4.3 (English for all technical identifiers).
Note: Error messages are in Portuguese as they are user-facing, while all
technical names (functions, variables, parameters) are in English.
"""

import logging
import time
from typing import Callable, Dict, List, Optional, Union

from fastapi import Depends, HTTPException, Request, status

from .audit_logger import log_permission_denied
from .auth_legacy import get_current_user_required
from .database import db
from .models.permissions import Role
from .models.users import User

logger = logging.getLogger(__name__)

# Cache configuration
# Type: Dict[cache_key, Dict[permissions: List[str], timestamp: float]]
_permissions_cache: Dict[str, Dict[str, Union[List[str], float]]] = {}
_CACHE_TTL: int = 300  # 5 minutes in seconds


def _get_cache_key(user_id: str) -> str:
    """
    Generate cache key for user permissions.

    Args:
        user_id: User identifier

    Returns:
        Cache key string
    """
    return f"user_permissions:{user_id}"


def _is_cache_valid(cache_key: str) -> bool:
    """
    Verify if cache entry is still valid.

    Args:
        cache_key: Cache key to check

    Returns:
        True if cache is valid, False otherwise
    """
    if cache_key not in _permissions_cache:
        return False

    cached_data = _permissions_cache[cache_key]
    current_time = time.time()

    return (current_time - cached_data["timestamp"]) < _CACHE_TTL


def _get_cached_permissions(user_id: str) -> Optional[List[str]]:
    """
    Return permissions from cache if valid.

    Args:
        user_id: User identifier

    Returns:
        List of permission names if cache is valid, None otherwise
    """
    cache_key = _get_cache_key(user_id)

    if _is_cache_valid(cache_key):
        logger.debug("Cache hit for user %s", user_id)
        return _permissions_cache[cache_key]["permissions"]

    logger.debug("Cache miss for user %s", user_id)
    return None


def _cache_permissions(user_id: str, permissions: List[str]) -> None:
    """
    Store permissions in cache.

    Args:
        user_id: User identifier
        permissions: List of permission names to cache
    """
    cache_key = _get_cache_key(user_id)
    _permissions_cache[cache_key] = {
        "permissions": permissions,
        "timestamp": time.time(),
    }
    logger.debug("Cached permissions for user %s: %s", user_id, permissions)


def invalidate_user_cache(user_id: str) -> None:
    """
    Invalidate cache for a specific user.

    This should be called when a user's roles or permissions are modified.

    Args:
        user_id: User identifier
    """
    cache_key = _get_cache_key(user_id)
    if cache_key in _permissions_cache:
        del _permissions_cache[cache_key]
        logger.info("Invalidated cache for user %s", user_id)


async def get_user_permissions(user: User) -> List[str]:
    """
    Return list of permissions for a user based on their roles.

    Uses cache to optimize performance. Updates cache if expired.
    Admin users always receive wildcard permission ["*"].

    Args:
        user: Authenticated user

    Returns:
        List of permission names (e.g., ["cells.create", "cells.read_own"])
    """
    # Check cache first
    cached = _get_cached_permissions(user.id)
    if cached is not None:
        return cached

    # Admin has all permissions
    if "admin" in user.roles:
        _cache_permissions(user.id, ["*"])
        return ["*"]

    # Load permissions from all user roles
    all_permissions = set()

    for role_name in user.roles:
        # Search for role in canonical storage
        role = await db.find_by_field(
            "roles", "name", role_name, Role, is_canonical=True
        )

        if role:
            all_permissions.update(role.permissions)
        else:
            logger.warning("Role '%s' not found in database for user %s", role_name, user.id)

    permissions_list = list(all_permissions)

    # Store in cache
    _cache_permissions(user.id, permissions_list)

    return permissions_list


def has_permission(
    required_permissions: List[str], require_all: bool = True
) -> Callable:
    """
    Decorator to validate permissions in FastAPI endpoints.

    Usage:
        @router.delete("/cells/{cell_id}")
        async def delete_cell(
            cell_id: str,
            user = Depends(has_permission(["cells.delete_own"]))
        ):
            ...

    Args:
        required_permissions: List of permissions needed
        require_all: If True, requires all permissions; if False, requires any one

    Returns:
        FastAPI dependency that returns User if authorized

    Raises:
        HTTPException 403: If user lacks required permissions
    """

    async def permission_checker(
        request: Request, current_user: User = Depends(get_current_user_required)
    ) -> User:
        # Admin always authorized
        if "admin" in current_user.roles:
            return current_user

        # Load user permissions
        user_permissions = await get_user_permissions(current_user)

        # Admin has wildcard
        if "*" in user_permissions:
            return current_user

        # Get IP address for audit logging
        ip_address = request.client.host if request and request.client else None
        endpoint = request.url.path if request else "unknown"

        # Validate permissions
        if require_all:
            # Require ALL permissions
            has_all = all(perm in user_permissions for perm in required_permissions)

            if not has_all:
                missing = set(required_permissions) - set(user_permissions)
                logger.warning(
                    "User %s lacks permissions. Required: %s, Missing: %s",
                    current_user.id, required_permissions, list(missing)
                )

                # Audit log the permission denial
                log_permission_denied(
                    user_id=current_user.id,
                    required_permission=", ".join(required_permissions),
                    endpoint=endpoint,
                    ip_address=ip_address,
                )

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "insufficient_permissions",
                        "message": "Você não tem permissões suficientes para esta ação",
                        "required": required_permissions,
                        "missing": list(missing),
                    },
                )
        else:
            # Require ANY permission
            has_any = any(perm in user_permissions for perm in required_permissions)

            if not has_any:
                logger.warning(
                    "User %s lacks any required permission. Required (any): %s",
                    current_user.id, required_permissions
                )

                # Audit log the permission denial
                log_permission_denied(
                    user_id=current_user.id,
                    required_permission=", ".join(required_permissions),
                    endpoint=endpoint,
                    ip_address=ip_address,
                )

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "insufficient_permissions",
                        "message": "Você não tem nenhuma das permissões necessárias",
                        "required_any": required_permissions,
                    },
                )

        return current_user

    return permission_checker


async def require_admin(
    current_user: User = Depends(get_current_user_required),
) -> User:
    """
    Helper for endpoints exclusive to administrators.

    Simplified usage for admin-only endpoints:
        @router.post("/system/config")
        async def update_config(
            config: dict,
            user = Depends(require_admin)
        ):
            ...

    Args:
        current_user: Authenticated user injected by dependency

    Returns:
        User if user is admin

    Raises:
        HTTPException 403: If user is not admin
    """
    if "admin" not in current_user.roles:
        logger.warning("User %s attempted admin-only action without admin role", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "admin_required",
                "message": "Acesso restrito a administradores do sistema",
            },
        )

    return current_user


async def check_resource_ownership(
    resource_user_id: str, current_user: User, admin_permission: str
) -> bool:
    """
    Verify if user owns a resource or has admin permission to access it.

    This helper checks ownership first, then admin role, then specific admin permission.
    Raises HTTPException if user lacks access.

    Args:
        resource_user_id: ID of the user who owns the resource
        current_user: User making the request
        admin_permission: Permission needed for admin override (e.g., "cells.delete_any")

    Returns:
        True if user can access resource

    Raises:
        HTTPException 403: If user is not owner and lacks admin permission
    """
    # User is owner
    if resource_user_id == current_user.id:
        return True

    # Admin always can
    if "admin" in current_user.roles:
        return True

    # Check specific admin permission
    user_permissions = await get_user_permissions(current_user)
    if admin_permission in user_permissions or "*" in user_permissions:
        return True

    # Access denied
    logger.warning(
        "User %s attempted to access resource owned by %s without permission %s",
        current_user.id, resource_user_id, admin_permission
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "resource_forbidden",
            "message": "Você só pode acessar seus próprios recursos",
        },
    )
